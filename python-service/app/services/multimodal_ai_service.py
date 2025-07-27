#!/usr/bin/env python3
"""
멀티모달 AI 서비스
Multimodal AI Service

이미지와 텍스트를 동시에 분석하는 통합 AI 시스템
비전-언어 모델을 활용한 지능형 문서 분류 및 이해
"""

import logging
import json
import base64
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import cv2
from datetime import datetime
import asyncio
import aiohttp
import os
from pathlib import Path

# 멀티모달 모델 관련 (로컬에서 사용 가능한 경우)
try:
    from transformers import (
        VisionEncoderDecoderModel, 
        ViTImageProcessor, 
        AutoTokenizer,
        BlipProcessor, 
        BlipForConditionalGeneration,
        CLIPProcessor, 
        CLIPModel
    )
    from PIL import Image
    MULTIMODAL_AVAILABLE = True
except ImportError:
    MULTIMODAL_AVAILABLE = False

from app.services.multilingual_two_tier_service import MultilingualTwoTierService
from app.services.transformer_ocr_service import transformer_ocr_service

logger = logging.getLogger(__name__)


@dataclass
class MultimodalAnalysis:
    """멀티모달 분석 결과"""
    document_type: str
    confidence: float
    visual_features: Dict[str, Any]
    textual_features: Dict[str, Any]
    combined_analysis: Dict[str, Any]
    classification_results: Dict[str, Any]
    recommendations: List[str]


@dataclass
class DocumentClassification:
    """문서 분류 결과"""
    primary_type: str
    secondary_types: List[str]
    confidence_scores: Dict[str, float]
    key_indicators: List[str]
    processing_suggestions: List[str]


@dataclass
class VisualTextAlignment:
    """시각적-텍스트 정렬 결과"""
    aligned_regions: List[Dict[str, Any]]
    text_image_mapping: Dict[str, Any]
    layout_analysis: Dict[str, Any]
    reading_order: List[int]


