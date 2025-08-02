"""
Rate Limiting Management
API 호출 제한 관리
"""

import time
import logging
from typing import Dict, List
from collections import defaultdict

from .model_config import ModelConfig

logger = logging.getLogger(__name__)


class RateLimiter:
    """API 호출 제한 관리자"""
    
    def __init__(self):
        self.request_history: Dict[str, List[float]] = defaultdict(list)
        self.token_history: Dict[str, List[tuple]] = defaultdict(list)
    
    def check_rate_limit(self, model_config: ModelConfig) -> bool:
        """Rate limit 체크"""
        model_key = f"{model_config.provider.value}:{model_config.model_name}"
        now = time.time()
        
        # RPM (Requests Per Minute) 체크
        if not self._check_rpm(model_key, model_config.rate_limit_rpm, now):
            return False
        
        # TPM (Tokens Per Minute) 체크는 실제 토큰 수가 필요하므로 
        # 호출 후에 업데이트
        return True
    
    def _check_rpm(self, model_key: str, limit: int, now: float) -> bool:
        """분당 요청 수 제한 체크"""
        minute_ago = now - 60
        
        # 1분 전 요청들 제거
        self.request_history[model_key] = [
            req_time for req_time in self.request_history[model_key]
            if req_time > minute_ago
        ]
        
        # 제한 체크
        if len(self.request_history[model_key]) >= limit:
            logger.warning(f"RPM limit exceeded for {model_key}: {len(self.request_history[model_key])}/{limit}")
            return False
        
        return True
    
    def record_request(self, model_config: ModelConfig, token_count: int = 0):
        """요청 기록"""
        model_key = f"{model_config.provider.value}:{model_config.model_name}"
        now = time.time()
        
        # 요청 시간 기록
        self.request_history[model_key].append(now)
        
        # 토큰 사용량 기록
        if token_count > 0:
            self.token_history[model_key].append((now, token_count))
    
    def get_current_usage(self, model_config: ModelConfig) -> Dict[str, int]:
        """현재 사용량 반환"""
        model_key = f"{model_config.provider.value}:{model_config.model_name}"
        now = time.time()
        minute_ago = now - 60
        
        # 최근 1분간 요청 수
        recent_requests = [
            req_time for req_time in self.request_history[model_key]
            if req_time > minute_ago
        ]
        
        # 최근 1분간 토큰 수
        recent_tokens = [
            token_count for req_time, token_count in self.token_history[model_key]
            if req_time > minute_ago
        ]
        
        return {
            "current_rpm": len(recent_requests),
            "max_rpm": model_config.rate_limit_rpm,
            "current_tpm": sum(recent_tokens),
            "max_tpm": model_config.rate_limit_tpm
        }
    
    def get_wait_time(self, model_config: ModelConfig) -> float:
        """다음 요청까지 대기 시간 (초)"""
        model_key = f"{model_config.provider.value}:{model_config.model_name}"
        
        if not self.request_history[model_key]:
            return 0.0
        
        now = time.time()
        minute_ago = now - 60
        
        # 1분 전 이후의 요청들
        recent_requests = [
            req_time for req_time in self.request_history[model_key]
            if req_time > minute_ago
        ]
        
        if len(recent_requests) < model_config.rate_limit_rpm:
            return 0.0
        
        # 가장 오래된 요청이 1분이 지날 때까지 대기
        oldest_request = min(recent_requests)
        wait_time = 60 - (now - oldest_request)
        
        return max(0.0, wait_time)
    
    def cleanup_old_records(self, max_age_hours: int = 24):
        """오래된 기록 정리"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        # 요청 기록 정리
        for model_key in list(self.request_history.keys()):
            self.request_history[model_key] = [
                req_time for req_time in self.request_history[model_key]
                if req_time > cutoff_time
            ]
            
            # 빈 리스트 제거
            if not self.request_history[model_key]:
                del self.request_history[model_key]
        
        # 토큰 기록 정리
        for model_key in list(self.token_history.keys()):
            self.token_history[model_key] = [
                (req_time, token_count) 
                for req_time, token_count in self.token_history[model_key]
                if req_time > cutoff_time
            ]
            
            # 빈 리스트 제거
            if not self.token_history[model_key]:
                del self.token_history[model_key]
    
    def reset_limits(self, model_key: str = None):
        """제한 리셋 (테스트용)"""
        if model_key:
            self.request_history.pop(model_key, None)
            self.token_history.pop(model_key, None)
        else:
            self.request_history.clear()
            self.token_history.clear()
    
    def get_statistics(self) -> Dict[str, Dict]:
        """통계 조회"""
        stats = {}
        now = time.time()
        
        for model_key in self.request_history.keys():
            # 최근 24시간 요청 수
            day_ago = now - 86400
            daily_requests = [
                req_time for req_time in self.request_history[model_key]
                if req_time > day_ago
            ]
            
            # 최근 1시간 요청 수
            hour_ago = now - 3600
            hourly_requests = [
                req_time for req_time in self.request_history[model_key]
                if req_time > hour_ago
            ]
            
            stats[model_key] = {
                "daily_requests": len(daily_requests),
                "hourly_requests": len(hourly_requests),
                "total_requests": len(self.request_history[model_key])
            }
        
        return stats