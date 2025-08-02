"""
formulas 라이브러리 테스트 및 검증
Excel 수식을 실시간으로 계산하고 검증하는 도구
"""

# formulas 라이브러리 설치 필요:
# pip install formulas

import formulas

def test_formulas_library():
    """formulas 라이브러리 기능 테스트"""
    
    print("=== Formulas Library 테스트 ===")
    
    # 1. 기본 수식 계산
    print("\n1. 기본 수식 계산:")
    try:
        # 간단한 수식
        result1 = formulas.Parser().ast('=1+1')[1].compile()()
        print(f"=1+1 = {result1}")
        
        # 셀 참조가 있는 수식 (컨텍스트 필요)
        xl_model = formulas.ExcelModel()
        xl_model.loads({
            'Sheet1': {
                'A1': 10,
                'B1': 20,
                'C1': '=A1+B1'
            }
        })
        xl_model.calculate()
        result2 = xl_model['Sheet1'].cells['C1'].value
        print(f"=A1+B1 with A1=10, B1=20 = {result2}")
        
    except Exception as e:
        print(f"기본 계산 테스트 실패: {e}")
    
    # 2. Excel 함수 테스트
    print("\n2. Excel 함수 테스트:")
    try:
        xl_model = formulas.ExcelModel()
        xl_model.loads({
            'Sheet1': {
                'A1': 5,
                'A2': 10,
                'A3': 15,
                'B1': '=SUM(A1:A3)',
                'B2': '=AVERAGE(A1:A3)', 
                'B3': '=IF(A1>0, "Positive", "Not Positive")',
                'B4': '=VLOOKUP(10, A1:A3, 1, FALSE)'
            }
        })
        xl_model.calculate()
        
        print(f"SUM(A1:A3) = {xl_model['Sheet1'].cells['B1'].value}")
        print(f"AVERAGE(A1:A3) = {xl_model['Sheet1'].cells['B2'].value}")
        print(f"IF(A1>0, ...) = {xl_model['Sheet1'].cells['B3'].value}")
        
    except Exception as e:
        print(f"Excel 함수 테스트 실패: {e}")
    
    # 3. 오류 시뮬레이션
    print("\n3. 오류 시뮬레이션:")
    try:
        xl_model = formulas.ExcelModel()
        xl_model.loads({
            'Sheet1': {
                'A1': 10,
                'B1': 0,
                'C1': '=A1/B1',  # Division by zero
                'D1': '=A1+#REF!',  # Reference error
            }
        })
        xl_model.calculate()
        
        c1_value = xl_model['Sheet1'].cells['C1'].value
        d1_value = xl_model['Sheet1'].cells['D1'].value
        
        print(f"=A1/B1 (10/0) = {c1_value}")
        print(f"=A1+#REF! = {d1_value}")
        
    except Exception as e:
        print(f"오류 시뮬레이션 테스트 실패: {e}")
    
    # 4. 순환 참조 검사
    print("\n4. 순환 참조 검사:")
    try:
        xl_model = formulas.ExcelModel()
        xl_model.loads({
            'Sheet1': {
                'A1': '=B1+1',
                'B1': '=A1+1'  # Circular reference
            }
        })
        xl_model.calculate()
        
    except Exception as e:
        print(f"순환 참조 감지됨: {e}")
    
    print("\n=== 테스트 완료 ===")

def create_excel_formula_validator():
    """실시간 Excel 수식 검증기 생성"""
    
    class ExcelFormulaValidator:
        def __init__(self):
            self.xl_model = formulas.ExcelModel()
            self.context = {}
        
        def set_context(self, sheet_name, cell_data):
            """컨텍스트 설정 (현재 시트의 셀 값들)"""
            if sheet_name not in self.context:
                self.context[sheet_name] = {}
            self.context[sheet_name].update(cell_data)
            self.xl_model.loads({sheet_name: cell_data})
        
        def validate_formula(self, formula, cell_address, sheet_name='Sheet1'):
            """수식 검증 및 계산"""
            try:
                # 임시로 수식을 컨텍스트에 추가
                temp_context = self.context.get(sheet_name, {}).copy()
                temp_context[cell_address] = formula
                
                # 새 모델로 테스트
                test_model = formulas.ExcelModel()
                test_model.loads({sheet_name: temp_context})
                test_model.calculate()
                
                # 결과 추출
                cell_value = test_model[sheet_name].cells[cell_address].value
                
                return {
                    'valid': True,
                    'result': cell_value,
                    'error': None,
                    'type': type(cell_value).__name__
                }
                
            except Exception as e:
                error_type = 'unknown'
                if 'circular' in str(e).lower():
                    error_type = 'circular_reference'
                elif 'ref' in str(e).lower():
                    error_type = 'reference_error'
                elif 'div' in str(e).lower():
                    error_type = 'division_by_zero'
                
                return {
                    'valid': False,
                    'result': None,
                    'error': str(e),
                    'error_type': error_type
                }
        
        def get_dependencies(self, formula):
            """수식의 의존성 분석"""
            try:
                ast = formulas.Parser().ast(formula)
                # 의존성 추출 로직
                return {'dependencies': []}  # 구현 필요
            except Exception as e:
                return {'error': str(e)}
    
    return ExcelFormulaValidator()

if __name__ == "__main__":
    # 라이브러리 테스트
    test_formulas_library()
    
    # 검증기 테스트
    print("\n" + "="*50)
    print("Excel Formula Validator 테스트")
    
    validator = create_excel_formula_validator()
    
    # 컨텍스트 설정
    validator.set_context('Sheet1', {
        'A1': 10,
        'A2': 20,
        'B1': 5,
        'B2': 0
    })
    
    # 수식 검증 테스트
    test_formulas = [
        '=A1+A2',
        '=SUM(A1:A2)',
        '=A1/B2',  # Division by zero
        '=VLOOKUP(10, A1:A2, 1, FALSE)',
        '=IF(A1>A2, "A1 is bigger", "A2 is bigger")'
    ]
    
    for formula in test_formulas:
        result = validator.validate_formula(formula, 'C1')
        print(f"Formula: {formula}")
        print(f"Result: {result}")
        print("-" * 30)