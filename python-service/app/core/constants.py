"""
Excel to Univer 변환기 상수 정의
매직 넘버와 하드코딩된 값들을 중앙화된 상수로 관리
"""

from enum import Enum
from typing import Dict, Any


class ProcessingThresholds:
    """처리 임계값 상수"""
    
    # 워크시트 크기 임계값
    LARGE_WORKSHEET_CELL_COUNT = 5000  # 대용량 워크시트 판정 기준 (셀 수)
    BATCH_PROCESSING_SIZE = 1000       # 배치 처리 단위 (셀 수)
    
    # 메모리 관리 임계값 (MB)
    MEMORY_WARNING_THRESHOLD = 100     # 메모리 증가 경고 임계값
    MEMORY_CRITICAL_THRESHOLD = 500    # 메모리 위험 임계값
    MEMORY_CLEANUP_THRESHOLD = 100     # 가비지 컬렉션 실행 임계값
    
    # 파일 크기 임계값 (MB)
    LARGE_FILE_SIZE_THRESHOLD = 50     # 대용량 파일 판정 기준
    MAX_FILE_SIZE_THRESHOLD = 100      # 최대 처리 가능 파일 크기
    
    # 이미지 처리 임계값
    MAX_IMAGE_SIZE_MB = 10             # 개별 이미지 최대 크기
    IMAGE_COMPRESSION_THRESHOLD = 5    # 압축 시작 임계값
    MAX_IMAGES_PER_WORKSHEET = 50      # 워크시트당 최대 이미지 수


class PerformanceSettings:
    """성능 관련 설정"""
    
    # 병렬 처리 설정
    MAX_WORKER_THREADS = 3             # ThreadPoolExecutor 최대 스레드 수
    PARALLEL_PROCESSING_MIN_CELLS = 5000  # 병렬 처리 시작 최소 셀 수
    
    # 캐시 설정
    STYLE_CACHE_SIZE = 10000          # 스타일 캐시 최대 크기
    CELL_CACHE_SIZE = 50000           # 셀 데이터 캐시 최대 크기
    
    # 타임아웃 설정 (초)
    CONVERSION_TIMEOUT = 300          # 변환 작업 최대 시간 (5분)
    WORKSHEET_TIMEOUT = 60            # 워크시트 처리 최대 시간 (1분)
    
    # 로깅 설정
    PERFORMANCE_LOG_INTERVAL = 100    # 성능 통계 로깅 주기 (요청 수)
    DEBUG_CELL_LOG_THRESHOLD = 10000  # 디버그 모드에서 셀 로깅 시작 임계값


class FormatConstants:
    """포맷 관련 상수"""
    
    # Excel 색상 인덱스 매핑
    DEFAULT_COLOR_MAP = {
        0: "000000",  # 검은색
        1: "FFFFFF",  # 흰색
        2: "FF0000",  # 빨간색
        3: "00FF00",  # 초록색
        4: "0000FF",  # 파란색
        5: "FFFF00",  # 노란색
        6: "FF00FF",  # 자홍색
        7: "00FFFF",  # 청록색
        8: "800000",  # 어두운 빨간색
        9: "008000",  # 어두운 초록색
        10: "000080", # 어두운 파란색
    }
    
    # 기본 폰트 설정
    DEFAULT_FONT_NAME = "Arial"
    DEFAULT_FONT_SIZE = 11
    
    # 셀 타입 매핑
    CELL_TYPE_MAPPING = {
        "s": "string",      # 문자열
        "n": "number",      # 숫자
        "b": "boolean",     # 불린
        "d": "date",        # 날짜
        "e": "error",       # 오류
        "f": "formula",     # 수식
    }
    
    # 정렬 매핑
    ALIGNMENT_MAPPING = {
        "left": "left",
        "center": "center", 
        "right": "right",
        "justify": "justify",
        "fill": "fill",
        "centerContinuous": "centerContinuous",
        "distributed": "distributed"
    }


class ValidationLimits:
    """유효성 검사 제한값"""
    
    # 문자열 길이 제한
    MAX_SHEET_NAME_LENGTH = 31        # 워크시트 이름 최대 길이
    MAX_CELL_VALUE_LENGTH = 32767     # 셀 값 최대 길이
    MAX_COMMENT_LENGTH = 2048         # 주석 최대 길이
    
    # 파일 크기 제한 (MB)
    MAX_FILE_SIZE_MB = 100            # 최대 Excel 파일 크기
    
    # 수량 제한
    MAX_WORKSHEETS_COUNT = 255        # 최대 워크시트 수
    MAX_COLUMNS_COUNT = 16384         # 최대 열 수 (XFD)
    MAX_ROWS_COUNT = 1048576          # 최대 행 수
    MAX_CELLS_PER_SHEET = 50000       # 워크시트당 처리 최대 셀 수
    MAX_TOTAL_CELLS = 500000          # 전체 처리 최대 셀 수
    
    # 스타일 제한
    MAX_STYLE_COUNT = 64000           # 최대 스타일 수
    MAX_NAMED_RANGES = 2048           # 최대 명명된 범위 수
    
    # 차트 및 이미지 제한
    MAX_CHARTS_PER_WORKSHEET = 20     # 워크시트당 최대 차트 수
    MAX_IMAGES_PER_WORKSHEET_LIMIT = ProcessingThresholds.MAX_IMAGES_PER_WORKSHEET


