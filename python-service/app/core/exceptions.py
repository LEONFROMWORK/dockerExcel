"""
Custom Exceptions for Excel Services
Excel 서비스 커스텀 예외 정의
"""

class ExcelServiceError(Exception):
    """Excel 서비스 기본 예외"""
    def __init__(self, message: str, code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

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