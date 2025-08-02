"""
AI Model Execution Engine
실제 AI 모델 호출 및 응답 처리
"""

import time
import logging
from typing import List, Dict, Any, Union, AsyncGenerator, Optional

import openai
import anthropic

from .model_config import ModelConfig, ModelProvider

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """AI 모델 실행 엔진"""
    
    def __init__(self, client_manager):
        self.client_manager = client_manager
    
    async def execute_chat_completion(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """개별 모델로 채팅 완성 실행"""
        
        client = self.client_manager.get_client(model_config.provider)
        if not client:
            raise Exception(f"Client not available for {model_config.provider.value}")
        
        temperature = temperature or model_config.temperature
        max_tokens = max_tokens or model_config.max_tokens
        
        if model_config.provider in [ModelProvider.OPENAI, ModelProvider.OPENROUTER]:
            return await self._execute_openai_style(
                client, model_config, messages, temperature, max_tokens, stream
            )
        elif model_config.provider == ModelProvider.ANTHROPIC:
            return await self._execute_anthropic(
                client, model_config, messages, temperature, max_tokens, stream
            )
        elif model_config.provider == ModelProvider.GROQ:
            return await self._execute_groq(
                client, model_config, messages, temperature, max_tokens, stream
            )
        else:
            raise Exception(f"Unsupported provider: {model_config.provider}")
    
    async def _execute_openai_style(
        self, client, model_config, messages, temperature, max_tokens, stream
    ):
        """OpenAI/OpenRouter/Groq 스타일 실행"""
        response = await client.chat.completions.create(
            model=model_config.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            timeout=model_config.timeout_seconds
        )
        
        if stream:
            return self._stream_openai_response(response)
        else:
            return response.choices[0].message.content
    
    async def _execute_anthropic(
        self, client, model_config, messages, temperature, max_tokens, stream
    ):
        """Anthropic 실행"""
        # Anthropic 메시지 형식 변환
        system_message = ""
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append(msg)
        
        response = await client.messages.create(
            model=model_config.model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message,
            messages=user_messages,
            stream=stream
        )
        
        if stream:
            return self._stream_anthropic_response(response)
        else:
            return response.content[0].text
    
    async def _execute_groq(
        self, client, model_config, messages, temperature, max_tokens, stream
    ):
        """Groq 실행"""
        response = await client.chat.completions.create(
            model=model_config.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream
        )
        
        if stream:
            return self._stream_openai_response(response)
        else:
            return response.choices[0].message.content
    
    async def _stream_openai_response(self, response) -> AsyncGenerator[str, None]:
        """OpenAI 스타일 스트림 응답 처리"""
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def _stream_anthropic_response(self, response) -> AsyncGenerator[str, None]:
        """Anthropic 스트림 응답 처리"""
        async for chunk in response:
            if chunk.type == "content_block_delta":
                yield chunk.delta.text
    
    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """토큰 수 추정 (간단한 휴리스틱)"""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        # 대략적인 추정: 4글자 ≈ 1토큰
        return total_chars // 4
    
    def validate_messages(self, messages: List[Dict[str, str]]) -> bool:
        """메시지 형식 검증"""
        if not messages:
            return False
        
        for msg in messages:
            if not isinstance(msg, dict):
                return False
            if "role" not in msg or "content" not in msg:
                return False
            if msg["role"] not in ["system", "user", "assistant"]:
                return False
        
        return True
    
    def prepare_vision_messages(
        self, 
        messages: List[Dict[str, Any]], 
        model_config: ModelConfig
    ) -> List[Dict[str, Any]]:
        """비전 모델용 메시지 준비"""
        if not model_config.supports_vision:
            # 이미지 내용 제거
            cleaned_messages = []
            for msg in messages:
                if isinstance(msg.get("content"), list):
                    text_content = [
                        item for item in msg["content"]
                        if item.get("type") == "text"
                    ]
                    if text_content:
                        cleaned_messages.append({
                            "role": msg["role"],
                            "content": text_content[0]["text"]
                        })
                else:
                    cleaned_messages.append(msg)
            return cleaned_messages
        
        return messages
    
    async def test_model_health(self, model_config: ModelConfig) -> bool:
        """모델 헬스 체크"""
        test_messages = [{"role": "user", "content": "Hello, are you working?"}]
        
        try:
            result = await self.execute_chat_completion(
                model_config, test_messages, 0.1, 10, False
            )
            return bool(result and len(str(result).strip()) > 0)
        except Exception as e:
            logger.error(f"Health check failed for {model_config.model_name}: {e}")
            return False