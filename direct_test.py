#!/usr/bin/env python3
"""
Excel to Univer 변환 직접 테스트
Python 서비스 없이 직접 변환기를 테스트합니다.
"""

import sys
import json
from pathlib import Path

# Python 서비스 경로 추가
sys.path.append('/Users/kevin/excel-unified/python-service')

def test_excel_to_univer_conversion():
    """Excel to Univer 변환 직접 테스트"""
    
    try:
        from app.services.excel_to_univer import ExcelToUniverConverter
        
        # 테스트 파일 경로
        excel_file = Path("/Users/kevin/excel-unified/test_sample.xlsx")
        
        if not excel_file.exists():
            print(f"❌ 테스트 파일이 없습니다: {excel_file}")
            return False
        
        print("🔧 Excel to Univer 변환기 직접 테스트")
        print(f"📄 파일: {excel_file}")
        print(f"📊 크기: {excel_file.stat().st_size:,} bytes")
        
        # 변환기 인스턴스 생성
        converter = ExcelToUniverConverter()
        
        # 변환 실행
        print("⚙️  변환 중...")
        result = converter.convert_excel_file(str(excel_file))
        
        print("✅ 변환 성공!")
        
        # 결과 구조 분석
        if 'data' in result:
            data = result['data']
            print(f"📋 결과 구조:")
            
            if 'sheets' in data:
                sheets = data['sheets']
                print(f"  📊 시트 수: {len(sheets)}")
                
                for sheet_id, sheet_data in sheets.items():
                    print(f"    - 시트 ID: {sheet_id}")
                    if 'name' in sheet_data:
                        print(f"      이름: {sheet_data['name']}")
                    if 'cellData' in sheet_data:
                        cell_count = len(sheet_data['cellData'])
                        print(f"      셀 수: {cell_count}")
                        
                        # 첫 번째 셀 데이터 예시
                        if cell_count > 0:
                            first_cell = list(sheet_data['cellData'].keys())[0]
                            first_cell_data = sheet_data['cellData'][first_cell]
                            print(f"      첫 번째 셀 ({first_cell}): {first_cell_data}")
            
            # 메타데이터
            if 'sheetOrder' in data:
                print(f"  🔄 시트 순서: {data['sheetOrder']}")
            
            if 'metadata' in result:
                metadata = result['metadata']
                print(f"  📋 메타데이터:")
                for key, value in metadata.items():
                    print(f"    {key}: {value}")
        
        return True
        
    except ImportError as e:
        print(f"❌ 모듈 가져오기 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 변환 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_excel_to_univer_conversion()
    
    if success:
        print("\n🎉 직접 변환 테스트 성공!")
        print("Python 서비스의 변환 로직은 정상 작동합니다.")
    else:
        print("\n❌ 직접 변환 테스트 실패")
        print("변환 로직에 문제가 있습니다.")
    
    sys.exit(0 if success else 1)