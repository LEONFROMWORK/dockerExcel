"""
Standardized error handling for WOPI API.
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from datetime import datetime
import traceback
from typing import Dict, Any, Optional
import logging

from ..infrastructure.structured_logger import wopi_logger

logger = logging.getLogger(__name__)


class WOPIError(HTTPException):
    """Base WOPI error class."""
    
    def __init__(
        self, 
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(status_code=status_code, detail=message)


class TokenError(WOPIError):
    """Token-related errors."""
    
    def __init__(self, message: str, error_code: str = "TOKEN_ERROR"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            message=message
        )


class FileNotFoundError(WOPIError):
    """File not found error."""
    
    def __init__(self, file_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="FILE_NOT_FOUND",
            message=f"File not found: {file_id}",
            details={"file_id": file_id}
        )


class PermissionError(WOPIError):
    """Permission denied error."""
    
    def __init__(self, operation: str, file_id: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="PERMISSION_DENIED",
            message=f"Permission denied for operation: {operation}",
            details={"operation": operation, "file_id": file_id}
        )


class FileSizeError(WOPIError):
    """File size exceeded error."""
    
    def __init__(self, size: int, max_size: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            error_code="FILE_SIZE_EXCEEDED",
            message=f"File size {size} exceeds maximum {max_size}",
            details={"size": size, "max_size": max_size}
        )


class InvalidFileTypeError(WOPIError):
    """Invalid file type error."""
    
    def __init__(self, file_type: str, allowed_types: list):
        super().__init__(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            error_code="INVALID_FILE_TYPE",
            message=f"File type {file_type} not allowed",
            details={"file_type": file_type, "allowed_types": allowed_types}
        )


class ServiceUnavailableError(WOPIError):
    """Service unavailable error."""
    
    def __init__(self, service: str, reason: str = ""):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="SERVICE_UNAVAILABLE",
            message=f"Service {service} is unavailable: {reason}",
            details={"service": service, "reason": reason}
        )


def create_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """Create standardized error response."""
    
    error_response = {
        "error": {
            "code": error_code,
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "details": details or {}
        }
    }
    
    if request_id:
        error_response["error"]["request_id"] = request_id
    
    # Log error
    wopi_logger.log_error(
        error_type=error_code,
        error_message=message,
        context={
            "status_code": status_code,
            "details": details,
            "request_id": request_id
        }
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


async def wopi_error_handler(request: Request, exc: WOPIError) -> JSONResponse:
    """Handle WOPI errors."""
    request_id = getattr(request.state, "request_id", None)
    
    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        request_id=request_id
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle validation errors."""
    request_id = getattr(request.state, "request_id", None)
    
    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Invalid request data",
        status_code=status.HTTP_400_BAD_REQUEST,
        details={"errors": str(exc)},
        request_id=request_id
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic errors."""
    request_id = getattr(request.state, "request_id", None)
    
    # Log full traceback
    logger.error(f"Unhandled error: {str(exc)}\n{traceback.format_exc()}")
    
    # In production, don't expose internal errors
    if request.app.debug:
        message = str(exc)
        details = {"traceback": traceback.format_exc()}
    else:
        message = "Internal server error"
        details = {}
    
    return create_error_response(
        error_code="INTERNAL_ERROR",
        message=message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=details,
        request_id=request_id
    )


# Error response models for OpenAPI documentation
ERROR_RESPONSES = {
    400: {
        "description": "Bad Request",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid request data",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "details": {}
                    }
                }
            }
        }
    },
    401: {
        "description": "Unauthorized",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "TOKEN_ERROR",
                        "message": "Invalid or expired token",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "details": {}
                    }
                }
            }
        }
    },
    403: {
        "description": "Forbidden",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": "Permission denied for operation",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "details": {}
                    }
                }
            }
        }
    },
    404: {
        "description": "Not Found",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "FILE_NOT_FOUND",
                        "message": "File not found",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "details": {}
                    }
                }
            }
        }
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Internal server error",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "details": {}
                    }
                }
            }
        }
    }
}