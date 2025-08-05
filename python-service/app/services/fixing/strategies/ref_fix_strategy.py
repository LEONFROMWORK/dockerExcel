"""
Ref Fix Strategy
#REF! 오류 수정 전략 구현
"""

from typing import Optional, Dict, Any, List, Tuple
from app.core.interfaces import IErrorFixStrategy, ExcelError, FixResult
import re
import logging

logger = logging.getLogger(__name__)


class RefFixStrategy(IErrorFixStrategy):
    """#REF! 오류 수정 전략"""

    def can_handle(self, error: ExcelError) -> bool:
        """이 전략이 처리할 수 있는 오류인지 확인"""
        return error.type.lower() in ["#ref!", "ref_error", "ref!", "#ref"]

    async def apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """#REF! 오류 수정 적용"""
        try:
            original_formula = error.formula or ""

            # 컨텍스트에서 정보 추출
            sheet_info = context.get("sheet_info", {}) if context else {}
            deleted_ranges = context.get("deleted_ranges", []) if context else []
            available_sheets = context.get("available_sheets", []) if context else []

            # 수정 시도
            fixed_formula = original_formula
            fix_method = ""

            # 1. #REF! 참조를 대체 가능한 범위로 변경
            if "#REF!" in fixed_formula:
                fixed_formula, method = self._replace_ref_errors(
                    fixed_formula, sheet_info
                )
                fix_method = method

            # 2. 삭제된 시트 참조 수정
            if fix_method == "" and available_sheets:
                fixed_formula, method = self._fix_sheet_references(
                    fixed_formula, available_sheets
                )
                if method:
                    fix_method = method

            # 3. 범위 참조 수정
            if fix_method == "":
                fixed_formula, method = self._fix_range_references(
                    fixed_formula, deleted_ranges
                )
                if method:
                    fix_method = method

            # 4. 수정이 안된 경우 IFERROR 처리
            if fixed_formula == original_formula or "#REF!" in fixed_formula:
                fixed_formula = f"=IFERROR({original_formula.lstrip('=')}, 0)"
                fix_method = "IFERROR로 감싸서 오류 처리"

            return FixResult(
                success=True,
                error_id=error.id,
                original_formula=original_formula,
                fixed_formula=fixed_formula,
                confidence=0.7 if fix_method != "IFERROR로 감싸서 오류 처리" else 0.5,
                applied=False,
                message=f"#REF! 오류 수정: {fix_method}",
            )

        except Exception as e:
            logger.error(f"Ref fix failed: {str(e)}")
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

        # 단순 #REF! 오류는 낮은 신뢰도
        ref_count = formula.count("#REF!")
        if ref_count == 1:
            return 0.7
        elif ref_count > 1:
            return 0.5

        return 0.6

    def _replace_ref_errors(
        self, formula: str, sheet_info: Dict[str, Any]
    ) -> Tuple[str, str]:
        """#REF! 참조를 대체 가능한 범위로 변경"""
        if not sheet_info:
            # 기본적으로 A1으로 대체
            fixed = formula.replace("#REF!", "A1")
            return fixed, "삭제된 참조를 A1으로 대체"

        # 사용 가능한 범위 정보가 있다면 활용
        max_row = sheet_info.get("max_row", 1000)
        max_col = sheet_info.get("max_col", 26)  # Z열까지

        # #REF!를 포함하는 범위 찾기
        ref_pattern = r"#REF!(?::#REF!)?"

        def replace_ref(match):
            ref_text = match.group(0)
            if ":#" in ref_text:  # 범위 참조
                return f"A1:{self._col_num_to_letter(max_col)}{max_row}"
            else:  # 단일 셀 참조
                return "A1"

        fixed = re.sub(ref_pattern, replace_ref, formula)
        return fixed, "삭제된 참조를 유효한 범위로 대체"

    def _fix_sheet_references(
        self, formula: str, available_sheets: List[str]
    ) -> Tuple[str, str]:
        """삭제된 시트 참조 수정"""
        # 시트 참조 패턴: 'SheetName'!
        sheet_pattern = r"'([^']+)'!|(\w+)!"

        def replace_sheet(match):
            sheet_name = match.group(1) or match.group(2)
            if sheet_name not in available_sheets and "#REF" in sheet_name:
                # 첫 번째 사용 가능한 시트로 대체
                if available_sheets:
                    new_sheet = available_sheets[0]
                    if " " in new_sheet or any(c in new_sheet for c in "!@#$%^&*()"):
                        return f"'{new_sheet}'!"
                    else:
                        return f"{new_sheet}!"
            return match.group(0)

        fixed = re.sub(sheet_pattern, replace_sheet, formula)

        if fixed != formula:
            return fixed, "삭제된 시트 참조를 기존 시트로 대체"

        return formula, ""

    def _fix_range_references(
        self, formula: str, deleted_ranges: List[Dict[str, Any]]
    ) -> Tuple[str, str]:
        """삭제된 범위 참조 수정"""
        # VLOOKUP, INDEX 등의 함수에서 범위 참조 수정

        # VLOOKUP 패턴
        vlookup_pattern = r"VLOOKUP\s*\([^,]+,\s*#REF!(?::#REF!)?\s*,"
        if re.search(vlookup_pattern, formula, re.IGNORECASE):
            # 기본 데이터 범위로 대체
            fixed = re.sub(r"#REF!(?::#REF!)?", "A:Z", formula)
            return fixed, "VLOOKUP 범위를 기본 범위로 대체"

        # INDEX 패턴
        index_pattern = r"INDEX\s*\(\s*#REF!(?::#REF!)?\s*,"
        if re.search(index_pattern, formula, re.IGNORECASE):
            # 기본 데이터 범위로 대체
            fixed = re.sub(r"#REF!(?::#REF!)?", "A:Z", formula)
            return fixed, "INDEX 범위를 기본 범위로 대체"

        # SUMIF/COUNTIF 등의 범위 함수
        range_func_pattern = r"(SUM|COUNT|AVERAGE|MIN|MAX)IF[S]?\s*\(\s*#REF!"
        if re.search(range_func_pattern, formula, re.IGNORECASE):
            fixed = re.sub(r"#REF!(?::#REF!)?", "A:A", formula)
            return fixed, "조건부 함수 범위를 기본 열로 대체"

        return formula, ""

    def _col_num_to_letter(self, col_num: int) -> str:
        """열 번호를 문자로 변환"""
        letter = ""
        while col_num > 0:
            col_num -= 1
            letter = chr(col_num % 26 + ord("A")) + letter
            col_num //= 26
        return letter
