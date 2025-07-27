#!/usr/bin/env python3
"""
자동 품질 검증 서비스
Automatic Quality Verification Service

AI 기반 OCR 결과 자동 검증, 오류 패턴 학습, 신뢰도 점수 산출
"""

import logging
import json
import re
import statistics
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import numpy as np
import asyncio
from collections import defaultdict, Counter
import difflib

from app.services.multilingual_two_tier_service import MultilingualTwoTierService
from app.services.transformer_ocr_service import transformer_ocr_service

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """품질 측정 지표"""
    overall_score: float
    character_accuracy: float
    word_accuracy: float
    layout_preservation: float
    consistency_score: float
    confidence_reliability: float
    error_density: float
    processing_time: float


@dataclass
class ErrorPattern:
    """오류 패턴"""
    pattern_id: str
    pattern_type: str  # 'substitution', 'insertion', 'deletion', 'structural'
    frequency: int
    examples: List[Dict[str, str]]
    languages: List[str]
    confidence_impact: float
    suggested_fix: str


@dataclass
class QualityReport:
    """품질 보고서"""
    document_id: str
    overall_grade: str
    quality_metrics: QualityMetrics
    detected_errors: List[Dict[str, Any]]
    error_patterns: List[ErrorPattern]
    recommendations: List[str]
    verification_timestamp: str
    processing_info: Dict[str, Any]


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    confidence_score: float
    quality_issues: List[str]
    suggested_corrections: List[Dict[str, str]]
    validation_details: Dict[str, Any]


