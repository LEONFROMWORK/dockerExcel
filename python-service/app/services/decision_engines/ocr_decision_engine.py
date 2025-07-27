"""
OCR 단계 전환 판단 엔진
TwoTierOCRService에서 분리된 OCR 처리 단계 결정 로직
Single Responsibility Principle 적용
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingTier(Enum):
    """처리 계층"""
    TIER_1 = "tier1"  # 기본 OCR (Tesseract)
    TIER_2 = "tier2"  # 고급 OCR (PaddleOCR + PP-Structure)
    TIER_3 = "tier3"  # 최고급 OCR (OpenAI Vision)


class UpgradeReason(Enum):
    """업그레이드 이유"""
    LOW_CONFIDENCE = "low_confidence"
    LOW_KOREAN_ACCURACY = "low_korean_accuracy"
    HIGH_TABLE_COMPLEXITY = "high_table_complexity"
    HIGH_OVERALL_COMPLEXITY = "high_overall_complexity"
    SPECIAL_CONTENT_DETECTED = "special_content_detected"
    POOR_TEXT_QUALITY = "poor_text_quality"
    MIXED_LANGUAGE_DETECTED = "mixed_language_detected"
    FINANCIAL_CONTENT = "financial_content"


@dataclass
class DecisionThresholds:
    """판단 임계값"""
    confidence_threshold: float = 0.85
    korean_accuracy_threshold: float = 0.9
    table_complexity_threshold: float = 0.7
    overall_complexity_threshold: float = 0.6
    text_quality_threshold: float = 0.8
    special_content_threshold: float = 0.75


@dataclass
class UpgradeDecision:
    """업그레이드 판단 결과"""
    should_upgrade: bool
    target_tier: ProcessingTier
    reasons: List[str]
    confidence_score: float
    priority_score: float
    decision_metadata: Dict[str, Any]
    cost_benefit_analysis: Dict[str, Any]


class OCRDecisionEngine:
    """OCR 단계 전환 판단 엔진 - SOLID 원칙 적용"""
    
    def __init__(self, thresholds: Optional[DecisionThresholds] = None):
        """
        초기화
        
        Args:
            thresholds: 판단 임계값 설정
        """
        self.thresholds = thresholds or DecisionThresholds()
        
        # 특수 케이스 키워드 정의
        self.special_case_keywords = {
            'charts': ['chart', 'graph', '차트', '그래프', '도표', 'pie', 'bar', 'line'],
            'forms': ['form', 'application', '신청서', '양식', '서식', 'questionnaire'],
            'complex_layouts': ['invoice', 'receipt', '영수증', '송장', '계산서', 'statement'],
            'financial': ['balance', 'income', 'revenue', '재무', '손익', '대차', 'financial'],
            'technical': ['diagram', 'blueprint', '도면', 'schematic', 'technical'],
            'handwritten': ['handwritten', 'manuscript', '손글씨', '필기'],
            'multilingual': ['multilingual', 'mixed', '다국어', 'bilingual']
        }
        
        # 업그레이드 이유별 가중치
        self.reason_weights = {
            UpgradeReason.LOW_CONFIDENCE: 0.9,
            UpgradeReason.LOW_KOREAN_ACCURACY: 0.8,
            UpgradeReason.HIGH_TABLE_COMPLEXITY: 0.7,
            UpgradeReason.HIGH_OVERALL_COMPLEXITY: 0.6,
            UpgradeReason.SPECIAL_CONTENT_DETECTED: 0.75,
            UpgradeReason.POOR_TEXT_QUALITY: 0.85,
            UpgradeReason.MIXED_LANGUAGE_DETECTED: 0.7,
            UpgradeReason.FINANCIAL_CONTENT: 0.65
        }
        
        # 비용-효과 분석 파라미터
        self.cost_params = {
            'tier2_base_cost': 1.0,
            'tier3_base_cost': 5.0,
            'accuracy_improvement_value': 10.0,
            'time_cost_factor': 0.1
        }
    
    def should_upgrade_to_tier3(self, tier2_result: Dict[str, Any], 
                              complexity_metrics: Dict[str, Any],
                              context_info: Optional[Dict[str, Any]] = None) -> UpgradeDecision:
        """Tier 3로 업그레이드 여부 판단"""
        try:
            reasons = []
            upgrade_factors = []
            
            # 1. 신뢰도 검사
            confidence = tier2_result.get('confidence', 0)
            if confidence < self.thresholds.confidence_threshold:
                reasons.append(f"낮은 신뢰도: {confidence:.2f}")
                upgrade_factors.append({
                    'reason': UpgradeReason.LOW_CONFIDENCE,
                    'score': (self.thresholds.confidence_threshold - confidence) * self.reason_weights[UpgradeReason.LOW_CONFIDENCE],
                    'evidence': {'current_confidence': confidence, 'threshold': self.thresholds.confidence_threshold}
                })
            
            # 2. 한국어 정확도 검사
            korean_accuracy = tier2_result.get('korean_accuracy', 0)
            if korean_accuracy < self.thresholds.korean_accuracy_threshold:
                reasons.append(f"한국어 정확도 낮음: {korean_accuracy:.2f}")
                upgrade_factors.append({
                    'reason': UpgradeReason.LOW_KOREAN_ACCURACY,
                    'score': (self.thresholds.korean_accuracy_threshold - korean_accuracy) * self.reason_weights[UpgradeReason.LOW_KOREAN_ACCURACY],
                    'evidence': {'korean_accuracy': korean_accuracy, 'threshold': self.thresholds.korean_accuracy_threshold}
                })
            
            # 3. 테이블 복잡도 검사
            table_complexity = complexity_metrics.get('table_complexity', 0)
            if table_complexity > self.thresholds.table_complexity_threshold:
                reasons.append(f"복잡한 테이블 구조: {table_complexity:.2f}")
                upgrade_factors.append({
                    'reason': UpgradeReason.HIGH_TABLE_COMPLEXITY,
                    'score': (table_complexity - self.thresholds.table_complexity_threshold) * self.reason_weights[UpgradeReason.HIGH_TABLE_COMPLEXITY],
                    'evidence': {'table_complexity': table_complexity, 'threshold': self.thresholds.table_complexity_threshold}
                })
            
            # 4. 전체 복잡도 검사
            overall_complexity = complexity_metrics.get('overall_complexity', 0)
            if overall_complexity > self.thresholds.overall_complexity_threshold:
                reasons.append(f"높은 전체 복잡도: {overall_complexity:.2f}")
                upgrade_factors.append({
                    'reason': UpgradeReason.HIGH_OVERALL_COMPLEXITY,
                    'score': (overall_complexity - self.thresholds.overall_complexity_threshold) * self.reason_weights[UpgradeReason.HIGH_OVERALL_COMPLEXITY],
                    'evidence': {'overall_complexity': overall_complexity, 'threshold': self.thresholds.overall_complexity_threshold}
                })
            
            # 5. 특수 케이스 검사
            special_cases = self._detect_special_cases(tier2_result, context_info)
            if special_cases:
                reasons.extend([f"특수 형식 감지: {', '.join(special_cases)}" for special_cases in special_cases])
                upgrade_factors.append({
                    'reason': UpgradeReason.SPECIAL_CONTENT_DETECTED,
                    'score': len(special_cases) * 0.2 * self.reason_weights[UpgradeReason.SPECIAL_CONTENT_DETECTED],
                    'evidence': {'detected_cases': special_cases}
                })
            
            # 6. 텍스트 품질 검사
            text_quality_score = self._analyze_text_quality(tier2_result)
            if text_quality_score < self.thresholds.text_quality_threshold:
                reasons.append(f"텍스트 품질 낮음: {text_quality_score:.2f}")
                upgrade_factors.append({
                    'reason': UpgradeReason.POOR_TEXT_QUALITY,
                    'score': (self.thresholds.text_quality_threshold - text_quality_score) * self.reason_weights[UpgradeReason.POOR_TEXT_QUALITY],
                    'evidence': {'text_quality': text_quality_score, 'threshold': self.thresholds.text_quality_threshold}
                })
            
            # 7. 다국어 컨텐츠 검사
            if self._has_mixed_language_content(tier2_result):
                reasons.append("다국어 컨텐츠 감지")
                upgrade_factors.append({
                    'reason': UpgradeReason.MIXED_LANGUAGE_DETECTED,
                    'score': 0.5 * self.reason_weights[UpgradeReason.MIXED_LANGUAGE_DETECTED],
                    'evidence': {'mixed_language_detected': True}
                })
            
            # 8. 재무 컨텐츠 검사
            if self._has_financial_content(tier2_result, context_info):
                reasons.append("재무 컨텐츠 감지")
                upgrade_factors.append({
                    'reason': UpgradeReason.FINANCIAL_CONTENT,
                    'score': 0.4 * self.reason_weights[UpgradeReason.FINANCIAL_CONTENT],
                    'evidence': {'financial_content_detected': True}
                })
            
            # 우선순위 점수 계산
            priority_score = sum(factor['score'] for factor in upgrade_factors)
            
            # 업그레이드 결정
            should_upgrade = priority_score > 0.5  # 임계값
            target_tier = ProcessingTier.TIER_3 if should_upgrade else ProcessingTier.TIER_2
            
            # 비용-효과 분석
            cost_benefit = self._analyze_cost_benefit(
                tier2_result, complexity_metrics, upgrade_factors, should_upgrade
            )
            
            # 결정 메타데이터
            decision_metadata = {
                'tier2_confidence': confidence,
                'korean_accuracy': korean_accuracy,
                'complexity_metrics': complexity_metrics,
                'upgrade_factors': upgrade_factors,
                'priority_score': priority_score,
                'threshold_comparisons': {
                    'confidence': {'value': confidence, 'threshold': self.thresholds.confidence_threshold, 'passed': confidence >= self.thresholds.confidence_threshold},
                    'korean_accuracy': {'value': korean_accuracy, 'threshold': self.thresholds.korean_accuracy_threshold, 'passed': korean_accuracy >= self.thresholds.korean_accuracy_threshold},
                    'table_complexity': {'value': table_complexity, 'threshold': self.thresholds.table_complexity_threshold, 'passed': table_complexity <= self.thresholds.table_complexity_threshold},
                    'overall_complexity': {'value': overall_complexity, 'threshold': self.thresholds.overall_complexity_threshold, 'passed': overall_complexity <= self.thresholds.overall_complexity_threshold}
                }
            }
            
            return UpgradeDecision(
                should_upgrade=should_upgrade,
                target_tier=target_tier,
                reasons=reasons,
                confidence_score=confidence,
                priority_score=priority_score,
                decision_metadata=decision_metadata,
                cost_benefit_analysis=cost_benefit
            )
            
        except Exception as e:
            logger.error(f"Decision engine failed: {e}")
            return self._create_fallback_decision(tier2_result)
    
    def _detect_special_cases(self, tier2_result: Dict[str, Any], 
                            context_info: Optional[Dict[str, Any]] = None) -> List[str]:
        """특수 케이스 감지"""
        detected_cases = []
        text = tier2_result.get('text', '').lower()
        
        # 텍스트 기반 감지
        for case_type, keywords in self.special_case_keywords.items():
            if any(keyword in text for keyword in keywords):
                detected_cases.append(case_type)
        
        # 컨텍스트 정보 기반 감지
        if context_info:
            context_tags = context_info.get('context_tags', [])
            for tag in context_tags:
                tag_lower = tag.lower()
                for case_type, keywords in self.special_case_keywords.items():
                    if any(keyword in tag_lower for keyword in keywords):
                        if case_type not in detected_cases:
                            detected_cases.append(case_type)
        
        # 구조적 특징 기반 감지
        if tier2_result.get('table_data'):
            if 'complex_layouts' not in detected_cases:
                detected_cases.append('table_structure')
        
        return detected_cases
    
    def _analyze_text_quality(self, tier2_result: Dict[str, Any]) -> float:
        """텍스트 품질 분석"""
        try:
            text = tier2_result.get('text', '')
            
            if not text:
                return 0.0
            
            quality_factors = []
            
            # 1. 문자 인식 일관성
            char_consistency = self._calculate_character_consistency(text)
            quality_factors.append(char_consistency * 0.3)
            
            # 2. 단어 완성도
            word_completeness = self._calculate_word_completeness(text)
            quality_factors.append(word_completeness * 0.25)
            
            # 3. 구두점 적절성
            punctuation_quality = self._calculate_punctuation_quality(text)
            quality_factors.append(punctuation_quality * 0.15)
            
            # 4. 문장 구조 일관성
            sentence_structure = self._calculate_sentence_structure_quality(text)
            quality_factors.append(sentence_structure * 0.2)
            
            # 5. 숫자/특수문자 정확성
            special_char_quality = self._calculate_special_character_quality(text)
            quality_factors.append(special_char_quality * 0.1)
            
            return sum(quality_factors)
            
        except Exception as e:
            logger.error(f"Text quality analysis failed: {e}")
            return 0.5  # 기본값
    
    def _calculate_character_consistency(self, text: str) -> float:
        """문자 인식 일관성 계산"""
        import re
        
        # 이상한 문자 조합 패턴 검사
        weird_patterns = [
            r'[0-9][a-zA-Z][0-9]',  # 숫자-문자-숫자
            r'[a-zA-Z][0-9][a-zA-Z]',  # 문자-숫자-문자
            r'[가-힣][0-9][가-힣]',  # 한글-숫자-한글
            r'[!@#$%^&*()]{2,}',  # 연속 특수문자
        ]
        
        total_chars = len(text)
        weird_chars = 0
        
        for pattern in weird_patterns:
            matches = re.findall(pattern, text)
            weird_chars += sum(len(match) for match in matches)
        
        if total_chars == 0:
            return 1.0
        
        consistency = 1.0 - (weird_chars / total_chars)
        return max(consistency, 0.0)
    
    def _calculate_word_completeness(self, text: str) -> float:
        """단어 완성도 계산"""
        words = text.split()
        if not words:
            return 0.0
        
        # 너무 짧거나 이상한 단어 비율 계산
        problematic_words = 0
        for word in words:
            # 1글자 단어 (조사, 접속사 제외)
            if len(word) == 1 and word not in ['I', 'a', '가', '을', '를', '이', '은', '는', '와', '과']:
                problematic_words += 1
            # 너무 긴 단어 (오인식 가능성)
            elif len(word) > 20:
                problematic_words += 1
            # 숫자와 문자가 섞인 이상한 단어
            elif any(c.isdigit() for c in word) and any(c.isalpha() for c in word) and len(word) > 3:
                problematic_words += 1
        
        completeness = 1.0 - (problematic_words / len(words))
        return max(completeness, 0.0)
    
    def _calculate_punctuation_quality(self, text: str) -> float:
        """구두점 품질 계산"""
        import re
        
        # 올바른 구두점 패턴
        good_punctuation = len(re.findall(r'[.!?,:;]', text))
        
        # 이상한 구두점 패턴
        bad_punctuation = len(re.findall(r'[.!?]{2,}|[,;:]{2,}', text))
        
        if good_punctuation + bad_punctuation == 0:
            return 1.0  # 구두점이 없으면 문제없음
        
        quality = good_punctuation / (good_punctuation + bad_punctuation * 2)
        return min(quality, 1.0)
    
    def _calculate_sentence_structure_quality(self, text: str) -> float:
        """문장 구조 품질 계산"""
        sentences = text.split('.')
        if len(sentences) <= 1:
            return 1.0  # 단일 문장이면 구조 문제 없음
        
        # 너무 짧거나 긴 문장 비율 확인
        problematic_sentences = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                if len(sentence) < 5:  # 너무 짧음
                    problematic_sentences += 1
                elif len(sentence) > 200:  # 너무 길음
                    problematic_sentences += 1
        
        if len(sentences) == 0:
            return 1.0
        
        quality = 1.0 - (problematic_sentences / len(sentences))
        return max(quality, 0.0)
    
    def _calculate_special_character_quality(self, text: str) -> float:
        """특수문자 품질 계산"""
        import re
        
        # 숫자 패턴 검사
        number_patterns = re.findall(r'\d+', text)
        good_numbers = 0
        bad_numbers = 0
        
        for num in number_patterns:
            if len(num) <= 10:  # 정상적인 숫자
                good_numbers += 1
            else:  # 너무 긴 숫자 (오인식 가능성)
                bad_numbers += 1
        
        if good_numbers + bad_numbers == 0:
            return 1.0
        
        quality = good_numbers / (good_numbers + bad_numbers)
        return min(quality, 1.0)
    
    def _has_mixed_language_content(self, tier2_result: Dict[str, Any]) -> bool:
        """다국어 컨텐츠 감지"""
        text = tier2_result.get('text', '')
        
        # 언어별 문자 비율 계산
        korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7af')
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        japanese_chars = sum(1 for c in text if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
        
        total_alpha_chars = korean_chars + english_chars + chinese_chars + japanese_chars
        
        if total_alpha_chars < 10:  # 너무 적은 텍스트
            return False
        
        # 두 개 이상 언어가 20% 이상씩 포함되어 있으면 다국어로 판단
        language_ratios = [
            korean_chars / total_alpha_chars,
            english_chars / total_alpha_chars,
            chinese_chars / total_alpha_chars,
            japanese_chars / total_alpha_chars
        ]
        
        significant_languages = sum(1 for ratio in language_ratios if ratio > 0.2)
        return significant_languages >= 2
    
    def _has_financial_content(self, tier2_result: Dict[str, Any], 
                             context_info: Optional[Dict[str, Any]] = None) -> bool:
        """재무 컨텐츠 감지"""
        text = tier2_result.get('text', '').lower()
        
        # 재무 키워드 확인
        financial_keywords = [
            'balance', 'income', 'revenue', 'profit', 'loss', 'asset', 'liability',
            '재무', '손익', '대차', '자산', '부채', '매출', '이익', '손실',
            'financial', 'statement', '제표', '계산서'
        ]
        
        financial_score = sum(1 for keyword in financial_keywords if keyword in text)
        
        # 컨텍스트 정보에서 재무 관련 힌트 확인
        if context_info:
            context_tags = context_info.get('context_tags', [])
            financial_score += sum(1 for tag in context_tags if 'financial' in tag.lower())
        
        return financial_score >= 2
    
    def _analyze_cost_benefit(self, tier2_result: Dict[str, Any], 
                            complexity_metrics: Dict[str, Any],
                            upgrade_factors: List[Dict[str, Any]], 
                            should_upgrade: bool) -> Dict[str, Any]:
        """비용-효과 분석"""
        try:
            # 현재 품질 점수
            current_quality = tier2_result.get('confidence', 0)
            
            # 예상 개선도 계산
            expected_improvement = 0.0
            for factor in upgrade_factors:
                weight = self.reason_weights.get(factor['reason'], 0.5)
                expected_improvement += factor['score'] * weight
            
            expected_improvement = min(expected_improvement, 0.3)  # 최대 30% 개선
            
            # 비용 계산
            tier2_cost = self.cost_params['tier2_base_cost']
            tier3_cost = self.cost_params['tier3_base_cost']
            additional_cost = tier3_cost - tier2_cost
            
            # 효과 계산
            quality_benefit = expected_improvement * self.cost_params['accuracy_improvement_value']
            
            # ROI 계산
            roi = (quality_benefit - additional_cost) / additional_cost if additional_cost > 0 else 0
            
            return {
                'current_quality': current_quality,
                'expected_improvement': expected_improvement,
                'expected_final_quality': min(current_quality + expected_improvement, 1.0),
                'tier2_cost': tier2_cost,
                'tier3_cost': tier3_cost,
                'additional_cost': additional_cost,
                'quality_benefit': quality_benefit,
                'roi': roi,
                'cost_effective': roi > 0.5,
                'upgrade_recommended': should_upgrade and roi > 0.2
            }
            
        except Exception as e:
            logger.error(f"Cost-benefit analysis failed: {e}")
            return {'error': str(e)}
    
    def _create_fallback_decision(self, tier2_result: Dict[str, Any]) -> UpgradeDecision:
        """fallback 결정 생성"""
        confidence = tier2_result.get('confidence', 0)
        
        return UpgradeDecision(
            should_upgrade=confidence < 0.7,  # 낮은 신뢰도면 업그레이드
            target_tier=ProcessingTier.TIER_3 if confidence < 0.7 else ProcessingTier.TIER_2,
            reasons=["Decision engine error - fallback decision"],
            confidence_score=confidence,
            priority_score=0.5,
            decision_metadata={'error': 'Decision engine failed'},
            cost_benefit_analysis={'error': 'Cost-benefit analysis failed'}
        )
    
    def get_tier_recommendation_for_document_type(self, document_type: str, 
                                                 language: str = "korean") -> ProcessingTier:
        """문서 타입별 권장 처리 계층"""
        recommendations = {
            'financial_statement': ProcessingTier.TIER_3,
            'complex_table': ProcessingTier.TIER_3,
            'handwritten_form': ProcessingTier.TIER_3,
            'technical_diagram': ProcessingTier.TIER_3,
            'simple_text': ProcessingTier.TIER_2,
            'basic_table': ProcessingTier.TIER_2,
            'receipt': ProcessingTier.TIER_2,
            'general': ProcessingTier.TIER_2
        }
        
        return recommendations.get(document_type, ProcessingTier.TIER_2)
    
    def analyze_upgrade_patterns(self, decisions: List[UpgradeDecision]) -> Dict[str, Any]:
        """업그레이드 패턴 분석"""
        if not decisions:
            return {}
        
        total_decisions = len(decisions)
        upgrades = sum(1 for d in decisions if d.should_upgrade)
        
        # 이유별 통계
        reason_stats = {}
        for decision in decisions:
            for reason in decision.reasons:
                reason_stats[reason] = reason_stats.get(reason, 0) + 1
        
        # 우선순위 점수 분포
        priority_scores = [d.priority_score for d in decisions]
        
        return {
            'total_decisions': total_decisions,
            'upgrade_rate': upgrades / total_decisions,
            'average_priority_score': sum(priority_scores) / len(priority_scores),
            'reason_frequency': reason_stats,
            'most_common_reasons': sorted(reason_stats.items(), key=lambda x: x[1], reverse=True)[:5],
            'score_distribution': {
                'low': sum(1 for s in priority_scores if s < 0.3),
                'medium': sum(1 for s in priority_scores if 0.3 <= s < 0.7),
                'high': sum(1 for s in priority_scores if s >= 0.7)
            }
        }