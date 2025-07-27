"""
Health check endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import psutil
import platform
from datetime import datetime

from app.core.database import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/status")
async def health_status():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "excel-ai-service",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


@router.get("/detailed")
async def detailed_health(db: AsyncSession = Depends(get_db)):
    """Detailed health check with system info"""
    
    # Check database connection
    db_status = "healthy"
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # System info
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "excel-ai-service",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "components": {
            "database": db_status,
            "openai": "configured" if settings.OPENAI_API_KEY else "not configured"
        },
        "system": {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "cpu_usage_percent": cpu_percent,
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": disk.percent
            }
        }
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe for kubernetes"""
    try:
        # Check database
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        
        # Check if AI service is configured
        if not settings.OPENAI_API_KEY:
            return {"ready": False, "reason": "OpenAI API key not configured"}
        
        return {"ready": True}
    except Exception as e:
        return {"ready": False, "reason": str(e)}