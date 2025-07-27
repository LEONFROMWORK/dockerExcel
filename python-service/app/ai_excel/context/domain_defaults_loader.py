"""
Domain defaults loader - Extracted from ContextBuilder
Loads domain-specific default configurations
"""

from typing import Dict, Any
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DomainDefaultsLoader:
    """Loads domain-specific default configurations"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._get_default_config_path()
        self._cache = {}
    
    def _get_default_config_path(self) -> str:
        """Get default configuration path"""
        return str(Path(__file__).parent / "configs" / "domain_defaults.json")
    
    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """Load all domain defaults"""
        if self._cache:
            return self._cache
        
        # Try to load from config file first
        try:
            self._cache = self._load_from_file()
            return self._cache
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}")
            # Fallback to hardcoded defaults
            self._cache = self._get_hardcoded_defaults()
            return self._cache
    
    def load_domain(self, domain: str) -> Dict[str, Any]:
        """Load defaults for specific domain"""
        all_defaults = self.load_all()
        return all_defaults.get(domain, self._get_general_defaults())
    
    def _load_from_file(self) -> Dict[str, Dict[str, Any]]:
        """Load defaults from configuration file"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_hardcoded_defaults(self) -> Dict[str, Dict[str, Any]]:
        """Get hardcoded defaults as fallback"""
        return {
            "finance": self._get_finance_defaults(),
            "hr": self._get_hr_defaults(),
            "sales": self._get_sales_defaults(),
            "inventory": self._get_inventory_defaults(),
            "project": self._get_project_defaults()
        }
    
    def _get_finance_defaults(self) -> Dict[str, Any]:
        """Get finance domain defaults"""
        return {
            "default_sheets": ["손익계산서", "재무상태표", "현금흐름표", "재무비율"],
            "required_columns": {
                "손익계산서": ["항목", "당기", "전기", "증감액", "증감률"],
                "재무상태표": ["계정과목", "당기", "전기", "구성비"],
                "현금흐름표": ["구분", "금액", "비고"]
            },
            "default_period": "annual",
            "currency": "KRW",
            "number_format": "#,##0원"
        }
    
    def _get_hr_defaults(self) -> Dict[str, Any]:
        """Get HR domain defaults"""
        return {
            "default_sheets": ["직원명부", "급여현황", "근태관리", "조직도"],
            "required_columns": {
                "직원명부": ["사번", "성명", "부서", "직급", "입사일"],
                "급여현황": ["사번", "성명", "기본급", "수당", "공제", "실수령액"],
                "근태관리": ["사번", "성명", "출근일수", "결근", "휴가"]
            },
            "default_period": "monthly",
            "privacy_level": "high"
        }
    
    def _get_sales_defaults(self) -> Dict[str, Any]:
        """Get sales domain defaults"""
        return {
            "default_sheets": ["매출현황", "고객분석", "제품별실적", "영업활동"],
            "required_columns": {
                "매출현황": ["일자", "고객명", "제품", "수량", "단가", "금액"],
                "고객분석": ["고객명", "매출액", "거래횟수", "평균구매액"],
                "제품별실적": ["제품명", "판매량", "매출액", "이익률"]
            },
            "default_period": "monthly",
            "include_charts": True
        }
    
    def _get_inventory_defaults(self) -> Dict[str, Any]:
        """Get inventory domain defaults"""
        return {
            "default_sheets": ["재고현황", "입출고내역", "재고회전율", "ABC분석"],
            "required_columns": {
                "재고현황": ["품목코드", "품목명", "현재고", "안전재고", "재주문점"],
                "입출고내역": ["일자", "구분", "품목", "수량", "단가", "금액"],
                "ABC분석": ["품목", "매출액", "누적비율", "등급"]
            },
            "calculations": ["재고회전율", "재고일수"],
            "alerts": ["재주문필요", "과잉재고"]
        }
    
    def _get_project_defaults(self) -> Dict[str, Any]:
        """Get project domain defaults"""
        return {
            "default_sheets": ["프로젝트개요", "일정관리", "리소스배치", "진행현황"],
            "required_columns": {
                "일정관리": ["작업명", "시작일", "종료일", "담당자", "진행률"],
                "리소스배치": ["담당자", "역할", "투입률", "작업"],
                "진행현황": ["단계", "계획", "실적", "달성률"]
            },
            "visualizations": ["gantt_chart", "progress_chart"],
            "date_format": "YYYY-MM-DD"
        }
    
    def _get_general_defaults(self) -> Dict[str, Any]:
        """Get general defaults for unknown domains"""
        return {
            "default_sheets": ["데이터"],
            "required_columns": {},
            "default_period": "monthly"
        }