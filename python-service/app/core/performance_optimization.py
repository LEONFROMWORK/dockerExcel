"""
OCR 시스템 성능 최적화 컴포넌트
SOLID 원칙 기반 설계로 확장 가능하고 유지보수 가능한 최적화 시스템
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Protocol, TypeVar, Generic
import weakref
import threading
import time
import logging
import numpy as np
from collections import defaultdict, deque
import hashlib
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

T = TypeVar('T')

# ===== 인터페이스 정의 (Interface Segregation Principle) =====

class PerformanceOptimizer(Protocol):
    """성능 최적화기 인터페이스"""
    def optimize(self, data: Any) -> Any:
        """데이터 최적화 수행"""
        ...

class CacheStrategy(Protocol):
    """캐시 전략 인터페이스"""
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        ...
    
    def put(self, key: str, value: Any) -> None:
        """캐시에 데이터 저장"""
        ...
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        ...

class MemoryManager(Protocol):
    """메모리 관리자 인터페이스"""
    def allocate(self, size: int) -> Any:
        """메모리 할당"""
        ...
    
    def deallocate(self, obj: Any) -> None:
        """메모리 해제"""
        ...
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """메모리 사용량 통계"""
        ...

class PerformanceMonitor(Protocol):
    """성능 모니터링 인터페이스"""
    def start_timing(self, operation: str) -> str:
        """타이밍 시작"""
        ...
    
    def end_timing(self, timing_id: str) -> float:
        """타이밍 종료 및 시간 반환"""
        ...
    
    def record_metric(self, name: str, value: Any) -> None:
        """메트릭 기록"""
        ...

# ===== 데이터 클래스 =====

@dataclass
class PerformanceMetrics:
    """성능 메트릭 데이터"""
    processing_times: List[float] = field(default_factory=list)
    memory_usage: List[int] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    error_count: int = 0
    throughput: float = 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    @property
    def avg_processing_time(self) -> float:
        return np.mean(self.processing_times) if self.processing_times else 0.0
    
    @property
    def p95_processing_time(self) -> float:
        return np.percentile(self.processing_times, 95) if self.processing_times else 0.0

@dataclass
class OptimizationConfig:
    """최적화 설정"""
    cache_size_limit: int = 1000
    memory_pool_size: int = 100
    batch_size: int = 32
    enable_vectorization: bool = True
    enable_memory_pooling: bool = True
    enable_result_caching: bool = True
    performance_monitoring: bool = True

# ===== 메모리 풀 구현 (Single Responsibility Principle) =====

class MemoryPool(Generic[T]):
    """메모리 풀 - 객체 재사용을 통한 메모리 할당 최적화"""
    
    def __init__(self, factory_func, max_size: int = 100):
        self.factory_func = factory_func
        self.max_size = max_size
        self.pool: deque = deque()
        self.lock = threading.Lock()
        self.created_count = 0
        self.reused_count = 0
    
    def acquire(self) -> T:
        """객체 획득 (풀에서 재사용 또는 새로 생성)"""
        with self.lock:
            if self.pool:
                obj = self.pool.popleft()
                self.reused_count += 1
                return obj
            else:
                self.created_count += 1
                return self.factory_func()
    
    def release(self, obj: T) -> None:
        """객체 반환 (풀로 돌려보냄)"""
        with self.lock:
            if len(self.pool) < self.max_size:
                # 객체 초기화 (재사용을 위해)
                if hasattr(obj, 'reset'):
                    obj.reset()
                self.pool.append(obj)
    
    def get_stats(self) -> Dict[str, Any]:
        """메모리 풀 통계"""
        with self.lock:
            total_operations = self.created_count + self.reused_count
            reuse_rate = self.reused_count / total_operations if total_operations > 0 else 0.0
            
            return {
                'pool_size': len(self.pool),
                'max_size': self.max_size,
                'created_count': self.created_count,
                'reused_count': self.reused_count,
                'reuse_rate': reuse_rate,
                'current_utilization': len(self.pool) / self.max_size
            }

# ===== LRU 캐시 구현 (Open/Closed Principle) =====

class LRUCache:
    """LRU (Least Recently Used) 캐시 구현"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: Dict[str, Any] = {}
        self.access_order: deque = deque()
        self.lock = threading.RLock()
        
        # 통계
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        with self.lock:
            if key in self.cache:
                self.hits += 1
                # 접근 순서 업데이트
                self.access_order.remove(key)
                self.access_order.append(key)
                return self.cache[key]
            else:
                self.misses += 1
                return None
    
    def put(self, key: str, value: Any) -> None:
        """캐시에 값 저장"""
        with self.lock:
            if key in self.cache:
                # 기존 키 업데이트
                self.access_order.remove(key)
            elif len(self.cache) >= self.max_size:
                # 가장 오래된 항목 제거
                oldest_key = self.access_order.popleft()
                del self.cache[oldest_key]
            
            self.cache[key] = value
            self.access_order.append(key)
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'utilization': len(self.cache) / self.max_size
        }

