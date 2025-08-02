"""
Structured logging configuration for WOPI context.
"""

import structlog
import logging
import sys
from typing import Any, Dict
from datetime import datetime
import json


def configure_structured_logging(
    log_level: str = "INFO",
    json_logs: bool = True,
    service_name: str = "wopi-service"
) -> structlog.BoundLogger:
    """Configure structured logging with context."""
    
    # Configure timestamp
    def add_timestamp(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return event_dict
    
    # Add service context
    def add_service_context(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        event_dict["service"] = service_name
        event_dict["environment"] = event_dict.get("environment", "development")
        return event_dict
    
    # Configure processors
    processors = [
        add_timestamp,
        add_service_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    return structlog.get_logger()


class WOPILogger:
    """WOPI-specific logger with predefined contexts."""
    
    def __init__(self, logger: structlog.BoundLogger):
        self.logger = logger
    
    def bind_request(self, request_id: str, method: str, path: str):
        """Bind HTTP request context."""
        return self.logger.bind(
            request_id=request_id,
            http_method=method,
            http_path=path
        )
    
    def bind_user(self, user_id: str, user_name: str = None):
        """Bind user context."""
        return self.logger.bind(
            user_id=user_id,
            user_name=user_name or "unknown"
        )
    
    def bind_file(self, file_id: str, file_name: str = None):
        """Bind file context."""
        return self.logger.bind(
            file_id=file_id,
            file_name=file_name
        )
    
    def log_token_generated(
        self, 
        user_id: str, 
        file_id: str, 
        permission: str,
        token_id: str = None
    ):
        """Log token generation event."""
        self.logger.info(
            "wopi.token.generated",
            user_id=user_id,
            file_id=file_id,
            permission=permission,
            token_id=token_id,
            event_type="security"
        )
    
    def log_token_validated(
        self, 
        token_id: str,
        valid: bool,
        reason: str = None
    ):
        """Log token validation event."""
        self.logger.info(
            "wopi.token.validated",
            token_id=token_id,
            valid=valid,
            reason=reason,
            event_type="security"
        )
    
    def log_file_accessed(
        self,
        file_id: str,
        user_id: str,
        operation: str,
        success: bool,
        size_bytes: int = None
    ):
        """Log file access event."""
        self.logger.info(
            "wopi.file.accessed",
            file_id=file_id,
            user_id=user_id,
            operation=operation,
            success=success,
            size_bytes=size_bytes,
            event_type="file_operation"
        )
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Dict[str, Any] = None
    ):
        """Log error event."""
        self.logger.error(
            "wopi.error",
            error_type=error_type,
            error_message=error_message,
            context=context or {},
            event_type="error"
        )
    
    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool,
        metadata: Dict[str, Any] = None
    ):
        """Log performance metrics."""
        self.logger.info(
            "wopi.performance",
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata or {},
            event_type="performance"
        )


# Create global logger instance
_structured_logger = configure_structured_logging()
wopi_logger = WOPILogger(_structured_logger)


# Example middleware for request logging
class LoggingMiddleware:
    """Middleware for structured request/response logging."""
    
    def __init__(self, app):
        self.app = app
        self.logger = wopi_logger
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Generate request ID
        import uuid
        request_id = str(uuid.uuid4())
        
        # Start time
        start_time = datetime.utcnow()
        
        # Log request
        self.logger.bind_request(
            request_id=request_id,
            method=scope["method"],
            path=scope["path"]
        ).info("request.started")
        
        # Capture response status
        status_code = None
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
            
            # Calculate duration
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Log response
            self.logger.bind_request(
                request_id=request_id,
                method=scope["method"],
                path=scope["path"]
            ).info(
                "request.completed",
                status_code=status_code,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            # Log error
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self.logger.bind_request(
                request_id=request_id,
                method=scope["method"],
                path=scope["path"]
            ).error(
                "request.failed",
                error=str(e),
                duration_ms=duration_ms
            )
            raise