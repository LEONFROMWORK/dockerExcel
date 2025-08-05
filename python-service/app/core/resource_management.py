"""
리소스 사용량 최적화 시스템
메모리 풀링, 객체 재사용, 가비지 컬렉션 최적화
SOLID 원칙 기반 설계
"""

import gc
import threading
import time
import weakref
import psutil
import logging
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Dict, Any, Optional, TypeVar, Generic, Callable
from contextlib import contextmanager
import numpy as np

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ===== 인터페이스 정의 (Interface Segregation Principle) =====


class ResourceManager(ABC):
    """리소스 관리자 추상 인터페이스"""

    @abstractmethod
    def acquire(self) -> Any:
        """리소스 획득"""

    @abstractmethod
    def release(self, resource: Any) -> None:
        """리소스 해제"""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """사용량 통계"""


class GarbageCollectionStrategy(ABC):
    """가비지 컬렉션 전략 인터페이스"""

    @abstractmethod
    def should_collect(self, memory_stats: Dict[str, Any]) -> bool:
        """가비지 컬렉션 실행 여부 판단"""

    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """가비지 컬렉션 실행"""


# ===== 데이터 클래스 =====


@dataclass
class MemoryStats:
    """메모리 사용량 통계"""

    total_memory: int = 0
    available_memory: int = 0
    used_memory: int = 0
    memory_percent: float = 0.0
    process_memory: int = 0
    process_memory_percent: float = 0.0
    peak_memory: int = 0

    @classmethod
    def get_current_stats(cls) -> "MemoryStats":
        """현재 메모리 통계 수집"""
        try:
            system_memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory_info = process.memory_info()

            return cls(
                total_memory=system_memory.total,
                available_memory=system_memory.available,
                used_memory=system_memory.used,
                memory_percent=system_memory.percent,
                process_memory=process_memory_info.rss,
                process_memory_percent=process.memory_percent(),
                peak_memory=getattr(
                    process_memory_info, "peak_wset", process_memory_info.rss
                ),
            )
        except Exception as e:
            logger.warning(f"메모리 통계 수집 실패: {e}")
            return cls()


@dataclass
class ResourcePoolConfig:
    """리소스 풀 설정"""

    max_size: int = 100
    initial_size: int = 10
    growth_factor: float = 1.5
    shrink_threshold: float = 0.3
    max_idle_time: float = 300.0  # 5분
    enable_monitoring: bool = True


# ===== 고급 메모리 풀 (Single Responsibility Principle) =====


