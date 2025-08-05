"""
Enhanced Monitoring and Logging
향상된 모니터링 및 로깅 시스템
"""

import time
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager
from functools import wraps
import traceback
import psutil
import os
from collections import defaultdict, deque

from app.core.integrated_cache import integrated_cache

logger = logging.getLogger(__name__)


class MetricsCollector:
    """메트릭 수집기"""

    def __init__(self):
        self.metrics = defaultdict(
            lambda: {
                "count": 0,
                "total_time": 0,
                "errors": 0,
                "last_error": None,
                "percentiles": deque(maxlen=1000),  # 최근 1000개 요청만 저장
            }
        )
        self.start_time = time.time()

    def record_request(
        self,
        endpoint: str,
        duration: float,
        status_code: int,
        error: Optional[str] = None,
    ):
        """요청 메트릭 기록"""
        metric = self.metrics[endpoint]
        metric["count"] += 1
        metric["total_time"] += duration
        metric["percentiles"].append(duration)

        if status_code >= 400:
            metric["errors"] += 1
            metric["last_error"] = {
                "time": datetime.now().isoformat(),
                "status": status_code,
                "error": error,
            }

    def get_stats(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """통계 조회"""
        if endpoint:
            return self._calculate_endpoint_stats(endpoint)

        # 전체 통계
        total_requests = sum(m["count"] for m in self.metrics.values())
        total_errors = sum(m["errors"] for m in self.metrics.values())
        uptime = time.time() - self.start_time

        return {
            "uptime_seconds": uptime,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / total_requests if total_requests > 0 else 0,
            "endpoints": {
                ep: self._calculate_endpoint_stats(ep) for ep in self.metrics.keys()
            },
        }

    def _calculate_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """엔드포인트별 통계 계산"""
        metric = self.metrics[endpoint]
        count = metric["count"]

        if count == 0:
            return {"count": 0, "errors": 0}

        percentiles = sorted(metric["percentiles"])

        return {
            "count": count,
            "errors": metric["errors"],
            "error_rate": metric["errors"] / count,
            "avg_time": metric["total_time"] / count,
            "p50": percentiles[len(percentiles) // 2] if percentiles else 0,
            "p90": percentiles[int(len(percentiles) * 0.9)] if percentiles else 0,
            "p99": percentiles[int(len(percentiles) * 0.99)] if percentiles else 0,
            "last_error": metric["last_error"],
        }


class SystemMonitor:
    """시스템 리소스 모니터"""

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """시스템 메트릭 수집"""
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # 메모리 사용률
            memory = psutil.virtual_memory()

            # 디스크 사용률
            disk = psutil.disk_usage("/")

            # 프로세스 정보
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()

            # 네트워크 I/O
            net_io = psutil.net_io_counters()

            return {
                "timestamp": datetime.now().isoformat(),
                "cpu": {"percent": cpu_percent, "count": psutil.cpu_count()},
                "memory": {
                    "percent": memory.percent,
                    "available_mb": memory.available / 1024 / 1024,
                    "total_mb": memory.total / 1024 / 1024,
                },
                "disk": {
                    "percent": disk.percent,
                    "free_gb": disk.free / 1024 / 1024 / 1024,
                    "total_gb": disk.total / 1024 / 1024 / 1024,
                },
                "process": {
                    "memory_mb": process_memory.rss / 1024 / 1024,
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads(),
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                },
            }
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {}


class PerformanceTracker:
    """성능 추적기"""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.checkpoints = []

    def start(self):
        """추적 시작"""
        self.start_time = time.time()
        self.checkpoints = []
        return self

    def checkpoint(self, label: str):
        """체크포인트 기록"""
        if not self.start_time:
            return

        elapsed = time.time() - self.start_time
        self.checkpoints.append(
            {
                "label": label,
                "elapsed": elapsed,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def end(self) -> Dict[str, Any]:
        """추적 종료 및 결과 반환"""
        if not self.start_time:
            return {}

        total_time = time.time() - self.start_time

        return {
            "name": self.name,
            "total_time": total_time,
            "checkpoints": self.checkpoints,
            "timestamp": datetime.now().isoformat(),
        }


class RequestLogger:
    """요청 로거"""

    @staticmethod
    async def log_request(
        request: Any, response: Any = None, error: Optional[Exception] = None
    ):
        """요청/응답 로깅"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
        }

        if response:
            log_data["status_code"] = response.status_code
            log_data["response_time"] = getattr(response, "headers", {}).get(
                "X-Process-Time"
            )

        if error:
            log_data["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }

        # 구조화된 로그 출력
        if error:
            logger.error(f"Request failed: {json.dumps(log_data)}")
        else:
            logger.info(f"Request completed: {json.dumps(log_data)}")

        # 캐시에 저장 (분석용)
        try:
            await integrated_cache.set(
                f"request_log:{datetime.now().strftime('%Y%m%d')}:{request.url.path}",
                log_data,
                ttl=86400,  # 1일 보관
            )
        except Exception as e:
            logger.warning(f"Failed to cache request log: {e}")


# 전역 인스턴스
metrics_collector = MetricsCollector()
system_monitor = SystemMonitor()


# 데코레이터
def monitor_performance(name: Optional[str] = None):
    """성능 모니터링 데코레이터"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = name or f"{func.__module__}.{func.__name__}"
            tracker = PerformanceTracker(func_name)
            tracker.start()

            try:
                result = await func(*args, **kwargs)
                performance_data = tracker.end()

                # 성능 데이터 로깅
                if performance_data["total_time"] > 1.0:  # 1초 이상 걸린 작업
                    logger.warning(
                        f"Slow operation detected: {json.dumps(performance_data)}"
                    )

                return result
            except Exception as e:
                performance_data = tracker.end()
                performance_data["error"] = str(e)
                logger.error(f"Operation failed: {json.dumps(performance_data)}")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = name or f"{func.__module__}.{func.__name__}"
            tracker = PerformanceTracker(func_name)
            tracker.start()

            try:
                result = func(*args, **kwargs)
                performance_data = tracker.end()

                if performance_data["total_time"] > 1.0:
                    logger.warning(
                        f"Slow operation detected: {json.dumps(performance_data)}"
                    )

                return result
            except Exception as e:
                performance_data = tracker.end()
                performance_data["error"] = str(e)
                logger.error(f"Operation failed: {json.dumps(performance_data)}")
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@asynccontextmanager
async def track_operation(operation_name: str):
    """컨텍스트 매니저 형태의 성능 추적"""
    tracker = PerformanceTracker(operation_name)
    tracker.start()

    try:
        yield tracker
    finally:
        performance_data = tracker.end()

        # 메트릭 기록
        metrics_collector.record_request(
            endpoint=operation_name,
            duration=performance_data["total_time"],
            status_code=200,
        )

        # 로깅
        if performance_data["total_time"] > 1.0:
            logger.warning(f"Slow operation: {json.dumps(performance_data)}")
        else:
            logger.debug(f"Operation completed: {json.dumps(performance_data)}")


class AlertManager:
    """알림 관리자"""

    def __init__(self):
        self.alerts = []
        self.thresholds = {
            "cpu_percent": 80,
            "memory_percent": 85,
            "disk_percent": 90,
            "error_rate": 0.05,  # 5%
            "response_time_p99": 2.0,  # 2초
        }

    async def check_and_alert(self):
        """시스템 상태 확인 및 알림"""
        # 시스템 메트릭 확인
        system_metrics = system_monitor.get_system_metrics()

        if (
            system_metrics.get("cpu", {}).get("percent", 0)
            > self.thresholds["cpu_percent"]
        ):
            await self._create_alert(
                "HIGH_CPU_USAGE",
                f"CPU usage is {system_metrics['cpu']['percent']}%",
                "warning",
            )

        if (
            system_metrics.get("memory", {}).get("percent", 0)
            > self.thresholds["memory_percent"]
        ):
            await self._create_alert(
                "HIGH_MEMORY_USAGE",
                f"Memory usage is {system_metrics['memory']['percent']}%",
                "warning",
            )

        # API 메트릭 확인
        api_stats = metrics_collector.get_stats()
        for endpoint, stats in api_stats.get("endpoints", {}).items():
            if stats.get("error_rate", 0) > self.thresholds["error_rate"]:
                await self._create_alert(
                    "HIGH_ERROR_RATE",
                    f"Error rate for {endpoint} is {stats['error_rate']:.2%}",
                    "critical",
                )

            if stats.get("p99", 0) > self.thresholds["response_time_p99"]:
                await self._create_alert(
                    "SLOW_RESPONSE",
                    f"P99 response time for {endpoint} is {stats['p99']:.2f}s",
                    "warning",
                )

    async def _create_alert(self, alert_type: str, message: str, severity: str):
        """알림 생성"""
        alert = {
            "id": f"{alert_type}_{int(time.time())}",
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "status": "active",
        }

        self.alerts.append(alert)

        # 로그 출력
        if severity == "critical":
            logger.critical(f"ALERT: {message}")
        else:
            logger.warning(f"ALERT: {message}")

        # 캐시에 저장
        await integrated_cache.set(
            f"alert:{alert['id']}", alert, ttl=3600  # 1시간 보관
        )

        # TODO: 실제 알림 발송 (이메일, Slack 등)

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """활성 알림 조회"""
        return [a for a in self.alerts if a["status"] == "active"]


# 전역 알림 관리자
alert_manager = AlertManager()


# 백그라운드 모니터링 태스크
async def background_monitoring():
    """백그라운드 모니터링 태스크"""
    while True:
        try:
            # 30초마다 시스템 체크
            await asyncio.sleep(30)

            # 알림 체크
            await alert_manager.check_and_alert()

            # 시스템 메트릭 캐싱
            system_metrics = system_monitor.get_system_metrics()
            await integrated_cache.set("system_metrics:latest", system_metrics, ttl=60)

        except Exception as e:
            logger.error(f"Background monitoring error: {e}")
            await asyncio.sleep(60)  # 오류 시 1분 대기
