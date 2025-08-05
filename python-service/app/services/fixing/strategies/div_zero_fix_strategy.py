"""
DIV/0 Error Fix Strategy
#DIV/0! 오류 수정 전략
"""

from typing import Optional, Dict, Any
from app.core.interfaces import IErrorFixStrategy, ExcelError, FixResult, ExcelErrorType
import re
import logging

logger = logging.getLogger(__name__)


class DivZeroFixStrategy(IErrorFixStrategy):
    """#DIV/0! 오류 수정 전략"""

    def __init__(self):
        self.patterns = {
            "simple_division": re.compile(r"=\s*([A-Z]+\d+)\s*/\s*([A-Z]+\d+)"),
            "complex_division": re.compile(r"=(.+)/(.+)"),
            "average_function": re.compile(r"=AVERAGE\((.*?)\)", re.IGNORECASE),
            "nested_division": re.compile(r"([^/]+)/([^/]+)"),
        }

    def can_handle(self, error: ExcelError) -> bool:
        """#DIV/0! 오류만 처리"""
        return error.type == ExcelErrorType.DIV_ZERO.value

    async def apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """오류 수정 적용"""
        if not self.can_handle(error):
            return FixResult(
                success=False,
                error_id=error.id,
                original_formula=error.formula or "",
                fixed_formula="",
                confidence=0.0,
                applied=False,
                message="이 전략은 #DIV/0! 오류만 처리할 수 있습니다",
            )

        # 수식이 없는 경우
        if not error.formula:
            return FixResult(
                success=False,
                error_id=error.id,
                original_formula="",
                fixed_formula="",
                confidence=0.0,
                applied=False,
                message="수식 정보가 없습니다",
            )

        # 수정 방법 결정
        fix_method = self._determine_fix_method(error.formula)
        fixed_formula = self._apply_fix_method(error.formula, fix_method)

        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=error.formula,
            fixed_formula=fixed_formula,
            confidence=self.get_confidence(error),
            applied=False,  # 실제 적용은 별도 단계에서
            message=f"{fix_method} 방법으로 수정되었습니다",
        )

    def get_confidence(self, error: ExcelError) -> float:
        """수정 신뢰도 계산"""
        if not error.formula:
            return 0.0

        # 간단한 나눗셈일수록 높은 신뢰도
        if self.patterns["simple_division"].match(error.formula):
            return 0.95
        elif "AVERAGE" in error.formula.upper():
            return 0.90
        elif self.patterns["complex_division"].match(error.formula):
            return 0.85
        else:
            return 0.70

    def _determine_fix_method(self, formula: str) -> str:
        """수정 방법 결정"""
        formula_upper = formula.upper()

        if "AVERAGE" in formula_upper:
            return "average_fix"
        elif "SUM" in formula_upper and "/" in formula:
            return "sum_division_fix"
        elif self.patterns["simple_division"].match(formula):
            return "simple_iferror"
        else:
            return "complex_iferror"

    def _apply_fix_method(self, formula: str, method: str) -> str:
        """수정 방법 적용"""
        # = 기호 제거
        formula_content = formula.lstrip("=").strip()

        if method == "average_fix":
            return self._fix_average_formula(formula_content)
        elif method == "sum_division_fix":
            return self._fix_sum_division(formula_content)
        elif method == "simple_iferror":
            return f"=IFERROR({formula_content}, 0)"
        else:
            return self._fix_complex_division(formula_content)

    def _fix_average_formula(self, formula: str) -> str:
        """AVERAGE 함수 수정"""
        # AVERAGE 함수에 IFERROR 적용
        return f"=IFERROR({formula}, 0)"

    def _fix_sum_division(self, formula: str) -> str:
        """SUM을 포함한 나눗셈 수정"""
        # 분모가 0인지 확인하는 IF 문 추가
        match = self.patterns["complex_division"].match(f"={formula}")
        if match:
            numerator = match.group(1).strip()
            denominator = match.group(2).strip()

            # IF 문으로 분모 확인
            return f"=IF({denominator}=0, 0, {numerator}/{denominator})"

        return f"=IFERROR({formula}, 0)"

    def _fix_complex_division(self, formula: str) -> str:
        """복잡한 나눗셈 수정"""
        # 여러 개의 나눗셈이 있는 경우
        if formula.count("/") > 1:
            # 전체를 IFERROR로 감싸기
            return f"=IFERROR({formula}, 0)"

        # 단일 나눗셈
        match = self.patterns["complex_division"].match(f"={formula}")
        if match:
            numerator = match.group(1).strip()
            denominator = match.group(2).strip()

            # 분모가 단순한 참조인 경우
            if re.match(r"^[A-Z]+\d+$", denominator):
                return f"=IF({denominator}=0, 0, {numerator}/{denominator})"
            else:
                # 복잡한 분모인 경우 IFERROR 사용
                return f"=IFERROR({formula}, 0)"

        return f"=IFERROR({formula}, 0)"

    def get_fix_explanation(self, formula: str, fixed_formula: str) -> str:
        """수정 설명 생성"""
        explanations = []

        if "IFERROR" in fixed_formula:
            explanations.append(
                "IFERROR 함수를 사용하여 0으로 나누기 오류를 처리합니다."
            )
            explanations.append("오류가 발생하면 0을 반환합니다.")

        if "IF" in fixed_formula and "=0" in fixed_formula:
            explanations.append("IF 함수를 사용하여 분모가 0인지 먼저 확인합니다.")
            explanations.append(
                "분모가 0이면 0을 반환하고, 그렇지 않으면 나눗셈을 수행합니다."
            )

        return " ".join(explanations)
