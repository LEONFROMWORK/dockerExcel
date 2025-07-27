"""
AI-powered data generator for creating contextual, realistic data
Uses GPT-4 to generate data that matches business context
"""

import json
import logging
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

from ...services.openai_service import openai_service
from .data_patterns import PatternApplierFactory
from .relationship_appliers import RelationshipApplierFactory
from .constraint_appliers import ConstraintManager

logger = logging.getLogger(__name__)


class AIDataGenerator:
    """Generates contextual data using AI"""
    
    def __init__(self):
        self.pattern_factory = PatternApplierFactory()
        self.relationship_factory = RelationshipApplierFactory()
        self.constraint_manager = ConstraintManager()
    
    async def generate_contextual_data(
        self,
        schema: Dict[str, Any],
        context: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Generate data that matches the context and constraints"""
        
        try:
            # Use AI to generate realistic data patterns
            data_spec = await self._get_ai_data_specification(schema, context, constraints)
            
            # Generate base data
            base_data = self._generate_base_data(schema, data_spec)
            
            # Apply patterns and relationships
            patterned_data = self._apply_data_patterns(base_data, data_spec)
            
            # Apply constraints
            constrained_data = self._apply_constraints(patterned_data, constraints)
            
            # Validate data
            validated_data = self._validate_generated_data(constrained_data, schema)
            
            return validated_data
            
        except Exception as e:
            logger.error(f"AI data generation failed: {str(e)}")
            # Fallback to simple data generation
            return self._generate_fallback_data(schema)
    
    async def _get_ai_data_specification(
        self,
        schema: Dict[str, Any],
        context: Dict[str, Any],
        constraints: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get AI-generated data specification"""
        
        system_prompt = """You are a data generation expert. Based on the schema and context provided,
        create a detailed specification for generating realistic business data.
        
        Return a JSON object with:
        {
            "data_characteristics": {
                "patterns": {}, // Growth patterns for each column
                "relationships": [], // Relationships between columns
                "distributions": {}, // Statistical distributions
                "ranges": {} // Value ranges for each column
            },
            "sample_values": {}, // Example values for each column
            "generation_rules": [] // Specific rules for data generation
        }
        """
        
        user_prompt = f"""Schema: {json.dumps(schema)}
        Context: {json.dumps(context)}
        Constraints: {json.dumps(constraints) if constraints else 'None'}
        
        Generate a data specification that creates realistic data matching this business context."""
        
        response = await openai_service.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI data specification: {response}")
            return self._get_default_data_specification(schema, context)
    
    def _generate_base_data(self, schema: Dict[str, Any], data_spec: Dict[str, Any]) -> pd.DataFrame:
        """Generate base data according to specification"""
        
        columns = schema.get("columns", [])
        row_count = schema.get("row_count", 100)
        
        data = {}
        sample_values = data_spec.get("sample_values", {})
        ranges = data_spec.get("data_characteristics", {}).get("ranges", {})
        
        for col in columns:
            col_name = col["name"]
            data_type = col.get("data_type", "text")
            
            if col_name in sample_values:
                # Use AI-suggested sample values
                values = self._expand_sample_values(
                    sample_values[col_name], row_count, data_type
                )
            else:
                # Generate based on data type and ranges
                values = self._generate_column_data(
                    col_name, data_type, row_count,
                    ranges.get(col_name, {})
                )
            
            data[col_name] = values
        
        return pd.DataFrame(data)
    
    def _expand_sample_values(
        self,
        samples: List[Any],
        row_count: int,
        data_type: str
    ) -> List[Any]:
        """Expand sample values to fill required rows"""
        
        if not samples:
            return self._generate_default_values(data_type, row_count)
        
        values = []
        
        if data_type in ["number", "currency"]:
            # Interpolate between samples
            base_values = [float(s) for s in samples]
            for i in range(row_count):
                idx = (i * len(base_values)) // row_count
                if idx < len(base_values) - 1:
                    # Linear interpolation
                    fraction = (i * len(base_values) / row_count) - idx
                    value = base_values[idx] + fraction * (base_values[idx + 1] - base_values[idx])
                else:
                    value = base_values[-1]
                values.append(value + np.random.normal(0, value * 0.05))  # Add small variation
        
        elif data_type == "text":
            # Cycle through samples with variations
            for i in range(row_count):
                base_value = samples[i % len(samples)]
                if isinstance(base_value, str) and base_value.endswith(("1", "2", "3")):
                    # Replace number suffix
                    values.append(base_value[:-1] + str((i % 10) + 1))
                else:
                    values.append(base_value)
        
        elif data_type == "date":
            # Generate date sequence
            start_date = pd.to_datetime(samples[0])
            end_date = pd.to_datetime(samples[-1]) if len(samples) > 1 else start_date + timedelta(days=row_count)
            values = pd.date_range(start=start_date, end=end_date, periods=row_count).tolist()
        
        else:
            # Default: repeat samples
            values = [samples[i % len(samples)] for i in range(row_count)]
        
        return values
    
    def _generate_column_data(
        self,
        col_name: str,
        data_type: str,
        row_count: int,
        value_range: Dict[str, Any]
    ) -> List[Any]:
        """Generate data for a single column"""
        
        if data_type == "number" or data_type == "currency":
            min_val = value_range.get("min", 1000)
            max_val = value_range.get("max", 1000000)
            distribution = value_range.get("distribution", "normal")
            
            if distribution == "normal":
                mean = (min_val + max_val) / 2
                std = (max_val - min_val) / 6  # 99.7% within range
                values = np.random.normal(mean, std, row_count)
                values = np.clip(values, min_val, max_val)
            elif distribution == "uniform":
                values = np.random.uniform(min_val, max_val, row_count)
            else:
                values = np.random.exponential((max_val - min_val) / 3, row_count) + min_val
            
            return values.tolist()
        
        elif data_type == "percentage":
            min_val = value_range.get("min", 0)
            max_val = value_range.get("max", 1)
            values = np.random.beta(2, 2, row_count) * (max_val - min_val) + min_val
            return values.tolist()
        
        elif data_type == "date":
            start_date = pd.to_datetime(value_range.get("start", datetime.now() - timedelta(days=365)))
            end_date = pd.to_datetime(value_range.get("end", datetime.now()))
            dates = pd.date_range(start=start_date, end=end_date, periods=row_count)
            return dates.tolist()
        
        elif data_type == "boolean":
            probability = value_range.get("true_probability", 0.5)
            return np.random.choice([True, False], row_count, p=[probability, 1-probability]).tolist()
        
        else:  # text
            prefix = value_range.get("prefix", col_name)
            return [f"{prefix}_{i+1}" for i in range(row_count)]
    
    def _apply_data_patterns(self, data: pd.DataFrame, data_spec: Dict[str, Any]) -> pd.DataFrame:
        """Apply patterns and relationships to data"""
        
        patterns = data_spec.get("data_characteristics", {}).get("patterns", {})
        relationships = data_spec.get("data_characteristics", {}).get("relationships", [])
        
        # Apply patterns using factory
        data = self.pattern_factory.apply_patterns(data, patterns)
        
        # Apply relationships using factory
        data = self.relationship_factory.apply_relationships(data, relationships)
        
        return data
    
    def _apply_constraints(self, data: pd.DataFrame, constraints: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """Apply constraints to generated data"""
        return self.constraint_manager.apply_constraints(data, constraints)
    
    def _validate_generated_data(self, data: pd.DataFrame, schema: Dict[str, Any]) -> pd.DataFrame:
        """Validate and fix generated data"""
        
        # Ensure correct data types
        for col in schema.get("columns", []):
            col_name = col["name"]
            data_type = col.get("data_type", "text")
            
            if col_name in data.columns:
                if data_type in ["number", "currency"]:
                    data[col_name] = pd.to_numeric(data[col_name], errors="coerce").fillna(0)
                elif data_type == "percentage":
                    data[col_name] = pd.to_numeric(data[col_name], errors="coerce").fillna(0)
                    data[col_name] = data[col_name].clip(0, 1)
                elif data_type == "date":
                    data[col_name] = pd.to_datetime(data[col_name], errors="coerce")
        
        return data
    
    def _generate_fallback_data(self, schema: Dict[str, Any]) -> pd.DataFrame:
        """Generate simple fallback data"""
        
        columns = schema.get("columns", [])
        row_count = schema.get("row_count", 10)
        
        data = {}
        for col in columns:
            col_name = col["name"]
            data_type = col.get("data_type", "text")
            
            data[col_name] = self._generate_default_values(data_type, row_count)
        
        return pd.DataFrame(data)
    
    def _generate_default_values(self, data_type: str, count: int) -> List[Any]:
        """Generate default values for a data type"""
        
        if data_type in ["number", "currency"]:
            return [random.randint(1000, 100000) for _ in range(count)]
        elif data_type == "percentage":
            return [random.random() for _ in range(count)]
        elif data_type == "date":
            base_date = datetime.now()
            return [base_date - timedelta(days=i) for i in range(count)]
        elif data_type == "boolean":
            return [random.choice([True, False]) for _ in range(count)]
        else:
            return [f"Item {i+1}" for i in range(count)]
    
    def _get_default_data_specification(self, schema: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Get default data specification when AI fails"""
        
        domain = context.get("domain", "general")
        
        # Domain-specific defaults
        domain_specs = {
            "finance": {
                "data_characteristics": {
                    "patterns": {
                        "revenue": {"type": "growth", "parameters": {"rate": 0.05}},
                        "costs": {"type": "growth", "parameters": {"rate": 0.03}}
                    },
                    "relationships": [
                        {
                            "source": "revenue",
                            "target": "profit",
                            "type": "derived",
                            "formula": "percentage",
                            "percentage": 0.15
                        }
                    ]
                }
            },
            "sales": {
                "data_characteristics": {
                    "patterns": {
                        "sales": {"type": "seasonal", "parameters": {}},
                        "customers": {"type": "growth", "parameters": {"rate": 0.02}}
                    }
                }
            }
        }
        
        return domain_specs.get(domain, {
            "data_characteristics": {
                "patterns": {},
                "relationships": [],
                "distributions": {},
                "ranges": {}
            }
        })