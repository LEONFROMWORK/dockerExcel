"""
Constraint validation module - validates data constraints
"""

from typing import List, Any, Optional
import pandas as pd


class ConstraintValidator:
    """Handles constraint validation (unique, required, range, etc.)"""

    def validate_required(self, series: pd.Series, column_name: str) -> List[dict]:
        """Check for missing required values"""
        errors = []
        null_rows = series[series.isnull()].index.tolist()

        for row in null_rows:
            errors.append(
                {
                    "column": column_name,
                    "row": row,
                    "error": "Required value is missing",
                }
            )

        return errors

    def validate_unique(self, series: pd.Series, column_name: str) -> List[dict]:
        """Check for duplicate values"""
        warnings = []
        duplicates = series[series.duplicated()].index.tolist()

        for row in duplicates:
            warnings.append(
                {
                    "column": column_name,
                    "row": row,
                    "warning": f"Duplicate value: {series.iloc[row]}",
                }
            )

        return warnings

    def validate_range(
        self,
        series: pd.Series,
        column_name: str,
        min_val: Optional[Any],
        max_val: Optional[Any],
    ) -> List[dict]:
        """Check if values are within specified range"""
        errors = []

        for idx, value in series.items():
            if pd.isna(value):
                continue

            if min_val is not None and value < min_val:
                errors.append(
                    {
                        "column": column_name,
                        "row": idx,
                        "error": f"Value {value} is below minimum {min_val}",
                    }
                )

            if max_val is not None and value > max_val:
                errors.append(
                    {
                        "column": column_name,
                        "row": idx,
                        "error": f"Value {value} is above maximum {max_val}",
                    }
                )

        return errors

    def validate_allowed_values(
        self, series: pd.Series, column_name: str, allowed_values: List[Any]
    ) -> List[dict]:
        """Check if values are in allowed list"""
        errors = []
        invalid_values = series[~series.isin(allowed_values + [None, pd.NA])]

        for row, value in invalid_values.items():
            errors.append(
                {
                    "column": column_name,
                    "row": row,
                    "error": f"Value '{value}' not in allowed values",
                }
            )

        return errors
