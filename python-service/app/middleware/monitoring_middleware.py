"""
모니터링 미들웨어
FastAPI 애플리케이션의 성능과 요청을 모니터링
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import psutil
import os

logger = logging.getLogger(__name__)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """
    성능 모니터링 및 로깅 미들웨어
    모든 HTTP 요청의 성능 메트릭을 수집하고 로깅
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.process = psutil.Process(os.getpid())

        # 성능 통계 카운터
        self.request_count = 0
        self.total_response_time = 0.0
        self.error_count = 0

        # 메모리 임계값 (MB)
        self.memory_warning_threshold = 500
        self.memory_critical_threshold = 1000

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 모니터링"""

        # 요청 시작 정보 수집
        start_time = time.time()
        request_start_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        self.request_count += 1

        # 요청 기본 정보 로깅
        logger.info(f"[{self.request_count}] {request.method} {request.url.path}")
        if hasattr(request, "client") and request.client:
            logger.debug(f"Client: {request.client.host}:{request.client.port}")

        # Content-Length 확인 (파일 업로드 등)
        content_length = request.headers.get("content-length")
        if content_length:
            file_size_mb = int(content_length) / 1024 / 1024
            if file_size_mb > 1:  # 1MB 이상인 경우 로깅
                logger.info(f"요청 크기: {file_size_mb:.2f} MB")

        response = None
        error_occurred = False

        try:
            # 실제 요청 처리
            response = await call_next(request)

        except Exception as e:
            error_occurred = True
            self.error_count += 1

            # 오류 상세 로깅
            logger.error("요청 처리 중 오류 발생:")
            logger.error(f"  URL: {request.method} {request.url}")
            logger.error(f"  오류: {str(e)}")
            logger.error(f"  오류 타입: {type(e).__name__}")

            # 500 에러 응답 생성
            from fastapi.responses import JSONResponse

            response = JSONResponse(
                status_code=500,
                content={
                    "error": True,
                    "message": "내부 서버 오류가 발생했습니다",
                    "request_id": str(self.request_count),
                },
            )

        finally:
            # 성능 메트릭 수집
            end_time = time.time()
            response_time = end_time - start_time
            self.total_response_time += response_time

            # 메모리 사용량 체크
            current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - request_start_memory

            # 응답 기본 정보 로깅
            status_code = response.status_code if response else 500
            logger.info(
                f"[{self.request_count}] 응답: {status_code} ({response_time:.3f}초)"
            )

            # 상세 성능 메트릭 로깅
            if response_time > 1.0:  # 1초 이상 소요된 요청
                logger.warning(f"느린 응답 감지: {response_time:.3f}초")

            if memory_increase > 10:  # 10MB 이상 메모리 증가
                logger.warning(f"메모리 증가 감지: +{memory_increase:.2f} MB")

            # 메모리 임계값 체크
            if current_memory > self.memory_critical_threshold:
                logger.critical(f"메모리 사용량 위험: {current_memory:.2f} MB")
            elif current_memory > self.memory_warning_threshold:
                logger.warning(f"메모리 사용량 주의: {current_memory:.2f} MB")

            # 성능 통계 로깅 (매 100번째 요청마다)
            if self.request_count % 100 == 0:
                self._log_performance_stats()

            # 상세 성능 메트릭을 별도 파일에 기록
            self._log_detailed_metrics(
                request=request,
                response_time=response_time,
                status_code=status_code,
                memory_used=current_memory,
                memory_increase=memory_increase,
                error_occurred=error_occurred,
            )

        return response

    def _log_performance_stats(self):
        """전체 성능 통계 로깅"""
        avg_response_time = self.total_response_time / max(self.request_count, 1)
        error_rate = (self.error_count / max(self.request_count, 1)) * 100

        logger.info("=== 성능 통계 ===")
        logger.info(f"총 요청 수: {self.request_count}")
        logger.info(f"평균 응답 시간: {avg_response_time:.3f}초")
        logger.info(f"오류율: {error_rate:.1f}%")
        logger.info(
            f"현재 메모리: {self.process.memory_info().rss / 1024 / 1024:.2f} MB"
        )

        # CPU 사용률
        try:
            cpu_percent = self.process.cpu_percent()
            logger.info(f"CPU 사용률: {cpu_percent:.1f}%")
        except (KeyError, IndexError, AttributeError):
            pass

    def _log_detailed_metrics(
        self,
        request: Request,
        response_time: float,
        status_code: int,
        memory_used: float,
        memory_increase: float,
        error_occurred: bool,
    ):
        """상세 성능 메트릭을 별도 로그에 기록"""

        # 성능 로그 파일에 JSON 형태로 기록
        try:
            from app.core.logging_config import log_performance_metrics

            # URL 경로에서 민감한 정보 제거
            safe_path = self._sanitize_path(str(request.url.path))

            log_performance_metrics(
                operation="http_request",
                duration=response_time,
                method=request.method,
                path=safe_path,
                status_code=status_code,
                memory_mb=round(memory_used, 2),
                memory_increase_mb=round(memory_increase, 2),
                error=error_occurred,
                request_id=self.request_count,
            )

        except Exception as e:
            logger.debug(f"성능 메트릭 로깅 실패: {e}")

    def _sanitize_path(self, path: str) -> str:
        """URL 경로에서 민감한 정보 제거"""
        import re

        # 파일 ID나 사용자 ID 등을 마스킹
        path = re.sub(r"/\d+", "/{id}", path)
        path = re.sub(r"/[a-f0-9-]{36}", "/{uuid}", path)  # UUID 패턴

        return path


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """
    헬스체크 및 시스템 상태 모니터링 미들웨어
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.start_time = time.time()
        self.process = psutil.Process(os.getpid())

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 헬스체크 엔드포인트 처리
        if request.url.path == "/health":
            return await self._handle_health_check()

        # 시스템 상태 엔드포인트 처리
        if request.url.path == "/system-status":
            return await self._handle_system_status()

        # 일반 요청은 다음 미들웨어로 전달
        return await call_next(request)

    async def _handle_health_check(self) -> Response:
        """기본 헬스체크 응답"""
        from fastapi.responses import JSONResponse

        uptime = time.time() - self.start_time

        health_data = {
            "status": "healthy",
            "uptime_seconds": round(uptime, 2),
            "timestamp": time.time(),
            "service": "excel-ai-service",
        }

        return JSONResponse(content=health_data, status_code=200)

    async def _handle_system_status(self) -> Response:
        """상세 시스템 상태 응답"""
        from fastapi.responses import JSONResponse

        try:
            # 시스템 리소스 정보
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            # 디스크 사용량
            disk_usage = psutil.disk_usage("/")
            disk_free_gb = disk_usage.free / 1024 / 1024 / 1024

            status_data = {
                "status": "operational",
                "uptime_seconds": round(time.time() - self.start_time, 2),
                "memory": {
                    "used_mb": round(memory_mb, 2),
                    "available_mb": round(
                        psutil.virtual_memory().available / 1024 / 1024, 2
                    ),
                },
                "disk": {"free_gb": round(disk_free_gb, 2)},
                "process": {
                    "pid": self.process.pid,
                    "threads": self.process.num_threads(),
                },
                "timestamp": time.time(),
            }

            # CPU 사용률 (부하가 클 수 있으므로 선택적)
            try:
                cpu_percent = self.process.cpu_percent(interval=0.1)
                status_data["cpu_percent"] = round(cpu_percent, 1)
            except (KeyError, IndexError, AttributeError):
                pass

            return JSONResponse(content=status_data, status_code=200)

        except Exception as e:
            logger.error(f"시스템 상태 조회 실패: {e}")

            error_data = {
                "status": "error",
                "message": "시스템 상태를 조회할 수 없습니다",
                "error": str(e),
                "timestamp": time.time(),
            }

            return JSONResponse(content=error_data, status_code=500)
