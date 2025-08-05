"""
Excel Utilities
Excel 처리를 위한 공통 유틸리티 함수
"""

import re
from typing import Tuple, Optional


class ExcelUtils:
    """Excel 관련 공통 유틸리티"""

    # 컴파일된 정규식 패턴 (성능 최적화)
    CELL_PATTERN = re.compile(r"^([A-Z]+)(\d+)$", re.IGNORECASE)
    RANGE_PATTERN = re.compile(r"^([A-Z]+)(\d+):([A-Z]+)(\d+)$", re.IGNORECASE)
    SHEET_CELL_PATTERN = re.compile(r"^(.+)!([A-Z]+)(\d+)$", re.IGNORECASE)

    @staticmethod
    def parse_cell_reference(cell_ref: str) -> Tuple[str, int]:
        """셀 참조를 열과 행으로 분리

        Args:
            cell_ref: 셀 참조 (예: "A1", "Sheet1!B2")

        Returns:
            (column, row) 튜플
        """
        # 시트명이 포함된 경우
        sheet_match = ExcelUtils.SHEET_CELL_PATTERN.match(cell_ref)
        if sheet_match:
            col = sheet_match.group(2)
            row = int(sheet_match.group(3))
            return col, row

        # 일반 셀 참조
        match = ExcelUtils.CELL_PATTERN.match(cell_ref)
        if match:
            col = match.group(1)
            row = int(match.group(2))
            return col, row

        return "A", 1  # 기본값

    @staticmethod
    def column_to_index(column: str) -> int:
        """열 문자를 인덱스로 변환 (A=0, B=1, ...)"""
        index = 0
        for char in column.upper():
            index = index * 26 + (ord(char) - ord("A") + 1)
        return index - 1

    @staticmethod
    def index_to_column(index: int) -> str:
        """인덱스를 열 문자로 변환 (0=A, 1=B, ...)"""
        column = ""
        index += 1
        while index > 0:
            index -= 1
            column = chr(index % 26 + ord("A")) + column
            index //= 26
        return column

    @staticmethod
    def column_to_number(column: str) -> int:
        """열 문자를 숫자로 변환 (A=1, B=2, ..., Z=26, AA=27)"""
        result = 0
        for char in column.upper():
            result = result * 26 + (ord(char) - ord("A") + 1)
        return result

    @staticmethod
    def number_to_column(number: int) -> str:
        """숫자를 열 문자로 변환 (1=A, 2=B, ..., 26=Z, 27=AA)"""
        column = ""
        while number > 0:
            number -= 1
            column = chr(number % 26 + ord("A")) + column
            number //= 26
        return column

    @staticmethod
    def is_cell_reference(text: str) -> bool:
        """텍스트가 셀 참조인지 확인"""
        if not text:
            return False

        # 단일 셀
        if ExcelUtils.CELL_PATTERN.match(text):
            return True

        # 범위
        if ExcelUtils.RANGE_PATTERN.match(text):
            return True

        # 시트 포함 참조
        if ExcelUtils.SHEET_CELL_PATTERN.match(text):
            return True

        return False

    @staticmethod
    def is_range_reference(text: str) -> bool:
        """텍스트가 범위 참조인지 확인"""
        return bool(ExcelUtils.RANGE_PATTERN.match(text))

    @staticmethod
    def extract_sheet_name(reference: str) -> Optional[str]:
        """참조에서 시트명 추출"""
        if "!" in reference:
            sheet_name = reference.split("!")[0]
            # 따옴표 제거
            if sheet_name.startswith("'") and sheet_name.endswith("'"):
                sheet_name = sheet_name[1:-1]
            return sheet_name
        return None

    @staticmethod
    def cell_to_row_col(cell: str) -> Tuple[int, int]:
        """셀 주소를 행, 열 숫자로 변환 (정렬용)"""
        col, row = ExcelUtils.parse_cell_reference(cell)
        col_num = ExcelUtils.column_to_number(col)
        return (row, col_num)

    @staticmethod
    def is_error_value(value: any) -> bool:
        """값이 Excel 오류인지 확인"""
        if isinstance(value, str):
            error_values = [
                "#DIV/0!",
                "#N/A",
                "#NAME?",
                "#NULL!",
                "#NUM!",
                "#REF!",
                "#VALUE!",
                "#SPILL!",
                "#CALC!",
            ]
            return value.upper() in [err.upper() for err in error_values]
        return False

    @staticmethod
    def get_error_type(value: str) -> Optional[str]:
        """오류 값에서 오류 타입 추출"""
        if ExcelUtils.is_error_value(value):
            return value.upper().strip("#").rstrip("!")
        return None
