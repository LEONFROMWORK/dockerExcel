"""
Type validation module - validates data types
"""

from typing import List, Tuple, Any
import pandas as pd
import re
from datetime import datetime, date
from ..validation import DataType


class TypeValidator:
    """Handles data type validation"""

    def __init__(self):
        self.patterns = {
            "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "phone_kr": r"^(\+82|0)[-.\s]?\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4}$",
            "phone_us": r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$",
            "url": r"^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b",
        }

    def validate(
        self, series: pd.Series, expected_type: DataType
    ) -> List[Tuple[int, str]]:
        """Validate series values against expected type"""
        errors = []

        for idx, value in series.items():
            if pd.isna(value):
                continue

            error = self._validate_single_value(value, expected_type)
            if error:
                errors.append((idx, error))

        return errors

    def _validate_single_value(self, value: Any, expected_type: DataType) -> str:
        """Validate a single value"""
        try:
            if expected_type == DataType.NUMBER:
                return self._validate_number(value)
            elif expected_type == DataType.CURRENCY:
                return self._validate_currency(value)
            elif expected_type == DataType.PERCENTAGE:
                return self._validate_percentage(value)
            elif expected_type == DataType.DATE:
                return self._validate_date(value)
            elif expected_type == DataType.BOOLEAN:
                return self._validate_boolean(value)
            elif expected_type == DataType.EMAIL:
                return self._validate_email(value)
            elif expected_type == DataType.URL:
                return self._validate_url(value)
            elif expected_type == DataType.PHONE:
                return self._validate_phone(value)
            else:
                return None  # Text type, always valid
        except (ValueError, TypeError) as e:
            return f"Invalid {expected_type.value}: {str(e)}"

    def _validate_number(self, value: Any) -> str:
        """Validate numeric value"""
        try:
            float(value)
            return None
        except (ValueError, TypeError):
            return "Not a valid number"

    def _validate_currency(self, value: Any) -> str:
        """Validate currency value"""
        try:
            # Remove currency symbols and check if numeric
            cleaned = str(value).replace("원", "").replace("$", "").replace(",", "")
            float(cleaned)
            return None
        except (ValueError, TypeError):
            return "Not a valid currency value"

    def _validate_percentage(self, value: Any) -> str:
        """Validate percentage value"""
        try:
            if isinstance(value, str):
                cleaned = value.replace("%", "")
                float(cleaned)
            else:
                float(value)
            return None
        except (ValueError, TypeError):
            return "Not a valid percentage"

    def _validate_date(self, value: Any) -> str:
        """Validate date value"""
        if isinstance(value, (datetime, date)):
            return None
        try:
            pd.to_datetime(value)
            return None
        except Exception:
            return "Not a valid date"

    def _validate_boolean(self, value: Any) -> str:
        """Validate boolean value"""
        if value in [True, False, 1, 0, "true", "false", "True", "False"]:
            return None
        return "Not a boolean value"

    def _validate_email(self, value: Any) -> str:
        """Validate email format"""
        if re.match(self.patterns["email"], str(value)):
            return None
        return "Invalid email format"

    def _validate_url(self, value: Any) -> str:
        """Validate URL format"""
        if re.match(self.patterns["url"], str(value)):
            return None
        return "Invalid URL format"

    def _validate_phone(self, value: Any) -> str:
        """Validate phone number format"""
        value_str = str(value)
        # Try both Korean and US formats
        if re.match(self.patterns["phone_kr"], value_str) or re.match(
            self.patterns["phone_us"], value_str
        ):
            return None
        return "Invalid phone number format"
