"""
Formula Error Detection Strategy
수식 오류 감지 전략 구현
"""

import re
from typing import List, Optional, Any
from app.core.interfaces import IErrorDetector, ExcelError, ExcelErrorType
import logging

logger = logging.getLogger(__name__)


class FormulaErrorDetector(IErrorDetector):
    """수식 오류 감지 전략"""

    def __init__(self):
        self.error_patterns = {
            ExcelErrorType.DIV_ZERO: re.compile(r"#DIV/0!"),
            ExcelErrorType.NA: re.compile(r"#N/A"),
            ExcelErrorType.NAME: re.compile(r"#NAME\?"),
            ExcelErrorType.NULL: re.compile(r"#NULL!"),
            ExcelErrorType.NUM: re.compile(r"#NUM!"),
            ExcelErrorType.REF: re.compile(r"#REF!"),
            ExcelErrorType.VALUE: re.compile(r"#VALUE!"),
            ExcelErrorType.SPILL: re.compile(r"#SPILL!"),
            ExcelErrorType.CALC: re.compile(r"#CALC!"),
        }

        self.formula_validators = {
            "parentheses": self._check_balanced_parentheses,
            "references": self._check_valid_references,
            "functions": self._check_function_syntax,
        }

    async def detect(self, workbook: Any) -> List[ExcelError]:
        """워크북에서 수식 오류 감지"""
        errors = []
        detected_cells = set()  # Track already detected errors

        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    cell_key = f"{sheet.title}_{cell.coordinate}"

                    # 1. 먼저 실제 셀 값을 확인 (최우선 순위)
                    if cell.value is not None:
                        value_str = str(cell.value).strip()
                        # Excel 오류 값 직접 체크
                        error_mapping = {
                            "#DIV/0!": ExcelErrorType.DIV_ZERO,
                            "#N/A": ExcelErrorType.NA,
                            "#NAME?": ExcelErrorType.NAME,
                            "#NULL!": ExcelErrorType.NULL,
                            "#NUM!": ExcelErrorType.NUM,
                            "#REF!": ExcelErrorType.REF,
                            "#VALUE!": ExcelErrorType.VALUE,
                            "#SPILL!": ExcelErrorType.SPILL,
                            "#CALC!": ExcelErrorType.CALC,
                        }

                        if value_str in error_mapping:
                            error = self._create_error_from_value(cell, sheet.title)
                            if error:
                                errors.append(error)
                                detected_cells.add(cell_key)
                                # Skip formula check if value error is found
                                continue

                    # 2. 수식이 있고 아직 오류로 감지되지 않은 경우에만 추가 검사
                    if (
                        hasattr(cell, "data_type")
                        and cell.data_type == "f"
                        and cell_key not in detected_cells
                    ):
                        cell_errors = await self.check_cell_formula(cell, sheet.title)
                        errors.extend(cell_errors)

        return errors

    def can_detect(self, error_type: str) -> bool:
        """수식 관련 오류만 감지 가능"""
        return error_type in [e.value for e in ExcelErrorType]

    async def check_cell_formula(self, cell, sheet_name: str) -> List[ExcelError]:
        """셀의 수식 검사"""
        errors = []

        # 1. 수식 구문 검사
        syntax_error = self._check_formula_syntax(cell)
        if syntax_error:
            errors.append(
                self._create_error(
                    cell,
                    sheet_name,
                    ExcelErrorType.BROKEN_FORMULA,
                    f"수식 구문 오류: {syntax_error}",
                )
            )

        # 2. 순환 참조 검사
        if self._has_circular_reference(cell):
            errors.append(
                self._create_error(
                    cell,
                    sheet_name,
                    ExcelErrorType.CIRCULAR_REF,
                    "순환 참조가 감지되었습니다",
                )
            )

        # 3. 참조 유효성 검사
        invalid_refs = self._check_references(cell)
        for ref in invalid_refs:
            errors.append(
                self._create_error(
                    cell, sheet_name, ExcelErrorType.REF, f"잘못된 참조: {ref}"
                )
            )

        return errors

    def _check_formula_syntax(self, cell) -> Optional[str]:
        """수식 구문 검사"""
        formula = cell.value
        if not formula or not isinstance(formula, str):
            return None

        # 균형 잡힌 괄호 검사
        if not self._check_balanced_parentheses(formula):
            return "괄호가 일치하지 않습니다"

        # 함수 구문 검사
        function_error = self._check_function_syntax(formula)
        if function_error:
            return function_error

        return None

    def _check_balanced_parentheses(self, formula: str) -> bool:
        """괄호 균형 검사"""
        stack = []
        pairs = {"(": ")", "[": "]", "{": "}"}

        for char in formula:
            if char in pairs:
                stack.append(char)
            elif char in pairs.values():
                if not stack:
                    return False
                if pairs[stack.pop()] != char:
                    return False

        return len(stack) == 0

    def _check_valid_references(self, formula: str) -> bool:
        """참조 유효성 검사"""
        # A1 스타일 참조 패턴
        ref_pattern = r"[A-Z]+\d+"
        refs = re.findall(ref_pattern, formula)

        for ref in refs:
            # 열이 XFD를 초과하거나 행이 1048576을 초과하는지 검사
            col_match = re.match(r"^([A-Z]+)", ref)
            row_match = re.search(r"(\d+)$", ref)

            if col_match and row_match:
                col = col_match.group(1)
                row = int(row_match.group(1))

                # Excel 한계 검사
                if self._column_to_number(col) > 16384 or row > 1048576:
                    return False

        return True

    def _check_function_syntax(self, formula: str) -> Optional[str]:
        """함수 구문 검사"""
        # 기본 함수 패턴
        func_pattern = r"([A-Z]+)\s*\("
        functions = re.findall(func_pattern, formula)

        # 알려진 Excel 함수 목록 (일부)
        known_functions = {
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
            "CONCATENATE",
            "LEFT",
            "RIGHT",
            "MID",
            "LEN",
            "TRIM",
            "UPPER",
            "LOWER",
        }

        for func in functions:
            if func.upper() not in known_functions:
                # 사용자 정의 함수가 아닌 경우 오류
                return f"알 수 없는 함수: {func}"

        return None

    def _has_circular_reference(self, cell) -> bool:
        """순환 참조 검사 (간단한 버전)"""
        # 실제 구현에서는 더 복잡한 그래프 기반 검사 필요
        if hasattr(cell, "_circular_reference"):
            return cell._circular_reference
        return False

    def _check_references(self, cell) -> List[str]:
        """참조 검사"""
        invalid_refs = []
        formula = str(cell.value)

        # 시트 참조 패턴
        sheet_ref_pattern = r"'([^']+)'![A-Z]+\d+"
        re.findall(sheet_ref_pattern, formula)

        # 여기서는 간단한 검사만 수행
        # 실제로는 워크북의 시트 목록과 비교 필요

        return invalid_refs

    def _create_error_from_value(self, cell, sheet_name: str) -> Optional[ExcelError]:
        """셀 값에서 오류 객체 생성"""
        value = str(cell.value).strip()

        # 직접 매핑으로 더 정확한 오류 타입 감지
        error_mapping = {
            "#DIV/0!": ExcelErrorType.DIV_ZERO,
            "#N/A": ExcelErrorType.NA,
            "#NAME?": ExcelErrorType.NAME,
            "#NULL!": ExcelErrorType.NULL,
            "#NUM!": ExcelErrorType.NUM,
            "#REF!": ExcelErrorType.REF,
            "#VALUE!": ExcelErrorType.VALUE,
            "#SPILL!": ExcelErrorType.SPILL,
            "#CALC!": ExcelErrorType.CALC,
        }

        # 정확한 매칭 시도
        if value in error_mapping:
            error_type = error_mapping[value]
            return self._create_error(
                cell, sheet_name, error_type, self._get_error_message(error_type)
            )

        # 패턴 매칭 (fallback)
        for error_type, pattern in self.error_patterns.items():
            if pattern.match(value):
                return self._create_error(
                    cell, sheet_name, error_type, self._get_error_message(error_type)
                )

        return None

    def _create_error(
        self, cell, sheet_name: str, error_type: ExcelErrorType, message: str
    ) -> ExcelError:
        """오류 객체 생성"""
        return ExcelError(
            id=f"{sheet_name}_{cell.coordinate}_{error_type.value}",
            type=error_type.value,
            category="critical_error",  # 수식 오류는 모두 명백한 오류
            sheet=sheet_name,
            cell=cell.coordinate,
            formula=str(cell.value) if cell.data_type == "f" else None,
            value=cell.value,
            message=message,
            severity=self._get_error_severity(error_type),
            is_auto_fixable=self._is_auto_fixable(error_type),
            suggested_fix=self._get_suggested_fix(error_type, cell),
            confidence=0.95,
        )

    def _get_error_message(self, error_type: ExcelErrorType) -> str:
        """오류 메시지 생성"""
        messages = {
            ExcelErrorType.DIV_ZERO: "0으로 나누기 오류입니다",
            ExcelErrorType.NA: "값을 찾을 수 없습니다",
            ExcelErrorType.NAME: "이름을 인식할 수 없습니다",
            ExcelErrorType.NULL: "잘못된 교집합입니다",
            ExcelErrorType.NUM: "숫자가 잘못되었습니다",
            ExcelErrorType.REF: "참조가 잘못되었습니다",
            ExcelErrorType.VALUE: "값 형식이 잘못되었습니다",
            ExcelErrorType.SPILL: "스필 범위가 차단되었습니다",
            ExcelErrorType.CALC: "계산할 수 없습니다",
            ExcelErrorType.CIRCULAR_REF: "순환 참조가 있습니다",
        }
        return messages.get(error_type, "알 수 없는 오류입니다")

    def _get_error_severity(self, error_type: ExcelErrorType) -> str:
        """오류 심각도 결정"""
        critical = [ExcelErrorType.CIRCULAR_REF, ExcelErrorType.REF]
        high = [ExcelErrorType.DIV_ZERO, ExcelErrorType.VALUE, ExcelErrorType.NAME]
        medium = [ExcelErrorType.NA, ExcelErrorType.NUM]

        if error_type in critical:
            return "critical"
        elif error_type in high:
            return "high"
        elif error_type in medium:
            return "medium"
        else:
            return "low"

    def _is_auto_fixable(self, error_type: ExcelErrorType) -> bool:
        """자동 수정 가능 여부"""
        auto_fixable = [
            ExcelErrorType.DIV_ZERO,
            ExcelErrorType.NA,
            ExcelErrorType.VALUE,
        ]
        return error_type in auto_fixable

    def _get_suggested_fix(self, error_type: ExcelErrorType, cell) -> Optional[str]:
        """제안된 수정 방법"""
        if error_type == ExcelErrorType.DIV_ZERO:
            return f"IFERROR({cell.value}, 0)"
        elif error_type == ExcelErrorType.NA:
            return f'IFERROR({cell.value}, "")'
        elif error_type == ExcelErrorType.VALUE:
            return f"IFERROR({cell.value}, 0)"
        return None

    def _column_to_number(self, column: str) -> int:
        """열 문자를 숫자로 변환"""
        result = 0
        for char in column:
            result = result * 26 + (ord(char) - ord("A") + 1)
        return result