class AdvancedMemoryPool(Generic[T], ResourceManager):
    """고급 메모리 풀 - 동적 크기 조정, 유휴 시간 관리"""

    def __init__(
        self,
        factory_func: Callable[[], T],
        reset_func: Optional[Callable[[T], None]] = None,
        config: Optional[ResourcePoolConfig] = None,
    ):
        self.factory_func = factory_func
        self.reset_func = reset_func or self._default_reset
        self.config = config or ResourcePoolConfig()

        # 풀 관리
        self.available_objects: deque = deque()
        self.in_use_objects: weakref.WeakSet = weakref.WeakSet()
        self.object_timestamps: Dict[int, float] = {}

        # 동기화
        self.lock = threading.RLock()

        # 통계
        self.stats = {
            "created_count": 0,
            "reused_count": 0,
            "destroyed_count": 0,
            "peak_size": 0,
            "current_size": 0,
            "hit_rate": 0.0,
        }

        # 초기 객체 생성
        self._initialize_pool()

        # 정리 스레드 시작
        if self.config.enable_monitoring:
            self._start_cleanup_thread()

    def _default_reset(self, obj: T) -> None:
        """기본 객체 리셋 함수"""
        if hasattr(obj, "clear"):
            obj.clear()
        elif hasattr(obj, "reset"):
            obj.reset()

    def _initialize_pool(self) -> None:
        """풀 초기화"""
        with self.lock:
            for _ in range(self.config.initial_size):
                obj = self.factory_func()
                self.available_objects.append(obj)
                self.object_timestamps[id(obj)] = time.time()
                self.stats["created_count"] += 1

            self.stats["current_size"] = len(self.available_objects)
            self.stats["peak_size"] = self.stats["current_size"]

    def acquire(self) -> T:
        """객체 획득"""
        with self.lock:
            if self.available_objects:
                # 기존 객체 재사용
                obj = self.available_objects.popleft()
                self.in_use_objects.add(obj)
                del self.object_timestamps[id(obj)]
                self.stats["reused_count"] += 1

                # 객체 리셋
                try:
                    self.reset_func(obj)
                except Exception as e:
                    logger.warning(f"객체 리셋 실패: {e}")

            else:
                # 새 객체 생성
                obj = self.factory_func()
                self.in_use_objects.add(obj)
                self.stats["created_count"] += 1

            self._update_stats()
            return obj

    def release(self, obj: T) -> None:
        """객체 해제"""
        with self.lock:
            if obj in self.in_use_objects:
                self.in_use_objects.discard(obj)

                # 풀 크기 제한 확인
                if len(self.available_objects) < self.config.max_size:
                    self.available_objects.append(obj)
                    self.object_timestamps[id(obj)] = time.time()
                else:
                    # 풀이 가득 찬 경우 객체 폐기
                    self.stats["destroyed_count"] += 1

                self._update_stats()

    def _update_stats(self) -> None:
        """통계 업데이트"""
        current_size = len(self.available_objects) + len(self.in_use_objects)
        self.stats["current_size"] = current_size
        self.stats["peak_size"] = max(self.stats["peak_size"], current_size)

        total_operations = self.stats["created_count"] + self.stats["reused_count"]
        if total_operations > 0:
            self.stats["hit_rate"] = self.stats["reused_count"] / total_operations

    def _cleanup_idle_objects(self) -> None:
        """유휴 객체 정리"""
        with self.lock:
            current_time = time.time()
            objects_to_remove = []

            # 유휴 시간 초과 객체 찾기
            for obj in list(self.available_objects):
                obj_id = id(obj)
                if obj_id in self.object_timestamps:
                    idle_time = current_time - self.object_timestamps[obj_id]
                    if idle_time > self.config.max_idle_time:
                        objects_to_remove.append(obj)

            # 객체 제거
            for obj in objects_to_remove:
                self.available_objects.remove(obj)
                del self.object_timestamps[id(obj)]
                self.stats["destroyed_count"] += 1

            # 풀 크기 축소 (사용률이 낮은 경우)
            target_size = max(
                self.config.initial_size,
                int(len(self.in_use_objects) * self.config.growth_factor),
            )

            while len(self.available_objects) > target_size:
                obj = self.available_objects.popleft()
                del self.object_timestamps[id(obj)]
                self.stats["destroyed_count"] += 1

            self._update_stats()

            if objects_to_remove:
                logger.debug(f"유휴 객체 {len(objects_to_remove)}개 정리됨")

    def _start_cleanup_thread(self) -> None:
        """정리 스레드 시작"""

        def cleanup_worker():
            while True:
                try:
                    time.sleep(60)  # 1분마다 정리
                    self._cleanup_idle_objects()
                except Exception as e:
                    logger.error(f"정리 스레드 오류: {e}")

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

    def get_stats(self) -> Dict[str, Any]:
        """풀 통계"""
        with self.lock:
            return {
                **self.stats,
                "available_objects": len(self.available_objects),
                "in_use_objects": len(self.in_use_objects),
                "pool_utilization": len(self.in_use_objects)
                / max(self.stats["current_size"], 1),
                "config": {
                    "max_size": self.config.max_size,
                    "initial_size": self.config.initial_size,
                    "max_idle_time": self.config.max_idle_time,
                },
            }


# ===== 스마트 가비지 컬렉션 전략 (Strategy Pattern) =====


