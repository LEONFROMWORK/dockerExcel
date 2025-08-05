"""
Core Type Definitions
핵심 타입 정의 - TypedDict를 사용한 구조화된 타입
"""

from typing import TypedDict, List, Optional, Any, Dict, Union
from enum import Enum


class ErrorSeverity(str, Enum):
    """오류 심각도"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorType(str, Enum):
    """오류 타입"""

    FORMULA_ERROR = "formula_error"
    CIRCULAR_REFERENCE = "circular_reference"
    DATA_QUALITY = "data_quality"
    STRUCTURE = "structure"
    FORMATTING = "formatting"
    VBA_ERROR = "vba_error"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class CellInfo(TypedDict):
    """셀 정보"""

    address: str
    sheet: str
    value: Any
    formula: Optional[str]
    row: int
    col: int
    has_error: Optional[bool]
    error_type: Optional[str]


class ErrorInfo(TypedDict):
    """오류 정보"""

    id: Optional[str]
    type: str
    severity: str
    cell: str
    sheet: str
    message: str
    is_auto_fixable: bool
    suggested_fix: Optional[str]
    confidence: Optional[float]
    details: Optional[Dict[str, Any]]


class SheetSummary(TypedDict):
    """시트 요약"""

    name: str
    rows: int
    columns: int
    non_empty_cells: int
    formulas_count: int
    errors_count: int
    data_types: Dict[str, int]


class AnalysisSummary(TypedDict):
    """분석 요약"""

    total_sheets: int
    total_rows: int
    total_cells_with_data: int
    total_errors: int
    has_errors: bool
    error_types: Dict[str, int]
    auto_fixable_count: int
    auto_fixable_percentage: float
    has_charts: bool
    has_pivot_tables: bool
    most_common_error_type: Optional[str]


class FileAnalysisResult(TypedDict):
    """파일 분석 결과"""

    status: str
    file_id: str
    file_path: str
    filename: str
    timestamp: str
    analysis_time: float
    errors: List[ErrorInfo]
    summary: AnalysisSummary
    sheets: Dict[str, SheetSummary]
    tier_used: str


class PatternInfo(TypedDict):
    """패턴 정보"""

    type: str
    description: str
    confidence: float
    frequency: int
    affected_cells: List[str]
    suggestions: List[str]


class PatternAnalysis(TypedDict):
    """패턴 분석 결과"""

    patterns: List[PatternInfo]
    summary: str
    has_insights: bool
    total_patterns: int


class PredictionInfo(TypedDict):
    """예측 정보"""

    cell: str
    error_type: str
    probability: float
    risk_level: str
    description: str
    prevention_tips: List[str]


class ErrorPrediction(TypedDict):
    """오류 예측 결과"""

    predictions: List[PredictionInfo]
    total_risks: int
    high_risks: int
    has_predictions: bool
    summary: str


class OptimizationSuggestion(TypedDict):
    """최적화 제안"""

    id: str
    type: str
    title: str
    description: str
    impact: str
    affected_cells: int
    auto_applicable: bool
    steps: Optional[List[str]]


class OptimizationAnalysis(TypedDict):
    """최적화 분석 결과"""

    suggestions: List[OptimizationSuggestion]
    total_suggestions: int
    auto_applicable: int
    has_suggestions: bool
    potential_improvement: str


class StandardErrorResponse(TypedDict):
    """표준 에러 응답"""

    status: str  # "error"
    message: str
    error_code: Optional[str]
    details: Optional[Dict[str, Any]]
    timestamp: str
    request_id: Optional[str]


class StandardSuccessResponse(TypedDict):
    """표준 성공 응답"""

    status: str  # "success"
    data: Any
    message: Optional[str]
    timestamp: str
    request_id: Optional[str]


class WorkbookContextSummary(TypedDict):
    """워크북 컨텍스트 요약"""

    file_id: str
    file_name: str
    total_sheets: int
    total_errors: int
    error_types: List[str]
    has_vba: bool
    last_updated: str


class SessionContext(TypedDict):
    """세션 컨텍스트"""

    session_id: str
    user_id: Optional[str]
    workbook_context: Optional[WorkbookContextSummary]
    selected_cells: List[CellInfo]
    chat_history: List[Dict[str, Any]]
    last_action: Optional[str]
    last_updated: str


class MultiCellAnalysis(TypedDict):
    """멀티 셀 분석 결과"""

    individual_cells: List[Dict[str, Any]]
    total_errors: int
    pattern_analysis: PatternAnalysis
    cross_cell_issues: List[Dict[str, Any]]
    summary: Dict[str, Any]


class AIConsultationResponse(TypedDict):
    """AI 상담 응답"""

    response: str
    suggestions: List[Dict[str, Any]]
    follow_up_questions: List[str]
    related_cells: List[str]
    action_items: List[Dict[str, Any]]
    model_used: str
    cell_context_provided: bool


class CacheStats(TypedDict):
    """캐시 통계"""

    memory_hits: int
    memory_misses: int
    redis_hits: int
    redis_misses: int
    total_gets: int
    total_sets: int
    memory_cache_size: int
    hit_rate: float


# Union 타입들
ErrorResponse = Union[StandardErrorResponse, Dict[str, Any]]
SuccessResponse = Union[StandardSuccessResponse, Dict[str, Any]]
AnalysisResult = Union[FileAnalysisResult, Dict[str, Any]]
