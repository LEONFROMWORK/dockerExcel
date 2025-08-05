"""
AI Model Configuration Management
모델 설정 및 상태 관리 분리
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime
from app.core.config import settings


class ModelProvider(Enum):
    """AI 모델 제공업체"""

    OPENAI = "openai"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    LOCAL = "local"


class ModelTier(Enum):
    """모델 성능 등급"""

    PREMIUM = "premium"
    STANDARD = "standard"
    BUDGET = "budget"
    FALLBACK = "fallback"


@dataclass
class ModelConfig:
    """AI 모델 설정"""

    provider: ModelProvider
    model_name: str
    tier: ModelTier
    max_tokens: int = 4096
    temperature: float = 0.7
    supports_vision: bool = False
    supports_function_calling: bool = False
    cost_per_1k_tokens: float = 0.0
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 60000
    timeout_seconds: int = 30
    enabled: bool = True
    priority: int = 0


@dataclass
class ModelStatus:
    """모델 상태 추적"""

    config: ModelConfig
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_response_time: float = 0.0
    current_rpm: int = 0
    current_tpm: int = 0
    is_healthy: bool = True
    consecutive_failures: int = 0
    last_health_check: Optional[datetime] = None
    error_messages: List[str] = field(default_factory=list)


class ModelConfigManager:
    """모델 설정 관리자"""

    def __init__(self):
        self.models: Dict[ModelProvider, List[ModelConfig]] = {}
        self._initialize_default_models()

    def _initialize_default_models(self):
        """기본 모델 설정 초기화"""
        # OpenAI 모델들 (낮은 우선순위 - 백업용)
        self.models[ModelProvider.OPENAI] = [
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4-turbo-preview",
                tier=ModelTier.PREMIUM,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.01,
                rate_limit_rpm=500,
                priority=10,  # 백업용으로 낮은 우선순위
                enabled=False,  # 현재 할당량 초과로 비활성화
            ),
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4",
                tier=ModelTier.PREMIUM,
                max_tokens=8192,
                supports_function_calling=True,
                cost_per_1k_tokens=0.03,
                rate_limit_rpm=200,
                priority=11,  # 백업용으로 낮은 우선순위
                enabled=False,  # 현재 할당량 초과로 비활성화
            ),
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-3.5-turbo",
                tier=ModelTier.STANDARD,
                supports_function_calling=True,
                cost_per_1k_tokens=0.0015,
                rate_limit_rpm=3500,
                priority=12,  # 백업용으로 낮은 우선순위
                enabled=False,  # 현재 할당량 초과로 비활성화
            ),
        ]

        # OpenRouter 모델들 (우선순위 높음)
        self.models[ModelProvider.OPENROUTER] = [
            ModelConfig(
                provider=ModelProvider.OPENROUTER,
                model_name="anthropic/claude-3-opus",
                tier=ModelTier.PREMIUM,
                max_tokens=4096,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.015,
                rate_limit_rpm=1000,
                priority=0,  # 최고 우선순위
                enabled=True,
            ),
            ModelConfig(
                provider=ModelProvider.OPENROUTER,
                model_name="openai/gpt-4-turbo-preview",
                tier=ModelTier.PREMIUM,
                max_tokens=128000,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.01,
                rate_limit_rpm=1000,
                priority=1,
                enabled=True,
            ),
            ModelConfig(
                provider=ModelProvider.OPENROUTER,
                model_name="openai/gpt-3.5-turbo",
                tier=ModelTier.STANDARD,
                max_tokens=16385,
                supports_function_calling=True,
                cost_per_1k_tokens=0.0005,
                rate_limit_rpm=2000,
                priority=2,
                enabled=True,
            ),
            ModelConfig(
                provider=ModelProvider.OPENROUTER,
                model_name="mistralai/mistral-7b-instruct:free",
                tier=ModelTier.BUDGET,
                cost_per_1k_tokens=0.0,
                rate_limit_rpm=200,
                priority=3,
                enabled=True,
            ),
            ModelConfig(
                provider=ModelProvider.OPENROUTER,
                model_name="meta-llama/llama-2-70b-chat",
                tier=ModelTier.STANDARD,
                cost_per_1k_tokens=0.0007,
                rate_limit_rpm=300,
                priority=4,
                enabled=True,
            ),
        ]

        # Anthropic 모델들 (중간 우선순위)
        self.models[ModelProvider.ANTHROPIC] = [
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-opus-20240229",
                tier=ModelTier.PREMIUM,
                supports_vision=True,
                cost_per_1k_tokens=0.015,
                rate_limit_rpm=100,
                priority=5,  # OpenRouter 다음 우선순위
                enabled=bool(getattr(settings, "ANTHROPIC_API_KEY", None)),
            ),
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-sonnet-20240229",
                tier=ModelTier.STANDARD,
                supports_vision=True,
                cost_per_1k_tokens=0.003,
                rate_limit_rpm=300,
                priority=6,
                enabled=bool(getattr(settings, "ANTHROPIC_API_KEY", None)),
            ),
        ]

        # Groq 모델들 (낮은 우선순위)
        self.models[ModelProvider.GROQ] = [
            ModelConfig(
                provider=ModelProvider.GROQ,
                model_name="llama3-70b-8192",
                tier=ModelTier.STANDARD,
                max_tokens=8192,
                cost_per_1k_tokens=0.0008,
                rate_limit_rpm=30,
                priority=7,
                enabled=bool(getattr(settings, "GROQ_API_KEY", None)),
            ),
            ModelConfig(
                provider=ModelProvider.GROQ,
                model_name="mixtral-8x7b-32768",
                tier=ModelTier.BUDGET,
                max_tokens=32768,
                cost_per_1k_tokens=0.0005,
                rate_limit_rpm=30,
                priority=8,
                enabled=bool(getattr(settings, "GROQ_API_KEY", None)),
            ),
        ]

    def get_models_by_provider(self, provider: ModelProvider) -> List[ModelConfig]:
        """제공업체별 모델 목록 반환"""
        return self.models.get(provider, [])

    def get_all_models(self) -> List[ModelConfig]:
        """모든 모델 목록 반환"""
        all_models = []
        for model_list in self.models.values():
            all_models.extend(model_list)
        return all_models

    def get_models_by_tier(self, tier: ModelTier) -> List[ModelConfig]:
        """등급별 모델 목록 반환"""
        return [
            model
            for model_list in self.models.values()
            for model in model_list
            if model.tier == tier
        ]

    def add_model(self, model_config: ModelConfig):
        """새 모델 추가"""
        if model_config.provider not in self.models:
            self.models[model_config.provider] = []
        self.models[model_config.provider].append(model_config)

    def remove_model(self, provider: ModelProvider, model_name: str):
        """모델 제거"""
        if provider in self.models:
            self.models[provider] = [
                model
                for model in self.models[provider]
                if model.model_name != model_name
            ]

    def update_model_config(self, provider: ModelProvider, model_name: str, **updates):
        """모델 설정 업데이트"""
        if provider not in self.models:
            return False

        for model in self.models[provider]:
            if model.model_name == model_name:
                for key, value in updates.items():
                    if hasattr(model, key):
                        setattr(model, key, value)
                return True
        return False