class AdaptiveGCStrategy(GarbageCollectionStrategy):
    """적응형 가비지 컬렉션 전략"""

    def __init__(self, memory_threshold: float = 80.0, collect_interval: float = 30.0):
        self.memory_threshold = memory_threshold
        self.collect_interval = collect_interval
        self.last_collection = 0.0
        self.collection_stats = {
            "total_collections": 0,
            "memory_freed": 0,
            "avg_collection_time": 0.0,
        }

    def should_collect(self, memory_stats: Dict[str, Any]) -> bool:
        """가비지 컬렉션 실행 여부 판단"""
        current_time = time.time()

        # 메모리 사용률 기준
        memory_usage = memory_stats.get("memory_percent", 0)
        if memory_usage > self.memory_threshold:
            return True

        # 시간 간격 기준
        if current_time - self.last_collection > self.collect_interval:
            return True

        return False

    def collect(self) -> Dict[str, Any]:
        """가비지 컬렉션 실행"""
        start_time = time.time()
        memory_before = MemoryStats.get_current_stats()

        # 가비지 컬렉션 실행
        collected_counts = {
            "generation_0": gc.collect(0),
            "generation_1": gc.collect(1),
            "generation_2": gc.collect(2),
        }

        end_time = time.time()
        memory_after = MemoryStats.get_current_stats()

        collection_time = end_time - start_time
        memory_freed = memory_before.process_memory - memory_after.process_memory

        # 통계 업데이트
        self.collection_stats["total_collections"] += 1
        self.collection_stats["memory_freed"] += memory_freed

        # 평균 수집 시간 업데이트
        total_time = self.collection_stats["avg_collection_time"] * (
            self.collection_stats["total_collections"] - 1
        )
        self.collection_stats["avg_collection_time"] = (
            total_time + collection_time
        ) / self.collection_stats["total_collections"]

        self.last_collection = end_time

        result = {
            "collection_time": collection_time,
            "memory_freed": memory_freed,
            "collected_objects": collected_counts,
            "memory_before": memory_before.process_memory,
            "memory_after": memory_after.process_memory,
            "stats": self.collection_stats.copy(),
        }

        logger.info(
            f"가비지 컬렉션 완료: {memory_freed / 1024 / 1024:.2f}MB 해제, {collection_time:.3f}초"
        )
        return result


# ===== 통합 리소스 관리자 (Facade Pattern) =====


