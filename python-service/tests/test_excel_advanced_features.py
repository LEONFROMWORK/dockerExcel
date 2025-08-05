"""
Excel 고급 기능 테스트
Test Excel Advanced Features (Charts, Pivot Tables)
"""

import pytest
import tempfile
import pandas as pd
import os
from datetime import datetime, timedelta
import numpy as np

from app.services.excel_chart_analyzer import excel_chart_analyzer
from app.services.excel_pivot_analyzer import excel_pivot_analyzer


class TestExcelChartAnalyzer:
    """Excel 차트 분석기 테스트"""

    @pytest.fixture
    def sample_excel_file(self):
        """테스트용 Excel 파일 생성"""

        # 샘플 데이터 생성
        np.random.seed(42)
        data = {
            "월": ["1월", "2월", "3월", "4월", "5월", "6월"] * 5,
            "제품": ["A"] * 6 + ["B"] * 6 + ["C"] * 6 + ["D"] * 6 + ["E"] * 6,
            "판매량": np.random.randint(100, 1000, 30),
            "매출": np.random.randint(10000, 100000, 30),
            "이익률": np.random.uniform(0.1, 0.3, 30),
            "날짜": [
                datetime(2024, i % 12 + 1, 1) + timedelta(days=j * 30)
                for i in range(30)
                for j in range(1)
            ][:30],
        }

        df = pd.DataFrame(data)

        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            df.to_excel(tmp_file.name, sheet_name="Sales_Data", index=False)
            return tmp_file.name

    def test_suggest_optimal_charts(self, sample_excel_file):
        """최적 차트 제안 테스트"""

        try:
            suggestions = excel_chart_analyzer.suggest_optimal_charts(sample_excel_file)

            # 기본 검증
            assert "total_suggestions" in suggestions
            assert "suggestions_by_sheet" in suggestions
            assert suggestions["total_suggestions"] > 0

            # 시트별 제안 확인
            sheet_suggestions = suggestions["suggestions_by_sheet"].get(
                "Sales_Data", {}
            )
            assert "suggested_charts" in sheet_suggestions

            suggested_charts = sheet_suggestions["suggested_charts"]
            assert len(suggested_charts) > 0

            # 첫 번째 제안 검증
            first_suggestion = suggested_charts[0]
            required_fields = ["type", "title", "data_range", "confidence", "reason"]
            for field in required_fields:
                assert field in first_suggestion

            # 차트 타입이 유효한지 확인
            valid_chart_types = ["column", "bar", "line", "pie", "scatter", "area"]
            assert first_suggestion["type"] in valid_chart_types

            print(f"✅ 차트 제안 테스트 성공: {len(suggested_charts)}개 제안")

        finally:
            if os.path.exists(sample_excel_file):
                os.unlink(sample_excel_file)

    def test_create_chart(self, sample_excel_file):
        """차트 생성 테스트"""

        try:
            # 차트 설정
            chart_config = {
                "sheet_name": "Sales_Data",
                "chart_type": "column",
                "data_range": "A1:C10",
                "title": "Test Chart",
                "position": "E2",
                "x_axis_title": "Month",
                "y_axis_title": "Sales",
            }

            result = excel_chart_analyzer.create_chart(sample_excel_file, chart_config)

            # 결과 검증
            assert result["status"] == "success"
            assert "output_file" in result
            assert os.path.exists(result["output_file"])

            print("✅ 차트 생성 테스트 성공")

            # 생성된 파일 정리
            if os.path.exists(result["output_file"]):
                os.unlink(result["output_file"])

        finally:
            if os.path.exists(sample_excel_file):
                os.unlink(sample_excel_file)

    def test_auto_generate_charts(self, sample_excel_file):
        """자동 차트 생성 테스트"""

        try:
            result = excel_chart_analyzer.auto_generate_charts(
                sample_excel_file, max_charts_per_sheet=2
            )

            # 결과 검증
            assert result["status"] == "success"
            assert "generated_charts" in result
            assert "total_charts_generated" in result
            assert result["total_charts_generated"] > 0

            print(
                f"✅ 자동 차트 생성 테스트 성공: {result['total_charts_generated']}개 생성"
            )

            # 생성된 파일 정리
            if "output_file" in result and os.path.exists(result["output_file"]):
                os.unlink(result["output_file"])

        finally:
            if os.path.exists(sample_excel_file):
                os.unlink(sample_excel_file)


