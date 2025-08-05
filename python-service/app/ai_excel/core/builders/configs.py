"""
Configuration objects for builder methods
Reduces parameter count by grouping related parameters
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from openpyxl.chart import Reference
from openpyxl.styles import Font, PatternFill, Border, Alignment


@dataclass
class TableConfig:
    """Configuration for creating tables"""

    start_cell: str
    end_cell: str
    table_name: str
    style: str = "TableStyleMedium9"


@dataclass
class ValidationConfig:
    """Configuration for data validation"""

    cell_range: str
    validation_type: str
    formula1: str
    formula2: Optional[str] = None
    allow_blank: bool = True
    error_title: str = "Invalid Entry"
    error_message: str = "Invalid entry"
    prompt_title: str = "Valid Entry"
    prompt_message: str = "Please enter a valid value"


@dataclass
class ChartConfig:
    """Configuration for creating charts"""

    chart_type: str
    data_range: Reference
    categories: Optional[Reference] = None
    title: str = ""
    position: str = "E5"
    width: float = 15
    height: float = 10


@dataclass
class ComboChartConfig:
    """Configuration for combination charts"""

    primary_data: Reference
    secondary_data: Reference
    categories: Reference
    title: str = ""
    position: str = "E5"
    primary_type: str = "column"
    secondary_type: str = "line"


@dataclass
class CellStyleConfig:
    """Configuration for cell styling"""

    font: Optional[Font] = None
    fill: Optional[PatternFill] = None
    alignment: Optional[Alignment] = None
    border: Optional[Border] = None
    number_format: Optional[str] = None


@dataclass
class RangeStyleConfig:
    """Configuration for range styling"""

    start_row: int
    start_col: int
    end_row: int
    end_col: int
    style: CellStyleConfig


@dataclass
class AlternateRowConfig:
    """Configuration for alternate row coloring"""

    start_row: int
    end_row: int
    start_col: int
    end_col: int
    color1: str = "FFFFFF"
    color2: str = "F2F2F2"


@dataclass
class ConditionalFormatConfig:
    """Configuration for conditional formatting"""

    cell_range: str
    rule_type: str
    # Additional parameters as dict for flexibility
    params: Dict[str, Any] = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}
