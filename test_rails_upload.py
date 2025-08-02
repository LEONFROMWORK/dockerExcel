#!/usr/bin/env python3
"""
Rails API를 통한 Excel 파일 업로드 및 렌더링 테스트
"""
import requests
import json
import time
from pathlib import Path

def test_rails_excel_upload():
    """Rails API로 Excel 파일 업로드 테스트"""
    
    print("🚀 Rails Excel 업로드 테스트 시작...")
    
    # 테스트 파일 경로
    test_file = Path("python-service/test_advanced_formatting.xlsx")
    if not test_file.exists():
        print("❌ 테스트 파일을 찾을 수 없습니다")
        return
    
    # Rails API 엔드포인트
    upload_url = "http://localhost:3000/api/v1/excel_analysis/files"
    
    print(f"📁 파일: {test_file}")
    print(f"🔗 업로드 URL: {upload_url}")
    
    # 파일 업로드
    try:
        with open(test_file, 'rb') as f:
            files = {'file': (test_file.name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            
            print("\n📤 파일 업로드 중...")
            response = requests.post(upload_url, files=files)
            
            print(f"📡 응답 상태: {response.status_code}")
            
            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                print("✅ 업로드 성공!")
                print(f"\n📊 결과:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                
                # 파일 ID 추출
                file_id = result.get('data', {}).get('id') or result.get('id')
                if file_id:
                    print(f"\n🆔 파일 ID: {file_id}")
                    
                    # 분석 결과 확인
                    time.sleep(2)  # 처리 대기
                    check_analysis_result(file_id)
                    
            else:
                print(f"❌ 업로드 실패: {response.status_code}")
                print(f"응답: {response.text}")
                
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

def check_analysis_result(file_id):
    """분석 결과 확인"""
    analysis_url = f"http://localhost:3000/api/v1/excel/files/{file_id}"
    
    print(f"\n🔍 분석 결과 확인 중... (ID: {file_id})")
    
    try:
        response = requests.get(analysis_url)
        
        if response.status_code == 200:
            result = response.json()
            data = result.get('data', result)
            
            print("\n✅ 분석 결과:")
            
            # Univer 데이터 확인
            if 'univer_data' in data:
                univer_data = data['univer_data']
                if isinstance(univer_data, str):
                    univer_data = json.loads(univer_data)
                
                print("\n📊 Univer 데이터 구조:")
                
                # 시트 정보
                sheets = univer_data.get('sheets', {})
                print(f"  시트 수: {len(sheets)}")
                
                for sheet_id, sheet in sheets.items():
                    print(f"\n  시트: {sheet.get('name', sheet_id)}")
                    print(f"    조건부 서식: {len(sheet.get('conditionalFormats', []))}개")
                    print(f"    데이터 유효성: {len(sheet.get('dataValidations', []))}개")
                    
                # 스타일 정보
                styles = univer_data.get('styles', {})
                numfmt_count = sum(1 for s in styles.values() if 'numberFormat' in s or 'numfmt' in s)
                print(f"\n  스타일 정보:")
                print(f"    총 스타일: {len(styles)}개")
                print(f"    숫자 포맷: {numfmt_count}개")
                
        else:
            print(f"❌ 분석 결과 조회 실패: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 오류: {e}")

def print_test_instructions():
    """테스트 방법 안내"""
    print("\n" + "="*60)
    print("📋 브라우저 테스트 방법:")
    print("="*60)
    print("1. 브라우저에서 http://localhost:3000 접속")
    print("2. Excel 파일 업로드 기능 찾기")
    print("3. test_advanced_formatting.xlsx 파일 업로드")
    print("4. 개발자 도구(F12) > Console 탭 열기")
    print("5. 다음 로그 확인:")
    print("   - 🎨 Registering advanced formatting plugins...")
    print("   - 📊 Number format styles")
    print("   - 🎨 Advanced formatting data")
    print("\n💡 추가 확인사항:")
    print("   - 숫자 포맷이 제대로 표시되는지")
    print("   - 조건부 서식이 적용되는지")
    print("   - 데이터 유효성 검사가 작동하는지")
    print("="*60)

if __name__ == "__main__":
    test_rails_excel_upload()
    print_test_instructions()