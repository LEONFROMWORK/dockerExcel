"""
NA Fix Strategy
#N/A 오류 수정 전략 구현
"""

from typing import Optional, Dict, Any
from app.services.fixing.strategies.base_fix_strategy import BaseFixStrategy
from app.core.interfaces import ExcelError, FixResult
import re
import logging

logger = logging.getLogger(__name__)


class NAFixStrategy(BaseFixStrategy):
    """#N/A 오류 수정 전략"""

    def can_handle(self, error: ExcelError) -> bool:
        """이 전략이 처리할 수 있는 오류인지 확인"""
        return error.type.lower() in ["#n/a", "na_error", "n/a", "#n/a!"]

    async def apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """#N/A 오류 수정 적용"""
        original_formula = error.formula or ""

        # VLOOKUP/HLOOKUP 관련 #N/A 오류
        if "LOOKUP" in original_formula.upper():
            fixed_formula = self._fix_lookup_na(original_formula)
        # MATCH 관련 #N/A 오류
        elif "MATCH" in original_formula.upper():
            fixed_formula = self._fix_match_na(original_formula)
        # INDEX 관련 #N/A 오류
        elif "INDEX" in original_formula.upper():
            fixed_formula = self._fix_index_na(original_formula)
        else:
            # 일반적인 #N/A 처리
            fixed_formula = self._wrap_with_iferror(original_formula)

        return self._create_success_result(
            error=error,
            fixed_formula=fixed_formula,
            confidence=0.85,
            message="#N/A 오류를 IFERROR로 처리했습니다",
            original_formula=original_formula,
        )

    def get_confidence(self, error: ExcelError) -> float:
        """수정 신뢰도 반환"""
        # LOOKUP 함수들은 더 높은 신뢰도
        if error.formula and "LOOKUP" in error.formula.upper():
            return 0.9
        return 0.8

    def _fix_lookup_na(self, formula: str) -> str:
        """VLOOKUP/HLOOKUP #N/A 수정"""
        # VLOOKUP 패턴 찾기
        vlookup_pattern = r"(=?\s*VLOOKUP\s*\([^)]+\))"
        hlookup_pattern = r"(=?\s*HLOOKUP\s*\([^)]+\))"

        if re.search(vlookup_pattern, formula, re.IGNORECASE) or re.search(
            hlookup_pattern, formula, re.IGNORECASE
        ):
            # IFERROR로 감싸기
            return self._wrap_with_iferror(formula)

        # XLOOKUP 사용 가능한 경우 대체 제안
        if "VLOOKUP" in formula.upper():
            # VLOOKUP을 XLOOKUP으로 변환하는 로직 (Excel 365)
            # 기본적으로 IFERROR 처리
            return self._wrap_with_iferror(formula)

        return formula

    def _fix_match_na(self, formula: str) -> str:
        """MATCH 함수 #N/A 수정"""
        # MATCH 함수를 IFERROR로 감싸기 (기본값 0)
        return self._wrap_with_iferror(formula, 0)

    def _fix_index_na(self, formula: str) -> str:
        """INDEX 함수 #N/A 수정"""
        # INDEX 함수를 IFERROR로 감싸기
        return self._wrap_with_iferror(formula)
