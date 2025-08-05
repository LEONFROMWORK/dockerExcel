"""
Name Fix Strategy
#NAME? 오류 수정 전략 구현
"""

from typing import Optional, Dict, Any
from app.core.interfaces import IErrorFixStrategy, ExcelError, FixResult
import re
import logging

logger = logging.getLogger(__name__)


class NameFixStrategy(IErrorFixStrategy):
    """#NAME? 오류 수정 전략"""

    def __init__(self):
        # Excel 내장 함수 목록 (일부)
        self.excel_functions = {
            "SUM",
            "AVERAGE",
            "COUNT",
            "MAX",
            "MIN",
            "IF",
            "VLOOKUP",
            "HLOOKUP",
            "INDEX",
            "MATCH",
            "SUMIF",
            "COUNTIF",
            "SUMIFS",
            "COUNTIFS",
            "CONCATENATE",
            "LEFT",
            "RIGHT",
            "MID",
            "LEN",
            "TRIM",
            "UPPER",
            "LOWER",
            "PROPER",
            "DATE",
            "YEAR",
            "MONTH",
            "DAY",
            "TODAY",
            "NOW",
            "WEEKDAY",
            "ROUND",
            "ROUNDUP",
            "ROUNDDOWN",
            "ABS",
            "SQRT",
            "POWER",
            "AND",
            "OR",
            "NOT",
            "IFERROR",
            "IFNA",
            "ISBLANK",
            "ISERROR",
        }

        # 일반적인 오타 매핑
        self.common_typos = {
            "VLOKUP": "VLOOKUP",
            "HLOKUP": "HLOOKUP",
            "SUMM": "SUM",
            "AVERGAE": "AVERAGE",
            "COUNTIFF": "COUNTIF",
            "CONCATENAT": "CONCATENATE",
            "IFERRO": "IFERROR",
            "VLOOKP": "VLOOKUP",
            "CONUT": "COUNT",
            "MACH": "MATCH",
            "INDX": "INDEX",
        }

    def can_handle(self, error: ExcelError) -> bool:
        """이 전략이 처리할 수 있는 오류인지 확인"""
        return error.type.lower() in ["#name?", "name_error", "name?", "#name!"]

    async def apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """#NAME? 오류 수정 적용"""
        try:
            original_formula = error.formula or ""

            # 1. 함수명 오타 확인 및 수정
            fixed_formula = self._fix_function_typos(original_formula)

            # 2. 따옴표 누락 확인
            if fixed_formula == original_formula:
                fixed_formula = self._fix_missing_quotes(original_formula)

            # 3. 잘못된 범위 참조 확인
            if fixed_formula == original_formula:
                fixed_formula = self._fix_range_references(original_formula)

            # 4. 정의된 이름 오류 확인
            if fixed_formula == original_formula:
                fixed_formula = self._fix_defined_names(original_formula, context)

            # 수정이 적용되었는지 확인
            if fixed_formula != original_formula:
                return FixResult(
                    success=True,
                    error_id=error.id,
                    original_formula=original_formula,
                    fixed_formula=fixed_formula,
                    confidence=0.85,
                    applied=False,
                    message="#NAME? 오류를 수정했습니다",
                )
            else:
                # 수정할 수 없는 경우 IFERROR로 처리
                fixed_formula = f"=IFERROR({original_formula.lstrip('=')}, \"#NAME?\")"
                return FixResult(
                    success=True,
                    error_id=error.id,
                    original_formula=original_formula,
                    fixed_formula=fixed_formula,
                    confidence=0.6,
                    applied=False,
                    message="#NAME? 오류를 IFERROR로 처리했습니다",
                )

        except Exception as e:
            logger.error(f"Name fix failed: {str(e)}")
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

        # 명확한 오타가 있는 경우 높은 신뢰도
        for typo in self.common_typos:
            if typo in formula.upper():
                return 0.95

        # 따옴표 문제인 경우
        if self._has_unquoted_text(formula):
            return 0.9

        return 0.7

    def _fix_function_typos(self, formula: str) -> str:
        """함수명 오타 수정"""
        fixed = formula

        # 일반적인 오타 수정
        for typo, correct in self.common_typos.items():
            pattern = rf"\b{typo}\b"
            fixed = re.sub(pattern, correct, fixed, flags=re.IGNORECASE)

        # 함수명 대소문자 수정
        for func in self.excel_functions:
            pattern = rf"\b{func}\b"
            fixed = re.sub(pattern, func, fixed, flags=re.IGNORECASE)

        return fixed

    def _fix_missing_quotes(self, formula: str) -> str:
        """텍스트 리터럴의 따옴표 누락 수정"""
        # 함수 인자 내의 텍스트 찾기
        # 예: VLOOKUP(Apple, A:B, 2, FALSE) -> VLOOKUP("Apple", A:B, 2, FALSE)

        # 간단한 패턴: 함수 내의 텍스트
        pattern = r"(\w+)\s*\(\s*([A-Za-z]+[A-Za-z0-9]*)\s*,"

        def replace_unquoted(match):
            func_name = match.group(1)
            text_value = match.group(2)

            # 셀 참조가 아닌 경우에만 따옴표 추가
            if not self._is_cell_reference(text_value) and text_value.upper() not in [
                "TRUE",
                "FALSE",
            ]:
                return f'{func_name}("{text_value}",'
            return match.group(0)

        return re.sub(pattern, replace_unquoted, formula)

    def _fix_range_references(self, formula: str) -> str:
        """잘못된 범위 참조 수정"""
        # 예: A:1 -> A:A, 1:B -> 1:1

        # 잘못된 열:숫자 패턴
        formula = re.sub(r"\b([A-Z]+):(\d+)\b", r"\1:\1", formula, flags=re.IGNORECASE)

        # 잘못된 숫자:열 패턴
        formula = re.sub(r"\b(\d+):([A-Z]+)\b", r"\1:\1", formula, flags=re.IGNORECASE)

        return formula

    def _fix_defined_names(
        self, formula: str, context: Optional[Dict[str, Any]]
    ) -> str:
        """정의된 이름 오류 수정"""
        # context에 정의된 이름 목록이 있다면 사용
        if context and "defined_names" in context:
            defined_names = context["defined_names"]

            # 대소문자 구분 없이 매칭
            words = re.findall(r"\b\w+\b", formula)
            for word in words:
                for defined_name in defined_names:
                    if word.upper() == defined_name.upper() and word != defined_name:
                        formula = formula.replace(word, defined_name)

        return formula

    def _has_unquoted_text(self, formula: str) -> bool:
        """따옴표가 없는 텍스트가 있는지 확인"""
        # 함수 인자 추출
        args_pattern = r"\(([^)]+)\)"
        matches = re.findall(args_pattern, formula)

        for args in matches:
            # 쉼표로 분리
            parts = args.split(",")
            for part in parts:
                part = part.strip()
                # 텍스트처럼 보이지만 따옴표가 없는 경우
                if (
                    part
                    and part[0] not in ['"', "'"]
                    and not self._is_cell_reference(part)
                    and not part.replace(".", "").replace("-", "").isdigit()
                    and part.upper() not in ["TRUE", "FALSE"]
                ):
                    return True

        return False

    def _is_cell_reference(self, text: str) -> bool:
        """셀 참조인지 확인"""
        # 간단한 셀 참조 패턴
        cell_pattern = r"^[A-Z]+\d+$"
        range_pattern = r"^[A-Z]+\d+:[A-Z]+\d+$"

        return (
            re.match(cell_pattern, text, re.IGNORECASE) is not None
            or re.match(range_pattern, text, re.IGNORECASE) is not None
        )
