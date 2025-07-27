"""
Smart Formula Fixer Service
AI 기반 수식 자동 수정 시스템
"""

import openpyxl
from openpyxl.utils import get_column_letter, column_index_from_string
import re
from datetime import datetime
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from .openai_service import OpenAIService
from .excel_error_detector import ExcelError

@dataclass
class FormulaFixResult:
    """수식 수정 결과를 담는 데이터 클래스"""
    original_formula: str
    fixed_formula: str
    fix_type: str
    confidence: float
    explanation: str
    test_passed: bool

class SmartFormulaFixer:
    """AI 기반 지능형 수식 수정 클래스"""

    def __init__(self):
        self.openai_service = OpenAIService()
        self.logger = logging.getLogger(__name__)

        # 일반적인 수식 수정 패턴
        self.fix_patterns = {
            '#DIV/0!': self._fix_division_by_zero,
            '#N/A': self._fix_na_error,
            '#NAME?': self._fix_name_error,
            '#REF!': self._fix_ref_error,
            '#VALUE!': self._fix_value_error,
            '#NUM!': self._fix_num_error,
            '#NULL!': self._fix_null_error
        }

        # 수식 최적화 패턴
        self.optimization_patterns = {
            'vlookup_to_xlookup': self._optimize_vlookup,
            'nested_if': self._optimize_nested_if,
            'inefficient_range': self._optimize_range_reference,
            'array_formula': self._optimize_array_formula
        }

    async def fix_formula_errors(self, workbook, errors: List[ExcelError]) -> Dict[str, Any]:
        """수식 오류들을 일괄 수정"""

        fix_results = {
            'fixed_formulas': [],
            'failed_fixes': [],
            'optimization_suggestions': [],
            'summary': {
                'total_processed': 0,
                'successfully_fixed': 0,
                'failed_fixes': 0,
                'optimizations_applied': 0
            }
        }

        formula_errors = [e for e in errors if e.error_type in ['formula_error', 'inefficient_formula']]

        for error in formula_errors:
            try:
                sheet_name, cell_ref = error.location.split('!')
                sheet = workbook[sheet_name]
                cell = sheet[cell_ref]

                if error.error_type == 'formula_error':
                    fix_result = await self._fix_single_formula_error(cell, error)
                elif error.error_type == 'inefficient_formula':
                    fix_result = await self._optimize_single_formula(cell, error)

                if fix_result and fix_result.test_passed:
                    # 수정된 수식 적용
                    cell.value = fix_result.fixed_formula
                    fix_results['fixed_formulas'].append({
                        'location': error.location,
                        'original': fix_result.original_formula,
                        'fixed': fix_result.fixed_formula,
                        'fix_type': fix_result.fix_type,
                        'confidence': fix_result.confidence,
                        'explanation': fix_result.explanation
                    })
                    fix_results['summary']['successfully_fixed'] += 1
                else:
                    fix_results['failed_fixes'].append({
                        'location': error.location,
                        'error': error.description,
                        'reason': '자동 수정 실패 - 수동 검토 필요'
                    })
                    fix_results['summary']['failed_fixes'] += 1

                fix_results['summary']['total_processed'] += 1

            except Exception as e:
                self.logger.error(f"수식 수정 중 오류: {str(e)}")
                fix_results['failed_fixes'].append({
                    'location': error.location,
                    'error': str(e),
                    'reason': '수정 처리 중 예외 발생'
                })

        return fix_results

    async def _fix_single_formula_error(self, cell, error: ExcelError) -> Optional[FormulaFixResult]:
        """단일 수식 오류 수정"""

        original_formula = str(cell.value)
        error_type = self._extract_error_type(original_formula)

        if error_type in self.fix_patterns:
            # 패턴 기반 수정 시도
            pattern_fix = self.fix_patterns[error_type](original_formula, cell)
            if pattern_fix:
                return pattern_fix

        # AI 기반 수정 시도
        ai_fix = await self._ai_fix_formula(original_formula, cell, error)
        return ai_fix

    async def _optimize_single_formula(self, cell, error: ExcelError) -> Optional[FormulaFixResult]:
        """단일 수식 최적화"""

        original_formula = str(cell.value)

        # 최적화 패턴 적용
        for pattern_name, optimizer in self.optimization_patterns.items():
            if self._formula_matches_pattern(original_formula, pattern_name):
                optimization = optimizer(original_formula, cell)
                if optimization:
                    return optimization

        # AI 기반 최적화
        ai_optimization = await self._ai_optimize_formula(original_formula, cell)
        return ai_optimization

    def _fix_division_by_zero(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """0으로 나누기 오류 수정"""

        # 기본 패턴: =A1/B1 -> =IFERROR(A1/B1, 0) 또는 =IF(B1=0, 0, A1/B1)

        # 간단한 나눗셈 패턴 찾기
        division_pattern = r'([A-Z]+\d+)/([A-Z]+\d+)'
        match = re.search(division_pattern, formula)

        if match:
            numerator = match.group(1)
            denominator = match.group(2)

            # IFERROR를 사용한 수정
            fixed_formula = f'=IFERROR({numerator}/{denominator}, 0)'

            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=fixed_formula,
                fix_type='division_by_zero_protection',
                confidence=0.9,
                explanation=f'{denominator}가 0일 때 0을 반환하도록 IFERROR 함수 적용',
                test_passed=True
            )

        return None

    def _fix_na_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#N/A 오류 수정 (주로 VLOOKUP, MATCH 함수)"""

        # VLOOKUP 패턴 수정
        vlookup_pattern = r'VLOOKUP\s*\((.*?)\)'
        match = re.search(vlookup_pattern, formula, re.IGNORECASE)

        if match:
            vlookup_args = match.group(1)
            fixed_formula = formula.replace(match.group(0), f'IFERROR(VLOOKUP({vlookup_args}), "Not Found")')

            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=fixed_formula,
                fix_type='vlookup_na_protection',
                confidence=0.85,
                explanation='VLOOKUP에서 값을 찾지 못할 때 "Not Found"를 반환하도록 수정',
                test_passed=True
            )

        # MATCH 패턴 수정
        match_pattern = r'MATCH\s*\((.*?)\)'
        match = re.search(match_pattern, formula, re.IGNORECASE)

        if match:
            match_args = match.group(1)
            fixed_formula = formula.replace(match.group(0), f'IFERROR(MATCH({match_args}), 0)')

            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=fixed_formula,
                fix_type='match_na_protection',
                confidence=0.8,
                explanation='MATCH에서 값을 찾지 못할 때 0을 반환하도록 수정',
                test_passed=True
            )

        return None

    def _fix_name_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#NAME? 오류 수정 (함수명 오타 등)"""

        # 일반적인 함수명 오타 수정
        common_typos = {
            'SUM': ['SUN', 'SUME', 'SUMM'],
            'VLOOKUP': ['VLOOK', 'VLOOKPU', 'VLOOKUP'],
            'IF': ['IFF', 'FI'],
            'COUNT': ['CONT', 'CONUT'],
            'AVERAGE': ['AVG', 'AVERAG', 'AVERGAE'],
            'MAX': ['MAZ', 'MX'],
            'MIN': ['MN', 'MIN'],
            'TODAY': ['TOAY', 'TODA'],
            'NOW': ['NW', 'NOV']
        }

        for correct_func, typos in common_typos.items():
            for typo in typos:
                if typo in formula.upper():
                    fixed_formula = formula.upper().replace(typo, correct_func)

                    return FormulaFixResult(
                        original_formula=formula,
                        fixed_formula=fixed_formula,
                        fix_type='function_name_correction',
                        confidence=0.95,
                        explanation=f'함수명 오타 수정: {typo} -> {correct_func}',
                        test_passed=True
                    )

        return None

    def _fix_ref_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#REF! 오류 수정 (참조 오류)"""

        # #REF! 참조를 상대적으로 안전한 참조로 변경
        if '#REF!' in formula:
            # 현재 셀을 기준으로 상대 참조 제안
            current_row = cell.row
            current_col = cell.column

            # 간단한 경우: 단일 #REF! 참조
            if formula.count('#REF!') == 1:
                # 인근 셀을 참조하도록 제안
                suggested_ref = f"{get_column_letter(current_col)}{current_row - 1}"
                fixed_formula = formula.replace('#REF!', suggested_ref)

                return FormulaFixResult(
                    original_formula=formula,
                    fixed_formula=fixed_formula,
                    fix_type='broken_reference_fix',
                    confidence=0.3,  # 낮은 신뢰도 - 수동 검토 필요
                    explanation=f'깨진 참조를 {suggested_ref}로 임시 수정 (검토 필요)',
                    test_passed=False  # 검증 필요
                )

        return None

    def _fix_value_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#VALUE! 오류 수정"""

        # 텍스트와 숫자 혼용 문제 해결
        # VALUE 함수로 텍스트를 숫자로 변환

        # 간단한 산술 연산에서 VALUE 오류가 있는 경우
        arithmetic_pattern = r'([A-Z]+\d+)\s*[\+\-\*/]\s*([A-Z]+\d+)'
        match = re.search(arithmetic_pattern, formula)

        if match:
            ref1 = match.group(1)
            ref2 = match.group(2)
            operator = re.search(r'[\+\-\*/]', formula).group(0)

            fixed_formula = f'=VALUE({ref1}){operator}VALUE({ref2})'

            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=fixed_formula,
                fix_type='value_conversion',
                confidence=0.7,
                explanation='텍스트로 저장된 숫자를 VALUE 함수로 변환',
                test_passed=True
            )

        return None

    def _fix_num_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#NUM! 오류 수정"""

        # 제곱근의 음수 처리
        if 'SQRT' in formula.upper():
            sqrt_pattern = r'SQRT\s*\((.*?)\)'
            match = re.search(sqrt_pattern, formula, re.IGNORECASE)

            if match:
                sqrt_arg = match.group(1)
                fixed_formula = formula.replace(match.group(0), f'IF({sqrt_arg}>=0, SQRT({sqrt_arg}), "")')

                return FormulaFixResult(
                    original_formula=formula,
                    fixed_formula=fixed_formula,
                    fix_type='sqrt_negative_protection',
                    confidence=0.9,
                    explanation='음수의 제곱근을 방지하도록 IF 조건 추가',
                    test_passed=True
                )

        return None

    def _fix_null_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#NULL! 오류 수정"""

        # 범위 연산자 오류 수정 (공백 대신 콜론 사용)
        # 예: A1 A5 -> A1:A5
        range_error_pattern = r'([A-Z]+\d+)\s+([A-Z]+\d+)'
        match = re.search(range_error_pattern, formula)

        if match:
            start_ref = match.group(1)
            end_ref = match.group(2)
            fixed_formula = formula.replace(f'{start_ref} {end_ref}', f'{start_ref}:{end_ref}')

            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=fixed_formula,
                fix_type='range_operator_fix',
                confidence=0.95,
                explanation=f'범위 연산자 수정: {start_ref} {end_ref} -> {start_ref}:{end_ref}',
                test_passed=True
            )

        return None

    def _fix_spill_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#SPILL! 오류 수정 (동적 배열 충돌)"""

        # 동적 배열 수식을 단일 셀 수식으로 변환
        # 예: =SORT(A:A) -> =INDEX(SORT(A:A), ROW())
        
        if 'SORT' in formula.upper() or 'FILTER' in formula.upper() or 'UNIQUE' in formula.upper():
            # 동적 배열 함수를 INDEX로 감싸서 단일 값 반환
            fixed_formula = f'=INDEX({formula[1:]}, 1)'  # 첫 번째 결과만 반환
            
            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=fixed_formula,
                fix_type='spill_error_fix',
                confidence=0.7,
                explanation='동적 배열 결과를 단일 셀로 제한',
                test_passed=True
            )
        
        return None
    
    def _fix_calc_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#CALC! 오류 수정 (계산 엔진 오류)"""
        
        # 배열 수식에서 자주 발생하므로 배열 수식 단순화
        if formula.startswith('{=') and formula.endswith('}'):
            # 레거시 배열 수식을 동적 배열로 변환
            inner_formula = formula[2:-1]
            fixed_formula = f'={inner_formula}'
            
            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=fixed_formula,
                fix_type='calc_error_array_fix',
                confidence=0.8,
                explanation='레거시 배열 수식을 동적 배열로 변환',
                test_passed=True
            )
        
        # 복잡한 수식을 단계별로 분리하는 것을 제안
        return FormulaFixResult(
            original_formula=formula,
            fixed_formula=formula,  # 수식은 그대로 유지
            fix_type='calc_error_suggestion',
            confidence=0.3,
            explanation='복잡한 수식을 여러 셀로 나누어 단계별로 계산하는 것을 권장',
            test_passed=False
        )
    
    def _fix_getting_data_error(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """#GETTING_DATA 오류 수정 (외부 데이터 대기)"""
        
        # 외부 데이터 연결 수식에 IFERROR 적용
        if any(func in formula.upper() for func in ['WEBSERVICE', 'FILTERXML', 'RTD']):
            fixed_formula = f'=IFERROR({formula[1:]}, "데이터 로딩 중...")'
            
            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=fixed_formula,
                fix_type='getting_data_protection',
                confidence=0.8,
                explanation='외부 데이터 로딩 실패 시 기본값 표시',
                test_passed=True
            )
        
        return None

    def _optimize_vlookup(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """VLOOKUP을 XLOOKUP으로 최적화"""

        vlookup_pattern = r'VLOOKUP\s*\((.*?)\)'
        match = re.search(vlookup_pattern, formula, re.IGNORECASE)

        if match:
            args = match.group(1).split(',')
            if len(args) >= 3:
                lookup_value = args[0].strip()
                table_array = args[1].strip()
                col_index = args[2].strip()
                range_lookup = args[3].strip() if len(args) > 3 else 'FALSE'

                # XLOOKUP으로 변환 (Excel 365 이상에서 사용 가능)
                # XLOOKUP(lookup_value, lookup_array, return_array, [if_not_found])
                fixed_formula = f'XLOOKUP({lookup_value}, INDEX({table_array}, 0, 1), INDEX({table_array}, 0, {col_index}), "Not Found")'

                return FormulaFixResult(
                    original_formula=formula,
                    fixed_formula=fixed_formula,
                    fix_type='vlookup_to_xlookup_optimization',
                    confidence=0.8,
                    explanation='VLOOKUP을 더 효율적인 XLOOKUP으로 변환 (Excel 365 필요)',
                    test_passed=True
                )

        return None

    def _optimize_nested_if(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """중첩된 IF를 SWITCH로 최적화"""

        if_count = formula.upper().count('IF(')

        if if_count > 3:
            # 간단한 값 비교 패턴인지 확인
            # 예: IF(A1=1,"One",IF(A1=2,"Two",IF(A1=3,"Three","Other")))

            # 복잡한 패턴 분석은 AI에게 위임
            return None  # AI 최적화로 넘김

        return None

    def _optimize_range_reference(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """비효율적인 범위 참조 최적화"""

        # 전체 열 참조 (A:A, 1:1 등) 최적화
        full_column_pattern = r'[A-Z]+:[A-Z]+'
        full_row_pattern = r'\d+:\d+'

        if re.search(full_column_pattern, formula) or re.search(full_row_pattern, formula):
            # 실제 데이터 범위로 제한하는 것을 제안
            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=formula,  # 실제 변경은 추가 정보 필요
                fix_type='range_optimization_suggestion',
                confidence=0.6,
                explanation='전체 열/행 참조를 실제 데이터 범위로 제한하는 것을 권장합니다',
                test_passed=False  # 수동 검토 필요
            )

        return None

    def _optimize_array_formula(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """배열 수식 최적화"""

        # 레거시 배열 수식을 동적 배열로 변환
        if formula.startswith('{=') and formula.endswith('}'):
            # 중괄호 제거하고 동적 배열 함수 적용
            array_formula = formula[2:-1]  # {= 와 } 제거

            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=f'={array_formula}',
                fix_type='legacy_array_to_dynamic',
                confidence=0.8,
                explanation='레거시 배열 수식을 동적 배열 수식으로 변환',
                test_passed=True
            )

        return None

    async def _ai_fix_formula(self, formula: str, cell, error: ExcelError) -> Optional[FormulaFixResult]:
        """AI를 활용한 수식 수정"""

        try:
            prompt = f"""
            Excel 수식에 오류가 있습니다. 다음 정보를 바탕으로 수식을 수정해주세요:

            오류가 있는 수식: {formula}
            오류 타입: {error.error_type}
            오류 설명: {error.description}
            셀 위치: {error.location}

            다음 JSON 형태로 응답해주세요:
            {{
                "fixed_formula": "수정된 수식",
                "explanation": "수정 이유와 방법 설명",
                "confidence": 0.8,
                "changes_made": ["변경사항 목록"]
            }}

            수정 시 고려사항:
            1. 원래 수식의 의도를 유지
            2. 오류 상황을 적절히 처리 (IFERROR, IF 등 사용)
            3. 가능한 한 간단하고 효율적인 수식 작성
            4. Excel 함수 문법 준수
            """

            response = await self.openai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            import json
            ai_result = json.loads(response)

            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=ai_result['fixed_formula'],
                fix_type='ai_formula_fix',
                confidence=ai_result.get('confidence', 0.5),
                explanation=ai_result['explanation'],
                test_passed=self._validate_formula_syntax(ai_result['fixed_formula'])
            )

        except Exception as e:
            self.logger.error(f"AI 수식 수정 중 오류: {str(e)}")
            return None

    async def _ai_optimize_formula(self, formula: str, cell) -> Optional[FormulaFixResult]:
        """AI를 활용한 수식 최적화"""

        try:
            prompt = f"""
            다음 Excel 수식을 최적화해주세요:

            현재 수식: {formula}
            셀 위치: {cell.coordinate}

            최적화 목표:
            1. 성능 향상 (계산 속도)
            2. 가독성 개선
            3. 유지보수성 향상
            4. 최신 Excel 함수 활용

            다음 JSON 형태로 응답해주세요:
            {{
                "optimized_formula": "최적화된 수식",
                "explanation": "최적화 내용 설명",
                "performance_improvement": "예상 성능 개선 정도",
                "confidence": 0.8,
                "optimization_type": "optimization_category"
            }}
            """

            response = await self.openai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            import json
            ai_result = json.loads(response)

            return FormulaFixResult(
                original_formula=formula,
                fixed_formula=ai_result['optimized_formula'],
                fix_type=f"ai_optimization_{ai_result.get('optimization_type', 'general')}",
                confidence=ai_result.get('confidence', 0.5),
                explanation=ai_result['explanation'],
                test_passed=self._validate_formula_syntax(ai_result['optimized_formula'])
            )

        except Exception as e:
            self.logger.error(f"AI 수식 최적화 중 오류: {str(e)}")
            return None

    def _extract_error_type(self, formula: str) -> Optional[str]:
        """수식에서 오류 타입 추출"""

        for error_type in self.formula_errors:
            if error_type in formula:
                return error_type

        return None

    def _formula_matches_pattern(self, formula: str, pattern_name: str) -> bool:
        """수식이 특정 패턴에 매치되는지 확인"""

        pattern_checks = {
            'vlookup_to_xlookup': lambda f: 'VLOOKUP' in f.upper(),
            'nested_if': lambda f: f.upper().count('IF(') > 3,
            'inefficient_range': lambda f: ':' in f and ('1048576' in f or '16384' in f),
            'array_formula': lambda f: f.startswith('{=') and f.endswith('}')
        }

        return pattern_checks.get(pattern_name, lambda f: False)(formula)

    def _validate_formula_syntax(self, formula: str) -> bool:
        """수식 문법 유효성 간단 검사"""

        if not formula.startswith('='):
            return False

        # 괄호 균형 검사
        open_parens = formula.count('(')
        close_parens = formula.count(')')

        if open_parens != close_parens:
            return False

        # 기본적인 함수명 검사
        invalid_chars = ['#', '<', '>']
        for char in invalid_chars:
            if char in formula:
                return False

        return True
