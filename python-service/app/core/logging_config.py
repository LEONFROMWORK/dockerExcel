"""
중앙화된 로깅 설정
모든 서비스에서 일관된 로깅 형식과 레벨 제공
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

class CustomFormatter(logging.Formatter):
    """컬러 출력을 지원하는 커스텀 포맷터"""
    
    # ANSI 색상 코드
    COLORS = {
        'DEBUG': '\033[36m',    # 청록색
        'INFO': '\033[32m',     # 초록색
        'WARNING': '\033[33m',  # 노란색
        'ERROR': '\033[31m',    # 빨간색
        'CRITICAL': '\033[35m', # 자홍색
        'RESET': '\033[0m'      # 리셋
    }
    
    def format(self, record):
        # 기본 포맷 적용
        formatted = super().format(record)
        
        # 컬러 터미널에서만 색상 적용
        if sys.stdout.isatty() and os.getenv('FORCE_COLOR', '').lower() != 'false':
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            formatted = f"{color}{formatted}{reset}"
        
        return formatted

def setup_logging(
    level: str = None,
    format_string: str = None,
    enable_debug: bool = None,
    log_file: Optional[str] = None
) -> None:
    """
    중앙화된 로깅 설정
    
    Args:
        level: 로깅 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: 로그 포맷 문자열
        enable_debug: 디버그 모드 활성화
        log_file: 로그 파일 경로 (선택사항)
    """
    
    # 환경변수에서 설정 읽기
    log_level = level or os.getenv('LOG_LEVEL', 'INFO').upper()
    debug_mode = enable_debug if enable_debug is not None else os.getenv('DEBUG_MODE', 'False').lower() == 'true'
    
    # 디버그 모드가 활성화되면 DEBUG 레벨로 설정
    if debug_mode:
        log_level = 'DEBUG'
    
    # 기본 포맷 설정
    default_format = (
        '%(asctime)s - %(name)s - %(levelname)s - '
        '[%(filename)s:%(lineno)d] - %(message)s'
    )
    
    format_str = format_string or os.getenv('LOG_FORMAT', default_format)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    
    # 커스텀 포맷터 적용
    formatter = CustomFormatter(format_str)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 설정 (선택사항)
    if log_file or os.getenv('LOG_FILE'):
        file_path = log_file or os.getenv('LOG_FILE')
        
        # 로그 디렉토리 생성
        log_dir = os.path.dirname(file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(getattr(logging, log_level))
        
        # 파일용 포맷터 (색상 코드 제외)
        file_formatter = logging.Formatter(format_str)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # 외부 라이브러리 로깅 레벨 조정
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('openpyxl').setLevel(logging.WARNING)
    
    # 설정 완료 로그
    logger = logging.getLogger(__name__)
    logger.info(f"로깅 시스템 초기화 완료")
    logger.info(f"로그 레벨: {log_level}")
    logger.info(f"디버그 모드: {'활성화' if debug_mode else '비활성화'}")
    if log_file or os.getenv('LOG_FILE'):
        logger.info(f"로그 파일: {log_file or os.getenv('LOG_FILE')}")

def get_performance_logger(name: str) -> logging.Logger:
    """
    성능 모니터링 전용 로거 생성
    
    Args:
        name: 로거 이름
        
    Returns:
        설정된 성능 로거
    """
    logger = logging.getLogger(f"performance.{name}")
    
    # 성능 로거는 별도 파일에 기록
    perf_log_file = os.getenv('PERFORMANCE_LOG_FILE', 'logs/performance.log')
    
    if perf_log_file and not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith('performance.log') for h in logger.handlers):
        # 성능 로그 디렉토리 생성
        log_dir = os.path.dirname(perf_log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        perf_handler = logging.FileHandler(perf_log_file, encoding='utf-8')
        perf_handler.setLevel(logging.INFO)
        
        # 성능 로그 전용 포맷
        perf_format = '%(asctime)s - %(name)s - %(message)s'
        perf_formatter = logging.Formatter(perf_format)
        perf_handler.setFormatter(perf_formatter)
        
        logger.addHandler(perf_handler)
        logger.setLevel(logging.INFO)
        
        # 콘솔 출력 방지 (성능 로그는 파일에만 기록)
        logger.propagate = False
    
    return logger

def log_performance_metrics(
    operation: str,
    duration: float,
    **kwargs
) -> None:
    """
    성능 메트릭 로깅 헬퍼 함수
    
    Args:
        operation: 작업 이름
        duration: 소요 시간 (초)
        **kwargs: 추가 메트릭 정보
    """
    perf_logger = get_performance_logger("metrics")
    
    metrics = {
        "operation": operation,
        "duration_seconds": round(duration, 3),
        "timestamp": datetime.now().isoformat(),
        **kwargs
    }
    
    # JSON 형태로 구조화된 로그 기록
    import json
    perf_logger.info(json.dumps(metrics, ensure_ascii=False))

def create_debug_logger(name: str) -> logging.Logger:
    """
    디버깅 전용 로거 생성
    
    Args:
        name: 로거 이름
        
    Returns:
        디버그 로거
    """
    logger = logging.getLogger(f"debug.{name}")
    
    # 디버그 모드가 활성화된 경우에만 동작
    if os.getenv('DEBUG_MODE', 'False').lower() == 'true':
        logger.setLevel(logging.DEBUG)
        
        # 디버그 전용 파일 핸들러
        debug_file = os.getenv('DEBUG_LOG_FILE', 'logs/debug.log')
        if debug_file and not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith('debug.log') for h in logger.handlers):
            # 디버그 로그 디렉토리 생성
            log_dir = os.path.dirname(debug_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            debug_handler = logging.FileHandler(debug_file, encoding='utf-8')
            debug_handler.setLevel(logging.DEBUG)
            
            # 상세한 디버그 포맷
            debug_format = (
                '%(asctime)s - %(name)s - %(levelname)s - '
                '[%(filename)s:%(lineno)d:%(funcName)s] - %(message)s'
            )
            debug_formatter = logging.Formatter(debug_format)
            debug_handler.setFormatter(debug_formatter)
            
            logger.addHandler(debug_handler)
    else:
        # 디버그 모드가 비활성화된 경우 로그 출력 안함
        logger.setLevel(logging.CRITICAL + 1)
    
    return logger

# 애플리케이션 시작 시 자동으로 로깅 설정 초기화
def init_logging():
    """애플리케이션 초기화 시 호출되는 로깅 설정"""
    setup_logging()

# 모듈 임포트 시 자동 초기화 (선택사항)
if os.getenv('AUTO_INIT_LOGGING', 'True').lower() == 'true':
    init_logging()