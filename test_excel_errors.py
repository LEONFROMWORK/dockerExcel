#!/usr/bin/env python3
"""
Excel 오류 감지 시스템 테스트
"""
import requests
import json
import sys

def test_excel_error_detection():
    """엑셀 파일의 오류 감지를 테스트"""

    # 테스트할 파일 경로
    excel_file_path = "/Users/kevin/Downloads/66기초입문-17-엑셀-오류의-모든-것-예제파일.xlsx"

    # Python 서비스에 직접 요청
    # excel.py가 비활성화되어 있으므로 excel_processing.py 사용
    url = "http://localhost:8000/api/v1/excel/process"

    with open(excel_file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, files=files)

    if response.status_code == 200:
        result = response.json()

        print("=== Excel 오류 감지 결과 ===")

        # 파일 정보
        if 'file_analysis' in result:
            analysis = result['file_analysis']

            # 오류 정보
            if 'errors' in analysis:
                errors = analysis['errors']
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
                if 'summary' in analysis:
                    summary = analysis['summary']
                    if 'error_types' in summary:
                        print(f"\n\n오류 타입별 요약:")
                        print("-" * 30)
                        for error_type, count in summary['error_types'].items():
                            print(f"  {error_type}: {count}개")
            else:
                print("오류가 발견되지 않았습니다.")
        else:
            print("분석 결과를 찾을 수 없습니다.")
            print(f"응답 구조: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print(f"오류 발생: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_excel_error_detection()
