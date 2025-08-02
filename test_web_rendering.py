#!/usr/bin/env python3
"""
웹 브라우저에서 Excel 파일 업로드 및 렌더링 테스트
"""
import time
import requests
import json
from pathlib import Path

# 서버 URL
BASE_URL = "http://localhost:3000"
API_URL = f"{BASE_URL}/api/v1"

def test_excel_upload():
    """Excel 파일 업로드 및 렌더링 테스트"""
    
    print("🌐 웹 렌더링 테스트 시작...")
    
    # 테스트 파일 경로
    test_file = Path("python-service/test_advanced_formatting.xlsx")
    if not test_file.exists():
        print("❌ 테스트 파일이 없습니다:", test_file)
        return
    
    print(f"📁 테스트 파일: {test_file}")
    
    # 1. 서버 상태 확인
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Rails 서버 연결 성공")
        else:
            print(f"⚠️ Rails 서버 응답: {response.status_code}")
    except Exception as e:
        print(f"❌ Rails 서버 연결 실패: {e}")
        return
    
    # 2. Python 서비스 상태 확인
    try:
        response = requests.get("http://localhost:8000/api/v1/health")
        if response.status_code == 200:
            print("✅ Python 서비스 연결 성공")
        else:
            print(f"⚠️ Python 서비스 응답: {response.status_code}")
    except Exception as e:
        print(f"❌ Python 서비스 연결 실패: {e}")
        return
    
    print("\n📊 Excel 파일 업로드 준비...")
    print("🔗 브라우저에서 다음 주소로 접속하세요:")
    print(f"   {BASE_URL}")
    print("\n📋 테스트 순서:")
    print("1. Excel 파일 업로드 버튼 클릭")
    print("2. test_advanced_formatting.xlsx 파일 선택")
    print("3. 업로드 및 분석 대기")
    print("4. 브라우저 콘솔(F12) 열기")
    print("5. 다음 로그 확인:")
    print("   - 🎨 Registering advanced formatting plugins...")
    print("   - 📊 Number format styles")
    print("   - 🎨 Advanced formatting data")
    print("\n💡 콘솔에서 다음 명령으로 상세 정보 확인:")
    print("   console.log(window.univerInstance)")
    
    # Univer 데이터 구조 샘플 출력
    sample_file = Path("python-service/test_advanced_formatting_univer.json")
    if sample_file.exists():
        print(f"\n📄 변환된 Univer 데이터: {sample_file}")
        with open(sample_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print("\n🔍 데이터 요약:")
        for sheet_id, sheet in data.get('sheets', {}).items():
            print(f"\n시트: {sheet.get('name', sheet_id)}")
            print(f"  조건부 서식: {len(sheet.get('conditionalFormats', []))}개")
            print(f"  데이터 유효성: {len(sheet.get('dataValidations', []))}개")
            
        styles = data.get('styles', {})
        numfmt_count = sum(1 for s in styles.values() if 'numberFormat' in s)
        print(f"\n스타일 정보:")
        print(f"  총 스타일: {len(styles)}개")
        print(f"  숫자 포맷 스타일: {numfmt_count}개")

if __name__ == "__main__":
    test_excel_upload()