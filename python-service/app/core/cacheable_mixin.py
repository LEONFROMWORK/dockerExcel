"""
Cacheable Mixin
캐싱 기능을 제공하는 믹스인 클래스 - DRY 원칙 적용
"""

from typing import Any, Optional, Dict, Callable
from datetime import datetime
import json
import hashlib
import logging
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


class CacheEntry:
    """캐시 엔트리"""

    def __init__(self, value: Any, ttl: int = 3600):
        self.value = value
        self.created_at = datetime.now()
        self.ttl = ttl
        self.hit_count = 0

    def is_expired(self) -> bool:
        """만료 여부 확인"""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl

    def get_value(self) -> Any:
        """값 가져오기 (hit count 증가)"""
        self.hit_count += 1
        return self.value


class CacheableMixin:
    """캐싱 기능을 제공하는 믹스인"""

    def __init__(self):
        # 믹스인이므로 super().__init__() 호출
        super().__init__()
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_stats = {"hits": 0, "misses": 0, "evictions": 0}
        self._max_cache_size = 1000
        self._default_ttl = 3600  # 1시간

    # === 캐시 기본 메서드 ===

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """캐시에서 값 가져오기"""
        cache_key = self._normalize_cache_key(key)

        if cache_key in self._cache:
            entry = self._cache[cache_key]

            if entry.is_expired():
                # 만료된 엔트리 제거
                del self._cache[cache_key]
                self._cache_stats["misses"] += 1
                logger.debug(f"캐시 미스 (만료): {cache_key}")
                return None

            self._cache_stats["hits"] += 1
            logger.debug(f"캐시 히트: {cache_key} (hit count: {entry.hit_count})")
            return entry.get_value()

        self._cache_stats["misses"] += 1
        logger.debug(f"캐시 미스: {cache_key}")
        return None

    def _save_to_cache(self, key: str, value: Any, ttl: Optional[int] = None):
        """캐시에 값 저장"""
        cache_key = self._normalize_cache_key(key)

        # 캐시 크기 제한 확인
        if len(self._cache) >= self._max_cache_size:
            self._evict_lru()

        ttl = ttl or self._default_ttl
        self._cache[cache_key] = CacheEntry(value, ttl)
        logger.debug(f"캐시 저장: {cache_key} (TTL: {ttl}초)")

    def _invalidate_cache(self, pattern: Optional[str] = None):
        """캐시 무효화"""
        if pattern:
            # 패턴에 맞는 키만 삭제
            keys_to_delete = [key for key in self._cache.keys() if pattern in key]
            for key in keys_to_delete:
                del self._cache[key]
            logger.info(
                f"캐시 무효화: {len(keys_to_delete)}개 엔트리 (패턴: {pattern})"
            )
        else:
            # 전체 캐시 클리어
            self._cache.clear()
            logger.info("전체 캐시 클리어")

    def _evict_lru(self):
        """LRU (Least Recently Used) 방식으로 캐시 정리"""
        if not self._cache:
            return

        # hit_count가 가장 적은 엔트리 찾기
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].hit_count)

        del self._cache[lru_key]
        self._cache_stats["evictions"] += 1
        logger.debug(f"캐시 제거 (LRU): {lru_key}")

    # === 캐시 키 관리 ===

    def _normalize_cache_key(self, key: str) -> str:
        """캐시 키 정규화"""
        # 길이 제한 및 특수문자 처리
        if len(key) > 200:
            # 긴 키는 해시로 변환
            return hashlib.md5(key.encode()).hexdigest()
        return key.replace(" ", "_").replace("/", "_")

    def _generate_cache_key(self, *args, **kwargs) -> str:
        """인자들로부터 캐시 키 생성"""
        key_parts = []

        # 위치 인자 처리
        for arg in args:
            if isinstance(arg, (str, int, float, bool)):
                key_parts.append(str(arg))
            elif isinstance(arg, (list, tuple)):
                key_parts.append(json.dumps(sorted(arg)))
            elif isinstance(arg, dict):
                key_parts.append(json.dumps(arg, sort_keys=True))
            else:
                # 복잡한 객체는 repr 사용
                key_parts.append(repr(arg))

        # 키워드 인자 처리
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")

        # 최종 키 생성
        cache_key = "|".join(key_parts)
        return self._normalize_cache_key(cache_key)

    # === 캐시 통계 ===

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = 0
        if total_requests > 0:
            hit_rate = self._cache_stats["hits"] / total_requests

        return {
            "size": len(self._cache),
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "evictions": self._cache_stats["evictions"],
            "hit_rate": round(hit_rate * 100, 2),
            "total_requests": total_requests,
        }

    def reset_cache_stats(self):
        """캐시 통계 초기화"""
        self._cache_stats = {"hits": 0, "misses": 0, "evictions": 0}

    # === 데코레이터 ===

    def cache_method(self, ttl: Optional[int] = None):
        """메서드 결과를 캐싱하는 데코레이터"""

        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(self, *args, **kwargs):
                # 캐시 키 생성
                cache_key = self._generate_cache_key(func.__name__, *args, **kwargs)

                # 캐시 확인
                cached_value = self._get_from_cache(cache_key)
                if cached_value is not None:
                    return cached_value

                # 실제 함수 실행
                result = await func(self, *args, **kwargs)

                # 결과 캐싱
                self._save_to_cache(cache_key, result, ttl)

                return result

            @wraps(func)
            def sync_wrapper(self, *args, **kwargs):
                # 캐시 키 생성
                cache_key = self._generate_cache_key(func.__name__, *args, **kwargs)

                # 캐시 확인
                cached_value = self._get_from_cache(cache_key)
                if cached_value is not None:
                    return cached_value

                # 실제 함수 실행
                result = func(self, *args, **kwargs)

                # 결과 캐싱
                self._save_to_cache(cache_key, result, ttl)

                return result

            # 비동기/동기 함수 구분
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator
