"""
AI Failover Service 테스트
다중 AI 모델 페일오버 시스템의 단위 및 통합 테스트
"""

import pytest
import asyncio
from unittest.mock import patch

from app.services.ai_failover_service import AIFailoverService
from app.services.ai_failover.model_config import (
    ModelProvider,
    ModelTier,
    ModelConfig,
    ModelStatus,
)


@pytest.fixture
def mock_settings():
    """모의 설정 객체"""
    with patch("app.core.config.settings") as mock:
        mock.OPENAI_API_KEY = "test-key"
        mock.ANTHROPIC_API_KEY = "test-key"
        mock.GROQ_API_KEY = "test-key"
        mock.OPENROUTER_API_KEY = "test-key"
        yield mock


@pytest.fixture
def ai_failover_service(mock_settings):
    """AI Failover Service 인스턴스"""
    service = AIFailoverService()
    return service


@pytest.fixture
def sample_messages():
    """샘플 메시지"""
    return [{"role": "user", "content": "Hello, how can you help me with Excel?"}]


class TestModelConfigManager:
    """모델 설정 관리자 테스트"""

    def test_get_all_models(self, ai_failover_service):
        """모든 모델 조회 테스트"""
        models = ai_failover_service.config_manager.get_all_models()
        assert len(models) > 0
        assert all(isinstance(model, ModelConfig) for model in models)

    def test_model_priorities(self, ai_failover_service):
        """모델 우선순위 정렬 테스트"""
        models = ai_failover_service.config_manager.get_all_models()
        priorities = [model.priority for model in models]
        assert priorities == sorted(priorities)

    def test_tier_filtering(self, ai_failover_service):
        """티어별 필터링 테스트"""
        premium_models = ai_failover_service.get_available_models(
            tier=ModelTier.PREMIUM
        )
        for model in premium_models:
            assert model.tier == ModelTier.PREMIUM


class TestClientManager:
    """클라이언트 관리자 테스트"""

    def test_client_initialization(self, ai_failover_service):
        """클라이언트 초기화 테스트"""
        client_manager = ai_failover_service.client_manager

        # 클라이언트가 올바르게 초기화되었는지 확인
        available_providers = client_manager.get_available_providers()
        assert ModelProvider.OPENAI in available_providers

    def test_has_client(self, ai_failover_service):
        """클라이언트 존재 여부 확인 테스트"""
        client_manager = ai_failover_service.client_manager
        assert client_manager.has_client(ModelProvider.OPENAI)


class TestRateLimiter:
    """Rate Limiter 테스트"""

    def test_check_rate_limit_new_model(self, ai_failover_service):
        """새 모델의 rate limit 체크"""
        models = ai_failover_service.config_manager.get_all_models()
        test_model = models[0]

        # 새 모델은 rate limit을 통과해야 함
        assert ai_failover_service.rate_limiter.check_rate_limit(test_model)

    def test_record_request(self, ai_failover_service):
        """요청 기록 테스트"""
        models = ai_failover_service.config_manager.get_all_models()
        test_model = models[0]

        ai_failover_service.rate_limiter.record_request(test_model, 100)

        usage = ai_failover_service.rate_limiter.get_current_usage(test_model)
        assert usage["current_rpm"] == 1
        assert usage["current_tpm"] == 100

    def test_rate_limit_exceeded(self, ai_failover_service):
        """Rate limit 초과 테스트"""
        models = ai_failover_service.config_manager.get_all_models()
        test_model = models[0]

        # Rate limit를 초과하도록 요청 기록
        for _ in range(test_model.rate_limit_rpm + 1):
            ai_failover_service.rate_limiter.record_request(test_model)

        assert not ai_failover_service.rate_limiter.check_rate_limit(test_model)


