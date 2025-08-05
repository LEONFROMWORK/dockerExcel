"""
Value Fix Strategy
#VALUE! 오류 수정 전략 구현
"""

from typing import Optional, Dict, Any
from app.core.interfaces import IErrorFixStrategy, ExcelError, FixResult
import re
import logging

logger = logging.getLogger(__name__)


class ValueFixStrategy(IErrorFixStrategy):
    """#VALUE! 오류 수정 전략"""

    def can_handle(self, error: ExcelError) -> bool:
        """이 전략이 처리할 수 있는 오류인지 확인"""
        return error.type.lower() in ["#value!", "value_error", "value!", "#value"]

    async def apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """#VALUE! 오류 수정 적용"""
        try:
            original_formula = error.formula or ""

            # 다양한 수정 방법 시도
            fixed_formula = original_formula
            fix_method = ""

            # 1. 텍스트와 숫자 연산 문제 수정
            if not fix_method:
                fixed_formula, method = self._fix_text_number_operations(
                    original_formula
                )
                if method:
                    fix_method = method

            # 2. 날짜 형식 문제 수정
            if not fix_method:
                fixed_formula, method = self._fix_date_operations(fixed_formula)
                if method:
                    fix_method = method

            # 3. 배열 수식 문제 수정
            if not fix_method:
                fixed_formula, method = self._fix_array_operations(fixed_formula)
                if method:
                    fix_method = method

            # 4. 함수 인자 타입 문제 수정
            if not fix_method:
                fixed_formula, method = self._fix_function_arguments(fixed_formula)
                if method:
                    fix_method = method

            # 5. 빈 셀 참조 문제 수정
            if not fix_method:
                fixed_formula, method = self._fix_empty_cell_references(fixed_formula)
                if method:
                    fix_method = method

            # 6. 수정되지 않은 경우 IFERROR 처리
            if fixed_formula == original_formula:
                fixed_formula = f"=IFERROR({original_formula.lstrip('=')}, 0)"
                fix_method = "IFERROR로 감싸서 오류 처리"

            return FixResult(
                success=True,
                error_id=error.id,
                original_formula=original_formula,
                fixed_formula=fixed_formula,
                confidence=0.8 if fix_method != "IFERROR로 감싸서 오류 처리" else 0.6,
                applied=False,
                message=f"#VALUE! 오류 수정: {fix_method}",
            )

        except Exception as e:
            logger.error(f"Value fix failed: {str(e)}")
            return FixResult(
                success=False,
                error_id=error.id,
                original_formula=error.formula or "",
                fixed_formula="",
                confidence=0.0,
                applied=False,
                message=f"수정 실패: {str(e)}",
            )

    def get_confidence(self, error: ExcelError) -> float:
        """수정 신뢰도 반환"""
        formula = error.formula or ""

        # 명확한 타입 변환이 필요한 경우 높은 신뢰도
        if any(
            func in formula.upper() for func in ["VALUE(", "DATEVALUE(", "TIMEVALUE("]
        ):
            return 0.9

        # 산술 연산이 포함된 경우
        if any(op in formula for op in ["+", "-", "*", "/"]):
            return 0.8

        return 0.7

    def _fix_text_number_operations(self, formula: str) -> tuple[str, str]:
        """텍스트와 숫자 연산 문제 수정"""
        # 패턴: "텍스트" + 숫자 또는 숫자 + "텍스트"

        # 텍스트를 숫자로 변환 필요한 경우
        # 예: ="5" + 10 -> =VALUE("5") + 10
        text_number_pattern = r'"(\d+(?:\.\d+)?)"'

        def replace_text_number(match):
            number_text = match.group(1)
            return f'VALUE("{number_text}")'

        fixed = re.sub(text_number_pattern, replace_text_number, formula)

        if fixed != formula:
            return fixed, "텍스트 숫자를 VALUE 함수로 변환"

        # 연결 연산자 & 사용 제안
        # 예: =A1 + " items" -> =A1 & " items"
        concat_pattern = r'(\w+\d+|\))\s*\+\s*"[^"]+"'
        if re.search(concat_pattern, formula):
            fixed = re.sub(r"\+", "&", formula)
            return fixed, "문자열 연결을 위해 + 를 & 로 변경"

        return formula, ""

    def _fix_date_operations(self, formula: str) -> tuple[str, str]:
        """날짜 형식 문제 수정"""
        # 날짜 문자열을 DATEVALUE로 변환
        # 예: ="2024-01-01" + 1 -> =DATEVALUE("2024-01-01") + 1
        date_pattern = r'"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"'

        def replace_date_text(match):
            date_text = match.group(1)
            return f'DATEVALUE("{date_text}")'

        fixed = re.sub(date_pattern, replace_date_text, formula)

        if fixed != formula:
            return fixed, "날짜 텍스트를 DATEVALUE 함수로 변환"

        return formula, ""

    def _fix_array_operations(self, formula: str) -> tuple[str, str]:
        """배열 수식 문제 수정"""
        # SUMPRODUCT를 사용하여 배열 연산 수정
        # 예: =SUM(A1:A10 * B1:B10) -> =SUMPRODUCT(A1:A10, B1:B10)

        array_sum_pattern = (
            r"SUM\s*\(\s*([A-Z]+\d+:[A-Z]+\d+)\s*\*\s*([A-Z]+\d+:[A-Z]+\d+)\s*\)"
        )

        def replace_array_sum(match):
            range1 = match.group(1)
            range2 = match.group(2)
            return f"SUMPRODUCT({range1}, {range2})"

        fixed = re.sub(
            array_sum_pattern, replace_array_sum, formula, flags=re.IGNORECASE
        )

        if fixed != formula:
            return fixed, "배열 연산을 SUMPRODUCT로 변환"

        return formula, ""

    def _fix_function_arguments(self, formula: str) -> tuple[str, str]:
        """함수 인자 타입 문제 수정"""
        # LEFT, RIGHT, MID 함수의 두 번째 인자가 텍스트인 경우
        text_func_pattern = r'(LEFT|RIGHT|MID)\s*\([^,]+,\s*"(\d+)"\s*(?:,|\))'

        def fix_text_func_args(match):
            func_name = match.group(1)
            num_text = match.group(2)
            if match.group(0).endswith(","):
                return f"{func_name}([^,]+, {num_text},"
            else:
                return f"{func_name}([^,]+, {num_text})"

        # 실제 수정은 더 복잡한 로직 필요
        if re.search(text_func_pattern, formula, re.IGNORECASE):
            # VALUE 함수로 감싸기
            fixed = re.sub(r'"(\d+)"', r'VALUE("\1")', formula)
            return fixed, "함수 인자의 텍스트 숫자를 VALUE로 변환"

        return formula, ""

    def _fix_empty_cell_references(self, formula: str) -> tuple[str, str]:
        """빈 셀 참조 문제 수정"""
        # 빈 셀을 0으로 처리
        # 간단한 수식에 IFERROR 추가

        # 단순 연산 수식인 경우
        if re.match(r"^=[A-Z]+\d+\s*[\+\-\*/]\s*[A-Z]+\d+$", formula, re.IGNORECASE):
            # 각 셀 참조를 IFERROR로 감싸기
            cell_pattern = r"([A-Z]+\d+)"

            def wrap_cell(match):
                cell = match.group(1)
                return f"IFERROR({cell}, 0)"

            fixed = re.sub(cell_pattern, wrap_cell, formula, flags=re.IGNORECASE)
            return fixed, "빈 셀 참조를 IFERROR로 처리"

        return formula, ""
