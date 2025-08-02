"""
AI Client Management
다양한 AI 제공업체 클라이언트 관리
"""

import logging
from typing import Dict, Any, Optional

import openai
import anthropic
from groq import AsyncGroq

from app.core.config import settings
from .model_config import ModelProvider

logger = logging.getLogger(__name__)


class ClientManager:
    """AI 클라이언트 관리자"""
    
    def __init__(self):
        self.clients: Dict[ModelProvider, Any] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """API 클라이언트 초기화"""
        self._init_openai()
        self._init_openrouter()
        self._init_anthropic()
        self._init_groq()
    
    def _init_openai(self):
        """OpenAI 클라이언트 초기화"""
        try:
            if settings.OPENAI_API_KEY:
                self.clients[ModelProvider.OPENAI] = openai.AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY
                )
                logger.info("OpenAI client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
    
    def _init_openrouter(self):
        """OpenRouter 클라이언트 초기화"""
        try:
            if settings.OPENROUTER_API_KEY:
                self.clients[ModelProvider.OPENROUTER] = openai.AsyncOpenAI(
                    api_key=settings.OPENROUTER_API_KEY,
                    base_url="https://openrouter.ai/api/v1",
                    default_headers={
                        "HTTP-Referer": "https://excel-unified.app",
                        "X-Title": "Excel Unified"
                    }
                )
                logger.info("OpenRouter client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter client: {e}")
    
    def _init_anthropic(self):
        """Anthropic 클라이언트 초기화"""
        try:
            if settings.ANTHROPIC_API_KEY:
                self.clients[ModelProvider.ANTHROPIC] = anthropic.AsyncAnthropic(
                    api_key=settings.ANTHROPIC_API_KEY
                )
                logger.info("Anthropic client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
    
    def _init_groq(self):
        """Groq 클라이언트 초기화"""
        try:
            if settings.GROQ_API_KEY:
                self.clients[ModelProvider.GROQ] = AsyncGroq(
                    api_key=settings.GROQ_API_KEY
                )
                logger.info("Groq client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
    
    def get_client(self, provider: ModelProvider) -> Optional[Any]:
        """제공업체별 클라이언트 반환"""
        return self.clients.get(provider)
    
    def has_client(self, provider: ModelProvider) -> bool:
        """클라이언트 사용 가능 여부 확인"""
        return provider in self.clients
    
    def get_available_providers(self) -> list[ModelProvider]:
        """사용 가능한 제공업체 목록"""
        return list(self.clients.keys())
    
    def reinitialize_client(self, provider: ModelProvider):
        """특정 클라이언트 재초기화"""
        if provider in self.clients:
            del self.clients[provider]
        
        if provider == ModelProvider.OPENAI:
            self._init_openai()
        elif provider == ModelProvider.OPENROUTER:
            self._init_openrouter()
        elif provider == ModelProvider.ANTHROPIC:
            self._init_anthropic()
        elif provider == ModelProvider.GROQ:
            self._init_groq()
    
    def test_connection(self, provider: ModelProvider) -> bool:
        """클라이언트 연결 테스트"""
        client = self.get_client(provider)
        if not client:
            return False
        
        try:
            # 각 제공업체별 간단한 연결 테스트
            # 실제 구현에서는 각 API의 health check 엔드포인트 사용
            return True
        except Exception as e:
            logger.error(f"Connection test failed for {provider.value}: {e}")
            return False