# ===== 계층화된 캐시 시스템 (Strategy Pattern) =====

class HierarchicalCache:
    """계층화된 캐시 시스템 - L1 (메모리), L2 (디스크)"""
    
    def __init__(self, l1_size: int = 500, l2_size: int = 2000, cache_dir: Optional[Path] = None):
        self.l1_cache = LRUCache(l1_size)  # 메모리 캐시
        self.l2_cache = LRUCache(l2_size)  # 디스크 캐시 인덱스
        self.cache_dir = cache_dir or Path("/tmp/ocr_cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        # 통계
        self.l1_hits = 0
        self.l2_hits = 0
        self.total_misses = 0
    
    def _generate_file_key(self, key: str) -> str:
        """파일 키 생성"""
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """계층화된 캐시에서 조회"""
        # L1 캐시 확인
        value = self.l1_cache.get(key)
        if value is not None:
            self.l1_hits += 1
            return value
        
        # L2 캐시 확인
        if self.l2_cache.get(key) is not None:
            try:
                file_key = self._generate_file_key(key)
                cache_file = self.cache_dir / f"{file_key}.pkl"
                
                if cache_file.exists():
                    with open(cache_file, 'rb') as f:
                        value = pickle.load(f)
                    
                    # L1 캐시로 승격
                    self.l1_cache.put(key, value)
                    self.l2_hits += 1
                    return value
            except Exception as e:
                logger.warning(f"L2 캐시 조회 실패: {e}")
        
        self.total_misses += 1
        return None
    
    def put(self, key: str, value: Any) -> None:
        """계층화된 캐시에 저장"""
        # L1 캐시에 저장
        self.l1_cache.put(key, value)
        
        # L2 캐시에도 저장 (비동기적으로)
        try:
            file_key = self._generate_file_key(key)
            cache_file = self.cache_dir / f"{file_key}.pkl"
            
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
            
            self.l2_cache.put(key, True)  # 존재 여부만 기록
        except Exception as e:
            logger.warning(f"L2 캐시 저장 실패: {e}")
    
    def clear(self) -> None:
        """모든 캐시 삭제"""
        self.l1_cache.clear()
        self.l2_cache.clear()
        
        # 디스크 캐시 파일 삭제
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"캐시 파일 삭제 실패: {e}")

# ===== 벡터화된 텍스트 분석 (Single Responsibility Principle) =====

