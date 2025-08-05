"""
결과 생성 팩토리
중복 코드 제거를 위한 통합 결과 생성
"""

from typing import Optional
from app.core.interfaces import FixResult, ExcelError
import uuid
from datetime import datetime


class ResultFactory:
    """결과 생성 팩토리 클래스"""

    @staticmethod
    def create_error_result(
        error: ExcelError, message: str, original_formula: Optional[str] = None
    ) -> FixResult:
        """오류 결과 생성"""
        return FixResult(
            success=False,
            error_id=error.id,
            original_formula=original_formula or error.formula or "",
            fixed_formula="",
            confidence=0.0,
            applied=False,
            message=message,
        )

    @staticmethod
    def create_success_result(
        error: ExcelError, fixed_formula: str, confidence: float, message: str = ""
    ) -> FixResult:
        """성공 결과 생성"""
        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=error.formula or "",
            fixed_formula=fixed_formula,
            confidence=confidence,
            applied=False,
            message=message,
        )

    @staticmethod
    def create_skip_result(error: ExcelError, reason: str) -> FixResult:
        """건너뛰기 결과 생성"""
        return FixResult(
            success=False,
            error_id=error.id,
            original_formula=error.formula or "",
            fixed_formula="",
            confidence=0.0,
            applied=False,
            message=f"건너뜀: {reason}",
            skipped=True,  # 추가 필드
        )

    @staticmethod
    def create_partial_result(
        error: ExcelError, fixed_formula: str, confidence: float, warning: str
    ) -> FixResult:
        """부분 성공 결과 생성"""
        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=error.formula or "",
            fixed_formula=fixed_formula,
            confidence=confidence,
            applied=False,
            message=f"부분 수정: {warning}",
            partial=True,  # 추가 필드
        )

    @staticmethod
    def generate_fix_id() -> str:
        """수정 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"fix_{timestamp}_{unique_id}"
