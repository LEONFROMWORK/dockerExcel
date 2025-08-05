"""
캐시 관리자
Excel to Univer 변환 과정에서 사용되는 다양한 캐시 전략 구현
"""

import time
import hashlib
import threading
from typing import Dict, Any, Optional, Union, Callable
from functools import wraps
from dataclasses import dataclass, field
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """캐시 엔트리"""

    value: Any
    created_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size: int = 0  # 메모리 사용량 (바이트)

    def touch(self):
        """캐시 엔트리 접근 시 호출"""
        self.last_accessed = time.time()
        self.access_count += 1


class LRUCache:
    """
    LRU (Least Recently Used) 캐시 구현
    스레드 안전성 보장
    """

    def __init__(self, max_size: int = 1000, ttl: Optional[float] = None):
        self.max_size = max_size
        self.ttl = ttl  # Time To Live (초)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # TTL 체크
            if self.ttl and (time.time() - entry.created_at) > self.ttl:
                del self._cache[key]
                self._misses += 1
                return None

            # LRU 업데이트 (가장 최근 사용으로 이동)
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1

            return entry.value

    def put(self, key: str, value: Any, size: int = 0) -> None:
        """캐시에 값 저장"""
        with self._lock:
            # 기존 키가 있으면 업데이트
            if key in self._cache:
                self._cache[key].value = value
                self._cache[key].created_at = time.time()
                self._cache[key].size = size
                self._cache.move_to_end(key)
                return

            # 캐시 크기 제한 체크
            while len(self._cache) >= self.max_size:
                # 가장 오래된 항목 제거
                oldest_key, oldest_entry = self._cache.popitem(last=False)
                logger.debug(f"캐시 크기 초과로 항목 제거: {oldest_key}")

            # 새 항목 추가
            entry = CacheEntry(value=value, created_at=time.time(), size=size)
            self._cache[key] = entry

    def remove(self, key: str) -> bool:
        """캐시에서 특정 키 제거"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """캐시 전체 정리"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.debug("캐시 전체 정리 완료")

    def cleanup_expired(self) -> int:
        """만료된 항목들 정리"""
        if not self.ttl:
            return 0

        removed_count = 0
        current_time = time.time()

        with self._lock:
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if (current_time - entry.created_at) > self.ttl
            ]

            for key in expired_keys:
                del self._cache[key]
                removed_count += 1

        if removed_count > 0:
            logger.debug(f"만료된 캐시 항목 {removed_count}개 정리")

        return removed_count

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0

            total_size = sum(entry.size for entry in self._cache.values())
            avg_size = total_size / len(self._cache) if self._cache else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate * 100, 2),
                "total_memory_bytes": total_size,
                "average_entry_size": round(avg_size, 2),
                "oldest_entry_age": self._get_oldest_entry_age(),
                "most_accessed_key": self._get_most_accessed_key(),
            }

    def _get_oldest_entry_age(self) -> Optional[float]:
        """가장 오래된 엔트리의 나이 (초)"""
        if not self._cache:
            return None

        oldest_entry = next(iter(self._cache.values()))
        return time.time() - oldest_entry.created_at

    def _get_most_accessed_key(self) -> Optional[str]:
        """가장 많이 접근된 키"""
        if not self._cache:
            return None

        return max(self._cache.keys(), key=lambda k: self._cache[k].access_count)


class StyleCacheManager:
    """
    스타일 캐시 관리자
    워크북 레벨과 글로벌 레벨 캐싱 지원
    """

    def __init__(self):
        # 글로벌 스타일 캐시 (모든 변환에서 공유)
        from app.core.constants import PerformanceSettings

        self.global_cache = LRUCache(
            max_size=PerformanceSettings.STYLE_CACHE_SIZE, ttl=3600  # 1시간
        )

        # 워크북별 스타일 캐시 (현재 변환 세션 동안만 유효)
        self.workbook_caches: Dict[str, LRUCache] = {}

        # 캐시 적중률 추적
        self._cache_lock = threading.Lock()

    def get_workbook_cache(self, workbook_id: str) -> LRUCache:
        """워크북별 캐시 조회/생성"""
        with self._cache_lock:
            if workbook_id not in self.workbook_caches:
                self.workbook_caches[workbook_id] = LRUCache(
                    max_size=1000, ttl=1800  # 워크북당 1000개 스타일  # 30분
                )
            return self.workbook_caches[workbook_id]

    def get_style(
        self, style_hash: str, workbook_id: Optional[str] = None
    ) -> Optional[Any]:
        """스타일 조회 (워크북 캐시 → 글로벌 캐시)"""
        # 1. 워크북 캐시에서 조회
        if workbook_id:
            workbook_cache = self.get_workbook_cache(workbook_id)
            style = workbook_cache.get(style_hash)
            if style is not None:
                logger.debug(f"워크북 캐시 적중: {style_hash[:8]}...")
                return style

        # 2. 글로벌 캐시에서 조회
        style = self.global_cache.get(style_hash)
        if style is not None:
            logger.debug(f"글로벌 캐시 적중: {style_hash[:8]}...")
            # 워크북 캐시에도 복사
            if workbook_id:
                workbook_cache = self.get_workbook_cache(workbook_id)
                workbook_cache.put(style_hash, style)

        return style

    def put_style(
        self, style_hash: str, style_data: Any, workbook_id: Optional[str] = None
    ) -> None:
        """스타일 저장"""
        style_size = len(str(style_data).encode("utf-8"))

        # 워크북 캐시에 저장
        if workbook_id:
            workbook_cache = self.get_workbook_cache(workbook_id)
            workbook_cache.put(style_hash, style_data, style_size)

        # 글로벌 캐시에도 저장 (재사용성 향상)
        self.global_cache.put(style_hash, style_data, style_size)

        logger.debug(f"스타일 캐시 저장: {style_hash[:8]}... ({style_size} bytes)")

    def cleanup_workbook_cache(self, workbook_id: str) -> None:
        """워크북 변환 완료 후 해당 캐시 정리"""
        with self._cache_lock:
            if workbook_id in self.workbook_caches:
                cache_stats = self.workbook_caches[workbook_id].get_stats()
                logger.info(f"워크북 캐시 정리: {workbook_id}, 통계: {cache_stats}")
                del self.workbook_caches[workbook_id]

    def get_cache_stats(self) -> Dict[str, Any]:
        """전체 캐시 통계"""
        global_stats = self.global_cache.get_stats()

        workbook_stats = {}
        with self._cache_lock:
            for wb_id, cache in self.workbook_caches.items():
                workbook_stats[wb_id] = cache.get_stats()

        return {
            "global_cache": global_stats,
            "workbook_caches": workbook_stats,
            "total_workbook_caches": len(self.workbook_caches),
        }

    def cleanup_expired(self) -> Dict[str, int]:
        """만료된 캐시 정리"""
        results = {
            "global_expired": self.global_cache.cleanup_expired(),
            "workbook_expired": {},
        }

        with self._cache_lock:
            for wb_id, cache in self.workbook_caches.items():
                expired_count = cache.cleanup_expired()
                if expired_count > 0:
                    results["workbook_expired"][wb_id] = expired_count

        return results


