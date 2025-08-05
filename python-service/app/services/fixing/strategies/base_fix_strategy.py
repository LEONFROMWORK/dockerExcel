"""
Base Fix Strategy
모든 Fix Strategy의 기본 클래스 - DRY 원칙 적용
"""

from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from app.core.interfaces import IErrorFixStrategy, ExcelError, FixResult
import logging

logger = logging.getLogger(__name__)


class BaseFixStrategy(IErrorFixStrategy, ABC):
    """모든 Fix Strategy의 기본 클래스"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def can_handle(self, error: ExcelError) -> bool:
        """서브클래스에서 구현해야 하는 처리 가능 여부 메서드"""

    @abstractmethod
    async def apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """서브클래스에서 구현해야 하는 수정 적용 메서드"""

    @abstractmethod
    def get_confidence(self, error: ExcelError) -> float:
        """서브클래스에서 구현해야 하는 신뢰도 계산 메서드"""

    # === 공통 유틸리티 메서드 ===

    def _create_error_result(
        self, error: ExcelError, error_msg: str, original_formula: Optional[str] = None
    ) -> FixResult:
        """표준화된 오류 결과 생성"""
        return FixResult(
            success=False,
            error_id=error.id,
            original_formula=original_formula or error.formula or "",
            fixed_formula="",
            confidence=0.0,
            applied=False,
            message=f"수정 실패: {error_msg}",
        )

    def _create_success_result(
        self,
        error: ExcelError,
        fixed_formula: str,
        confidence: float,
        message: str,
        original_formula: Optional[str] = None,
    ) -> FixResult:
        """표준화된 성공 결과 생성"""
        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=original_formula or error.formula or "",
            fixed_formula=fixed_formula,
            confidence=confidence,
            applied=False,
            message=message,
        )

    async def safe_apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """예외 처리를 포함한 안전한 수정 적용"""
        try:
            return await self.apply_fix(error, context)
        except Exception as e:
            self.logger.error(f"{self.__class__.__name__} fix failed: {str(e)}")
            return self._create_error_result(error, str(e))

    def _is_cell_reference(self, text: str) -> bool:
        """셀 참조인지 확인 (공통 유틸리티)"""
        import re

        cell_pattern = r"^[A-Z]+\d+$"
        range_pattern = r"^[A-Z]+\d+:[A-Z]+\d+$"
        sheet_pattern = r"^[A-Za-z0-9_]+![A-Z]+\d+$"

        return bool(
            re.match(cell_pattern, text, re.IGNORECASE)
            or re.match(range_pattern, text, re.IGNORECASE)
            or re.match(sheet_pattern, text, re.IGNORECASE)
        )

    def _extract_formula_content(self, formula: str) -> str:
        """수식에서 = 기호 제거"""
        return formula.lstrip("=").strip()

    def _wrap_with_iferror(self, formula: str, default_value: Any = '""') -> str:
        """수식을 IFERROR로 감싸기"""
        formula_content = self._extract_formula_content(formula)
        return f"=IFERROR({formula_content}, {default_value})"
