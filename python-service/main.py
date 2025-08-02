"""
FastAPI application entry point for Excel AI services
모니터링 및 로깅 강화 버전
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import os

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.logging_config import init_logging, log_performance_metrics
from app.api import router as api_router
from app.core.database import engine, Base
from app.middleware.monitoring_middleware import MonitoringMiddleware, HealthCheckMiddleware

# 향상된 로깅 시스템 초기화
init_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle events
    """
    # Startup
    logger.info("Starting Excel AI Service...")
    
    # Try to create database tables (optional for OCR-only mode)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.info("Running in OCR-only mode without database features")
    
    # Start AI failover service health monitoring
    try:
        from app.services.ai_failover_service import ai_failover_service
        ai_failover_service._start_health_monitoring()
        logger.info("AI failover service health monitoring started")
    except Exception as e:
        logger.warning(f"Failed to start AI failover health monitoring: {e}")
    
    # Initialize WOPI services - skip for now to avoid initialization errors
    # try:
    #     from app.contexts.wopi.infrastructure.dependencies import get_token_service, get_file_storage
    #     token_service = get_token_service()
    #     file_storage = get_file_storage()
    #     logger.info("WOPI services initialized successfully")
    # except Exception as e:
    #     logger.warning(f"Failed to initialize WOPI services: {e}")
    logger.info("WOPI services initialization skipped")
    
    # 시작 성능 메트릭 로깅
    log_performance_metrics(
        operation="application_startup",
        duration=0,
        status="completed",
        features_enabled=[
            "database" if "Database tables created" in "success" else "ocr_only",
            "ai_failover" if "AI failover service" in "success" else "ai_failover_disabled"
        ]
    )
    
    logger.info("=== Excel AI Service 시작 완료 ===")
    
    yield
    
    # Shutdown
    logger.info("=== Excel AI Service 종료 시작 ===")
    shutdown_start = __import__('time').time()
    
    try:
        await engine.dispose()
        logger.info("데이터베이스 연결 정리 완료")
    except Exception as e:
        logger.warning(f"데이터베이스 정리 실패: {e}")
    
    # Cleanup WOPI services
    try:
        from app.contexts.wopi.infrastructure.dependencies import cleanup_services
        await cleanup_services()
        logger.info("WOPI services cleaned up")
    except Exception as e:
        logger.warning(f"Failed to cleanup WOPI services: {e}")
    
    # 종료 성능 메트릭 로깅
    shutdown_time = __import__('time').time() - shutdown_start
    log_performance_metrics(
        operation="application_shutdown",
        duration=shutdown_time,
        status="completed"
    )
    
    logger.info("Excel AI Service 종료 완료")


# Create FastAPI application
app = FastAPI(
    title="Excel AI Service - 모니터링 강화",
    description="AI-powered Excel analysis and consultation service with enhanced monitoring",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# 모니터링 미들웨어 추가 (순서 중요: 가장 먼저 추가)
app.add_middleware(MonitoringMiddleware)
app.add_middleware(HealthCheckMiddleware)

# Add CSRF protection middleware
from app.contexts.wopi.api.middleware.csrf_protection import CSRFProtection
from app.contexts.wopi.infrastructure.config import settings as wopi_settings
csrf_protection = CSRFProtection(
    redis_url=wopi_settings.redis_url,
    token_name=wopi_settings.csrf_token_name,
    header_name=wopi_settings.csrf_header_name,
    cookie_secure=wopi_settings.csrf_cookie_secure,
    cookie_samesite=wopi_settings.csrf_cookie_samesite,
    token_ttl_hours=wopi_settings.csrf_token_ttl_hours
)

# Add as middleware class
from starlette.middleware.base import BaseHTTPMiddleware
app.add_middleware(BaseHTTPMiddleware, dispatch=csrf_protection)

# Add structured logging middleware
from app.contexts.wopi.infrastructure.structured_logger import LoggingMiddleware
app.add_middleware(LoggingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.API_PREFIX)

# Include WOPI routes
from app.contexts.wopi.api.endpoints import router as wopi_router
app.include_router(wopi_router)

# Add WOPI error handlers
from app.contexts.wopi.api.error_handlers import (
    WOPIError, 
    wopi_error_handler,
    validation_error_handler,
    generic_error_handler
)
from fastapi.exceptions import RequestValidationError

app.add_exception_handler(WOPIError, wopi_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Serve static files (temporary files)
from fastapi.staticfiles import StaticFiles
import tempfile
app.mount("/tmp/uploads", StaticFiles(directory=tempfile.gettempdir()), name="temp_files")

# Serve test files
app.mount("/test-files", StaticFiles(directory="."), name="test_files")


# Serve the test HTML page
from fastapi.responses import FileResponse




@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring"""
    return {
        "status": "healthy",
        "service": "excel-ai-service",
        "version": "1.0.0"
    }


# WebSocket endpoint for Excel error detection
from fastapi import WebSocket, WebSocketDisconnect
from app.websocket.excel_websocket_handler import ExcelWebSocketHandler

websocket_handler = ExcelWebSocketHandler()

@app.websocket("/ws/excel/{session_id}")
async def excel_websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time Excel error detection"""
    try:
        await websocket_handler.handle_connection(websocket, session_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket_handler.close_connection(session_id)


# Background task for cleaning up inactive sessions
import asyncio

async def cleanup_inactive_sessions():
    """Cleanup inactive WebSocket sessions periodically"""
    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            await websocket_handler.cleanup_inactive_sessions(30)  # 30 minutes timeout
        except Exception as e:
            logger.error(f"Session cleanup error: {str(e)}")

# Start cleanup task on startup
@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    asyncio.create_task(cleanup_inactive_sessions())


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )