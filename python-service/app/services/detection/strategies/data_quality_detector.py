"""
Data Quality Error Detector
데이터 품질 오류 감지 전략
"""

from typing import List, Any
from app.core.interfaces import IErrorDetector, ExcelError, ExcelErrorType
from collections import defaultdict
import re
import logging
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


class DataQualityDetector(IErrorDetector):
    """데이터 품질 오류 감지기"""

    def __init__(self):
        self.patterns = {
            "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
            "phone": re.compile(r"^[\d\s\-\+\(\)]+$"),
            "date": re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}$"),
            "number": re.compile(r"^-?\d+\.?\d*$"),
            "percentage": re.compile(r"^-?\d+\.?\d*%$"),
            "currency": re.compile(r"^[$￦€£¥]\s*-?\d+\.?\d*$"),
        }

    async def detect(self, workbook: Any) -> List[ExcelError]:
        """워크북에서 데이터 품질 오류 감지"""
        errors = []

        for sheet in workbook.sheetnames:
            worksheet = workbook[sheet]
            sheet_errors = await self._detect_sheet_errors(worksheet, sheet)
            errors.extend(sheet_errors)

        return errors

    def can_detect(self, error_type: str) -> bool:
        """데이터 품질 관련 오류만 감지"""
        return error_type in [
            ExcelErrorType.DUPLICATE.value,
            ExcelErrorType.MISSING_DATA.value,
            ExcelErrorType.TYPE_MISMATCH.value,
        ]

    async def _detect_sheet_errors(
        self, worksheet: Any, sheet_name: str
    ) -> List[ExcelError]:
        """시트별 오류 감지"""
        errors = []

        # 중복 데이터 감지
        duplicate_errors = self._detect_duplicates(worksheet, sheet_name)
        errors.extend(duplicate_errors)

        # 누락 데이터 감지
        missing_errors = self._detect_missing_data(worksheet, sheet_name)
        errors.extend(missing_errors)

        # 타입 불일치 감지
        type_errors = self._detect_type_mismatches(worksheet, sheet_name)
        errors.extend(type_errors)

        # 이상치 감지
        outlier_errors = self._detect_outliers(worksheet, sheet_name)
        errors.extend(outlier_errors)

        return errors

    def _detect_duplicates(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """중복 데이터 감지"""
        errors = []
        value_positions = defaultdict(list)

        # 모든 셀 값과 위치 수집
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.value is not None and cell.value != "":
                    # 헤더 행은 제외 (첫 번째 행)
                    if cell.row > 1:
                        value_positions[str(cell.value)].append(
                            (cell.row, cell.column, cell.coordinate)
                        )

        # 중복 찾기 (더 정교한 규칙 적용)
        for value, positions in value_positions.items():
            if len(positions) > 1:
                # 단순한 값(예: 'A', 'B', '1', '2' 등)은 중복으로 간주하지 않음
                if len(str(value)) > 2 and str(value).lower() not in [
                    "yes",
                    "no",
                    "true",
                    "false",
                    "y",
                    "n",
                    "t",
                    "f",
                ]:
                    # 같은 열에서의 중복만 오류로 표시
                    col_positions = defaultdict(list)
                    for row, col, coord in positions:
                        col_positions[col].append((row, coord))

                    for col, col_items in col_positions.items():
                        if len(col_items) > 1:
                            # 첫 번째 위치를 제외한 나머지를 중복으로 표시
                            for row, coord in col_items[1:]:
                                error = ExcelError(
                                    id=f"{sheet_name}_{coord}_duplicate",
                                    type=ExcelErrorType.DUPLICATE.value,
                                    category="potential_issue",  # 잠재적 문제
                                    sheet=sheet_name,
                                    cell=coord,
                                    formula=None,
                                    value=value,
                                    message=f"같은 열에 중복된 값: '{value}'가 {col_items[0][1]}에도 있습니다",
                                    severity="low",
                                    is_auto_fixable=False,
                                    suggested_fix="데이터 무결성을 위해 중복 여부를 확인하세요",
                                    confidence=0.7,
                                )
                                errors.append(error)

        return errors

    def _detect_missing_data(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """누락된 데이터 감지"""
        errors = []

        # 각 열의 데이터 패턴 분석
        column_data = defaultdict(list)
        max_row = worksheet.max_row
        max_col = worksheet.max_column

        for col in range(1, max_col + 1):
            for row in range(1, max_row + 1):
                cell = worksheet.cell(row=row, column=col)
                column_data[col].append(
                    {"row": row, "value": cell.value, "coord": cell.coordinate}
                )

        # 각 열에서 누락된 데이터 찾기
        for col, data in column_data.items():
            # 헤더를 제외한 데이터
            if len(data) > 1:
                header = data[0]["value"]
                values = data[1:]

                # 값이 있는 셀의 비율 계산
                non_empty_count = sum(1 for item in values if item["value"] is not None)
                fill_rate = non_empty_count / len(values) if values else 0

                # 채워진 비율이 80% 이상인 열에서만 빈 셀을 오류로 표시
                # 그리고 헤더가 실제로 의미있는 경우에만
                if (
                    fill_rate > 0.8
                    and header is not None
                    and str(header).strip() != ""
                    and header != "None"
                ):
                    for item in values:
                        if item["value"] is None or item["value"] == "":
                            # 연속된 빈 셀이 3개 이상인 경우 스킵 (의도적으로 비운 것일 가능성)
                            consecutive_empty = 0
                            for i in range(
                                max(0, values.index(item) - 2),
                                min(len(values), values.index(item) + 3),
                            ):
                                if (
                                    values[i]["value"] is None
                                    or values[i]["value"] == ""
                                ):
                                    consecutive_empty += 1

                            if consecutive_empty < 3:
                                error = ExcelError(
                                    id=f"{sheet_name}_{item['coord']}_missing",
                                    type=ExcelErrorType.MISSING_DATA.value,
                                    category="potential_issue",  # 잠재적 문제
                                    sheet=sheet_name,
                                    cell=item["coord"],
                                    formula=None,
                                    value=None,
                                    message=f"'{header}' 열에 누락된 데이터",
                                    severity="low",
                                    is_auto_fixable=False,
                                    suggested_fix="필요한 경우 누락된 데이터를 입력하세요",
                                    confidence=0.6,
                                )
                                errors.append(error)

        return errors

    def _detect_type_mismatches(
        self, worksheet: Any, sheet_name: str
    ) -> List[ExcelError]:
        """타입 불일치 감지"""
        errors = []

        # 각 열의 데이터 타입 패턴 분석
        column_types = defaultdict(lambda: defaultdict(int))

        for col in worksheet.iter_cols():
            col_idx = col[0].column

            # 헤더를 제외한 데이터 분석
            for cell in col[1:]:
                if cell.value is not None and cell.value != "":
                    data_type = self._detect_data_type(cell.value)
                    column_types[col_idx][data_type] += 1

        # 각 열의 주요 타입 결정
        column_main_types = {}
        for col_idx, types in column_types.items():
            if types:
                main_type = max(types.items(), key=lambda x: x[1])[0]
                total_count = sum(types.values())
                main_type_ratio = types[main_type] / total_count

                # 주요 타입이 80% 이상인 경우
                if main_type_ratio >= 0.8:
                    column_main_types[col_idx] = main_type

        # 타입 불일치 찾기
        for col in worksheet.iter_cols():
            col_idx = col[0].column
            if col_idx in column_main_types:
                expected_type = column_main_types[col_idx]

                for cell in col[1:]:  # 헤더 제외
                    if cell.value is not None and cell.value != "":
                        actual_type = self._detect_data_type(cell.value)

                        if actual_type != expected_type:
                            error = ExcelError(
                                id=f"{sheet_name}_{cell.coordinate}_type_mismatch",
                                type=ExcelErrorType.TYPE_MISMATCH.value,
                                category="critical_error",  # 명백한 오류
                                sheet=sheet_name,
                                cell=cell.coordinate,
                                formula=None,
                                value=cell.value,
                                message=f"타입 불일치: {expected_type} 예상, {actual_type} 발견",
                                severity="medium",
                                is_auto_fixable=(
                                    True
                                    if actual_type == "text"
                                    and expected_type == "number"
                                    else False
                                ),
                                suggested_fix=f"값을 {expected_type} 타입으로 변환하세요",
                                confidence=0.85,
                            )
                            errors.append(error)

        return errors

    def _detect_outliers(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """이상치 감지 (숫자 열에 대해)"""
        errors = []

        # 각 열의 숫자 데이터 수집
        column_numbers = defaultdict(list)

        for col in worksheet.iter_cols():
            col_idx = col[0].column

            for cell in col[1:]:  # 헤더 제외
                if isinstance(cell.value, (int, float)):
                    column_numbers[col_idx].append(
                        {"value": cell.value, "coord": cell.coordinate, "row": cell.row}
                    )

        # 각 열에서 이상치 찾기 (IQR 방법)
        for col_idx, data in column_numbers.items():
            if len(data) >= 4:  # 최소 4개 이상의 데이터가 있어야 의미 있음
                values = [item["value"] for item in data]

                # IQR 계산
                q1 = statistics.quantiles(values, n=4)[0]
                q3 = statistics.quantiles(values, n=4)[2]
                iqr = q3 - q1

                # 이상치 경계
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                for item in data:
                    if item["value"] < lower_bound or item["value"] > upper_bound:
                        error = ExcelError(
                            id=f"{sheet_name}_{item['coord']}_outlier",
                            type="Outlier",
                            category="potential_issue",  # 잠재적 문제
                            sheet=sheet_name,
                            cell=item["coord"],
                            formula=None,
                            value=item["value"],
                            message=f"이상치 감지: 값 {item['value']}이 정상 범위({lower_bound:.2f} ~ {upper_bound:.2f})를 벗어남",
                            severity="low",
                            is_auto_fixable=False,
                            suggested_fix="이상치가 올바른 값인지 확인하세요",
                            confidence=0.7,
                        )
                        errors.append(error)

        return errors

    def _detect_data_type(self, value: Any) -> str:
        """데이터 타입 감지"""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, datetime):
            return "date"
        elif isinstance(value, str):
            # 문자열 패턴 분석
            if self.patterns["email"].match(value):
                return "email"
            elif self.patterns["phone"].match(value):
                return "phone"
            elif self.patterns["date"].match(value):
                return "date"
            elif self.patterns["number"].match(value):
                return "number"
            elif self.patterns["percentage"].match(value):
                return "percentage"
            elif self.patterns["currency"].match(value):
                return "currency"
            else:
                return "text"
        else:
            return "unknown"