class TestExcelPivotAnalyzer:
    """Excel 피벗테이블 분석기 테스트"""

    @pytest.fixture
    def sample_excel_file(self):
        """테스트용 Excel 파일 생성"""

        # 더 복잡한 샘플 데이터 생성
        np.random.seed(42)
        data = {
            "지역": ["서울", "부산", "대구", "인천", "광주"] * 20,
            "제품카테고리": ["전자", "의류", "식품", "도서", "스포츠"] * 20,
            "판매원": [f"직원{i%10+1}" for i in range(100)],
            "판매량": np.random.randint(10, 500, 100),
            "단가": np.random.randint(1000, 50000, 100),
            "할인율": np.random.uniform(0, 0.2, 100),
            "월": [f"{i%12+1}월" for i in range(100)],
            "요일": ["월", "화", "수", "목", "금", "토", "일"] * 14 + ["월", "화"],
        }

        df = pd.DataFrame(data)
        df["매출"] = df["판매량"] * df["단가"] * (1 - df["할인율"])

        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            df.to_excel(tmp_file.name, sheet_name="Sales_Data", index=False)
            return tmp_file.name

    def test_suggest_optimal_pivots(self, sample_excel_file):
        """최적 피벗테이블 제안 테스트"""

        try:
            suggestions = excel_pivot_analyzer.suggest_optimal_pivots(sample_excel_file)

            # 기본 검증
            assert "total_suggestions" in suggestions
            assert "suggestions_by_sheet" in suggestions
            assert suggestions["total_suggestions"] > 0

            # 시트별 제안 확인
            sheet_suggestions = suggestions["suggestions_by_sheet"].get(
                "Sales_Data", {}
            )
            assert "suggested_pivots" in sheet_suggestions

            suggested_pivots = sheet_suggestions["suggested_pivots"]
            assert len(suggested_pivots) > 0

            # 첫 번째 제안 검증
            first_suggestion = suggested_pivots[0]
            required_fields = [
                "type",
                "title",
                "row_fields",
                "value_fields",
                "aggfunc",
                "confidence",
                "reason",
            ]
            for field in required_fields:
                assert field in first_suggestion

            # 필드가 리스트인지 확인
            assert isinstance(first_suggestion["row_fields"], list)
            assert isinstance(first_suggestion["value_fields"], list)
            assert len(first_suggestion["row_fields"]) > 0
            assert len(first_suggestion["value_fields"]) > 0

            print(f"✅ 피벗테이블 제안 테스트 성공: {len(suggested_pivots)}개 제안")

        finally:
            if os.path.exists(sample_excel_file):
                os.unlink(sample_excel_file)

    def test_create_pivot_table(self, sample_excel_file):
        """피벗테이블 생성 테스트"""

        try:
            # 피벗테이블 설정
            pivot_config = {
                "source_sheet": "Sales_Data",
                "pivot_sheet": "Region_Summary",
                "row_fields": ["지역"],
                "column_fields": ["제품카테고리"],
                "value_fields": ["매출"],
                "aggfunc": "sum",
                "show_totals": True,
            }

            result = excel_pivot_analyzer.create_pivot_table(
                sample_excel_file, pivot_config
            )

            # 결과 검증
            assert result["status"] == "success"
            assert "output_file" in result
            assert os.path.exists(result["output_file"])
            assert "pivot_summary" in result

            # 피벗테이블 요약 정보 확인
            pivot_summary = result["pivot_summary"]
            assert "rows" in pivot_summary
            assert "columns" in pivot_summary
            assert pivot_summary["rows"] > 0
            assert pivot_summary["columns"] > 0

            print("✅ 피벗테이블 생성 테스트 성공")

            # 생성된 파일 정리
            if os.path.exists(result["output_file"]):
                os.unlink(result["output_file"])

        finally:
            if os.path.exists(sample_excel_file):
                os.unlink(sample_excel_file)

    def test_create_cross_tabulation(self, sample_excel_file):
        """교차표 생성 테스트"""

        try:
            # 교차표 설정
            crosstab_config = {
                "source_sheet": "Sales_Data",
                "row_field": "지역",
                "col_field": "제품카테고리",
                "value_field": "매출",
                "aggfunc": "sum",
                "show_totals": True,
            }

            result = excel_pivot_analyzer.create_cross_tabulation(
                sample_excel_file, crosstab_config
            )

            # 결과 검증
            assert result["status"] == "success"
            assert "output_file" in result
            assert os.path.exists(result["output_file"])
            assert "crosstab_summary" in result

            # 교차표 요약 정보 확인
            crosstab_summary = result["crosstab_summary"]
            assert "rows" in crosstab_summary
            assert "columns" in crosstab_summary
            assert crosstab_summary["rows"] > 0
            assert crosstab_summary["columns"] > 0

            print("✅ 교차표 생성 테스트 성공")

            # 생성된 파일 정리
            if os.path.exists(result["output_file"]):
                os.unlink(result["output_file"])

        finally:
            if os.path.exists(sample_excel_file):
                os.unlink(sample_excel_file)

    def test_auto_generate_pivots(self, sample_excel_file):
        """자동 피벗테이블 생성 테스트"""

        try:
            result = excel_pivot_analyzer.auto_generate_pivots(
                sample_excel_file, max_pivots_per_sheet=2
            )

            # 결과 검증
            assert result["status"] == "success"
            assert "generated_pivots" in result
            assert "total_pivots_generated" in result
            assert result["total_pivots_generated"] > 0

            print(
                f"✅ 자동 피벗테이블 생성 테스트 성공: {result['total_pivots_generated']}개 생성"
            )

            # 생성된 파일 정리
            if "final_output_file" in result and os.path.exists(
                result["final_output_file"]
            ):
                os.unlink(result["final_output_file"])

        finally:
            if os.path.exists(sample_excel_file):
                os.unlink(sample_excel_file)


