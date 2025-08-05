#!/usr/bin/env python
"""
IntegratedErrorDetector 통합 테스트 스크립트
전체 시스템이 올바르게 작동하는지 검증
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.services.error_classification_service import ErrorClassificationService
from app.services.fix_recommendation_service import FixRecommendationService
from app.core.interfaces import ExcelError


async def test_integrated_system():
    """통합 시스템 테스트"""
    print("=== IntegratedErrorDetector 통합 테스트 시작 ===")
    print(f"시작 시간: {datetime.now()}")

    # 테스트 파일 경로
    test_file = "/Users/kevin/Downloads/66기초입문-17-엑셀-오류의-모든-것-예제파일.xlsx"

    if not os.path.exists(test_file):
        print(f"❌ 테스트 파일을 찾을 수 없습니다: {test_file}")
        return False

    try:
        # 1. IntegratedErrorDetector 테스트
        print("\n1. IntegratedErrorDetector 테스트...")
        detector = IntegratedErrorDetector()
        result = await detector.detect_all_errors(test_file)
        errors_dict = result["errors"]

        # dict를 ExcelError 객체로 변환
        errors = []
        for err_dict in errors_dict:
            error = ExcelError(
                id=err_dict.get("id", ""),
                type=err_dict.get("type", ""),
                sheet=err_dict.get("sheet", ""),
                cell=err_dict.get("cell", ""),
                message=err_dict.get("message", ""),
                severity=err_dict.get("severity", "medium"),
                is_auto_fixable=err_dict.get("is_auto_fixable", False),
                suggested_fix=err_dict.get("suggested_fix", ""),
                formula=err_dict.get("formula"),
                value=err_dict.get("value"),
                confidence=err_dict.get("confidence", 0.5),
            )
            errors.append(error)

        print(f"✅ 감지된 오류 수: {len(errors)}")

        # 오류 타입별 분류
        error_types = {}
        for error in errors:
            # error가 dict인지 객체인지 확인
            if isinstance(error, dict):
                error_type = error.get("type", "Unknown")
            else:
                error_type = error.type
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1

        print("\n오류 타입별 통계:")
        for error_type, count in sorted(
            error_types.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  - {error_type}: {count}개")

        # 2. ErrorClassificationService 테스트
        print("\n2. ErrorClassificationService 테스트...")
        classifier = ErrorClassificationService()

        # 오류 분류
        classified_errors = classifier.classify_errors(errors)
        print(f"✅ 오류 카테고리 수: {len(classified_errors)}")

        for category, errors_list in classified_errors.items():
            print(f"  - {category}: {len(errors_list)}개")

        # 오류 요약
        error_summary = classifier.get_error_summary(errors)
        print("\n오류 요약:")
        print(f"  - 총 오류: {error_summary['total']}")
        print(f"  - 중요 오류: {error_summary['critical_count']}")
        print(f"  - 자동 수정 가능: {error_summary['auto_fixable']}")
        print(f"  - 자동 수정률: {error_summary['auto_fix_rate']}%")

        # 3. FixRecommendationService 테스트
        print("\n3. FixRecommendationService 테스트...")
        recommender = FixRecommendationService()

        # 상위 5개 오류에 대한 수정 제안
        prioritized_errors = classifier.prioritize_errors(errors)

        print("\n상위 5개 중요 오류 및 수정 제안:")
        for i, error in enumerate(prioritized_errors[:5], 1):
            recommendation = recommender.generate_recommendations(error)
            print(f"\n{i}. {error.type} at {error.sheet}!{error.cell}")
            print(f"   심각도: {error.severity}")
            print(f"   메시지: {error.message}")
            print(f"   자동 수정 가능: {'예' if error.is_auto_fixable else '아니오'}")

            if recommendation["fixes"]:
                print("   수정 방법:")
                for fix in recommendation["fixes"]:
                    print(f"     - {fix.get('description', fix.get('code', ''))}")

        # 4. VBA 오류 감지 테스트
        vba_errors = [e for e in errors if "vba" in e.type.lower()]
        if vba_errors:
            print("\n4. VBA 오류 감지 테스트...")
            print(f"✅ VBA 관련 오류 {len(vba_errors)}개 감지")

            # VBA 오류 타입 분석
            vba_types = {}
            for error in vba_errors:
                vba_type = error.type
                if vba_type not in vba_types:
                    vba_types[vba_type] = 0
                vba_types[vba_type] += 1

            print("\nVBA 오류 타입:")
            for vba_type, count in vba_types.items():
                print(f"  - {vba_type}: {count}개")
        else:
            print("\n4. VBA 오류 감지 테스트...")
            print("ℹ️ VBA 코드가 없거나 VBA 오류가 없습니다")

        # 5. 캐싱 성능 테스트
        print("\n5. 캐싱 성능 테스트...")
        import time

        # 첫 번째 실행 (캐시 없음)
        start_time = time.time()
        result1 = await detector.detect_all_errors(test_file)
        errors1 = result1["errors"]
        first_run_time = time.time() - start_time

        # 두 번째 실행 (캐시 사용)
        start_time = time.time()
        result2 = await detector.detect_all_errors(test_file)
        errors2 = result2["errors"]
        second_run_time = time.time() - start_time

        print(f"✅ 첫 번째 실행 시간: {first_run_time:.2f}초")
        print(f"✅ 두 번째 실행 시간 (캐시): {second_run_time:.2f}초")
        print(
            f"✅ 성능 향상: {((first_run_time - second_run_time) / first_run_time * 100):.1f}%"
        )

        # 결과 검증
        assert len(errors1) == len(errors2), "캐시된 결과가 일치하지 않습니다"

        print("\n=== 통합 테스트 완료 ===")
        print(f"종료 시간: {datetime.now()}")
        print("✅ 모든 테스트가 성공적으로 완료되었습니다!")

        return True

    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def test_validate_and_report():
    """validate-and-report 엔드포인트 테스트"""
    print("\n=== validate-and-report 엔드포인트 테스트 ===")

    try:
        import aiohttp

        # Python 서비스 URL
        base_url = "http://localhost:8000"

        # 테스트 파일
        test_file = (
            "/Users/kevin/Downloads/66기초입문-17-엑셀-오류의-모든-것-예제파일.xlsx"
        )

        if not os.path.exists(test_file):
            print(f"❌ 테스트 파일을 찾을 수 없습니다: {test_file}")
            return False

        async with aiohttp.ClientSession() as session:
            # 파일 업로드
            with open(test_file, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("file", f, filename=os.path.basename(test_file))
                data.add_field("session_id", "test-session-123")
                data.add_field("user_id", "test-user")

                async with session.post(
                    f"{base_url}/api/v1/excel/validate-and-report", data=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        print("✅ validate-and-report 성공!")
                        print("\n검증 결과:")
                        print(
                            f"- 총 오류: {result['validation_results']['total_errors']}"
                        )
                        print(
                            f"- 자동 수정 가능: {result['validation_results']['auto_fixable_count']}"
                        )

                        print("\nAI 보고서 (첫 500자):")
                        print(result["ai_report"][:500] + "...")

                        return True
                    else:
                        print(f"❌ 엔드포인트 호출 실패: {response.status}")
                        error_text = await response.text()
                        print(f"오류: {error_text}")
                        return False

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        return False


async def main():
    """메인 테스트 함수"""
    # 1. 통합 시스템 테스트
    success1 = await test_integrated_system()

    # 2. API 엔드포인트 테스트 (서버가 실행 중인 경우)
    print("\n" + "=" * 50)
    try:
        success2 = await test_validate_and_report()
    except (ValueError, TypeError):
        print("ℹ️ API 서버가 실행 중이 아닙니다. API 테스트 건너뜀")
        success2 = True

    # 전체 결과
    print("\n" + "=" * 50)
    print("=== 전체 테스트 결과 ===")
    if success1 and success2:
        print("✅ 모든 테스트 통과!")
        return 0
    else:
        print("❌ 일부 테스트 실패")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
