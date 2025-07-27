"""
OCR 결과 캐싱 서비스
이미지 해시를 기반으로 OCR 결과를 Redis에 캐싱
"""

import redis
import hashlib
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class OCRCacheService:
    """OCR 결과 캐싱을 위한 Redis 기반 서비스"""
    
    def __init__(self):
        """Redis 연결 초기화"""
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 1))  # OCR 전용 DB
        self.cache_ttl = int(os.getenv('OCR_CACHE_TTL', 86400))  # 24시간
        
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # 연결 테스트
            self.redis_client.ping()
            logger.info(f"Redis OCR cache connected: {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.warning(f"Redis connection failed, cache disabled: {e}")
            self.redis_client = None
    
    def generate_image_hash(self, image_data: bytes, language: str = None, params: Dict = None) -> str:
        """이미지 데이터와 파라미터를 기반으로 고유 해시 생성"""
        hash_obj = hashlib.sha256()
        hash_obj.update(image_data)
        
        # 언어와 처리 파라미터도 해시에 포함
        if language:
            hash_obj.update(language.encode('utf-8'))
        
        if params:
            # 파라미터를 정렬된 JSON으로 변환하여 일관성 확보
            params_str = json.dumps(params, sort_keys=True)
            hash_obj.update(params_str.encode('utf-8'))
        
        return hash_obj.hexdigest()
    
    def get_cached_result(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """캐시된 OCR 결과 조회"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"ocr_result:{image_hash}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                result = json.loads(cached_data)
                # 캐시 히트 통계 업데이트
                self.redis_client.incr("ocr_cache:hits")
                
                logger.info(f"OCR cache hit: {image_hash[:12]}...")
                
                # 캐시된 시간 정보 추가
                result['cached'] = True
                result['cache_time'] = result.get('cache_time')
                
                return result
            
            # 캐시 미스 통계 업데이트
            self.redis_client.incr("ocr_cache:misses")
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def cache_result(self, image_hash: str, ocr_result: Dict[str, Any]) -> bool:
        """OCR 결과를 캐시에 저장"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"ocr_result:{image_hash}"
            
            # 캐시 메타데이터 추가
            cache_data = ocr_result.copy()
            cache_data['cache_time'] = datetime.now().isoformat()
            cache_data['cached'] = False  # 원본 결과임을 표시
            
            # JSON 직렬화
            cache_json = json.dumps(cache_data, ensure_ascii=False)
            
            # Redis에 저장 (TTL 설정)
            success = self.redis_client.setex(
                cache_key, 
                self.cache_ttl, 
                cache_json
            )
            
            if success:
                # 저장된 캐시 수 통계 업데이트
                self.redis_client.incr("ocr_cache:stored")
                logger.info(f"OCR result cached: {image_hash[:12]}... (TTL: {self.cache_ttl}s)")
                return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
        
        return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        if not self.redis_client:
            return {"status": "disabled", "reason": "Redis not available"}
        
        try:
            hits = int(self.redis_client.get("ocr_cache:hits") or 0)
            misses = int(self.redis_client.get("ocr_cache:misses") or 0)
            stored = int(self.redis_client.get("ocr_cache:stored") or 0)
            
            total_requests = hits + misses
            hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
            
            # Redis 메모리 사용량 정보
            redis_info = self.redis_client.info()
            memory_used = redis_info.get('used_memory_human', 'N/A')
            
            # 현재 저장된 OCR 캐시 키 수
            cache_keys = self.redis_client.keys("ocr_result:*")
            active_cache_count = len(cache_keys)
            
            return {
                "status": "active",
                "cache_hits": hits,
                "cache_misses": misses,
                "cache_stored": stored,
                "hit_rate_percent": round(hit_rate, 2),
                "active_cache_count": active_cache_count,
                "ttl_seconds": self.cache_ttl,
                "memory_used": memory_used,
                "redis_info": {
                    "connected_clients": redis_info.get('connected_clients', 0),
                    "uptime_in_seconds": redis_info.get('uptime_in_seconds', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {"status": "error", "error": str(e)}
    
    def clear_cache(self, pattern: str = "ocr_result:*") -> int:
        """캐시 클리어"""
        if not self.redis_client:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries")
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    def is_available(self) -> bool:
        """캐시 서비스 사용 가능 여부"""
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def get_cache_key_info(self, image_hash: str) -> Dict[str, Any]:
        """특정 캐시 키의 상세 정보"""
        if not self.redis_client:
            return {"status": "disabled"}
        
        try:
            cache_key = f"ocr_result:{image_hash}"
            
            # 키 존재 여부
            exists = self.redis_client.exists(cache_key)
            if not exists:
                return {"status": "not_found"}
            
            # TTL 정보
            ttl = self.redis_client.ttl(cache_key)
            
            # 데이터 크기
            data = self.redis_client.get(cache_key)
            data_size = len(data.encode('utf-8')) if data else 0
            
            return {
                "status": "found",
                "ttl_seconds": ttl,
                "data_size_bytes": data_size,
                "expires_at": (datetime.now() + timedelta(seconds=ttl)).isoformat() if ttl > 0 else "never"
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

# 전역 캐시 서비스 인스턴스
ocr_cache = OCRCacheService()