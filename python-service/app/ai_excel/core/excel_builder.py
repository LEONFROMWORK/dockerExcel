"""
Excel builder facade - coordinates specialized builders
Provides a unified interface to all Excel building operations
"""

from typing import Dict, List, Any, Optional, Tuple
import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.chart import Reference
import pandas as pd

from .builders import (
    TableBuilder, ChartBuilder, StyleBuilder,
    TableConfig, ValidationConfig, ChartConfig,
    CellStyleConfig, RangeStyleConfig
)


class ExcelBuilder:
    """Facade for Excel building operations - coordinates specialized builders"""
    
    def __init__(self):
        self.table_builder = TableBuilder()
        self.chart_builder = ChartBuilder()
        self.style_builder = StyleBuilder()
    
    @property
    def table(self) -> TableBuilder:
        """Access table builder directly"""
        return self.table_builder
    
    @property
    def chart(self) -> ChartBuilder:
        """Access chart builder directly"""
        return self.chart_builder
    
    @property
    def style(self) -> StyleBuilder:
        """Access style builder directly"""
        return self.style_builder
    
    # Legacy methods for backward compatibility only
    def create_table(self, worksheet: Worksheet, start_cell: str, end_cell: str, 
                    table_name: str, style: str = "TableStyleMedium9"):
        """DEPRECATED: Use builder.table.create_table() with TableConfig"""
        return self.table_builder.create_table_legacy(worksheet, start_cell, end_cell, table_name, style)
    
    def write_dataframe(self, worksheet: Worksheet, df: pd.DataFrame,
                       start_row: int = 1, start_col: int = 1) -> Tuple[int, int]:
        """DEPRECATED: Use builder.table.write_dataframe()"""
        return self.table_builder.write_dataframe(worksheet, df, start_row, start_col)
    
    def add_data_validation(self, worksheet: Worksheet, cell_range: str,
                          validation_type: str, formula1: str,
                          formula2: Optional[str] = None,
                          allow_blank: bool = True) -> None:
        """DEPRECATED: Use builder.table.add_data_validation() with ValidationConfig"""
        self.table_builder.add_data_validation_legacy(
            worksheet, cell_range, validation_type, 
            formula1, formula2, allow_blank
        )
    
    def create_chart(self, worksheet: Worksheet, chart_type: str, 
                    data_range: Reference, categories: Optional[Reference] = None,
                    title: str = "", position: str = "E5") -> None:
        """DEPRECATED: Use builder.chart.create_chart() with ChartConfig"""
        self.chart_builder.create_chart_legacy(
            worksheet, chart_type, data_range, 
            categories, title, position
        )
    
    def apply_cell_style(self, cell, **style_kwargs) -> None:
        """DEPRECATED: Use builder.style.apply_cell_style() with CellStyleConfig"""
        self.style_builder.apply_cell_style_legacy(cell, **style_kwargs)
    
    # Legacy compatibility methods
    def write_dataframe_with_formatting(self, worksheet: Worksheet, df: pd.DataFrame,
                                      start_row: int = 1, start_col: int = 1,
                                      header_style: Optional[Dict[str, Any]] = None,
                                      data_formats: Optional[Dict[str, str]] = None) -> Tuple[int, int]:
        """Write DataFrame with formatting (legacy compatibility)"""
        # Write data
        end_row, end_col = self.write_dataframe(worksheet, df, start_row, start_col)
        
        # Apply header style if provided
        if header_style:
            self.apply_range_style(
                worksheet, start_row, start_col, 
                start_row, start_col + len(df.columns) - 1,
                **header_style
            )
        
        # Apply data formats if provided
        if data_formats:
            for col_idx, column in enumerate(df.columns):
                if column in data_formats:
                    for row_idx in range(start_row + 1, end_row + 1):
                        cell = worksheet.cell(row=row_idx, column=start_col + col_idx)
                        cell.number_format = data_formats[column]
        
        return end_row, end_col
    
    # Backward compatibility static methods
    @staticmethod
    def apply_cell_style_static(cell, **kwargs):
        """Static method for backward compatibility"""
        builder = ExcelBuilder()
        builder.apply_cell_style(cell, **kwargs)
    
    @staticmethod
    def auto_adjust_column_width(worksheet: Worksheet, min_width: float = 8.0,
                               max_width: float = 50.0) -> None:
        """Static method for backward compatibility"""
        builder = ExcelBuilder()
        builder.auto_adjust_columns(worksheet, min_width, max_width)