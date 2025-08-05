"""
Pattern Analyzer for Proactive Insights
프로액티브 인사이트를 위한 패턴 분석 엔진
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import logging
from app.core.interfaces import IPatternAnalyzer, PatternType
from app.services.context import WorkbookContext

logger = logging.getLogger(__name__)


@dataclass
class UserAction:
    """사용자 작업 기록"""

    timestamp: datetime
    action_type: str  # cell_select, formula_edit, value_change, etc.
    target: str  # cell address or range
    details: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""


@dataclass
class WorkPattern:
    """작업 패턴"""

    pattern_type: PatternType
    confidence: float
    description: str
    frequency: int
    last_seen: datetime
    actions: List[UserAction] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class PatternAnalyzer(IPatternAnalyzer):
    """패턴 분석 엔진"""

    def __init__(self):
        self.user_actions: Dict[str, List[UserAction]] = defaultdict(list)
        self.detected_patterns: Dict[str, List[WorkPattern]] = defaultdict(list)
        self.pattern_templates = self._init_pattern_templates()

    def _init_pattern_templates(self) -> Dict[str, Dict[str, Any]]:
        """패턴 템플릿 초기화"""
        return {
            "sequential_cell_edit": {
                "type": PatternType.SEQUENTIAL,
                "min_actions": 3,
                "time_window": 300,  # 5분
                "detector": self._detect_sequential_edits,
            },
            "formula_copy_pattern": {
                "type": PatternType.FORMULA_COPY,
                "min_actions": 2,
                "time_window": 120,
                "detector": self._detect_formula_copy,
            },
            "data_validation_pattern": {
                "type": PatternType.DATA_VALIDATION,
                "min_actions": 2,
                "time_window": 600,
                "detector": self._detect_data_validation_need,
            },
            "calculation_chain": {
                "type": PatternType.CALCULATION,
                "min_actions": 3,
                "time_window": 300,
                "detector": self._detect_calculation_chain,
            },
            "error_correction_loop": {
                "type": PatternType.ERROR_LOOP,
                "min_actions": 2,
                "time_window": 180,
                "detector": self._detect_error_loop,
            },
        }

    async def analyze_user_actions(
        self, session_id: str, context: WorkbookContext
    ) -> List[WorkPattern]:
        """사용자 작업 패턴 분석"""
        try:
            actions = self.user_actions.get(session_id, [])
            if len(actions) < 2:
                return []

            detected = []
            current_time = datetime.now()

            # 각 패턴 템플릿에 대해 검사
            for pattern_name, template in self.pattern_templates.items():
                # 시간 윈도우 내의 작업만 필터링
                time_window = timedelta(seconds=template["time_window"])
                recent_actions = [
                    a for a in actions if current_time - a.timestamp <= time_window
                ]

                if len(recent_actions) >= template["min_actions"]:
                    # 패턴 감지 함수 실행
                    pattern = await template["detector"](
                        recent_actions, context, session_id
                    )
                    if pattern:
                        detected.append(pattern)

            # 감지된 패턴 저장
            self.detected_patterns[session_id] = detected

            return detected

        except Exception as e:
            logger.error(f"패턴 분석 실패: {str(e)}")
            return []

    async def _detect_sequential_edits(
        self, actions: List[UserAction], context: WorkbookContext, session_id: str
    ) -> Optional[WorkPattern]:
        """순차적 셀 편집 패턴 감지"""
        # 연속된 셀 편집 감지
        cell_sequence = []
        for action in actions:
            if action.action_type in ["cell_edit", "value_change"]:
                cell_sequence.append(action.target)

        if len(cell_sequence) < 3:
            return None

        # 패턴 확인 (예: A1, A2, A3...)
        if self._is_sequential_cells(cell_sequence):
            return WorkPattern(
                pattern_type=PatternType.SEQUENTIAL,
                confidence=0.85,
                description="순차적 셀 편집 패턴 감지",
                frequency=len(cell_sequence),
                last_seen=datetime.now(),
                actions=actions[-5:],  # 최근 5개 액션
                suggestions=[
                    "자동 채우기 기능을 사용하면 더 빠르게 작업할 수 있습니다",
                    "Ctrl+D (아래로 채우기) 또는 Ctrl+R (오른쪽으로 채우기) 사용을 고려하세요",
                    "데이터 > 플래시 채우기 기능도 유용할 수 있습니다",
                ],
            )

        return None

    async def _detect_formula_copy(
        self, actions: List[UserAction], context: WorkbookContext, session_id: str
    ) -> Optional[WorkPattern]:
        """수식 복사 패턴 감지"""
        formula_actions = [
            a
            for a in actions
            if a.action_type == "formula_edit" and a.details.get("formula")
        ]

        if len(formula_actions) < 2:
            return None

        # 유사한 수식 패턴 확인
        formulas = [a.details["formula"] for a in formula_actions]
        if self._are_similar_formulas(formulas):
            return WorkPattern(
                pattern_type=PatternType.FORMULA_COPY,
                confidence=0.90,
                description="반복적인 수식 패턴 감지",
                frequency=len(formula_actions),
                last_seen=datetime.now(),
                actions=formula_actions,
                suggestions=[
                    "배열 수식을 사용하여 여러 셀에 동시에 적용할 수 있습니다",
                    "상대 참조와 절대 참조($)를 적절히 활용하세요",
                    "이름 정의를 사용하면 수식을 더 읽기 쉽게 만들 수 있습니다",
                ],
            )

        return None

    async def _detect_data_validation_need(
        self, actions: List[UserAction], context: WorkbookContext, session_id: str
    ) -> Optional[WorkPattern]:
        """데이터 유효성 검사 필요 패턴 감지"""
        # 같은 셀에 대한 반복적인 수정 감지
        cell_edit_counts = defaultdict(int)
        error_corrections = []

        for action in actions:
            if action.action_type == "value_change":
                cell_edit_counts[action.target] += 1
            elif action.action_type == "error_correction":
                error_corrections.append(action)

        # 동일 셀 3회 이상 수정 또는 오류 수정이 있는 경우
        frequently_edited = [
            cell for cell, count in cell_edit_counts.items() if count >= 3
        ]

        if frequently_edited or len(error_corrections) >= 2:
            return WorkPattern(
                pattern_type=PatternType.DATA_VALIDATION,
                confidence=0.75,
                description="데이터 입력 오류 반복 패턴",
                frequency=(
                    max(cell_edit_counts.values())
                    if cell_edit_counts
                    else len(error_corrections)
                ),
                last_seen=datetime.now(),
                actions=actions[-5:],
                suggestions=[
                    "데이터 유효성 검사를 설정하여 입력 오류를 방지하세요",
                    "드롭다운 목록을 사용하여 유효한 값만 선택할 수 있게 하세요",
                    "조건부 서식을 사용하여 잘못된 데이터를 시각적으로 표시하세요",
                ],
            )

        return None

    async def _detect_calculation_chain(
        self, actions: List[UserAction], context: WorkbookContext, session_id: str
    ) -> Optional[WorkPattern]:
        """계산 체인 패턴 감지"""
        formula_cells = []

        for action in actions:
            if action.action_type == "formula_edit":
                cell_addr = action.target
                cell = context.get_cell(
                    action.details.get("sheet", "Sheet1"), cell_addr
                )
                if cell and cell.dependencies:
                    formula_cells.append((cell_addr, cell.dependencies))

        # 의존성 체인 분석
        if len(formula_cells) >= 3:
            # 연결된 계산인지 확인
            is_chain = self._is_calculation_chain(formula_cells)
            if is_chain:
                return WorkPattern(
                    pattern_type=PatternType.CALCULATION,
                    confidence=0.80,
                    description="복잡한 계산 체인 구성 중",
                    frequency=len(formula_cells),
                    last_seen=datetime.now(),
                    actions=actions[-5:],
                    suggestions=[
                        "중간 계산 결과를 별도 셀에 저장하면 디버깅이 쉬워집니다",
                        "복잡한 수식은 여러 단계로 나누어 가독성을 높이세요",
                        "이름 정의를 사용하여 계산 로직을 명확하게 표현하세요",
                    ],
                )

        return None

    async def _detect_error_loop(
        self, actions: List[UserAction], context: WorkbookContext, session_id: str
    ) -> Optional[WorkPattern]:
        """오류 수정 루프 패턴 감지"""
        error_actions = [
            a
            for a in actions
            if a.action_type in ["error_detected", "error_correction", "formula_error"]
        ]

        if len(error_actions) >= 2:
            # 같은 셀에서 반복되는 오류인지 확인
            error_cells = [a.target for a in error_actions]
            if len(set(error_cells)) < len(error_cells):  # 중복이 있음
                return WorkPattern(
                    pattern_type=PatternType.ERROR_LOOP,
                    confidence=0.85,
                    description="오류 수정이 반복되고 있습니다",
                    frequency=len(error_actions),
                    last_seen=datetime.now(),
                    actions=error_actions,
                    suggestions=[
                        "수식의 참조 범위를 다시 확인해보세요",
                        "순환 참조가 있는지 확인하세요",
                        "데이터 타입이 일치하는지 확인하세요",
                        "자동 수정 기능을 사용해보세요",
                    ],
                )

        return None

    def _is_sequential_cells(self, cells: List[str]) -> bool:
        """셀 주소가 순차적인지 확인"""
        try:
            # 간단한 구현 - A1, A2, A3 형태 확인
            if len(cells) < 3:
                return False

            # 행 또는 열이 순차적으로 증가하는지 확인
            from app.core.excel_utils import ExcelUtils

            coords = [ExcelUtils.cell_to_row_col(cell) for cell in cells]

            # 행 순차 확인
            rows = [c[0] for c in coords]
            cols = [c[1] for c in coords]

            # 같은 열에서 행이 순차적으로 증가
            if len(set(cols)) == 1 and all(
                rows[i] + 1 == rows[i + 1] for i in range(len(rows) - 1)
            ):
                return True

            # 같은 행에서 열이 순차적으로 증가
            if len(set(rows)) == 1 and all(
                cols[i] + 1 == cols[i + 1] for i in range(len(cols) - 1)
            ):
                return True

            return False

        except Exception:
            return False

    def _are_similar_formulas(self, formulas: List[str]) -> bool:
        """수식들이 유사한 패턴인지 확인"""
        if len(formulas) < 2:
            return False

        # 수식에서 셀 참조를 제거하고 구조 비교
        import re

        # 셀 참조를 플레이스홀더로 변경
        normalized = []
        for formula in formulas:
            # A1, $A$1 형태의 셀 참조를 CELL로 변경
            norm = re.sub(r"\$?[A-Z]+\$?\d+", "CELL", formula)
            normalized.append(norm)

        # 정규화된 수식이 모두 같으면 유사한 패턴
        return len(set(normalized)) == 1

    def _is_calculation_chain(self, formula_cells: List[Tuple[str, Set[str]]]) -> bool:
        """계산 체인 여부 확인"""
        # 각 셀이 이전 셀을 참조하는지 확인
        for i in range(1, len(formula_cells)):
            formula_cells[i][0]
            prev_cell = formula_cells[i - 1][0]
            dependencies = formula_cells[i][1]

            # 이전 셀을 참조하지 않으면 체인이 아님
            if prev_cell not in dependencies:
                return False

        return True

    def record_action(self, session_id: str, action: UserAction):
        """사용자 작업 기록"""
        self.user_actions[session_id].append(action)

        # 메모리 관리 - 세션당 최대 1000개 액션만 유지
        if len(self.user_actions[session_id]) > 1000:
            self.user_actions[session_id] = self.user_actions[session_id][-500:]

    def get_pattern_insights(self, session_id: str) -> Dict[str, Any]:
        """패턴 기반 인사이트 조회"""
        patterns = self.detected_patterns.get(session_id, [])

        if not patterns:
            return {"has_insights": False, "patterns": []}

        # 신뢰도 순으로 정렬
        patterns.sort(key=lambda p: p.confidence, reverse=True)

        return {
            "has_insights": True,
            "patterns": [
                {
                    "type": p.pattern_type.value,
                    "confidence": p.confidence,
                    "description": p.description,
                    "frequency": p.frequency,
                    "suggestions": p.suggestions,
                    "last_seen": p.last_seen.isoformat(),
                }
                for p in patterns[:5]  # 상위 5개만
            ],
            "summary": self._generate_pattern_summary(patterns),
        }

    def _generate_pattern_summary(self, patterns: List[WorkPattern]) -> str:
        """패턴 요약 생성"""
        if not patterns:
            return "작업 패턴을 분석 중입니다."

        most_frequent = max(patterns, key=lambda p: p.frequency)

        summaries = {
            PatternType.SEQUENTIAL: "순차적으로 셀을 편집하고 있습니다. 자동 채우기 기능을 활용해보세요.",
            PatternType.FORMULA_COPY: "유사한 수식을 반복 입력하고 있습니다. 배열 수식을 고려해보세요.",
            PatternType.DATA_VALIDATION: "데이터 입력 오류가 자주 발생합니다. 유효성 검사를 설정하세요.",
            PatternType.CALCULATION: "복잡한 계산을 구성 중입니다. 단계별로 나누어 관리하세요.",
            PatternType.ERROR_LOOP: "오류 수정이 반복되고 있습니다. 근본 원인을 확인하세요.",
        }

        return summaries.get(
            most_frequent.pattern_type,
            f"{len(patterns)}개의 작업 패턴이 감지되었습니다.",
        )

    def clear_patterns(self, session_id: str):
        """세션의 패턴 데이터 초기화"""
        self.user_actions.pop(session_id, None)
        self.detected_patterns.pop(session_id, None)
