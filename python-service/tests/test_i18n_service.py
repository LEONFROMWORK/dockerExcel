"""
국제화(i18n) 서비스 테스트
Internationalization Service Tests
"""

from app.services.i18n_service import (
    I18nService,
    i18n_service,
    get_text,
    get_error_message,
)


class TestI18nService:
    """국제화 서비스 테스트"""

    def test_service_initialization(self):
        """서비스 초기화 테스트"""
        service = I18nService()

        assert service.default_language == "ko"
        assert len(service.supported_languages) == 4
        assert "ko" in service.supported_languages
        assert "en" in service.supported_languages
        assert "ja" in service.supported_languages
        assert "zh" in service.supported_languages

        print("✅ 서비스 초기화 테스트 통과")

    def test_translation_files_loaded(self):
        """번역 파일 로드 테스트"""

        # 모든 지원 언어의 번역이 로드되었는지 확인
        for language in i18n_service.supported_languages:
            assert language in i18n_service.translations
            assert isinstance(i18n_service.translations[language], dict)
            assert len(i18n_service.translations[language]) > 0

        print(f"✅ 번역 파일 로드 테스트 통과: {len(i18n_service.translations)}개 언어")

    def test_get_text_basic(self):
        """기본 텍스트 가져오기 테스트"""

        # 한국어 테스트
        korean_success = i18n_service.get_text("common.success", "ko")
        assert korean_success == "성공"

        # 영어 테스트
        english_success = i18n_service.get_text("common.success", "en")
        assert english_success == "Success"

        # 일본어 테스트
        japanese_success = i18n_service.get_text("common.success", "ja")
        assert japanese_success == "成功"

        # 중국어 테스트
        chinese_success = i18n_service.get_text("common.success", "zh")
        assert chinese_success == "成功"

        print("✅ 기본 텍스트 가져오기 테스트 통과")

    def test_get_text_with_formatting(self):
        """포맷팅 변수를 포함한 텍스트 테스트"""

        # 한국어 포맷팅
        korean_formatted = i18n_service.get_text(
            "excel.analysis.sheets_found", "ko", count=5
        )
        assert "5개의 시트" in korean_formatted

        # 영어 포맷팅
        english_formatted = i18n_service.get_text(
            "excel.analysis.sheets_found", "en", count=3
        )
        assert "Found 3 sheets" == english_formatted

        print("✅ 포맷팅 변수 테스트 통과")

    def test_fallback_to_english(self):
        """영어 폴백 테스트"""

        # 존재하지 않는 키를 한국어로 요청했을 때 영어로 폴백
        nonexistent_key = "nonexistent.key.test"
        result = i18n_service.get_text(nonexistent_key, "ko")

        # 키 자체가 반환되어야 함 (영어에도 없는 경우)
        assert result == nonexistent_key

        print("✅ 영어 폴백 테스트 통과")

    def test_unsupported_language(self):
        """지원하지 않는 언어 처리 테스트"""

        # 지원하지 않는 언어 코드
        result = i18n_service.get_text("common.success", "fr")  # 프랑스어

        # 기본 언어(한국어)로 폴백되어야 함
        assert result == "성공"

        print("✅ 지원하지 않는 언어 처리 테스트 통과")

    def test_accept_language_parsing(self):
        """Accept-Language 헤더 파싱 테스트"""

        # 복잡한 Accept-Language 헤더
        test_cases = [
            ("ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7", "ko"),
            ("en-US,en;q=0.9,fr;q=0.8", "en"),
            ("ja,en;q=0.8", "ja"),
            ("zh-CN,zh;q=0.9", "zh"),
            ("fr,de;q=0.8", "ko"),  # 지원하지 않는 언어들 -> 기본값
            ("", "ko"),  # 빈 문자열 -> 기본값
        ]

        for accept_language, expected in test_cases:
            result = i18n_service.get_language_from_accept_header(accept_language)
            assert (
                result == expected
            ), f"Expected {expected}, got {result} for {accept_language}"

        print("✅ Accept-Language 헤더 파싱 테스트 통과")

    def test_language_validation(self):
        """언어 코드 유효성 검사 테스트"""

        # 유효한 언어들
        valid_languages = ["ko", "en", "ja", "zh"]
        for lang in valid_languages:
            assert i18n_service.validate_language(lang) is True

        # 무효한 언어들
        invalid_languages = ["fr", "de", "es", "invalid", ""]
        for lang in invalid_languages:
            assert i18n_service.validate_language(lang) is False

        print("✅ 언어 코드 유효성 검사 테스트 통과")

    def test_error_message_localization(self):
        """에러 메시지 현지화 테스트"""

        # 파일 관련 에러 메시지
        korean_error = i18n_service.get_localized_error_message(
            "invalid_file_type", "ko", extensions=".xlsx, .xls"
        )
        assert "유효하지 않은 파일 형식" in korean_error
        assert ".xlsx, .xls" in korean_error

        # 영어 에러 메시지
        english_error = i18n_service.get_localized_error_message(
            "file_too_large", "en", max_size=10485760
        )
        assert "File too large" in english_error
        assert "10485760" in english_error

        print("✅ 에러 메시지 현지화 테스트 통과")

    def test_template_metadata_localization(self):
        """템플릿 메타데이터 현지화 테스트"""

        # 샘플 템플릿 데이터
        template_data = {
            "categories": {
                "financial_statements": {
                    "name": "Financial Statements",
                    "description": "Income statements, balance sheets, etc.",
                }
            },
            "templates": {
                "test_template": {
                    "name": "Test Template",
                    "complexity_score": 7,
                    "recommended_tier": "pro",
                    "category": "financial_statements",
                }
            },
        }

        # 한국어 현지화
        localized_ko = i18n_service.localize_template_metadata(template_data, "ko")

        # 카테고리 현지화 확인
        financial_category = localized_ko["categories"]["financial_statements"]
        assert "localized_name" in financial_category
        assert financial_category["localized_name"] == "재무제표"

        # 템플릿 복잡도 현지화 확인
        test_template = localized_ko["templates"]["test_template"]
        assert "localized_complexity" in test_template
        assert test_template["localized_complexity"] == "고급"

        # 티어 현지화 확인
        assert "localized_tier" in test_template
        assert test_template["localized_tier"] == "프로"

        print("✅ 템플릿 메타데이터 현지화 테스트 통과")

    def test_progress_stage_localization(self):
        """진행 단계 현지화 테스트"""

        # 진행 단계들
        stages = ["uploaded", "analyzing", "completed", "failed"]

        for stage in stages:
            # 한국어
            korean_stage = i18n_service.get_progress_stage_text(stage, "ko")
            assert korean_stage != stage  # 번역된 텍스트여야 함

            # 영어
            english_stage = i18n_service.get_progress_stage_text(stage, "en")
            assert english_stage != stage  # 번역된 텍스트여야 함

        print("✅ 진행 단계 현지화 테스트 통과")

    def test_convenience_functions(self):
        """편의 함수 테스트"""

        # get_text 편의 함수
        text = get_text("common.error", "en")
        assert text == "Error"

        # get_error_message 편의 함수
        error_msg = get_error_message("file_not_found", "ko")
        assert "파일을 찾을 수 없습니다" in error_msg

        print("✅ 편의 함수 테스트 통과")

    def test_caching_behavior(self):
        """캐싱 동작 테스트"""

        # 같은 키로 여러 번 호출
        text1 = i18n_service.get_text("common.success", "ko")
        text2 = i18n_service.get_text("common.success", "ko")
        text3 = i18n_service.get_text("common.success", "ko")

        # 모두 같은 결과여야 함
        assert text1 == text2 == text3 == "성공"

        print("✅ 캐싱 동작 테스트 통과")

    def test_get_supported_languages(self):
        """지원 언어 목록 테스트"""

        languages = i18n_service.get_supported_languages()

        assert isinstance(languages, dict)
        assert "ko" in languages
        assert "en" in languages
        assert "ja" in languages
        assert "zh" in languages

        assert languages["ko"] == "한국어"
        assert languages["en"] == "English"
        assert languages["ja"] == "日本語"
        assert languages["zh"] == "中文"

        print("✅ 지원 언어 목록 테스트 통과")


