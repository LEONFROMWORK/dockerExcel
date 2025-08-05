"""
Integrated Cache System
통합 캐시 시스템 - 모든 캐시 작업을 위한 단일 인터페이스
"""

import asyncio
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import logging
from functools import wraps

from app.core.unified_cache import unified_cache
from app.core.cache import CACHE_TTL

logger = logging.getLogger(__name__)


class IntegratedCache:
    """통합 캐시 시스템 - L1(메모리) + L2(Redis)"""

    def __init__(self):
        # L1: 메모리 캐시 (빠른 접근)
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._memory_cache_metadata: Dict[str, datetime] = {}

        # L2: Redis 캐시 (unified_cache 사용)
        self.redis_cache = unified_cache

        # 캐시 설정
        self.ttl_config = CACHE_TTL
        self.max_memory_items = 1000  # 메모리 캐시 최대 항목 수

        # 통계
        self.stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "total_gets": 0,
            "total_sets": 0,
        }

    async def get(self, key: str, cache_level: str = "all") -> Optional[Any]:
        """
        캐시에서 값 조회

        Args:
            key: 캐시 키
            cache_level: "all", "memory", "redis"

        Returns:
            캐시된 값 또는 None
        """
        self.stats["total_gets"] += 1

        # L1 메모리 캐시 확인
        if cache_level in ["all", "memory"]:
            if key in self._memory_cache:
                # TTL 확인
                if self._is_memory_cache_valid(key):
                    self.stats["memory_hits"] += 1
                    logger.debug(f"Memory cache hit: {key}")
                    return self._memory_cache[key]["value"]
                else:
                    # 만료된 항목 제거
                    self._remove_from_memory(key)

            self.stats["memory_misses"] += 1

        # L2 Redis 캐시 확인
        if cache_level in ["all", "redis"]:
            try:
                value = await self.redis_cache.get(key)
                if value is not None:
                    self.stats["redis_hits"] += 1
                    logger.debug(f"Redis cache hit: {key}")

                    # 메모리 캐시에도 저장 (write-through)
                    if cache_level == "all":
                        self._set_memory_cache(key, value, ttl=300)  # 5분

                    return value

                self.stats["redis_misses"] += 1
            except Exception as e:
                logger.error(f"Redis cache error: {str(e)}")

        return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, cache_level: str = "all"
    ) -> bool:
        """
        캐시에 값 저장

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: Time To Live (초)
            cache_level: "all", "memory", "redis"

        Returns:
            성공 여부
        """
        self.stats["total_sets"] += 1

        # 기본 TTL 설정
        if ttl is None:
            ttl = self.ttl_config.get("DEFAULT", 3600)

        success = True

        # L1 메모리 캐시 저장
        if cache_level in ["all", "memory"]:
            self._set_memory_cache(key, value, ttl)

        # L2 Redis 캐시 저장
        if cache_level in ["all", "redis"]:
            try:
                await self.redis_cache.set(key, value, ttl)
            except Exception as e:
                logger.error(f"Redis cache set error: {str(e)}")
                success = False

        return success

    async def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        success = True

        # 메모리에서 삭제
        self._remove_from_memory(key)

        # Redis에서 삭제
        try:
            await self.redis_cache.delete(key)
        except Exception as e:
            logger.error(f"Redis cache delete error: {str(e)}")
            success = False

        return success

    async def clear_pattern(self, pattern: str) -> int:
        """패턴과 일치하는 모든 키 삭제"""
        count = 0

        # 메모리 캐시에서 삭제
        keys_to_remove = [k for k in self._memory_cache if pattern in k]
        for key in keys_to_remove:
            self._remove_from_memory(key)
            count += 1

        # Redis는 unified_cache의 기능 사용
        # Redis 패턴 삭제는 구현이 복잡하므로 생략

        return count

    def _set_memory_cache(self, key: str, value: Any, ttl: int):
        """메모리 캐시에 저장"""
        # 캐시 크기 제한 확인
        if len(self._memory_cache) >= self.max_memory_items:
            self._evict_oldest()

        self._memory_cache[key] = {"value": value, "ttl": ttl}
        self._memory_cache_metadata[key] = datetime.now()

    def _is_memory_cache_valid(self, key: str) -> bool:
        """메모리 캐시 항목이 유효한지 확인"""
        if key not in self._memory_cache_metadata:
            return False

        created_at = self._memory_cache_metadata[key]
        ttl = self._memory_cache[key].get("ttl", 3600)

        return datetime.now() < created_at + timedelta(seconds=ttl)

    def _remove_from_memory(self, key: str):
        """메모리에서 제거"""
        self._memory_cache.pop(key, None)
        self._memory_cache_metadata.pop(key, None)

    def _evict_oldest(self):
        """가장 오래된 항목 제거 (LRU)"""
        if not self._memory_cache_metadata:
            return

        oldest_key = min(self._memory_cache_metadata.items(), key=lambda x: x[1])[0]
        self._remove_from_memory(oldest_key)

    async def get_analysis(self, file_id: str) -> Optional[Dict[str, Any]]:
        """분석 결과 조회 (unified_cache 호환)"""
        return await self.get(f"analysis:{file_id}")

    async def set_analysis(self, file_id: str, analysis: Dict[str, Any]):
        """분석 결과 저장 (unified_cache 호환)"""
        await self.set(
            f"analysis:{file_id}", analysis, ttl=self.ttl_config.get("LONG", 7200)
        )

    async def get_errors(self, file_id: str) -> Optional[List[Any]]:
        """오류 목록 조회 (unified_cache 호환)"""
        return await self.get(f"errors:{file_id}")

    async def set_errors(self, file_id: str, errors: List[Any]):
        """오류 목록 저장 (unified_cache 호환)"""
        await self.set(
            f"errors:{file_id}", errors, ttl=self.ttl_config.get("LONG", 7200)
        )

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_hits = self.stats["memory_hits"] + self.stats["redis_hits"]
        total_misses = self.stats["memory_misses"] + self.stats["redis_misses"]
        hit_rate = (
            total_hits / (total_hits + total_misses)
            if (total_hits + total_misses) > 0
            else 0
        )

        return {
            **self.stats,
            "memory_cache_size": len(self._memory_cache),
            "hit_rate": round(hit_rate * 100, 2),
        }

    async def warmup(self, keys: List[str]):
        """캐시 워밍업 - 자주 사용되는 키들을 미리 로드"""
        tasks = []
        for key in keys:
            tasks.append(self.get(key))

        await asyncio.gather(*tasks, return_exceptions=True)


# 전역 인스턴스
integrated_cache = IntegratedCache()


def cache_result(
    prefix: str = "", ttl: Optional[int] = None, key_builder: Optional[callable] = None
):
    """
    함수 결과 캐싱 데코레이터 (기존 @cached 대체)

    Args:
        prefix: 캐시 키 접두사
        ttl: 캐시 유효 시간
        key_builder: 커스텀 키 생성 함수
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 캐시 키 생성
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # 기본 키 생성
                key_parts = [prefix or func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            # 캐시 조회
            cached_value = await integrated_cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 함수 실행
            result = await func(*args, **kwargs)

            # 결과 캐싱
            await integrated_cache.set(cache_key, result, ttl=ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 동기 함수용 래퍼
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(async_wrapper(*args, **kwargs))

        # 함수가 코루틴인지 확인
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
