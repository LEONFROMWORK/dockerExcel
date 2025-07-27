"""
Structure Error Detector
구조적 오류 감지 전략
"""

from typing import List, Dict, Any, Optional, Set
from app.core.interfaces import IErrorDetector, ExcelError, ExcelErrorType
import re
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class StructureDetector(IErrorDetector):
    """구조적 오류 감지기"""
    
    def __init__(self):
        self.min_table_width = 2  # 테이블로 간주할 최소 열 수
        self.min_table_height = 3  # 테이블로 간주할 최소 행 수
        self.max_empty_rows = 3   # 연속된 빈 행의 최대 허용 수
    
    async def detect(self, workbook: Any) -> List[ExcelError]:
        """워크북에서 구조적 오류 감지"""
        errors = []
        
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            sheet_errors = await self._detect_sheet_errors(worksheet, sheet_name)
            errors.extend(sheet_errors)
        
        return errors
    
    def can_detect(self, error_type: str) -> bool:
        """구조 관련 오류만 감지"""
        return error_type in [
            ExcelErrorType.MERGED_CELLS.value,
            ExcelErrorType.EMPTY_ROWS.value,
            ExcelErrorType.BROKEN_FORMULA.value,
            "Inconsistent Format",
            "Hidden Data",
            "Circular Reference"
        ]
    
    async def _detect_sheet_errors(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """시트별 구조적 오류 감지"""
        errors = []
        
        # 병합된 셀 감지
        merge_errors = self._detect_merged_cells(worksheet, sheet_name)
        errors.extend(merge_errors)
        
        # 빈 행/열 감지
        empty_errors = self._detect_empty_rows_cols(worksheet, sheet_name)
        errors.extend(empty_errors)
        
        # 테이블 구조 문제 감지
        structure_errors = self._detect_table_structure_issues(worksheet, sheet_name)
        errors.extend(structure_errors)
        
        # 숨겨진 데이터 감지
        hidden_errors = self._detect_hidden_data(worksheet, sheet_name)
        errors.extend(hidden_errors)
        
        # 일관성 없는 형식 감지
        format_errors = self._detect_inconsistent_formats(worksheet, sheet_name)
        errors.extend(format_errors)
        
        return errors
    
    def _detect_merged_cells(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """병합된 셀 감지"""
        errors = []
        
        # openpyxl의 merged_cells 속성 사용
        if hasattr(worksheet, 'merged_cells'):
            for merged_range in worksheet.merged_cells.ranges:
                # 병합 범위의 첫 번째 셀
                min_row, min_col = merged_range.min_row, merged_range.min_col
                max_row, max_col = merged_range.max_row, merged_range.max_col
                
                # 병합 범위가 데이터 테이블 내에 있는지 확인
                if self._is_in_data_table(worksheet, min_row, min_col):
                    top_left_cell = worksheet.cell(row=min_row, column=min_col)
                    
                    error = ExcelError(
                        id=f"{sheet_name}_{top_left_cell.coordinate}_merged",
                        type=ExcelErrorType.MERGED_CELLS.value,
                        sheet=sheet_name,
                        cell=str(merged_range),
                        formula=None,
                        value=top_left_cell.value,
                        message=f"병합된 셀 감지: {merged_range}",
                        severity="medium" if (max_row - min_row > 1 or max_col - min_col > 1) else "low",
                        is_auto_fixable=True,
                        suggested_fix="데이터 분석을 위해 병합된 셀을 분리하는 것을 권장합니다",
                        confidence=1.0
                    )
                    errors.append(error)
        
        return errors
    
    def _detect_empty_rows_cols(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """빈 행과 열 감지"""
        errors = []
        
        # 빈 행 감지
        consecutive_empty = 0
        last_data_row = 0
        
        for row_idx in range(1, worksheet.max_row + 1):
            row_empty = all(
                cell.value is None or str(cell.value).strip() == ""
                for cell in worksheet[row_idx]
            )
            
            if row_empty:
                consecutive_empty += 1
            else:
                if consecutive_empty > self.max_empty_rows and last_data_row > 0:
                    # 데이터 사이의 빈 행들
                    error = ExcelError(
                        id=f"{sheet_name}_row{last_data_row+1}_empty_rows",
                        type=ExcelErrorType.EMPTY_ROWS.value,
                        sheet=sheet_name,
                        cell=f"A{last_data_row+1}:A{row_idx-1}",
                        formula=None,
                        value=None,
                        message=f"{consecutive_empty}개의 연속된 빈 행 발견",
                        severity="low",
                        is_auto_fixable=True,
                        suggested_fix="불필요한 빈 행을 제거하여 데이터 연속성을 개선하세요",
                        confidence=0.9
                    )
                    errors.append(error)
                
                consecutive_empty = 0
                last_data_row = row_idx
        
        # 빈 열 감지
        for col_idx in range(1, worksheet.max_column + 1):
            col_empty = all(
                worksheet.cell(row=row, column=col_idx).value is None
                for row in range(1, min(worksheet.max_row + 1, 100))  # 처음 100행만 확인
            )
            
            if col_empty and col_idx < worksheet.max_column:
                # 데이터가 있는 열들 사이의 빈 열
                col_letter = self._get_column_letter(col_idx)
                error = ExcelError(
                    id=f"{sheet_name}_col{col_letter}_empty",
                    type="Empty Column",
                    sheet=sheet_name,
                    cell=f"{col_letter}1",
                    formula=None,
                    value=None,
                    message=f"빈 열 발견: {col_letter}열",
                    severity="low",
                    is_auto_fixable=True,
                    suggested_fix="빈 열을 제거하여 데이터 구조를 개선하세요",
                    confidence=0.8
                )
                errors.append(error)
        
        return errors
    
    def _detect_table_structure_issues(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """테이블 구조 문제 감지"""
        errors = []
        
        # 테이블 영역 찾기
        tables = self._find_tables(worksheet)
        
        for table in tables:
            # 헤더 행 확인
            header_row = table['start_row']
            headers = []
            
            for col in range(table['start_col'], table['end_col'] + 1):
                header_cell = worksheet.cell(row=header_row, column=col)
                headers.append(header_cell.value)
            
            # 빈 헤더 검사
            empty_headers = [i for i, h in enumerate(headers) if h is None or str(h).strip() == ""]
            if empty_headers:
                error = ExcelError(
                    id=f"{sheet_name}_table{table['id']}_empty_headers",
                    type="Empty Headers",
                    sheet=sheet_name,
                    cell=f"{self._get_column_letter(table['start_col'] + empty_headers[0])}{header_row}",
                    formula=None,
                    value=None,
                    message=f"테이블 헤더에 빈 값이 있습니다",
                    severity="medium",
                    is_auto_fixable=False,
                    suggested_fix="모든 열에 명확한 헤더를 지정하세요",
                    confidence=0.9
                )
                errors.append(error)
            
            # 중복 헤더 검사
            header_counts = defaultdict(int)
            for h in headers:
                if h:
                    header_counts[str(h)] += 1
            
            duplicates = [h for h, count in header_counts.items() if count > 1]
            if duplicates:
                error = ExcelError(
                    id=f"{sheet_name}_table{table['id']}_duplicate_headers",
                    type="Duplicate Headers",
                    sheet=sheet_name,
                    cell=f"{self._get_column_letter(table['start_col'])}{header_row}",
                    formula=None,
                    value=", ".join(duplicates),
                    message=f"중복된 헤더 발견: {', '.join(duplicates)}",
                    severity="high",
                    is_auto_fixable=False,
                    suggested_fix="각 열에 고유한 헤더를 사용하세요",
                    confidence=1.0
                )
                errors.append(error)
        
        return errors
    
    def _detect_hidden_data(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """숨겨진 행/열 감지"""
        errors = []
        
        # 숨겨진 행 검사
        if hasattr(worksheet, 'row_dimensions'):
            hidden_rows = []
            for row_idx, row_dim in worksheet.row_dimensions.items():
                if hasattr(row_dim, 'hidden') and row_dim.hidden:
                    hidden_rows.append(row_idx)
            
            if hidden_rows:
                error = ExcelError(
                    id=f"{sheet_name}_hidden_rows",
                    type="Hidden Data",
                    sheet=sheet_name,
                    cell=f"A{hidden_rows[0]}",
                    formula=None,
                    value=None,
                    message=f"{len(hidden_rows)}개의 숨겨진 행이 있습니다",
                    severity="medium",
                    is_auto_fixable=True,
                    suggested_fix="숨겨진 행을 표시하거나 삭제하세요",
                    confidence=1.0
                )
                errors.append(error)
        
        # 숨겨진 열 검사
        if hasattr(worksheet, 'column_dimensions'):
            hidden_cols = []
            for col_letter, col_dim in worksheet.column_dimensions.items():
                if hasattr(col_dim, 'hidden') and col_dim.hidden:
                    hidden_cols.append(col_letter)
            
            if hidden_cols:
                error = ExcelError(
                    id=f"{sheet_name}_hidden_cols",
                    type="Hidden Data",
                    sheet=sheet_name,
                    cell=f"{hidden_cols[0]}1",
                    formula=None,
                    value=None,
                    message=f"{len(hidden_cols)}개의 숨겨진 열이 있습니다",
                    severity="medium",
                    is_auto_fixable=True,
                    suggested_fix="숨겨진 열을 표시하거나 삭제하세요",
                    confidence=1.0
                )
                errors.append(error)
        
        return errors
    
    def _detect_inconsistent_formats(self, worksheet: Any, sheet_name: str) -> List[ExcelError]:
        """일관성 없는 형식 감지"""
        errors = []
        
        # 각 열의 형식 패턴 분석
        column_formats = defaultdict(lambda: defaultdict(int))
        
        for col_idx in range(1, min(worksheet.max_column + 1, 50)):  # 최대 50열까지
            for row_idx in range(2, min(worksheet.max_row + 1, 100)):  # 헤더 제외, 최대 100행
                cell = worksheet.cell(row=row_idx, column=col_idx)
                if cell.value is not None:
                    # 숫자 형식 추출
                    format_code = cell.number_format if hasattr(cell, 'number_format') else 'General'
                    column_formats[col_idx][format_code] += 1
        
        # 일관성 없는 형식 찾기
        for col_idx, formats in column_formats.items():
            if len(formats) > 1:
                total_cells = sum(formats.values())
                main_format = max(formats.items(), key=lambda x: x[1])
                
                # 주요 형식이 70% 미만인 경우
                if main_format[1] / total_cells < 0.7:
                    col_letter = self._get_column_letter(col_idx)
                    error = ExcelError(
                        id=f"{sheet_name}_col{col_letter}_inconsistent_format",
                        type="Inconsistent Format",
                        sheet=sheet_name,
                        cell=f"{col_letter}2",
                        formula=None,
                        value=None,
                        message=f"{col_letter}열에 {len(formats)}개의 다른 형식이 혼재",
                        severity="low",
                        is_auto_fixable=True,
                        suggested_fix="열 전체에 일관된 형식을 적용하세요",
                        confidence=0.8
                    )
                    errors.append(error)
        
        return errors
    
    # Helper methods
    def _is_in_data_table(self, worksheet: Any, row: int, col: int) -> bool:
        """주어진 위치가 데이터 테이블 내에 있는지 확인"""
        # 간단한 휴리스틱: 주변에 데이터가 있는지 확인
        nearby_data = 0
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                try:
                    cell = worksheet.cell(row=row+dr, column=col+dc)
                    if cell.value is not None:
                        nearby_data += 1
                except:
                    pass
        
        return nearby_data >= 3
    
    def _find_tables(self, worksheet: Any) -> List[Dict[str, Any]]:
        """워크시트에서 테이블 영역 찾기"""
        tables = []
        visited = set()
        table_id = 0
        
        for row in range(1, min(worksheet.max_row + 1, 1000)):
            for col in range(1, min(worksheet.max_column + 1, 100)):
                if (row, col) not in visited:
                    # 데이터가 있는 셀에서 시작
                    cell = worksheet.cell(row=row, column=col)
                    if cell.value is not None:
                        # 연결된 데이터 영역 찾기
                        table = self._find_connected_region(worksheet, row, col, visited)
                        
                        # 최소 크기 이상인 경우만 테이블로 간주
                        if (table['end_row'] - table['start_row'] >= self.min_table_height - 1 and
                            table['end_col'] - table['start_col'] >= self.min_table_width - 1):
                            table['id'] = table_id
                            tables.append(table)
                            table_id += 1
        
        return tables
    
    def _find_connected_region(self, worksheet: Any, start_row: int, start_col: int, 
                              visited: Set[tuple]) -> Dict[str, Any]:
        """연결된 데이터 영역 찾기"""
        min_row, max_row = start_row, start_row
        min_col, max_col = start_col, start_col
        
        # BFS로 연결된 영역 탐색
        queue = [(start_row, start_col)]
        visited.add((start_row, start_col))
        
        while queue:
            row, col = queue.pop(0)
            
            # 인접한 셀 확인
            for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                new_row, new_col = row + dr, col + dc
                
                if (new_row, new_col) not in visited:
                    if 1 <= new_row <= worksheet.max_row and 1 <= new_col <= worksheet.max_column:
                        cell = worksheet.cell(row=new_row, column=new_col)
                        if cell.value is not None:
                            visited.add((new_row, new_col))
                            queue.append((new_row, new_col))
                            
                            min_row = min(min_row, new_row)
                            max_row = max(max_row, new_row)
                            min_col = min(min_col, new_col)
                            max_col = max(max_col, new_col)
        
        return {
            'start_row': min_row,
            'end_row': max_row,
            'start_col': min_col,
            'end_col': max_col
        }
    
    def _get_column_letter(self, col_idx: int) -> str:
        """열 인덱스를 문자로 변환"""
        result = ""
        while col_idx > 0:
            col_idx -= 1
            result = chr(65 + col_idx % 26) + result
            col_idx //= 26
        return result