class IntegratedResourceManager:
    """통합 리소스 관리자 - 메모리, 객체, GC 통합 관리"""

    def __init__(self):
        self.memory_pools: Dict[str, AdvancedMemoryPool] = {}
        self.gc_strategy = AdaptiveGCStrategy()
        self.monitoring_enabled = True
        self.monitoring_interval = 30.0

        # 모니터링 데이터
        self.memory_history: deque = deque(maxlen=100)
        self.performance_history: deque = deque(maxlen=50)

        # 기본 풀 생성
        self._create_default_pools()

        # 모니터링 시작
        if self.monitoring_enabled:
            self._start_monitoring()

    def _create_default_pools(self) -> None:
        """기본 메모리 풀 생성"""
        # NumPy 배열 풀
        self.register_pool(
            "numpy_arrays",
            lambda: np.zeros(1024, dtype=np.float32),
            lambda arr: arr.fill(0),
            ResourcePoolConfig(max_size=50, initial_size=5),
        )

        # 딕셔너리 풀
        self.register_pool(
            "dictionaries",
            lambda: {},
            lambda d: d.clear(),
            ResourcePoolConfig(max_size=100, initial_size=10),
        )

        # 리스트 풀
        self.register_pool(
            "lists",
            lambda: [],
            lambda lst: lst.clear(),
            ResourcePoolConfig(max_size=100, initial_size=10),
        )

    def register_pool(
        self,
        name: str,
        factory_func: Callable,
        reset_func: Optional[Callable] = None,
        config: Optional[ResourcePoolConfig] = None,
    ) -> None:
        """새 메모리 풀 등록"""
        if name in self.memory_pools:
            logger.warning(f"메모리 풀 '{name}' 이미 존재함 - 덮어씀")

        self.memory_pools[name] = AdvancedMemoryPool(
            factory_func=factory_func,
            reset_func=reset_func,
            config=config or ResourcePoolConfig(),
        )

        logger.info(f"메모리 풀 '{name}' 등록됨")

    def get_resource(self, pool_name: str) -> Any:
        """리소스 획득"""
        if pool_name not in self.memory_pools:
            raise ValueError(f"알 수 없는 메모리 풀: {pool_name}")

        return self.memory_pools[pool_name].acquire()

    def return_resource(self, pool_name: str, resource: Any) -> None:
        """리소스 반환"""
        if pool_name not in self.memory_pools:
            logger.warning(f"알 수 없는 메모리 풀: {pool_name}")
            return

        self.memory_pools[pool_name].release(resource)

    @contextmanager
    def get_resource_context(self, pool_name: str):
        """리소스 컨텍스트 매니저"""
        resource = self.get_resource(pool_name)
        try:
            yield resource
        finally:
            self.return_resource(pool_name, resource)

    def _monitor_system_resources(self) -> None:
        """시스템 리소스 모니터링"""
        try:
            memory_stats = MemoryStats.get_current_stats()
            current_time = time.time()

            # 메모리 히스토리 업데이트
            self.memory_history.append(
                {
                    "timestamp": current_time,
                    "memory_percent": memory_stats.memory_percent,
                    "process_memory_mb": memory_stats.process_memory / 1024 / 1024,
                    "available_memory_mb": memory_stats.available_memory / 1024 / 1024,
                }
            )

            # 가비지 컬렉션 필요성 판단
            if self.gc_strategy.should_collect(memory_stats.__dict__):
                gc_result = self.gc_strategy.collect()

                self.performance_history.append(
                    {
                        "timestamp": current_time,
                        "gc_time": gc_result["collection_time"],
                        "memory_freed_mb": gc_result["memory_freed"] / 1024 / 1024,
                        "collected_objects": gc_result["collected_objects"],
                    }
                )

        except Exception as e:
            logger.error(f"리소스 모니터링 오류: {e}")

    def _start_monitoring(self) -> None:
        """모니터링 스레드 시작"""

        def monitoring_worker():
            while self.monitoring_enabled:
                try:
                    self._monitor_system_resources()
                    time.sleep(self.monitoring_interval)
                except Exception as e:
                    logger.error(f"모니터링 스레드 오류: {e}")

        monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
        monitoring_thread.start()
        logger.info("리소스 모니터링 시작됨")

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """종합 리소스 통계"""
        current_memory = MemoryStats.get_current_stats()

        pool_stats = {}
        for name, pool in self.memory_pools.items():
            pool_stats[name] = pool.get_stats()

        return {
            "current_memory": {
                "total_memory_gb": current_memory.total_memory / 1024 / 1024 / 1024,
                "available_memory_gb": current_memory.available_memory
                / 1024
                / 1024
                / 1024,
                "memory_percent": current_memory.memory_percent,
                "process_memory_mb": current_memory.process_memory / 1024 / 1024,
                "process_memory_percent": current_memory.process_memory_percent,
            },
            "memory_pools": pool_stats,
            "gc_stats": self.gc_strategy.collection_stats,
            "monitoring": {
                "enabled": self.monitoring_enabled,
                "interval": self.monitoring_interval,
                "history_size": len(self.memory_history),
            },
            "performance_trends": {
                "memory_trend": list(self.memory_history)[-10:],  # 최근 10개
                "gc_trend": list(self.performance_history)[-5:],  # 최근 5개
            },
        }

    def optimize_memory_usage(self) -> Dict[str, Any]:
        """메모리 사용량 최적화"""
        optimization_start = time.time()

        # 1. 강제 가비지 컬렉션
        gc_result = self.gc_strategy.collect()

        # 2. 메모리 풀 정리
        pool_cleanup_stats = {}
        for name, pool in self.memory_pools.items():
            if hasattr(pool, "_cleanup_idle_objects"):
                before_stats = pool.get_stats()
                pool._cleanup_idle_objects()
                after_stats = pool.get_stats()

                pool_cleanup_stats[name] = {
                    "objects_before": before_stats["available_objects"],
                    "objects_after": after_stats["available_objects"],
                    "objects_cleaned": before_stats["available_objects"]
                    - after_stats["available_objects"],
                }

        optimization_time = time.time() - optimization_start

        return {
            "optimization_time": optimization_time,
            "gc_result": gc_result,
            "pool_cleanup": pool_cleanup_stats,
            "final_memory_stats": MemoryStats.get_current_stats().__dict__,
        }

    def shutdown(self) -> None:
        """리소스 관리자 종료"""
        self.monitoring_enabled = False

        # 모든 풀 정리
        for name, pool in self.memory_pools.items():
            logger.info(f"메모리 풀 '{name}' 정리 중...")

        # 최종 가비지 컬렉션
        self.gc_strategy.collect()

        logger.info("통합 리소스 관리자 종료됨")


# ===== 전역 리소스 관리자 인스턴스 =====

_global_resource_manager: Optional[IntegratedResourceManager] = None


def get_resource_manager() -> IntegratedResourceManager:
    """전역 리소스 관리자 인스턴스 반환"""
    global _global_resource_manager

    if _global_resource_manager is None:
        _global_resource_manager = IntegratedResourceManager()

    return _global_resource_manager


def cleanup_global_resources() -> None:
    """전역 리소스 정리"""
    global _global_resource_manager

    if _global_resource_manager is not None:
        _global_resource_manager.shutdown()
        _global_resource_manager = None