class TestIntegratedFeatures:
    """통합 기능 테스트"""

    @pytest.fixture
    def comprehensive_excel_file(self):
        """종합 테스트용 Excel 파일 생성"""

        # 실제 비즈니스 시나리오와 유사한 데이터
        np.random.seed(42)

        # 판매 데이터
        sales_data = {
            "날짜": pd.date_range("2024-01-01", periods=365, freq="D"),
            "지역": np.random.choice(["서울", "경기", "부산", "대구", "인천"], 365),
            "제품": np.random.choice(
                ["노트북", "태블릿", "스마트폰", "스마트워치", "이어폰"], 365
            ),
            "판매원": np.random.choice([f"직원{i}" for i in range(1, 21)], 365),
            "판매량": np.random.randint(1, 50, 365),
            "단가": np.random.choice([500000, 800000, 1200000, 300000, 150000], 365),
            "고객만족도": np.random.uniform(3.0, 5.0, 365),
        }

        df_sales = pd.DataFrame(sales_data)
        df_sales["매출"] = df_sales["판매량"] * df_sales["단가"]
        df_sales["월"] = df_sales["날짜"].dt.month
        df_sales["분기"] = df_sales["날짜"].dt.quarter

        # 여러 시트로 구성된 Excel 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            with pd.ExcelWriter(tmp_file.name, engine="openpyxl") as writer:
                df_sales.to_excel(writer, sheet_name="Sales", index=False)

                # 월별 요약 시트 추가
                monthly_summary = (
                    df_sales.groupby("월")
                    .agg({"매출": "sum", "판매량": "sum", "고객만족도": "mean"})
                    .reset_index()
                )
                monthly_summary.to_excel(
                    writer, sheet_name="Monthly_Summary", index=False
                )

                # 제품별 요약 시트 추가
                product_summary = (
                    df_sales.groupby("제품")
                    .agg({"매출": "sum", "판매량": "sum", "고객만족도": "mean"})
                    .reset_index()
                )
                product_summary.to_excel(
                    writer, sheet_name="Product_Summary", index=False
                )

            return tmp_file.name

    def test_comprehensive_analysis(self, comprehensive_excel_file):
        """종합 분석 테스트"""

        try:
            # 차트 제안 분석
            chart_suggestions = excel_chart_analyzer.suggest_optimal_charts(
                comprehensive_excel_file
            )
            assert chart_suggestions["total_suggestions"] > 0

            # 피벗테이블 제안 분석
            pivot_suggestions = excel_pivot_analyzer.suggest_optimal_pivots(
                comprehensive_excel_file
            )
            assert pivot_suggestions["total_suggestions"] > 0

            # 각 시트별로 제안이 있는지 확인
            expected_sheets = ["Sales", "Monthly_Summary", "Product_Summary"]
            for sheet in expected_sheets:
                if sheet in chart_suggestions["suggestions_by_sheet"]:
                    sheet_chart_suggestions = chart_suggestions["suggestions_by_sheet"][
                        sheet
                    ]
                    assert "suggested_charts" in sheet_chart_suggestions

                if sheet in pivot_suggestions["suggestions_by_sheet"]:
                    sheet_pivot_suggestions = pivot_suggestions["suggestions_by_sheet"][
                        sheet
                    ]
                    assert "suggested_pivots" in sheet_pivot_suggestions

            print("✅ 종합 분석 테스트 성공")
            print(f"   - 차트 제안: {chart_suggestions['total_suggestions']}개")
            print(f"   - 피벗테이블 제안: {pivot_suggestions['total_suggestions']}개")

        finally:
            if os.path.exists(comprehensive_excel_file):
                os.unlink(comprehensive_excel_file)


