"""
국제화 FastAPI 의존성
Internationalization FastAPI Dependencies
"""

from fastapi import Header, Request
from typing import Optional
import logging

from ..services.i18n_service import i18n_service

logger = logging.getLogger(__name__)


def get_language_from_request(
    accept_language: Optional[str] = Header(None),
    x_language: Optional[str] = Header(None, alias="X-Language"),
    request: Request = None
) -> str:
    """
    요청에서 언어 추출
    
    우선순위:
    1. X-Language 헤더
    2. Accept-Language 헤더
    3. 기본 언어 (ko)
    
    Args:
        accept_language: Accept-Language 헤더
        x_language: X-Language 커스텀 헤더
        request: FastAPI Request 객체
        
    Returns:
        언어 코드
    """
    
    # 1. X-Language 헤더 우선 확인
    if x_language and i18n_service.validate_language(x_language):
        logger.debug(f"X-Language 헤더에서 언어 감지: {x_language}")
        return x_language
    
    # 2. Accept-Language 헤더에서 언어 추출
    if accept_language:
        detected_language = i18n_service.get_language_from_accept_header(accept_language)
        logger.debug(f"Accept-Language 헤더에서 언어 감지: {detected_language}")
        return detected_language
    
    # 3. URL 경로에서 언어 추출 (옵션)
    if request and hasattr(request, 'path_params'):
        lang_from_path = request.path_params.get('language')
        if lang_from_path and i18n_service.validate_language(lang_from_path):
            logger.debug(f"URL 경로에서 언어 감지: {lang_from_path}")
            return lang_from_path
    
    # 4. 기본 언어 반환
    default_lang = i18n_service.default_language
    logger.debug(f"기본 언어 사용: {default_lang}")
    return default_lang


class I18nContext:
    """국제화 컨텍스트 클래스"""
    
    def __init__(self, language: str):
        self.language = language
        self.service = i18n_service
    
    def get_text(self, key: str, **kwargs) -> str:
        """번역 텍스트 가져오기"""
        return self.service.get_text(key, self.language, **kwargs)
    
    def get_error_message(self, error_type: str, **kwargs) -> str:
        """에러 메시지 가져오기"""
        return self.service.get_localized_error_message(error_type, self.language, **kwargs)
    
    def localize_template_metadata(self, template_data):
        """템플릿 메타데이터 현지화"""
        return self.service.localize_template_metadata(template_data, self.language)
    
    def get_progress_text(self, stage: str) -> str:
        """진행 단계 텍스트"""
        return self.service.get_progress_stage_text(stage, self.language)


def get_i18n_context(language: str = get_language_from_request) -> I18nContext:
    """
    국제화 컨텍스트 의존성
    
    Usage:
        @app.get("/api/endpoint")
        async def my_endpoint(i18n: I18nContext = Depends(get_i18n_context)):
            return {"message": i18n.get_text("common.success")}
    """
    return I18nContext(language)