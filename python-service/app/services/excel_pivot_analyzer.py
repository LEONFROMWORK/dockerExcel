"""
Excel 피벗테이블 분석 및 생성 서비스
Excel Pivot Table Analysis and Generation Service
"""

import logging
import pandas as pd
import openpyxl

# from openpyxl.pivot.table import PivotTable
# from openpyxl.pivot.cache import PivotCache
# from openpyxl.pivot.fields import PivotField
# Note: PivotTable features temporarily disabled due to openpyxl compatibility
from typing import Dict, List, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class ExcelPivotAnalyzer:
    """Excel 피벗테이블 분석 및 생성 관리자"""

    def __init__(self):
        self.aggregation_functions = {
            "sum": "Sum",
            "count": "Count",
            "average": "Average",
            "max": "Max",
            "min": "Min",
            "std": "StdDev",
            "var": "Var",
        }

    def analyze_existing_pivots(self, file_path: str) -> Dict[str, Any]:
        """기존 피벗테이블 분석"""

        try:
            workbook = openpyxl.load_workbook(file_path, keep_vba=True, data_only=False)
            pivot_analysis = {
                "total_pivots": 0,
                "pivots_by_sheet": {},
                "pivot_details": [],
            }

            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_pivots = []

                # 시트의 모든 피벗테이블 분석
                if hasattr(sheet, "_pivots"):
                    for pivot in sheet._pivots:
                        pivot_info = {
                            "pivot_name": getattr(
                                pivot, "name", f"Pivot_{len(sheet_pivots) + 1}"
                            ),
                            "location": (
                                str(pivot.location)
                                if hasattr(pivot, "location")
                                else "Unknown"
                            ),
                            "source_range": self._extract_pivot_source_range(pivot),
                            "row_fields": self._extract_pivot_fields(pivot, "row"),
                            "column_fields": self._extract_pivot_fields(
                                pivot, "column"
                            ),
                            "data_fields": self._extract_pivot_fields(pivot, "data"),
                            "filter_fields": self._extract_pivot_fields(
                                pivot, "filter"
                            ),
                        }

                        sheet_pivots.append(pivot_info)
                        pivot_analysis["pivot_details"].append(
                            {**pivot_info, "sheet": sheet_name}
                        )

                pivot_analysis["pivots_by_sheet"][sheet_name] = {
                    "count": len(sheet_pivots),
                    "pivots": sheet_pivots,
                }
                pivot_analysis["total_pivots"] += len(sheet_pivots)

            # 피벗테이블 품질 및 개선 제안
            pivot_analysis["recommendations"] = self._generate_pivot_recommendations(
                pivot_analysis["pivot_details"]
            )

            return pivot_analysis

        except Exception as e:
            logger.error(f"피벗테이블 분석 중 오류: {str(e)}")
            return {
                "error": str(e),
                "total_pivots": 0,
                "pivots_by_sheet": {},
                "pivot_details": [],
            }

    def suggest_optimal_pivots(
        self, file_path: str, sheet_name: str = None
    ) -> Dict[str, Any]:
        """데이터에 최적화된 피벗테이블 제안"""

        try:
            # Excel 파일에서 데이터 읽기
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                sheets_to_analyze = [(sheet_name, df)]
            else:
                excel_data = pd.read_excel(file_path, sheet_name=None)
                sheets_to_analyze = list(excel_data.items())

            suggestions = {"total_suggestions": 0, "suggestions_by_sheet": {}}

            for sheet_name, df in sheets_to_analyze:
                sheet_suggestions = self._analyze_data_for_pivot_suggestions(
                    df, sheet_name
                )
                suggestions["suggestions_by_sheet"][sheet_name] = sheet_suggestions
                suggestions["total_suggestions"] += len(
                    sheet_suggestions.get("suggested_pivots", [])
                )

            return suggestions

        except Exception as e:
            logger.error(f"피벗테이블 제안 분석 중 오류: {str(e)}")
            return {"error": str(e), "total_suggestions": 0, "suggestions_by_sheet": {}}

    def create_pivot_table(
        self, file_path: str, pivot_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """pandas를 사용한 피벗테이블 생성 (openpyxl 제한 때문)"""

        try:
            # 설정 파라미터 추출
            source_sheet = pivot_config.get("source_sheet")
            pivot_sheet = pivot_config.get("pivot_sheet", f"{source_sheet}_Pivot")

            # 데이터 읽기
            df = pd.read_excel(file_path, sheet_name=source_sheet)

            # 피벗테이블 설정
            row_fields = pivot_config.get("row_fields", [])
            column_fields = pivot_config.get("column_fields", [])
            value_fields = pivot_config.get("value_fields", [])
            aggfunc = pivot_config.get("aggfunc", "sum")

            # 필드 유효성 검사
            missing_fields = []
            all_fields = row_fields + column_fields + value_fields
            for field in all_fields:
                if field not in df.columns:
                    missing_fields.append(field)

            if missing_fields:
                return {
                    "status": "error",
                    "message": f'다음 필드를 찾을 수 없습니다: {", ".join(missing_fields)}',
                }

            # pandas 피벗테이블 생성
            pivot_table = pd.pivot_table(
                df,
                values=value_fields if value_fields else None,
                index=row_fields if row_fields else None,
                columns=column_fields if column_fields else None,
                aggfunc=aggfunc,
                fill_value=0,
                margins=pivot_config.get("show_totals", True),
            )

            # 기존 워크북 로드
            with pd.ExcelWriter(
                file_path.replace(".xlsx", "_with_pivot.xlsx"),
                engine="openpyxl",
                mode="a",
            ) as writer:

                # 원본 데이터 복사
                original_data = pd.read_excel(file_path, sheet_name=None)
                for sheet_name, sheet_df in original_data.items():
                    sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

                # 새 피벗테이블 시트 추가
                pivot_table.to_excel(writer, sheet_name=pivot_sheet)

            return {
                "status": "success",
                "message": "피벗테이블이 성공적으로 생성되었습니다",
                "pivot_sheet": pivot_sheet,
                "source_sheet": source_sheet,
                "row_fields": row_fields,
                "column_fields": column_fields,
                "value_fields": value_fields,
                "aggfunc": aggfunc,
                "output_file": file_path.replace(".xlsx", "_with_pivot.xlsx"),
                "pivot_summary": {
                    "rows": len(pivot_table.index),
                    "columns": len(pivot_table.columns),
                    "total_cells": pivot_table.size,
                    "non_zero_cells": (pivot_table != 0).sum().sum(),
                },
            }

        except Exception as e:
            logger.error(f"피벗테이블 생성 중 오류: {str(e)}")
            return {"status": "error", "message": f"피벗테이블 생성 실패: {str(e)}"}

    def auto_generate_pivots(
        self, file_path: str, max_pivots_per_sheet: int = 2
    ) -> Dict[str, Any]:
        """데이터를 기반으로 자동으로 피벗테이블 생성"""

        try:
            # 최적 피벗테이블 제안 받기
            suggestions = self.suggest_optimal_pivots(file_path)

            generated_pivots = []

            for sheet_name, sheet_suggestions in suggestions[
                "suggestions_by_sheet"
            ].items():
                suggested_pivots = sheet_suggestions.get("suggested_pivots", [])[
                    :max_pivots_per_sheet
                ]

                for i, pivot_suggestion in enumerate(suggested_pivots):
                    pivot_config = {
                        "source_sheet": sheet_name,
                        "pivot_sheet": f"{sheet_name}_Pivot_{i+1}",
                        "row_fields": pivot_suggestion["row_fields"],
                        "column_fields": pivot_suggestion.get("column_fields", []),
                        "value_fields": pivot_suggestion["value_fields"],
                        "aggfunc": pivot_suggestion.get("aggfunc", "sum"),
                        "show_totals": True,
                    }

                    # 개별 피벗테이블 생성
                    pivot_result = self.create_pivot_table(file_path, pivot_config)
                    if pivot_result["status"] == "success":
                        generated_pivots.append(
                            {
                                **pivot_result,
                                "suggestion_reason": pivot_suggestion["reason"],
                            }
                        )
                        # 다음 피벗테이블을 위해 새로 생성된 파일 사용
                        file_path = pivot_result["output_file"]

            return {
                "status": "success",
                "message": f"{len(generated_pivots)}개의 피벗테이블이 자동 생성되었습니다",
                "generated_pivots": generated_pivots,
                "final_output_file": file_path,
                "total_pivots_generated": len(generated_pivots),
            }

        except Exception as e:
            logger.error(f"자동 피벗테이블 생성 중 오류: {str(e)}")
            return {
                "status": "error",
                "message": f"자동 피벗테이블 생성 실패: {str(e)}",
            }

    def create_cross_tabulation(
        self, file_path: str, crosstab_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """교차표 생성"""

        try:
            source_sheet = crosstab_config.get("source_sheet")
            df = pd.read_excel(file_path, sheet_name=source_sheet)

            row_field = crosstab_config.get("row_field")
            col_field = crosstab_config.get("col_field")
            value_field = crosstab_config.get("value_field")

            if not all([row_field, col_field]):
                return {
                    "status": "error",
                    "message": "row_field와 col_field는 필수입니다",
                }

            # 교차표 생성
            if value_field and value_field in df.columns:
                crosstab = pd.crosstab(
                    df[row_field],
                    df[col_field],
                    values=df[value_field],
                    aggfunc=crosstab_config.get("aggfunc", "sum"),
                    margins=crosstab_config.get("show_totals", True),
                )
            else:
                crosstab = pd.crosstab(
                    df[row_field],
                    df[col_field],
                    margins=crosstab_config.get("show_totals", True),
                )

            # 결과를 새 시트에 저장
            output_file = file_path.replace(".xlsx", "_with_crosstab.xlsx")
            with pd.ExcelWriter(output_file, engine="openpyxl", mode="a") as writer:
                # 원본 데이터 복사
                original_data = pd.read_excel(file_path, sheet_name=None)
                for sheet_name, sheet_df in original_data.items():
                    sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

                # 교차표 추가
                crosstab_sheet = f"{source_sheet}_CrossTab"
                crosstab.to_excel(writer, sheet_name=crosstab_sheet)

            return {
                "status": "success",
                "message": "교차표가 성공적으로 생성되었습니다",
                "crosstab_sheet": crosstab_sheet,
                "row_field": row_field,
                "col_field": col_field,
                "value_field": value_field,
                "output_file": output_file,
                "crosstab_summary": {
                    "rows": len(crosstab.index),
                    "columns": len(crosstab.columns),
                    "total_entries": crosstab.size,
                },
            }

        except Exception as e:
            logger.error(f"교차표 생성 중 오류: {str(e)}")
            return {"status": "error", "message": f"교차표 생성 실패: {str(e)}"}

    def _extract_pivot_source_range(self, pivot) -> Optional[str]:
        """피벗테이블의 소스 데이터 범위 추출"""
        try:
            if hasattr(pivot, "cache") and hasattr(pivot.cache, "worksheetSource"):
                ws_source = pivot.cache.worksheetSource
                if hasattr(ws_source, "ref"):
                    return str(ws_source.ref)
            return None
        except Exception:
            return None

    def _extract_pivot_fields(self, pivot, field_type: str) -> List[str]:
        """피벗테이블에서 특정 유형의 필드 추출"""
        try:
            fields = []
            if hasattr(pivot, field_type + "Fields"):
                field_list = getattr(pivot, field_type + "Fields")
                for field in field_list:
                    if hasattr(field, "name"):
                        fields.append(field.name)
            return fields
        except Exception:
            return []

    def _generate_pivot_recommendations(self, pivot_details: List[Dict]) -> List[str]:
        """피벗테이블 개선 권장사항 생성"""
        recommendations = []

        if len(pivot_details) == 0:
            recommendations.append(
                "데이터 요약 분석을 위해 피벗테이블 생성을 고려해보세요"
            )

        # 복잡도가 낮은 피벗테이블 확인
        simple_pivots = [
            pivot
            for pivot in pivot_details
            if len(pivot.get("row_fields", [])) + len(pivot.get("column_fields", []))
            <= 2
        ]

        if len(simple_pivots) > len(pivot_details) * 0.7:
            recommendations.append(
                "더 복잡한 다차원 분석을 위해 추가 필드를 활용할 수 있습니다"
            )

        # 데이터 필드가 없는 피벗테이블
        pivots_without_data = [
            pivot for pivot in pivot_details if not pivot.get("data_fields")
        ]

        if pivots_without_data:
            recommendations.append(
                f"{len(pivots_without_data)}개의 피벗테이블에 집계 데이터 필드 추가를 고려해보세요"
            )

        return recommendations

    def _analyze_data_for_pivot_suggestions(
        self, df: pd.DataFrame, sheet_name: str
    ) -> Dict[str, Any]:
        """데이터프레임 분석하여 적합한 피벗테이블 제안"""

        if df.empty or len(df.columns) < 2:
            return {
                "message": "피벗테이블 생성에 충분한 데이터가 없습니다",
                "suggested_pivots": [],
            }

        suggestions = []

        # 숫자 컬럼과 카테고리 컬럼 식별
        numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_columns = df.select_dtypes(
            include=["object", "string"]
        ).columns.tolist()
        datetime_columns = df.select_dtypes(include=["datetime64"]).columns.tolist()

        # 카테고리 컬럼의 고유값 개수 확인 (피벗에 적합한지)
        suitable_categorical = []
        for col in categorical_columns:
            unique_count = df[col].nunique()
            if 2 <= unique_count <= 50:  # 너무 적거나 많지 않은 카테고리
                suitable_categorical.append((col, unique_count))

        # 1. 카테고리별 숫자 집계 (기본 피벗)
        if len(suitable_categorical) >= 1 and len(numeric_columns) >= 1:
            cat_col, cat_count = suitable_categorical[0]
            suggestions.append(
                {
                    "type": "basic_summary",
                    "title": f"{sheet_name} - {cat_col}별 요약",
                    "row_fields": [cat_col],
                    "column_fields": [],
                    "value_fields": numeric_columns[:2],
                    "aggfunc": "sum",
                    "confidence": 0.9,
                    "reason": f"{cat_col}별 수치 데이터 집계 분석에 적합 ({cat_count}개 카테고리)",
                }
            )

        # 2. 2차원 피벗 분석
        if len(suitable_categorical) >= 2 and len(numeric_columns) >= 1:
            cat1, count1 = suitable_categorical[0]
            cat2, count2 = suitable_categorical[1]

            # 카테고리 조합이 너무 크지 않은 경우만
            if count1 * count2 <= 200:
                suggestions.append(
                    {
                        "type": "two_dimensional",
                        "title": f"{sheet_name} - {cat1} vs {cat2} 교차분석",
                        "row_fields": [cat1],
                        "column_fields": [cat2],
                        "value_fields": [numeric_columns[0]],
                        "aggfunc": "sum",
                        "confidence": 0.8,
                        "reason": f"{cat1}와 {cat2}의 교차 분석에 적합 ({count1}x{count2} 조합)",
                    }
                )

        # 3. 시계열 기반 피벗
        if (
            len(datetime_columns) >= 1
            and len(categorical_columns) >= 1
            and len(numeric_columns) >= 1
        ):
            # 날짜를 년/월/분기로 그룹화
            suggestions.append(
                {
                    "type": "time_series_pivot",
                    "title": f"{sheet_name} - 시간별 {categorical_columns[0]} 분석",
                    "row_fields": [categorical_columns[0]],
                    "column_fields": [
                        datetime_columns[0]
                    ],  # 실제로는 년/월로 변환 필요
                    "value_fields": [numeric_columns[0]],
                    "aggfunc": "sum",
                    "confidence": 0.7,
                    "reason": "시간 축을 기준으로 한 트렌드 분석에 적합",
                    "note": "날짜 데이터를 년/월 단위로 그룹화하여 분석합니다",
                }
            )

        # 4. 다중 지표 분석
        if len(suitable_categorical) >= 1 and len(numeric_columns) >= 2:
            cat_col, cat_count = suitable_categorical[0]
            suggestions.append(
                {
                    "type": "multi_metric",
                    "title": f"{sheet_name} - {cat_col}별 다중 지표 분석",
                    "row_fields": [cat_col],
                    "column_fields": [],
                    "value_fields": numeric_columns[:3],  # 최대 3개 지표
                    "aggfunc": "mean",  # 평균으로 다양한 관점 제공
                    "confidence": 0.6,
                    "reason": f"여러 수치 지표를 {cat_col}별로 종합 비교 분석",
                }
            )

        # 신뢰도 순으로 정렬
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "data_summary": {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "numeric_columns": len(numeric_columns),
                "categorical_columns": len(categorical_columns),
                "datetime_columns": len(datetime_columns),
                "suitable_categories": len(suitable_categorical),
            },
            "suggested_pivots": suggestions[:4],  # 최대 4개 제안
            "sheet_name": sheet_name,
        }


# 전역 피벗테이블 분석기 인스턴스
excel_pivot_analyzer = ExcelPivotAnalyzer()