class MultimodalAIService:
    """멀티모달 AI 서비스"""
    
    def __init__(self):
        """초기화"""
        self.ocr_service = MultilingualTwoTierService()
        
        # 모델 캐시
        self.model_cache = {}
        
        # 문서 타입 분류 규칙
        self.document_types = {
            "financial_statement": {
                "keywords": ["매출", "이익", "자산", "부채", "revenue", "profit", "assets"],
                "visual_patterns": ["table_structure", "numerical_data", "financial_charts"],
                "confidence_threshold": 0.7
            },
            "invoice": {
                "keywords": ["청구서", "invoice", "bill", "총액", "세금", "tax"],
                "visual_patterns": ["header_footer", "line_items", "total_section"],
                "confidence_threshold": 0.8
            },
            "contract": {
                "keywords": ["계약", "contract", "agreement", "조항", "clause"],
                "visual_patterns": ["paragraph_structure", "signature_area", "legal_format"],
                "confidence_threshold": 0.75
            },
            "report": {
                "keywords": ["보고서", "report", "분석", "analysis", "결과", "결론"],
                "visual_patterns": ["title_section", "body_paragraphs", "charts_graphs"],
                "confidence_threshold": 0.6
            },
            "form": {
                "keywords": ["신청", "application", "양식", "form", "기입", "작성"],
                "visual_patterns": ["input_fields", "checkboxes", "form_structure"],
                "confidence_threshold": 0.7
            }
        }
        
        # OpenAI API 설정
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.use_openai_vision = bool(self.openai_api_key)
        
        logger.info(f"MultimodalAIService 초기화 완료")
        logger.info(f"멀티모달 모델: {'사용 가능' if MULTIMODAL_AVAILABLE else '사용 불가'}")
        logger.info(f"OpenAI Vision: {'사용 가능' if self.use_openai_vision else '사용 불가'}")
    
    async def analyze_document_multimodal(
        self,
        image_path: str,
        language: str = "kor",
        analysis_depth: str = "comprehensive"
    ) -> MultimodalAnalysis:
        """
        멀티모달 문서 분석
        
        Args:
            image_path: 이미지 파일 경로
            language: 언어 코드
            analysis_depth: 분석 깊이 (basic, comprehensive, detailed)
            
        Returns:
            멀티모달 분석 결과
        """
        try:
            logger.info(f"멀티모달 분석 시작: {image_path}")
            
            # 1. 기본 OCR 수행
            ocr_result = self.ocr_service.process_image(image_path, language)
            extracted_text = ocr_result.get("extracted_text", "")
            
            # 2. 시각적 특징 추출
            visual_features = await self._extract_visual_features(image_path)
            
            # 3. 텍스트 특징 추출
            textual_features = self._extract_textual_features(extracted_text, language)
            
            # 4. 문서 분류
            classification = await self._classify_document_multimodal(
                image_path, extracted_text, visual_features, textual_features
            )
            
            # 5. 시각적-텍스트 정렬
            alignment = await self._align_visual_text(image_path, extracted_text)
            
            # 6. 통합 분석
            combined_analysis = await self._perform_combined_analysis(
                visual_features, textual_features, classification, alignment, analysis_depth
            )
            
            # 7. 추천사항 생성
            recommendations = self._generate_processing_recommendations(
                classification, combined_analysis
            )
            
            return MultimodalAnalysis(
                document_type=classification.primary_type,
                confidence=max(classification.confidence_scores.values()) if classification.confidence_scores else 0.0,
                visual_features=visual_features,
                textual_features=textual_features,
                combined_analysis=combined_analysis,
                classification_results=classification.__dict__,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"멀티모달 분석 실패: {e}")
            # 기본 OCR 결과로 폴백
            return MultimodalAnalysis(
                document_type="unknown",
                confidence=0.0,
                visual_features={},
                textual_features={"text": extracted_text if 'extracted_text' in locals() else ""},
                combined_analysis={"error": str(e)},
                classification_results={},
                recommendations=["기본 OCR 처리 권장"]
            )
    
    async def _extract_visual_features(self, image_path: str) -> Dict[str, Any]:
        """시각적 특징 추출"""
        try:
            # OpenCV를 사용한 기본 시각적 특징 추출
            image = cv2.imread(image_path)
            if image is None:
                return {"error": "이미지 로드 실패"}
            
            height, width = image.shape[:2]
            
            # 기본 이미지 속성
            basic_features = {
                "dimensions": {"width": width, "height": height},
                "aspect_ratio": width / height,
                "color_channels": image.shape[2] if len(image.shape) > 2 else 1
            }
            
            # 레이아웃 분석
            layout_features = self._analyze_layout_structure(image)
            
            # 텍스트 영역 감지
            text_regions = self._detect_text_regions(image)
            
            # 차트/표 감지
            structural_elements = self._detect_structural_elements(image)
            
            # OpenAI Vision API 사용 (가능한 경우)
            vision_analysis = {}
            if self.use_openai_vision:
                vision_analysis = await self._analyze_with_openai_vision(image_path)
            
            return {
                "basic": basic_features,
                "layout": layout_features,
                "text_regions": text_regions,
                "structural_elements": structural_elements,
                "vision_analysis": vision_analysis
            }
            
        except Exception as e:
            logger.error(f"시각적 특징 추출 실패: {e}")
            return {"error": str(e)}
    
    def _analyze_layout_structure(self, image: np.ndarray) -> Dict[str, Any]:
        """레이아웃 구조 분석"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 수평/수직 선 감지
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            
            horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
            vertical_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, vertical_kernel)
            
            # 윤곽선 감지
            contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 영역 분석
            regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = cv2.contourArea(contour)
                if area > 1000:  # 작은 영역 제외
                    regions.append({
                        "x": int(x), "y": int(y), 
                        "width": int(w), "height": int(h),
                        "area": int(area)
                    })
            
            return {
                "horizontal_lines_detected": len(cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]),
                "vertical_lines_detected": len(cv2.findContours(vertical_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]),
                "major_regions": regions[:10],  # 상위 10개 영역만
                "total_regions": len(regions),
                "layout_type": self._determine_layout_type(regions, horizontal_lines, vertical_lines)
            }
            
        except Exception as e:
            logger.error(f"레이아웃 분석 실패: {e}")
            return {"error": str(e)}
    
    def _determine_layout_type(self, regions: List[Dict], horizontal_lines: np.ndarray, vertical_lines: np.ndarray) -> str:
        """레이아웃 타입 결정"""
        h_lines = len(cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0])
        v_lines = len(cv2.findContours(vertical_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0])
        
        if h_lines > 5 and v_lines > 3:
            return "table_structured"
        elif len(regions) > 10:
            return "multi_column"
        elif h_lines > v_lines * 2:
            return "form_like"
        else:
            return "document_text"
    
    def _detect_text_regions(self, image: np.ndarray) -> Dict[str, Any]:
        """텍스트 영역 감지"""
        try:
            # EAST 텍스트 감지 (간단한 구현)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 모폴로지 연산으로 텍스트 영역 감지
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            processed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            
            # 윤곽선 기반 텍스트 영역 추정
            contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            text_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h
                aspect_ratio = w / h
                
                # 텍스트 영역으로 추정되는 조건
                if 50 < area < 50000 and 1 < aspect_ratio < 20:
                    text_regions.append({
                        "x": int(x), "y": int(y),
                        "width": int(w), "height": int(h),
                        "area": int(area),
                        "aspect_ratio": float(aspect_ratio)
                    })
            
            return {
                "detected_regions": len(text_regions),
                "regions": text_regions[:20],  # 상위 20개만
                "density": len(text_regions) / (image.shape[0] * image.shape[1]) * 100000
            }
            
        except Exception as e:
            logger.error(f"텍스트 영역 감지 실패: {e}")
            return {"error": str(e)}
    
    def _detect_structural_elements(self, image: np.ndarray) -> Dict[str, Any]:
        """구조적 요소 감지 (표, 차트 등)"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 직선 감지 (Hough Transform)
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=50, maxLineGap=10)
            
            # 원형 구조 감지 (차트용)
            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 50, param1=50, param2=30, minRadius=20, maxRadius=200)
            
            # 사각형 구조 감지
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rectangles = []
            
            for contour in contours:
                approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                if len(approx) == 4:  # 사각형
                    x, y, w, h = cv2.boundingRect(contour)
                    rectangles.append({"x": int(x), "y": int(y), "width": int(w), "height": int(h)})
            
            return {
                "lines_detected": len(lines) if lines is not None else 0,
                "circles_detected": len(circles[0]) if circles is not None else 0,
                "rectangles_detected": len(rectangles),
                "has_table_structure": len(lines) > 10 if lines is not None else False,
                "has_chart_elements": len(circles[0]) > 0 if circles is not None else False
            }
            
        except Exception as e:
            logger.error(f"구조적 요소 감지 실패: {e}")
            return {"error": str(e)}
    
    async def _analyze_with_openai_vision(self, image_path: str) -> Dict[str, Any]:
        """OpenAI Vision API를 사용한 이미지 분석"""
        if not self.use_openai_vision:
            return {}
        
        try:
            # 이미지를 base64로 인코딩
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # OpenAI Vision API 호출
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-4-vision-preview",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "이 문서 이미지를 분석하여 다음 정보를 JSON 형태로 제공해주세요: 1) 문서 유형, 2) 주요 구조적 요소, 3) 텍스트 레이아웃, 4) 시각적 특징"
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 1000
                }
                
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        
                        # JSON 파싱 시도
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError:
                            return {"raw_analysis": content}
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI Vision API 오류: {error_text}")
                        return {"error": f"API 오류: {response.status}"}
        
        except Exception as e:
            logger.error(f"OpenAI Vision 분석 실패: {e}")
            return {"error": str(e)}
    
    def _extract_textual_features(self, text: str, language: str) -> Dict[str, Any]:
        """텍스트 특징 추출"""
        try:
            if not text.strip():
                return {"error": "텍스트 없음"}
            
            # 기본 텍스트 통계
            lines = text.split('\n')
            words = text.split()
            
            # 언어별 특징
            lang_features = self._analyze_language_features(text, language)
            
            # 키워드 밀도
            keyword_density = self._calculate_keyword_density(text)
            
            # 구조적 패턴
            structural_patterns = self._detect_text_patterns(text)
            
            return {
                "basic_stats": {
                    "total_length": len(text),
                    "line_count": len(lines),
                    "word_count": len(words),
                    "avg_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0,
                    "avg_word_length": sum(len(word) for word in words) / len(words) if words else 0
                },
                "language_features": lang_features,
                "keyword_density": keyword_density,
                "structural_patterns": structural_patterns
            }
            
        except Exception as e:
            logger.error(f"텍스트 특징 추출 실패: {e}")
            return {"error": str(e)}
    
    def _analyze_language_features(self, text: str, language: str) -> Dict[str, Any]:
        """언어별 특징 분석"""
        features = {
            "language": language,
            "mixed_languages": False,
            "script_types": []
        }
        
        # 간단한 스크립트 타입 감지
        has_korean = bool(re.search(r'[가-힣]', text))
        has_english = bool(re.search(r'[a-zA-Z]', text))
        has_chinese = bool(re.search(r'[一-龯]', text))
        has_japanese = bool(re.search(r'[ひらがなカタカナ]', text))
        has_arabic = bool(re.search(r'[ء-ي]', text))
        has_numbers = bool(re.search(r'\d', text))
        
        script_count = sum([has_korean, has_english, has_chinese, has_japanese, has_arabic])
        
        if script_count > 1:
            features["mixed_languages"] = True
        
        if has_korean: features["script_types"].append("korean")
        if has_english: features["script_types"].append("english")
        if has_chinese: features["script_types"].append("chinese")
        if has_japanese: features["script_types"].append("japanese")
        if has_arabic: features["script_types"].append("arabic")
        if has_numbers: features["script_types"].append("numbers")
        
        return features
    
    def _calculate_keyword_density(self, text: str) -> Dict[str, float]:
        """키워드 밀도 계산"""
        text_lower = text.lower()
        total_words = len(text.split())
        
        densities = {}
        
        # 각 문서 타입별 키워드 밀도 계산
        for doc_type, config in self.document_types.items():
            keyword_count = 0
            for keyword in config["keywords"]:
                keyword_count += text_lower.count(keyword.lower())
            
            densities[doc_type] = keyword_count / max(total_words, 1) * 100
        
        return densities
    
    def _detect_text_patterns(self, text: str) -> Dict[str, Any]:
        """텍스트 패턴 감지"""
        import re
        
        patterns = {
            "dates": len(re.findall(r'\d{4}[-년./]\d{1,2}[-월./]\d{1,2}[일]?', text)),
            "numbers": len(re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', text)),
            "currencies": len(re.findall(r'[¥$€₩]\s*\d+(?:,\d{3})*(?:\.\d+)?', text)),
            "emails": len(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)),
            "phones": len(re.findall(r'\b\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4}\b', text)),
            "percentages": len(re.findall(r'\d+(?:\.\d+)?%', text)),
            "bullet_points": len(re.findall(r'^\s*[•·▪▫\*\-]\s', text, re.MULTILINE)),
            "headers": len(re.findall(r'^[A-Z\s가-힣]{3,}$', text, re.MULTILINE))
        }
        
        return patterns
    
    async def _classify_document_multimodal(
        self, 
        image_path: str, 
        text: str, 
        visual_features: Dict, 
        textual_features: Dict
    ) -> DocumentClassification:
        """멀티모달 문서 분류"""
        try:
            confidence_scores = {}
            key_indicators = []
            
            # 텍스트 기반 분류
            text_scores = textual_features.get("keyword_density", {})
            
            # 시각적 특징 기반 분류
            visual_scores = self._score_visual_features(visual_features)
            
            # 통합 점수 계산
            for doc_type in self.document_types.keys():
                text_score = text_scores.get(doc_type, 0)
                visual_score = visual_scores.get(doc_type, 0)
                
                # 가중 평균 (텍스트 60%, 시각적 40%)
                combined_score = (text_score * 0.6) + (visual_score * 0.4)
                confidence_scores[doc_type] = combined_score
                
                if combined_score > self.document_types[doc_type]["confidence_threshold"]:
                    key_indicators.extend(self.document_types[doc_type]["keywords"][:3])
            
            # 최고 점수 문서 타입 선택
            primary_type = max(confidence_scores, key=confidence_scores.get) if confidence_scores else "unknown"
            
            # 상위 2개 보조 타입
            sorted_types = sorted(confidence_scores.items(), key=lambda x: x[1], reverse=True)
            secondary_types = [t[0] for t in sorted_types[1:3]]
            
            # 처리 제안
            processing_suggestions = self._generate_processing_suggestions(primary_type, confidence_scores[primary_type])
            
            return DocumentClassification(
                primary_type=primary_type,
                secondary_types=secondary_types,
                confidence_scores=confidence_scores,
                key_indicators=list(set(key_indicators)),
                processing_suggestions=processing_suggestions
            )
            
        except Exception as e:
            logger.error(f"문서 분류 실패: {e}")
            return DocumentClassification(
                primary_type="unknown",
                secondary_types=[],
                confidence_scores={},
                key_indicators=[],
                processing_suggestions=["기본 처리 권장"]
            )
    
    def _score_visual_features(self, visual_features: Dict) -> Dict[str, float]:
        """시각적 특징 점수화"""
        scores = {}
        
        try:
            layout = visual_features.get("layout", {})
            structural = visual_features.get("structural_elements", {})
            
            # 재무제표 점수
            financial_score = 0
            if layout.get("layout_type") == "table_structured":
                financial_score += 30
            if structural.get("has_table_structure"):
                financial_score += 25
            if layout.get("horizontal_lines_detected", 0) > 5:
                financial_score += 20
            scores["financial_statement"] = financial_score
            
            # 청구서 점수
            invoice_score = 0
            if layout.get("total_regions", 0) > 5:
                invoice_score += 20
            if structural.get("rectangles_detected", 0) > 3:
                invoice_score += 15
            scores["invoice"] = invoice_score
            
            # 계약서 점수
            contract_score = 0
            if layout.get("layout_type") == "document_text":
                contract_score += 25
            scores["contract"] = contract_score
            
            # 보고서 점수
            report_score = 0
            if structural.get("has_chart_elements"):
                report_score += 30
            if layout.get("layout_type") == "multi_column":
                report_score += 20
            scores["report"] = report_score
            
            # 양식 점수
            form_score = 0
            if layout.get("layout_type") == "form_like":
                form_score += 35
            if structural.get("rectangles_detected", 0) > 10:
                form_score += 20
            scores["form"] = form_score
            
        except Exception as e:
            logger.error(f"시각적 특징 점수화 실패: {e}")
        
        return scores
    
    def _generate_processing_suggestions(self, doc_type: str, confidence: float) -> List[str]:
        """처리 제안 생성"""
        suggestions = []
        
        if confidence < 50:
            suggestions.append("문서 유형이 불확실하므로 수동 검토 필요")
            suggestions.append("다양한 OCR 모델로 재처리 권장")
        
        if doc_type == "financial_statement":
            suggestions.extend([
                "표 구조 인식 활용 권장",
                "숫자 정확도 검증 필요",
                "트랜스포머 OCR 모델 사용 권장"
            ])
        elif doc_type == "invoice":
            suggestions.extend([
                "라인 아이템 개별 처리 권장",
                "총액 검증 로직 적용",
                "날짜 형식 정규화 필요"
            ])
        elif doc_type == "contract":
            suggestions.extend([
                "긴 텍스트 처리에 최적화된 설정 사용",
                "법적 용어 사전 활용",
                "단락 구조 보존 중요"
            ])
        elif doc_type == "report":
            suggestions.extend([
                "차트/그래프 별도 분석",
                "멀티모달 분석 활용",
                "섹션별 처리 권장"
            ])
        elif doc_type == "form":
            suggestions.extend([
                "필드 단위 개별 처리",
                "체크박스/선택항목 별도 인식",
                "구조화된 데이터 추출"
            ])
        
        return suggestions
    
    async def _align_visual_text(self, image_path: str, text: str) -> VisualTextAlignment:
        """시각적-텍스트 정렬"""
        try:
            # 간단한 구현 - 실제로는 더 복잡한 정렬 알고리즘 필요
            image = cv2.imread(image_path)
            height, width = image.shape[:2]
            
            # 텍스트 라인을 이미지 영역에 매핑 (추정)
            lines = text.split('\n')
            line_height = height // max(len(lines), 1)
            
            aligned_regions = []
            for i, line in enumerate(lines):
                if line.strip():
                    aligned_regions.append({
                        "text": line.strip(),
                        "estimated_bbox": {
                            "x": 0,
                            "y": i * line_height,
                            "width": width,
                            "height": line_height
                        },
                        "confidence": 0.5  # 추정값
                    })
            
            return VisualTextAlignment(
                aligned_regions=aligned_regions,
                text_image_mapping={"method": "estimated", "accuracy": "low"},
                layout_analysis={"reading_order": "top_to_bottom"},
                reading_order=list(range(len(aligned_regions)))
            )
            
        except Exception as e:
            logger.error(f"시각적-텍스트 정렬 실패: {e}")
            return VisualTextAlignment(
                aligned_regions=[],
                text_image_mapping={},
                layout_analysis={},
                reading_order=[]
            )
    
    async def _perform_combined_analysis(
        self, 
        visual_features: Dict, 
        textual_features: Dict, 
        classification: DocumentClassification,
        alignment: VisualTextAlignment,
        depth: str
    ) -> Dict[str, Any]:
        """통합 분석 수행"""
        try:
            analysis = {
                "analysis_depth": depth,
                "timestamp": datetime.now().isoformat(),
                "summary": {}
            }
            
            # 기본 분석
            analysis["summary"]["document_complexity"] = self._assess_document_complexity(
                visual_features, textual_features
            )
            
            analysis["summary"]["processing_difficulty"] = self._assess_processing_difficulty(
                visual_features, textual_features, classification
            )
            
            # 상세 분석 (depth가 comprehensive 이상인 경우)
            if depth in ["comprehensive", "detailed"]:
                analysis["detailed_insights"] = {
                    "layout_analysis": self._analyze_layout_insights(visual_features),
                    "content_analysis": self._analyze_content_insights(textual_features),
                    "cross_modal_correlations": self._find_cross_modal_correlations(
                        visual_features, textual_features
                    )
                }
            
            # 고급 분석 (depth가 detailed인 경우)
            if depth == "detailed":
                analysis["advanced_features"] = {
                    "semantic_analysis": await self._perform_semantic_analysis(textual_features),
                    "visual_semantics": self._analyze_visual_semantics(visual_features),
                    "multimodal_coherence": self._assess_multimodal_coherence(
                        visual_features, textual_features, alignment
                    )
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"통합 분석 실패: {e}")
            return {"error": str(e)}
    
    def _assess_document_complexity(self, visual_features: Dict, textual_features: Dict) -> str:
        """문서 복잡도 평가"""
        complexity_score = 0
        
        # 시각적 복잡도
        layout = visual_features.get("layout", {})
        complexity_score += min(layout.get("total_regions", 0) / 10, 3)
        complexity_score += min(layout.get("horizontal_lines_detected", 0) / 20, 2)
        
        # 텍스트 복잡도
        basic_stats = textual_features.get("basic_stats", {})
        complexity_score += min(basic_stats.get("line_count", 0) / 50, 3)
        complexity_score += min(basic_stats.get("word_count", 0) / 500, 2)
        
        if complexity_score < 3:
            return "simple"
        elif complexity_score < 6:
            return "moderate"
        else:
            return "complex"
    
    def _assess_processing_difficulty(self, visual_features: Dict, textual_features: Dict, classification: DocumentClassification) -> str:
        """처리 난이도 평가"""
        difficulty_score = 0
        
        # 분류 신뢰도가 낮으면 어려움
        max_confidence = max(classification.confidence_scores.values()) if classification.confidence_scores else 0
        if max_confidence < 50:
            difficulty_score += 3
        elif max_confidence < 70:
            difficulty_score += 1
        
        # 혼합 언어는 어려움
        lang_features = textual_features.get("language_features", {})
        if lang_features.get("mixed_languages", False):
            difficulty_score += 2
        
        # 구조적 복잡성
        structural = visual_features.get("structural_elements", {})
        if structural.get("has_chart_elements", False):
            difficulty_score += 1
        if structural.get("has_table_structure", False):
            difficulty_score += 1
        
        if difficulty_score <= 2:
            return "easy"
        elif difficulty_score <= 4:
            return "moderate"
        else:
            return "difficult"
    
    def _analyze_layout_insights(self, visual_features: Dict) -> Dict[str, Any]:
        """레이아웃 인사이트 분석"""
        layout = visual_features.get("layout", {})
        
        insights = {
            "dominant_structure": layout.get("layout_type", "unknown"),
            "region_distribution": self._analyze_region_distribution(layout.get("major_regions", [])),
            "line_patterns": {
                "horizontal_dominance": layout.get("horizontal_lines_detected", 0) > layout.get("vertical_lines_detected", 0),
                "grid_like": layout.get("horizontal_lines_detected", 0) > 3 and layout.get("vertical_lines_detected", 0) > 3
            }
        }
        
        return insights
    
    def _analyze_region_distribution(self, regions: List[Dict]) -> Dict[str, Any]:
        """영역 분포 분석"""
        if not regions:
            return {"empty": True}
        
        # 영역 크기 분포
        areas = [region["area"] for region in regions]
        widths = [region["width"] for region in regions]
        heights = [region["height"] for region in regions]
        
        return {
            "total_regions": len(regions),
            "area_stats": {
                "mean": np.mean(areas),
                "std": np.std(areas),
                "min": np.min(areas),
                "max": np.max(areas)
            },
            "dimension_stats": {
                "avg_width": np.mean(widths),
                "avg_height": np.mean(heights),
                "aspect_ratio_avg": np.mean([w/h for w, h in zip(widths, heights) if h > 0])
            }
        }
    
    def _analyze_content_insights(self, textual_features: Dict) -> Dict[str, Any]:
        """콘텐츠 인사이트 분석"""
        basic_stats = textual_features.get("basic_stats", {})
        patterns = textual_features.get("structural_patterns", {})
        
        insights = {
            "readability": self._assess_readability(basic_stats),
            "information_density": self._calculate_information_density(basic_stats, patterns),
            "content_structure": self._analyze_content_structure(patterns)
        }
        
        return insights
    
    def _assess_readability(self, basic_stats: Dict) -> Dict[str, Any]:
        """가독성 평가"""
        avg_word_length = basic_stats.get("avg_word_length", 0)
        avg_line_length = basic_stats.get("avg_line_length", 0)
        
        readability_score = 0
        
        # 적절한 단어 길이 (4-6자)
        if 4 <= avg_word_length <= 6:
            readability_score += 2
        elif avg_word_length > 8:
            readability_score -= 1
        
        # 적절한 라인 길이 (50-80자)
        if 50 <= avg_line_length <= 80:
            readability_score += 2
        elif avg_line_length > 100:
            readability_score -= 1
        
        return {
            "score": readability_score,
            "level": "good" if readability_score >= 2 else "moderate" if readability_score >= 0 else "poor"
        }
    
    def _calculate_information_density(self, basic_stats: Dict, patterns: Dict) -> float:
        """정보 밀도 계산"""
        total_chars = basic_stats.get("total_length", 1)
        
        information_elements = (
            patterns.get("numbers", 0) +
            patterns.get("dates", 0) +
            patterns.get("currencies", 0) +
            patterns.get("emails", 0) +
            patterns.get("phones", 0)
        )
        
        return information_elements / total_chars * 1000  # per 1000 characters
    
    def _analyze_content_structure(self, patterns: Dict) -> Dict[str, Any]:
        """콘텐츠 구조 분석"""
        structure_score = 0
        
        if patterns.get("headers", 0) > 0:
            structure_score += 2
        if patterns.get("bullet_points", 0) > 0:
            structure_score += 1
        if patterns.get("numbers", 0) / max(patterns.get("total_words", 1), 1) > 0.1:
            structure_score += 1
        
        return {
            "structure_score": structure_score,
            "has_headers": patterns.get("headers", 0) > 0,
            "has_lists": patterns.get("bullet_points", 0) > 0,
            "number_heavy": patterns.get("numbers", 0) / max(patterns.get("total_words", 1), 1) > 0.1
        }
    
    def _find_cross_modal_correlations(self, visual_features: Dict, textual_features: Dict) -> Dict[str, Any]:
        """교차 모달 상관관계 찾기"""
        correlations = {}
        
        # 표 구조와 숫자 패턴 상관관계
        has_table_visual = visual_features.get("structural_elements", {}).get("has_table_structure", False)
        number_density = textual_features.get("structural_patterns", {}).get("numbers", 0)
        
        correlations["table_number_correlation"] = {
            "visual_table": has_table_visual,
            "text_numbers": number_density,
            "correlation": "high" if has_table_visual and number_density > 5 else "low"
        }
        
        # 차트와 수치 데이터 상관관계
        has_chart_visual = visual_features.get("structural_elements", {}).get("has_chart_elements", False)
        has_percentages = textual_features.get("structural_patterns", {}).get("percentages", 0) > 0
        
        correlations["chart_data_correlation"] = {
            "visual_chart": has_chart_visual,
            "text_data": has_percentages,
            "correlation": "high" if has_chart_visual and has_percentages else "low"
        }
        
        return correlations
    
    async def _perform_semantic_analysis(self, textual_features: Dict) -> Dict[str, Any]:
        """의미론적 분석 수행"""
        # 여기서는 간단한 구현만 제공
        # 실전에서는 더 정교한 NLP 모델 활용 필요
        
        return {
            "sentiment": "neutral",  # 감정 분석
            "topics": [],  # 주제 추출
            "entities": [],  # 개체명 인식
            "note": "semantic analysis requires advanced NLP models"
        }
    
    def _analyze_visual_semantics(self, visual_features: Dict) -> Dict[str, Any]:
        """시각적 의미론 분석"""
        return {
            "visual_hierarchy": self._determine_visual_hierarchy(visual_features),
            "attention_regions": self._identify_attention_regions(visual_features),
            "visual_flow": self._analyze_visual_flow(visual_features)
        }
    
    def _determine_visual_hierarchy(self, visual_features: Dict) -> Dict[str, Any]:
        """시각적 계층 구조 결정"""
        layout = visual_features.get("layout", {})
        regions = layout.get("major_regions", [])
        
        if not regions:
            return {"hierarchy": "flat"}
        
        # 영역 크기 기준 계층 구조 추정
        sorted_by_area = sorted(regions, key=lambda r: r["area"], reverse=True)
        
        return {
            "hierarchy": "hierarchical" if len(sorted_by_area) > 3 else "simple",
            "primary_region": sorted_by_area[0] if sorted_by_area else None,
            "secondary_regions": sorted_by_area[1:3] if len(sorted_by_area) > 1 else []
        }
    
    def _identify_attention_regions(self, visual_features: Dict) -> List[Dict]:
        """주목 영역 식별"""
        # 간단한 구현 - 실제로는 더 정교한 시각적 주의 모델 필요
        layout = visual_features.get("layout", {})
        regions = layout.get("major_regions", [])
        
        # 크기와 위치 기준으로 주목도 계산
        attention_regions = []
        for region in regions[:5]:  # 상위 5개 영역만
            attention_score = region["area"] / 10000  # 간단한 점수
            if region["y"] < 100:  # 상단 영역에 가중치
                attention_score *= 1.2
            
            attention_regions.append({
                "region": region,
                "attention_score": attention_score
            })
        
        return sorted(attention_regions, key=lambda r: r["attention_score"], reverse=True)
    
    def _analyze_visual_flow(self, visual_features: Dict) -> Dict[str, Any]:
        """시각적 흐름 분석"""
        layout = visual_features.get("layout", {})
        
        # 레이아웃 타입에 따른 흐름 패턴
        layout_type = layout.get("layout_type", "unknown")
        
        flow_patterns = {
            "table_structured": "grid_based",
            "multi_column": "column_wise",
            "form_like": "sequential",
            "document_text": "linear"
        }
        
        return {
            "primary_flow": flow_patterns.get(layout_type, "unknown"),
            "reading_direction": "left_to_right",  # 언어에 따라 조정 필요
            "flow_complexity": "simple" if layout.get("total_regions", 0) < 5 else "complex"
        }
    
    def _assess_multimodal_coherence(self, visual_features: Dict, textual_features: Dict, alignment: VisualTextAlignment) -> Dict[str, Any]:
        """멀티모달 일관성 평가"""
        coherence_score = 0
        issues = []
        
        # 정렬 품질 확인
        aligned_regions = len(alignment.aligned_regions)
        if aligned_regions > 0:
            coherence_score += 2
        else:
            issues.append("텍스트-이미지 정렬 실패")
        
        # 구조적 일관성 확인
        visual_structure = visual_features.get("layout", {}).get("layout_type", "unknown")
        text_patterns = textual_features.get("structural_patterns", {})
        
        if visual_structure == "table_structured" and text_patterns.get("numbers", 0) > 5:
            coherence_score += 3
        elif visual_structure == "document_text" and text_patterns.get("headers", 0) > 0:
            coherence_score += 2
        else:
            issues.append("시각적-텍스트 구조 불일치")
        
        return {
            "coherence_score": coherence_score,
            "coherence_level": "high" if coherence_score >= 4 else "medium" if coherence_score >= 2 else "low",
            "issues": issues,
            "alignment_quality": "good" if aligned_regions > 0 else "poor"
        }
    
    def _generate_processing_recommendations(self, classification: DocumentClassification, combined_analysis: Dict) -> List[str]:
        """처리 권장사항 생성"""
        recommendations = []
        
        # 문서 타입별 기본 권장사항
        recommendations.extend(classification.processing_suggestions)
        
        # 복잡도 기반 권장사항
        complexity = combined_analysis.get("summary", {}).get("document_complexity", "moderate")
        if complexity == "complex":
            recommendations.append("단계별 처리 권장")
            recommendations.append("섹션별 분할 처리 고려")
        
        # 난이도 기반 권장사항
        difficulty = combined_analysis.get("summary", {}).get("processing_difficulty", "moderate")
        if difficulty == "difficult":
            recommendations.append("수작업 검토 필수")
            recommendations.append("다중 OCR 엔진 활용 권장")
        
        # 상세 분석 기반 권장사항
        if "detailed_insights" in combined_analysis:
            insights = combined_analysis["detailed_insights"]
            
            # 레이아웃 기반
            layout_insights = insights.get("layout_analysis", {})
            if layout_insights.get("line_patterns", {}).get("grid_like", False):
                recommendations.append("표 인식 모드 사용 권장")
            
            # 콘텐츠 기반
            content_insights = insights.get("content_analysis", {})
            if content_insights.get("information_density", 0) > 50:
                recommendations.append("정보 추출 모드 최적화")
        
        return list(set(recommendations))  # 중복 제거
    
    def get_service_info(self) -> Dict[str, Any]:
        """서비스 정보 반환"""
        return {
            "service": "multimodal_ai",
            "version": "1.0.0",
            "capabilities": {
                "vision_analysis": True,
                "text_analysis": True,
                "document_classification": True,
                "visual_text_alignment": True,
                "multimodal_integration": True
            },
            "supported_analysis_depths": ["basic", "comprehensive", "detailed"],
            "supported_document_types": list(self.document_types.keys()),
            "models_available": {
                "multimodal_models": MULTIMODAL_AVAILABLE,
                "openai_vision": self.use_openai_vision,
                "opencv_analysis": True
            }
        }


# 전역 인스턴스
multimodal_ai_service = MultimodalAIService()