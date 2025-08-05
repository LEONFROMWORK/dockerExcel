"""
Rate Limiter Service
속도 제한 서비스 - Redis 기반 분산 환경 지원
"""

import time
from typing import Dict, Any, Optional, Tuple
import logging
from enum import Enum
from app.core.integrated_cache import integrated_cache

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate Limiting 전략"""

    FIXED_WINDOW = "fixed_window"  # 고정 시간 창
    SLIDING_WINDOW = "sliding_window"  # 슬라이딩 윈도우
    TOKEN_BUCKET = "token_bucket"  # 토큰 버킷
    LEAKY_BUCKET = "leaky_bucket"  # 리키 버킷


class RateLimitTier(Enum):
    """사용자 티어별 제한"""

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    ADMIN = "admin"


class RateLimiter:
    """Rate Limiting 구현"""

    # 티어별 기본 제한
    TIER_LIMITS = {
        RateLimitTier.FREE: {
            "requests_per_minute": 30,
            "requests_per_hour": 500,
            "requests_per_day": 5000,
            "file_uploads_per_hour": 10,
            "ai_requests_per_hour": 20,
        },
        RateLimitTier.BASIC: {
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
            "requests_per_day": 10000,
            "file_uploads_per_hour": 30,
            "ai_requests_per_hour": 50,
        },
        RateLimitTier.PREMIUM: {
            "requests_per_minute": 120,
            "requests_per_hour": 3000,
            "requests_per_day": 30000,
            "file_uploads_per_hour": 100,
            "ai_requests_per_hour": 200,
        },
        RateLimitTier.ENTERPRISE: {
            "requests_per_minute": 300,
            "requests_per_hour": 10000,
            "requests_per_day": 100000,
            "file_uploads_per_hour": 500,
            "ai_requests_per_hour": 1000,
        },
        RateLimitTier.ADMIN: {
            # 관리자는 제한 없음
            "requests_per_minute": float("inf"),
            "requests_per_hour": float("inf"),
            "requests_per_day": float("inf"),
            "file_uploads_per_hour": float("inf"),
            "ai_requests_per_hour": float("inf"),
        },
    }

    # 엔드포인트별 가중치
    ENDPOINT_WEIGHTS = {
        "/api/v1/excel/analyze": 3,  # 무거운 작업
        "/api/v1/excel/detect-errors": 2,
        "/api/v1/ai/chat": 2,
        "/api/v1/excel/upload": 5,
        "/api/v1/insights/get-insights": 2,
        # 기본값
        "default": 1,
    }

    def __init__(self, strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW):
        self.strategy = strategy
        self.cache = integrated_cache

    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str = "default",
        tier: RateLimitTier = RateLimitTier.FREE,
        custom_limits: Optional[Dict[str, int]] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Rate limit 확인

        Args:
            identifier: 사용자 식별자 (IP, API key, user ID)
            endpoint: API 엔드포인트
            tier: 사용자 티어
            custom_limits: 커스텀 제한 (있을 경우)

        Returns:
            (allowed, info) 튜플
            - allowed: 요청 허용 여부
            - info: 제한 정보 (남은 횟수, 리셋 시간 등)
        """
        try:
            # 제한 설정 가져오기
            limits = custom_limits or self.TIER_LIMITS.get(
                tier, self.TIER_LIMITS[RateLimitTier.FREE]
            )

            # 엔드포인트 가중치 적용
            weight = self.ENDPOINT_WEIGHTS.get(
                endpoint, self.ENDPOINT_WEIGHTS["default"]
            )

            # 전략별 처리
            if self.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return await self._sliding_window_check(identifier, limits, weight)
            elif self.strategy == RateLimitStrategy.FIXED_WINDOW:
                return await self._fixed_window_check(identifier, limits, weight)
            elif self.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return await self._token_bucket_check(identifier, limits, weight)
            else:
                return await self._leaky_bucket_check(identifier, limits, weight)

        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            # 오류 시 요청 허용 (fail open)
            return True, None

    async def _sliding_window_check(
        self, identifier: str, limits: Dict[str, int], weight: int
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """슬라이딩 윈도우 방식 구현"""
        current_time = time.time()

        # 분당 제한 확인
        minute_key = f"rate_limit:sliding:{identifier}:minute"
        minute_limit = limits.get("requests_per_minute", 60)

        # 최근 1분간 요청 기록 가져오기
        minute_data = await self.cache.get(minute_key) or []

        # 1분 이전 기록 제거
        minute_data = [t for t in minute_data if current_time - t < 60]

        # 가중치 적용한 요청 수 계산
        weighted_count = sum(1 for _ in minute_data) * weight

        if weighted_count >= minute_limit:
            # 제한 초과
            reset_time = min(minute_data) + 60 if minute_data else current_time + 60
            return False, {
                "limit": minute_limit,
                "remaining": 0,
                "reset_time": int(reset_time),
                "retry_after": int(reset_time - current_time),
            }

        # 요청 기록 추가
        minute_data.append(current_time)
        await self.cache.set(minute_key, minute_data, ttl=70)  # 70초 보관

        # 시간당 제한도 확인
        hour_key = f"rate_limit:sliding:{identifier}:hour"
        hour_limit = limits.get("requests_per_hour", 1000)
        hour_data = await self.cache.get(hour_key) or []
        hour_data = [t for t in hour_data if current_time - t < 3600]

        if len(hour_data) * weight >= hour_limit:
            reset_time = min(hour_data) + 3600 if hour_data else current_time + 3600
            return False, {
                "limit": hour_limit,
                "remaining": 0,
                "reset_time": int(reset_time),
                "retry_after": int(reset_time - current_time),
            }

        hour_data.append(current_time)
        await self.cache.set(hour_key, hour_data, ttl=3700)

        return True, {
            "limit": minute_limit,
            "remaining": minute_limit - weighted_count,
            "reset_time": int(current_time + 60),
        }

    async def _fixed_window_check(
        self, identifier: str, limits: Dict[str, int], weight: int
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """고정 시간 창 방식 구현"""
        current_time = int(time.time())

        # 분 단위 창
        minute_window = current_time // 60
        minute_key = f"rate_limit:fixed:{identifier}:{minute_window}"
        minute_limit = limits.get("requests_per_minute", 60)

        # 현재 창의 요청 수
        current_count = await self.cache.get(minute_key) or 0

        if current_count * weight >= minute_limit:
            return False, {
                "limit": minute_limit,
                "remaining": 0,
                "reset_time": (minute_window + 1) * 60,
                "retry_after": (minute_window + 1) * 60 - current_time,
            }

        # 카운터 증가
        await self.cache.set(minute_key, current_count + 1, ttl=70)

        return True, {
            "limit": minute_limit,
            "remaining": minute_limit - (current_count + 1) * weight,
            "reset_time": (minute_window + 1) * 60,
        }

    async def _token_bucket_check(
        self, identifier: str, limits: Dict[str, int], weight: int
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """토큰 버킷 방식 구현"""
        current_time = time.time()
        bucket_key = f"rate_limit:token:{identifier}"

        # 버킷 정보 가져오기
        bucket_data = await self.cache.get(bucket_key) or {
            "tokens": limits.get("requests_per_minute", 60),
            "last_refill": current_time,
        }

        # 토큰 리필
        max_tokens = limits.get("requests_per_minute", 60)
        refill_rate = max_tokens / 60.0  # 초당 리필 속도
        elapsed = current_time - bucket_data["last_refill"]

        # 새로운 토큰 추가
        new_tokens = min(max_tokens, bucket_data["tokens"] + (elapsed * refill_rate))

        if new_tokens < weight:
            # 토큰 부족
            tokens_needed = weight - new_tokens
            wait_time = tokens_needed / refill_rate

            return False, {
                "limit": max_tokens,
                "remaining": int(new_tokens),
                "reset_time": int(current_time + wait_time),
                "retry_after": int(wait_time),
            }

        # 토큰 소비
        bucket_data["tokens"] = new_tokens - weight
        bucket_data["last_refill"] = current_time
        await self.cache.set(bucket_key, bucket_data, ttl=120)

        return True, {
            "limit": max_tokens,
            "remaining": int(bucket_data["tokens"]),
            "reset_time": int(current_time + 60),
        }

    async def _leaky_bucket_check(
        self, identifier: str, limits: Dict[str, int], weight: int
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """리키 버킷 방식 구현"""
        current_time = time.time()
        bucket_key = f"rate_limit:leaky:{identifier}"

        # 버킷 정보
        bucket_data = await self.cache.get(bucket_key) or {
            "water_level": 0,
            "last_leak": current_time,
        }

        # 버킷 용량과 누출 속도
        capacity = limits.get("requests_per_minute", 60)
        leak_rate = capacity / 60.0  # 초당 누출 속도

        # 누출 처리
        elapsed = current_time - bucket_data["last_leak"]
        leaked = elapsed * leak_rate
        bucket_data["water_level"] = max(0, bucket_data["water_level"] - leaked)

        # 요청 추가 가능 여부 확인
        if bucket_data["water_level"] + weight > capacity:
            # 버킷 넘침
            overflow = bucket_data["water_level"] + weight - capacity
            wait_time = overflow / leak_rate

            return False, {
                "limit": capacity,
                "remaining": int(capacity - bucket_data["water_level"]),
                "reset_time": int(current_time + wait_time),
                "retry_after": int(wait_time),
            }

        # 물 추가
        bucket_data["water_level"] += weight
        bucket_data["last_leak"] = current_time
        await self.cache.set(bucket_key, bucket_data, ttl=120)

        return True, {
            "limit": capacity,
            "remaining": int(capacity - bucket_data["water_level"]),
            "reset_time": int(current_time + 60),
        }

    async def get_user_tier(self, user_id: Optional[str]) -> RateLimitTier:
        """사용자 티어 조회"""
        if not user_id:
            return RateLimitTier.FREE

        # 캐시에서 티어 정보 조회
        tier_key = f"user_tier:{user_id}"
        cached_tier = await self.cache.get(tier_key)

        if cached_tier:
            try:
                return RateLimitTier(cached_tier)
            except ValueError:
                pass

        # TODO: 실제 구현 시 데이터베이스에서 조회
        # 여기서는 기본값 반환
        return RateLimitTier.FREE

    async def reset_rate_limit(self, identifier: str):
        """특정 사용자의 rate limit 초기화"""
        patterns = [f"rate_limit:*:{identifier}:*", f"rate_limit:*:{identifier}"]

        for pattern in patterns:
            # Redis에서 패턴 매칭으로 키 삭제
            # 실제 구현 시 Redis SCAN 명령어 사용
            pass

        logger.info(f"Rate limit reset for: {identifier}")

    def get_headers(self, info: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """Rate limit 정보를 HTTP 헤더로 변환"""
        if not info:
            return {}

        headers = {}

        if "limit" in info:
            headers["X-RateLimit-Limit"] = str(info["limit"])

        if "remaining" in info:
            headers["X-RateLimit-Remaining"] = str(info["remaining"])

        if "reset_time" in info:
            headers["X-RateLimit-Reset"] = str(info["reset_time"])

        if "retry_after" in info and info["retry_after"] > 0:
            headers["Retry-After"] = str(info["retry_after"])

        return headers


# 싱글톤 인스턴스
rate_limiter = RateLimiter()


# 데코레이터
def rate_limit(
    tier: RateLimitTier = RateLimitTier.FREE,
    endpoint: Optional[str] = None,
    custom_limits: Optional[Dict[str, int]] = None,
):
    """Rate limiting 데코레이터"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 요청 객체에서 식별자 추출
            request = kwargs.get("request") or (args[0] if args else None)
            if not request:
                return await func(*args, **kwargs)

            # 식별자 결정 (IP 또는 API 키)
            identifier = request.headers.get("X-API-Key")
            if not identifier:
                identifier = request.client.host if request.client else "unknown"

            # Rate limit 확인
            allowed, info = await rate_limiter.check_rate_limit(
                identifier=identifier,
                endpoint=endpoint or request.url.path,
                tier=tier,
                custom_limits=custom_limits,
            )

            # 헤더 추가
            if hasattr(request, "state"):
                request.state.rate_limit_headers = rate_limiter.get_headers(info)

            if not allowed:
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers=rate_limiter.get_headers(info),
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
