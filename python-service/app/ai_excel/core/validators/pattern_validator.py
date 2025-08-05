"""
Pattern validation module - validates data against patterns
"""

from typing import List, Dict
import pandas as pd
import re


class PatternValidator:
    """Handles pattern-based validation"""

    def __init__(self):
        self.predefined_patterns = {
            "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "phone_kr": r"^(\+82|0)[-.\s]?\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4}$",
            "phone_us": r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$",
            "url": r"^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b",
            "postal_code_kr": r"^\d{5}$",
            "postal_code_us": r"^\d{5}(-\d{4})?$",
            "ssn_kr": r"^\d{6}-[1-4]\d{6}$",  # Korean Resident Registration Number pattern
            "business_no_kr": r"^\d{3}-\d{2}-\d{5}$",  # Korean Business Registration Number
        }

    def validate(self, series: pd.Series, column_name: str, pattern: str) -> List[dict]:
        """Validate series against pattern"""
        errors = []

        # Use predefined pattern if available
        if pattern in self.predefined_patterns:
            pattern = self.predefined_patterns[pattern]

        try:
            compiled_pattern = re.compile(pattern)
        except re.error:
            return [
                {
                    "column": column_name,
                    "row": -1,
                    "error": f"Invalid regex pattern: {pattern}",
                }
            ]

        for idx, value in series.items():
            if pd.isna(value):
                continue

            if not compiled_pattern.match(str(value)):
                errors.append(
                    {
                        "column": column_name,
                        "row": idx,
                        "error": f"Value '{value}' doesn't match pattern",
                    }
                )

        return errors

    def add_pattern(self, name: str, pattern: str):
        """Add a new predefined pattern"""
        self.predefined_patterns[name] = pattern

    def get_available_patterns(self) -> Dict[str, str]:
        """Get all available predefined patterns"""
        return self.predefined_patterns.copy()
