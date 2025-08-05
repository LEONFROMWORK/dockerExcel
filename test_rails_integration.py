#!/usr/bin/env python3
"""
Rails API를 통한 Excel 오류 감지 통합 테스트
"""
import requests
import json
import time

def test_rails_integration():
    """Rails API를 통해 Excel 파일 업로드 및 분석 테스트"""

    # 테스트할 파일 경로
    excel_file_path = "/Users/kevin/Downloads/66기초입문-17-엑셀-오류의-모든-것-예제파일.xlsx"

    # 1. Excel 파일 업로드
    print("1. Excel 파일 업로드 중...")
    upload_url = "http://localhost:3000/api/v1/excel_analysis/files"

    with open(excel_file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(upload_url, files=files)

    if response.status_code != 200:
        print(f"업로드 실패: {response.status_code}")
        print(response.text)
        return

    upload_result = response.json()
    print(f"업로드 응답: {json.dumps(upload_result, indent=2, ensure_ascii=False)}")

    # 응답 구조에 따라 ID 추출
    file_id = upload_result.get('id') or upload_result.get('file_id')
    session_id = upload_result.get('session_id') or upload_result.get('analysis', {}).get('session_id')

    print(f"파일 업로드 성공! file_id: {file_id}, session_id: {session_id}")

    # 2. 분석 시작
    print("\n2. 분석 시작...")
    analyze_url = "http://localhost:3000/api/v1/excel_analysis/analyze"
    analyze_data = {"file_id": file_id}
    response = requests.post(analyze_url, json=analyze_data)

    if response.status_code != 200:
        print(f"분석 시작 실패: {response.status_code}")
        print(response.text)
        return

    analyze_result = response.json()
    session_id = analyze_result.get('session_id')
    print(f"분석 시작됨! session_id: {session_id}")

    # 3. 분석 상태 확인 (polling)
    print("\n3. 분석 상태 확인 중...")
    status_url = f"http://localhost:3000/api/v1/excel_analysis/status/{session_id}"

    max_attempts = 30  # 최대 30초 대기
    for attempt in range(max_attempts):
        response = requests.get(status_url)

        if response.status_code == 200:
            status_data = response.json()
            status = status_data.get('status')
            progress = status_data.get('progress', 0)

            print(f"상태: {status} ({progress}%)")

            if status == 'completed':
                errors = status_data.get('errors', [])
                print(f"\n=== 분석 완료 ===")
                print(f"총 {len(errors)}개의 오류 발견:")
                print("-" * 50)

                for i, error in enumerate(errors, 1):
                    print(f"\n오류 {i}:")
                    print(f"  위치: {error.get('sheet', 'N/A')}!{error.get('cell', 'N/A')}")
                    print(f"  타입: {error.get('type', 'N/A')}")
                    print(f"  설명: {error.get('message', 'N/A')}")
                    print(f"  심각도: {error.get('severity', 'N/A')}")
                    if error.get('formula'):
                        print(f"  수식: {error.get('formula')}")
                    if error.get('suggestion'):
                        print(f"  제안: {error.get('suggestion')}")

                # 오류 타입별 요약
                error_types = {}
                for error in errors:
                    error_type = error.get('type', 'unknown')
                    error_types[error_type] = error_types.get(error_type, 0) + 1

                print(f"\n\n오류 타입별 요약:")
                print("-" * 30)
                for error_type, count in error_types.items():
                    print(f"  {error_type}: {count}개")

                return

            elif status == 'failed':
                print(f"분석 실패: {status_data.get('error', 'Unknown error')}")
                return

        time.sleep(1)  # 1초 대기

    print("분석 시간 초과")

if __name__ == "__main__":
    test_rails_integration()
