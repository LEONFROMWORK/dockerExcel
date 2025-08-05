"""
AI Model Failover Service (Refactored)
다중 모델 지원과 자동 페일오버를 통한 서비스 안정성 보장
"""

import asyncio
import logging
import time
import json
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from datetime import datetime

from .ai_failover.model_config import (
    ModelTier,
    ModelConfig,
    ModelStatus,
    ModelConfigManager,
)
from .ai_failover.client_manager import ClientManager
from .ai_failover.rate_limiter import RateLimiter
from .ai_failover.execution_engine import ExecutionEngine

logger = logging.getLogger(__name__)


class AIFailoverService:
    """AI 모델 페일오버 관리 서비스 (리팩토링됨)"""

    def __init__(self):
        # 모듈화된 컴포넌트들
        self.config_manager = ModelConfigManager()
        self.client_manager = ClientManager()
        self.rate_limiter = RateLimiter()
        self.execution_engine = ExecutionEngine(self.client_manager)

        # 상태 관리
        self.model_status: Dict[str, ModelStatus] = {}
        self.fallback_cache: Dict[str, Any] = {}
        self.max_cache_size = 100  # 캐시 크기 제한

        # 모델 상태 초기화
        self._initialize_model_status()

        # 헬스체크 태스크 시작 (이벤트 루프가 실행될 때까지 지연)
        self.health_check_task = None
        self._health_monitoring_enabled = True

    def _initialize_model_status(self):
        """모델 상태 초기화"""
        for model in self.config_manager.get_all_models():
            model_key = f"{model.provider.value}:{model.model_name}"
            self.model_status[model_key] = ModelStatus(config=model)

    def get_available_models(
        self,
        tier: Optional[ModelTier] = None,
        supports_vision: Optional[bool] = None,
        supports_function_calling: Optional[bool] = None,
    ) -> List[ModelConfig]:
        """사용 가능한 모델 목록 반환 (필터링 가능)"""
        available_models = []

        for model in self.config_manager.get_all_models():
            # 클라이언트 사용가능성 체크
            if not self.client_manager.has_client(model.provider):
                continue

            # 활성화 및 건강 상태 체크
            if not model.enabled:
                continue

            model_key = f"{model.provider.value}:{model.model_name}"
            status = self.model_status.get(model_key)
            if not status or not status.is_healthy:
                continue

            # 필터 적용
            if self._matches_filters(
                model, tier, supports_vision, supports_function_calling
            ):
                available_models.append(model)

        # 우선순위 순으로 정렬
        return sorted(available_models, key=lambda m: m.priority)

    def _matches_filters(self, model, tier, supports_vision, supports_function_calling):
        """모델이 필터 조건에 맞는지 확인"""
        if tier and model.tier != tier:
            return False
        if supports_vision is not None and model.supports_vision != supports_vision:
            return False
        if (
            supports_function_calling is not None
            and model.supports_function_calling != supports_function_calling
        ):
            return False
        return True

    async def chat_completion_with_failover(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        required_tier: Optional[ModelTier] = None,
        supports_vision: Optional[bool] = None,
        supports_function_calling: Optional[bool] = None,
        max_retries: int = 3,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """페일오버를 지원하는 채팅 완성"""

        # 검증
        if not self.execution_engine.validate_messages(messages):
            raise ValueError(
                "Invalid message format. Messages must be a list of dicts with 'role' and 'content' keys"
            )

        available_models = self.get_available_models(
            tier=required_tier,
            supports_vision=supports_vision,
            supports_function_calling=supports_function_calling,
        )

        if not available_models:
            return self._try_fallback_cache(messages)

        # 모델 순회하며 시도
        for model_config in available_models:
            try:
                result = await self._try_model_execution(
                    model_config, messages, temperature, max_tokens, stream
                )
                if result:
                    return result
            except Exception as e:
                logger.error(f"Model {model_config.model_name} failed: {str(e)}")
                self._update_model_failure(model_config, str(e))
                continue

        # 모든 모델 실패
        return self._handle_complete_failure(messages)

    async def _try_model_execution(
        self, model_config, messages, temperature, max_tokens, stream
    ):
        """개별 모델 실행 시도"""
        logger.info(
            f"Attempting with model: {model_config.provider.value}:{model_config.model_name}"
        )

        # Rate limiting 체크
        if not self.rate_limiter.check_rate_limit(model_config):
            logger.warning(f"Rate limit exceeded for {model_config.model_name}")
            return None

        # 실행
        start_time = time.time()
        result = await self.execution_engine.execute_chat_completion(
            model_config, messages, temperature, max_tokens, stream
        )

        # 성공 처리
        execution_time = time.time() - start_time
        token_count = self.execution_engine.estimate_tokens(messages)

        self._update_model_success(model_config, execution_time)
        self.rate_limiter.record_request(model_config, token_count)

        return result

    def _try_fallback_cache(self, messages):
        """캐시된 응답 시도"""
        cache_key = self._generate_cache_key(messages)
        if cache_key in self.fallback_cache:
            logger.info("Using cached fallback response")
            return self.fallback_cache[cache_key]
        raise Exception("No available AI models found")

    def _handle_complete_failure(self, messages):
        """모든 모델 실패 시 처리"""
        logger.error("All AI models failed")
        cache_key = self._generate_cache_key(messages)
        if cache_key in self.fallback_cache:
            logger.info("Using cached fallback response")
            return self.fallback_cache[cache_key]

        # 캐시 크기 관리
        if len(self.fallback_cache) > self.max_cache_size:
            # 가장 오래된 항목 제거 (간단한 FIFO)
            oldest_key = next(iter(self.fallback_cache))
            del self.fallback_cache[oldest_key]

        raise Exception("All AI models failed")

    def _update_model_success(self, model_config: ModelConfig, response_time: float):
        """모델 성공 상태 업데이트"""
        model_key = f"{model_config.provider.value}:{model_config.model_name}"
        status = self.model_status[model_key]

        status.success_count += 1
        status.last_success = datetime.now()
        status.consecutive_failures = 0
        status.is_healthy = True

        # 평균 응답 시간 업데이트
        if status.avg_response_time == 0:
            status.avg_response_time = response_time
        else:
            status.avg_response_time = (status.avg_response_time * 0.9) + (
                response_time * 0.1
            )

    def _update_model_failure(self, model_config: ModelConfig, error_message: str):
        """모델 실패 상태 업데이트"""
        model_key = f"{model_config.provider.value}:{model_config.model_name}"
        status = self.model_status[model_key]

        status.failure_count += 1
        status.last_failure = datetime.now()
        status.consecutive_failures += 1

        # 연속 실패 시 비활성화
        if status.consecutive_failures >= 3:
            status.is_healthy = False
            logger.warning(
                f"Model {model_key} marked as unhealthy after 3 consecutive failures"
            )

        # 오류 메시지 저장 (최근 10개만)
        status.error_messages.append(f"{datetime.now()}: {error_message}")
        if len(status.error_messages) > 10:
            status.error_messages.pop(0)

    def _generate_cache_key(self, messages: List[Dict[str, str]]) -> str:
        """캐시 키 생성"""
        content = json.dumps(messages, sort_keys=True)
        return str(hash(content))

    def _start_health_monitoring(self):
        """헬스 모니터링 시작"""
        if not self._health_monitoring_enabled:
            return

        try:
            # 이벤트 루프가 실행 중인지 확인
            asyncio.get_running_loop()

            async def health_monitor():
                while self._health_monitoring_enabled:
                    try:
                        await self._perform_health_checks()
                        await asyncio.sleep(300)  # 5분마다 체크
                    except Exception as e:
                        logger.error(f"Health monitoring error: {e}")
                        await asyncio.sleep(60)  # 오류 시 1분 후 재시도

            self.health_check_task = asyncio.create_task(health_monitor())
        except RuntimeError:
            # 이벤트 루프가 실행되지 않은 경우, 나중에 시작하도록 예약
            logger.debug(
                "Event loop not running, health monitoring will be started later"
            )

    async def _perform_health_checks(self):
        """모든 모델 헬스체크 수행"""
        logger.info("Performing health checks on AI models")

        for model_config in self.config_manager.get_all_models():
            if not self.client_manager.has_client(model_config.provider):
                continue

            model_key = f"{model_config.provider.value}:{model_config.model_name}"
            status = self.model_status[model_key]

            # 비활성화된 모델은 주기적으로 재시도
            if not status.is_healthy:
                try:
                    await self._health_check_model(model_config)
                    logger.info(f"Model {model_key} is back online")
                except Exception as e:
                    logger.debug(f"Model {model_key} still unhealthy: {e}")

            status.last_health_check = datetime.now()

    async def _health_check_model(self, model_config: ModelConfig):
        """개별 모델 헬스체크"""
        is_healthy = await self.execution_engine.test_model_health(model_config)
        if is_healthy:
            # 성공 시 상태 복구
            model_key = f"{model_config.provider.value}:{model_config.model_name}"
            status = self.model_status[model_key]
            status.is_healthy = True
            status.consecutive_failures = 0
        else:
            raise Exception("Health check failed")

    def get_system_status(self) -> Dict[str, Any]:
        """시스템 전체 상태 반환"""
        status_summary = {
            "total_models": 0,
            "healthy_models": 0,
            "unhealthy_models": 0,
            "providers": {},
            "models": {},
        }

        for model_key, status in self.model_status.items():
            status_summary["total_models"] += 1

            if status.is_healthy:
                status_summary["healthy_models"] += 1
            else:
                status_summary["unhealthy_models"] += 1

            provider = status.config.provider.value
            if provider not in status_summary["providers"]:
                status_summary["providers"][provider] = {
                    "healthy": 0,
                    "unhealthy": 0,
                    "available": self.client_manager.has_client(status.config.provider),
                }

            if status.is_healthy:
                status_summary["providers"][provider]["healthy"] += 1
            else:
                status_summary["providers"][provider]["unhealthy"] += 1

            # 모델별 상세 정보
            status_summary["models"][model_key] = {
                "provider": provider,
                "model_name": status.config.model_name,
                "tier": status.config.tier.value,
                "is_healthy": status.is_healthy,
                "success_count": status.success_count,
                "failure_count": status.failure_count,
                "consecutive_failures": status.consecutive_failures,
                "avg_response_time": status.avg_response_time,
                "last_success": (
                    status.last_success.isoformat() if status.last_success else None
                ),
                "last_failure": (
                    status.last_failure.isoformat() if status.last_failure else None
                ),
                "last_health_check": (
                    status.last_health_check.isoformat()
                    if status.last_health_check
                    else None
                ),
            }

        return status_summary

    async def shutdown(self):
        """서비스 종료"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        logger.info("AI Failover Service shutdown complete")


# 싱글톤 인스턴스
ai_failover_service = AIFailoverService()
