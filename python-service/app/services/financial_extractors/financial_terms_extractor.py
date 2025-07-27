"""
재무 용어 추출기
TransformerOCRService에서 분리된 재무 용어 추출 및 분석 로직
Single Responsibility Principle 적용
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

from app.core.ocr_interfaces import LanguageCode, DocumentType

logger = logging.getLogger(__name__)


class FinancialCategory(Enum):
    """재무 카테고리"""
    ASSETS = "assets"
    LIABILITIES = "liabilities"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSES = "expenses"
    PROFIT_LOSS = "profit_loss"
    CASH_FLOW = "cash_flow"
    RATIOS = "ratios"
    CURRENCY = "currency"
    UNKNOWN = "unknown"


@dataclass
class FinancialTerm:
    """재무 용어"""
    term: str
    category: FinancialCategory
    language: LanguageCode
    confidence: float
    position: Dict[str, int]
    amount: Optional[str] = None
    normalized_term: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class FinancialAmount:
    """재무 금액"""
    raw_amount: str
    normalized_amount: float
    currency: str
    unit: str  # 천원, 백만원 등
    confidence: float
    position: Dict[str, int]
    context: str  # 주변 텍스트


@dataclass
class FinancialExtraction:
    """재무 추출 결과"""
    terms: List[FinancialTerm]
    amounts: List[FinancialAmount]
    ratios: List[Dict[str, Any]]
    summary: Dict[str, Any]
    confidence: float


class FinancialTermsExtractor:
    """재무 용어 추출기 - SOLID 원칙 적용"""
    
    def __init__(self):
        # 언어별 재무 용어 사전
        self.financial_terms = {
            LanguageCode.KOREAN: {
                FinancialCategory.ASSETS: [
                    ('현금및현금성자산', '현금및현금성자산', 1.0),
                    ('현금', '현금', 0.9),
                    ('단기투자자산', '단기투자자산', 1.0),
                    ('매출채권', '매출채권', 1.0),
                    ('수취채권', '매출채권', 0.9),
                    ('재고자산', '재고자산', 1.0),
                    ('재고', '재고자산', 0.8),
                    ('유동자산', '유동자산', 1.0),
                    ('고정자산', '고정자산', 1.0),
                    ('유형자산', '유형자산', 1.0),
                    ('무형자산', '무형자산', 1.0),
                    ('자산총계', '자산총계', 1.0),
                    ('총자산', '자산총계', 0.9),
                ],
                FinancialCategory.LIABILITIES: [
                    ('매입채무', '매입채무', 1.0),
                    ('지급채무', '매입채무', 0.9),
                    ('미지급금', '미지급금', 1.0),
                    ('미지급비용', '미지급비용', 1.0),
                    ('단기차입금', '단기차입금', 1.0),
                    ('장기차입금', '장기차입금', 1.0),
                    ('유동부채', '유동부채', 1.0),
                    ('고정부채', '고정부채', 1.0),
                    ('부채총계', '부채총계', 1.0),
                    ('총부채', '부채총계', 0.9),
                ],
                FinancialCategory.EQUITY: [
                    ('자본금', '자본금', 1.0),
                    ('자기자본', '자기자본', 1.0),
                    ('이익잉여금', '이익잉여금', 1.0),
                    ('자본잉여금', '자본잉여금', 1.0),
                    ('자본총계', '자본총계', 1.0),
                    ('총자본', '자본총계', 0.9),
                ],
                FinancialCategory.REVENUE: [
                    ('매출액', '매출액', 1.0),
                    ('매출', '매출액', 0.9),
                    ('영업수익', '영업수익', 1.0),
                    ('영업외수익', '영업외수익', 1.0),
                    ('기타수익', '기타수익', 1.0),
                ],
                FinancialCategory.EXPENSES: [
                    ('매출원가', '매출원가', 1.0),
                    ('원가', '매출원가', 0.8),
                    ('판매비와관리비', '판매비와관리비', 1.0),
                    ('판관비', '판매비와관리비', 0.9),
                    ('연구개발비', '연구개발비', 1.0),
                    ('감가상각비', '감가상각비', 1.0),
                    ('인건비', '인건비', 1.0),
                    ('지급이자', '지급이자', 1.0),
                ],
                FinancialCategory.PROFIT_LOSS: [
                    ('영업이익', '영업이익', 1.0),
                    ('영업손실', '영업손실', 1.0),
                    ('법인세차감전순이익', '법인세차감전순이익', 1.0),
                    ('당기순이익', '당기순이익', 1.0),
                    ('당기순손실', '당기순손실', 1.0),
                    ('순이익', '순이익', 0.9),
                    ('총이익', '총이익', 0.9),
                ],
                FinancialCategory.RATIOS: [
                    ('유동비율', '유동비율', 1.0),
                    ('부채비율', '부채비율', 1.0),
                    ('자기자본비율', '자기자본비율', 1.0),
                    ('총자산순이익률', 'ROA', 1.0),
                    ('자기자본순이익률', 'ROE', 1.0),
                    ('ROA', 'ROA', 1.0),
                    ('ROE', 'ROE', 1.0),
                ]
            },
            LanguageCode.ENGLISH: {
                FinancialCategory.ASSETS: [
                    ('cash and cash equivalents', 'Cash and Cash Equivalents', 1.0),
                    ('cash', 'Cash', 0.9),
                    ('short-term investments', 'Short-term Investments', 1.0),
                    ('accounts receivable', 'Accounts Receivable', 1.0),
                    ('inventory', 'Inventory', 1.0),
                    ('current assets', 'Current Assets', 1.0),
                    ('fixed assets', 'Fixed Assets', 1.0),
                    ('property plant equipment', 'Property, Plant & Equipment', 1.0),
                    ('intangible assets', 'Intangible Assets', 1.0),
                    ('total assets', 'Total Assets', 1.0),
                ],
                FinancialCategory.LIABILITIES: [
                    ('accounts payable', 'Accounts Payable', 1.0),
                    ('accrued expenses', 'Accrued Expenses', 1.0),
                    ('short-term debt', 'Short-term Debt', 1.0),
                    ('long-term debt', 'Long-term Debt', 1.0),
                    ('current liabilities', 'Current Liabilities', 1.0),
                    ('non-current liabilities', 'Non-current Liabilities', 1.0),
                    ('total liabilities', 'Total Liabilities', 1.0),
                ],
                FinancialCategory.EQUITY: [
                    ('common stock', 'Common Stock', 1.0),
                    ('retained earnings', 'Retained Earnings', 1.0),
                    ('shareholders equity', 'Shareholders Equity', 1.0),
                    ('stockholders equity', 'Stockholders Equity', 1.0),
                    ('total equity', 'Total Equity', 1.0),
                ],
                FinancialCategory.REVENUE: [
                    ('revenue', 'Revenue', 1.0),
                    ('sales', 'Sales', 0.9),
                    ('net sales', 'Net Sales', 1.0),
                    ('operating revenue', 'Operating Revenue', 1.0),
                    ('total revenue', 'Total Revenue', 1.0),
                ],
                FinancialCategory.EXPENSES: [
                    ('cost of goods sold', 'Cost of Goods Sold', 1.0),
                    ('cost of sales', 'Cost of Sales', 1.0),
                    ('operating expenses', 'Operating Expenses', 1.0),
                    ('selling general administrative', 'Selling, General & Administrative', 1.0),
                    ('research development', 'Research & Development', 1.0),
                    ('depreciation', 'Depreciation', 1.0),
                    ('interest expense', 'Interest Expense', 1.0),
                ],
                FinancialCategory.PROFIT_LOSS: [
                    ('gross profit', 'Gross Profit', 1.0),
                    ('operating income', 'Operating Income', 1.0),
                    ('net income', 'Net Income', 1.0),
                    ('net loss', 'Net Loss', 1.0),
                    ('earnings before tax', 'Earnings Before Tax', 1.0),
                    ('ebitda', 'EBITDA', 1.0),
                ]
            }
        }
        
        # 통화 패턴
        self.currency_patterns = {
            LanguageCode.KOREAN: {
                '원': ('KRW', 1.0),
                'KRW': ('KRW', 1.0),
                '달러': ('USD', 0.9),
                '불': ('USD', 0.8),
                '$': ('USD', 1.0),
                '유로': ('EUR', 0.9),
                '€': ('EUR', 1.0),
                '엔': ('JPY', 0.9),
                '¥': ('JPY', 1.0),
                '위안': ('CNY', 0.9),
            },
            LanguageCode.ENGLISH: {
                'USD': ('USD', 1.0),
                '$': ('USD', 1.0),
                'dollar': ('USD', 0.9),
                'EUR': ('EUR', 1.0),
                '€': ('EUR', 1.0),
                'euro': ('EUR', 0.9),
                'GBP': ('GBP', 1.0),
                '£': ('GBP', 1.0),
                'pound': ('GBP', 0.9),
                'JPY': ('JPY', 1.0),
                '¥': ('JPY', 1.0),
                'yen': ('JPY', 0.9),
            }
        }
        
        # 금액 단위 패턴
        self.amount_units = {
            LanguageCode.KOREAN: {
                '천원': ('thousands', 1000, 1.0),
                '천': ('thousands', 1000, 0.9),
                'K': ('thousands', 1000, 0.8),
                '백만원': ('millions', 1000000, 1.0),
                '백만': ('millions', 1000000, 0.9),
                'M': ('millions', 1000000, 0.8),
                '십억원': ('billions', 1000000000, 1.0),
                '십억': ('billions', 1000000000, 0.9),
                'B': ('billions', 1000000000, 0.8),
                '조원': ('trillions', 1000000000000, 1.0),
                '조': ('trillions', 1000000000000, 0.9),
                'T': ('trillions', 1000000000000, 0.8),
            },
            LanguageCode.ENGLISH: {
                'thousand': ('thousands', 1000, 1.0),
                'K': ('thousands', 1000, 0.9),
                'million': ('millions', 1000000, 1.0),
                'M': ('millions', 1000000, 0.9),
                'billion': ('billions', 1000000000, 1.0),
                'B': ('billions', 1000000000, 0.9),
                'trillion': ('trillions', 1000000000000, 1.0),
                'T': ('trillions', 1000000000000, 0.9),
            }
        }
        
        # 금액 패턴 (정규표현식)
        self.amount_patterns = [
            # 기본 숫자 + 단위
            r'([\d,]+(?:\.\d{1,2})?)\s*([천백만십억조]?원|[KMBT]?(?:USD|EUR|GBP|JPY|원))',
            # 괄호 표시 (손실)
            r'\(\s*([\d,]+(?:\.\d{1,2})?)\s*([천백만십억조]?원|[KMBT]?(?:USD|EUR|GBP|JPY))\s*\)',
            # 통화 기호 + 숫자
            r'([$€£¥])\s*([\d,]+(?:\.\d{1,2})?)\s*([KMBT]?)',
            # 퍼센트
            r'([\d,]+(?:\.\d{1,2})?)\s*%',
        ]
        
        # 재무비율 패턴
        self.ratio_patterns = [
            r'(유동비율|부채비율|자기자본비율|ROA|ROE)\s*[:=]\s*([\d,]+(?:\.\d{1,2})?)\s*%?',
            r'(current ratio|debt ratio|equity ratio|roa|roe)\s*[:=]\s*([\d,]+(?:\.\d{1,2})?)\s*%?'
        ]
    
    def extract_financial_information(self, text: str, language: LanguageCode, 
                                    document_type: DocumentType = DocumentType.UNKNOWN) -> FinancialExtraction:
        """재무 정보 추출"""
        try:
            # 1. 재무 용어 추출
            terms = self._extract_financial_terms(text, language)
            
            # 2. 금액 정보 추출
            amounts = self._extract_amounts(text, language)
            
            # 3. 재무비율 추출
            ratios = self._extract_ratios(text, language)
            
            # 4. 요약 정보 생성
            summary = self._generate_summary(terms, amounts, ratios, document_type)
            
            # 5. 전체 신뢰도 계산
            confidence = self._calculate_extraction_confidence(terms, amounts, ratios)
            
            return FinancialExtraction(
                terms=terms,
                amounts=amounts,
                ratios=ratios,
                summary=summary,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Financial information extraction failed: {e}")
            return FinancialExtraction(
                terms=[],
                amounts=[],
                ratios=[],
                summary={},
                confidence=0.0
            )
    
    def _extract_financial_terms(self, text: str, language: LanguageCode) -> List[FinancialTerm]:
        """재무 용어 추출"""
        terms = []
        
        if language not in self.financial_terms:
            return terms
        
        text_lower = text.lower()
        
        for category, term_list in self.financial_terms[language].items():
            for term_pattern, normalized_term, confidence in term_list:
                pattern = re.escape(term_pattern.lower())
                matches = list(re.finditer(pattern, text_lower))
                
                for match in matches:
                    # 원본 텍스트에서 실제 표기 찾기
                    original_term = text[match.start():match.end()]
                    
                    terms.append(FinancialTerm(
                        term=original_term,
                        category=category,
                        language=language,
                        confidence=confidence,
                        position={'start': match.start(), 'end': match.end()},
                        normalized_term=normalized_term,
                        metadata={'pattern': term_pattern}
                    ))
        
        # 중복 제거 (같은 위치의 용어들)
        unique_terms = []
        positions_used = set()
        
        for term in sorted(terms, key=lambda x: x.confidence, reverse=True):
            pos_key = (term.position['start'], term.position['end'])
            if pos_key not in positions_used:
                unique_terms.append(term)
                positions_used.add(pos_key)
        
        return unique_terms
    
    def _extract_amounts(self, text: str, language: LanguageCode) -> List[FinancialAmount]:
        """금액 정보 추출"""
        amounts = []
        
        for pattern in self.amount_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            
            for match in matches:
                amount_info = self._parse_amount_match(match, text, language)
                if amount_info:
                    amounts.append(amount_info)
        
        return amounts
    
    def _parse_amount_match(self, match, text: str, language: LanguageCode) -> Optional[FinancialAmount]:
        """금액 매치 파싱"""
        try:
            groups = match.groups()
            raw_amount = match.group()
            
            # 숫자 부분 추출
            number_str = None
            currency = None
            unit = None
            
            if len(groups) >= 2:
                if groups[0].startswith(('$', '€', '£', '¥')):
                    # 통화 기호 + 숫자 패턴
                    currency_symbol = groups[0]
                    number_str = groups[1]
                    unit = groups[2] if len(groups) > 2 else ''
                    currency = self._resolve_currency(currency_symbol, language)
                else:
                    # 숫자 + 단위 패턴
                    number_str = groups[0]
                    unit_str = groups[1] if len(groups) > 1 else ''
                    currency = self._resolve_currency(unit_str, language)
                    unit = self._resolve_unit(unit_str, language)
            
            if not number_str:
                return None
            
            # 숫자 정규화
            normalized_amount = self._normalize_number(number_str)
            if normalized_amount is None:
                return None
            
            # 단위 적용
            if unit and language in self.amount_units:
                for unit_pattern, (unit_name, multiplier, confidence) in self.amount_units[language].items():
                    if unit_pattern in unit:
                        normalized_amount *= multiplier
                        break
            
            # 주변 컨텍스트 추출
            context_start = max(0, match.start() - 50)
            context_end = min(len(text), match.end() + 50)
            context = text[context_start:context_end].strip()
            
            return FinancialAmount(
                raw_amount=raw_amount,
                normalized_amount=normalized_amount,
                currency=currency or 'KRW',  # 기본 통화
                unit=unit or '',
                confidence=0.8,
                position={'start': match.start(), 'end': match.end()},
                context=context
            )
            
        except Exception as e:
            logger.error(f"Amount parsing failed: {e}")
            return None
    
    def _resolve_currency(self, currency_str: str, language: LanguageCode) -> Optional[str]:
        """통화 해결"""
        if not currency_str or language not in self.currency_patterns:
            return None
        
        currency_str = currency_str.strip()
        patterns = self.currency_patterns[language]
        
        for pattern, (currency_code, confidence) in patterns.items():
            if pattern in currency_str:
                return currency_code
        
        return None
    
    def _resolve_unit(self, unit_str: str, language: LanguageCode) -> Optional[str]:
        """단위 해결"""
        if not unit_str or language not in self.amount_units:
            return None
        
        units = self.amount_units[language]
        
        for pattern, (unit_name, multiplier, confidence) in units.items():
            if pattern in unit_str:
                return pattern
        
        return None
    
    def _normalize_number(self, number_str: str) -> Optional[float]:
        """숫자 정규화"""
        try:
            # 쉼표 제거
            clean_number = number_str.replace(',', '')
            
            # 숫자만 추출
            number_match = re.search(r'(\d+(?:\.\d{1,2})?)', clean_number)
            if number_match:
                return float(number_match.group(1))
            
            return None
        except ValueError:
            return None
    
    def _extract_ratios(self, text: str, language: LanguageCode) -> List[Dict[str, Any]]:
        """재무비율 추출"""
        ratios = []
        
        for pattern in self.ratio_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            
            for match in matches:
                ratio_name = match.group(1)
                ratio_value = match.group(2)
                
                try:
                    normalized_value = float(ratio_value.replace(',', ''))
                    
                    ratios.append({
                        'name': ratio_name,
                        'value': normalized_value,
                        'raw_value': ratio_value,
                        'confidence': 0.9,
                        'position': {'start': match.start(), 'end': match.end()},
                        'context': text[max(0, match.start()-30):match.end()+30]
                    })
                    
                except ValueError:
                    continue
        
        return ratios
    
    def _generate_summary(self, terms: List[FinancialTerm], amounts: List[FinancialAmount], 
                         ratios: List[Dict[str, Any]], document_type: DocumentType) -> Dict[str, Any]:
        """요약 정보 생성"""
        summary = {
            'total_terms': len(terms),
            'total_amounts': len(amounts),
            'total_ratios': len(ratios),
            'categories_found': [],
            'currencies_found': [],
            'amount_range': {},
            'document_type': document_type.value
        }
        
        # 카테고리별 통계
        category_counts = {}
        for term in terms:
            category = term.category.value
            category_counts[category] = category_counts.get(category, 0) + 1
        
        summary['categories_found'] = list(category_counts.keys())
        summary['category_counts'] = category_counts
        
        # 통화별 통계
        currency_amounts = {}
        for amount in amounts:
            currency = amount.currency
            if currency not in currency_amounts:
                currency_amounts[currency] = []
            currency_amounts[currency].append(amount.normalized_amount)
        
        summary['currencies_found'] = list(currency_amounts.keys())
        
        # 금액 범위
        for currency, amount_list in currency_amounts.items():
            if amount_list:
                summary['amount_range'][currency] = {
                    'min': min(amount_list),
                    'max': max(amount_list),
                    'count': len(amount_list),
                    'total': sum(amount_list)
                }
        
        # 주요 재무 지표 식별
        key_indicators = []
        for term in terms:
            if term.category in [FinancialCategory.PROFIT_LOSS, FinancialCategory.RATIOS]:
                key_indicators.append({
                    'term': term.normalized_term or term.term,
                    'category': term.category.value,
                    'confidence': term.confidence
                })
        
        summary['key_indicators'] = key_indicators
        
        return summary
    
    def _calculate_extraction_confidence(self, terms: List[FinancialTerm], 
                                       amounts: List[FinancialAmount], 
                                       ratios: List[Dict[str, Any]]) -> float:
        """추출 신뢰도 계산"""
        if not terms and not amounts and not ratios:
            return 0.0
        
        # 용어 신뢰도
        term_confidence = 0.0
        if terms:
            term_confidence = sum(term.confidence for term in terms) / len(terms)
        
        # 금액 신뢰도
        amount_confidence = 0.0
        if amounts:
            amount_confidence = sum(amount.confidence for amount in amounts) / len(amounts)
        
        # 비율 신뢰도
        ratio_confidence = 0.0
        if ratios:
            ratio_confidence = sum(ratio['confidence'] for ratio in ratios) / len(ratios)
        
        # 가중 평균
        weights = []
        confidences = []
        
        if terms:
            weights.append(len(terms))
            confidences.append(term_confidence)
        
        if amounts:
            weights.append(len(amounts) * 1.2)  # 금액에 약간 더 높은 가중치
            confidences.append(amount_confidence)
        
        if ratios:
            weights.append(len(ratios) * 1.1)  # 비율에 약간 더 높은 가중치
            confidences.append(ratio_confidence)
        
        if not weights:
            return 0.0
        
        weighted_sum = sum(w * c for w, c in zip(weights, confidences))
        total_weight = sum(weights)
        
        return weighted_sum / total_weight
    
    def get_financial_metrics(self, extraction: FinancialExtraction) -> Dict[str, Any]:
        """재무 메트릭 분석"""
        metrics = {
            'coverage_score': 0.0,
            'data_quality_score': 0.0,
            'completeness_score': 0.0,
            'consistency_score': 0.0
        }
        
        # 커버리지 점수 (다양한 카테고리 커버)
        unique_categories = set(term.category for term in extraction.terms)
        total_categories = len(FinancialCategory) - 1  # UNKNOWN 제외
        metrics['coverage_score'] = len(unique_categories) / total_categories
        
        # 데이터 품질 점수 (평균 신뢰도)
        all_confidences = [term.confidence for term in extraction.terms]
        all_confidences.extend([amount.confidence for amount in extraction.amounts])
        all_confidences.extend([ratio['confidence'] for ratio in extraction.ratios])
        
        if all_confidences:
            metrics['data_quality_score'] = sum(all_confidences) / len(all_confidences)
        
        # 완전성 점수 (용어, 금액, 비율 모두 있는가)
        completeness_factors = [
            1.0 if extraction.terms else 0.0,
            1.0 if extraction.amounts else 0.0,
            1.0 if extraction.ratios else 0.0
        ]
        metrics['completeness_score'] = sum(completeness_factors) / len(completeness_factors)
        
        # 일관성 점수 (금액과 용어가 매칭되는가)
        consistency_count = 0
        total_checks = 0
        
        for amount in extraction.amounts:
            total_checks += 1
            # 주변 컨텍스트에서 재무 용어 찾기
            context_lower = amount.context.lower()
            for term in extraction.terms:
                if term.term.lower() in context_lower:
                    consistency_count += 1
                    break
        
        if total_checks > 0:
            metrics['consistency_score'] = consistency_count / total_checks
        
        return metrics
    
    def validate_financial_data(self, extraction: FinancialExtraction) -> Dict[str, Any]:
        """재무 데이터 검증"""
        validation = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'recommendations': []
        }
        
        # 기본 검증
        if not extraction.terms and not extraction.amounts:
            validation['is_valid'] = False
            validation['errors'].append("No financial terms or amounts found")
        
        # 금액 일관성 검증
        currency_counts = {}
        for amount in extraction.amounts:
            currency = amount.currency
            currency_counts[currency] = currency_counts.get(currency, 0) + 1
        
        if len(currency_counts) > 2:
            validation['warnings'].append(f"Multiple currencies found: {list(currency_counts.keys())}")
        
        # 이상치 검증
        for currency, amounts_list in extraction.summary.get('amount_range', {}).items():
            if amounts_list.get('max', 0) > amounts_list.get('min', 0) * 1000:
                validation['warnings'].append(f"Large amount variance in {currency}")
        
        # 추천사항
        if extraction.confidence < 0.7:
            validation['recommendations'].append("Consider manual review due to low confidence")
        
        if not extraction.ratios:
            validation['recommendations'].append("No financial ratios detected - consider adding ratio analysis")
        
        return validation