class TestExecutionEngine:
    """실행 엔진 테스트"""

    def test_validate_messages_valid(self, ai_failover_service, sample_messages):
        """유효한 메시지 검증 테스트"""
        assert ai_failover_service.execution_engine.validate_messages(sample_messages)

    def test_validate_messages_invalid(self, ai_failover_service):
        """무효한 메시지 검증 테스트"""
        invalid_messages = [
            {"content": "Missing role"},  # role 누락
            {"role": "invalid_role", "content": "Invalid role"},  # 잘못된 role
        ]
        assert not ai_failover_service.execution_engine.validate_messages(
            invalid_messages
        )

    def test_estimate_tokens(self, ai_failover_service, sample_messages):
        """토큰 수 추정 테스트"""
        token_count = ai_failover_service.execution_engine.estimate_tokens(
            sample_messages
        )
        assert token_count > 0
        assert isinstance(token_count, int)

    def test_prepare_vision_messages(self, ai_failover_service):
        """비전 메시지 준비 테스트"""
        models = ai_failover_service.config_manager.get_all_models()
        vision_model = next((m for m in models if m.supports_vision), None)

        if vision_model:
            vision_messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in this image?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/jpeg;base64,..."},
                        },
                    ],
                }
            ]

            prepared = ai_failover_service.execution_engine.prepare_vision_messages(
                vision_messages, vision_model
            )
            assert len(prepared) == 1


@pytest.mark.asyncio
class TestAIFailoverService:
    """AI Failover Service 통합 테스트"""

    async def test_get_available_models(self, ai_failover_service):
        """사용 가능한 모델 조회 테스트"""
        models = ai_failover_service.get_available_models()
        assert len(models) > 0

        # 모든 모델이 활성화되어 있고 건강한 상태인지 확인
        for model in models:
            assert model.enabled
            model_key = f"{model.provider.value}:{model.model_name}"
            status = ai_failover_service.model_status.get(model_key)
            if status:
                assert status.is_healthy

    async def test_get_available_models_with_filters(self, ai_failover_service):
        """필터링된 모델 조회 테스트"""
        # 비전 지원 모델만 조회
        vision_models = ai_failover_service.get_available_models(supports_vision=True)
        for model in vision_models:
            assert model.supports_vision

        # 함수 호출 지원 모델만 조회
        function_models = ai_failover_service.get_available_models(
            supports_function_calling=True
        )
        for model in function_models:
            assert model.supports_function_calling

    @patch(
        "app.services.ai_failover.execution_engine.ExecutionEngine.execute_chat_completion"
    )
    async def test_chat_completion_success(
        self, mock_execute, ai_failover_service, sample_messages
    ):
        """채팅 완성 성공 테스트"""
        mock_execute.return_value = "Test response"

        result = await ai_failover_service.chat_completion_with_failover(
            sample_messages
        )
        assert result == "Test response"
        mock_execute.assert_called_once()

    @patch(
        "app.services.ai_failover.execution_engine.ExecutionEngine.execute_chat_completion"
    )
    async def test_chat_completion_failover(
        self, mock_execute, ai_failover_service, sample_messages
    ):
        """채팅 완성 페일오버 테스트"""
        # 첫 번째 호출은 실패, 두 번째는 성공
        mock_execute.side_effect = [Exception("API Error"), "Fallback response"]

        result = await ai_failover_service.chat_completion_with_failover(
            sample_messages
        )
        assert result == "Fallback response"
        assert mock_execute.call_count == 2

    @patch(
        "app.services.ai_failover.execution_engine.ExecutionEngine.execute_chat_completion"
    )
    async def test_chat_completion_all_models_fail(
        self, mock_execute, ai_failover_service, sample_messages
    ):
        """모든 모델 실패 테스트"""
        mock_execute.side_effect = Exception("All models failed")

        with pytest.raises(Exception, match="All AI models failed"):
            await ai_failover_service.chat_completion_with_failover(sample_messages)

    def test_update_model_success(self, ai_failover_service):
        """모델 성공 상태 업데이트 테스트"""
        models = ai_failover_service.config_manager.get_all_models()
        test_model = models[0]

        ai_failover_service._update_model_success(test_model, 1.5)

        model_key = f"{test_model.provider.value}:{test_model.model_name}"
        status = ai_failover_service.model_status[model_key]

        assert status.success_count == 1
        assert status.consecutive_failures == 0
        assert status.is_healthy
        assert status.avg_response_time == 1.5

    def test_update_model_failure(self, ai_failover_service):
        """모델 실패 상태 업데이트 테스트"""
        models = ai_failover_service.config_manager.get_all_models()
        test_model = models[0]

        # 3번 연속 실패로 비활성화
        for i in range(3):
            ai_failover_service._update_model_failure(test_model, f"Error {i+1}")

        model_key = f"{test_model.provider.value}:{test_model.model_name}"
        status = ai_failover_service.model_status[model_key]

        assert status.failure_count == 3
        assert status.consecutive_failures == 3
        assert not status.is_healthy

    def test_get_system_status(self, ai_failover_service):
        """시스템 상태 조회 테스트"""
        status = ai_failover_service.get_system_status()

        assert "total_models" in status
        assert "healthy_models" in status
        assert "unhealthy_models" in status
        assert "providers" in status
        assert "models" in status

        assert isinstance(status["total_models"], int)
        assert status["total_models"] > 0

    async def test_health_monitoring(self, ai_failover_service):
        """헬스 모니터링 테스트"""
        # 헬스체크가 시작되었는지 확인
        assert ai_failover_service.health_check_task is not None
        assert not ai_failover_service.health_check_task.done()

    @patch(
        "app.services.ai_failover.execution_engine.ExecutionEngine.test_model_health"
    )
    async def test_health_check_model_recovery(self, mock_health, ai_failover_service):
        """모델 상태 복구 테스트"""
        models = ai_failover_service.config_manager.get_all_models()
        test_model = models[0]

        # 모델을 비활성화 상태로 설정
        model_key = f"{test_model.provider.value}:{test_model.model_name}"
        status = ai_failover_service.model_status[model_key]
        status.is_healthy = False
        status.consecutive_failures = 3

        # 헬스체크가 성공하도록 설정
        mock_health.return_value = True

        # 헬스체크 수행
        await ai_failover_service._health_check_model(test_model)

        # 상태가 복구되었는지 확인
        assert status.is_healthy
        assert status.consecutive_failures == 0

    async def test_shutdown(self, ai_failover_service):
        """서비스 종료 테스트"""
        await ai_failover_service.shutdown()

        # 헬스체크 태스크가 취소되었는지 확인
        if ai_failover_service.health_check_task:
            assert ai_failover_service.health_check_task.cancelled()