class ErrorCodes:
    """오류 코드 상수"""
    
    # 파일 관련 오류
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_CORRUPTED = "FILE_CORRUPTED"
    INVALID_FORMAT = "INVALID_FORMAT"
    
    # 메모리 관련 오류
    MEMORY_ERROR = "MEMORY_ERROR"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    
    # 처리 관련 오류
    CONVERSION_ERROR = "CONVERSION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    WORKSHEET_ERROR = "WORKSHEET_ERROR"
    
    # 권한 관련 오류
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ACCESS_ERROR = "ACCESS_ERROR"


class EnvironmentKeys:
    """환경변수 키 상수"""
    
    # 디버그 모드
    EXCEL_CONVERTER_DEBUG = "EXCEL_CONVERTER_DEBUG"
    VBA_ANALYZER_DEBUG = "VBA_ANALYZER_DEBUG"
    
    # 로깅 설정
    LOG_LEVEL = "LOG_LEVEL"
    DEBUG_MODE = "DEBUG_MODE"
    LOG_FILE = "LOG_FILE"
    PERFORMANCE_LOG_FILE = "PERFORMANCE_LOG_FILE"
    
    # 성능 설정
    MAX_WORKER_THREADS_ENV = "EXCEL_MAX_WORKER_THREADS"
    MEMORY_LIMIT_MB = "EXCEL_MEMORY_LIMIT_MB"
    
    # 기능 토글
    ENABLE_PARALLEL_PROCESSING = "EXCEL_ENABLE_PARALLEL_PROCESSING"
    ENABLE_STYLE_CACHING = "EXCEL_ENABLE_STYLE_CACHING"
    ENABLE_MEMORY_MONITORING = "EXCEL_ENABLE_MEMORY_MONITORING"


class DefaultValues:
    """기본값 상수"""
    
    # Univer 워크북 기본 설정
    DEFAULT_LOCALE = "ko-KR"
    DEFAULT_SHEET_NAME = "Sheet1"
    
    # 스타일 기본값
    DEFAULT_STYLE_ID = "default"
    DEFAULT_BACKGROUND_COLOR = "FFFFFF"
    DEFAULT_TEXT_COLOR = "000000"
    
    # 행/열 기본 크기
    DEFAULT_ROW_HEIGHT = 20
    DEFAULT_COLUMN_WIDTH = 72
    
    # 셀 기본값
    DEFAULT_CELL_TYPE = "string"
    DEFAULT_CELL_VALUE = ""


class RegexPatterns:
    """정규식 패턴 상수"""
    
    # 셀 좌표 패턴
    CELL_COORDINATE_PATTERN = r"^([A-Z]+)(\d+)$"
    RANGE_PATTERN = r"^([A-Z]+\d+):([A-Z]+\d+)$"
    
    # 색상 패턴
    RGB_COLOR_PATTERN = r"^[A-Fa-f0-9]{6}$"
    ARGB_COLOR_PATTERN = r"^[A-Fa-f0-9]{8}$"
    
    # 수식 패턴
    FORMULA_PATTERN = r"^="
    
    # UUID 패턴
    UUID_PATTERN = r"^[a-f0-9-]{36}$"


def get_threshold_value(key: str, default: Any = None) -> Any:
    """
    환경변수에서 임계값을 가져오거나 기본값 반환
    
    Args:
        key: 환경변수 키
        default: 기본값
        
    Returns:
        설정된 값 또는 기본값
    """
    import os
    
    env_value = os.getenv(key)
    if env_value is None:
        return default
    
    # 숫자 변환 시도
    try:
        if '.' in env_value:
            return float(env_value)
        else:
            return int(env_value)
    except ValueError:
        # 불린 변환 시도
        if env_value.lower() in ('true', 'false'):
            return env_value.lower() == 'true'
        return env_value


def get_processing_config() -> Dict[str, Any]:
    """
    현재 환경설정을 반영한 처리 설정 반환
    
    Returns:
        처리 설정 딕셔너리
    """
    return {
        "large_worksheet_threshold": get_threshold_value(
            "EXCEL_LARGE_WORKSHEET_THRESHOLD", 
            ProcessingThresholds.LARGE_WORKSHEET_CELL_COUNT
        ),
        "max_worker_threads": get_threshold_value(
            EnvironmentKeys.MAX_WORKER_THREADS_ENV,
            PerformanceSettings.MAX_WORKER_THREADS
        ),
        "memory_warning_threshold": get_threshold_value(
            "EXCEL_MEMORY_WARNING_THRESHOLD",
            ProcessingThresholds.MEMORY_WARNING_THRESHOLD
        ),
        "enable_parallel_processing": get_threshold_value(
            EnvironmentKeys.ENABLE_PARALLEL_PROCESSING,
            True
        ),
        "enable_style_caching": get_threshold_value(
            EnvironmentKeys.ENABLE_STYLE_CACHING,
            True
        ),
        "conversion_timeout": get_threshold_value(
            "EXCEL_CONVERSION_TIMEOUT",
            PerformanceSettings.CONVERSION_TIMEOUT
        )
    }