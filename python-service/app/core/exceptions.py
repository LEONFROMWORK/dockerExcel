"""
Custom Exceptions for Excel Services
Excel 서비스 커스텀 예외 정의 (강화된 오류 처리)
"""
from typing import Optional, Dict, Any, List
from enum import Enum


class ErrorSeverity(Enum):
    """오류 심각도 레벨"""
    CRITICAL = "critical"    # 변환 불가능
    HIGH = "high"           # 주요 기능 손실
    MEDIUM = "medium"       # 일부 기능 손실
    LOW = "low"            # 경미한 문제
    WARNING = "warning"     # 주의 사항


class ErrorCategory(Enum):
    """오류 카테고리"""
    FILE_FORMAT = "file_format"           # 파일 형식 오류
    MEMORY = "memory"                     # 메모리 부족
    PERMISSION = "permission"             # 권한 오류
    CORRUPTION = "corruption"             # 파일 손상
    FEATURE_UNSUPPORTED = "unsupported"   # 지원하지 않는 기능
    PERFORMANCE = "performance"           # 성능 문제
    NETWORK = "network"                   # 네트워크 오류


class ExcelServiceError(Exception):
    """Excel 서비스 기본 예외 (강화 버전)"""
    def __init__(
        self, 
        message: str, 
        code: str = None, 
        details: dict = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.FILE_FORMAT,
        user_message: Optional[str] = None,
        recovery_suggestions: Optional[List[str]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code or "GENERIC_ERROR"
        self.details = details or {}
        self.severity = severity
        self.category = category
        self.user_message = user_message or self._generate_user_message()
        self.recovery_suggestions = recovery_suggestions or self._generate_recovery_suggestions()
    
    def _generate_user_message(self) -> str:
        """사용자 친화적 메시지 생성"""
        user_messages = {
            ErrorCategory.FILE_FORMAT: "Excel 파일 형식에 문제가 있습니다.",
            ErrorCategory.MEMORY: "파일이 너무 커서 처리할 수 없습니다.",
            ErrorCategory.PERMISSION: "파일에 접근할 수 있는 권한이 없습니다.",
            ErrorCategory.CORRUPTION: "Excel 파일이 손상되었습니다.",
            ErrorCategory.FEATURE_UNSUPPORTED: "이 Excel 파일의 일부 기능은 지원되지 않습니다.",
            ErrorCategory.PERFORMANCE: "파일 처리 시간이 너무 오래 걸립니다.",
            ErrorCategory.NETWORK: "네트워크 연결에 문제가 있습니다."
        }
        return user_messages.get(self.category, "Excel 파일 처리 중 오류가 발생했습니다.")
    
    def _generate_recovery_suggestions(self) -> List[str]:
        """복구 제안사항 생성"""
        suggestions_map = {
            ErrorCategory.FILE_FORMAT: [
                "Excel 파일을 다시 저장해보세요 (.xlsx 형식 권장)",
                "다른 Excel 버전에서 파일을 열어 호환성을 확인해보세요"
            ],
            ErrorCategory.MEMORY: [
                "파일 크기를 줄여보세요 (불필요한 시트나 데이터 제거)",
                "파일을 여러 개의 작은 파일로 분할해보세요"
            ],
            ErrorCategory.CORRUPTION: [
                "Excel의 '파일 복구' 기능을 사용해보세요",
                "백업 파일이 있다면 해당 파일을 사용해보세요"
            ]
        }
        return suggestions_map.get(self.category, ["관리자에게 문의해주세요"])
    
    def to_dict(self) -> Dict[str, Any]:
        """예외 정보를 딕셔너리로 변환"""
        return {
            "error": True,
            "error_code": self.code,
            "severity": self.severity.value,
            "category": self.category.value,
            "technical_message": self.message,
            "user_message": self.user_message,
            "recovery_suggestions": self.recovery_suggestions,
            "details": self.details
        }

class ErrorDetectionError(ExcelServiceError):
    """오류 감지 중 발생하는 예외"""
    pass

class ErrorFixingError(ExcelServiceError):
    """오류 수정 중 발생하는 예외"""
    pass

class WorkbookLoadError(ExcelServiceError):
    """워크북 로드 중 발생하는 예외"""
    pass

class WebSocketError(ExcelServiceError):
    """WebSocket 통신 중 발생하는 예외"""
    pass

class ValidationError(ExcelServiceError):
    """데이터 검증 중 발생하는 예외"""
    pass

class AIServiceError(ExcelServiceError):
    """AI 서비스 호출 중 발생하는 예외"""
    pass