"""
Pydantic models for Excel structure definition
Provides type-safe schema for Excel generation
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class ChartType(str, Enum):
    """Supported chart types"""

    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    COMBO = "combo"
    WATERFALL = "waterfall"


class DataType(str, Enum):
    """Excel column data types"""

    TEXT = "text"
    NUMBER = "number"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    FORMULA = "formula"


class FormulaType(str, Enum):
    """Common formula types"""

    SUM = "sum"
    AVERAGE = "average"
    COUNT = "count"
    IF = "if"
    VLOOKUP = "vlookup"
    INDEX_MATCH = "index_match"
    CUSTOM = "custom"


class CellStyle(BaseModel):
    """Cell styling options"""

    font_name: Optional[str] = "Arial"
    font_size: Optional[int] = 11
    font_bold: Optional[bool] = False
    font_italic: Optional[bool] = False
    font_color: Optional[str] = "000000"
    fill_color: Optional[str] = None
    border: Optional[str] = None
    alignment: Optional[str] = "left"
    number_format: Optional[str] = None


class ColumnDefinition(BaseModel):
    """Definition for a single column"""

    name: str = Field(..., description="Column header name")
    data_type: DataType = Field(DataType.TEXT, description="Data type for the column")
    width: Optional[float] = Field(15.0, description="Column width")
    style: Optional[CellStyle] = None
    formula: Optional[str] = Field(None, description="Formula for calculated columns")
    validation: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

    @validator("width")
    def validate_width(cls, v):
        if v and (v < 1 or v > 255):
            raise ValueError("Column width must be between 1 and 255")
        return v


class FormulaDefinition(BaseModel):
    """Definition for Excel formulas"""

    cell_reference: str = Field(
        ..., description="Cell or range reference (e.g., 'E2:E10')"
    )
    formula_type: FormulaType
    formula: str = Field(..., description="Excel formula string")
    description: Optional[str] = None
    depends_on: Optional[List[str]] = Field(
        default_factory=list, description="Cell references this formula depends on"
    )


class ChartSpecification(BaseModel):
    """Specification for charts"""

    chart_type: ChartType
    title: str
    data_range: str = Field(..., description="Data range for the chart")
    categories_range: Optional[str] = Field(None, description="Categories/labels range")
    position: str = Field("E5", description="Top-left cell position for the chart")
    width: Optional[int] = Field(15, description="Chart width in cells")
    height: Optional[int] = Field(10, description="Chart height in cells")
    series_names: Optional[List[str]] = None
    style_id: Optional[int] = None


class DataRelationship(BaseModel):
    """Defines relationships between data in different sheets or ranges"""

    source_sheet: str
    source_range: str
    target_sheet: str
    target_range: str
    relationship_type: str = Field(
        ..., description="Type of relationship (e.g., 'lookup', 'sum', 'reference')"
    )
    key_columns: Optional[List[str]] = None


class ConditionalFormat(BaseModel):
    """Conditional formatting rules"""

    range: str = Field(..., description="Cell range to apply formatting")
    rule_type: str = Field(
        ..., description="Type of rule (e.g., 'cell_value', 'color_scale', 'data_bar')"
    )
    conditions: Dict[str, Any]
    format: CellStyle


class SheetSchema(BaseModel):
    """Schema for a single worksheet"""

    name: str = Field(..., description="Sheet name")
    columns: List[ColumnDefinition]
    row_count: Optional[int] = Field(100, description="Expected number of data rows")
    has_header: bool = Field(True, description="Whether sheet has header row")
    has_totals: bool = Field(False, description="Whether sheet has totals row")
    freeze_panes: Optional[str] = Field(
        None, description="Cell reference for freeze panes (e.g., 'B2')"
    )
    formulas: Optional[List[FormulaDefinition]] = Field(default_factory=list)
    charts: Optional[List[ChartSpecification]] = Field(default_factory=list)
    conditional_formats: Optional[List[ConditionalFormat]] = Field(default_factory=list)
    description: Optional[str] = None

    @validator("name")
    def validate_sheet_name(cls, v):
        # Excel sheet name restrictions
        if len(v) > 31:
            raise ValueError("Sheet name must be 31 characters or less")
        invalid_chars = ["\\", "/", "*", "[", "]", ":", "?"]
        if any(char in v for char in invalid_chars):
            raise ValueError(f'Sheet name cannot contain: {", ".join(invalid_chars)}')
        return v


class ExcelStructure(BaseModel):
    """Complete Excel file structure"""

    filename: Optional[str] = Field(None, description="Suggested filename")
    title: Optional[str] = Field(None, description="Document title")
    description: Optional[str] = Field(None, description="Document description")
    domain: Optional[str] = Field(None, description="Business domain")
    sheets: List[SheetSchema]
    relationships: Optional[List[DataRelationship]] = Field(default_factory=list)
    global_styles: Optional[Dict[str, CellStyle]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator("sheets")
    def validate_sheets(cls, v):
        if not v:
            raise ValueError("At least one sheet is required")
        # Check for duplicate sheet names
        names = [sheet.name for sheet in v]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate sheet names are not allowed")
        return v

    def get_sheet(self, name: str) -> Optional[SheetSchema]:
        """Get sheet by name"""
        for sheet in self.sheets:
            if sheet.name == name:
                return sheet
        return None

    def add_sheet(self, sheet: SheetSchema) -> None:
        """Add a new sheet"""
        if any(s.name == sheet.name for s in self.sheets):
            raise ValueError(f"Sheet '{sheet.name}' already exists")
        self.sheets.append(sheet)

    def add_relationship(self, relationship: DataRelationship) -> None:
        """Add a data relationship"""
        if self.relationships is None:
            self.relationships = []
        self.relationships.append(relationship)

    def to_generation_spec(self) -> Dict[str, Any]:
        """Convert to a specification suitable for generation"""
        return {
            "structure": self.dict(),
            "generation_hints": {
                "total_sheets": len(self.sheets),
                "total_columns": sum(len(sheet.columns) for sheet in self.sheets),
                "has_formulas": any(sheet.formulas for sheet in self.sheets),
                "has_charts": any(sheet.charts for sheet in self.sheets),
                "complexity": self._calculate_complexity(),
            },
        }

    def _calculate_complexity(self) -> str:
        """Calculate structure complexity"""
        score = 0
        score += len(self.sheets) * 10
        score += len(self.relationships or []) * 5
        score += sum(len(sheet.formulas or []) for sheet in self.sheets) * 2
        score += sum(len(sheet.charts or []) for sheet in self.sheets) * 3

        if score < 20:
            return "simple"
        elif score < 50:
            return "intermediate"
        elif score < 100:
            return "advanced"
        else:
            return "expert"


class GenerationRequest(BaseModel):
    """Request model for Excel generation"""

    user_request: str = Field(..., description="Natural language request from user")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional context"
    )
    language: str = Field("ko", description="Language code")
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Generation options"
    )


class GenerationResponse(BaseModel):
    """Response model for Excel generation"""

    status: str = Field(..., description="Generation status (success, error, pending)")
    file_path: Optional[str] = Field(None, description="Path to generated Excel file")
    structure: Optional[ExcelStructure] = Field(None, description="Generated structure")
    insights: Optional[List[str]] = Field(
        default_factory=list, description="AI insights about the generation"
    )
    warnings: Optional[List[str]] = Field(
        default_factory=list, description="Any warnings during generation"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
