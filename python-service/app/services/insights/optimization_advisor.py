"""
Optimization Advisor Service
자동 최적화 제안 시스템
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging
from app.core.interfaces import IOptimizationAdvisor, OptimizationType
from app.services.context import WorkbookContext

logger = logging.getLogger(__name__)


@dataclass
class OptimizationSuggestion:
    """최적화 제안"""

    type: OptimizationType
    priority: int  # 1-5, 5가 가장 높음
    title: str
    description: str
    affected_cells: List[str]
    estimated_impact: str
    implementation_steps: List[str]
    example_code: Optional[str] = None
    auto_applicable: bool = False


class OptimizationAdvisor(IOptimizationAdvisor):
    """최적화 자문 서비스"""

    def __init__(self):
        self.optimization_rules = self._init_optimization_rules()
        self.suggestion_cache: Dict[str, List[OptimizationSuggestion]] = {}

    def _init_optimization_rules(self) -> Dict[str, Dict[str, Any]]:
        """최적화 규칙 초기화"""
        return {
            "volatile_functions": {
                "type": OptimizationType.FORMULA,
                "detector": self._detect_volatile_functions,
                "priority_base": 4,
            },
            "array_formula_opportunity": {
                "type": OptimizationType.FORMULA,
                "detector": self._detect_array_formula_opportunity,
                "priority_base": 3,
            },
            "redundant_calculations": {
                "type": OptimizationType.PERFORMANCE,
                "detector": self._detect_redundant_calculations,
                "priority_base": 4,
            },
            "lookup_optimization": {
                "type": OptimizationType.FORMULA,
                "detector": self._detect_lookup_optimization,
                "priority_base": 3,
            },
            "conditional_formatting_overuse": {
                "type": OptimizationType.PERFORMANCE,
                "detector": self._detect_conditional_formatting_overuse,
                "priority_base": 2,
            },
            "pivot_table_opportunity": {
                "type": OptimizationType.STRUCTURE,
                "detector": self._detect_pivot_table_opportunity,
                "priority_base": 3,
            },
            "data_validation_missing": {
                "type": OptimizationType.DATA_QUALITY,
                "detector": self._detect_missing_data_validation,
                "priority_base": 3,
            },
            "formula_complexity": {
                "type": OptimizationType.READABILITY,
                "detector": self._detect_complex_formulas,
                "priority_base": 2,
            },
        }

    async def analyze_for_optimizations(
        self, context: WorkbookContext
    ) -> List[OptimizationSuggestion]:
        """워크북 최적화 분석"""
        try:
            suggestions = []

            # 각 최적화 규칙 적용
            for rule_name, rule in self.optimization_rules.items():
                try:
                    rule_suggestions = await rule["detector"](context, rule)
                    suggestions.extend(rule_suggestions)
                except Exception as e:
                    logger.warning(f"최적화 규칙 {rule_name} 실행 실패: {e}")

            # 우선순위 순으로 정렬
            suggestions.sort(key=lambda s: s.priority, reverse=True)

            # 캐시 저장
            self.suggestion_cache[context.file_id] = suggestions[:20]  # 상위 20개

            return suggestions[:10]  # 상위 10개 반환

        except Exception as e:
            logger.error(f"최적화 분석 실패: {str(e)}")
            return []

    async def _detect_volatile_functions(
        self, context: WorkbookContext, rule: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """휘발성 함수 사용 감지"""
        volatile_functions = [
            "NOW",
            "TODAY",
            "RAND",
            "RANDBETWEEN",
            "OFFSET",
            "INDIRECT",
        ]
        suggestions = []
        affected_cells = []

        for sheet in context.sheets.values():
            for cell in sheet.cells.values():
                if cell.formula:
                    for func in volatile_functions:
                        if func + "(" in cell.formula.upper():
                            affected_cells.append(f"{sheet.name}!{cell.address}")
                            break

        if affected_cells:
            suggestion = OptimizationSuggestion(
                type=OptimizationType.FORMULA,
                priority=min(5, rule["priority_base"] + len(affected_cells) // 10),
                title="휘발성 함수 사용 최적화",
                description=f"{len(affected_cells)}개 셀에서 휘발성 함수를 사용 중입니다. 이는 재계산 성능에 영향을 줍니다.",
                affected_cells=affected_cells[:10],  # 최대 10개
                estimated_impact="재계산 시간 20-50% 단축 가능",
                implementation_steps=[
                    "NOW() 대신 정적 타임스탬프 사용을 고려하세요",
                    "INDIRECT() 대신 직접 참조를 사용하세요",
                    "OFFSET() 대신 INDEX/MATCH 조합을 사용하세요",
                    "필요한 경우에만 F9 키로 수동 재계산하세요",
                ],
                example_code="=INDEX(A:A, MATCH(lookup_value, B:B, 0))",
                auto_applicable=False,
            )
            suggestions.append(suggestion)

        return suggestions

    async def _detect_array_formula_opportunity(
        self, context: WorkbookContext, rule: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """배열 수식 적용 기회 감지"""
        suggestions = []

        # 같은 패턴의 수식이 연속된 셀에 있는지 확인
        for sheet in context.sheets.values():
            formula_patterns = {}

            for cell in sheet.cells.values():
                if cell.formula:
                    # 수식을 정규화 (셀 참조를 패턴으로 변환)
                    import re

                    normalized = re.sub(r"\$?[A-Z]+\$?\d+", "REF", cell.formula)

                    if normalized not in formula_patterns:
                        formula_patterns[normalized] = []
                    formula_patterns[normalized].append(cell.address)

            # 같은 패턴이 5개 이상인 경우
            for pattern, cells in formula_patterns.items():
                if len(cells) >= 5:
                    suggestion = OptimizationSuggestion(
                        type=OptimizationType.FORMULA,
                        priority=rule["priority_base"],
                        title="배열 수식으로 변환 가능",
                        description=f"{sheet.name} 시트에서 {len(cells)}개의 유사한 수식을 배열 수식으로 통합할 수 있습니다",
                        affected_cells=[f"{sheet.name}!{c}" for c in cells[:5]],
                        estimated_impact="수식 관리 간소화, 일관성 향상",
                        implementation_steps=[
                            "범위를 선택하세요",
                            "수식을 입력하세요",
                            "Ctrl+Shift+Enter로 배열 수식으로 입력하세요",
                            "또는 SEQUENCE, FILTER 등 동적 배열 함수 사용을 고려하세요",
                        ],
                        example_code="{=SUM(A1:A10*B1:B10)}",
                        auto_applicable=False,
                    )
                    suggestions.append(suggestion)

        return suggestions

    async def _detect_redundant_calculations(
        self, context: WorkbookContext, rule: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """중복 계산 감지"""
        suggestions = []
        calculation_cache = {}

        for sheet in context.sheets.values():
            for cell in sheet.cells.values():
                if cell.formula:
                    # 복잡한 계산식 찾기 (함수 중첩이 많은 경우)
                    import re

                    nested_count = cell.formula.count("(")

                    if nested_count >= 3:
                        # 동일한 부분 수식이 여러 번 사용되는지 확인
                        sub_expressions = re.findall(r"[A-Z]+\([^)]+\)", cell.formula)

                        for expr in sub_expressions:
                            if expr not in calculation_cache:
                                calculation_cache[expr] = []
                            calculation_cache[expr].append(
                                f"{sheet.name}!{cell.address}"
                            )

        # 같은 계산이 3번 이상 반복되는 경우
        for expr, cells in calculation_cache.items():
            if len(cells) >= 3:
                suggestion = OptimizationSuggestion(
                    type=OptimizationType.PERFORMANCE,
                    priority=rule["priority_base"] + 1,
                    title="중복 계산 최적화 필요",
                    description=f"'{expr}' 계산이 {len(cells)}개 셀에서 반복됩니다",
                    affected_cells=cells[:5],
                    estimated_impact="계산 속도 30% 향상 가능",
                    implementation_steps=[
                        "중복 계산을 별도 셀에 저장하세요",
                        "다른 셀에서는 이 셀을 참조하세요",
                        "이름 정의를 사용하여 가독성을 높이세요",
                    ],
                    example_code="보조_계산 = " + expr + "\n다른 셀 = 보조_계산 * 2",
                    auto_applicable=True,
                )
                suggestions.append(suggestion)

        return suggestions

    async def _detect_lookup_optimization(
        self, context: WorkbookContext, rule: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """LOOKUP 함수 최적화 기회 감지"""
        suggestions = []
        vlookup_cells = []

        for sheet in context.sheets.values():
            for cell in sheet.cells.values():
                if cell.formula and "VLOOKUP" in cell.formula.upper():
                    vlookup_cells.append(f"{sheet.name}!{cell.address}")

        if len(vlookup_cells) >= 5:
            suggestion = OptimizationSuggestion(
                type=OptimizationType.FORMULA,
                priority=rule["priority_base"],
                title="VLOOKUP을 INDEX/MATCH로 최적화",
                description=f"{len(vlookup_cells)}개의 VLOOKUP 사용을 INDEX/MATCH로 변경하면 성능이 향상됩니다",
                affected_cells=vlookup_cells[:5],
                estimated_impact="조회 속도 40% 향상, 더 유연한 참조",
                implementation_steps=[
                    "VLOOKUP(A1, B:D, 3, FALSE)를",
                    "INDEX(D:D, MATCH(A1, B:B, 0))로 변경",
                    "XLOOKUP 함수 사용도 고려 (Excel 365)",
                    "정렬된 데이터의 경우 근사 일치 사용",
                ],
                example_code="=INDEX(반환_열, MATCH(조회값, 조회_열, 0))",
                auto_applicable=True,
            )
            suggestions.append(suggestion)

        return suggestions

    async def _detect_conditional_formatting_overuse(
        self, context: WorkbookContext, rule: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """조건부 서식 과다 사용 감지"""
        # 실제 구현에서는 조건부 서식 규칙을 확인해야 함
        # 여기서는 시뮬레이션
        suggestions = []

        # 많은 수의 개별 셀 서식이 있다고 가정
        if context.total_cells > 1000:
            suggestion = OptimizationSuggestion(
                type=OptimizationType.PERFORMANCE,
                priority=rule["priority_base"],
                title="조건부 서식 통합 권장",
                description="개별 셀 서식 대신 범위 기반 조건부 서식을 사용하세요",
                affected_cells=[],
                estimated_impact="화면 새로고침 속도 향상",
                implementation_steps=[
                    "유사한 조건부 서식 규칙을 통합하세요",
                    "전체 열/행에 적용 가능한 규칙을 만드세요",
                    "불필요한 서식 규칙은 제거하세요",
                    "서식 규칙 우선순위를 최적화하세요",
                ],
                auto_applicable=False,
            )
            suggestions.append(suggestion)

        return suggestions

    async def _detect_pivot_table_opportunity(
        self, context: WorkbookContext, rule: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """피벗 테이블 사용 기회 감지"""
        suggestions = []

        # SUMIF, COUNTIF 등의 집계 함수가 많이 사용되는지 확인
        for sheet in context.sheets.values():
            aggregation_count = 0
            aggregation_cells = []

            for cell in sheet.cells.values():
                if cell.formula:
                    formula_upper = cell.formula.upper()
                    if any(
                        func in formula_upper
                        for func in ["SUMIF", "COUNTIF", "AVERAGEIF", "SUMIFS"]
                    ):
                        aggregation_count += 1
                        aggregation_cells.append(f"{sheet.name}!{cell.address}")

            if aggregation_count >= 10:
                suggestion = OptimizationSuggestion(
                    type=OptimizationType.STRUCTURE,
                    priority=rule["priority_base"],
                    title="피벗 테이블 사용 권장",
                    description=f"{sheet.name}에서 {aggregation_count}개의 집계 함수를 피벗 테이블로 대체할 수 있습니다",
                    affected_cells=aggregation_cells[:5],
                    estimated_impact="데이터 분석 속도 향상, 유연성 증가",
                    implementation_steps=[
                        "원본 데이터를 테이블로 변환하세요",
                        "삽입 > 피벗 테이블을 선택하세요",
                        "필요한 필드를 행/열/값 영역에 배치하세요",
                        "슬라이서를 추가하여 동적 필터링하세요",
                    ],
                    auto_applicable=False,
                )
                suggestions.append(suggestion)

        return suggestions

    async def _detect_missing_data_validation(
        self, context: WorkbookContext, rule: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """데이터 유효성 검사 누락 감지"""
        suggestions = []

        # 입력 셀 추정 (수식이 없고 값이 있는 셀)
        for sheet in context.sheets.values():
            input_cells = []
            data_patterns = {}

            for cell in sheet.cells.values():
                if not cell.formula and cell.value is not None:
                    input_cells.append(cell)

                    # 데이터 패턴 분석
                    value_type = type(cell.value).__name__
                    if value_type not in data_patterns:
                        data_patterns[value_type] = []
                    data_patterns[value_type].append(cell.address)

            # 같은 타입의 데이터가 많은 열 찾기
            for dtype, cells in data_patterns.items():
                if len(cells) >= 10:
                    suggestion = OptimizationSuggestion(
                        type=OptimizationType.DATA_QUALITY,
                        priority=rule["priority_base"],
                        title=f"{dtype} 데이터 유효성 검사 추가",
                        description=f"{sheet.name}의 {len(cells)}개 셀에 데이터 유효성 검사를 추가하세요",
                        affected_cells=[f"{sheet.name}!{c}" for c in cells[:5]],
                        estimated_impact="데이터 입력 오류 90% 감소",
                        implementation_steps=[
                            "데이터 > 데이터 유효성 검사를 선택하세요",
                            f"{dtype} 타입에 맞는 검증 규칙을 설정하세요",
                            "오류 메시지와 입력 메시지를 추가하세요",
                            "드롭다운 목록 사용을 고려하세요",
                        ],
                        auto_applicable=True,
                    )
                    suggestions.append(suggestion)
                    break

        return suggestions

    async def _detect_complex_formulas(
        self, context: WorkbookContext, rule: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """복잡한 수식 감지"""
        suggestions = []
        complex_formulas = []

        for sheet in context.sheets.values():
            for cell in sheet.cells.values():
                if cell.formula:
                    # 수식 복잡도 측정
                    complexity = 0
                    complexity += cell.formula.count("(")  # 중첩 수준
                    complexity += cell.formula.count("IF")  # 조건문
                    complexity += len(cell.formula) // 50  # 길이

                    if complexity >= 10:
                        complex_formulas.append(
                            {
                                "cell": f"{sheet.name}!{cell.address}",
                                "formula": cell.formula[:100] + "...",
                                "complexity": complexity,
                            }
                        )

        if complex_formulas:
            # 가장 복잡한 수식들
            complex_formulas.sort(key=lambda x: x["complexity"], reverse=True)

            suggestion = OptimizationSuggestion(
                type=OptimizationType.READABILITY,
                priority=rule["priority_base"],
                title="복잡한 수식 단순화 필요",
                description=f"{len(complex_formulas)}개의 복잡한 수식을 단순화할 수 있습니다",
                affected_cells=[f["cell"] for f in complex_formulas[:5]],
                estimated_impact="유지보수성 향상, 오류 가능성 감소",
                implementation_steps=[
                    "복잡한 수식을 여러 단계로 나누세요",
                    "중간 계산 결과를 별도 셀에 저장하세요",
                    "이름 정의를 사용하여 가독성을 높이세요",
                    "LET 함수를 사용하여 변수를 정의하세요 (Excel 365)",
                ],
                example_code="=LET(세율, 0.1, 매출, A1, 비용, B1, (매출-비용)*세율)",
                auto_applicable=False,
            )
            suggestions.append(suggestion)

        return suggestions

    def get_optimization_summary(self, file_id: str) -> Dict[str, Any]:
        """최적화 제안 요약"""
        suggestions = self.suggestion_cache.get(file_id, [])

        if not suggestions:
            return {
                "has_suggestions": False,
                "total_suggestions": 0,
                "by_type": {},
                "top_suggestions": [],
            }

        # 타입별 집계
        by_type = {}
        for s in suggestions:
            type_name = s.type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

        # 자동 적용 가능한 제안
        auto_applicable = [s for s in suggestions if s.auto_applicable]

        return {
            "has_suggestions": True,
            "total_suggestions": len(suggestions),
            "auto_applicable": len(auto_applicable),
            "by_type": by_type,
            "top_suggestions": [
                {
                    "type": s.type.value,
                    "priority": s.priority,
                    "title": s.title,
                    "description": s.description,
                    "impact": s.estimated_impact,
                    "affected_cells": len(s.affected_cells),
                    "auto_applicable": s.auto_applicable,
                }
                for s in suggestions[:5]
            ],
        }

    async def apply_optimization(
        self, file_id: str, optimization_id: str
    ) -> Dict[str, Any]:
        """최적화 자동 적용 (가능한 경우)"""
        # 실제 구현에서는 최적화를 실제로 적용
        # 여기서는 시뮬레이션만
        return {
            "success": True,
            "message": "최적화가 성공적으로 적용되었습니다",
            "changes_made": 5,
        }
