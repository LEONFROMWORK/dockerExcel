"""
Context builder for constructing rich context from parsed information
Enriches parsed context with business logic and domain knowledge
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import logging

from .parser import ContextParser
from .domain_defaults_loader import DomainDefaultsLoader
from .business_rules_loader import BusinessRulesLoader
from .date_range_parser import DateRangeParser

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds enriched context for Excel generation"""
    
    def __init__(self):
        self.parser = ContextParser()
        self.defaults_loader = DomainDefaultsLoader()
        self.rules_loader = BusinessRulesLoader()
        self.domain_defaults = self.defaults_loader.load_all()
        self.business_rules = self.rules_loader.load_all()
    
    def build(self, user_request: str, additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build complete context from user request"""
        # Parse the request
        parsed_context = self.parser.parse(user_request)
        
        # Merge with additional context
        if additional_context:
            parsed_context = self._merge_contexts(parsed_context, additional_context)
        
        # Apply domain defaults
        enriched_context = self._apply_domain_defaults(parsed_context)
        
        # Apply business rules
        enriched_context = self._apply_business_rules(enriched_context)
        
        # Generate data specifications
        enriched_context["data_specs"] = self._generate_data_specs(enriched_context)
        
        # Add generation hints
        enriched_context["generation_hints"] = self._generate_hints(enriched_context)
        
        return enriched_context
    
    
    def _merge_contexts(self, parsed: Dict[str, Any], additional: Dict[str, Any]) -> Dict[str, Any]:
        """Merge parsed context with additional context"""
        merged = parsed.copy()
        
        # Deep merge for nested dictionaries
        for key, value in additional.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key].update(value)
            else:
                merged[key] = value
        
        return merged
    
    def _apply_domain_defaults(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply domain-specific defaults"""
        domain = context.get("domain")
        
        if domain and domain in self.domain_defaults:
            defaults = self.domain_defaults[domain]
            
            # Add default sheets if not specified
            if "sheets" not in context:
                context["sheets"] = defaults["default_sheets"]
            
            # Add required columns
            context["required_columns"] = defaults.get("required_columns", {})
            
            # Add other domain-specific settings
            for key, value in defaults.items():
                if key not in ["default_sheets", "required_columns"] and key not in context:
                    context[key] = value
        
        return context
    
    def _apply_business_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply business rules to context"""
        domain = context.get("domain")
        
        if domain and domain in self.business_rules:
            context["business_rules"] = self.business_rules[domain]
        
        return context
    
    def _generate_data_specs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data specifications based on context"""
        specs = {
            "row_count": self._estimate_row_count(context),
            "date_range": self._determine_date_range(context),
            "data_patterns": self._determine_data_patterns(context),
            "calculations": self._determine_calculations(context)
        }
        
        return specs
    
    def _estimate_row_count(self, context: Dict[str, Any]) -> int:
        """Estimate number of rows needed"""
        # Check if explicitly specified
        if context.get("constraints", {}).get("size_limits"):
            return context["constraints"]["size_limits"]
        
        # Domain-based estimation
        domain = context.get("domain")
        time_context = context.get("time_context", {})
        
        if domain == "finance":
            # Financial statements typically have 20-50 line items
            return 30
        elif domain == "hr":
            # Based on company size if mentioned
            counts = context.get("entities", {}).get("counts", [])
            for count in counts:
                if count.get("unit") == "명":
                    return count["value"]
            return 50  # Default
        elif domain == "sales":
            # Monthly data = 30 days, quarterly = 90, yearly = 365
            if time_context.get("duration"):
                duration = time_context["duration"]
                if duration["unit"] == "months":
                    return duration["value"] * 30
            return 100  # Default
        else:
            return 50  # General default
    
    def _determine_date_range(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine date range for data generation"""
        time_context = context.get("time_context", {})
        parser = DateRangeParser(time_context)
        return parser.parse()
    
    def _determine_period_type(self, start_date: date, end_date: date) -> str:
        """Determine the period type based on date range"""
        days = (end_date - start_date).days
        
        if days <= 31:
            return "monthly"
        elif days <= 93:
            return "quarterly"
        elif days <= 366:
            return "annual"
        else:
            return "multi_year"
    
    def _determine_data_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine data generation patterns"""
        domain = context.get("domain")
        requirements = context.get("requirements", [])
        
        patterns = {
            "trends": "stable",  # stable, growth, decline, seasonal
            "volatility": "low",  # low, medium, high
            "seasonality": False,
            "outliers": False
        }
        
        # Adjust based on domain
        if domain == "sales":
            patterns["seasonality"] = True
            patterns["trends"] = "growth"
        elif domain == "finance":
            patterns["volatility"] = "medium"
        
        # Adjust based on requirements
        if "forecast" in requirements:
            patterns["trends"] = "growth"
        if "analysis" in requirements:
            patterns["outliers"] = True
        
        return patterns
    
    def _determine_calculations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Determine required calculations"""
        domain = context.get("domain")
        calculations = []
        
        if domain == "finance":
            calculations.extend([
                {"name": "total", "type": "sum", "columns": ["amount"]},
                {"name": "growth_rate", "type": "percentage_change", "columns": ["current", "previous"]},
                {"name": "ratio_analysis", "type": "custom", "formula": "various financial ratios"}
            ])
        elif domain == "sales":
            calculations.extend([
                {"name": "revenue", "type": "multiply", "columns": ["quantity", "unit_price"]},
                {"name": "profit_margin", "type": "margin", "columns": ["revenue", "cost"]},
                {"name": "cumulative", "type": "running_total", "columns": ["revenue"]}
            ])
        
        return calculations
    
    def _generate_hints(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate hints for the AI generator"""
        hints = {
            "complexity_level": self._determine_complexity(context),
            "emphasis_areas": self._determine_emphasis(context),
            "formatting_style": self._determine_style(context),
            "language_tone": "professional",
            "include_explanations": False
        }
        
        # Adjust based on constraints
        constraints = context.get("constraints", {})
        if "simple" in constraints.get("format_constraints", []):
            hints["complexity_level"] = "basic"
            hints["include_explanations"] = False
        elif "detailed" in constraints.get("format_constraints", []):
            hints["complexity_level"] = "advanced"
            hints["include_explanations"] = True
        
        return hints
    
    def _determine_complexity(self, context: Dict[str, Any]) -> str:
        """Determine complexity level"""
        requirements = context.get("requirements", [])
        
        if len(requirements) > 5:
            return "advanced"
        elif len(requirements) > 2:
            return "intermediate"
        else:
            return "basic"
    
    def _determine_emphasis(self, context: Dict[str, Any]) -> List[str]:
        """Determine areas to emphasize"""
        emphasis = []
        requirements = context.get("requirements", [])
        
        if "visualization" in requirements:
            emphasis.append("charts")
        if "analysis" in requirements:
            emphasis.append("insights")
        if "comparison" in requirements:
            emphasis.append("trends")
        
        return emphasis
    
    def _determine_style(self, context: Dict[str, Any]) -> str:
        """Determine formatting style"""
        domain = context.get("domain")
        
        style_map = {
            "finance": "formal",
            "hr": "structured",
            "sales": "dynamic",
            "inventory": "functional",
            "project": "visual"
        }
        
        return style_map.get(domain, "standard")