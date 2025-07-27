"""
Constraint appliers - handles different types of data constraints
"""

from typing import Dict, Any, Optional
import pandas as pd
from abc import ABC, abstractmethod


class ConstraintApplier(ABC):
    """Base class for constraint appliers"""
    
    @abstractmethod
    def apply(self, data: pd.DataFrame, constraints: Dict[str, Any]) -> pd.DataFrame:
        """Apply constraints to data"""
        pass


class ColumnConstraintApplier(ConstraintApplier):
    """Applies column-level constraints"""
    
    def apply(self, data: pd.DataFrame, constraints: Dict[str, Any]) -> pd.DataFrame:
        """Apply column constraints"""
        column_constraints = constraints.get("columns", {})
        
        for col_name, col_constraints in column_constraints.items():
            if col_name not in data.columns:
                continue
            
            data = self._apply_min_max(data, col_name, col_constraints)
            data = self._apply_unique(data, col_name, col_constraints)
            data = self._apply_allowed_values(data, col_name, col_constraints)
        
        return data
    
    def _apply_min_max(self, data: pd.DataFrame, col_name: str, constraints: Dict[str, Any]) -> pd.DataFrame:
        """Apply min/max constraints"""
        if "min" in constraints:
            data[col_name] = data[col_name].clip(lower=constraints["min"])
        if "max" in constraints:
            data[col_name] = data[col_name].clip(upper=constraints["max"])
        return data
    
    def _apply_unique(self, data: pd.DataFrame, col_name: str, constraints: Dict[str, Any]) -> pd.DataFrame:
        """Apply unique constraint"""
        if constraints.get("unique", False):
            data[col_name] = data[col_name].astype(str) + "_" + data.index.astype(str)
        return data
    
    def _apply_allowed_values(self, data: pd.DataFrame, col_name: str, constraints: Dict[str, Any]) -> pd.DataFrame:
        """Apply allowed values constraint"""
        if "allowed_values" in constraints:
            allowed = constraints["allowed_values"]
            # Replace non-allowed values with the first allowed value
            mask = ~data[col_name].isin(allowed)
            if mask.any() and allowed:
                data.loc[mask, col_name] = allowed[0]
        return data


class GlobalConstraintApplier(ConstraintApplier):
    """Applies global constraints across columns"""
    
    def apply(self, data: pd.DataFrame, constraints: Dict[str, Any]) -> pd.DataFrame:
        """Apply global constraints"""
        data = self._apply_total_sum(data, constraints)
        data = self._apply_row_sum(data, constraints)
        return data
    
    def _apply_total_sum(self, data: pd.DataFrame, constraints: Dict[str, Any]) -> pd.DataFrame:
        """Apply total sum constraints"""
        if "total_sum" not in constraints:
            return data
        
        for col_name, target_sum in constraints["total_sum"].items():
            if col_name in data.columns:
                current_sum = data[col_name].sum()
                if current_sum != 0:
                    data[col_name] = data[col_name] * (target_sum / current_sum)
        
        return data
    
    def _apply_row_sum(self, data: pd.DataFrame, constraints: Dict[str, Any]) -> pd.DataFrame:
        """Apply row sum constraints"""
        if "row_sum" not in constraints:
            return data
        
        row_sum_config = constraints["row_sum"]
        columns = row_sum_config.get("columns", [])
        target = row_sum_config.get("target", 100)
        
        if all(col in data.columns for col in columns):
            row_sums = data[columns].sum(axis=1)
            for col in columns:
                data[col] = data[col] / row_sums * target
        
        return data


class ConstraintManager:
    """Manages all constraint applications"""
    
    def __init__(self):
        self.appliers = [
            ColumnConstraintApplier(),
            GlobalConstraintApplier()
        ]
    
    def apply_constraints(self, data: pd.DataFrame, constraints: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """Apply all constraints to data"""
        if not constraints:
            return data
        
        for applier in self.appliers:
            data = applier.apply(data, constraints)
        
        return data