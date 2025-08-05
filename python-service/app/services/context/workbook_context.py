"""
Workbook Context Manager
워크북 전체 컨텍스트 관리 - 멀티 셀 분석을 위한 확장
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class CellInfo:
    """셀 정보"""

    address: str
    sheet: str
    value: Any
    formula: Optional[str] = None
    format: Optional[Dict[str, Any]] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)  # 이 셀이 참조하는 셀들
    dependents: Set[str] = field(default_factory=set)  # 이 셀을 참조하는 셀들


@dataclass
class SheetContext:
    """시트별 컨텍스트"""

    name: str
    cells: Dict[str, CellInfo]  # address -> CellInfo
    row_count: int
    column_count: int
    data_ranges: List[Dict[str, Any]]  # 데이터 영역 정보
    named_ranges: Dict[str, str]  # 이름 정의

    def get_cell(self, address: str) -> Optional[CellInfo]:
        """셀 정보 조회"""
        return self.cells.get(address)

    def add_cell(self, cell: CellInfo):
        """셀 정보 추가"""
        self.cells[cell.address] = cell


@dataclass
class WorkbookContext:
    """워크북 전체 컨텍스트"""

    file_id: str
    file_name: str
    sheets: Dict[str, SheetContext]  # sheet_name -> SheetContext
    global_errors: List[Dict[str, Any]]
    analysis_summary: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 메타데이터
    total_cells: int = 0
    total_formulas: int = 0
    total_errors: int = 0

    def get_sheet(self, sheet_name: str) -> Optional[SheetContext]:
        """시트 컨텍스트 조회"""
        return self.sheets.get(sheet_name)

    def add_sheet(self, sheet: SheetContext):
        """시트 추가"""
        self.sheets[sheet.name] = sheet
        self.updated_at = datetime.now()

    def get_cell(self, sheet_name: str, address: str) -> Optional[CellInfo]:
        """특정 셀 정보 조회"""
        sheet = self.get_sheet(sheet_name)
        return sheet.get_cell(address) if sheet else None

    def get_cells_in_range(
        self, sheet_name: str, start: str, end: str
    ) -> List[CellInfo]:
        """범위 내 셀들 조회"""
        sheet = self.get_sheet(sheet_name)
        if not sheet:
            return []

        # 간단한 구현 - 실제로는 더 복잡한 범위 파싱 필요
        cells = []
        for address, cell in sheet.cells.items():
            # TODO: 실제 범위 체크 구현
            cells.append(cell)

        return cells

    def get_dependent_cells(self, sheet_name: str, address: str) -> Set[str]:
        """특정 셀에 의존하는 모든 셀 찾기"""
        cell = self.get_cell(sheet_name, address)
        if not cell:
            return set()

        all_dependents = set()
        to_check = {f"{sheet_name}!{address}"}
        checked = set()

        while to_check:
            current = to_check.pop()
            if current in checked:
                continue
            checked.add(current)

            # 현재 셀의 직접 의존 셀들 찾기
            sheet_name_part, address_part = current.split("!")
            current_cell = self.get_cell(sheet_name_part, address_part)
            if current_cell:
                for dep in current_cell.dependents:
                    all_dependents.add(dep)
                    to_check.add(dep)

        return all_dependents

    def update_cell_dependency(
        self,
        sheet_name: str,
        address: str,
        dependencies: Set[str],
        dependents: Set[str],
    ):
        """셀 의존성 정보 업데이트"""
        cell = self.get_cell(sheet_name, address)
        if cell:
            cell.dependencies = dependencies
            cell.dependents = dependents
            self.updated_at = datetime.now()

    def get_summary(self) -> Dict[str, Any]:
        """워크북 요약 정보"""
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "sheet_count": len(self.sheets),
            "total_cells": self.total_cells,
            "total_formulas": self.total_formulas,
            "total_errors": self.total_errors,
            "sheets": [
                {
                    "name": name,
                    "cell_count": len(sheet.cells),
                    "row_count": sheet.row_count,
                    "column_count": sheet.column_count,
                }
                for name, sheet in self.sheets.items()
            ],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_json(self) -> str:
        """JSON 직렬화"""
        data = {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "sheets": {},
            "global_errors": self.global_errors,
            "analysis_summary": self.analysis_summary,
            "metadata": {
                "total_cells": self.total_cells,
                "total_formulas": self.total_formulas,
                "total_errors": self.total_errors,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
            },
        }

        # 시트 정보 직렬화
        for sheet_name, sheet in self.sheets.items():
            data["sheets"][sheet_name] = {
                "name": sheet.name,
                "row_count": sheet.row_count,
                "column_count": sheet.column_count,
                "cell_count": len(sheet.cells),
                "data_ranges": sheet.data_ranges,
                "named_ranges": sheet.named_ranges,
                # 셀 정보는 크기 때문에 요약만
                "sample_cells": list(sheet.cells.keys())[:10],
            }

        return json.dumps(data, ensure_ascii=False)


class WorkbookContextBuilder:
    """워크북 컨텍스트 빌더"""

    @staticmethod
    def build_from_analysis(
        file_id: str, file_name: str, analysis_result: Dict[str, Any]
    ) -> WorkbookContext:
        """분석 결과로부터 워크북 컨텍스트 생성"""
        context = WorkbookContext(
            file_id=file_id,
            file_name=file_name,
            sheets={},
            global_errors=analysis_result.get("errors", []),
            analysis_summary=analysis_result.get("summary", {}),
        )

        # 시트별 정보 구축
        sheets_data = analysis_result.get("sheets", {})
        for sheet_name, sheet_data in sheets_data.items():
            sheet_context = SheetContext(
                name=sheet_name,
                cells={},
                row_count=sheet_data.get("row_count", 0),
                column_count=sheet_data.get("column_count", 0),
                data_ranges=sheet_data.get("data_ranges", []),
                named_ranges=sheet_data.get("named_ranges", {}),
            )

            # 셀 정보 추가
            cells_data = sheet_data.get("cells", {})
            for address, cell_data in cells_data.items():
                cell_info = CellInfo(
                    address=address,
                    sheet=sheet_name,
                    value=cell_data.get("value"),
                    formula=cell_data.get("formula"),
                    format=cell_data.get("format"),
                    errors=cell_data.get("errors", []),
                )
                sheet_context.add_cell(cell_info)

            context.add_sheet(sheet_context)

        # 메타데이터 업데이트
        context.total_cells = sum(len(sheet.cells) for sheet in context.sheets.values())
        context.total_formulas = sum(
            1
            for sheet in context.sheets.values()
            for cell in sheet.cells.values()
            if cell.formula
        )
        context.total_errors = len(context.global_errors) + sum(
            len(cell.errors)
            for sheet in context.sheets.values()
            for cell in sheet.cells.values()
        )

        return context

    @staticmethod
    def update_from_detector_result(
        context: WorkbookContext, detector_result: Dict[str, Any]
    ) -> WorkbookContext:
        """IntegratedErrorDetector 결과로 컨텍스트 업데이트"""
        # 오류 정보 업데이트
        if "errors" in detector_result:
            for error in detector_result["errors"]:
                sheet_name = error.get("sheet")
                cell_address = error.get("cell")

                if sheet_name and cell_address:
                    cell = context.get_cell(sheet_name, cell_address)
                    if cell:
                        cell.errors.append(error)

        # 요약 정보 업데이트
        if "summary" in detector_result:
            context.analysis_summary.update(detector_result["summary"])

        context.updated_at = datetime.now()
        return context
