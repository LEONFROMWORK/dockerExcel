"""
BERT 기반 텍스트 교정기
TransformerOCRService에서 분리된 BERT 전용 교정 로직
Single Responsibility Principle 적용
"""

import logging
from typing import List, Dict, Any, Optional
import re
import asyncio

from app.core.ocr_interfaces import (
    BaseTextCorrector, CorrectionContext, CorrectionResult, 
    TextCorrection, CorrectionMethod, LanguageCode
)

logger = logging.getLogger(__name__)

# BERT 모델 관련 imports (선택적)
try:
    from transformers import (
        AutoTokenizer, BertTokenizer, BertForMaskedLM,
        pipeline, AutoModel, AutoModelForMaskedLM
    )
    TRANSFORMERS_AVAILABLE = True
    logger.info("BERT transformers available")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("BERT transformers not available")


class BERTTextCorrector(BaseTextCorrector):
    """BERT 모델 기반 텍스트 교정기"""
    
    def __init__(self, metrics_collector=None):
        super().__init__(metrics_collector)
        
        self.model_cache = {}
        self.tokenizer_cache = {}
        
        # 언어별 BERT 모델 설정
        self.model_configs = {
            LanguageCode.KOREAN: {
                'model_name': 'klue/bert-base',
                'tokenizer_name': 'klue/bert-base',
                'enabled': True
            },
            LanguageCode.ENGLISH: {
                'model_name': 'bert-base-uncased',
                'tokenizer_name': 'bert-base-uncased', 
                'enabled': True
            },
            LanguageCode.CHINESE_SIMPLIFIED: {
                'model_name': 'bert-base-chinese',
                'tokenizer_name': 'bert-base-chinese',
                'enabled': True
            },
            LanguageCode.JAPANESE: {
                'model_name': 'cl-tohoku/bert-base-japanese',
                'tokenizer_name': 'cl-tohoku/bert-base-japanese',
                'enabled': True
            }
        }
        
        # 재무 용어 패턴 정의
        self.financial_patterns = {
            LanguageCode.KOREAN: [
                (r'매출액|매출', '매출액'),
                (r'순이익|순익', '순이익'),
                (r'자산총계|총자산', '자산총계'),
                (r'부채총계|총부채', '부채총계'),
                (r'자본총계|총자본', '자본총계'),
                (r'영업이익', '영업이익'),
                (r'당기순이익', '당기순이익')
            ],
            LanguageCode.ENGLISH: [
                (r'revenue|sales', 'Revenue'),
                (r'net income|profit', 'Net Income'),
                (r'total assets', 'Total Assets'),
                (r'total liabilities', 'Total Liabilities'),
                (r'shareholders equity', 'Shareholders Equity')
            ]
        }
    
    async def _correct_text_impl(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """BERT 기반 텍스트 교정 구현"""
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("BERT transformers not available, returning original text")
            return CorrectionResult(
                corrected_text=text,
                corrections=[],
                overall_confidence=1.0,
                method_used=CorrectionMethod.BERT_BASED,
                processing_time=0.0
            )
        
        try:
            corrections = []
            corrected_text = text
            
            # 1. 의심스러운 단어 찾기
            suspicious_words = self._find_suspicious_words(text, context)
            
            # 2. BERT 모델로 각 의심스러운 단어 교정
            for word_info in suspicious_words:
                correction = await self._correct_word_with_bert(word_info, context)
                if correction:
                    corrections.append(correction)
                    corrected_text = corrected_text.replace(
                        correction.original, correction.corrected
                    )
            
            # 3. 재무 용어 패턴 교정
            pattern_corrections = self._apply_financial_patterns(corrected_text, context.language)
            corrections.extend(pattern_corrections)
            
            for correction in pattern_corrections:
                corrected_text = corrected_text.replace(
                    correction.original, correction.corrected
                )
            
            # 4. 전체 신뢰도 계산
            overall_confidence = self._calculate_overall_confidence(corrections)
            
            return CorrectionResult(
                corrected_text=corrected_text,
                corrections=corrections,
                overall_confidence=overall_confidence,
                method_used=CorrectionMethod.BERT_BASED,
                processing_time=0.0  # 상위 클래스에서 설정
            )
            
        except Exception as e:
            logger.error(f"BERT correction failed: {e}")
            return CorrectionResult(
                corrected_text=text,
                corrections=[],
                overall_confidence=0.0,
                method_used=CorrectionMethod.BERT_BASED,
                processing_time=0.0
            )
    
    def _find_suspicious_words(self, text: str, context: CorrectionContext) -> List[Dict[str, Any]]:
        """의심스러운 단어들 찾기"""
        suspicious_words = []
        words = text.split()
        
        for i, word in enumerate(words):
            # 숫자와 문자가 섞인 경우
            if re.search(r'[0-9].*[a-zA-Z가-힣]|[a-zA-Z가-힣].*[0-9]', word):
                suspicious_words.append({
                    'word': word,
                    'position': i,
                    'context': ' '.join(words[max(0, i-3):i+4]),
                    'reason': 'mixed_alphanumeric'
                })
            
            # 너무 짧거나 너무 긴 단어
            elif len(word) == 1 and word.isalpha():
                suspicious_words.append({
                    'word': word,
                    'position': i,
                    'context': ' '.join(words[max(0, i-3):i+4]),
                    'reason': 'single_character'
                })
            
            # 특수문자가 포함된 단어
            elif re.search(r'[^\w\s가-힣]', word) and len(word) > 1:
                suspicious_words.append({
                    'word': word,
                    'position': i,
                    'context': ' '.join(words[max(0, i-3):i+4]),
                    'reason': 'special_characters'
                })
        
        return suspicious_words
    
    async def _correct_word_with_bert(self, word_info: Dict[str, Any], 
                                    context: CorrectionContext) -> Optional[TextCorrection]:
        """BERT 모델로 단어 교정"""
        try:
            if context.language not in self.model_configs:
                return None
            
            model_config = self.model_configs[context.language]
            if not model_config['enabled']:
                return None
            
            # 모델과 토크나이저 로드
            model, tokenizer = await self._get_model_and_tokenizer(context.language)
            if not model or not tokenizer:
                return None
            
            # 마스킹된 문장 생성
            masked_context = word_info['context'].replace(word_info['word'], '[MASK]')
            
            # BERT 예측 수행
            predicted_word = self._predict_with_bert(masked_context, tokenizer, model)
            
            if predicted_word and predicted_word != word_info['word']:
                # 신뢰도 계산 (간단한 휴리스틱)
                confidence = self._calculate_word_confidence(
                    word_info['word'], predicted_word, context
                )
                
                if confidence >= context.confidence_threshold:
                    return TextCorrection(
                        original=word_info['word'],
                        corrected=predicted_word,
                        confidence=confidence,
                        method=CorrectionMethod.BERT_BASED,
                        reason=f"BERT prediction: {word_info['reason']}",
                        position={'start': word_info['position'], 'end': word_info['position']}
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"BERT word correction failed: {e}")
            return None
    
    async def _get_model_and_tokenizer(self, language: LanguageCode):
        """모델과 토크나이저 로드 (캐시 사용)"""
        try:
            config = self.model_configs[language]
            model_name = config['model_name']
            
            # 캐시에서 확인
            if model_name in self.model_cache:
                return self.model_cache[model_name], self.tokenizer_cache[model_name]
            
            # 새로 로드
            tokenizer = AutoTokenizer.from_pretrained(config['tokenizer_name'])
            model = AutoModelForMaskedLM.from_pretrained(model_name)
            
            # 캐시에 저장
            self.model_cache[model_name] = model
            self.tokenizer_cache[model_name] = tokenizer
            
            logger.info(f"BERT model loaded: {model_name}")
            return model, tokenizer
            
        except Exception as e:
            logger.error(f"Failed to load BERT model for {language}: {e}")
            return None, None
    
    def _predict_with_bert(self, masked_text: str, tokenizer, model) -> Optional[str]:
        """BERT로 마스크된 단어 예측"""
        try:
            # 토큰화
            inputs = tokenizer(masked_text, return_tensors="pt", truncate=True, max_length=512)
            
            # 예측
            with torch.no_grad():
                outputs = model(**inputs)
                predictions = outputs.logits
            
            # 마스크 위치 찾기
            mask_token_index = torch.where(inputs.input_ids == tokenizer.mask_token_id)[1]
            
            if len(mask_token_index) == 0:
                return None
            
            # 가장 높은 확률의 토큰 선택
            mask_token_logits = predictions[0, mask_token_index, :]
            top_token = torch.argmax(mask_token_logits, dim=1)
            
            predicted_token = tokenizer.decode(top_token[0])
            
            # 특수 토큰 제거
            predicted_token = predicted_token.replace('[CLS]', '').replace('[SEP]', '').strip()
            
            return predicted_token if predicted_token else None
            
        except Exception as e:
            logger.error(f"BERT prediction failed: {e}")
            return None
    
    def _apply_financial_patterns(self, text: str, language: LanguageCode) -> List[TextCorrection]:
        """재무 용어 패턴 기반 교정"""
        corrections = []
        
        if language not in self.financial_patterns:
            return corrections
        
        patterns = self.financial_patterns[language]
        
        for pattern, replacement in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if match.group() != replacement:
                    corrections.append(TextCorrection(
                        original=match.group(),
                        corrected=replacement,
                        confidence=0.9,
                        method=CorrectionMethod.BERT_BASED,
                        reason="financial_term_pattern",
                        position={'start': match.start(), 'end': match.end()}
                    ))
        
        return corrections
    
    def _calculate_word_confidence(self, original: str, predicted: str, 
                                 context: CorrectionContext) -> float:
        """단어 교정 신뢰도 계산"""
        # 간단한 휴리스틱 기반 신뢰도
        confidence = 0.5
        
        # 길이 유사성
        len_ratio = min(len(original), len(predicted)) / max(len(original), len(predicted))
        confidence += len_ratio * 0.2
        
        # 첫 글자 일치
        if original and predicted and original[0].lower() == predicted[0].lower():
            confidence += 0.1
        
        # 재무 용어인 경우 신뢰도 증가
        if context.financial_context:
            financial_keywords = ['revenue', 'profit', 'asset', 'liability', 
                                '매출', '이익', '자산', '부채']
            if any(keyword in predicted.lower() for keyword in financial_keywords):
                confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _calculate_overall_confidence(self, corrections: List[TextCorrection]) -> float:
        """전체 교정 신뢰도 계산"""
        if not corrections:
            return 1.0
        
        # 개별 교정의 평균 신뢰도
        avg_confidence = sum(c.confidence for c in corrections) / len(corrections)
        
        # 교정 비율에 따른 가중치 (너무 많은 교정은 신뢰도 감소)
        correction_ratio = len(corrections) / 10  # 가정: 10개 단어당 1개 교정이 적정
        weight = max(0.1, 1.0 - correction_ratio * 0.1)
        
        return avg_confidence * weight
    
    def supports_language(self, language: LanguageCode) -> bool:
        """언어 지원 여부 확인"""
        return language in self.model_configs and TRANSFORMERS_AVAILABLE
    
    def get_correction_method(self) -> CorrectionMethod:
        """교정 방법 반환"""
        return CorrectionMethod.BERT_BASED


# torch import 처리
try:
    import torch
except ImportError:
    logger.warning("PyTorch not available for BERT correction")
    torch = None