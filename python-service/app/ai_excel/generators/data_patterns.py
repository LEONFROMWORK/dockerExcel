"""
Data pattern appliers - handles different types of data patterns
"""

from typing import Dict, Any
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod


class PatternApplier(ABC):
    """Base class for pattern appliers"""

    @abstractmethod
    def apply(
        self, data: pd.DataFrame, col_name: str, pattern_spec: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply pattern to column"""


class SeasonalPatternApplier(PatternApplier):
    """Applies seasonal patterns to data"""

    def __init__(self):
        self.seasonal_func = lambda base, period: base * (
            1 + 0.1 * np.sin(2 * np.pi * period / 12)
        )

    def apply(
        self, data: pd.DataFrame, col_name: str, pattern_spec: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply seasonal pattern"""
        values = data[col_name].values
        base_value = values[0]

        for i in range(1, len(values)):
            values[i] = self.seasonal_func(base_value, i)

        data[col_name] = values
        return data


class TrendPatternApplier(PatternApplier):
    """Applies trend patterns (growth, decline) to data"""

    def apply(
        self, data: pd.DataFrame, col_name: str, pattern_spec: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply trend pattern"""
        values = data[col_name].values
        rate = pattern_spec.get("parameters", {}).get("rate", 0.05)
        pattern_type = pattern_spec.get("type", "growth")

        multiplier = 1 + rate if pattern_type == "growth" else 1 - rate

        for i in range(1, len(values)):
            values[i] = values[i - 1] * multiplier

        data[col_name] = values
        return data


class StablePatternApplier(PatternApplier):
    """Applies stable pattern with small variations"""

    def apply(
        self, data: pd.DataFrame, col_name: str, pattern_spec: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply stable pattern with small random variations"""
        values = data[col_name].values
        std_dev = np.std(values) * 0.02  # 2% variation

        for i in range(1, len(values)):
            values[i] = values[i - 1] + np.random.normal(0, std_dev)

        data[col_name] = values
        return data


class PatternApplierFactory:
    """Factory for creating pattern appliers"""

    def __init__(self):
        self.appliers = {
            "seasonal": SeasonalPatternApplier(),
            "growth": TrendPatternApplier(),
            "decline": TrendPatternApplier(),
            "stable": StablePatternApplier(),
        }

    def get_applier(self, pattern_type: str) -> PatternApplier:
        """Get appropriate applier for pattern type"""
        return self.appliers.get(pattern_type, self.appliers["stable"])

    def apply_patterns(
        self, data: pd.DataFrame, patterns: Dict[str, Dict[str, Any]]
    ) -> pd.DataFrame:
        """Apply all patterns to data"""
        for col_name, pattern_spec in patterns.items():
            if col_name in data.columns:
                pattern_type = pattern_spec.get("type", "stable")
                applier = self.get_applier(pattern_type)
                data = applier.apply(data, col_name, pattern_spec)

        return data
