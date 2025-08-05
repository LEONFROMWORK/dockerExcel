"""
Security Middleware
보안 미들웨어 - OWASP 권장사항 적용
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from typing import Dict, Any, List
import re
from datetime import datetime, timedelta
import logging
from app.core.config import settings
from app.core.responses import ResponseBuilder

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """통합 보안 미들웨어"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.blocked_ips: Dict[str, datetime] = {}
        self.request_counts: Dict[str, List[float]] = {}

        # 보안 헤더 설정
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

        # SQL Injection 패턴
        self.sql_injection_patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
            r"(--|#|\/\*|\*\/)",
            r"(\bor\b\s*\d+\s*=\s*\d+)",
            r"(\band\b\s*\d+\s*=\s*\d+)",
            r"(';|';--|';\s*\/\*)",
            r"(\bwaitfor\s+delay\b)",
            r"(\bconvert\s*\()",
            r"(\bcast\s*\()",
        ]

        # XSS 패턴
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<img[^>]*onerror\s*=",
            r"<svg[^>]*onload\s*=",
        ]

        # Path Traversal 패턴
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"\.\.%2f",
            r"\.\.%5c",
        ]

    async def dispatch(self, request: Request, call_next):
        """모든 요청에 대한 보안 검사"""
        start_time = time.time()

        try:
            # 1. IP 차단 확인
            client_ip = self._get_client_ip(request)
            if self._is_ip_blocked(client_ip):
                return self._blocked_response()

            # 2. Rate Limiting 확인
            if not await self._check_rate_limit(client_ip, request.url.path):
                return self._rate_limit_response()

            # 3. 입력 검증
            if not await self._validate_input(request):
                return self._invalid_input_response()

            # 4. CSRF 토큰 검증 (POST, PUT, DELETE)
            if request.method in ["POST", "PUT", "DELETE"]:
                if not await self._validate_csrf_token(request):
                    return self._csrf_error_response()

            # 5. 파일 업로드 검증
            if "multipart/form-data" in request.headers.get("content-type", ""):
                if not await self._validate_file_upload(request):
                    return self._invalid_file_response()

            # 요청 처리
            response = await call_next(request)

            # 보안 헤더 추가
            for header, value in self.security_headers.items():
                response.headers[header] = value

            # 응답 시간 로깅
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)

            # 의심스러운 활동 로깅
            if process_time > 10:  # 10초 이상 걸린 요청
                logger.warning(
                    f"Slow request: {request.url.path} took {process_time:.2f}s from {client_ip}"
                )

            return response

        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}")
            return self._error_response(str(e))

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출"""
        # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 환경)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 직접 연결
        return request.client.host if request.client else "unknown"

    def _is_ip_blocked(self, ip: str) -> bool:
        """IP 차단 확인"""
        if ip in self.blocked_ips:
            block_time = self.blocked_ips[ip]
            # 1시간 후 차단 해제
            if datetime.now() - block_time > timedelta(hours=1):
                del self.blocked_ips[ip]
                return False
            return True
        return False

    async def _check_rate_limit(self, ip: str, path: str) -> bool:
        """Rate Limiting 확인 (고급 rate limiter 사용)"""
        # 정적 파일은 제외
        if path.startswith("/static/") or path.startswith("/docs"):
            return True

        # 고급 rate limiter 사용
        from app.services.rate_limiter import rate_limiter, RateLimitTier

        # IP 기반 rate limiting
        allowed, info = await rate_limiter.check_rate_limit(
            identifier=ip, endpoint=path, tier=RateLimitTier.FREE  # 기본 티어
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {ip} on path: {path}")
            if info and info.get("retry_after", 0) > 300:  # 5분 이상 대기 필요 시
                self.blocked_ips[ip] = datetime.now()
            return False

        return True

    async def _validate_input(self, request: Request) -> bool:
        """입력 검증"""
        # URL 파라미터 검증
        for param, value in request.query_params.items():
            if not self._is_safe_input(str(value)):
                logger.warning(f"Unsafe query parameter: {param}={value}")
                return False

        # Path 파라미터 검증
        for param, value in request.path_params.items():
            if not self._is_safe_path(str(value)):
                logger.warning(f"Unsafe path parameter: {param}={value}")
                return False

        # Body 검증 (JSON)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.body()
                    if body and not self._is_safe_json(body.decode()):
                        logger.warning("Unsafe JSON body detected")
                        return False
                except Exception:
                    pass

        return True

    def _is_safe_input(self, value: str) -> bool:
        """입력값 안전성 검사"""
        # SQL Injection 패턴 검사
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False

        # XSS 패턴 검사
        for pattern in self.xss_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False

        return True

    def _is_safe_path(self, value: str) -> bool:
        """경로 안전성 검사"""
        # Path Traversal 패턴 검사
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False

        # 추가 경로 검증
        if ".." in value or "~" in value:
            return False

        return True

    def _is_safe_json(self, json_str: str) -> bool:
        """JSON 안전성 검사"""
        # 간단한 XSS 패턴 검사
        dangerous_patterns = ["<script", "javascript:", "onerror=", "onclick="]
        json_lower = json_str.lower()

        for pattern in dangerous_patterns:
            if pattern in json_lower:
                return False

        return True

    async def _validate_csrf_token(self, request: Request) -> bool:
        """CSRF 토큰 검증"""
        # API 엔드포인트는 CSRF 검증 제외 (JWT 사용 시)
        if request.url.path.startswith("/api/"):
            return True

        # 헤더 또는 쿠키에서 CSRF 토큰 확인
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            csrf_token = request.cookies.get("csrf_token")

        if not csrf_token:
            return False

        # 세션의 CSRF 토큰과 비교 (실제 구현 시 세션 스토어 사용)
        # 여기서는 간단한 검증만 수행
        return len(csrf_token) >= 32

    async def _validate_file_upload(self, request: Request) -> bool:
        """파일 업로드 검증"""
        # Content-Type 확인
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            return True

        # 파일 크기 제한 확인 (헤더에서)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                # 50MB 제한
                if size > 50 * 1024 * 1024:
                    logger.warning(f"File too large: {size} bytes")
                    return False
            except ValueError:
                return False

        return True

    def _blocked_response(self) -> JSONResponse:
        """차단 응답"""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseBuilder.error(
                message="Access denied", error_code="IP_BLOCKED"
            ),
        )

    def _rate_limit_response(self) -> JSONResponse:
        """Rate limit 응답"""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=ResponseBuilder.error(
                message="Too many requests", error_code="RATE_LIMIT_EXCEEDED"
            ),
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + 60)),
            },
        )

    def _invalid_input_response(self) -> JSONResponse:
        """잘못된 입력 응답"""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseBuilder.error(
                message="Invalid input detected", error_code="INVALID_INPUT"
            ),
        )

    def _csrf_error_response(self) -> JSONResponse:
        """CSRF 오류 응답"""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseBuilder.error(
                message="CSRF token validation failed", error_code="CSRF_ERROR"
            ),
        )

    def _invalid_file_response(self) -> JSONResponse:
        """잘못된 파일 응답"""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseBuilder.error(
                message="Invalid file upload", error_code="INVALID_FILE"
            ),
        )

    def _error_response(self, error: str) -> JSONResponse:
        """일반 오류 응답"""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseBuilder.error(
                message="Security check failed",
                error_code="SECURITY_ERROR",
                details={"error": error} if settings.DEBUG else None,
            ),
        )


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API 키 인증 미들웨어"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.api_keys: Dict[str, Dict[str, Any]] = {}  # 실제로는 DB에서 로드

        # 데모용 API 키
        if settings.DEBUG:
            self.api_keys["demo_key_123"] = {
                "name": "Demo Client",
                "rate_limit": 100,
                "expires_at": None,
            }

    async def dispatch(self, request: Request, call_next):
        """API 키 검증"""
        # 공개 엔드포인트는 제외
        public_paths = ["/docs", "/openapi.json", "/health", "/"]
        if request.url.path in public_paths:
            return await call_next(request)

        # API 키 추출
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            api_key = request.query_params.get("api_key")

        if not api_key or api_key not in self.api_keys:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=ResponseBuilder.unauthorized("Invalid or missing API key"),
            )

        # API 키 정보 확인
        key_info = self.api_keys[api_key]

        # 만료 확인
        if key_info.get("expires_at") and datetime.now() > key_info["expires_at"]:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=ResponseBuilder.unauthorized("API key expired"),
            )

        # 요청에 API 키 정보 추가
        request.state.api_key_info = key_info

        return await call_next(request)
