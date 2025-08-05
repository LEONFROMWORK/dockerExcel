"""
Standardized Response Builders
표준화된 응답 빌더 - 일관된 API 응답 생성
"""

from typing import Any, Dict, Optional
from datetime import datetime
import uuid
import traceback
import logging

from app.core.types import StandardErrorResponse, StandardSuccessResponse, ErrorSeverity

logger = logging.getLogger(__name__)


class ResponseBuilder:
    """표준 응답 빌더"""

    @staticmethod
    def success(
        data: Any, message: Optional[str] = None, request_id: Optional[str] = None
    ) -> StandardSuccessResponse:
        """
        성공 응답 생성

        Args:
            data: 응답 데이터
            message: 선택적 메시지
            request_id: 요청 ID

        Returns:
            표준 성공 응답
        """
        return {
            "status": "success",
            "data": data,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id or str(uuid.uuid4()),
        }

    @staticmethod
    def error(
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> StandardErrorResponse:
        """
        에러 응답 생성

        Args:
            message: 에러 메시지
            error_code: 에러 코드
            details: 추가 상세 정보
            request_id: 요청 ID

        Returns:
            표준 에러 응답
        """
        return {
            "status": "error",
            "message": message,
            "error_code": error_code,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id or str(uuid.uuid4()),
        }

    @staticmethod
    def from_exception(
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        include_traceback: bool = False,
        request_id: Optional[str] = None,
    ) -> StandardErrorResponse:
        """
        예외로부터 에러 응답 생성

        Args:
            exception: 예외 객체
            context: 추가 컨텍스트
            include_traceback: 스택 트레이스 포함 여부
            request_id: 요청 ID

        Returns:
            표준 에러 응답
        """
        error_code = exception.__class__.__name__
        message = str(exception)

        details = context or {}

        if include_traceback:
            details["traceback"] = traceback.format_exc()

        # 로깅
        logger.error(f"Exception occurred: {error_code} - {message}", exc_info=True)

        return ResponseBuilder.error(
            message=message,
            error_code=error_code,
            details=details,
            request_id=request_id,
        )

    @staticmethod
    def validation_error(
        field: str, message: str, value: Any = None, request_id: Optional[str] = None
    ) -> StandardErrorResponse:
        """
        검증 오류 응답 생성

        Args:
            field: 오류 필드
            message: 오류 메시지
            value: 잘못된 값
            request_id: 요청 ID

        Returns:
            표준 에러 응답
        """
        return ResponseBuilder.error(
            message=f"Validation error: {message}",
            error_code="VALIDATION_ERROR",
            details={"field": field, "message": message, "value": value},
            request_id=request_id,
        )

    @staticmethod
    def not_found(
        resource: str, identifier: Any, request_id: Optional[str] = None
    ) -> StandardErrorResponse:
        """
        리소스 없음 응답 생성

        Args:
            resource: 리소스 타입
            identifier: 리소스 식별자
            request_id: 요청 ID

        Returns:
            표준 에러 응답
        """
        return ResponseBuilder.error(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
            request_id=request_id,
        )

    @staticmethod
    def unauthorized(
        message: str = "Unauthorized access", request_id: Optional[str] = None
    ) -> StandardErrorResponse:
        """
        인증 오류 응답 생성

        Args:
            message: 오류 메시지
            request_id: 요청 ID

        Returns:
            표준 에러 응답
        """
        return ResponseBuilder.error(
            message=message, error_code="UNAUTHORIZED", request_id=request_id
        )

    @staticmethod
    def rate_limited(
        retry_after: int, limit: int, request_id: Optional[str] = None
    ) -> StandardErrorResponse:
        """
        속도 제한 응답 생성

        Args:
            retry_after: 재시도 가능 시간 (초)
            limit: 제한 수
            request_id: 요청 ID

        Returns:
            표준 에러 응답
        """
        return ResponseBuilder.error(
            message=f"Rate limit exceeded. Try again after {retry_after} seconds",
            error_code="RATE_LIMITED",
            details={"retry_after": retry_after, "limit": limit},
            request_id=request_id,
        )


class ExcelErrorBuilder:
    """Excel 특화 에러 빌더"""

    @staticmethod
    def formula_error(
        cell: str,
        sheet: str,
        formula: str,
        error_type: str,
        suggestion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        수식 오류 정보 생성

        Args:
            cell: 셀 주소
            sheet: 시트명
            formula: 수식
            error_type: 오류 타입
            suggestion: 수정 제안

        Returns:
            수식 오류 정보
        """
        return {
            "type": "FORMULA_ERROR",
            "severity": ErrorSeverity.HIGH,
            "cell": cell,
            "sheet": sheet,
            "message": f"Formula error in {cell}: {error_type}",
            "details": {"formula": formula, "error_type": error_type},
            "is_auto_fixable": suggestion is not None,
            "suggested_fix": suggestion,
        }

    @staticmethod
    def data_quality_error(
        cell: str,
        sheet: str,
        issue: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> Dict[str, Any]:
        """
        데이터 품질 오류 정보 생성

        Args:
            cell: 셀 주소
            sheet: 시트명
            issue: 문제 설명
            severity: 심각도

        Returns:
            데이터 품질 오류 정보
        """
        return {
            "type": "DATA_QUALITY",
            "severity": severity,
            "cell": cell,
            "sheet": sheet,
            "message": f"Data quality issue in {cell}: {issue}",
            "details": {"issue": issue},
            "is_auto_fixable": False,
            "suggested_fix": None,
        }
