"""
Data validation module for AI Excel generation
Ensures data integrity and business rule compliance
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime, date
import pandas as pd
import re
from enum import Enum
from pydantic import BaseModel, Field, validator
import logging

from .validators import (
    TypeValidator,
    ConstraintValidator,
    PatternValidator,
    CustomRuleValidator
)

logger = logging.getLogger(__name__)


class DataType(str, Enum):
    """Supported data types for Excel columns"""
    TEXT = "text"
    NUMBER = "number"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"


class ValidationRule(BaseModel):
    """Validation rule definition"""
    rule_type: str
    parameters: Dict[str, Any]
    error_message: Optional[str] = None


class ColumnSchema(BaseModel):
    """Schema definition for a column"""
    name: str
    data_type: DataType
    required: bool = False
    unique: bool = False
    min_value: Optional[Union[float, int, date]] = None
    max_value: Optional[Union[float, int, date]] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None
    custom_rules: Optional[List[ValidationRule]] = None


class DataValidator:
    """Validates data against defined schemas"""
    
    def __init__(self):
        self.validation_results = []
        self.type_validator = TypeValidator()
        self.constraint_validator = ConstraintValidator()
        self.pattern_validator = PatternValidator()
        self.custom_rule_validator = CustomRuleValidator()
    
    def validate_dataframe(self, df: pd.DataFrame, schema: List[ColumnSchema]) -> Dict[str, Any]:
        """Validate entire DataFrame against schema"""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "summary": {}
        }
        
        # Create schema map
        schema_map = {col.name: col for col in schema}
        
        # Check for missing required columns
        for col_schema in schema:
            if col_schema.required and col_schema.name not in df.columns:
                results["errors"].append({
                    "column": col_schema.name,
                    "error": "Required column missing"
                })
                results["valid"] = False
        
        # Validate each column
        for column in df.columns:
            if column in schema_map:
                col_results = self._validate_column(df[column], schema_map[column])
                if col_results["errors"]:
                    results["errors"].extend(col_results["errors"])
                    results["valid"] = False
                if col_results["warnings"]:
                    results["warnings"].extend(col_results["warnings"])
        
        # Summary statistics
        results["summary"] = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "error_count": len(results["errors"]),
            "warning_count": len(results["warnings"])
        }
        
        return results
    
    def _validate_column(self, series: pd.Series, schema: ColumnSchema) -> Dict[str, Any]:
        """Validate a single column using specialized validators"""
        results = {"errors": [], "warnings": []}
        
        # Type validation
        type_errors = self.type_validator.validate(series, schema.data_type)
        if type_errors:
            results["errors"].extend([{
                "column": schema.name,
                "row": row,
                "error": error,
                "value": series.iloc[row] if row < len(series) else None
            } for row, error in type_errors])
        
        # Constraint validations
        if schema.required:
            results["errors"].extend(
                self.constraint_validator.validate_required(series, schema.name)
            )
        
        if schema.unique:
            results["warnings"].extend(
                self.constraint_validator.validate_unique(series, schema.name)
            )
        
        if schema.min_value is not None or schema.max_value is not None:
            results["errors"].extend(
                self.constraint_validator.validate_range(
                    series, schema.name, schema.min_value, schema.max_value
                )
            )
        
        if schema.allowed_values:
            results["errors"].extend(
                self.constraint_validator.validate_allowed_values(
                    series, schema.name, schema.allowed_values
                )
            )
        
        # Pattern validation
        if schema.pattern:
            results["errors"].extend(
                self.pattern_validator.validate(series, schema.name, schema.pattern)
            )
        
        # Custom rules
        if schema.custom_rules:
            for rule in schema.custom_rules:
                results["errors"].extend(
                    self.custom_rule_validator.validate(series, schema.name, rule)
                )
        
        return results
    
    # Legacy methods are now handled by specialized validators
    # These can be removed in a future refactoring
    
    def validate_excel_structure(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Excel structure definition"""
        results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required fields
        if "sheets" not in structure:
            results["errors"].append("Missing 'sheets' in structure")
            results["valid"] = False
            return results
        
        # Validate each sheet
        for sheet in structure["sheets"]:
            if "name" not in sheet:
                results["errors"].append("Sheet missing 'name' field")
                results["valid"] = False
            
            if "columns" not in sheet:
                results["errors"].append(f"Sheet '{sheet.get('name', 'Unknown')}' missing 'columns'")
                results["valid"] = False
        
        return results