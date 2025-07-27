"""
Business rules loader - Extracted from ContextBuilder
Loads domain-specific business rules
"""

from typing import Dict, List, Any
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BusinessRulesLoader:
    """Loads domain-specific business rules"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._get_default_config_path()
        self._cache = {}
    
    def _get_default_config_path(self) -> str:
        """Get default configuration path"""
        return str(Path(__file__).parent / "configs" / "business_rules.json")
    
    def load_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load all business rules"""
        if self._cache:
            return self._cache
        
        try:
            self._cache = self._load_from_file()
            return self._cache
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}")
            self._cache = self._get_hardcoded_rules()
            return self._cache
    
    def load_domain_rules(self, domain: str) -> List[Dict[str, Any]]:
        """Load rules for specific domain"""
        all_rules = self.load_all()
        return all_rules.get(domain, [])
    
    def _load_from_file(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load rules from configuration file"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_hardcoded_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get hardcoded rules as fallback"""
        return {
            "finance": self._get_finance_rules(),
            "hr": self._get_hr_rules(),
            "sales": self._get_sales_rules(),
            "inventory": self._get_inventory_rules()
        }
    
    def _get_finance_rules(self) -> List[Dict[str, Any]]:
        """Get finance business rules"""
        return [
            {
                "rule": "balance_sheet_equation",
                "description": "자산 = 부채 + 자본",
                "validation": "assets == liabilities + equity",
                "priority": "high"
            },
            {
                "rule": "profit_calculation",
                "description": "당기순이익 = 매출 - 비용",
                "formula": "net_income = revenue - expenses",
                "priority": "high"
            },
            {
                "rule": "gross_margin",
                "description": "매출총이익 = 매출 - 매출원가",
                "formula": "gross_profit = revenue - cogs",
                "priority": "medium"
            }
        ]
    
    def _get_hr_rules(self) -> List[Dict[str, Any]]:
        """Get HR business rules"""
        return [
            {
                "rule": "salary_calculation",
                "description": "실수령액 = 기본급 + 수당 - 공제",
                "formula": "net_pay = base_salary + allowances - deductions",
                "priority": "high"
            },
            {
                "rule": "working_days",
                "description": "근무일수 체크",
                "validation": "working_days <= calendar_days",
                "priority": "medium"
            },
            {
                "rule": "overtime_limit",
                "description": "초과근무 제한",
                "validation": "overtime_hours <= 52",
                "priority": "high"
            }
        ]
    
    def _get_sales_rules(self) -> List[Dict[str, Any]]:
        """Get sales business rules"""
        return [
            {
                "rule": "revenue_calculation",
                "description": "매출액 = 수량 × 단가",
                "formula": "revenue = quantity * unit_price",
                "priority": "high"
            },
            {
                "rule": "profit_margin",
                "description": "이익률 = (매출 - 원가) / 매출",
                "formula": "margin = (revenue - cost) / revenue",
                "priority": "medium"
            },
            {
                "rule": "discount_limit",
                "description": "할인율 제한",
                "validation": "discount_rate <= 0.3",
                "priority": "low"
            }
        ]
    
    def _get_inventory_rules(self) -> List[Dict[str, Any]]:
        """Get inventory business rules"""
        return [
            {
                "rule": "reorder_point",
                "description": "재주문점 = 일평균사용량 × 리드타임 + 안전재고",
                "formula": "reorder_point = avg_daily_usage * lead_time + safety_stock",
                "priority": "high"
            },
            {
                "rule": "inventory_turnover",
                "description": "재고회전율 = 매출원가 / 평균재고",
                "formula": "turnover = cogs / avg_inventory",
                "priority": "medium"
            },
            {
                "rule": "safety_stock",
                "description": "안전재고 = (최대사용량 - 평균사용량) × 리드타임",
                "formula": "safety_stock = (max_usage - avg_usage) * lead_time",
                "priority": "medium"
            }
        ]
    
    def get_rules_by_priority(self, domain: str, priority: str) -> List[Dict[str, Any]]:
        """Get rules filtered by priority"""
        rules = self.load_domain_rules(domain)
        return [r for r in rules if r.get("priority") == priority]
    
    def validate_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Validate a business rule against data"""
        if "validation" in rule:
            try:
                # Simple evaluation - in production, use safer evaluation
                return eval(rule["validation"], {"__builtins__": {}}, data)
            except Exception as e:
                logger.error(f"Rule validation failed: {e}")
                return False
        return True