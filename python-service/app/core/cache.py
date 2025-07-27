"""
캐싱 시스템
Redis 기반 캐싱과 메모리 캐싱 지원
"""

import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps
import redis
from redis.exceptions import RedisError
import pickle
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """캐시 매니저"""
    
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        self._init_redis()
    
    def _init_redis(self):
        """Redis 연결 초기화"""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=False
            )
            self.redis_client.ping()
            logger.info("Redis 연결 성공")
        except Exception as e:
            logger.warning(f"Redis 연결 실패, 메모리 캐시 사용: {e}")
            self.redis_client = None
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """캐시 키 생성"""
        # 인자를 문자열로 변환하여 해시
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        try:
            # Redis 우선 확인
            if self.redis_client:
                try:
                    value = self.redis_client.get(key)
                    if value:
                        return self._deserialize(value)
                except RedisError as e:
                    logger.error(f"Redis 읽기 오류: {e}")
            
            # 메모리 캐시 확인
            return self.memory_cache.get(key)
            
        except Exception as e:
            logger.error(f"캐시 조회 오류: {e}")
            return None
    
    def _serialize(self, data: Any) -> bytes:
        """데이터 직렬화 (JSON 우선, 복잡한 객체는 pickle)"""
        try:
            # JSON으로 직렬화 시도
            if isinstance(data, (dict, list, str, int, float, bool, type(None))):
                return json.dumps(data).encode('utf-8')
            else:
                # 복잡한 객체는 pickle 사용 (경고와 함께)
                logger.warning(f"Using pickle for complex object type: {type(data)}")
                return pickle.dumps(data)
        except Exception as e:
            logger.error(f"직렬화 오류: {e}")
            # 최후의 수단으로 pickle 사용
            return pickle.dumps(data)
    
    def _deserialize(self, data: bytes) -> Any:
        """데이터 역직렬화"""
        try:
            # 먼저 JSON으로 시도
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # JSON 실패시 pickle로 시도 (기존 데이터 호환성)
            try:
                return pickle.loads(data)
            except Exception as e:
                logger.error(f"역직렬화 오류: {e}")
                return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """캐시에 값 저장"""
        try:
            # Redis에 저장
            if self.redis_client:
                try:
                    serialized = self._serialize(value)
                    self.redis_client.setex(key, ttl, serialized)
                except RedisError as e:
                    logger.error(f"Redis 쓰기 오류: {e}")
            
            # 메모리 캐시에도 저장
            self.memory_cache[key] = value
            
            # 메모리 캐시 크기 제한 (최대 1000개)
            if len(self.memory_cache) > 1000:
                # 가장 오래된 항목 제거
                oldest_key = next(iter(self.memory_cache))
                del self.memory_cache[oldest_key]
                
        except Exception as e:
            logger.error(f"캐시 저장 오류: {e}")
    
    def delete(self, key: str):
        """캐시에서 값 삭제"""
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            
            if key in self.memory_cache:
                del self.memory_cache[key]
                
        except Exception as e:
            logger.error(f"캐시 삭제 오류: {e}")
    
    def clear_pattern(self, pattern: str):
        """패턴에 맞는 캐시 삭제"""
        try:
            if self.redis_client:
                for key in self.redis_client.scan_iter(match=pattern):
                    self.redis_client.delete(key)
            
            # 메모리 캐시에서도 삭제
            keys_to_delete = [k for k in self.memory_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self.memory_cache[key]
                
        except Exception as e:
            logger.error(f"패턴 캐시 삭제 오류: {e}")


# 싱글톤 인스턴스
cache_manager = CacheManager()


def cached(prefix: str, ttl: int = 3600):
    """캐싱 데코레이터"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = cache_manager._generate_key(prefix, *args, **kwargs)
            
            # 캐시 확인
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"캐시 히트: {cache_key}")
                return cached_value
            
            # 함수 실행
            result = await func(*args, **kwargs)
            
            # 결과 캐싱
            cache_manager.set(cache_key, result, ttl)
            logger.debug(f"캐시 저장: {cache_key}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = cache_manager._generate_key(prefix, *args, **kwargs)
            
            # 캐시 확인
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"캐시 히트: {cache_key}")
                return cached_value
            
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 결과 캐싱
            cache_manager.set(cache_key, result, ttl)
            logger.debug(f"캐시 저장: {cache_key}")
            
            return result
        
        # 비동기/동기 함수 구분
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class ExcelAnalysisCache:
    """Excel 분석 전용 캐시"""
    
    @staticmethod
    def get_file_hash(file_path: str) -> str:
        """파일 해시 생성"""
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256()  # SHA256 사용 (보안성 향상)
            while chunk := f.read(8192):
                file_hash.update(chunk)
        return file_hash.hexdigest()
    
    @staticmethod
    def get_analysis_cache_key(file_path: str, analysis_type: str) -> str:
        """분석 캐시 키 생성"""
        file_hash = ExcelAnalysisCache.get_file_hash(file_path)
        return f"excel_analysis:{analysis_type}:{file_hash}"
    
    @staticmethod
    def cache_analysis_result(file_path: str, analysis_type: str, result: Any, ttl: int = 7200):
        """분석 결과 캐싱"""
        cache_key = ExcelAnalysisCache.get_analysis_cache_key(file_path, analysis_type)
        cache_manager.set(cache_key, result, ttl)
    
    @staticmethod
    def get_cached_analysis(file_path: str, analysis_type: str) -> Optional[Any]:
        """캐시된 분석 결과 조회"""
        cache_key = ExcelAnalysisCache.get_analysis_cache_key(file_path, analysis_type)
        return cache_manager.get(cache_key)


# 일반적인 캐시 TTL 상수
CACHE_TTL = {
    'SHORT': 300,      # 5분
    'MEDIUM': 3600,    # 1시간
    'LONG': 7200,      # 2시간
    'DAY': 86400,      # 1일
    'WEEK': 604800     # 1주일
}