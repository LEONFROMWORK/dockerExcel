"""
Circular Reference Fix Strategy
순환 참조 오류 수정 전략 구현
"""

from typing import Optional, Dict, Any, List, Tuple
from app.core.interfaces import IErrorFixStrategy, ExcelError, FixResult
import re
import logging

logger = logging.getLogger(__name__)


class CircularRefFixStrategy(IErrorFixStrategy):
    """순환 참조 오류 수정 전략"""

    def can_handle(self, error: ExcelError) -> bool:
        """이 전략이 처리할 수 있는 오류인지 확인"""
        return error.type.lower() in ["circular_reference", "circular", "circular_ref"]

    async def apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """순환 참조 오류 수정 적용"""
        try:
            original_formula = error.formula or ""
            current_cell = error.cell

            # 컨텍스트에서 순환 참조 체인 정보 추출
            circular_chain = []
            if context and "circular_chain" in context:
                circular_chain = context["circular_chain"]
            elif context and "details" in context:
                # 오류 메시지에서 순환 참조 체인 추출 시도
                details = context["details"]
                if isinstance(details, str):
                    circular_chain = self._extract_circular_chain(details)

            # 수정 방법 결정
            fixed_formula = original_formula
            fix_method = ""

            # 1. 자기 참조 제거
            if current_cell and current_cell in original_formula:
                fixed_formula, method = self._remove_self_reference(
                    original_formula, current_cell
                )
                fix_method = method

            # 2. 순환 체인 끊기
            elif circular_chain:
                fixed_formula, method = self._break_circular_chain(
                    original_formula, current_cell, circular_chain
                )
                fix_method = method

            # 3. 반복 계산으로 해결 가능한 경우
            elif self._is_iterative_calculation(original_formula):
                fixed_formula, method = self._convert_to_iterative(original_formula)
                fix_method = method

            # 4. 기본 수정: 정적 값으로 대체
            if fixed_formula == original_formula:
                # 수식의 복잡도에 따라 기본값 결정
                default_value = self._get_default_value(original_formula)
                fixed_formula = str(default_value)
                fix_method = f"순환 참조를 정적 값({default_value})으로 대체"

            return FixResult(
                success=True,
                error_id=error.id,
                original_formula=original_formula,
                fixed_formula=fixed_formula,
                confidence=0.7 if fix_method != "순환 참조를 정적 값" else 0.5,
                applied=False,
                message=f"순환 참조 수정: {fix_method}",
            )

        except Exception as e:
            logger.error(f"Circular reference fix failed: {str(e)}")
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
        # 자기 참조는 높은 신뢰도
        if error.cell and error.cell in (error.formula or ""):
            return 0.9

        # 일반 순환 참조는 중간 신뢰도
        return 0.7

    def _remove_self_reference(
        self, formula: str, current_cell: str
    ) -> Tuple[str, str]:
        """자기 참조 제거"""
        # 현재 셀 참조를 0으로 대체
        cell_pattern = rf"\b{re.escape(current_cell)}\b"
        fixed = re.sub(cell_pattern, "0", formula, flags=re.IGNORECASE)

        if fixed != formula:
            return fixed, f"{current_cell} 자기 참조를 0으로 대체"

        return formula, ""

    def _break_circular_chain(
        self, formula: str, current_cell: str, circular_chain: List[str]
    ) -> Tuple[str, str]:
        """순환 체인 끊기"""
        # 순환 체인에서 현재 셀 다음에 오는 셀 찾기
        try:
            current_index = circular_chain.index(current_cell)
            if current_index < len(circular_chain) - 1:
                next_cell = circular_chain[current_index + 1]

                # 다음 셀 참조를 이전 값 참조로 변경
                # 예: =A1+B1 에서 B1이 순환이면 -> =A1+OFFSET(B1,-1,0)
                cell_pattern = rf"\b{re.escape(next_cell)}\b"

                # OFFSET을 사용하여 이전 행 참조
                fixed = re.sub(
                    cell_pattern,
                    f"IFERROR(OFFSET({next_cell},-1,0),0)",
                    formula,
                    flags=re.IGNORECASE,
                )

                if fixed != formula:
                    return fixed, f"순환 체인의 {next_cell} 참조를 이전 행으로 변경"
        except ValueError:
            pass

        # 체인의 마지막 셀 참조를 제거
        if circular_chain:
            last_cell = circular_chain[-1]
            cell_pattern = rf"\b{re.escape(last_cell)}\b"
            fixed = re.sub(cell_pattern, "0", formula, flags=re.IGNORECASE)

            if fixed != formula:
                return fixed, f"순환 체인의 마지막 셀 {last_cell}을 0으로 대체"

        return formula, ""

    def _is_iterative_calculation(self, formula: str) -> bool:
        """반복 계산으로 해결 가능한지 확인"""
        # 이자 계산, 할인율 계산 등의 패턴
        iterative_patterns = [
            r"PMT\s*\(",  # 대출 상환액 계산
            r"IRR\s*\(",  # 내부 수익률
            r"XIRR\s*\(",  # 확장 내부 수익률
            r"RATE\s*\(",  # 이자율 계산
        ]

        for pattern in iterative_patterns:
            if re.search(pattern, formula, re.IGNORECASE):
                return True

        return False

    def _convert_to_iterative(self, formula: str) -> Tuple[str, str]:
        """반복 계산 수식으로 변환"""
        # 간단한 경우: IF 조건 추가로 순환 방지
        # 예: =A1+B1 -> =IF(ISBLANK(A1),0,A1+B1)

        # 셀 참조 찾기
        cell_refs = re.findall(r"\b[A-Z]+\d+\b", formula, re.IGNORECASE)

        if cell_refs:
            first_ref = cell_refs[0]
            # ISBLANK 조건 추가
            fixed = f"=IF(ISBLANK({first_ref}), 0, {formula.lstrip('=')})"
            return fixed, "반복 계산을 위한 조건문 추가"

        return formula, ""

    def _extract_circular_chain(self, details: str) -> List[str]:
        """오류 메시지에서 순환 참조 체인 추출"""
        # 예: "A1 -> B1 -> C1 -> A1"
        chain = []

        # 화살표 패턴
        arrow_pattern = r"([A-Z]+\d+)\s*(?:->|→)"
        matches = re.findall(arrow_pattern, details, re.IGNORECASE)
        chain.extend(matches)

        # 쉼표로 구분된 패턴
        if not chain:
            comma_pattern = r"([A-Z]+\d+)(?:\s*,\s*|$)"
            matches = re.findall(comma_pattern, details, re.IGNORECASE)
            chain.extend(matches)

        return chain

    def _get_default_value(self, formula: str) -> Any:
        """수식에 따른 기본값 결정"""
        # SUM, COUNT 등은 0
        if any(func in formula.upper() for func in ["SUM", "COUNT", "COUNTA"]):
            return 0

        # AVERAGE는 빈 문자열
        if "AVERAGE" in formula.upper():
            return '""'

        # 텍스트 함수는 빈 문자열
        if any(
            func in formula.upper() for func in ["CONCATENATE", "TEXT", "LEFT", "RIGHT"]
        ):
            return '""'

        # 기본값은 0
        return 0
