"""
국제화(i18n) 지원 서비스
Internationalization Service for Multi-language Support
"""

import json
from typing import Dict, Any
from functools import lru_cache
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class I18nService:
    """다국어 지원 서비스"""

    def __init__(self):
        self.default_language = "ko"
        self.supported_languages = ["ko", "en", "ja", "zh"]
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.locales_dir = Path(__file__).parent.parent / "locales"

        # 번역 파일 로드
        self._load_translations()

    def _load_translations(self):
        """번역 파일들을 메모리에 로드"""
        try:
            for language in self.supported_languages:
                file_path = self.locales_dir / f"{language}.json"

                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.translations[language] = json.load(f)
                    logger.info(f"번역 파일 로드 완료: {language}")
                else:
                    logger.warning(f"번역 파일을 찾을 수 없음: {file_path}")

        except Exception as e:
            logger.error(f"번역 파일 로드 실패: {str(e)}")
            # 기본 영어 번역이라도 설정
            self.translations = {
                "en": {"common": {"error": "Error", "success": "Success"}}
            }

    @lru_cache(maxsize=1000)
    def get_text(self, key: str, language: str = None, **kwargs) -> str:
        """
        번역된 텍스트 반환

        Args:
            key: 번역 키 (예: "common.success", "file.invalid_type")
            language: 언어 코드 (기본값: ko)
            **kwargs: 텍스트 포맷팅에 사용할 변수들

        Returns:
            번역된 텍스트
        """
        if language is None:
            language = self.default_language

        # 지원하지 않는 언어인 경우 기본 언어 사용
        if language not in self.supported_languages:
            language = self.default_language

        # 번역 데이터 가져오기
        translation_data = self.translations.get(language, {})

        # 키를 점(.)으로 분리해서 중첩 딕셔너리 탐색
        keys = key.split(".")
        current_data = translation_data

        for k in keys:
            if isinstance(current_data, dict) and k in current_data:
                current_data = current_data[k]
            else:
                # 키를 찾을 수 없으면 영어 버전으로 시도
                if language != "en":
                    return self.get_text(key, "en", **kwargs)
                else:
                    # 영어도 없으면 키 자체를 반환
                    logger.warning(f"번역 키를 찾을 수 없음: {key}")
                    return key

        # 최종 번역 텍스트
        if isinstance(current_data, str):
            # 포맷팅 변수가 있으면 적용
            if kwargs:
                try:
                    return current_data.format(**kwargs)
                except (KeyError, ValueError) as e:
                    logger.warning(f"번역 텍스트 포맷팅 실패: {key}, {e}")
                    return current_data
            return current_data
        else:
            logger.warning(f"번역 값이 문자열이 아님: {key}")
            return key

    def get_language_from_accept_header(self, accept_language: str) -> str:
        """
        Accept-Language 헤더에서 언어 추출

        Args:
            accept_language: HTTP Accept-Language 헤더 값

        Returns:
            지원하는 언어 코드
        """
        if not accept_language:
            return self.default_language

        # Accept-Language 헤더 파싱 (간단한 버전)
        # 예: "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        languages = []

        for lang_item in accept_language.split(","):
            lang_item = lang_item.strip()
            if ";" in lang_item:
                lang, quality = lang_item.split(";", 1)
                try:
                    q_value = float(quality.split("=")[1])
                except (IndexError, ValueError):
                    q_value = 1.0
            else:
                lang = lang_item
                q_value = 1.0

            # 언어 코드만 추출 (ko-KR -> ko)
            lang_code = lang.split("-")[0].lower()
            languages.append((lang_code, q_value))

        # 품질 값 순으로 정렬
        languages.sort(key=lambda x: x[1], reverse=True)

        # 지원하는 언어 중에서 찾기
        for lang_code, _ in languages:
            if lang_code in self.supported_languages:
                return lang_code

        return self.default_language

    def get_supported_languages(self) -> Dict[str, str]:
        """지원하는 언어 목록 반환"""
        return {"ko": "한국어", "en": "English", "ja": "日本語", "zh": "中文"}

    def validate_language(self, language: str) -> bool:
        """언어 코드 유효성 검사"""
        return language in self.supported_languages

    def get_localized_error_message(
        self, error_type: str, language: str = None, **kwargs
    ) -> str:
        """
        에러 타입에 따른 현지화된 에러 메시지 반환

        Args:
            error_type: 에러 타입 (예: "file_not_found", "invalid_format")
            language: 언어 코드
            **kwargs: 메시지 포맷팅 변수
        """
        error_key_mapping = {
            "file_not_found": "file.not_found",
            "invalid_file_type": "file.invalid_type",
            "file_too_large": "file.too_large",
            "upload_failed": "file.upload_failed",
            "excel_only": "file.excel_only",
            "template_not_found": "templates.not_found",
            "generation_failed": "templates.generation_failed",
            "no_suitable_template": "templates.no_suitable_template",
            "ai_error": "ai.error",
            "api_error": "api.error",
            "invalid_request": "api.invalid_request",
            "unauthorized": "api.unauthorized",
            "forbidden": "api.forbidden",
            "internal_error": "api.internal_error",
            "service_unavailable": "api.service_unavailable",
            "validation_required": "validation.required",
            "validation_format": "validation.invalid_format",
        }

        key = error_key_mapping.get(error_type, "api.error")
        return self.get_text(key, language, **kwargs)

    def localize_template_metadata(
        self, template_data: Dict[str, Any], language: str = None
    ) -> Dict[str, Any]:
        """
        템플릿 메타데이터를 현지화

        Args:
            template_data: 템플릿 메타데이터
            language: 언어 코드

        Returns:
            현지화된 템플릿 메타데이터
        """
        if language is None:
            language = self.default_language

        localized_data = template_data.copy()

        # 카테고리 현지화
        if "categories" in localized_data:
            for category_id, category_info in localized_data["categories"].items():
                category_key = f"templates.categories_list.{category_id}"
                localized_name = self.get_text(category_key, language)
                if localized_name != category_key:  # 번역이 존재하는 경우
                    category_info["localized_name"] = localized_name

        # 복잡도 레벨 현지화
        complexity_mapping = {
            1: "basic",
            2: "basic",
            3: "basic",
            4: "intermediate",
            5: "intermediate",
            6: "intermediate",
            7: "advanced",
            8: "advanced",
            9: "expert",
            10: "expert",
        }

        # 템플릿별 복잡도 텍스트 현지화
        if "templates" in localized_data:
            for template_id, template_info in localized_data["templates"].items():
                complexity_score = template_info.get("complexity_score", 5)
                complexity_level = complexity_mapping.get(
                    complexity_score, "intermediate"
                )
                complexity_key = f"templates.complexity.{complexity_level}"
                template_info["localized_complexity"] = self.get_text(
                    complexity_key, language
                )

                # 티어 정보 현지화
                if "recommended_tier" in template_info:
                    tier = template_info["recommended_tier"]
                    tier_key = f"templates.tier.{tier}"
                    template_info["localized_tier"] = self.get_text(tier_key, language)

        return localized_data

    def get_progress_stage_text(self, stage: str, language: str = None) -> str:
        """진행 단계 텍스트 현지화"""
        key = f"progress.stages.{stage}"
        return self.get_text(key, language)

    def format_progress_message(
        self, percent: int, estimated_time: str = None, language: str = None
    ) -> Dict[str, str]:
        """진행률 메시지 포맷팅"""
        messages = {
            "percentage": self.get_text(
                "progress.percentage", language, percent=percent
            )
        }

        if estimated_time:
            messages["estimated_time"] = self.get_text(
                "progress.estimated_time", language, time=estimated_time
            )

        return messages

    def reload_translations(self):
        """번역 파일 다시 로드 (개발 시 유용)"""
        self.get_text.cache_clear()  # 캐시 초기화
        self._load_translations()
        logger.info("번역 파일이 다시 로드되었습니다")


# 전역 인스턴스
i18n_service = I18nService()


def get_text(key: str, language: str = None, **kwargs) -> str:
    """편의 함수: 번역 텍스트 가져오기"""
    return i18n_service.get_text(key, language, **kwargs)


def get_error_message(error_type: str, language: str = None, **kwargs) -> str:
    """편의 함수: 에러 메시지 가져오기"""
    return i18n_service.get_localized_error_message(error_type, language, **kwargs)


def detect_language_from_header(accept_language: str) -> str:
    """편의 함수: Accept-Language 헤더에서 언어 감지"""
    return i18n_service.get_language_from_accept_header(accept_language)
