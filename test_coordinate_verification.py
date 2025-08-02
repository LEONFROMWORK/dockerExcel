#!/usr/bin/env python3
"""
셀 일치성 검사 자동화 스크립트

이 스크립트는 Luckysheet 프론트엔드와 Python 백엔드 간의 
셀 좌표 일치성을 자동으로 검증합니다.

사용법:
    python test_coordinate_verification.py

기능:
- 단일 시트 일치성 검사
- 다중 시트 일치성 검사  
- 좌표 변환 검증
- 자동화된 테스트 실행
"""

import requests
import json
import sys
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class TestCase:
    file_id: str
    sheet_name: str
    cell_address: str
    row: int  # 0-based
    col: int  # 0-based
    expected_value: Any
    description: str

class CellConsistencyTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_endpoint = f"{base_url}/api/v1/test/test-cell-consistency"
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []

    def run_test(self, test_case: TestCase) -> Dict[str, Any]:
        """단일 테스트 케이스 실행"""
        
        payload = {
            "file_id": test_case.file_id,
            "sheet_name": test_case.sheet_name,
            "frontend_cell": {
                "address": test_case.cell_address,
                "row": test_case.row,
                "col": test_case.col,
                "value": test_case.expected_value
            }
        }
        
        try:
            response = requests.post(
                self.api_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                test_result = {
                    "description": test_case.description,
                    "file_id": test_case.file_id,
                    "sheet_name": test_case.sheet_name,
                    "cell": test_case.cell_address,
                    "frontend_coordinates": [test_case.row, test_case.col],
                    "backend_coordinates": [result.get("row", 0), result.get("col", 0)],
                    "frontend_value": test_case.expected_value,
                    "backend_value": result.get("value"),
                    "match": result.get("match", False),
                    "differences": result.get("differences", []),
                    "debug_info": result.get("debug_info", {}),
                    "status": "✅ PASSED" if result.get("match", False) else "❌ FAILED"
                }
                
                if result.get("match", False):
                    self.passed_tests += 1
                    print(f"✅ {test_case.description}")
                else:
                    self.failed_tests += 1
                    print(f"❌ {test_case.description}")
                    print(f"   차이점: {result.get('differences', [])}")
                
                self.test_results.append(test_result)
                return test_result
                
            else:
                print(f"❌ HTTP Error {response.status_code}: {test_case.description}")
                return {"error": f"HTTP {response.status_code}", "status": "❌ FAILED"}
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network Error: {test_case.description} - {str(e)}")
            return {"error": str(e), "status": "❌ FAILED"}

    def run_all_tests(self) -> Dict[str, Any]:
        """모든 테스트 케이스 실행"""
        
        print("🔍 셀 일치성 검사 시작...\n")
        
        # 테스트 케이스 정의
        test_cases = [
            # 단일 시트 테스트
            TestCase(
                file_id="converted_table_20250726_215046.xlsx",
                sheet_name="Imported_Table", 
                cell_address="A1",
                row=0, col=0,
                expected_value="구분",
                description="단일시트 A1 셀 테스트"
            ),
            TestCase(
                file_id="converted_table_20250726_215046.xlsx",
                sheet_name="Imported_Table",
                cell_address="C2", 
                row=1, col=2,
                expected_value=66,
                description="단일시트 C2 셀 테스트"
            ),
            
            # 다중 시트 테스트
            TestCase(
                file_id="multi_sheet_test.xlsx",
                sheet_name="Sheet1",
                cell_address="A1",
                row=0, col=0,
                expected_value="첫번째시트",
                description="다중시트 Sheet1/A1 테스트"
            ),
            TestCase(
                file_id="multi_sheet_test.xlsx", 
                sheet_name="Sheet1",
                cell_address="B2",
                row=1, col=1,
                expected_value=100,
                description="다중시트 Sheet1/B2 테스트"
            ),
            TestCase(
                file_id="multi_sheet_test.xlsx",
                sheet_name="Sheet2", 
                cell_address="A1",
                row=0, col=0,
                expected_value="두번째시트",
                description="다중시트 Sheet2/A1 테스트"
            ),
            TestCase(
                file_id="multi_sheet_test.xlsx",
                sheet_name="Sheet2",
                cell_address="B2",
                row=1, col=1, 
                expected_value=200,
                description="다중시트 Sheet2/B2 테스트"
            ),
            TestCase(
                file_id="multi_sheet_test.xlsx",
                sheet_name="테스트시트",
                cell_address="C2",
                row=1, col=2,
                expected_value="테스트값",
                description="한글시트명 테스트시트/C2 테스트"
            )
        ]
        
        # 테스트 실행
        for test_case in test_cases:
            self.run_test(test_case)
        
        # 결과 요약
        total_tests = self.passed_tests + self.failed_tests
        success_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        summary = {
            "total_tests": total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "success_rate": f"{success_rate:.1f}%",
            "overall_status": "✅ ALL_PASSED" if self.failed_tests == 0 else "❌ SOME_FAILED",
            "test_results": self.test_results
        }
        
        print(f"\n📊 테스트 결과 요약:")
        print(f"   총 테스트: {total_tests}")
        print(f"   통과: {self.passed_tests}")
        print(f"   실패: {self.failed_tests}")
        print(f"   성공률: {success_rate:.1f}%")
        print(f"   상태: {summary['overall_status']}")
        
        return summary

    def save_results(self, filename: str = "coordinate_verification_results.json"):
        """테스트 결과를 JSON 파일로 저장"""
        
        summary = {
            "test_date": "2025-01-28",
            "total_tests": self.passed_tests + self.failed_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "success_rate": f"{(self.passed_tests / (self.passed_tests + self.failed_tests) * 100):.1f}%",
            "test_results": self.test_results
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"\n💾 결과가 {filename} 파일에 저장되었습니다.")
        except Exception as e:
            print(f"❌ 파일 저장 실패: {str(e)}")

def main():
    """메인 실행 함수"""
    
    print("🧪 Luckysheet ↔ Python 셀 일치성 검사 도구")
    print("=" * 50)
    
    tester = CellConsistencyTester()
    
    try:
        # 테스트 실행
        results = tester.run_all_tests()
        
        # 결과 저장
        tester.save_results()
        
        # 종료 코드 설정
        exit_code = 0 if tester.failed_tests == 0 else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  테스트가 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()