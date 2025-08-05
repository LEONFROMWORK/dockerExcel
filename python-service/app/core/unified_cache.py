"""
통합 캐시 관리자
모든 Excel 관련 캐싱을 중앙에서 관리
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from app.core.interfaces import ExcelError, FixResult
import hashlib
import logging

logger = logging.getLogger(__name__)


class CacheEntry:
    """캐시 엔트리"""

    def __init__(self, data: Any, ttl_seconds: int = 3600):
        self.data = data
        self.timestamp = datetime.now()
        self.ttl = timedelta(seconds=ttl_seconds)
        self.access_count = 0
        self.last_accessed = datetime.now()

    def is_expired(self) -> bool:
        """만료 여부 확인"""
        return datetime.now() - self.timestamp > self.ttl

    def access(self) -> Any:
        """데이터 접근"""
        self.access_count += 1
        self.last_accessed = datetime.now()
        return self.data


class UnifiedExcelCache:
    """통합 Excel 캐시 관리자"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._analysis_cache: Dict[str, CacheEntry] = {}
        self._error_cache: Dict[str, CacheEntry] = {}
        self._fix_cache: Dict[str, CacheEntry] = {}
        self._file_hash_cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._max_cache_size = 1000  # 최대 캐시 항목 수
        self._default_ttl = 3600  # 기본 TTL: 1시간
        self._initialized = True

        # 통계
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    # 분석 캐시 메서드
    async def get_analysis(self, file_id: str) -> Optional[Dict]:
        """분석 결과 가져오기"""
        async with self._lock:
            entry = self._analysis_cache.get(file_id)
            if entry and not entry.is_expired():
                self._stats["hits"] += 1
                return entry.access()

            self._stats["misses"] += 1
            if entry:
                del self._analysis_cache[file_id]
            return None

    async def set_analysis(
        self, file_id: str, analysis: Dict, ttl: Optional[int] = None
    ):
        """분석 결과 저장"""
        async with self._lock:
            # 캐시 크기 확인
            await self._ensure_cache_size()

            self._analysis_cache[file_id] = CacheEntry(
                analysis, ttl or self._default_ttl
            )
            logger.debug(f"Cached analysis for file {file_id}")

    # 오류 캐시 메서드
    async def get_errors(self, file_id: str) -> Optional[List[ExcelError]]:
        """파일의 오류 목록 가져오기"""
        async with self._lock:
            entry = self._error_cache.get(f"file_{file_id}")
            if entry and not entry.is_expired():
                self._stats["hits"] += 1
                return entry.access()

            self._stats["misses"] += 1
            return None

    async def set_errors(self, file_id: str, errors: List[ExcelError]):
        """오류 목록 저장"""
        async with self._lock:
            await self._ensure_cache_size()

            # 파일별 오류 저장
            self._error_cache[f"file_{file_id}"] = CacheEntry(errors)

            # 개별 오류도 캐시
            for error in errors:
                self._error_cache[error.id] = CacheEntry(error)

            logger.debug(f"Cached {len(errors)} errors for file {file_id}")

    async def get_error_by_id(self, error_id: str) -> Optional[ExcelError]:
        """오류 ID로 개별 오류 가져오기"""
        async with self._lock:
            entry = self._error_cache.get(error_id)
            if entry and not entry.is_expired():
                self._stats["hits"] += 1
                return entry.access()

            self._stats["misses"] += 1
            return None

    # 수정 결과 캐시 메서드
    async def get_fix_result(self, error_id: str) -> Optional[FixResult]:
        """수정 결과 가져오기"""
        async with self._lock:
            entry = self._fix_cache.get(error_id)
            if entry and not entry.is_expired():
                self._stats["hits"] += 1
                return entry.access()

            self._stats["misses"] += 1
            return None

    async def set_fix_result(self, error_id: str, result: FixResult):
        """수정 결과 저장"""
        async with self._lock:
            await self._ensure_cache_size()
            self._fix_cache[error_id] = CacheEntry(result)
            logger.debug(f"Cached fix result for error {error_id}")

    # 파일 해시 캐시
    async def get_file_hash(self, file_id: str) -> Optional[str]:
        """파일 해시 가져오기"""
        async with self._lock:
            return self._file_hash_cache.get(file_id)

    async def set_file_hash(self, file_id: str, file_hash: str):
        """파일 해시 저장"""
        async with self._lock:
            self._file_hash_cache[file_id] = file_hash

    def generate_cache_key(self, file_id: str, analysis_type: str) -> str:
        """캐시 키 생성"""
        key_data = f"{file_id}:{analysis_type}"
        return hashlib.md5(key_data.encode()).hexdigest()

    # 캐시 관리 메서드
    async def _ensure_cache_size(self):
        """캐시 크기 관리 - LRU 정책"""
        total_size = (
            len(self._analysis_cache) + len(self._error_cache) + len(self._fix_cache)
        )

        if total_size >= self._max_cache_size:
            # 가장 오래된 항목 제거
            await self._evict_oldest()

    async def _evict_oldest(self):
        """가장 오래된 캐시 항목 제거"""
        all_entries = []

        # 모든 캐시에서 항목 수집
        for key, entry in self._analysis_cache.items():
            all_entries.append(("analysis", key, entry))
        for key, entry in self._error_cache.items():
            all_entries.append(("error", key, entry))
        for key, entry in self._fix_cache.items():
            all_entries.append(("fix", key, entry))

        # 마지막 접근 시간으로 정렬
        all_entries.sort(key=lambda x: x[2].last_accessed)

        # 가장 오래된 10% 제거
        evict_count = max(1, len(all_entries) // 10)

        for cache_type, key, _ in all_entries[:evict_count]:
            if cache_type == "analysis":
                del self._analysis_cache[key]
            elif cache_type == "error":
                del self._error_cache[key]
            elif cache_type == "fix":
                del self._fix_cache[key]

            self._stats["evictions"] += 1

    async def clear_file_cache(self, file_id: str):
        """특정 파일의 모든 캐시 삭제"""
        async with self._lock:
            # 분석 캐시 삭제
            if file_id in self._analysis_cache:
                del self._analysis_cache[file_id]

            # 오류 캐시 삭제
            file_error_key = f"file_{file_id}"
            if file_error_key in self._error_cache:
                errors = self._error_cache[file_error_key].data
                del self._error_cache[file_error_key]

                # 개별 오류도 삭제
                for error in errors:
                    if error.id in self._error_cache:
                        del self._error_cache[error.id]

            # 파일 해시 삭제
            if file_id in self._file_hash_cache:
                del self._file_hash_cache[file_id]

            logger.info(f"Cleared all cache for file {file_id}")

    async def clear_all(self):
        """모든 캐시 삭제"""
        async with self._lock:
            self._analysis_cache.clear()
            self._error_cache.clear()
            self._fix_cache.clear()
            self._file_hash_cache.clear()
            logger.info("Cleared all cache")

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        return {
            **self._stats,
            "analysis_cache_size": len(self._analysis_cache),
            "error_cache_size": len(self._error_cache),
            "fix_cache_size": len(self._fix_cache),
            "total_size": (
                len(self._analysis_cache)
                + len(self._error_cache)
                + len(self._fix_cache)
            ),
            "hit_rate": (
                self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
                if (self._stats["hits"] + self._stats["misses"]) > 0
                else 0
            ),
        }


# 싱글톤 인스턴스
unified_cache = UnifiedExcelCache()