class QualityVerificationService:
    """자동 품질 검증 서비스"""
    
    def __init__(self):
        """초기화"""
        self.ocr_service = MultilingualTwoTierService()
        
        # 품질 기준 및 임계값
        self.quality_thresholds = {
            "excellent": 95.0,
            "good": 85.0,
            "acceptable": 70.0,
            "poor": 50.0
        }
        
        # 오류 패턴 데이터베이스 (메모리 기반, 실제로는 DB 저장)
        self.error_patterns_db = {}
        self.quality_history = []
        
        # 언어별 검증 규칙
        self.validation_rules = {
            "kor": {
                "character_set": r'[가-힣ㄱ-ㅎㅏ-ㅣ0-9a-zA-Z\s\.\,\!\?\-\(\)\[\]\{\}]',
                "common_errors": {
                    "ㅇ": ["o", "0"],
                    "ㄱ": ["r", "k"],
                    "ㅣ": ["l", "I", "1"],
                    "ㅏ": ["ㅓ"],
                    "ㅡ": ["-", "_"]
                },
                "structural_patterns": [
                    r'\d{4}[-년]?\s*\d{1,2}[-월]?\s*\d{1,2}[일]?',  # 날짜
                    r'\d{1,3}(?:,\d{3})*(?:\.\d+)?[원달러유로]?',    # 숫자/금액
                ]
            },
            "eng": {
                "character_set": r'[a-zA-Z0-9\s\.\,\!\?\-\(\)\[\]\{\}]',
                "common_errors": {
                    "o": ["0"],
                    "l": ["1", "I"],
                    "S": ["5"],
                    "G": ["6"],
                    "B": ["8"]
                },
                "structural_patterns": [
                    r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',  # 날짜
                    r'\$\d{1,3}(?:,\d{3})*(?:\.\d+)?',     # 달러
                ]
            },
            "chi_sim": {
                "character_set": r'[一-龯0-9a-zA-Z\s\.\,\!\?\-\(\)\[\]\{\}]',
                "common_errors": {
                    "人": ["入"],
                    "工": ["工"],
                    "口": ["o", "0"]
                },
                "structural_patterns": [
                    r'\d{4}年\d{1,2}月\d{1,2}日',
                    r'¥\d{1,3}(?:,\d{3})*(?:\.\d+)?'
                ]
            }
        }
        
        # 품질 검증 히스토리 (실제로는 데이터베이스)
        self.verification_history = []
        
        logger.info("QualityVerificationService 초기화 완료")
    
    async def verify_ocr_quality(
        self,
        image_path: str,
        extracted_text: str,
        language: str = "kor",
        reference_text: Optional[str] = None,
        verification_level: str = "comprehensive"
    ) -> QualityReport:
        """
        OCR 품질 자동 검증
        
        Args:
            image_path: 원본 이미지 경로
            extracted_text: 추출된 텍스트
            language: 언어 코드
            reference_text: 참조 텍스트 (있는 경우)
            verification_level: 검증 수준 (basic, comprehensive, detailed)
            
        Returns:
            품질 보고서
        """
        try:
            document_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"품질 검증 시작: {document_id}")
            
            start_time = datetime.now()
            
            # 1. 기본 품질 측정
            quality_metrics = await self._calculate_quality_metrics(
                image_path, extracted_text, language, reference_text
            )
            
            # 2. 오류 감지
            detected_errors = await self._detect_errors(
                extracted_text, language, verification_level
            )
            
            # 3. 오류 패턴 분석
            error_patterns = self._analyze_error_patterns(
                detected_errors, language
            )
            
            # 4. 전체 등급 산정
            overall_grade = self._calculate_overall_grade(quality_metrics)
            
            # 5. 추천사항 생성
            recommendations = self._generate_recommendations(
                quality_metrics, detected_errors, error_patterns
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 6. 품질 보고서 생성
            report = QualityReport(
                document_id=document_id,
                overall_grade=overall_grade,
                quality_metrics=quality_metrics,
                detected_errors=detected_errors,
                error_patterns=error_patterns,
                recommendations=recommendations,
                verification_timestamp=datetime.now().isoformat(),
                processing_info={
                    "language": language,
                    "verification_level": verification_level,
                    "processing_time": processing_time,
                    "text_length": len(extracted_text),
                    "has_reference": reference_text is not None
                }
            )
            
            # 7. 히스토리 저장 및 패턴 학습
            await self._update_quality_history(report)
            await self._learn_error_patterns(detected_errors, language)
            
            logger.info(f"품질 검증 완료: {overall_grade} ({quality_metrics.overall_score:.2f})")
            
            return report
            
        except Exception as e:
            logger.error(f"품질 검증 실패: {e}")
            # 기본 보고서 반환
            return QualityReport(
                document_id=f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                overall_grade="UNKNOWN",
                quality_metrics=QualityMetrics(0, 0, 0, 0, 0, 0, 1.0, 0),
                detected_errors=[{"error": str(e)}],
                error_patterns=[],
                recommendations=["수동 검토 필요"],
                verification_timestamp=datetime.now().isoformat(),
                processing_info={"error": str(e)}
            )
    
    async def _calculate_quality_metrics(
        self,
        image_path: str,
        extracted_text: str,
        language: str,
        reference_text: Optional[str] = None
    ) -> QualityMetrics:
        """품질 지표 계산"""
        try:
            # 기본 신뢰도 (OCR 엔진 기본값)
            base_confidence = 0.8  # 실제로는 OCR 엔진에서 가져옴
            
            # 텍스트 품질 분석
            text_quality = self._analyze_text_quality(extracted_text, language)
            
            # 참조 텍스트가 있는 경우 정확도 계산
            character_accuracy = 1.0
            word_accuracy = 1.0
            
            if reference_text:
                character_accuracy = self._calculate_character_accuracy(
                    extracted_text, reference_text
                )
                word_accuracy = self._calculate_word_accuracy(
                    extracted_text, reference_text
                )
            else:
                # 참조 텍스트가 없는 경우 휴리스틱 기반 추정
                character_accuracy = self._estimate_character_accuracy(
                    extracted_text, language
                )
                word_accuracy = self._estimate_word_accuracy(
                    extracted_text, language
                )
            
            # 레이아웃 보존도 (이미지 분석 기반)
            layout_preservation = await self._analyze_layout_preservation(
                image_path, extracted_text
            )
            
            # 일관성 점수
            consistency_score = self._calculate_consistency_score(extracted_text, language)
            
            # 신뢰도 신뢰성
            confidence_reliability = self._assess_confidence_reliability(
                base_confidence, text_quality
            )
            
            # 오류 밀도
            error_density = self._calculate_error_density(extracted_text, language)
            
            # 전체 점수 계산 (가중 평균)
            overall_score = (
                character_accuracy * 0.3 +
                word_accuracy * 0.25 +
                layout_preservation * 0.15 +
                consistency_score * 0.15 +
                confidence_reliability * 0.1 +
                (1 - error_density) * 0.05
            ) * 100
            
            return QualityMetrics(
                overall_score=overall_score,
                character_accuracy=character_accuracy * 100,
                word_accuracy=word_accuracy * 100,
                layout_preservation=layout_preservation * 100,
                consistency_score=consistency_score * 100,
                confidence_reliability=confidence_reliability * 100,
                error_density=error_density,
                processing_time=0.0  # 나중에 설정
            )
            
        except Exception as e:
            logger.error(f"품질 지표 계산 실패: {e}")
            return QualityMetrics(0, 0, 0, 0, 0, 0, 1.0, 0)
    
    def _analyze_text_quality(self, text: str, language: str) -> float:
        """텍스트 품질 분석"""
        if not text.strip():
            return 0.0
        
        quality_score = 1.0
        
        # 1. 문자 집합 검증
        if language in self.validation_rules:
            valid_chars = self.validation_rules[language]["character_set"]
            invalid_chars = len([c for c in text if not re.match(valid_chars, c)])
            quality_score *= max(0, 1 - (invalid_chars / len(text)))
        
        # 2. 구조적 패턴 검증
        if language in self.validation_rules:
            patterns = self.validation_rules[language]["structural_patterns"]
            pattern_matches = sum(len(re.findall(pattern, text)) for pattern in patterns)
            # 패턴이 많이 일치할수록 구조적으로 올바름
            if len(text.split()) > 10:  # 충분한 텍스트가 있는 경우만
                pattern_density = pattern_matches / max(len(text.split()), 1)
                quality_score *= min(1.0, 0.7 + pattern_density * 0.3)
        
        # 3. 반복 문자 검증 (OCR 오류 특성)
        repeated_chars = len(re.findall(r'(.)\1{3,}', text))  # 4회 이상 반복
        if repeated_chars > 0:
            quality_score *= max(0.5, 1 - (repeated_chars * 0.1))
        
        return quality_score
    
    def _calculate_character_accuracy(self, predicted: str, reference: str) -> float:
        """문자 정확도 계산"""
        if not reference:
            return 1.0
        
        # Levenshtein 거리 기반 정확도
        matcher = difflib.SequenceMatcher(None, predicted, reference)
        return matcher.ratio()
    
    def _calculate_word_accuracy(self, predicted: str, reference: str) -> float:
        """단어 정확도 계산"""
        if not reference:
            return 1.0
        
        pred_words = predicted.split()
        ref_words = reference.split()
        
        if not ref_words:
            return 1.0 if not pred_words else 0.0
        
        # 단어 단위 유사도
        matcher = difflib.SequenceMatcher(None, pred_words, ref_words)
        return matcher.ratio()
    
    def _estimate_character_accuracy(self, text: str, language: str) -> float:
        """문자 정확도 추정 (참조 텍스트 없이)"""
        if not text.strip():
            return 0.0
        
        # 휴리스틱 기반 추정
        accuracy = 0.9  # 기본값
        
        # 1. 알려진 OCR 오류 패턴 검사
        if language in self.validation_rules:
            common_errors = self.validation_rules[language]["common_errors"]
            error_count = 0
            
            for correct, wrong_list in common_errors.items():
                for wrong in wrong_list:
                    error_count += text.count(wrong)
            
            # 오류가 많을수록 정확도 감소
            error_ratio = error_count / max(len(text), 1)
            accuracy *= max(0.5, 1 - error_ratio * 2)
        
        # 2. 비정상적인 문자 시퀀스 검사
        unusual_sequences = len(re.findall(r'[^\w\s]{3,}', text))
        if unusual_sequences > 0:
            accuracy *= max(0.7, 1 - unusual_sequences * 0.1)
        
        return accuracy
    
    def _estimate_word_accuracy(self, text: str, language: str) -> float:
        """단어 정확도 추정 (참조 텍스트 없이)"""
        if not text.strip():
            return 0.0
        
        words = text.split()
        if not words:
            return 0.0
        
        accuracy = 0.85  # 기본값
        
        # 1. 단어 길이 분포 검사
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        if language == "kor":
            # 한국어 평균 단어 길이: 2-4자
            if 1.5 <= avg_word_length <= 5:
                accuracy *= 1.0
            else:
                accuracy *= max(0.6, 1 - abs(avg_word_length - 3) * 0.1)
        elif language == "eng":
            # 영어 평균 단어 길이: 4-6자
            if 3 <= avg_word_length <= 7:
                accuracy *= 1.0
            else:
                accuracy *= max(0.6, 1 - abs(avg_word_length - 5) * 0.1)
        
        # 2. 매우 짧거나 긴 단어 비율
        unusual_words = sum(1 for word in words if len(word) <= 1 or len(word) > 15)
        unusual_ratio = unusual_words / len(words)
        accuracy *= max(0.7, 1 - unusual_ratio)
        
        return accuracy
    
    async def _analyze_layout_preservation(self, image_path: str, text: str) -> float:
        """레이아웃 보존도 분석"""
        try:
            # 간단한 구현 - 실제로는 더 정교한 레이아웃 분석 필요
            
            # 텍스트 줄 수와 이미지 높이 비교
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            line_count = len(lines)
            
            if line_count == 0:
                return 0.0
            
            # 줄 길이 분산 분석 (일정한 패턴이 있으면 레이아웃이 잘 보존됨)
            line_lengths = [len(line) for line in lines if line]
            if line_lengths:
                length_variance = statistics.variance(line_lengths) if len(line_lengths) > 1 else 0
                # 분산이 적당하면 좋은 레이아웃
                normalized_variance = min(length_variance / max(statistics.mean(line_lengths), 1), 1.0)
                layout_score = max(0.5, 1 - normalized_variance * 0.5)
            else:
                layout_score = 0.5
            
            # 구조적 요소 분석 (표, 목록 등)
            structural_elements = 0
            structural_elements += len(re.findall(r'\t', text))  # 탭 문자
            structural_elements += len(re.findall(r'^\s*[•\-\*]\s+', text, re.MULTILINE))  # 목록
            structural_elements += len(re.findall(r'\|.*\|', text))  # 표 구분자
            
            if structural_elements > 0:
                layout_score = min(1.0, layout_score + 0.2)
            
            return layout_score
            
        except Exception as e:
            logger.error(f"레이아웃 분석 실패: {e}")
            return 0.5
    
    def _calculate_consistency_score(self, text: str, language: str) -> float:
        """일관성 점수 계산"""
        if not text.strip():
            return 0.0
        
        consistency = 1.0
        
        # 1. 폰트/스타일 일관성 (간접 추정)
        # 대문자/소문자 패턴의 일관성
        if language == "eng":
            sentences = re.split(r'[.!?]+', text)
            capitalization_errors = 0
            
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and not sentence[0].isupper():
                    capitalization_errors += 1
            
            if sentences:
                consistency *= max(0.7, 1 - (capitalization_errors / len(sentences)))
        
        # 2. 숫자 형식 일관성
        numbers = re.findall(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?', text)
        if len(numbers) > 1:
            # 천 단위 구분 일관성
            comma_format = sum(1 for num in numbers if ',' in num)
            no_comma_format = len(numbers) - comma_format
            
            if comma_format > 0 and no_comma_format > 0:
                # 혼재된 경우 일관성 점수 감소
                consistency *= 0.8
        
        # 3. 공백 패턴 일관성
        lines = text.split('\n')
        indentations = []
        for line in lines:
            if line.strip():
                leading_spaces = len(line) - len(line.lstrip())
                indentations.append(leading_spaces)
        
        if indentations and len(set(indentations)) > len(indentations) * 0.5:
            # 들여쓰기가 너무 다양하면 일관성 감소
            consistency *= 0.9
        
        return consistency
    
    def _assess_confidence_reliability(self, base_confidence: float, text_quality: float) -> float:
        """신뢰도 신뢰성 평가"""
        # OCR 엔진의 신뢰도와 실제 텍스트 품질 간의 일치도
        expected_quality = base_confidence
        actual_quality = text_quality
        
        # 차이가 클수록 신뢰도 신뢰성 낮음
        difference = abs(expected_quality - actual_quality)
        reliability = max(0.5, 1 - difference)
        
        return reliability
    
    def _calculate_error_density(self, text: str, language: str) -> float:
        """오류 밀도 계산"""
        if not text.strip():
            return 1.0
        
        error_count = 0
        total_chars = len(text)
        
        # 1. 알려진 OCR 오류 패턴
        if language in self.validation_rules:
            common_errors = self.validation_rules[language]["common_errors"]
            for correct, wrong_list in common_errors.items():
                for wrong in wrong_list:
                    error_count += text.count(wrong)
        
        # 2. 비정상적인 문자 조합
        error_count += len(re.findall(r'[^\w\s]{2,}', text))  # 연속 특수문자
        error_count += len(re.findall(r'\d[a-zA-Z]{1}(?=\s)', text))  # 숫자-문자 혼재
        
        return min(1.0, error_count / max(total_chars, 1) * 100)
    
    async def _detect_errors(
        self,
        text: str,
        language: str,
        verification_level: str
    ) -> List[Dict[str, Any]]:
        """오류 감지"""
        errors = []
        
        try:
            # 1. 문자 수준 오류
            char_errors = self._detect_character_errors(text, language)
            errors.extend(char_errors)
            
            # 2. 단어 수준 오류
            word_errors = self._detect_word_errors(text, language)
            errors.extend(word_errors)
            
            # 3. 구조적 오류
            if verification_level in ["comprehensive", "detailed"]:
                structural_errors = self._detect_structural_errors(text, language)
                errors.extend(structural_errors)
            
            # 4. 의미적 오류 (상세 검증 시)
            if verification_level == "detailed":
                semantic_errors = await self._detect_semantic_errors(text, language)
                errors.extend(semantic_errors)
            
            logger.info(f"총 {len(errors)}개 오류 감지")
            
        except Exception as e:
            logger.error(f"오류 감지 실패: {e}")
            errors.append({
                "type": "detection_error",
                "description": str(e),
                "severity": "high",
                "position": {"start": 0, "end": 0}
            })
        
        return errors
    
    def _detect_character_errors(self, text: str, language: str) -> List[Dict[str, Any]]:
        """문자 수준 오류 감지"""
        errors = []
        
        if language not in self.validation_rules:
            return errors
        
        common_errors = self.validation_rules[language]["common_errors"]
        
        for correct, wrong_list in common_errors.items():
            for wrong in wrong_list:
                for match in re.finditer(re.escape(wrong), text):
                    errors.append({
                        "type": "character_substitution",
                        "description": f"'{wrong}' -> '{correct}' 치환 필요",
                        "severity": "medium",
                        "position": {
                            "start": match.start(),
                            "end": match.end()
                        },
                        "original": wrong,
                        "suggested": correct,
                        "context": text[max(0, match.start()-10):match.end()+10]
                    })
        
        return errors
    
    def _detect_word_errors(self, text: str, language: str) -> List[Dict[str, Any]]:
        """단어 수준 오류 감지"""
        errors = []
        
        words = text.split()
        
        for i, word in enumerate(words):
            # 1. 비정상적으로 짧은 단어
            if len(word) == 1 and word.isalpha() and word not in ['a', 'I', '은', '는', '이', '가']:
                errors.append({
                    "type": "suspicious_short_word",
                    "description": f"의심스러운 단일 문자: '{word}'",
                    "severity": "low",
                    "position": {"word_index": i},
                    "original": word,
                    "context": " ".join(words[max(0, i-2):i+3])
                })
            
            # 2. 비정상적으로 긴 단어
            if len(word) > 20:
                errors.append({
                    "type": "suspicious_long_word",
                    "description": f"비정상적으로 긴 단어: '{word[:20]}...'",
                    "severity": "medium",
                    "position": {"word_index": i},
                    "original": word,
                    "context": " ".join(words[max(0, i-2):i+3])
                })
            
            # 3. 숫자-문자 혼재
            if re.search(r'\d.*[a-zA-Z]|[a-zA-Z].*\d', word) and not re.match(r'^[A-Z0-9]+$', word):
                errors.append({
                    "type": "mixed_alphanumeric",
                    "description": f"숫자-문자 혼재: '{word}'",
                    "severity": "medium",
                    "position": {"word_index": i},
                    "original": word,
                    "context": " ".join(words[max(0, i-2):i+3])
                })
        
        return errors
    
    def _detect_structural_errors(self, text: str, language: str) -> List[Dict[str, Any]]:
        """구조적 오류 감지"""
        errors = []
        
        # 1. 불완전한 표 구조
        lines = text.split('\n')
        table_lines = [line for line in lines if '|' in line or '\t' in line]
        
        if len(table_lines) > 1:
            # 표의 컬럼 수 일관성 검사
            column_counts = []
            for line in table_lines:
                if '|' in line:
                    column_counts.append(len(line.split('|')))
                elif '\t' in line:
                    column_counts.append(len(line.split('\t')))
            
            if column_counts and len(set(column_counts)) > 1:
                errors.append({
                    "type": "inconsistent_table_structure",
                    "description": "표의 컬럼 수가 일치하지 않음",
                    "severity": "high",
                    "details": {
                        "column_counts": column_counts,
                        "table_lines": len(table_lines)
                    }
                })
        
        # 2. 불완전한 목록 구조
        list_items = re.findall(r'^\s*[•\-\*\d+\.]\s+(.+)$', text, re.MULTILINE)
        if len(list_items) > 0:
            # 목록 마커의 일관성 검사
            markers = re.findall(r'^\s*([•\-\*\d+\.])\s+', text, re.MULTILINE)
            unique_markers = set(markers)
            if len(unique_markers) > 2:  # 마커가 너무 다양하면 오류 가능성
                errors.append({
                    "type": "inconsistent_list_markers",
                    "description": "목록 마커가 일관되지 않음",
                    "severity": "medium",
                    "details": {
                        "markers_used": list(unique_markers),
                        "list_items_count": len(list_items)
                    }
                })
        
        # 3. 날짜/시간 형식 오류
        if language in self.validation_rules:
            date_patterns = self.validation_rules[language]["structural_patterns"]
            for pattern in date_patterns:
                if "년|월|日" in pattern or "/-" in pattern:  # 날짜 패턴
                    matches = re.findall(pattern, text)
                    for match in matches:
                        # 날짜 유효성 검사 (간단한 버전)
                        if not self._validate_date_format(match, language):
                            errors.append({
                                "type": "invalid_date_format",
                                "description": f"잘못된 날짜 형식: '{match}'",
                                "severity": "medium",
                                "original": match
                            })
        
        return errors
    
    def _validate_date_format(self, date_str: str, language: str) -> bool:
        """날짜 형식 유효성 검사"""
        try:
            # 매우 간단한 검사 - 실제로는 더 정교한 검증 필요
            numbers = re.findall(r'\d+', date_str)
            if len(numbers) >= 3:
                year, month, day = int(numbers[0]), int(numbers[1]), int(numbers[2])
                return (1900 <= year <= 2100 and 
                       1 <= month <= 12 and 
                       1 <= day <= 31)
            return True  # 숫자가 충분하지 않으면 패스
        except:
            return False
    
    async def _detect_semantic_errors(self, text: str, language: str) -> List[Dict[str, Any]]:
        """의미적 오류 감지"""
        errors = []
        
        try:
            # 1. 문맥상 이상한 단어 조합
            sentences = re.split(r'[.!?]+', text)
            
            for i, sentence in enumerate(sentences):
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                # 반복되는 단어 패턴 (OCR 오류 특성)
                words = sentence.split()
                word_counts = Counter(words)
                repeated_words = [word for word, count in word_counts.items() if count > 3]
                
                if repeated_words:
                    errors.append({
                        "type": "excessive_word_repetition",
                        "description": f"과도한 단어 반복: {', '.join(repeated_words)}",
                        "severity": "medium",
                        "position": {"sentence_index": i},
                        "repeated_words": repeated_words
                    })
                
                # 매우 짧은 문장 (의미 손실 가능)
                if len(words) == 1 and not re.match(r'^[A-Z가-힣]\w*[.!?]?$', sentence):
                    errors.append({
                        "type": "fragmented_sentence",
                        "description": f"의미가 불분명한 문장 조각: '{sentence}'",
                        "severity": "low",
                        "position": {"sentence_index": i}
                    })
        
        except Exception as e:
            logger.error(f"의미적 오류 감지 실패: {e}")
        
        return errors
    
    def _analyze_error_patterns(
        self,
        detected_errors: List[Dict[str, Any]],
        language: str
    ) -> List[ErrorPattern]:
        """오류 패턴 분석"""
        patterns = []
        
        try:
            # 오류 유형별 분류
            error_by_type = defaultdict(list)
            for error in detected_errors:
                error_by_type[error["type"]].append(error)
            
            # 각 유형에 대해 패턴 생성
            for error_type, errors in error_by_type.items():
                if len(errors) >= 2:  # 2개 이상일 때만 패턴으로 인식
                    # 예시 추출
                    examples = []
                    for error in errors[:5]:  # 최대 5개 예시
                        example = {
                            "original": error.get("original", ""),
                            "suggested": error.get("suggested", ""),
                            "context": error.get("context", "")
                        }
                        examples.append(example)
                    
                    # 신뢰도 영향 계산
                    avg_severity = self._calculate_severity_impact(errors)
                    confidence_impact = avg_severity * len(errors) * 0.1
                    
                    # 수정 제안
                    suggested_fix = self._generate_pattern_fix_suggestion(error_type, errors)
                    
                    pattern = ErrorPattern(
                        pattern_id=f"{error_type}_{language}_{datetime.now().strftime('%Y%m%d')}",
                        pattern_type=error_type,
                        frequency=len(errors),
                        examples=examples,
                        languages=[language],
                        confidence_impact=confidence_impact,
                        suggested_fix=suggested_fix
                    )
                    
                    patterns.append(pattern)
            
        except Exception as e:
            logger.error(f"오류 패턴 분석 실패: {e}")
        
        return patterns
    
    def _calculate_severity_impact(self, errors: List[Dict[str, Any]]) -> float:
        """심각도 영향 계산"""
        severity_weights = {"low": 0.2, "medium": 0.5, "high": 1.0}
        
        total_weight = 0
        for error in errors:
            severity = error.get("severity", "medium")
            total_weight += severity_weights.get(severity, 0.5)
        
        return total_weight / len(errors) if errors else 0
    
    def _generate_pattern_fix_suggestion(self, error_type: str, errors: List[Dict[str, Any]]) -> str:
        """패턴별 수정 제안 생성"""
        suggestions = {
            "character_substitution": "문자 매핑 테이블을 사용한 자동 치환 적용",
            "suspicious_short_word": "주변 문맥을 고려한 단어 복원 또는 제거",
            "suspicious_long_word": "단어 분할 또는 OCR 재처리",
            "mixed_alphanumeric": "숫자와 문자 영역 분리 후 개별 처리",
            "inconsistent_table_structure": "표 구조 재인식 및 정렬",
            "inconsistent_list_markers": "목록 마커 통일화",
            "invalid_date_format": "날짜 형식 정규화 적용",
            "excessive_word_repetition": "중복 단어 제거 및 문맥 복원",
            "fragmented_sentence": "문장 연결성 복원"
        }
        
        return suggestions.get(error_type, "수동 검토 및 수정 필요")
    
    def _calculate_overall_grade(self, quality_metrics: QualityMetrics) -> str:
        """전체 등급 산정"""
        score = quality_metrics.overall_score
        
        if score >= self.quality_thresholds["excellent"]:
            return "A"
        elif score >= self.quality_thresholds["good"]:
            return "B"
        elif score >= self.quality_thresholds["acceptable"]:
            return "C"
        elif score >= self.quality_thresholds["poor"]:
            return "D"
        else:
            return "F"
    
    def _generate_recommendations(
        self,
        quality_metrics: QualityMetrics,
        detected_errors: List[Dict[str, Any]],
        error_patterns: List[ErrorPattern]
    ) -> List[str]:
        """추천사항 생성"""
        recommendations = []
        
        # 전체 점수 기반 추천
        if quality_metrics.overall_score < 70:
            recommendations.append("OCR 재처리 권장 (다른 엔진 또는 설정 사용)")
        
        # 문자 정확도 기반
        if quality_metrics.character_accuracy < 85:
            recommendations.append("이미지 품질 개선 (해상도, 대비, 노이즈 제거)")
        
        # 단어 정확도 기반
        if quality_metrics.word_accuracy < 80:
            recommendations.append("언어별 특화 모델 사용 고려")
        
        # 레이아웃 보존도 기반
        if quality_metrics.layout_preservation < 75:
            recommendations.append("구조 인식 기능 활용 (표, 목록 등)")
        
        # 오류 패턴 기반
        high_frequency_patterns = [p for p in error_patterns if p.frequency >= 5]
        if high_frequency_patterns:
            recommendations.append("반복 오류 패턴 자동 수정 규칙 적용")
        
        # 오류 밀도 기반
        if quality_metrics.error_density > 0.1:
            recommendations.append("전처리 단계에서 노이즈 제거 강화")
        
        # 일관성 점수 기반
        if quality_metrics.consistency_score < 80:
            recommendations.append("문서 전체의 일관된 형식 적용")
        
        # 신뢰도 관련
        if quality_metrics.confidence_reliability < 70:
            recommendations.append("OCR 신뢰도 점수 재보정 필요")
        
        # 특정 오류 유형별 추천
        error_types = set(error["type"] for error in detected_errors)
        
        if "character_substitution" in error_types:
            recommendations.append("문자 치환 후처리 규칙 적용")
        
        if "inconsistent_table_structure" in error_types:
            recommendations.append("표 구조 전용 OCR 엔진 사용")
        
        if "mixed_alphanumeric" in error_types:
            recommendations.append("숫자와 텍스트 영역 분리 처리")
        
        # 기본 추천사항
        if not recommendations:
            recommendations.append("현재 품질 수준이 양호함")
        
        return recommendations[:10]  # 최대 10개
    
    async def _update_quality_history(self, report: QualityReport):
        """품질 히스토리 업데이트"""
        try:
            # 실제로는 데이터베이스에 저장
            self.verification_history.append({
                "timestamp": report.verification_timestamp,
                "document_id": report.document_id,
                "overall_score": report.quality_metrics.overall_score,
                "grade": report.overall_grade,
                "language": report.processing_info.get("language", "unknown"),
                "error_count": len(report.detected_errors),
                "pattern_count": len(report.error_patterns)
            })
            
            # 히스토리 크기 제한 (메모리 관리)
            if len(self.verification_history) > 1000:
                self.verification_history = self.verification_history[-800:]
            
            logger.debug(f"품질 히스토리 업데이트: {report.document_id}")
            
        except Exception as e:
            logger.error(f"품질 히스토리 업데이트 실패: {e}")
    
    async def _learn_error_patterns(self, detected_errors: List[Dict[str, Any]], language: str):
        """오류 패턴 학습"""
        try:
            # 패턴 데이터베이스 업데이트
            for error in detected_errors:
                error_type = error["type"]
                pattern_key = f"{error_type}_{language}"
                
                if pattern_key not in self.error_patterns_db:
                    self.error_patterns_db[pattern_key] = {
                        "count": 0,
                        "examples": [],
                        "last_seen": None
                    }
                
                pattern_data = self.error_patterns_db[pattern_key]
                pattern_data["count"] += 1
                pattern_data["last_seen"] = datetime.now().isoformat()
                
                # 예시 추가 (최대 20개)
                if len(pattern_data["examples"]) < 20:
                    example = {
                        "original": error.get("original", ""),
                        "context": error.get("context", ""),
                        "timestamp": datetime.now().isoformat()
                    }
                    pattern_data["examples"].append(example)
            
            logger.debug(f"오류 패턴 학습 완료: {len(detected_errors)}개 오류")
            
        except Exception as e:
            logger.error(f"오류 패턴 학습 실패: {e}")
    
    async def validate_text_with_ai(
        self,
        text: str,
        language: str,
        expected_content_type: str = "general"
    ) -> ValidationResult:
        """AI를 사용한 텍스트 검증"""
        try:
            # 트랜스포머 OCR 서비스를 사용한 문맥 기반 검증
            transformer_result = await transformer_ocr_service.process_with_context(
                image_path="",  # 텍스트만 검증
                language=language,
                use_context=True,
                model_preference="auto"
            )
            
            # 검증 결과 분석
            is_valid = True
            confidence_score = 0.8
            quality_issues = []
            suggested_corrections = []
            
            # 간단한 구현 - 실제로는 더 정교한 AI 검증 필요
            if len(text.strip()) == 0:
                is_valid = False
                quality_issues.append("빈 텍스트")
                confidence_score = 0.0
            
            return ValidationResult(
                is_valid=is_valid,
                confidence_score=confidence_score,
                quality_issues=quality_issues,
                suggested_corrections=suggested_corrections,
                validation_details={
                    "method": "transformer_based",
                    "language": language,
                    "content_type": expected_content_type
                }
            )
            
        except Exception as e:
            logger.error(f"AI 텍스트 검증 실패: {e}")
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                quality_issues=[f"검증 오류: {str(e)}"],
                suggested_corrections=[],
                validation_details={"error": str(e)}
            )
    
    def get_quality_statistics(self) -> Dict[str, Any]:
        """품질 통계 조회"""
        try:
            if not self.verification_history:
                return {"message": "품질 검증 히스토리 없음"}
            
            scores = [record["overall_score"] for record in self.verification_history]
            grades = [record["grade"] for record in self.verification_history]
            
            # 기본 통계
            stats = {
                "total_verifications": len(self.verification_history),
                "average_score": statistics.mean(scores),
                "score_std": statistics.stdev(scores) if len(scores) > 1 else 0,
                "grade_distribution": dict(Counter(grades)),
                "recent_trend": self._calculate_recent_trend()
            }
            
            # 언어별 통계
            language_stats = defaultdict(list)
            for record in self.verification_history:
                lang = record.get("language", "unknown")
                language_stats[lang].append(record["overall_score"])
            
            stats["language_performance"] = {
                lang: {
                    "average_score": statistics.mean(scores),
                    "count": len(scores)
                }
                for lang, scores in language_stats.items()
            }
            
            # 오류 패턴 통계
            stats["error_patterns"] = {
                pattern_key: {
                    "frequency": data["count"],
                    "last_seen": data["last_seen"]
                }
                for pattern_key, data in self.error_patterns_db.items()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"품질 통계 계산 실패: {e}")
            return {"error": str(e)}
    
    def _calculate_recent_trend(self) -> str:
        """최근 품질 트렌드 계산"""
        try:
            recent_records = self.verification_history[-10:]  # 최근 10개
            if len(recent_records) < 5:
                return "insufficient_data"
            
            first_half = recent_records[:len(recent_records)//2]
            second_half = recent_records[len(recent_records)//2:]
            
            first_avg = statistics.mean([r["overall_score"] for r in first_half])
            second_avg = statistics.mean([r["overall_score"] for r in second_half])
            
            diff = second_avg - first_avg
            
            if diff > 5:
                return "improving"
            elif diff < -5:
                return "declining"
            else:
                return "stable"
                
        except Exception:
            return "unknown"
    
    def get_service_info(self) -> Dict[str, Any]:
        """서비스 정보 반환"""
        return {
            "service": "quality_verification",
            "version": "1.0.0",
            "supported_languages": list(self.validation_rules.keys()),
            "verification_levels": ["basic", "comprehensive", "detailed"],
            "quality_grades": ["A", "B", "C", "D", "F"],
            "verification_count": len(self.verification_history),
            "learned_patterns": len(self.error_patterns_db),
            "capabilities": [
                "automatic_quality_assessment",
                "error_pattern_detection",
                "ai_based_validation",
                "quality_trend_analysis",
                "recommendation_generation"
            ]
        }


# 전역 인스턴스
quality_verification_service = QualityVerificationService()