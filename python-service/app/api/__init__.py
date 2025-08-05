"""
API routes initialization
"""

from fastapi import APIRouter
import logging

from app.api.v1 import (
    health,
    excel_processing,
    excel_reader,
    excel_cleanup,
    excel,
    excel_error_analysis,
    excel_fixes,
)

logger = logging.getLogger(__name__)

# Create main API router
router = APIRouter()

# Include v1 routes
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(excel.router, prefix="/excel", tags=["excel"])
router.include_router(
    excel_processing.router, prefix="/excel-processing", tags=["excel-processing"]
)
router.include_router(
    excel_reader.router, prefix="/excel-reader", tags=["excel-reader"]
)
router.include_router(
    excel_cleanup.router, prefix="/excel-cleanup", tags=["excel-cleanup"]
)
router.include_router(excel_error_analysis.router, tags=["excel-error-analysis"])
router.include_router(excel_fixes.router, prefix="/excel-fixes", tags=["excel-fixes"])

# AI endpoints (필수)
try:
    from app.api.v1 import ai

    router.include_router(ai.router, prefix="/ai", tags=["ai"])
    logger.info("AI router loaded successfully")
except ImportError as e:
    logger.warning(f"Failed to import AI router: {e}")

# Context WebSocket (새로운 실시간 동기화)
try:
    from app.api.v1 import context_websocket

    router.include_router(context_websocket.router, tags=["websocket-context"])
    logger.info("Context WebSocket router loaded successfully")
except ImportError as e:
    logger.warning(f"Failed to import Context WebSocket router: {e}")

# Context Bridge (Rails Action Cable 연동)
try:
    from app.api.v1 import context_bridge

    router.include_router(
        context_bridge.router, prefix="/context", tags=["context-bridge"]
    )
    logger.info("Context Bridge router loaded successfully")
except ImportError as e:
    logger.warning(f"Failed to import Context Bridge router: {e}")

# Monitoring endpoints
try:
    from app.api.v1 import monitoring

    router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
    logger.info("Monitoring router loaded successfully")
except ImportError as e:
    logger.warning(f"Failed to import Monitoring router: {e}")

# Optional modules - try to import but don't fail if missing
optional_modules = [
    ("embeddings", "/embeddings", ["embeddings"]),
    ("excel_modifications", "/excel-modifications", ["excel-modifications"]),
    ("vba_analysis", "/vba", ["vba"]),
    ("vba_generation", "/vba-generation", ["vba-generation"]),
    ("websocket_progress", "/ws", ["websocket-progress"]),
    ("quality_verification", "/quality-verification", ["quality-verification"]),
    ("excel_advanced_features", "/excel-advanced", ["excel-advanced-features"]),
    ("excel_templates", "/excel-templates", ["excel-templates"]),
    ("i18n", "/i18n", ["internationalization"]),
    ("pwa", "/pwa", ["progressive-web-app"]),
    ("admin_templates", "", ["admin-templates"]),
    ("excel_comparison", "/excel-comparison", ["excel-comparison"]),
    ("formula_analysis", "/formula-analysis", ["formula-analysis"]),
    ("ai_excel_generation", "/ai-excel", ["ai-excel-generation"]),
    ("comprehensive_analysis", "/comprehensive", ["comprehensive-analysis"]),
    ("formula_validation", "", ["formula-validation"]),
    ("ai_failover", "", ["ai-failover"]),
    ("simple_excel", "/simple-excel", ["simple-excel"]),
    ("excel_conversion", "/excel", ["excel-conversion"]),
    ("excel_format_preservation", "/excel", ["excel-format-preservation"]),
]

for module_name, prefix, tags in optional_modules:
    try:
        module = __import__(f"app.api.v1.{module_name}", fromlist=[module_name])
        if prefix:
            router.include_router(module.router, prefix=prefix, tags=tags)
        else:
            router.include_router(module.router, tags=tags)
        logger.info(f"{module_name} router loaded successfully")
    except ImportError as e:
        logger.debug(f"Optional module {module_name} not available: {e}")
    except Exception as e:
        logger.error(f"Failed to load {module_name}: {e}")
