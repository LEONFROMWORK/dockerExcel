"""
Error Classification Service
오류 분류 및 우선순위 지정 전담 서비스 - DRY 원칙 적용
"""

from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from app.core.interfaces import ExcelError
import logging

logger = logging.getLogger(__name__)


class ErrorClassificationService:
    """오류 분류 및 우선순위 지정 서비스"""

    # 오류 카테고리 정의
    CATEGORIES = {
        "formula": ["formula_error", "circular_reference", "inefficient_formula"],
        "data": [
            "duplicate_data",
            "missing_data",
            "text_stored_as_number",
            "data_validation_error",
        ],
        "structure": [
            "merged_cells",
            "excessive_empty_rows",
            "empty_sheets",
            "duplicate_headers",
        ],
        "formatting": ["inconsistent_date_format", "mixed_currency_symbols"],
        "reference": ["broken_reference", "external_reference", "invalid_range"],
        "vba": ["vba_syntax_error", "vba_logic_error", "vba_security_risk"],
        "performance": [
            "large_formula_range",
            "volatile_functions",
            "array_formula_performance",
        ],
    }

    # 심각도 가중치
    SEVERITY_WEIGHTS = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    def classify_errors(self, errors: List[ExcelError]) -> Dict[str, List[ExcelError]]:
        """오류를 카테고리별로 분류"""
        classified = defaultdict(list)

        for error in errors:
            category = self._determine_category(error.type)
            classified[category].append(error)

        # 각 카테고리 내에서 심각도별 정렬
        for category in classified:
            classified[category] = self._sort_by_severity(classified[category])

        logger.info(
            f"오류 분류 완료: {len(errors)}개 오류를 {len(classified)}개 카테고리로 분류"
        )

        return dict(classified)

    def prioritize_errors(self, errors: List[ExcelError]) -> List[ExcelError]:
        """오류를 우선순위에 따라 정렬"""
        # 우선순위 점수 계산
        scored_errors = [
            (error, self._calculate_priority_score(error)) for error in errors
        ]

        # 점수 기준 내림차순 정렬
        scored_errors.sort(key=lambda x: x[1], reverse=True)

        # 정렬된 오류만 반환
        prioritized = [error for error, _ in scored_errors]

        logger.info(f"오류 우선순위 지정 완료: {len(errors)}개 오류")

        return prioritized

    def group_related_errors(self, errors: List[ExcelError]) -> List[List[ExcelError]]:
        """관련된 오류들을 그룹화"""
        groups = []
        processed = set()

        for error in errors:
            if error.id in processed:
                continue

            # 이 오류와 관련된 오류들 찾기
            group = [error]
            processed.add(error.id)

            for other in errors:
                if other.id not in processed and self._are_related(error, other):
                    group.append(other)
                    processed.add(other.id)

            if group:
                groups.append(group)

        logger.info(
            f"오류 그룹화 완료: {len(errors)}개 오류를 {len(groups)}개 그룹으로"
        )

        return groups

    def get_error_summary(self, errors: List[ExcelError]) -> Dict[str, Any]:
        """오류 요약 통계 생성"""
        summary = {
            "total": len(errors),
            "by_category": defaultdict(int),
            "by_severity": defaultdict(int),
            "by_sheet": defaultdict(int),
            "auto_fixable": 0,
            "critical_count": 0,
        }

        for error in errors:
            # 카테고리별 집계
            category = self._determine_category(error.type)
            summary["by_category"][category] += 1

            # 심각도별 집계
            summary["by_severity"][error.severity] += 1

            # 시트별 집계
            summary["by_sheet"][error.sheet] += 1

            # 자동 수정 가능 개수
            if error.is_auto_fixable:
                summary["auto_fixable"] += 1

            # 중요 오류 개수
            if error.severity == "critical":
                summary["critical_count"] += 1

        # defaultdict를 일반 dict로 변환
        summary["by_category"] = dict(summary["by_category"])
        summary["by_severity"] = dict(summary["by_severity"])
        summary["by_sheet"] = dict(summary["by_sheet"])

        # 추가 통계
        summary["auto_fix_rate"] = round(
            (
                (summary["auto_fixable"] / summary["total"] * 100)
                if summary["total"] > 0
                else 0
            ),
            2,
        )

        return summary

    def filter_errors_by_criteria(
        self,
        errors: List[ExcelError],
        severity: Optional[str] = None,
        category: Optional[str] = None,
        sheet: Optional[str] = None,
        auto_fixable_only: bool = False,
    ) -> List[ExcelError]:
        """조건에 따라 오류 필터링"""
        filtered = errors

        if severity:
            filtered = [e for e in filtered if e.severity == severity]

        if category:
            filtered = [
                e for e in filtered if self._determine_category(e.type) == category
            ]

        if sheet:
            filtered = [e for e in filtered if e.sheet == sheet]

        if auto_fixable_only:
            filtered = [e for e in filtered if e.is_auto_fixable]

        logger.debug(f"오류 필터링: {len(errors)}개 → {len(filtered)}개")

        return filtered

    # === Private 메서드 ===

    def _determine_category(self, error_type: str) -> str:
        """오류 타입으로부터 카테고리 결정"""
        error_type_lower = error_type.lower()

        for category, types in self.CATEGORIES.items():
            if any(t in error_type_lower for t in types):
                return category

        # 기본 카테고리
        if "error" in error_type_lower:
            return "general"
        return "other"

    def _calculate_priority_score(self, error: ExcelError) -> float:
        """오류의 우선순위 점수 계산"""
        # 기본 점수 = 심각도 가중치
        score = self.SEVERITY_WEIGHTS.get(error.severity, 1)

        # 자동 수정 가능하면 점수 증가
        if error.is_auto_fixable:
            score += 0.5

        # 신뢰도가 높으면 점수 증가
        score += error.confidence * 0.3

        # 특정 오류 타입에 가중치
        if "circular_reference" in error.type.lower():
            score += 2
        elif "security" in error.type.lower():
            score += 1.5

        return score

    def _sort_by_severity(self, errors: List[ExcelError]) -> List[ExcelError]:
        """심각도별로 정렬"""
        return sorted(
            errors,
            key=lambda e: (
                -self.SEVERITY_WEIGHTS.get(e.severity, 0),  # 심각도 내림차순
                e.sheet,  # 시트명 오름차순
                e.cell,  # 셀 주소 오름차순
            ),
        )

    def _are_related(self, error1: ExcelError, error2: ExcelError) -> bool:
        """두 오류가 관련되어 있는지 확인"""
        # 같은 시트의 인접한 셀
        if error1.sheet == error2.sheet:
            # 셀 주소 파싱
            col1, row1 = self._parse_cell(error1.cell)
            col2, row2 = self._parse_cell(error2.cell)

            # 인접한 셀인지 확인 (상하좌우)
            if abs(col1 - col2) <= 1 and abs(row1 - row2) <= 1:
                return True

        # 같은 수식 참조
        if error1.formula and error2.formula:
            if error1.formula == error2.formula:
                return True

        # 같은 타입의 오류가 연속된 행/열에 있는 경우
        if error1.type == error2.type and error1.sheet == error2.sheet:
            col1, row1 = self._parse_cell(error1.cell)
            col2, row2 = self._parse_cell(error2.cell)

            # 같은 열의 연속된 행
            if col1 == col2 and abs(row1 - row2) == 1:
                return True

            # 같은 행의 연속된 열
            if row1 == row2 and abs(col1 - col2) == 1:
                return True

        return False

    def _parse_cell(self, cell_ref: str) -> Tuple[int, int]:
        """셀 주소를 열/행 인덱스로 파싱"""
        import re

        match = re.match(r"([A-Z]+)(\d+)", cell_ref)
        if match:
            col_str = match.group(1)
            row = int(match.group(2))

            # 열 문자를 숫자로 변환
            col = 0
            for char in col_str:
                col = col * 26 + (ord(char) - ord("A") + 1)

            return col, row

        return 0, 0
