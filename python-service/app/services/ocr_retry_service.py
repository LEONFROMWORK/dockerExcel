"""
OCR 실패 재시도 로직 서비스
지수 백오프, 실패 유형 분류, 재시도 전략 구현
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
import random

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """실패 유형 분류"""
    TEMPORARY_NETWORK = "temporary_network"    # 일시적 네트워크 오류
    TEMPORARY_RESOURCE = "temporary_resource"  # 리소스 부족 (메모리, CPU)
    TEMPORARY_SERVICE = "temporary_service"    # 서비스 일시 중단
    PERMANENT_FORMAT = "permanent_format"      # 잘못된 파일 형식
    PERMANENT_CORRUPT = "permanent_corrupt"    # 파일 손상
    PERMANENT_MODEL = "permanent_model"        # 모델 파일 누락
    UNKNOWN = "unknown"                        # 분류 불가능한 오류


@dataclass
class RetryConfig:
    """재시도 설정"""
    max_attempts: int = 3                      # 최대 재시도 횟수
    base_delay: float = 1.0                   # 기본 대기 시간 (초)
    max_delay: float = 60.0                   # 최대 대기 시간 (초)
    backoff_multiplier: float = 2.0           # 백오프 배수
    jitter: bool = True                       # 지터 적용 여부
    timeout: float = 30.0                     # 개별 시도 타임아웃


@dataclass
class RetryAttempt:
    """재시도 시도 정보"""
    attempt_number: int
    delay: float
    failure_type: FailureType
    error_message: str
    timestamp: float


@dataclass
class RetryResult:
    """재시도 결과"""
    success: bool
    data: Any = None
    error_message: str = ""
    attempts: List[RetryAttempt] = None
    total_duration: float = 0.0
    final_failure_type: FailureType = FailureType.UNKNOWN


class OCRRetryService:
    """OCR 재시도 서비스"""
    
    def __init__(self, config: RetryConfig = None):
        """
        Args:
            config: 재시도 설정. None이면 기본값 사용
        """
        self.config = config or RetryConfig()
        self.retry_stats = {
            'total_attempts': 0,
            'successful_retries': 0,
            'failed_after_retries': 0,
            'failure_types': {},
            'average_attempts': 0.0
        }
        
        logger.info(f"OCRRetryService 초기화: max_attempts={self.config.max_attempts}")
    
    def classify_failure(self, error: Exception) -> FailureType:
        """에러를 분류하여 실패 유형 결정"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # 네트워크 관련 오류
        if any(keyword in error_str for keyword in ['connection', 'timeout', 'network', 'socket']):
            return FailureType.TEMPORARY_NETWORK
        if any(keyword in error_type for keyword in ['connectionerror', 'timeout', 'httperror']):
            return FailureType.TEMPORARY_NETWORK
            
        # 리소스 관련 오류
        if any(keyword in error_str for keyword in ['memory', 'resource', 'busy', 'overload']):
            return FailureType.TEMPORARY_RESOURCE
        if 'memoryerror' in error_type:
            return FailureType.TEMPORARY_RESOURCE
            
        # 서비스 관련 오류
        if any(keyword in error_str for keyword in ['service unavailable', '503', 'temporarily']):
            return FailureType.TEMPORARY_SERVICE
            
        # 파일 형식 오류
        if any(keyword in error_str for keyword in ['format', 'invalid', 'decode', 'corrupt']):
            if 'cannot identify image file' in error_str:
                return FailureType.PERMANENT_FORMAT
            if 'image file is truncated' in error_str:
                return FailureType.PERMANENT_CORRUPT
            if 'invalid' in error_str and 'format' in error_str:
                return FailureType.PERMANENT_FORMAT
            return FailureType.PERMANENT_FORMAT  # 기본적으로 파일 형식 오류로 분류
        
        # ValueError 타입은 일반적으로 파일 형식 오류
        if 'valueerror' in error_type:
            return FailureType.PERMANENT_FORMAT
                
        # 모델 파일 오류
        if any(keyword in error_str for keyword in ['model', 'traineddata', 'tessdata']):
            return FailureType.PERMANENT_MODEL
            
        # Tesseract 관련 오류
        if 'tesseract' in error_str:
            if 'failed loading language' in error_str:
                return FailureType.PERMANENT_MODEL
            elif 'too few characters' in error_str:
                return FailureType.PERMANENT_FORMAT
            else:
                return FailureType.TEMPORARY_SERVICE
        
        return FailureType.UNKNOWN
    
    def should_retry(self, failure_type: FailureType, attempt: int) -> bool:
        """재시도 여부 결정"""
        # 최대 시도 횟수 초과
        if attempt >= self.config.max_attempts:
            return False
            
        # 영구적 실패는 재시도하지 않음
        if failure_type in [FailureType.PERMANENT_FORMAT, 
                           FailureType.PERMANENT_CORRUPT, 
                           FailureType.PERMANENT_MODEL]:
            return False
            
        return True
    
    def calculate_delay(self, attempt: int, failure_type: FailureType) -> float:
        """대기 시간 계산 (지수 백오프 + 지터)"""
        # 기본 지수 백오프
        delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))
        
        # 실패 유형별 조정
        if failure_type == FailureType.TEMPORARY_NETWORK:
            delay *= 1.5  # 네트워크 오류는 더 긴 대기
        elif failure_type == FailureType.TEMPORARY_RESOURCE:
            delay *= 2.0  # 리소스 오류는 더 긴 대기
            
        # 최대 대기 시간 제한
        delay = min(delay, self.config.max_delay)
        
        # 지터 적용 (동시 재시도 방지)
        if self.config.jitter:
            jitter_range = delay * 0.1  # 10% 지터
            delay += random.uniform(-jitter_range, jitter_range)
            
        return max(0.1, delay)  # 최소 0.1초
    
    async def retry_with_backoff(self, 
                                func: Callable,
                                *args,
                                **kwargs) -> RetryResult:
        """지수 백오프로 함수 재시도 실행"""
        start_time = time.time()
        attempts = []
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                self.retry_stats['total_attempts'] += 1
                
                # 함수 실행
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), 
                        timeout=self.config.timeout
                    )
                else:
                    result = func(*args, **kwargs)
                
                # 성공
                if attempt > 1:
                    self.retry_stats['successful_retries'] += 1
                    logger.info(f"재시도 성공: {attempt}번째 시도에서 성공")
                
                return RetryResult(
                    success=True,
                    data=result,
                    attempts=attempts,
                    total_duration=time.time() - start_time
                )
                
            except Exception as e:
                failure_type = self.classify_failure(e)
                error_message = str(e)
                
                # 시도 정보 기록
                attempt_info = RetryAttempt(
                    attempt_number=attempt,
                    delay=0.0,  # 이번 시도 후 대기 시간
                    failure_type=failure_type,
                    error_message=error_message,
                    timestamp=time.time()
                )
                attempts.append(attempt_info)
                
                # 통계 업데이트
                if failure_type.value not in self.retry_stats['failure_types']:
                    self.retry_stats['failure_types'][failure_type.value] = 0
                self.retry_stats['failure_types'][failure_type.value] += 1
                
                logger.warning(f"시도 {attempt}/{self.config.max_attempts} 실패 "
                             f"({failure_type.value}): {error_message}")
                
                # 재시도 여부 확인
                if not self.should_retry(failure_type, attempt):
                    logger.error(f"재시도 중단: {failure_type.value} (시도: {attempt}번)")
                    break
                
                # 마지막 시도가 아니면 대기
                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt, failure_type)
                    attempt_info.delay = delay
                    
                    logger.info(f"재시도 대기: {delay:.2f}초")
                    await asyncio.sleep(delay)
        
        # 모든 시도 실패
        self.retry_stats['failed_after_retries'] += 1
        final_failure_type = attempts[-1].failure_type if attempts else FailureType.UNKNOWN
        
        return RetryResult(
            success=False,
            error_message=attempts[-1].error_message if attempts else "Unknown error",
            attempts=attempts,
            total_duration=time.time() - start_time,
            final_failure_type=final_failure_type
        )
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """재시도 통계 조회"""
        total_operations = (self.retry_stats['successful_retries'] + 
                          self.retry_stats['failed_after_retries'])
        
        if total_operations > 0:
            self.retry_stats['average_attempts'] = (
                self.retry_stats['total_attempts'] / total_operations
            )
        
        return self.retry_stats.copy()
    
    def reset_stats(self):
        """통계 초기화"""
        self.retry_stats = {
            'total_attempts': 0,
            'successful_retries': 0,
            'failed_after_retries': 0,
            'failure_types': {},
            'average_attempts': 0.0
        }
        logger.info("재시도 통계 초기화됨")


# 전역 재시도 서비스 인스턴스
default_retry_service = OCRRetryService()


def with_retry(config: RetryConfig = None):
    """재시도 데코레이터"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            retry_service = OCRRetryService(config) if config else default_retry_service
            result = await retry_service.retry_with_backoff(func, *args, **kwargs)
            
            if result.success:
                return result.data
            else:
                raise Exception(f"재시도 후 최종 실패: {result.error_message}")
        
        return wrapper
    return decorator