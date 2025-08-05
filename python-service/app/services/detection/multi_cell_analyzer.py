"""
Multi-Cell Analysis Service
멀티 셀 분석 전문 서비스
"""

from typing import List, Dict, Any
from app.core.interfaces import ExcelError
import re
import logging

logger = logging.getLogger(__name__)


class MultiCellAnalyzer:
    """멀티 셀 분석 전문 클래스"""

    # 셀 주소 패턴 컴파일 (성능 최적화)
    CELL_PATTERN = re.compile(r"([A-Z]+)(\d+)")

    async def analyze_cell_patterns(
        self, cells: List[Dict[str, Any]], errors: List[ExcelError]
    ) -> Dict[str, Any]:
        """셀 패턴 분석"""
        patterns = {
            "error_patterns": {},
            "formula_patterns": {},
            "value_patterns": {},
            "spatial_patterns": {},
        }

        # 오류 패턴 분석
        error_types = {}
        for error in errors:
            error_types[error.type] = error_types.get(error.type, 0) + 1
        patterns["error_patterns"] = {
            "types": error_types,
            "most_common": (
                max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
            ),
        }

        # 수식 패턴 분석
        formulas = [c.get("formula") for c in cells if c.get("formula")]
        if formulas:
            # 공통 함수 추출
            common_functions = {}
            for formula in formulas:
                if formula and isinstance(formula, str):
                    # 함수명 추출 (간단한 정규식)
                    functions = re.findall(r"([A-Z]+)\s*\(", formula)
                    for func in functions:
                        common_functions[func] = common_functions.get(func, 0) + 1

            patterns["formula_patterns"] = {
                "total_formulas": len(formulas),
                "common_functions": common_functions,
                "formula_rate": len(formulas) / len(cells) if cells else 0,
            }

        # 값 패턴 분석
        values = [c.get("value") for c in cells if c.get("value") is not None]
        if values:
            numeric_values = [v for v in values if isinstance(v, (int, float))]
            patterns["value_patterns"] = {
                "total_values": len(values),
                "numeric_count": len(numeric_values),
                "empty_count": sum(1 for v in values if v == "" or v is None),
                "error_values": sum(
                    1 for v in values if isinstance(v, str) and v.startswith("#")
                ),
            }

        # 공간 패턴 분석 (연속된 셀인지 확인)
        if len(cells) > 1:
            addresses = [c["address"] for c in cells]
            patterns["spatial_patterns"] = {
                "is_continuous": self._check_continuous_range(addresses),
                "is_same_row": self._check_same_row(addresses),
                "is_same_column": self._check_same_column(addresses),
            }

        return patterns

    async def detect_cross_cell_issues(
        self, cells: List[Dict[str, Any]], workbook: Any
    ) -> List[Dict[str, Any]]:
        """교차 셀 문제 감지 (의존성, 일관성 등)"""
        issues = []

        # 수식 의존성 검사
        formula_cells = [c for c in cells if c.get("formula")]
        for i, cell1 in enumerate(formula_cells):
            for cell2 in formula_cells[i + 1 :]:
                # 서로 참조하는지 확인
                if cell1["address"] in str(cell2.get("formula", "")):
                    issues.append(
                        {
                            "type": "dependency",
                            "cells": [cell1["address"], cell2["address"]],
                            "message": f"{cell2['address']}가 {cell1['address']}를 참조합니다",
                        }
                    )

        # 데이터 타입 일관성 검사
        if self._check_same_column([c["address"] for c in cells]):
            value_types = [type(c.get("value")).__name__ for c in cells]
            if len(set(value_types)) > 1:
                issues.append(
                    {
                        "type": "inconsistency",
                        "cells": [c["address"] for c in cells],
                        "message": "같은 열의 데이터 타입이 일치하지 않습니다",
                    }
                )

        return issues

    def create_multi_cell_summary(
        self, cell_results: List[Dict], patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """멀티 셀 분석 요약"""
        total_cells = len(cell_results)
        cells_with_errors = sum(1 for c in cell_results if c.get("has_errors"))

        summary = {
            "total_cells_analyzed": total_cells,
            "cells_with_errors": cells_with_errors,
            "error_rate": cells_with_errors / total_cells if total_cells > 0 else 0,
            "patterns_detected": [],
        }

        # 감지된 패턴 요약
        if patterns.get("formula_patterns", {}).get("formula_rate", 0) > 0.7:
            summary["patterns_detected"].append("수식 위주 데이터")

        if patterns.get("spatial_patterns", {}).get("is_continuous"):
            summary["patterns_detected"].append("연속된 셀 범위")

        if patterns.get("error_patterns", {}).get("most_common"):
            summary["patterns_detected"].append(
                f"주요 오류 타입: {patterns['error_patterns']['most_common']}"
            )

        return summary

    def _check_continuous_range(self, addresses: List[str]) -> bool:
        """연속된 셀 범위인지 확인"""
        if len(addresses) < 2:
            return False

        # 주소를 행/열로 변환
        coords = []
        for addr in addresses:
            match = self.CELL_PATTERN.match(addr)
            if match:
                col = self._column_to_number(match.group(1))
                row = int(match.group(2))
                coords.append((row, col))

        if not coords:
            return False

        coords.sort()

        # 연속성 확인 (행 또는 열이 연속적인지)
        rows = [c[0] for c in coords]
        cols = [c[1] for c in coords]

        # 같은 행에서 열이 연속적인지
        if len(set(rows)) == 1:
            return all(cols[i] + 1 == cols[i + 1] for i in range(len(cols) - 1))

        # 같은 열에서 행이 연속적인지
        if len(set(cols)) == 1:
            return all(rows[i] + 1 == rows[i + 1] for i in range(len(rows) - 1))

        return False

    def _check_same_row(self, addresses: List[str]) -> bool:
        """같은 행인지 확인"""
        rows = []
        for addr in addresses:
            match = self.CELL_PATTERN.match(addr)
            if match:
                rows.append(int(match.group(2)))
        return len(set(rows)) == 1 if rows else False

    def _check_same_column(self, addresses: List[str]) -> bool:
        """같은 열인지 확인"""
        cols = []
        for addr in addresses:
            match = self.CELL_PATTERN.match(addr)
            if match:
                cols.append(match.group(1))
        return len(set(cols)) == 1 if cols else False

    def _column_to_number(self, column: str) -> int:
        """열 문자를 숫자로 변환"""
        result = 0
        for char in column:
            result = result * 26 + (ord(char) - ord("A") + 1)
        return result
