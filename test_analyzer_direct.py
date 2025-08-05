#!/usr/bin/env python3
"""
Excel Analyzer 직접 테스트
"""
import asyncio
import sys
import os
sys.path.append('/Users/kevin/excel-unified/python-service')

from app.services.excel_analyzer import excel_analyzer

async def test_excel_analyzer():
    """Excel Analyzer 직접 테스트"""

    # 테스트할 파일 경로
    excel_file_path = "/Users/kevin/Downloads/66기초입문-17-엑셀-오류의-모든-것-예제파일.xlsx"

    if not os.path.exists(excel_file_path):
        print(f"파일을 찾을 수 없습니다: {excel_file_path}")
        return

    try:
        # 직접 analyze_file 호출
        result = await excel_analyzer.analyze_file(excel_file_path)

        print("=== Excel 오류 감지 결과 ===")

        # 오류 정보 출력
        if 'errors' in result:
            errors = result['errors']
            print(f"\n총 {len(errors)}개의 오류 발견:")
            print("-" * 50)

            for i, error in enumerate(errors, 1):
                print(f"\n오류 {i}:")
                print(f"  위치: {error.get('location', 'N/A')}")
                print(f"  타입: {error.get('error_type', 'N/A')}")
                print(f"  설명: {error.get('description', 'N/A')}")
                print(f"  심각도: {error.get('severity', 'N/A')}")
                if error.get('formula'):
                    print(f"  수식: {error.get('formula')}")
                if error.get('suggestion'):
                    print(f"  제안: {error.get('suggestion')}")

            # 오류 타입별 요약
            if 'summary' in result:
                summary = result['summary']
                if 'error_types' in summary:
                    print(f"\n\n오류 타입별 요약:")
                    print("-" * 30)
                    for error_type, count in summary['error_types'].items():
                        print(f"  {error_type}: {count}개")
        else:
            print("오류가 발견되지 않았습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_excel_analyzer())
