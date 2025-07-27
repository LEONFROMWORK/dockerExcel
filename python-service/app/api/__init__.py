"""
API routes initialization
"""
from fastapi import APIRouter

from app.api.v1 import excel, ai, embeddings, health, excel_modifications, vba_analysis, vba_generation, excel_from_structure, multilingual_ocr, async_ocr, ocr_retry_stats, table_detection, chart_detection, batch_processing, excel_error_analysis, transformer_ocr, multimodal_ai, websocket_progress, quality_verification, excel_advanced_features, excel_templates, i18n, pwa, admin_templates, strategic_batch, image_excel_integration, excel_comparison, formula_analysis, ai_excel_generation, comprehensive_analysis
# Temporarily disabled problematic imports:
# monitoring, korean_crawler, advanced_monitoring, business_analytics

# Create main API router
router = APIRouter()

# Include v1 routes
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(excel.router, prefix="/excel", tags=["excel"])
router.include_router(excel_modifications.router, prefix="/excel-modifications", tags=["excel-modifications"])
router.include_router(vba_analysis.router, prefix="/vba", tags=["vba"])
router.include_router(vba_generation.router, prefix="/vba-generation", tags=["vba-generation"])
# router.include_router(image_analysis.router, prefix="/image", tags=["image"])  # Replaced by image_excel_integration
router.include_router(ai.router, prefix="/ai", tags=["ai"])
router.include_router(embeddings.router, prefix="/embeddings", tags=["embeddings"])
router.include_router(excel_from_structure.router, prefix="/excel-structure", tags=["excel-structure"])
# router.include_router(image_to_excel.router, tags=["image-to-excel"])  # Replaced by image_excel_integration
router.include_router(multilingual_ocr.router, prefix="/ocr", tags=["multilingual-ocr"])
router.include_router(async_ocr.router, prefix="/async-ocr", tags=["async-ocr"])
router.include_router(ocr_retry_stats.router, prefix="/ocr", tags=["ocr-retry"])
router.include_router(table_detection.router, prefix="/table", tags=["table-detection"])
router.include_router(chart_detection.router, prefix="/chart", tags=["chart-detection"])
router.include_router(batch_processing.router, prefix="/batch", tags=["batch-processing"])
router.include_router(excel_error_analysis.router, prefix="/excel-error-analysis", tags=["excel-error-analysis"])
router.include_router(transformer_ocr.router, prefix="/transformer-ocr", tags=["transformer-ocr"])
router.include_router(multimodal_ai.router, prefix="/multimodal-ai", tags=["multimodal-ai"])
router.include_router(websocket_progress.router, prefix="/ws", tags=["websocket-progress"])
router.include_router(quality_verification.router, prefix="/quality-verification", tags=["quality-verification"])
router.include_router(excel_advanced_features.router, prefix="/excel-advanced", tags=["excel-advanced-features"])
router.include_router(excel_templates.router, prefix="/excel-templates", tags=["excel-templates"])
router.include_router(i18n.router, prefix="/i18n", tags=["internationalization"])
router.include_router(pwa.router, prefix="/pwa", tags=["progressive-web-app"])
router.include_router(admin_templates.router, tags=["admin-templates"])
router.include_router(strategic_batch.router, prefix="/strategic-batch", tags=["strategic-batch"])
router.include_router(image_excel_integration.router, prefix="/image-excel-integration", tags=["image-excel-integration"])
router.include_router(excel_comparison.router, prefix="/excel-comparison", tags=["excel-comparison"])
router.include_router(formula_analysis.router, prefix="/formula-analysis", tags=["formula-analysis"])
router.include_router(ai_excel_generation.router, prefix="/ai-excel", tags=["ai-excel-generation"])
router.include_router(comprehensive_analysis.router, prefix="/comprehensive", tags=["comprehensive-analysis"])
# Temporarily disabled:
# router.include_router(korean_crawler.router, tags=["korean-crawler"])
# router.include_router(monitoring.router, tags=["monitoring"])
# router.include_router(advanced_monitoring.router, prefix="/advanced-monitoring", tags=["advanced-monitoring"])
# router.include_router(business_analytics.router, prefix="/business-analytics", tags=["business-analytics"])