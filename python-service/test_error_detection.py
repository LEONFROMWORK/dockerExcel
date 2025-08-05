#!/usr/bin/env python
"""
Excel 오류 감지 테스트 스크립트
"""

import asyncio
import sys
import os

# 프로젝트 경로를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.excel_analyzer import excel_analyzer


async def test_error_detection():
    """Excel 파일의 오류 감지 테스트"""
    file_path = "/Users/kevin/Downloads/7777777.xlsx"

    print(f"파일 분석 중: {file_path}")
    print("-" * 80)

    try:
        result = await excel_analyzer.analyze_file(file_path)

        # 오류 정보 출력
        errors = result.get("errors", [])
        print(f"감지된 오류 수: {len(errors)}")
        print("-" * 80)

        # 오류를 시트별로 그룹화
        errors_by_sheet = {}
        for error in errors:
            sheet = error.get("sheet", "Unknown")
            if sheet not in errors_by_sheet:
                errors_by_sheet[sheet] = []
            errors_by_sheet[sheet].append(error)

        # 시트별로 오류 출력
        for sheet, sheet_errors in errors_by_sheet.items():
            print(f"\n[{sheet} 시트] - {len(sheet_errors)}개 오류")
            print("-" * 50)

            for error in sheet_errors:
                print(f"셀: {error.get('cell')}")
                print(f"오류 타입: {error.get('error_type')}")
                print(f"카테고리: {error.get('category', '미분류')}")
                print(f"설명: {error.get('description')}")
                print(f"심각도: {error.get('severity')}")
                print(f"값: {error.get('value')}")
                if error.get("formula"):
                    print(f"수식: {error.get('formula')}")
                if error.get("suggestion"):
                    print(f"제안: {error.get('suggestion')}")
                print("-" * 30)

        # 카테고리별 통계
        print("\n카테고리별 통계:")
        category_counts = {}
        for error in errors:
            category = error.get("category", "미분류")
            category_counts[category] = category_counts.get(category, 0) + 1

        for category, count in category_counts.items():
            print(f"  {category}: {count}개")

        # 오류 타입별 통계
        print("\n오류 타입별 통계:")
        type_counts = {}
        for error in errors:
            error_type = error.get("error_type", "Unknown")
            type_counts[error_type] = type_counts.get(error_type, 0) + 1

        for error_type, count in type_counts.items():
            print(f"  {error_type}: {count}개")

    except Exception as e:
        print(f"오류 발생: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_error_detection())
