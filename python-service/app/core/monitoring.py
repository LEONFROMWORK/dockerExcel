"""
모니터링 시스템
Prometheus 메트릭과 구조화된 로깅
"""

import time
import logging
from typing import Optional, Dict, Any
from functools import wraps
from contextlib import contextmanager
from prometheus_client import Counter, Histogram, Gauge, Info
import structlog
from datetime import datetime
import asyncio
import os
import sys

# 조건부 imports
try:
    import psutil
except ImportError:
    psutil = None

# Prometheus 메트릭 정의
request_count = Counter(
    'excel_unified_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'excel_unified_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

active_connections = Gauge(
    'excel_unified_active_connections',
    'Number of active connections'
)

error_count = Counter(
    'excel_unified_errors_total',
    'Total number of errors',
    ['error_type', 'endpoint']
)

analysis_count = Counter(
    'excel_unified_analysis_total',
    'Total number of analyses performed',
    ['analysis_type', 'status']
)

analysis_duration = Histogram(
    'excel_unified_analysis_duration_seconds',
    'Analysis duration in seconds',
    ['analysis_type']
)

cache_hits = Counter(
    'excel_unified_cache_hits_total',
    'Total number of cache hits',
    ['cache_type']
)

cache_misses = Counter(
    'excel_unified_cache_misses_total',
    'Total number of cache misses',
    ['cache_type']
)

file_processing_size = Histogram(
    'excel_unified_file_size_bytes',
    'Size of processed files in bytes',
    ['file_type']
)

# 서비스 정보
service_info = Info(
    'excel_unified_service',
    'Service information'
)
service_info.info({
    'version': '1.0.0',
    'environment': 'development'
})

# 구조화된 로거 설정
def setup_structured_logging():
    """구조화된 로깅 설정"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# 구조화된 로거 인스턴스
logger = structlog.get_logger()


class PerformanceMonitor:
    """성능 모니터링 클래스"""
    
    @staticmethod
    @contextmanager
    def monitor_operation(operation_name: str, **extra_fields):
        """작업 성능 모니터링 컨텍스트 매니저"""
        start_time = time.time()
        
        logger.info(
            "operation_started",
            operation=operation_name,
            **extra_fields
        )
        
        try:
            yield
            
            duration = time.time() - start_time
            logger.info(
                "operation_completed",
                operation=operation_name,
                duration=duration,
                status="success",
                **extra_fields
            )
            
            # Prometheus 메트릭 업데이트
            if 'analysis_type' in extra_fields:
                analysis_duration.labels(
                    analysis_type=extra_fields['analysis_type']
                ).observe(duration)
                analysis_count.labels(
                    analysis_type=extra_fields['analysis_type'],
                    status='success'
                ).inc()
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "operation_failed",
                operation=operation_name,
                duration=duration,
                status="error",
                error=str(e),
                **extra_fields
            )
            
            # 오류 메트릭 업데이트
            error_count.labels(
                error_type=type(e).__name__,
                endpoint=extra_fields.get('endpoint', 'unknown')
            ).inc()
            
            if 'analysis_type' in extra_fields:
                analysis_count.labels(
                    analysis_type=extra_fields['analysis_type'],
                    status='error'
                ).inc()
            
            raise
    
    @staticmethod
    def monitor_request(func):
        """요청 모니터링 데코레이터"""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            endpoint = func.__name__
            
            try:
                result = await func(*args, **kwargs)
                
                duration = time.time() - start_time
                status_code = getattr(result, 'status_code', 200)
                
                # 메트릭 업데이트
                request_count.labels(
                    method='POST',
                    endpoint=endpoint,
                    status=status_code
                ).inc()
                
                request_duration.labels(
                    method='POST',
                    endpoint=endpoint
                ).observe(duration)
                
                logger.info(
                    "request_completed",
                    endpoint=endpoint,
                    duration=duration,
                    status_code=status_code
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                request_count.labels(
                    method='POST',
                    endpoint=endpoint,
                    status=500
                ).inc()
                
                error_count.labels(
                    error_type=type(e).__name__,
                    endpoint=endpoint
                ).inc()
                
                logger.error(
                    "request_failed",
                    endpoint=endpoint,
                    duration=duration,
                    error=str(e)
                )
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            endpoint = func.__name__
            
            try:
                result = func(*args, **kwargs)
                
                duration = time.time() - start_time
                
                logger.info(
                    "request_completed",
                    endpoint=endpoint,
                    duration=duration
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    "request_failed",
                    endpoint=endpoint,
                    duration=duration,
                    error=str(e)
                )
                
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    @staticmethod
    def record_file_processing(file_path: str, file_type: str):
        """파일 처리 메트릭 기록"""
        file_size = os.path.getsize(file_path)
        
        file_processing_size.labels(
            file_type=file_type
        ).observe(file_size)
        
        logger.info(
            "file_processed",
            file_path=file_path,
            file_type=file_type,
            file_size=file_size
        )
    
    @staticmethod
    def record_cache_access(cache_type: str, hit: bool):
        """캐시 접근 메트릭 기록"""
        if hit:
            cache_hits.labels(cache_type=cache_type).inc()
        else:
            cache_misses.labels(cache_type=cache_type).inc()


class AnalysisMetrics:
    """분석 관련 메트릭"""
    
    @staticmethod
    def record_error_detection(error_count: int, error_types: Dict[str, int]):
        """오류 감지 메트릭 기록"""
        logger.info(
            "errors_detected",
            total_errors=error_count,
            error_types=error_types
        )
    
    @staticmethod
    def record_formula_analysis(formula_count: int, complexity_dist: Dict[str, int]):
        """수식 분석 메트릭 기록"""
        logger.info(
            "formulas_analyzed",
            total_formulas=formula_count,
            complexity_distribution=complexity_dist
        )
    
    @staticmethod
    def record_comparison_result(differences: int, match_percentage: float):
        """비교 분석 메트릭 기록"""
        logger.info(
            "comparison_completed",
            differences_found=differences,
            match_percentage=match_percentage
        )


class HealthCheck:
    """시스템 상태 확인"""
    
    @staticmethod
    def get_system_health() -> Dict[str, Any]:
        """시스템 상태 정보 반환"""
        if psutil is None:
            return {
                "status": "unknown",
                "timestamp": datetime.now().isoformat(),
                "message": "psutil not installed, system metrics unavailable"
            }
        
        try:
            # CPU 사용률 (블로킹 방지를 위해 interval=0 사용)
            cpu_percent = psutil.cpu_percent(interval=0)
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            
            # Python 프로세스 정보
            process = psutil.Process()
            
            return {
                "status": "healthy" if cpu_percent < 80 and memory.percent < 80 else "degraded",
                "timestamp": datetime.now().isoformat(),
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_mb": memory.available / (1024 * 1024),
                    "disk_percent": disk.percent,
                    "disk_free_gb": disk.free / (1024 * 1024 * 1024)
                },
                "process": {
                    "pid": process.pid,
                    "cpu_percent": process.cpu_percent(interval=0),
                    "memory_mb": process.memory_info().rss / (1024 * 1024),
                    "threads": process.num_threads(),
                    "open_files": len(process.open_files())
                },
                "python": {
                    "version": sys.version,
                    "platform": sys.platform
                }
            }
        except PermissionError as e:
            logger.error(f"권한 오류: {e}")
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": "Permission denied accessing system metrics"
            }
        except Exception as e:
            logger.error(f"시스템 상태 확인 오류: {e}", exc_info=True)
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }


# 모니터링 초기화
setup_structured_logging()