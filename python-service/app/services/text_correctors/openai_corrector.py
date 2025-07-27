"""
OpenAI 기반 텍스트 교정기
TransformerOCRService에서 분리된 OpenAI 전용 교정 로직
Single Responsibility Principle 적용
"""

import logging
import json
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import os
import re

from app.core.ocr_interfaces import (
    BaseTextCorrector, CorrectionContext, CorrectionResult,
    TextCorrection, CorrectionMethod, LanguageCode, DocumentType
)

logger = logging.getLogger(__name__)


class OpenAITextCorrector(BaseTextCorrector):
    """OpenAI GPT 기반 텍스트 교정기"""
    
    def __init__(self, metrics_collector=None):
        super().__init__(metrics_collector)
        
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.base_url = "https://api.openai.com/v1/chat/completions"
        
        # 문서 타입별 시스템 프롬프트
        self.system_prompts = {
            DocumentType.FINANCIAL_STATEMENT: """
            당신은 재무제표 OCR 텍스트 교정 전문가입니다.
            다음 규칙에 따라 텍스트를 교정해주세요:
            1. 재무 용어의 정확한 표기 (매출액, 순이익, 자산총계 등)
            2. 숫자와 단위의 정확한 분리 (1,000원 → 1,000 원)
            3. 통화 표기의 통일 (원, KRW, USD 등)
            4. 회계 항목명의 표준화
            """,
            DocumentType.INVOICE: """
            당신은 송장/청구서 OCR 텍스트 교정 전문가입니다.
            다음 규칙에 따라 텍스트를 교정해주세요:
            1. 날짜 형식 통일 (YYYY-MM-DD)
            2. 금액 표기의 정확성
            3. 상품명 및 수량의 명확한 분리
            4. 세금 관련 용어 정확성
            """,
            DocumentType.CONTRACT: """
            당신은 계약서 OCR 텍스트 교정 전문가입니다.
            다음 규칙에 따라 텍스트를 교정해주세요:
            1. 법률 용어의 정확성
            2. 날짜 및 기간 표기의 명확성
            3. 당사자 정보의 정확성
            4. 조항 번호 및 구조의 일관성
            """
        }
        
        # 언어별 기본 프롬프트
        self.language_prompts = {
            LanguageCode.KOREAN: "한국어 텍스트를 교정해주세요.",
            LanguageCode.ENGLISH: "Please correct the English text.",
            LanguageCode.CHINESE_SIMPLIFIED: "请纠正简体中文文本。",
            LanguageCode.JAPANESE: "日本語のテキストを校正してください。"
        }
        
        # 세션 관리
        self.session = None
    
    async def _correct_text_impl(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """OpenAI 기반 텍스트 교정 구현"""
        if not self.api_key:
            logger.warning("OpenAI API key not available")
            return CorrectionResult(
                corrected_text=text,
                corrections=[],
                overall_confidence=0.0,
                method_used=CorrectionMethod.OPENAI_GPT,
                processing_time=0.0
            )
        
        try:
            # 1. 시스템 프롬프트 구성
            system_prompt = self._build_system_prompt(context)
            
            # 2. 사용자 프롬프트 구성
            user_prompt = self._build_user_prompt(text, context)
            
            # 3. OpenAI API 호출
            response = await self._call_openai_api(system_prompt, user_prompt)
            
            # 4. 응답 파싱
            corrected_text, corrections = self._parse_openai_response(response, text)
            
            # 5. 신뢰도 계산
            confidence = self._calculate_confidence(text, corrected_text, corrections)
            
            return CorrectionResult(
                corrected_text=corrected_text,
                corrections=corrections,
                overall_confidence=confidence,
                method_used=CorrectionMethod.OPENAI_GPT,
                processing_time=0.0  # 상위 클래스에서 설정
            )
            
        except Exception as e:
            logger.error(f"OpenAI correction failed: {e}")
            return CorrectionResult(
                corrected_text=text,
                corrections=[],
                overall_confidence=0.0,
                method_used=CorrectionMethod.OPENAI_GPT,
                processing_time=0.0
            )
    
    def _build_system_prompt(self, context: CorrectionContext) -> str:
        """시스템 프롬프트 구성"""
        # 문서 타입별 프롬프트
        base_prompt = self.system_prompts.get(
            context.document_type,
            "당신은 OCR 텍스트 교정 전문가입니다."
        )
        
        # 언어별 추가 지시사항
        language_instruction = self.language_prompts.get(
            context.language,
            "텍스트를 교정해주세요."
        )
        
        # 컨텍스트 기반 추가 지시사항
        additional_instructions = []
        
        if context.financial_context:
            additional_instructions.append("재무/회계 용어의 정확성에 특별히 주의하세요.")
        
        if context.custom_vocabulary:
            vocab_list = ", ".join(context.custom_vocabulary[:10])  # 최대 10개
            additional_instructions.append(f"다음 용어들을 우선적으로 고려하세요: {vocab_list}")
        
        # 출력 형식 지시
        format_instruction = """
        응답 형식을 JSON으로 해주세요:
        {
            "corrected_text": "교정된 전체 텍스트",
            "corrections": [
                {
                    "original": "원본 텍스트",
                    "corrected": "교정된 텍스트", 
                    "reason": "교정 이유",
                    "confidence": 0.95
                }
            ]
        }
        """
        
        return "\n".join([
            base_prompt,
            language_instruction,
            *additional_instructions,
            format_instruction
        ])
    
    def _build_user_prompt(self, text: str, context: CorrectionContext) -> str:
        """사용자 프롬프트 구성"""
        prompt_parts = []
        
        # 기본 텍스트
        prompt_parts.append(f"교정할 텍스트:\n{text}")
        
        # 주변 컨텍스트 (있는 경우)
        if context.surrounding_text and context.surrounding_text != text:
            prompt_parts.append(f"주변 컨텍스트:\n{context.surrounding_text[:200]}...")
        
        # 추가 지시사항
        prompt_parts.append("다음 사항에 특별히 주의하여 교정해주세요:")
        prompt_parts.append("1. OCR에서 잘못 인식된 문자들")
        prompt_parts.append("2. 숫자와 문자의 혼동")
        prompt_parts.append("3. 전문 용어의 정확한 표기")
        prompt_parts.append("4. 문법 및 맞춤법")
        
        return "\n".join(prompt_parts)
    
    async def _call_openai_api(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """OpenAI API 호출"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o-mini",  # 비용 효율적인 모델 사용
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 2000,
            "temperature": 0.1,  # 일관성을 위해 낮은 temperature
            "response_format": {"type": "json_object"}  # JSON 응답 강제
        }
        
        async with self.session.post(self.base_url, headers=headers, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                return result
            else:
                error_text = await response.text()
                raise Exception(f"OpenAI API error {response.status}: {error_text}")
    
    def _parse_openai_response(self, response: Dict[str, Any], original_text: str) -> tuple[str, List[TextCorrection]]:
        """OpenAI 응답 파싱"""
        try:
            content = response["choices"][0]["message"]["content"]
            parsed_response = json.loads(content)
            
            corrected_text = parsed_response.get("corrected_text", original_text)
            corrections_data = parsed_response.get("corrections", [])
            
            corrections = []
            for correction_data in corrections_data:
                correction = TextCorrection(
                    original=correction_data.get("original", ""),
                    corrected=correction_data.get("corrected", ""),
                    confidence=correction_data.get("confidence", 0.8),
                    method=CorrectionMethod.OPENAI_GPT,
                    reason=correction_data.get("reason", "OpenAI correction")
                )
                corrections.append(correction)
            
            return corrected_text, corrections
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            # fallback: 원본 텍스트 반환
            return original_text, []
    
    def _calculate_confidence(self, original: str, corrected: str, 
                           corrections: List[TextCorrection]) -> float:
        """교정 신뢰도 계산"""
        if original == corrected:
            return 1.0  # 변경사항 없음
        
        if not corrections:
            return 0.5  # 교정 정보 없음
        
        # 개별 교정의 평균 신뢰도
        avg_correction_confidence = sum(c.confidence for c in corrections) / len(corrections)
        
        # 텍스트 유사도 기반 신뢰도 조정
        similarity = self._calculate_text_similarity(original, corrected)
        
        # 최종 신뢰도: 교정 신뢰도 + 유사도 가중치
        final_confidence = avg_correction_confidence * 0.7 + similarity * 0.3
        
        return min(final_confidence, 1.0)
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """텍스트 유사도 계산 (간단한 방식)"""
        if not text1 or not text2:
            return 0.0
        
        # 단어 기반 유사도
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def supports_language(self, language: LanguageCode) -> bool:
        """언어 지원 여부 확인"""
        # OpenAI는 대부분의 언어를 지원
        return language in [
            LanguageCode.KOREAN, LanguageCode.ENGLISH, 
            LanguageCode.CHINESE_SIMPLIFIED, LanguageCode.CHINESE_TRADITIONAL,
            LanguageCode.JAPANESE, LanguageCode.SPANISH, LanguageCode.PORTUGUESE,
            LanguageCode.FRENCH, LanguageCode.GERMAN, LanguageCode.ITALIAN,
            LanguageCode.ARABIC, LanguageCode.AUTO_DETECT
        ]
    
    def get_correction_method(self) -> CorrectionMethod:
        """교정 방법 반환"""
        return CorrectionMethod.OPENAI_GPT
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
            self.session = None


class OpenAIStreamingCorrector(OpenAITextCorrector):
    """스트리밍 방식의 OpenAI 교정기"""
    
    async def _call_openai_api(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """스트리밍 방식으로 OpenAI API 호출"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 2000,
            "temperature": 0.1,
            "stream": True  # 스트리밍 활성화
        }
        
        full_content = ""
        
        async with self.session.post(self.base_url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"OpenAI API error {response.status}: {error_text}")
            
            async for line in response.content:
                line = line.decode('utf-8').strip()
                
                if line.startswith('data: '):
                    data = line[6:]  # 'data: ' 제거
                    
                    if data == '[DONE]':
                        break
                    
                    try:
                        chunk = json.loads(data)
                        if 'choices' in chunk and chunk['choices']:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                full_content += delta['content']
                    except json.JSONDecodeError:
                        continue
        
        # 스트리밍 결과를 일반 응답 형식으로 변환
        return {
            "choices": [{
                "message": {
                    "content": full_content
                }
            }]
        }