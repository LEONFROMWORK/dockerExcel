"""
AI Chat Helper Functions
AI 채팅 관련 헬퍼 함수들
"""

from typing import List, Dict, Optional
from app.api.v1.ai import CellContext
import logging

logger = logging.getLogger(__name__)


def build_enhanced_prompt(prompt: str, cell_context: Optional[CellContext]) -> str:
    """셀 컨텍스트를 포함한 향상된 프롬프트 생성"""
    if not cell_context:
        return prompt

    enhanced_prompt = f"{prompt}\n\n"
    enhanced_prompt += "[셀 정보]\n"
    enhanced_prompt += f"- 위치: {cell_context.address}"

    if cell_context.sheetName:
        enhanced_prompt += f" ({cell_context.sheetName} 시트)"

    enhanced_prompt += "\n"

    if cell_context.value is not None:
        enhanced_prompt += f"- 현재 값: {cell_context.value}\n"

    if cell_context.formula:
        enhanced_prompt += f"- 수식: {cell_context.formula}\n"

    return enhanced_prompt


def generate_contextual_suggestions(
    cell_context: Optional[CellContext], prompt: str
) -> List[str]:
    """셀 컨텍스트 기반 제안 생성"""
    suggestions = []

    if not cell_context:
        suggestions = [
            "Excel 함수 참조 가이드 확인하기",
            "데이터 유효성 검사 설정하기",
            "조건부 서식 적용하기",
        ]
    else:
        # Formula-based suggestions
        if cell_context.formula:
            suggestions.extend(
                [
                    "수식 오류 검사하기",
                    "수식 최적화 방법 알아보기",
                    "함수 중첩 단순화하기",
                ]
            )

        # Value-based suggestions
        if isinstance(cell_context.value, (int, float)):
            suggestions.extend(
                ["숫자 서식 설정하기", "차트 만들기", "조건부 서식으로 강조하기"]
            )
        elif isinstance(cell_context.value, str):
            if "#" in str(cell_context.value):
                suggestions.extend(["에러 원인 분석하기", "참조 오류 수정하기"])
            else:
                suggestions.extend(["텍스트 함수 활용하기", "데이터 정리하기"])

        # General suggestions
        suggestions.extend(["셀 보호 설정하기", "데이터 검증 규칙 추가하기"])

    return suggestions[:5]  # Return top 5 suggestions


def generate_follow_up_questions(
    cell_context: Optional[CellContext], prompt: str
) -> List[str]:
    """컨텍스트 기반 후속 질문 생성"""
    questions = []

    if not cell_context:
        questions = [
            "다른 Excel 기능에 대해 궁금한 것이 있나요?",
            "특정 작업을 자동화하고 싶으신가요?",
            "데이터 분석에 도움이 필요하신가요?",
        ]
    else:
        if cell_context.formula:
            questions.extend(
                [
                    "이 수식의 다른 활용 방법을 알고 싶으신가요?",
                    "수식 성능을 개선하는 방법이 궁금하신가요?",
                ]
            )

        if cell_context.value:
            questions.extend(
                [
                    "이 데이터로 다른 분석을 하고 싶으신가요?",
                    "관련된 다른 셀들과의 연관성을 확인하고 싶으신가요?",
                ]
            )

        questions.extend(
            [
                "이 셀과 관련된 다른 문제가 있나요?",
                "비슷한 작업을 다른 셀에도 적용하고 싶으신가요?",
            ]
        )

    return questions[:4]  # Return top 4 questions


def analyze_related_cells(cell_context: Optional[CellContext]) -> List[str]:
    """관련 셀 분석"""
    if not cell_context or not cell_context.formula:
        return []

    # Basic formula parsing to find referenced cells
    related_cells = []
    formula = cell_context.formula

    # Simple regex to find cell references (A1, B2, etc.)
    import re

    cell_refs = re.findall(r"[A-Z]+\d+", formula.upper())

    # Remove duplicates and current cell
    related_cells = list(set(cell_refs))
    if cell_context.address in related_cells:
        related_cells.remove(cell_context.address)

    return related_cells[:5]  # Return top 5 related cells


def generate_action_items(
    cell_context: Optional[CellContext], ai_response: str
) -> List[Dict[str, str]]:
    """실행 가능한 액션 아이템 생성"""
    action_items = []

    if not cell_context:
        return action_items

    # Formula-related actions
    if cell_context.formula:
        action_items.append(
            {
                "type": "formula",
                "description": "수식 유효성 검사 실행",
                "code": f"=FORMULATEXT({cell_context.address})",
            }
        )

    # Value-related actions
    if isinstance(cell_context.value, (int, float)):
        action_items.append(
            {
                "type": "format",
                "description": "숫자 서식 적용",
                "code": "셀 서식 > 숫자 탭에서 원하는 형식 선택",
            }
        )

        action_items.append(
            {
                "type": "chart",
                "description": "차트 생성",
                "code": "삽입 > 차트 > 적절한 차트 유형 선택",
            }
        )

    # Error-related actions
    if cell_context.value and "#" in str(cell_context.value):
        action_items.append(
            {
                "type": "data",
                "description": "에러 추적 및 수정",
                "code": "수식 > 수식 계산 > 오류 검사",
            }
        )

    return action_items[:3]  # Return top 3 action items