class TestModelConfig:
    """모델 설정 테스트"""

    def test_model_config_creation(self):
        """모델 설정 생성 테스트"""
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4",
            tier=ModelTier.PREMIUM,
            priority=1,
            temperature=0.7,
            max_tokens=2048,
            timeout_seconds=30,
            rate_limit_rpm=60,
            rate_limit_tpm=40000,
            supports_vision=True,
            supports_function_calling=True,
            enabled=True,
        )

        assert config.provider == ModelProvider.OPENAI
        assert config.model_name == "gpt-4"
        assert config.tier == ModelTier.PREMIUM
        assert config.supports_vision
        assert config.supports_function_calling

    def test_model_status_creation(self):
        """모델 상태 생성 테스트"""
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4",
            tier=ModelTier.PREMIUM,
            priority=1,
        )

        status = ModelStatus(config=config)

        assert status.config == config
        assert status.is_healthy
        assert status.success_count == 0
        assert status.failure_count == 0
        assert status.consecutive_failures == 0
        assert len(status.error_messages) == 0


@pytest.mark.integration
class TestAIFailoverIntegration:
    """AI Failover Service 통합 테스트"""

    @pytest.mark.asyncio
    async def test_complete_workflow(self, ai_failover_service, sample_messages):
        """전체 워크플로우 통합 테스트"""
        # 이 테스트는 실제 API 키가 필요하므로 mock을 사용
        with patch(
            "app.services.ai_failover.execution_engine.ExecutionEngine.execute_chat_completion"
        ) as mock_execute:
            mock_execute.return_value = "Integration test response"

            # 1. 사용 가능한 모델 확인
            models = ai_failover_service.get_available_models()
            assert len(models) > 0

            # 2. 채팅 완성 실행
            result = await ai_failover_service.chat_completion_with_failover(
                sample_messages
            )
            assert result == "Integration test response"

            # 3. 시스템 상태 확인
            status = ai_failover_service.get_system_status()
            assert status["healthy_models"] > 0

    @pytest.mark.asyncio
    async def test_stress_test(self, ai_failover_service, sample_messages):
        """스트레스 테스트 - 동시 요청 처리"""
        with patch(
            "app.services.ai_failover.execution_engine.ExecutionEngine.execute_chat_completion"
        ) as mock_execute:
            mock_execute.return_value = "Stress test response"

            # 10개의 동시 요청 실행
            tasks = []
            for i in range(10):
                task = ai_failover_service.chat_completion_with_failover(
                    sample_messages
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # 모든 요청이 성공했는지 확인
            for result in results:
                assert result == "Stress test response"