class CellDataCacheManager:
    """
    셀 데이터 캐시 관리자
    대용량 워크시트에서 중복 셀 값 캐싱
    """

    def __init__(self):
        from app.core.constants import PerformanceSettings

        self.cache = LRUCache(
            max_size=PerformanceSettings.CELL_CACHE_SIZE, ttl=1800  # 30분
        )

    def get_cell_key(self, value: Any, formula: Optional[str] = None) -> str:
        """셀 데이터의 캐시 키 생성"""
        key_data = f"{type(value).__name__}:{value}"
        if formula:
            key_data += f":formula:{formula}"

        return hashlib.md5(key_data.encode("utf-8")).hexdigest()

    def get_cached_cell_data(
        self, value: Any, formula: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """캐시된 셀 데이터 조회"""
        cache_key = self.get_cell_key(value, formula)
        return self.cache.get(cache_key)

    def cache_cell_data(
        self, value: Any, cell_data: Dict[str, Any], formula: Optional[str] = None
    ) -> None:
        """셀 데이터 캐싱"""
        cache_key = self.get_cell_key(value, formula)
        data_size = len(str(cell_data).encode("utf-8"))
        self.cache.put(cache_key, cell_data, data_size)


# 전역 캐시 매니저 인스턴스
style_cache_manager = StyleCacheManager()
cell_cache_manager = CellDataCacheManager()


def cached_method(
    cache_manager: Union[LRUCache, StyleCacheManager],
    key_func: Optional[Callable] = None,
    ttl: Optional[float] = None,
):
    """
    메서드 캐싱 데코레이터

    Args:
        cache_manager: 사용할 캐시 매니저
        key_func: 캐시 키 생성 함수
        ttl: Time To Live (초)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 기본 키 생성 (함수명 + 인자들의 해시)
                key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
                cache_key = hashlib.md5(key_data.encode("utf-8")).hexdigest()

            # 캐시에서 조회
            if hasattr(cache_manager, "get"):
                cached_result = cache_manager.get(cache_key)
                if cached_result is not None:
                    return cached_result

            # 캐시 미스 - 실제 함수 실행
            result = func(*args, **kwargs)

            # 결과 캐싱
            if hasattr(cache_manager, "put"):
                result_size = len(str(result).encode("utf-8"))
                cache_manager.put(cache_key, result, result_size)

            return result

        return wrapper

    return decorator


def get_cache_stats() -> Dict[str, Any]:
    """전체 캐시 시스템 통계"""
    return {
        "style_cache": style_cache_manager.get_cache_stats(),
        "cell_cache": cell_cache_manager.cache.get_stats(),
        "memory_usage": _get_cache_memory_usage(),
    }


def _get_cache_memory_usage() -> Dict[str, Any]:
    """캐시 메모리 사용량 계산"""
    import sys

    style_memory = sys.getsizeof(style_cache_manager)
    cell_memory = sys.getsizeof(cell_cache_manager)

    return {
        "style_cache_mb": round(style_memory / 1024 / 1024, 2),
        "cell_cache_mb": round(cell_memory / 1024 / 1024, 2),
        "total_cache_mb": round((style_memory + cell_memory) / 1024 / 1024, 2),
    }


def cleanup_all_caches() -> Dict[str, Any]:
    """모든 캐시 정리"""
    style_cleanup = style_cache_manager.cleanup_expired()
    cell_cleanup = cell_cache_manager.cache.cleanup_expired()

    return {
        "style_cache_cleanup": style_cleanup,
        "cell_cache_expired": cell_cleanup,
        "cleanup_time": time.time(),
    }
