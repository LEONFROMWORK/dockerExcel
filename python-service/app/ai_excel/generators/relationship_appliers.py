"""
Relationship appliers - handles data relationships between columns
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod


class RelationshipApplier(ABC):
    """Base class for relationship appliers"""
    
    @abstractmethod
    def apply(self, data: pd.DataFrame, relationship: Dict[str, Any]) -> pd.DataFrame:
        """Apply relationship between columns"""
        pass


class DerivedRelationshipApplier(RelationshipApplier):
    """Handles derived relationships (formulas)"""
    
    def apply(self, data: pd.DataFrame, relationship: Dict[str, Any]) -> pd.DataFrame:
        """Apply derived relationship"""
        source_col = relationship.get("source")
        target_col = relationship.get("target")
        formula = relationship.get("formula")
        
        if source_col not in data.columns or target_col not in data.columns:
            return data
        
        if formula == "multiply":
            factor = relationship.get("factor", 1.1)
            data[target_col] = data[source_col] * factor
        elif formula == "percentage":
            percentage = relationship.get("percentage", 0.1)
            data[target_col] = data[source_col] * percentage
        elif formula == "add":
            value = relationship.get("value", 0)
            data[target_col] = data[source_col] + value
        elif formula == "subtract":
            value = relationship.get("value", 0)
            data[target_col] = data[source_col] - value
        
        return data


class CorrelatedRelationshipApplier(RelationshipApplier):
    """Handles correlated relationships"""
    
    def apply(self, data: pd.DataFrame, relationship: Dict[str, Any]) -> pd.DataFrame:
        """Apply correlated relationship"""
        source_col = relationship.get("source")
        target_col = relationship.get("target")
        correlation = relationship.get("correlation", 0.8)
        
        if source_col not in data.columns or target_col not in data.columns:
            return data
        
        # Add correlated noise
        source_std = data[source_col].std()
        noise_std = source_std * np.sqrt(1 - correlation**2)
        
        data[target_col] = (
            data[source_col] * correlation +
            np.random.normal(0, noise_std, len(data))
        )
        
        return data


class RelationshipApplierFactory:
    """Factory for creating relationship appliers"""
    
    def __init__(self):
        self.appliers = {
            "derived": DerivedRelationshipApplier(),
            "correlated": CorrelatedRelationshipApplier()
        }
    
    def apply_relationships(self, data: pd.DataFrame, relationships: List[Dict[str, Any]]) -> pd.DataFrame:
        """Apply all relationships to data"""
        for relationship in relationships:
            rel_type = relationship.get("type")
            if rel_type in self.appliers:
                applier = self.appliers[rel_type]
                data = applier.apply(data, relationship)
        
        return data