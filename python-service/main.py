"""
FastAPI application entry point for Excel AI services
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import router as api_router
from app.core.database import engine, Base

# Setup logging
setup_logging()
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
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Excel AI Service...")
    try:
        await engine.dispose()
    except Exception as e:
        logger.warning(f"Database cleanup failed: {e}")


# Create FastAPI application
app = FastAPI(
    title="Excel AI Service",
    description="AI-powered Excel analysis and consultation service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

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

# Serve static files (temporary files)
from fastapi.staticfiles import StaticFiles
import tempfile
app.mount("/tmp/uploads", StaticFiles(directory=tempfile.gettempdir()), name="temp_files")


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