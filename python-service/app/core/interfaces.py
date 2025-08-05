"""
Core Interfaces for Excel Error Detection System
SOLID 원칙에 따른 인터페이스 정의
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


# Data Models
@dataclass
class ExcelError:
    """Excel 오류 데이터 모델"""

    id: str
    type: str
    sheet: str
    cell: str
    formula: Optional[str]
    value: Any
    message: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    is_auto_fixable: bool
    suggested_fix: Optional[str]
    confidence: float
    category: str = "critical_error"  # 'critical_error' or 'potential_issue'


@dataclass
class FixResult:
    """오류 수정 결과 모델"""

    success: bool
    error_id: str
    original_formula: str
    fixed_formula: str
    confidence: float
    applied: bool
    message: str


@dataclass
class Context:
    """AI 채팅 컨텍스트 모델"""

    session_id: str
    file_info: Dict[str, Any]
    selected_cell: Optional[str]
    detected_errors: List[ExcelError]
    user_history: List[Dict[str, Any]]
    current_operation: Optional[str]


# Interfaces
class IErrorDetector(ABC):
    """오류 감지 인터페이스"""

    @abstractmethod
    async def detect(self, workbook: Any) -> List[ExcelError]:
        """워크북에서 오류 감지"""

    @abstractmethod
    def can_detect(self, error_type: str) -> bool:
        """특정 오류 타입 감지 가능 여부"""


class IErrorFixer(ABC):
    """오류 수정 인터페이스"""

    @abstractmethod
    async def fix(self, error: ExcelError) -> FixResult:
        """오류 수정"""

    @abstractmethod
    def can_fix(self, error: ExcelError) -> bool:
        """오류 수정 가능 여부"""


class IProgressReporter(ABC):
    """진행 상황 보고 인터페이스"""

    @abstractmethod
    async def report_progress(self, current: int, total: int, message: str = ""):
        """진행 상황 보고"""

    @abstractmethod
    async def report_error(self, error: Exception):
        """오류 보고"""


class ICacheable(ABC):
    """캐시 가능 인터페이스"""

    @abstractmethod
    def get_cache_key(self) -> str:
        """캐시 키 생성"""

    @abstractmethod
    def is_cacheable(self) -> bool:
        """캐시 가능 여부"""


# Dummy Implementation for Progress Reporter
import logging

logger = logging.getLogger(__name__)


class DummyProgressReporter(IProgressReporter):
    """진행 상황을 로깅만 하는 더미 구현"""

    async def report_progress(self, current: int, total: int, message: str = ""):
        """진행 상황을 로그로만 기록"""
        logger.debug(f"Progress: {current}/{total} - {message}")

    async def report_error(self, error: Exception):
        """오류를 로그로만 기록"""
        logger.error(f"Error reported: {str(error)}")

    async def start_task(self, task_name: str, total_steps: int = 0):
        """작업 시작 - 더미 구현"""
        logger.debug(f"Task started: {task_name} (total steps: {total_steps})")

    async def complete_task(self, task_name: str, result: Any = None):
        """작업 완료 - 더미 구현"""
        logger.debug(f"Task completed: {task_name}")


class IErrorFixStrategy(ABC):
    """오류 수정 전략 인터페이스"""

    @abstractmethod
    def can_handle(self, error: ExcelError) -> bool:
        """이 전략이 오류를 처리할 수 있는지"""

    @abstractmethod
    async def apply_fix(self, error: ExcelError) -> FixResult:
        """수정 적용"""

    @abstractmethod
    def get_confidence(self, error: ExcelError) -> float:
        """수정 신뢰도 (0.0 ~ 1.0)"""


class IAIProcessor(ABC):
    """AI 처리 인터페이스"""

    @abstractmethod
    async def process(self, query: str, context: Context) -> Dict[str, Any]:
        """AI 쿼리 처리"""

    @abstractmethod
    def get_tier(self) -> int:
        """처리 티어 (1, 2, 3)"""

    @abstractmethod
    def get_cost_estimate(self, query: str) -> float:
        """예상 비용"""


class IWebSocketHandler(ABC):
    """WebSocket 핸들러 인터페이스"""

    @abstractmethod
    async def handle_connection(self, websocket: Any, session_id: str):
        """WebSocket 연결 처리"""

    @abstractmethod
    async def broadcast(self, session_id: str, message: Dict[str, Any]):
        """메시지 브로드캐스트"""

    @abstractmethod
    async def close_connection(self, session_id: str):
        """연결 종료"""


class IContextBuilder(ABC):
    """컨텍스트 빌더 인터페이스"""

    @abstractmethod
    def build_context(self, session_id: str) -> Context:
        """컨텍스트 생성"""

    @abstractmethod
    def update_context(self, context: Context, update_data: Dict[str, Any]) -> Context:
        """컨텍스트 업데이트"""


# Error Types Enum
class ExcelErrorType(Enum):
    """Excel 오류 타입"""

    DIV_ZERO = "#DIV/0!"
    NA = "#N/A"
    NAME = "#NAME?"
    NULL = "#NULL!"
    NUM = "#NUM!"
    REF = "#REF!"
    VALUE = "#VALUE!"
    SPILL = "#SPILL!"
    CALC = "#CALC!"
    CIRCULAR_REF = "Circular Reference"

    # Data Quality Errors
    DUPLICATE = "Duplicate Data"
    MISSING_DATA = "Missing Data"
    TYPE_MISMATCH = "Type Mismatch"

    # Structure Errors
    MERGED_CELLS = "Merged Cells"
    EMPTY_ROWS = "Empty Rows"
    BROKEN_FORMULA = "Broken Formula"


# Tier System
class ProcessingTier(Enum):
    """처리 티어"""

    CACHE = 1  # 캐시/패턴 기반
    FAST_AI = 2  # 빠른 AI (GPT-3.5 등)
    ADVANCED_AI = 3  # 고급 AI (GPT-4 등)


class IWorkbookLoader(ABC):
    """워크북 로더 인터페이스 - 순환 참조 방지"""

    @abstractmethod
    async def load_workbook(self, file_path: str) -> Any:
        """워크북을 로드합니다"""

    @abstractmethod
    async def save_workbook(self, workbook: Any, file_path: str) -> bool:
        """워크북을 저장합니다"""

    @abstractmethod
    async def get_cell_value(self, workbook: Any, sheet: str, cell: str) -> Any:
        """셀 값을 가져옵니다"""

    @abstractmethod
    async def set_cell_value(
        self, workbook: Any, sheet: str, cell: str, value: Any
    ) -> bool:
        """셀 값을 설정합니다"""