class VectorizedTextAnalyzer:
    """벡터화된 텍스트 분석 - NumPy를 활용한 고속 텍스트 처리"""
    
    def __init__(self):
        self.korean_char_range = (0xAC00, 0xD7AF)
        self.chinese_char_range = (0x4E00, 0x9FFF)
        self.japanese_char_range = (0x3040, 0x30FF)
    
    def analyze_language_distribution(self, texts: List[str]) -> Dict[str, float]:
        """여러 텍스트의 언어 분포 벡터화 분석"""
        if not texts:
            return {}
        
        # 전체 텍스트를 하나로 합침
        combined_text = ''.join(texts)
        char_codes = np.array([ord(c) for c in combined_text])
        
        total_chars = len(char_codes)
        if total_chars == 0:
            return {}
        
        # 벡터화된 언어 감지
        korean_mask = (char_codes >= self.korean_char_range[0]) & (char_codes <= self.korean_char_range[1])
        chinese_mask = (char_codes >= self.chinese_char_range[0]) & (char_codes <= self.chinese_char_range[1])
        japanese_mask = (char_codes >= self.japanese_char_range[0]) & (char_codes <= self.japanese_char_range[1])
        
        return {
            'korean': np.sum(korean_mask) / total_chars,
            'chinese': np.sum(chinese_mask) / total_chars,
            'japanese': np.sum(japanese_mask) / total_chars,
            'other': 1.0 - (np.sum(korean_mask) + np.sum(chinese_mask) + np.sum(japanese_mask)) / total_chars
        }
    
    def batch_confidence_analysis(self, confidence_scores: List[float]) -> Dict[str, float]:
        """벡터화된 신뢰도 분석"""
        if not confidence_scores:
            return {}
        
        scores_array = np.array(confidence_scores)
        
        return {
            'mean': float(np.mean(scores_array)),
            'std': float(np.std(scores_array)),
            'min': float(np.min(scores_array)),
            'max': float(np.max(scores_array)),
            'p25': float(np.percentile(scores_array, 25)),
            'p50': float(np.percentile(scores_array, 50)),
            'p75': float(np.percentile(scores_array, 75)),
            'p95': float(np.percentile(scores_array, 95))
        }

# ===== 배치 I/O 최적화 (Dependency Inversion Principle) =====

class BatchIOOptimizer:
    """배치 I/O 최적화 - 디스크 읽기/쓰기 최소화"""
    
    def __init__(self, batch_size: int = 32):
        self.batch_size = batch_size
        self.write_queue: List[tuple] = []
        self.lock = threading.Lock()
    
    def queue_write(self, file_path: str, data: Any) -> None:
        """쓰기 작업을 큐에 추가"""
        with self.lock:
            self.write_queue.append((file_path, data))
            
            if len(self.write_queue) >= self.batch_size:
                self._flush_write_queue()
    
    def _flush_write_queue(self) -> None:
        """큐에 있는 모든 쓰기 작업 실행"""
        if not self.write_queue:
            return
        
        # 파일별로 그룹화
        file_groups = defaultdict(list)
        for file_path, data in self.write_queue:
            file_groups[file_path].append(data)
        
        # 각 파일에 대해 배치 쓰기
        for file_path, data_list in file_groups.items():
            try:
                with open(file_path, 'ab') as f:  # append binary
                    for data in data_list:
                        pickle.dump(data, f)
            except Exception as e:
                logger.error(f"배치 쓰기 실패 {file_path}: {e}")
        
        self.write_queue.clear()
    
    def force_flush(self) -> None:
        """강제로 큐 비우기"""
        with self.lock:
            self._flush_write_queue()

# ===== 통합 성능 최적화 매니저 (Facade Pattern) =====

