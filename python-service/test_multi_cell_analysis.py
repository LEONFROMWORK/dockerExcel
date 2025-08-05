#!/usr/bin/env python3
"""
Multi-Cell Analysis Test Script
멀티 셀 분석 기능 테스트
"""

import asyncio
import json
from app.services.detection.multi_cell_analyzer import MultiCellAnalyzer


async def test_multi_cell_analysis():
    """멀티 셀 분석 테스트"""

    # 테스트 데이터
    test_cells = [
        {"sheet": "Sheet1", "address": "A1", "value": 100, "formula": None},
        {"sheet": "Sheet1", "address": "A2", "value": 200, "formula": None},
        {"sheet": "Sheet1", "address": "A3", "value": "#DIV/0!", "formula": "=A1/0"},
        {"sheet": "Sheet1", "address": "A4", "value": 300, "formula": "=A1+A2"},
    ]

    # MultiCellAnalyzer 직접 테스트
    analyzer = MultiCellAnalyzer()

    # 패턴 분석 테스트
    patterns = await analyzer.analyze_cell_patterns(test_cells, [])
    print("패턴 분석 결과:")
    print(json.dumps(patterns, indent=2, ensure_ascii=False))

    # 공간 패턴 테스트
    addresses = ["A1", "A2", "A3", "A4"]
    print(f"\n연속된 범위 확인: {analyzer._check_continuous_range(addresses)}")
    print(f"같은 열 확인: {analyzer._check_same_column(addresses)}")
    print(f"같은 행 확인: {analyzer._check_same_row(addresses)}")

    # 다른 패턴 테스트
    addresses2 = ["A1", "B1", "C1", "D1"]
    print(f"\n행 방향 연속성: {analyzer._check_continuous_range(addresses2)}")
    print(f"같은 행 확인: {analyzer._check_same_row(addresses2)}")

    # 교차 셀 문제 감지 테스트
    formula_cells = [
        {"address": "A1", "formula": "=B1+1"},
        {"address": "B1", "formula": "=A1*2"},  # 순환 참조 가능성
    ]
    issues = await analyzer.detect_cross_cell_issues(formula_cells, None)
    print(f"\n교차 셀 문제: {json.dumps(issues, indent=2, ensure_ascii=False)}")

    print("\n테스트 완료!")


if __name__ == "__main__":
    asyncio.run(test_multi_cell_analysis())
