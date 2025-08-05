"""
국제화(i18n) API 엔드포인트
Internationalization API Endpoints
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
import logging
from datetime import datetime

from ...core.i18n_dependencies import get_i18n_context, I18nContext
from ...services.i18n_service import i18n_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/languages")
async def get_supported_languages():
    """지원하는 언어 목록 조회"""

    try:
        languages = i18n_service.get_supported_languages()

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "supported_languages": languages,
            "default_language": i18n_service.default_language,
        }

    except Exception as e:
        logger.error(f"언어 목록 조회 실패: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/translations")
async def get_translations(
    language: Optional[str] = Query(None, description="언어 코드"),
    namespace: Optional[str] = Query(
        None, description="네임스페이스 (예: common, templates)"
    ),
    i18n: I18nContext = Depends(get_i18n_context),
):
    """번역 데이터 조회"""

    try:
        target_language = (
            language
            if language and i18n_service.validate_language(language)
            else i18n.language
        )

        # 전체 번역 데이터 가져오기
        translation_data = i18n_service.translations.get(target_language, {})

        # 특정 네임스페이스만 필터링
        if namespace and namespace in translation_data:
            translation_data = {namespace: translation_data[namespace]}

        return {
            "status": "success",
            "language": target_language,
            "namespace": namespace,
            "timestamp": datetime.now().isoformat(),
            "translations": translation_data,
        }

    except Exception as e:
        logger.error(f"번역 데이터 조회 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        return {
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/text/{key}")
async def get_translated_text(
    key: str,
    language: Optional[str] = Query(None, description="언어 코드"),
    i18n: I18nContext = Depends(get_i18n_context),
):
    """특정 키의 번역 텍스트 조회"""

    try:
        target_language = (
            language
            if language and i18n_service.validate_language(language)
            else i18n.language
        )
        translated_text = i18n_service.get_text(key, target_language)

        return {
            "status": "success",
            "key": key,
            "language": target_language,
            "text": translated_text,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"번역 텍스트 조회 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        return {
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/validate")
async def validate_language_code(
    language: str, i18n: I18nContext = Depends(get_i18n_context)
):
    """언어 코드 유효성 검사"""

    try:
        is_valid = i18n_service.validate_language(language)

        return {
            "status": "success",
            "language": language,
            "is_valid": is_valid,
            "supported_languages": list(i18n_service.supported_languages),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"언어 코드 검증 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        return {
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/detect-language")
async def detect_language_from_header(
    accept_language: Optional[str] = Query(None, description="Accept-Language 헤더 값")
):
    """Accept-Language 헤더에서 언어 감지"""

    try:
        if not accept_language:
            return {
                "status": "success",
                "detected_language": i18n_service.default_language,
                "source": "default",
                "timestamp": datetime.now().isoformat(),
            }

        detected_language = i18n_service.get_language_from_accept_header(
            accept_language
        )

        return {
            "status": "success",
            "accept_language_header": accept_language,
            "detected_language": detected_language,
            "source": "header",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"언어 감지 실패: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/localized-errors")
async def get_localized_error_messages(
    language: Optional[str] = Query(None, description="언어 코드"),
    i18n: I18nContext = Depends(get_i18n_context),
):
    """현지화된 에러 메시지 목록"""

    try:
        target_language = (
            language
            if language and i18n_service.validate_language(language)
            else i18n.language
        )

        # 주요 에러 타입들의 번역된 메시지
        error_types = [
            "file_not_found",
            "invalid_file_type",
            "file_too_large",
            "excel_only",
            "template_not_found",
            "generation_failed",
            "ai_error",
            "api_error",
            "unauthorized",
            "forbidden",
        ]

        localized_errors = {}
        for error_type in error_types:
            localized_errors[error_type] = i18n_service.get_localized_error_message(
                error_type, target_language
            )

        return {
            "status": "success",
            "language": target_language,
            "error_messages": localized_errors,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"에러 메시지 목록 조회 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        return {
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/template-categories")
async def get_localized_template_categories(
    language: Optional[str] = Query(None, description="언어 코드"),
    i18n: I18nContext = Depends(get_i18n_context),
):
    """현지화된 템플릿 카테고리 목록"""

    try:
        target_language = (
            language
            if language and i18n_service.validate_language(language)
            else i18n.language
        )

        # 템플릿 카테고리 목록
        categories = [
            "financial_statements",
            "analytics_dashboard",
            "project_management",
            "hr_management",
            "marketing_reports",
            "academic_research",
            "inventory_management",
            "budget_planning",
        ]

        localized_categories = {}
        for category in categories:
            key = f"templates.categories_list.{category}"
            localized_categories[category] = i18n_service.get_text(key, target_language)

        return {
            "status": "success",
            "language": target_language,
            "categories": localized_categories,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"템플릿 카테고리 현지화 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        return {
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/progress-stages")
async def get_localized_progress_stages(
    language: Optional[str] = Query(None, description="언어 코드"),
    i18n: I18nContext = Depends(get_i18n_context),
):
    """현지화된 진행 단계 텍스트"""

    try:
        target_language = (
            language
            if language and i18n_service.validate_language(language)
            else i18n.language
        )

        # 진행 단계 목록
        stages = [
            "uploaded",
            "analyzing",
            "detecting_errors",
            "fixing_formulas",
            "generating_charts",
            "creating_pivots",
            "applying_templates",
            "finalizing",
            "completed",
            "failed",
        ]

        localized_stages = {}
        for stage in stages:
            localized_stages[stage] = i18n_service.get_progress_stage_text(
                stage, target_language
            )

        return {
            "status": "success",
            "language": target_language,
            "progress_stages": localized_stages,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"진행 단계 현지화 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        return {
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/reload")
async def reload_translations(i18n: I18nContext = Depends(get_i18n_context)):
    """번역 파일 다시 로드 (개발/테스트용)"""

    try:
        i18n_service.reload_translations()

        return {
            "status": "success",
            "message": i18n.get_text("common.success"),
            "action": "translations_reloaded",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"번역 파일 재로드 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        return {
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/health")
async def i18n_service_health():
    """국제화 서비스 상태 확인"""

    try:
        loaded_languages = list(i18n_service.translations.keys())

        return {
            "status": "healthy",
            "service": "i18n",
            "timestamp": datetime.now().isoformat(),
            "info": {
                "loaded_languages": loaded_languages,
                "supported_languages": list(i18n_service.supported_languages),
                "default_language": i18n_service.default_language,
                "translation_files_loaded": len(loaded_languages),
            },
        }

    except Exception as e:
        logger.error(f"i18n 서비스 상태 확인 실패: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "i18n",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