class OCRPerformanceOptimizer:
    """OCR 성능 최적화 통합 매니저 - SOLID 원칙 적용"""
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        
        # 컴포넌트 초기화 (Dependency Injection)
        self.cache = HierarchicalCache(
            l1_size=config.cache_size_limit // 2,
            l2_size=config.cache_size_limit
        ) if config.enable_result_caching else None
        
        self.memory_pools = {
            'numpy_arrays': MemoryPool(lambda: np.zeros(1024), config.memory_pool_size),
            'text_buffers': MemoryPool(lambda: [], config.memory_pool_size),
            'dict_objects': MemoryPool(lambda: {}, config.memory_pool_size)
        } if config.enable_memory_pooling else {}
        
        self.text_analyzer = VectorizedTextAnalyzer() if config.enable_vectorization else None
        self.io_optimizer = BatchIOOptimizer(config.batch_size)
        
        # 성능 메트릭
        self.metrics = PerformanceMetrics()
        self.timing_contexts = {}
        
        logger.info(f"OCR 성능 최적화 시스템 초기화 완료: {config}")
    
    def start_operation_timing(self, operation_name: str) -> str:
        """작업 타이밍 시작"""
        timing_id = f"{operation_name}_{int(time.time() * 1000000)}"
        self.timing_contexts[timing_id] = {
            'operation': operation_name,
            'start_time': time.perf_counter()
        }
        return timing_id
    
    def end_operation_timing(self, timing_id: str) -> float:
        """작업 타이밍 종료"""
        if timing_id not in self.timing_contexts:
            return 0.0
        
        context = self.timing_contexts[timing_id]
        duration = time.perf_counter() - context['start_time']
        
        self.metrics.processing_times.append(duration)
        del self.timing_contexts[timing_id]
        
        return duration
    
    def get_cached_result(self, cache_key: str) -> Optional[Any]:
        """캐시된 결과 조회"""
        if not self.cache:
            return None
        
        result = self.cache.get(cache_key)
        if result is not None:
            self.metrics.cache_hits += 1
        else:
            self.metrics.cache_misses += 1
        
        return result
    
    def cache_result(self, cache_key: str, result: Any) -> None:
        """결과 캐싱"""
        if self.cache:
            self.cache.put(cache_key, result)
    
    def optimize_text_batch(self, texts: List[str]) -> Dict[str, Any]:
        """텍스트 배치 최적화 분석"""
        if not self.text_analyzer:
            return {}
        
        timing_id = self.start_operation_timing("text_batch_analysis")
        
        try:
            # 벡터화된 분석
            language_dist = self.text_analyzer.analyze_language_distribution(texts)
            
            # 메모리 풀 활용
            if 'text_buffers' in self.memory_pools:
                buffer = self.memory_pools['text_buffers'].acquire()
                try:
                    # 텍스트 처리 로직
                    buffer.extend(texts)
                    processed_count = len(buffer)
                finally:
                    self.memory_pools['text_buffers'].release(buffer)
            else:
                processed_count = len(texts)
            
            return {
                'language_distribution': language_dist,
                'processed_count': processed_count,
                'processing_time': self.end_operation_timing(timing_id)
            }
        
        except Exception as e:
            logger.error(f"텍스트 배치 최적화 실패: {e}")
            self.end_operation_timing(timing_id)
            return {}
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보"""
        summary = {
            'metrics': {
                'avg_processing_time': self.metrics.avg_processing_time,
                'p95_processing_time': self.metrics.p95_processing_time,
                'cache_hit_rate': self.metrics.cache_hit_rate,
                'total_operations': len(self.metrics.processing_times)
            }
        }
        
        # 캐시 통계
        if self.cache:
            summary['cache_stats'] = {
                'l1_stats': self.cache.l1_cache.get_stats(),
                'l2_hits': self.cache.l2_hits,
                'total_misses': self.cache.total_misses
            }
        
        # 메모리 풀 통계
        if self.memory_pools:
            summary['memory_pool_stats'] = {
                name: pool.get_stats() 
                for name, pool in self.memory_pools.items()
            }
        
        return summary
    
    def cleanup(self) -> None:
        """리소스 정리"""
        if self.cache:
            self.cache.clear()
        
        self.io_optimizer.force_flush()
        
        logger.info("OCR 성능 최적화 시스템 정리 완료")

# ===== 팩토리 (Factory Pattern) =====

class PerformanceOptimizerFactory:
    """성능 최적화기 팩토리"""
    
    @staticmethod
    def create_optimizer(
        optimization_level: str = "standard",
        custom_config: Optional[OptimizationConfig] = None
    ) -> OCRPerformanceOptimizer:
        """최적화 수준에 따른 최적화기 생성"""
        
        if custom_config:
            config = custom_config
        elif optimization_level == "basic":
            config = OptimizationConfig(
                cache_size_limit=500,
                memory_pool_size=50,
                batch_size=16,
                enable_vectorization=False
            )
        elif optimization_level == "aggressive":
            config = OptimizationConfig(
                cache_size_limit=2000,
                memory_pool_size=200,
                batch_size=64,
                enable_vectorization=True
            )
        else:  # standard
            config = OptimizationConfig()
        
        return OCRPerformanceOptimizer(config)