if __name__ == "__main__":
    # 간단한 테스트 실행
    import sys

    try:
        # 차트 분석기 테스트
        test_chart = TestExcelChartAnalyzer()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            # 샘플 데이터 생성
            data = pd.DataFrame(
                {
                    "월": ["1월", "2월", "3월", "4월", "5월"],
                    "판매량": [100, 150, 120, 180, 200],
                    "매출": [10000, 15000, 12000, 18000, 20000],
                }
            )
            data.to_excel(tmp.name, index=False)

            # 차트 제안 테스트
            suggestions = excel_chart_analyzer.suggest_optimal_charts(tmp.name)
            print(f"차트 제안 개수: {suggestions.get('total_suggestions', 0)}")

            os.unlink(tmp.name)

        # 피벗테이블 분석기 테스트
        test_pivot = TestExcelPivotAnalyzer()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            # 샘플 데이터 생성
            data = pd.DataFrame(
                {
                    "지역": ["서울", "부산", "대구"] * 10,
                    "제품": ["A", "B", "C"] * 10,
                    "판매량": np.random.randint(50, 200, 30),
                    "매출": np.random.randint(5000, 20000, 30),
                }
            )
            data.to_excel(tmp.name, index=False)

            # 피벗테이블 제안 테스트
            suggestions = excel_pivot_analyzer.suggest_optimal_pivots(tmp.name)
            print(f"피벗테이블 제안 개수: {suggestions.get('total_suggestions', 0)}")

            os.unlink(tmp.name)

        print("✅ 모든 기본 테스트 통과")

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        sys.exit(1)
