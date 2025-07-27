#!/usr/bin/env python3
"""
트랜스포머 기반 OCR 서비스
Transformer-based OCR Service

BERT/GPT 기반 문맥 이해를 통한 OCR 정확도 향상 시스템
"""

import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import cv2
from datetime import datetime
import asyncio
import aiohttp
import os

# Transformer 모델 관련 (로컬에서 사용 가능한 경우)
try:
    from transformers import (
        AutoTokenizer, AutoModelForMaskedLM, AutoModel,
        pipeline, BertTokenizer, BertForMaskedLM
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

from app.services.multilingual_two_tier_service import MultilingualTwoTierService

logger = logging.getLogger(__name__)


@dataclass
class ContextualPrediction:
    """문맥 기반 예측 결과"""
    original_text: str
    corrected_text: str
    confidence: float
    corrections: List[Dict[str, Any]]
    context_used: str
    model_used: str


@dataclass
class DocumentStructure:
    """문서 구조 정보"""
    text_blocks: List[Dict[str, Any]]
    financial_terms: List[str]
    numbers: List[str]
    dates: List[str]
    currencies: List[str]
    structure_type: str  # "table", "paragraph", "list", etc.


class TransformerOCRService:
    """트랜스포머 기반 OCR 서비스"""
    
    def __init__(self):
        """초기화"""
        self.base_ocr = MultilingualTwoTierService()
        self.model_cache = {}
        self.financial_vocab = self._load_financial_vocabulary()
        
        # 모델 설정
        self.model_configs = {
            "bert_base": {
                "model_name": "bert-base-multilingual-cased",
                "languages": ["ko", "en", "zh", "ja", "ar"],
                "max_length": 512
            },
            "financial_bert": {
                # 실제 환경에서는 금융 특화 BERT 모델 사용
                "model_name": "bert-base-multilingual-cased",
                "languages": ["ko", "en"],
                "max_length": 512,
                "specialization": "financial"
            }
        }
        
        # OpenAI API 설정 (환경변수에서 로드)
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.use_openai = bool(self.openai_api_key)
        
        logger.info(f"TransformerOCRService 초기화 완료")
        logger.info(f"Transformers 라이브러리: {'사용 가능' if TRANSFORMERS_AVAILABLE else '사용 불가'}")
        logger.info(f"OpenAI API: {'사용 가능' if self.use_openai else '사용 불가'}")
    
    def _load_financial_vocabulary(self) -> Dict[str, List[str]]:
        """금융 전문 용어 사전 로드"""
        return {
            "korean": [
                "매출액", "영업이익", "당기순이익", "자산", "부채", "자본", "현금흐름",
                "투자", "배당", "주식", "채권", "이자", "환율", "인플레이션", "GDP",
                "재무제표", "손익계산서", "대차대조표", "현금흐름표", "주주지분",
                "유동자산", "고정자산", "유동부채", "장기부채", "자기자본", "이익잉여금"
            ],
            "english": [
                "revenue", "operating income", "net income", "assets", "liabilities", "equity",
                "cash flow", "investment", "dividend", "stock", "bond", "interest", "exchange rate",
                "inflation", "GDP", "financial statement", "income statement", "balance sheet",
                "cash flow statement", "shareholders equity", "current assets", "fixed assets",
                "current liabilities", "long-term debt", "retained earnings"
            ],
            "chinese": [
                "营业收入", "营业利润", "净利润", "资产", "负债", "权益", "现金流",
                "投资", "股息", "股票", "债券", "利息", "汇率", "通胀", "GDP",
                "财务报表", "损益表", "资产负债表", "现金流量表"
            ],
            "numbers": [
                r"\d+\.?\d*", r"\d{1,3}(,\d{3})*", r"\$\d+", r"¥\d+", r"€\d+", r"₩\d+"
            ]
        }
    
    async def process_with_context(
        self,
        image_path: str,
        language: str = "kor",
        use_context: bool = True,
        model_preference: str = "auto"
    ) -> ContextualPrediction:
        """
        문맥을 활용한 OCR 처리
        
        Args:
            image_path: 이미지 파일 경로
            language: 언어 코드
            use_context: 문맥 활용 여부
            model_preference: 모델 선택 (auto, bert, openai)
            
        Returns:
            문맥 기반 예측 결과
        """
        try:
            # 1. 기본 OCR 수행
            logger.info(f"기본 OCR 처리 시작: {image_path}")
            base_result = self.base_ocr.process_image(image_path, language)
            original_text = base_result.get("extracted_text", "")
            
            if not original_text.strip():
                return ContextualPrediction(
                    original_text="",
                    corrected_text="",
                    confidence=0.0,
                    corrections=[],
                    context_used="",
                    model_used="none"
                )
            
            logger.info(f"기본 OCR 결과: {len(original_text)}자 추출")
            
            # 2. 문서 구조 분석
            document_structure = self._analyze_document_structure(original_text, image_path)
            
            # 3. 문맥 기반 교정
            if use_context:
                corrected_result = await self._apply_contextual_correction(
                    original_text, 
                    document_structure, 
                    language, 
                    model_preference
                )
                return corrected_result
            else:
                return ContextualPrediction(
                    original_text=original_text,
                    corrected_text=original_text,
                    confidence=base_result.get("confidence", 0.0),
                    corrections=[],
                    context_used="none",
                    model_used="base_ocr"
                )
                
        except Exception as e:
            logger.error(f"문맥 OCR 처리 실패: {e}")
            return ContextualPrediction(
                original_text="",
                corrected_text="",
                confidence=0.0,
                corrections=[{"error": str(e)}],
                context_used="",
                model_used="error"
            )
    
    def _analyze_document_structure(self, text: str, image_path: str) -> DocumentStructure:
        """문서 구조 분석"""
        try:
            # 텍스트 블록 분리
            text_blocks = []
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
                if line.strip():
                    text_blocks.append({
                        "line_number": i,
                        "text": line.strip(),
                        "length": len(line.strip()),
                        "has_numbers": bool(re.search(r'\d', line)),
                        "has_currency": bool(re.search(r'[¥$€₩]', line)),
                        "is_header": self._is_likely_header(line)
                    })
            
            # 금융 용어 추출
            financial_terms = self._extract_financial_terms(text)
            
            # 숫자 추출
            numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', text)
            
            # 날짜 추출
            dates = re.findall(r'\d{4}[-년./]\d{1,2}[-월./]\d{1,2}[일]?', text)
            dates.extend(re.findall(r'\d{1,2}[-./]\d{1,2}[-./]\d{2,4}', text))
            
            # 통화 추출
            currencies = re.findall(r'[¥$€₩]\s*\d+(?:,\d{3})*(?:\.\d+)?', text)
            
            # 구조 타입 추정
            structure_type = self._determine_structure_type(text_blocks, image_path)
            
            return DocumentStructure(
                text_blocks=text_blocks,
                financial_terms=financial_terms,
                numbers=numbers,
                dates=dates,
                currencies=currencies,
                structure_type=structure_type
            )
            
        except Exception as e:
            logger.error(f"문서 구조 분석 실패: {e}")
            return DocumentStructure([], [], [], [], [], "unknown")
    
    def _is_likely_header(self, text: str) -> bool:
        """헤더 텍스트 판별"""
        text = text.strip()
        if len(text) < 3:
            return False
        
        # 헤더 패턴들
        header_patterns = [
            r'^제?\s*\d+\s*[장절]',  # 제1장, 1절 등
            r'^[A-Z\s]+$',  # 대문자만
            r'^\d+\.\s+',  # 1. 형태
            r'^[가-힣\s]+\s*(?:현황|분석|보고서|제표)$',  # ~현황, ~분석 등
        ]
        
        return any(re.match(pattern, text) for pattern in header_patterns)
    
    def _extract_financial_terms(self, text: str) -> List[str]:
        """금융 용어 추출"""
        found_terms = []
        
        for lang, terms in self.financial_vocab.items():
            if lang == "numbers":
                continue
            
            for term in terms:
                if term in text:
                    found_terms.append(term)
        
        return list(set(found_terms))
    
    def _determine_structure_type(self, text_blocks: List[Dict], image_path: str) -> str:
        """문서 구조 타입 결정"""
        try:
            # 이미지 기반 분석 (간단한 휴리스틱)
            image = cv2.imread(image_path)
            if image is None:
                return "text"
            
            height, width = image.shape[:2]
            aspect_ratio = width / height
            
            # 텍스트 기반 분석
            has_many_numbers = sum(1 for block in text_blocks if block["has_numbers"]) > len(text_blocks) * 0.5
            has_currency = any(block["has_currency"] for block in text_blocks)
            avg_line_length = np.mean([block["length"] for block in text_blocks]) if text_blocks else 0
            
            # 판별 로직
            if has_many_numbers and has_currency:
                return "financial_table"
            elif aspect_ratio > 1.5 and has_many_numbers:
                return "chart_or_graph"
            elif avg_line_length < 30:
                return "list_or_table"
            else:
                return "paragraph"
                
        except Exception as e:
            logger.warning(f"구조 타입 결정 실패: {e}")
            return "unknown"
    
    async def _apply_contextual_correction(
        self, 
        text: str, 
        structure: DocumentStructure, 
        language: str, 
        model_preference: str
    ) -> ContextualPrediction:
        """문맥 기반 교정 적용"""
        try:
            corrections = []
            
            # 모델 선택
            if model_preference == "auto":
                if self.use_openai and len(text) < 3000:
                    model_used = "openai"
                elif TRANSFORMERS_AVAILABLE:
                    model_used = "bert"
                else:
                    model_used = "rule_based"
            else:
                model_used = model_preference
            
            # 선택된 모델로 교정
            if model_used == "openai":
                corrected_text, corrections = await self._correct_with_openai(text, structure, language)
            elif model_used == "bert" and TRANSFORMERS_AVAILABLE:
                corrected_text, corrections = await self._correct_with_bert(text, structure, language)
            else:
                corrected_text, corrections = self._correct_with_rules(text, structure, language)
            
            # 신뢰도 계산
            confidence = self._calculate_correction_confidence(text, corrected_text, corrections)
            
            return ContextualPrediction(
                original_text=text,
                corrected_text=corrected_text,
                confidence=confidence,
                corrections=corrections,
                context_used=structure.structure_type,
                model_used=model_used
            )
            
        except Exception as e:
            logger.error(f"문맥 교정 실패: {e}")
            return ContextualPrediction(
                original_text=text,
                corrected_text=text,
                confidence=0.5,
                corrections=[{"error": str(e)}],
                context_used="error",
                model_used="error"
            )
    
    async def _correct_with_openai(
        self, 
        text: str, 
        structure: DocumentStructure, 
        language: str
    ) -> Tuple[str, List[Dict]]:
        """OpenAI를 사용한 문맥 교정"""
        if not self.use_openai:
            return text, [{"error": "OpenAI API 키가 설정되지 않음"}]
        
        try:
            # 문맥 정보 구성
            context_info = {
                "document_type": structure.structure_type,
                "financial_terms": structure.financial_terms[:10],  # 최대 10개
                "has_numbers": len(structure.numbers) > 0,
                "has_currencies": len(structure.currencies) > 0
            }
            
            # 프롬프트 구성
            system_prompt = self._build_openai_system_prompt(language, context_info)
            user_prompt = f"다음 OCR 텍스트를 교정해주세요:\n\n{text}"
            
            # OpenAI API 호출
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.1
                }
                
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        corrected_text = result["choices"][0]["message"]["content"].strip()
                        
                        corrections = [{
                            "type": "openai_correction",
                            "original_length": len(text),
                            "corrected_length": len(corrected_text),
                            "model": "gpt-3.5-turbo"
                        }]
                        
                        return corrected_text, corrections
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI API 오류 ({response.status}): {error_text}")
                        return text, [{"error": f"OpenAI API 오류: {response.status}"}]
        
        except Exception as e:
            logger.error(f"OpenAI 교정 실패: {e}")
            return text, [{"error": str(e)}]
    
    def _build_openai_system_prompt(self, language: str, context_info: Dict) -> str:
        """OpenAI 시스템 프롬프트 구성"""
        language_names = {
            "kor": "한국어",
            "eng": "영어",
            "chi_sim": "중국어(간체)",
            "jpn": "일본어"
        }
        
        lang_name = language_names.get(language, "한국어")
        
        prompt = f"""당신은 {lang_name} OCR 텍스트 교정 전문가입니다.

문서 정보:
- 문서 타입: {context_info['document_type']}
- 숫자 포함: {'예' if context_info['has_numbers'] else '아니오'}
- 통화 포함: {'예' if context_info['has_currencies'] else '아니오'}
- 금융 용어: {', '.join(context_info['financial_terms'][:5]) if context_info['financial_terms'] else '없음'}

교정 규칙:
1. OCR로 인한 오탈자를 수정하세요
2. 금융 용어의 정확한 표기를 유지하세요
3. 숫자와 통화 기호를 정확히 유지하세요
4. 문맥에 맞는 적절한 단어로 교정하세요
5. 원본의 구조와 형식을 최대한 유지하세요

교정된 텍스트만 반환하고, 추가 설명은 하지 마세요."""

        return prompt
    
    async def _correct_with_bert(
        self, 
        text: str, 
        structure: DocumentStructure, 
        language: str
    ) -> Tuple[str, List[Dict]]:
        """BERT를 사용한 문맥 교정"""
        if not TRANSFORMERS_AVAILABLE:
            return text, [{"error": "Transformers 라이브러리 사용 불가"}]
        
        try:
            # BERT 모델 로드 (캐시 활용)
            model_key = f"bert_{language}"
            if model_key not in self.model_cache:
                tokenizer = AutoTokenizer.from_pretrained("bert-base-multilingual-cased")
                model = AutoModelForMaskedLM.from_pretrained("bert-base-multilingual-cased")
                self.model_cache[model_key] = {"tokenizer": tokenizer, "model": model}
                logger.info(f"BERT 모델 로드 완료: {model_key}")
            
            tokenizer = self.model_cache[model_key]["tokenizer"]
            model = self.model_cache[model_key]["model"]
            
            # 마스크 기반 교정 수행
            corrections = []
            corrected_text = text
            
            # 의심스러운 단어들 찾기
            suspicious_words = self._find_suspicious_words(text, structure)
            
            for word_info in suspicious_words:
                original_word = word_info["word"]
                context = word_info["context"]
                
                # BERT로 예측
                predicted_word = self._predict_with_bert(
                    context, original_word, tokenizer, model
                )
                
                if predicted_word and predicted_word != original_word:
                    corrected_text = corrected_text.replace(original_word, predicted_word, 1)
                    corrections.append({
                        "type": "bert_correction",
                        "original": original_word,
                        "corrected": predicted_word,
                        "context": context[:50] + "..." if len(context) > 50 else context
                    })
            
            return corrected_text, corrections
            
        except Exception as e:
            logger.error(f"BERT 교정 실패: {e}")
            return text, [{"error": str(e)}]
    
    def _find_suspicious_words(self, text: str, structure: DocumentStructure) -> List[Dict]:
        """의심스러운 단어들 찾기"""
        suspicious = []
        
        # 간단한 휴리스틱으로 의심스러운 단어 판별
        words = re.findall(r'\b\w+\b', text)
        
        for i, word in enumerate(words):
            # 단일 문자이거나 매우 짧은 단어
            if len(word) == 1 and word.isalpha():
                context_start = max(0, i-3)
                context_end = min(len(words), i+4)
                context = ' '.join(words[context_start:context_end])
                
                suspicious.append({
                    "word": word,
                    "position": i,
                    "context": context,
                    "reason": "single_character"
                })
        
        return suspicious[:10]  # 최대 10개만 처리
    
    def _predict_with_bert(self, context: str, target_word: str, tokenizer, model) -> Optional[str]:
        """BERT로 단어 예측"""
        try:
            # 문맥에서 대상 단어를 [MASK]로 교체
            masked_context = context.replace(target_word, "[MASK]", 1)
            
            # 토크나이제이션
            inputs = tokenizer(masked_context, return_tensors="pt", max_length=128, truncation=True)
            
            # 예측
            with torch.no_grad():
                outputs = model(**inputs)
                predictions = outputs.logits
            
            # 마스크 위치 찾기
            mask_token_id = tokenizer.mask_token_id
            mask_positions = (inputs["input_ids"] == mask_token_id).nonzero(as_tuple=True)[1]
            
            if len(mask_positions) == 0:
                return None
            
            # 예측 결과 가져오기
            mask_pos = mask_positions[0]
            predicted_token_id = predictions[0, mask_pos].argmax().item()
            predicted_word = tokenizer.decode([predicted_token_id]).strip()
            
            # 특수 토큰이나 너무 다른 단어는 제외
            if predicted_word.startswith('[') or len(predicted_word) > len(target_word) * 3:
                return None
            
            return predicted_word
            
        except Exception as e:
            logger.warning(f"BERT 예측 실패: {e}")
            return None
    
    def _correct_with_rules(
        self, 
        text: str, 
        structure: DocumentStructure, 
        language: str
    ) -> Tuple[str, List[Dict]]:
        """규칙 기반 교정"""
        corrections = []
        corrected_text = text
        
        # 일반적인 OCR 오류 패턴들
        ocr_patterns = {
            # 한국어 패턴
            "kor": [
                (r'0(?=\d)', 'O'),  # 숫자 0을 문자 O로 잘못 인식
                (r'(?<=\d)O(?=\d)', '0'),  # 문자 O를 숫자 0으로 교정
                (r'(?<=\d)l(?=\d)', '1'),  # 소문자 l을 숫자 1로 교정
                (r'\b1l\b', '11'),  # 11을 1l로 잘못 인식
                (r'\bO(?=\d)', '0'),  # 앞에 오는 O를 0으로
            ],
            # 숫자 관련 공통 패턴
            "numbers": [
                (r'(\d),(\d{3})', r'\1,\2'),  # 천 단위 구분 콤마 유지
                (r'(\d)\.(\d{1,2})\b', r'\1.\2'),  # 소수점 유지
                (r'([¥$€₩])\s+(\d)', r'\1\2'),  # 통화 기호와 숫자 사이 공백 제거
            ]
        }
        
        # 선택된 언어의 패턴 적용
        patterns_to_apply = ocr_patterns.get(language, [])
        patterns_to_apply.extend(ocr_patterns["numbers"])
        
        for pattern, replacement in patterns_to_apply:
            matches = list(re.finditer(pattern, corrected_text))
            for match in reversed(matches):  # 뒤에서부터 교체
                original = match.group(0)
                new_text = re.sub(pattern, replacement, corrected_text)
                if new_text != corrected_text:
                    corrections.append({
                        "type": "rule_based",
                        "pattern": pattern,
                        "original": original,
                        "corrected": re.sub(pattern, replacement, original),
                        "position": match.start()
                    })
                    corrected_text = new_text
        
        # 금융 용어 교정
        for term in structure.financial_terms:
            # 일반적인 OCR 오류가 있는 금융 용어들 교정
            variations = self._generate_term_variations(term)
            for variation in variations:
                if variation in corrected_text and variation != term:
                    corrected_text = corrected_text.replace(variation, term)
                    corrections.append({
                        "type": "financial_term_correction",
                        "original": variation,
                        "corrected": term
                    })
        
        return corrected_text, corrections
    
    def _generate_term_variations(self, term: str) -> List[str]:
        """용어의 일반적인 OCR 오류 변형들 생성"""
        variations = []
        
        # 간단한 문자 치환
        replacements = {
            '0': 'O', 'O': '0', '1': 'l', 'l': '1', 'I': '1',
            '6': 'G', 'G': '6', '5': 'S', 'S': '5'
        }
        
        for original, replacement in replacements.items():
            if original in term:
                variations.append(term.replace(original, replacement))
        
        return variations
    
    def _calculate_correction_confidence(
        self, 
        original: str, 
        corrected: str, 
        corrections: List[Dict]
    ) -> float:
        """교정 신뢰도 계산"""
        if not corrections:
            return 1.0
        
        # 기본 신뢰도
        base_confidence = 0.8
        
        # 교정 개수에 따른 조정
        correction_count = len(corrections)
        confidence_penalty = min(correction_count * 0.1, 0.3)
        
        # 텍스트 길이 대비 교정 비율
        text_length = len(original)
        correction_ratio = correction_count / max(text_length, 1)
        
        if correction_ratio > 0.1:  # 10% 이상 교정된 경우
            confidence_penalty += 0.2
        
        return max(base_confidence - confidence_penalty, 0.1)
    
    def get_model_info(self) -> Dict[str, Any]:
        """사용 가능한 모델 정보 반환"""
        return {
            "transformers_available": TRANSFORMERS_AVAILABLE,
            "openai_available": self.use_openai,
            "supported_models": list(self.model_configs.keys()),
            "cached_models": list(self.model_cache.keys()),
            "financial_vocab_languages": list(self.financial_vocab.keys())
        }


# 전역 인스턴스
transformer_ocr_service = TransformerOCRService()