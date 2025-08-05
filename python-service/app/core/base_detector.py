"""
Base Error Detector
모든 오류 감지기의 기본 클래스 - DRY 원칙 적용
"""

from typing import List, Any, Optional, Tuple
from abc import ABC, abstractmethod
from app.core.interfaces import IErrorDetector, ExcelError
from app.core.excel_utils import ExcelUtils
import re
import logging
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class BaseErrorDetector(IErrorDetector, ABC):
    """모든 오류 감지기의 기본 클래스"""

    # 셀 주소 패턴 (공통 사용)
    CELL_PATTERN = re.compile(r"([A-Z]+)(\d+)")

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._cache = {}

    @abstractmethod
    async def detect(self, workbook: Any) -> List[ExcelError]:
        """서브클래스에서 구현해야 하는 감지 메서드"""

    @abstractmethod
    def can_detect(self, error_type: str) -> bool:
        """서브클래스에서 구현해야 하는 감지 가능 여부 메서드"""

    # === 공통 유틸리티 메서드 ===

    def _create_error(
        self,
        error_id: str,
        error_type: str,
        sheet: str,
        cell: str,
        message: str,
        severity: str = "medium",
        is_auto_fixable: bool = False,
        suggested_fix: Optional[str] = None,
        formula: Optional[str] = None,
        value: Any = None,
        confidence: float = 0.85,
    ) -> ExcelError:
        """표준화된 오류 객체 생성"""
        return ExcelError(
            id=error_id,
            type=error_type,
            sheet=sheet,
            cell=cell,
            formula=formula,
            value=value,
            message=message,
            severity=severity,
            is_auto_fixable=is_auto_fixable,
            suggested_fix=suggested_fix,
            confidence=confidence,
        )

    def _generate_error_id(self, sheet: str, cell: str, error_type: str) -> str:
        """고유한 오류 ID 생성"""
        # 더 짧고 의미있는 ID 생성
        type_abbr = "".join(word[0] for word in error_type.split("_"))
        return f"{sheet}_{cell}_{type_abbr}_{datetime.now().strftime('%H%M%S')}"

    def _parse_cell_reference(self, cell_ref: str) -> Tuple[str, int]:
        """셀 참조를 열과 행으로 분리"""
        return ExcelUtils.parse_cell_reference(cell_ref)

    def _column_to_index(self, column: str) -> int:
        """열 문자를 인덱스로 변환 (A=0, B=1, ...)"""
        return ExcelUtils.column_to_index(column)

    def _index_to_column(self, index: int) -> str:
        """인덱스를 열 문자로 변환 (0=A, 1=B, ...)"""
        return ExcelUtils.index_to_column(index)

    def _get_cell_value_safe(self, cell: Any) -> Any:
        """셀 값을 안전하게 가져오기"""
        try:
            if hasattr(cell, "value"):
                return cell.value
            return cell
        except Exception as e:
            self.logger.warning(f"셀 값 읽기 오류: {str(e)}")
            return None

    def _get_cell_formula_safe(self, cell: Any) -> Optional[str]:
        """셀 수식을 안전하게 가져오기"""
        try:
            if hasattr(cell, "data_type") and cell.data_type == "f":
                return cell.value
            return None
        except Exception as e:
            self.logger.warning(f"셀 수식 읽기 오류: {str(e)}")
            return None

    def _is_error_value(self, value: Any) -> bool:
        """값이 Excel 오류인지 확인"""
        return ExcelUtils.is_error_value(value)

    def _get_severity_from_error_type(self, error_type: str) -> str:
        """오류 타입으로부터 심각도 추정"""
        critical_keywords = ["circular", "corrupt", "invalid_reference"]
        high_keywords = ["error", "missing", "broken"]
        low_keywords = ["style", "warning", "suggestion"]

        error_lower = error_type.lower()

        if any(keyword in error_lower for keyword in critical_keywords):
            return "critical"
        elif any(keyword in error_lower for keyword in high_keywords):
            return "high"
        elif any(keyword in error_lower for keyword in low_keywords):
            return "low"
        return "medium"

    def _calculate_confidence(self, checks_passed: int, total_checks: int) -> float:
        """신뢰도 계산"""
        if total_checks == 0:
            return 0.5
        base_confidence = checks_passed / total_checks
        # 0.5 ~ 0.95 범위로 정규화
        return 0.5 + (base_confidence * 0.45)

    def _get_cache_key(self, *args) -> str:
        """캐시 키 생성"""
        key_parts = [str(arg) for arg in args]
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _log_detection_start(self, sheet_name: str, total_cells: int):
        """감지 시작 로깅"""
        self.logger.info(f"시트 '{sheet_name}' 오류 감지 시작 (셀 수: {total_cells})")

    def _log_detection_complete(
        self, sheet_name: str, errors_found: int, time_taken: float
    ):
        """감지 완료 로깅"""
        self.logger.info(
            f"시트 '{sheet_name}' 오류 감지 완료: "
            f"{errors_found}개 오류 발견, {time_taken:.2f}초 소요"
        )
