"""
API routes initialization
"""
from fastapi import APIRouter

from app.api.v1 import health, excel_processing, excel_reader
# Temporarily disabled imports due to missing modules:
# excel, ai, embeddings, excel_modifications, vba_analysis, vba_generation, excel_error_analysis, 
# websocket_progress, quality_verification, excel_advanced_features, excel_templates, i18n, pwa, 
# admin_templates, excel_comparison, formula_analysis, ai_excel_generation, comprehensive_analysis, 
# formula_validation, ai_failover, simple_excel, excel_conversion, excel_format_preservation
# Temporarily disabled problematic imports:
# monitoring, korean_crawler, advanced_monitoring, business_analytics

# Create main API router
router = APIRouter()

# Include v1 routes
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(excel_processing.router, prefix="/excel", tags=["excel-processing"])
router.include_router(excel_reader.router, prefix="/excel", tags=["excel-reader"])
# Temporarily disabled routers:
# router.include_router(excel.router, prefix="/excel", tags=["excel"])
# router.include_router(simple_excel.router, prefix="/simple-excel", tags=["simple-excel"])
# router.include_router(excel_modifications.router, prefix="/excel-modifications", tags=["excel-modifications"])
# router.include_router(vba_analysis.router, prefix="/vba", tags=["vba"])
# router.include_router(vba_generation.router, prefix="/vba-generation", tags=["vba-generation"])
# router.include_router(ai.router, prefix="/ai", tags=["ai"])
# router.include_router(embeddings.router, prefix="/embeddings", tags=["embeddings"])
# router.include_router(excel_error_analysis.router, prefix="/excel-error-analysis", tags=["excel-error-analysis"])
# router.include_router(websocket_progress.router, prefix="/ws", tags=["websocket-progress"])
# router.include_router(quality_verification.router, prefix="/quality-verification", tags=["quality-verification"])
# router.include_router(excel_advanced_features.router, prefix="/excel-advanced", tags=["excel-advanced-features"])
# router.include_router(excel_templates.router, prefix="/excel-templates", tags=["excel-templates"])
# router.include_router(i18n.router, prefix="/i18n", tags=["internationalization"])
# router.include_router(pwa.router, prefix="/pwa", tags=["progressive-web-app"])
# router.include_router(admin_templates.router, tags=["admin-templates"])
# router.include_router(excel_comparison.router, prefix="/excel-comparison", tags=["excel-comparison"])
# router.include_router(formula_analysis.router, prefix="/formula-analysis", tags=["formula-analysis"])
# router.include_router(ai_excel_generation.router, prefix="/ai-excel", tags=["ai-excel-generation"])
# router.include_router(comprehensive_analysis.router, prefix="/comprehensive", tags=["comprehensive-analysis"])
# router.include_router(formula_validation.router, tags=["formula-validation"])
# router.include_router(ai_failover.router, tags=["ai-failover"])
# router.include_router(excel_conversion.router, prefix="/excel", tags=["excel-conversion"])
# router.include_router(excel_format_preservation.router, prefix="/excel", tags=["excel-format-preservation"])
# Temporarily disabled:
# router.include_router(korean_crawler.router, tags=["korean-crawler"])
# router.include_router(monitoring.router, tags=["monitoring"])
# router.include_router(advanced_monitoring.router, prefix="/advanced-monitoring", tags=["advanced-monitoring"])
# router.include_router(business_analytics.router, prefix="/business-analytics", tags=["business-analytics"])