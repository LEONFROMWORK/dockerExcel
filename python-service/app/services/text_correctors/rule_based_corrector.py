"""
규칙 기반 텍스트 교정기
TransformerOCRService에서 분리된 규칙 기반 교정 로직
Single Responsibility Principle 적용
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
import unicodedata

from app.core.ocr_interfaces import (
    BaseTextCorrector, CorrectionContext, CorrectionResult,
    TextCorrection, CorrectionMethod, LanguageCode, DocumentType
)

logger = logging.getLogger(__name__)


class RuleBasedCorrector(BaseTextCorrector):
    """규칙 기반 텍스트 교정기"""
    
    def __init__(self, metrics_collector=None):
        super().__init__(metrics_collector)
        
        # 일반적인 OCR 오류 패턴
        self.common_ocr_patterns = {
            # 숫자와 문자 혼동
            r'0': ['O', 'o', 'D'],
            r'1': ['l', 'I', '|'],
            r'5': ['S', 's'],
            r'8': ['B'],
            r'9': ['g', 'q'],
            # 문자와 숫자 혼동
            r'O': ['0'],
            r'I': ['1', 'l'],
            r'S': ['5'],
            r'B': ['8'],
            r'g': ['9'],
            r'q': ['9']
        }
        
        # 언어별 일반적인 오류 패턴
        self.language_patterns = {
            LanguageCode.KOREAN: {
                # 한글 자소 분리/결합 오류
                'ㄱ': 'ᆨ',  # 종성 ㄱ
                'ㄴ': 'ᆫ',  # 종성 ㄴ
                'ㄷ': 'ᆮ',  # 종성 ㄷ
                'ㄹ': 'ᆯ',  # 종성 ㄹ
                'ㅁ': 'ᆷ',  # 종성 ㅁ
                'ㅂ': 'ᆸ',  # 종성 ㅂ
                'ㅅ': 'ᆺ',  # 종성 ㅅ
                'ㅇ': 'ᆼ',  # 종성 ㅇ
                'ㅈ': 'ᆽ',  # 종성 ㅈ
                'ㅊ': 'ᆾ',  # 종성 ㅊ
                'ㅋ': 'ᆿ',  # 종성 ㅋ
                'ㅌ': 'ᇀ',  # 종성 ㅌ
                'ㅍ': 'ᇁ',  # 종성 ㅍ
                'ㅎ': 'ᇂ',  # 종성 ㅎ
            },
            LanguageCode.ENGLISH: {
                'rn': 'm',  # rn이 m으로 보이는 경우
                'cl': 'd',  # cl이 d로 보이는 경우
                'vv': 'w',  # vv가 w로 보이는 경우
            },
            LanguageCode.CHINESE_SIMPLIFIED: {
                '丶': '丿',  # 점과 삐침 혼동
                '乚': '乙',  # 유사한 부수 혼동
            },
            LanguageCode.JAPANESE: {
                'ツ': 'シ',  # 가타카나 혼동
                'ソ': 'ン',  # 가타카나 혼동
                'る': 'ろ',  # 히라가나 혼동
            }
        }
        
        # 재무 용어별 일반적인 오류 패턴
        self.financial_corrections = {
            LanguageCode.KOREAN: [
                (r'매출액|매출', '매출액'),
                (r'순이익|순익', '순이익'),
                (r'자산총계|총자산|자산계', '자산총계'),
                (r'부채총계|총부채|부채계', '부채총계'),
                (r'자본총계|총자본|자본계', '자본총계'),
                (r'영업이익', '영업이익'),
                (r'당기순이익|당기이익', '당기순이익'),
                (r'유동자산', '유동자산'),
                (r'고정자산', '고정자산'),
                (r'유동부채', '유동부채'),
                (r'고정부채', '고정부채'),
                (r'자기자본', '자기자본'),
                (r'손익계산서', '손익계산서'),
                (r'대차대조표', '대차대조표'),
                (r'현금흐름표', '현금흐름표'),
            ],
            LanguageCode.ENGLISH: [
                (r'revenue|sales', 'Revenue'),
                (r'net income|profit', 'Net Income'),
                (r'total assets', 'Total Assets'),
                (r'total liabilities', 'Total Liabilities'),
                (r'shareholders equity', 'Shareholders Equity'),
                (r'operating income', 'Operating Income'),
                (r'current assets', 'Current Assets'),
                (r'fixed assets', 'Fixed Assets'),
                (r'current liabilities', 'Current Liabilities'),
                (r'long term liabilities', 'Long-term Liabilities'),
                (r'balance sheet', 'Balance Sheet'),
                (r'income statement', 'Income Statement'),
                (r'cash flow statement', 'Cash Flow Statement'),
            ]
        }
        
        # 숫자 패턴 교정
        self.number_patterns = [
            # 쉼표가 빠진 큰 숫자
            (r'(\d{4,})', self._add_comma_to_number),
            # 잘못된 소수점 표기
            (r'(\d+)\.(\d{1,2})\s*원', r'\1.\2원'),
            # 통화 단위 분리
            (r'(\d+)(원|달러|\$|€|¥)', r'\1 \2'),
        ]
        
        # 날짜 패턴 교정
        self.date_patterns = [
            # YYYY/MM/DD → YYYY-MM-DD
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', r'\1-\2-\3'),
            # MM/DD/YYYY → YYYY-MM-DD
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', r'\3-\1-\2'),
            # DD.MM.YYYY → YYYY-MM-DD
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', r'\3-\2-\1'),
        ]
        
        # 공백 정규화 패턴
        self.whitespace_patterns = [
            # 여러 공백을 하나로
            (r'\s+', ' '),
            # 줄바꿈 정규화
            (r'\n\s*\n', '\n'),
            # 탭을 공백으로
            (r'\t', ' '),
        ]
    
    async def _correct_text_impl(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """규칙 기반 텍스트 교정 구현"""
        try:
            corrections = []
            corrected_text = text
            
            # 1. 공백 정규화
            corrected_text, whitespace_corrections = self._normalize_whitespace(corrected_text)
            corrections.extend(whitespace_corrections)
            
            # 2. 유니코드 정규화
            corrected_text, unicode_corrections = self._normalize_unicode(corrected_text, context.language)
            corrections.extend(unicode_corrections)
            
            # 3. 일반적인 OCR 오류 교정
            corrected_text, ocr_corrections = self._correct_common_ocr_errors(corrected_text, context)
            corrections.extend(ocr_corrections)
            
            # 4. 언어별 특수 패턴 교정
            corrected_text, language_corrections = self._correct_language_specific_errors(corrected_text, context.language)
            corrections.extend(language_corrections)
            
            # 5. 숫자 패턴 교정
            corrected_text, number_corrections = self._correct_number_patterns(corrected_text)
            corrections.extend(number_corrections)
            
            # 6. 날짜 패턴 교정
            corrected_text, date_corrections = self._correct_date_patterns(corrected_text)
            corrections.extend(date_corrections)
            
            # 7. 재무 용어 교정 (재무 컨텍스트인 경우)
            if context.financial_context:
                corrected_text, financial_corrections = self._correct_financial_terms(corrected_text, context.language)
                corrections.extend(financial_corrections)
            
            # 8. 사용자 정의 어휘 교정
            if context.custom_vocabulary:
                corrected_text, vocab_corrections = self._correct_custom_vocabulary(corrected_text, context.custom_vocabulary)
                corrections.extend(vocab_corrections)
            
            # 9. 전체 신뢰도 계산
            overall_confidence = self._calculate_overall_confidence(text, corrected_text, corrections)
            
            return CorrectionResult(
                corrected_text=corrected_text,
                corrections=corrections,
                overall_confidence=overall_confidence,
                method_used=CorrectionMethod.RULE_BASED,
                processing_time=0.0  # 상위 클래스에서 설정
            )
            
        except Exception as e:
            logger.error(f"Rule-based correction failed: {e}")
            return CorrectionResult(
                corrected_text=text,
                corrections=[],
                overall_confidence=0.0,
                method_used=CorrectionMethod.RULE_BASED,
                processing_time=0.0
            )
    
    def _normalize_whitespace(self, text: str) -> Tuple[str, List[TextCorrection]]:
        """공백 정규화"""
        corrections = []
        result = text
        
        for pattern, replacement in self.whitespace_patterns:
            matches = list(re.finditer(pattern, result))
            for match in reversed(matches):  # 뒤에서부터 교체
                original = match.group()
                if pattern == r'\s+' and len(original) > 1:
                    corrected = ' '
                elif pattern == r'\n\s*\n' and original != '\n':
                    corrected = '\n'
                elif pattern == r'\t':
                    corrected = ' '
                else:
                    continue
                
                if original != corrected:
                    corrections.append(TextCorrection(
                        original=original,
                        corrected=corrected,
                        confidence=0.95,
                        method=CorrectionMethod.RULE_BASED,
                        reason="whitespace_normalization",
                        position={'start': match.start(), 'end': match.end()}
                    ))
                    result = result[:match.start()] + corrected + result[match.end():]
        
        return result, corrections
    
    def _normalize_unicode(self, text: str, language: LanguageCode) -> Tuple[str, List[TextCorrection]]:
        """유니코드 정규화"""
        corrections = []
        
        # NFC 정규화 (한글 자소 결합)
        normalized = unicodedata.normalize('NFC', text)
        
        if normalized != text:
            corrections.append(TextCorrection(
                original=text,
                corrected=normalized,
                confidence=0.9,
                method=CorrectionMethod.RULE_BASED,
                reason="unicode_normalization"
            ))
        
        return normalized, corrections
    
    def _correct_common_ocr_errors(self, text: str, context: CorrectionContext) -> Tuple[str, List[TextCorrection]]:
        """일반적인 OCR 오류 교정"""
        corrections = []
        result = text
        
        for correct_char, wrong_chars in self.common_ocr_patterns.items():
            for wrong_char in wrong_chars:
                # 숫자 컨텍스트에서만 숫자 교정
                if correct_char.isdigit() and wrong_char.isalpha():
                    pattern = rf'\b{re.escape(wrong_char)}(?=\d|\s|\b)'
                    matches = list(re.finditer(pattern, result))
                    
                    for match in reversed(matches):
                        corrections.append(TextCorrection(
                            original=wrong_char,
                            corrected=correct_char,
                            confidence=0.8,
                            method=CorrectionMethod.RULE_BASED,
                            reason="digit_letter_confusion",
                            position={'start': match.start(), 'end': match.end()}
                        ))
                        result = result[:match.start()] + correct_char + result[match.end():]
        
        return result, corrections
    
    def _correct_language_specific_errors(self, text: str, language: LanguageCode) -> Tuple[str, List[TextCorrection]]:
        """언어별 특수 패턴 교정"""
        corrections = []
        result = text
        
        if language not in self.language_patterns:
            return result, corrections
        
        patterns = self.language_patterns[language]
        
        for wrong, correct in patterns.items():
            if wrong in result:
                corrections.append(TextCorrection(
                    original=wrong,
                    corrected=correct,
                    confidence=0.85,
                    method=CorrectionMethod.RULE_BASED,
                    reason=f"language_specific_{language.value}",
                ))
                result = result.replace(wrong, correct)
        
        return result, corrections
    
    def _correct_number_patterns(self, text: str) -> Tuple[str, List[TextCorrection]]:
        """숫자 패턴 교정"""
        corrections = []
        result = text
        
        for pattern, replacement in self.number_patterns:
            if callable(replacement):
                # 함수 기반 교정
                matches = list(re.finditer(pattern, result))
                for match in reversed(matches):
                    original = match.group()
                    corrected = replacement(match)
                    
                    if original != corrected:
                        corrections.append(TextCorrection(
                            original=original,
                            corrected=corrected,
                            confidence=0.9,
                            method=CorrectionMethod.RULE_BASED,
                            reason="number_formatting",
                            position={'start': match.start(), 'end': match.end()}
                        ))
                        result = result[:match.start()] + corrected + result[match.end():]
            else:
                # 정규표현식 기반 교정
                corrected_result = re.sub(pattern, replacement, result)
                if corrected_result != result:
                    corrections.append(TextCorrection(
                        original=result,
                        corrected=corrected_result,
                        confidence=0.9,
                        method=CorrectionMethod.RULE_BASED,
                        reason="number_pattern"
                    ))
                    result = corrected_result
        
        return result, corrections
    
    def _add_comma_to_number(self, match) -> str:
        """큰 숫자에 쉼표 추가"""
        number = match.group(1)
        if len(number) >= 4:
            # 뒤에서부터 3자리씩 쉼표 추가
            formatted = ""
            for i, digit in enumerate(reversed(number)):
                if i > 0 and i % 3 == 0:
                    formatted = "," + formatted
                formatted = digit + formatted
            return formatted
        return number
    
    def _correct_date_patterns(self, text: str) -> Tuple[str, List[TextCorrection]]:
        """날짜 패턴 교정"""
        corrections = []
        result = text
        
        for pattern, replacement in self.date_patterns:
            matches = list(re.finditer(pattern, result))
            for match in reversed(matches):
                original = match.group()
                corrected = re.sub(pattern, replacement, original)
                
                if original != corrected:
                    corrections.append(TextCorrection(
                        original=original,
                        corrected=corrected,
                        confidence=0.85,
                        method=CorrectionMethod.RULE_BASED,
                        reason="date_formatting",
                        position={'start': match.start(), 'end': match.end()}
                    ))
                    result = result[:match.start()] + corrected + result[match.end():]
        
        return result, corrections
    
    def _correct_financial_terms(self, text: str, language: LanguageCode) -> Tuple[str, List[TextCorrection]]:
        """재무 용어 교정"""
        corrections = []
        result = text
        
        if language not in self.financial_corrections:
            return result, corrections
        
        patterns = self.financial_corrections[language]
        
        for pattern, replacement in patterns:
            matches = list(re.finditer(pattern, result, re.IGNORECASE))
            for match in reversed(matches):
                original = match.group()
                if original != replacement:
                    corrections.append(TextCorrection(
                        original=original,
                        corrected=replacement,
                        confidence=0.95,
                        method=CorrectionMethod.RULE_BASED,
                        reason="financial_term_standardization",
                        position={'start': match.start(), 'end': match.end()}
                    ))
                    result = result[:match.start()] + replacement + result[match.end():]
        
        return result, corrections
    
    def _correct_custom_vocabulary(self, text: str, vocabulary: List[str]) -> Tuple[str, List[TextCorrection]]:
        """사용자 정의 어휘 교정"""
        corrections = []
        result = text
        
        words = result.split()
        corrected_words = words.copy()
        
        for i, word in enumerate(words):
            # 어휘와 유사한 단어 찾기
            best_match = self._find_best_vocabulary_match(word, vocabulary)
            if best_match and best_match != word:
                corrections.append(TextCorrection(
                    original=word,
                    corrected=best_match,
                    confidence=0.8,
                    method=CorrectionMethod.RULE_BASED,
                    reason="custom_vocabulary_match"
                ))
                corrected_words[i] = best_match
        
        if corrected_words != words:
            result = ' '.join(corrected_words)
        
        return result, corrections
    
    def _find_best_vocabulary_match(self, word: str, vocabulary: List[str]) -> Optional[str]:
        """어휘에서 가장 유사한 단어 찾기"""
        if not word or not vocabulary:
            return None
        
        # 완전 일치
        if word in vocabulary:
            return word
        
        # 대소문자 무시 일치
        for vocab_word in vocabulary:
            if word.lower() == vocab_word.lower():
                return vocab_word
        
        # 편집 거리 기반 유사도 (간단한 버전)
        best_match = None
        min_distance = float('inf')
        
        for vocab_word in vocabulary:
            distance = self._calculate_edit_distance(word.lower(), vocab_word.lower())
            # 유사도 임계값: 단어 길이의 30% 이하
            threshold = max(1, len(vocab_word) * 0.3)
            
            if distance < min_distance and distance <= threshold:
                min_distance = distance
                best_match = vocab_word
        
        return best_match
    
    def _calculate_edit_distance(self, s1: str, s2: str) -> int:
        """편집 거리 계산 (레벤시테인 거리)"""
        if len(s1) < len(s2):
            return self._calculate_edit_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _calculate_overall_confidence(self, original: str, corrected: str, 
                                    corrections: List[TextCorrection]) -> float:
        """전체 교정 신뢰도 계산"""
        if original == corrected:
            return 1.0
        
        if not corrections:
            return 0.5
        
        # 교정 타입별 가중치
        type_weights = {
            "whitespace_normalization": 0.95,
            "unicode_normalization": 0.9,
            "digit_letter_confusion": 0.8,
            "number_formatting": 0.9,
            "date_formatting": 0.85,
            "financial_term_standardization": 0.95,
            "custom_vocabulary_match": 0.8
        }
        
        # 가중 평균 신뢰도
        weighted_sum = 0.0
        total_weight = 0.0
        
        for correction in corrections:
            weight = type_weights.get(correction.reason, 0.7)
            weighted_sum += correction.confidence * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.5
        
        base_confidence = weighted_sum / total_weight
        
        # 교정 비율에 따른 페널티 (너무 많은 교정은 신뢰도 감소)
        correction_ratio = len(corrections) / max(len(original.split()), 1)
        penalty = min(0.3, correction_ratio * 0.1)
        
        return max(0.1, base_confidence - penalty)
    
    def supports_language(self, language: LanguageCode) -> bool:
        """언어 지원 여부 확인"""
        # 규칙 기반 교정은 대부분의 언어를 지원
        return True
    
    def get_correction_method(self) -> CorrectionMethod:
        """교정 방법 반환"""
        return CorrectionMethod.RULE_BASED


class FinancialRuleBasedCorrector(RuleBasedCorrector):
    """재무 특화 규칙 기반 교정기"""
    
    def __init__(self, metrics_collector=None):
        super().__init__(metrics_collector)
        
        # 재무제표 특화 패턴 확장
        self.financial_corrections[LanguageCode.KOREAN].extend([
            # 계정과목 표준화
            (r'현금및현금성자산|현금성자산', '현금및현금성자산'),
            (r'단기투자자산|단기투자', '단기투자자산'),
            (r'매출채권|수취채권', '매출채권'),
            (r'재고자산|재고', '재고자산'),
            (r'유형자산|고정자산', '유형자산'),
            (r'무형자산', '무형자산'),
            (r'매입채무|지급채무', '매입채무'),
            (r'미지급금|미지급비용', '미지급금'),
            (r'차입금|借入金', '차입금'),
            (r'자본금|資本金', '자본금'),
            (r'이익잉여금|留保利益', '이익잉여금'),
            
            # 손익계산서 항목
            (r'매출원가|원가', '매출원가'),
            (r'판매비와관리비|판관비', '판매비와관리비'),
            (r'연구개발비|R&D비용', '연구개발비'),
            (r'감가상각비|減價償却費', '감가상각비'),
            (r'법인세비용|법인세', '법인세비용'),
            
            # 재무비율 관련
            (r'유동비율|流動比率', '유동비율'),
            (r'부채비율|負債比率', '부채비율'),
            (r'자기자본비율|自己資本比率', '자기자본비율'),
            (r'총자산순이익률|ROA', '총자산순이익률'),
            (r'자기자본순이익률|ROE', '자기자본순이익률'),
        ])
    
    async def _correct_text_impl(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """재무 특화 교정 로직"""
        # 기본 규칙 기반 교정 수행
        result = await super()._correct_text_impl(text, context)
        
        # 재무 특화 후처리
        if context.financial_context:
            financial_result = self._apply_financial_post_processing(result.corrected_text, context)
            result.corrected_text = financial_result.corrected_text
            result.corrections.extend(financial_result.corrections)
            
            # 신뢰도 재계산
            result.overall_confidence = self._calculate_overall_confidence(
                text, result.corrected_text, result.corrections
            )
        
        return result
    
    def _apply_financial_post_processing(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """재무 특화 후처리"""
        corrections = []
        result = text
        
        # 금액 표기 정규화
        result, amount_corrections = self._normalize_financial_amounts(result)
        corrections.extend(amount_corrections)
        
        # 회계 기간 표기 정규화
        result, period_corrections = self._normalize_accounting_periods(result)
        corrections.extend(period_corrections)
        
        # 재무비율 표기 정규화
        result, ratio_corrections = self._normalize_financial_ratios(result)
        corrections.extend(ratio_corrections)
        
        return CorrectionResult(
            corrected_text=result,
            corrections=corrections,
            overall_confidence=0.9,
            method_used=CorrectionMethod.RULE_BASED,
            processing_time=0.0
        )
    
    def _normalize_financial_amounts(self, text: str) -> Tuple[str, List[TextCorrection]]:
        """금액 표기 정규화"""
        corrections = []
        result = text
        
        # 금액 단위 패턴
        amount_patterns = [
            # 천원, 백만원 등 단위 정규화
            (r'(\d+)\s*(천원|천|K)', r'\1천원'),
            (r'(\d+)\s*(백만원|백만|M)', r'\1백만원'),
            (r'(\d+)\s*(십억원|십억|B)', r'\1십억원'),
            (r'(\d+)\s*(조원|조|T)', r'\1조원'),
            
            # 괄호 표기 정규화 (손실 표시)
            (r'\((\d+(?:,\d{3})*)\)', r'(\1)'),
            
            # 퍼센트 표기 정규화
            (r'(\d+(?:\.\d+)?)\s*%', r'\1%'),
        ]
        
        for pattern, replacement in amount_patterns:
            matches = list(re.finditer(pattern, result))
            for match in reversed(matches):
                original = match.group()
                corrected = re.sub(pattern, replacement, original)
                
                if original != corrected:
                    corrections.append(TextCorrection(
                        original=original,
                        corrected=corrected,
                        confidence=0.9,
                        method=CorrectionMethod.RULE_BASED,
                        reason="financial_amount_normalization",
                        position={'start': match.start(), 'end': match.end()}
                    ))
                    result = result[:match.start()] + corrected + result[match.end():]
        
        return result, corrections
    
    def _normalize_accounting_periods(self, text: str) -> Tuple[str, List[TextCorrection]]:
        """회계 기간 표기 정규화"""
        corrections = []
        result = text
        
        # 회계 기간 패턴
        period_patterns = [
            # 분기 표기
            (r'(\d{4})\s*년\s*(\d)\s*분기', r'\1년 \2분기'),
            (r'(\d{4})\s*Q(\d)', r'\1년 \2분기'),
            
            # 반기 표기
            (r'(\d{4})\s*년\s*상반기', r'\1년 상반기'),
            (r'(\d{4})\s*년\s*하반기', r'\1년 하반기'),
            (r'(\d{4})\s*H1', r'\1년 상반기'),
            (r'(\d{4})\s*H2', r'\1년 하반기'),
            
            # 연도 표기
            (r'(\d{4})\s*년도', r'\1년'),
            (r'(\d{4})\s*FY', r'\1년'),
        ]
        
        for pattern, replacement in period_patterns:
            corrected_result = re.sub(pattern, replacement, result)
            if corrected_result != result:
                corrections.append(TextCorrection(
                    original=result,
                    corrected=corrected_result,
                    confidence=0.85,
                    method=CorrectionMethod.RULE_BASED,
                    reason="accounting_period_normalization"
                ))
                result = corrected_result
        
        return result, corrections
    
    def _normalize_financial_ratios(self, text: str) -> Tuple[str, List[TextCorrection]]:
        """재무비율 표기 정규화"""
        corrections = []
        result = text
        
        # 재무비율 약어 확장
        ratio_expansions = {
            'ROA': '총자산순이익률',
            'ROE': '자기자본순이익률',
            'ROIC': '투자자본순이익률',
            'P/E': '주가수익비율',
            'P/B': '주가순자산비율',
            'EPS': '주당순이익',
            'BPS': '주당순자산',
            'DPS': '주당배당금',
            'EBITDA': '세전영업이익',
        }
        
        for abbreviation, full_name in ratio_expansions.items():
            pattern = rf'\b{re.escape(abbreviation)}\b'
            if re.search(pattern, result):
                corrected_result = re.sub(pattern, full_name, result)
                if corrected_result != result:
                    corrections.append(TextCorrection(
                        original=abbreviation,
                        corrected=full_name,
                        confidence=0.95,
                        method=CorrectionMethod.RULE_BASED,
                        reason="financial_ratio_expansion"
                    ))
                    result = corrected_result
        
        return result, corrections