class TestI18nIntegration:
    """통합 테스트"""

    def test_multiple_language_workflow(self):
        """다국어 워크플로우 통합 테스트"""

        # 시나리오: 파일 분석 결과를 여러 언어로 표시
        file_info = {
            "filename": "test.xlsx",
            "sheet_count": 3,
            "formula_count": 15,
            "error_count": 2,
        }

        languages = ["ko", "en", "ja", "zh"]
        results = {}

        for lang in languages:
            results[lang] = {
                "title": i18n_service.get_text("excel.analysis.title", lang),
                "sheets": i18n_service.get_text(
                    "excel.analysis.sheets_found", lang, count=file_info["sheet_count"]
                ),
                "formulas": i18n_service.get_text(
                    "excel.analysis.formulas_found",
                    lang,
                    count=file_info["formula_count"],
                ),
                "errors": i18n_service.get_text(
                    "excel.analysis.errors_found", lang, count=file_info["error_count"]
                ),
            }

        # 결과 검증
        assert results["ko"]["title"] == "Excel 분석"
        assert results["en"]["title"] == "Excel Analysis"
        assert results["ja"]["title"] == "Excel分析"
        assert results["zh"]["title"] == "Excel分析"

        assert "3개의 시트" in results["ko"]["sheets"]
        assert "Found 3 sheets" == results["en"]["sheets"]

        print("✅ 다국어 워크플로우 통합 테스트 통과")

    def test_real_world_scenario(self):
        """실제 사용 시나리오 테스트"""

        # Accept-Language 헤더에서 언어 감지
        accept_language = "ja,en;q=0.8,ko;q=0.6"
        detected_language = i18n_service.get_language_from_accept_header(
            accept_language
        )

        # 에러 상황 시뮬레이션
        error_type = "invalid_file_type"
        error_message = i18n_service.get_localized_error_message(
            error_type, detected_language, extensions=".xlsx, .xls"
        )

        # 일본어로 번역되었는지 확인
        assert detected_language == "ja"
        assert "無効なファイル形式" in error_message
        assert ".xlsx, .xls" in error_message

        print("✅ 실제 사용 시나리오 테스트 통과")


if __name__ == "__main__":
    # 간단한 테스트 실행
    test_i18n = TestI18nService()
    test_integration = TestI18nIntegration()

    print("🧪 국제화(i18n) 서비스 테스트 시작")

    try:
        # 기본 테스트
        test_i18n.test_service_initialization()
        test_i18n.test_translation_files_loaded()
        test_i18n.test_get_text_basic()
        test_i18n.test_get_text_with_formatting()
        test_i18n.test_fallback_to_english()
        test_i18n.test_unsupported_language()
        test_i18n.test_accept_language_parsing()
        test_i18n.test_language_validation()
        test_i18n.test_error_message_localization()
        test_i18n.test_template_metadata_localization()
        test_i18n.test_progress_stage_localization()
        test_i18n.test_convenience_functions()
        test_i18n.test_caching_behavior()
        test_i18n.test_get_supported_languages()

        # 통합 테스트
        test_integration.test_multiple_language_workflow()
        test_integration.test_real_world_scenario()

        print("✅ 모든 i18n 테스트 통과!")

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback

        traceback.print_exc()
