"""
Custom rule validation module - applies custom validation rules
"""

from typing import List, Dict, Any
import pandas as pd
from ..validation import ValidationRule


class CustomRuleValidator:
    """Handles custom validation rules"""
    
    def validate(self, series: pd.Series, column_name: str, rule: ValidationRule) -> List[dict]:
        """Apply custom validation rule"""
        failed_indices = self._apply_rule(series, rule)
        
        errors = []
        for idx in failed_indices:
            errors.append({
                "column": column_name,
                "row": idx,
                "error": rule.error_message or f"Custom rule '{rule.rule_type}' failed"
            })
        
        return errors
    
    def _apply_rule(self, series: pd.Series, rule: ValidationRule) -> List[int]:
        """Apply specific rule type"""
        if rule.rule_type == "sum_equals":
            return self._validate_sum_equals(series, rule.parameters)
        elif rule.rule_type == "sum_between":
            return self._validate_sum_between(series, rule.parameters)
        elif rule.rule_type == "all_positive":
            return self._validate_all_positive(series)
        elif rule.rule_type == "all_negative":
            return self._validate_all_negative(series)
        elif rule.rule_type == "monotonic_increasing":
            return self._validate_monotonic_increasing(series)
        elif rule.rule_type == "monotonic_decreasing":
            return self._validate_monotonic_decreasing(series)
        elif rule.rule_type == "standard_deviation":
            return self._validate_standard_deviation(series, rule.parameters)
        else:
            return []
    
    def _validate_sum_equals(self, series: pd.Series, params: Dict[str, Any]) -> List[int]:
        """Validate that sum equals expected value"""
        expected_sum = params.get("value")
        if expected_sum is None:
            return []
        
        actual_sum = series.sum()
        if abs(actual_sum - expected_sum) > 0.001:  # Allow small floating point differences
            return series.index.tolist()
        return []
    
    def _validate_sum_between(self, series: pd.Series, params: Dict[str, Any]) -> List[int]:
        """Validate that sum is between min and max"""
        min_sum = params.get("min")
        max_sum = params.get("max")
        actual_sum = series.sum()
        
        if (min_sum is not None and actual_sum < min_sum) or \
           (max_sum is not None and actual_sum > max_sum):
            return series.index.tolist()
        return []
    
    def _validate_all_positive(self, series: pd.Series) -> List[int]:
        """Validate all values are positive"""
        negative_indices = series[series < 0].index.tolist()
        return negative_indices
    
    def _validate_all_negative(self, series: pd.Series) -> List[int]:
        """Validate all values are negative"""
        positive_indices = series[series > 0].index.tolist()
        return positive_indices
    
    def _validate_monotonic_increasing(self, series: pd.Series) -> List[int]:
        """Validate values are monotonically increasing"""
        failed_indices = []
        for i in range(1, len(series)):
            if series.iloc[i] < series.iloc[i-1]:
                failed_indices.append(series.index[i])
        return failed_indices
    
    def _validate_monotonic_decreasing(self, series: pd.Series) -> List[int]:
        """Validate values are monotonically decreasing"""
        failed_indices = []
        for i in range(1, len(series)):
            if series.iloc[i] > series.iloc[i-1]:
                failed_indices.append(series.index[i])
        return failed_indices
    
    def _validate_standard_deviation(self, series: pd.Series, params: Dict[str, Any]) -> List[int]:
        """Validate standard deviation is within bounds"""
        max_std = params.get("max")
        if max_std is None:
            return []
        
        std = series.std()
        if std > max_std:
            # Return indices of outliers (values beyond 2 std deviations)
            mean = series.mean()
            outliers = series[abs(series - mean) > 2 * std]
            return outliers.index.tolist()
        return []