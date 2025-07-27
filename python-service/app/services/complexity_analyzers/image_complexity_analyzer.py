"""
이미지 복잡도 분석기
TwoTierOCRService에서 분리된 이미지 복잡도 분석 로직
Single Responsibility Principle 적용
"""

import cv2
import numpy as np
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ComplexityMetric(Enum):
    """복잡도 메트릭 타입"""
    TABLE_COMPLEXITY = "table_complexity"
    TEXT_DENSITY = "text_density"
    LANGUAGE_COMPLEXITY = "language_complexity"
    STRUCTURE_COMPLEXITY = "structure_complexity"
    OVERALL_COMPLEXITY = "overall_complexity"


@dataclass
class ComplexityThresholds:
    """복잡도 임계값 설정"""
    table_complexity: float = 0.7
    text_density: float = 0.8
    language_complexity: float = 0.6
    structure_complexity: float = 0.75
    overall_threshold: float = 0.65


@dataclass
class ComplexityAnalysisResult:
    """복잡도 분석 결과"""
    table_complexity: float
    text_density: float
    language_complexity: float
    structure_complexity: float
    overall_complexity: float
    analysis_metadata: Dict[str, Any]
    recommendations: Dict[str, Any]


class ImageComplexityAnalyzer:
    """이미지 복잡도 분석기 - SOLID 원칙 적용"""
    
    def __init__(self, thresholds: Optional[ComplexityThresholds] = None):
        """
        초기화
        
        Args:
            thresholds: 복잡도 임계값 설정
        """
        self.thresholds = thresholds or ComplexityThresholds()
        
        # 언어 복잡도 지표
        self.language_indicators = {
            'korean': {
                'keywords': ['korean', 'hangul', 'kr', '한글', '한국', 'kor'],
                'complexity_score': 0.8,
                'confidence': 0.9
            },
            'chinese': {
                'keywords': ['chinese', 'china', '중국', 'cn', 'zh'],
                'complexity_score': 0.85,
                'confidence': 0.9
            },
            'japanese': {
                'keywords': ['japanese', 'japan', '일본', 'jp', 'ja'],
                'complexity_score': 0.8,
                'confidence': 0.9
            },
            'arabic': {
                'keywords': ['arabic', 'arab', '아랍', 'ar'],
                'complexity_score': 0.9,
                'confidence': 0.8
            },
            'mixed': {
                'keywords': ['excel', 'table', 'chart', 'multi', 'mixed'],
                'complexity_score': 0.6,
                'confidence': 0.7
            },
            'english': {
                'keywords': ['english', 'en', 'eng'],
                'complexity_score': 0.4,
                'confidence': 0.8
            }
        }
        
        # 구조적 복잡도 분석 파라미터
        self.structure_params = {
            'min_contour_area': 100,
            'contour_normalization_factor': 10000,
            'significant_contour_threshold': 50
        }
        
        # 테이블 복잡도 분석 파라미터
        self.table_params = {
            'canny_low_threshold': 50,
            'canny_high_threshold': 150,
            'horizontal_kernel_size': (40, 1),
            'vertical_kernel_size': (1, 40),
            'complexity_normalization_factor': 1000
        }
    
    def analyze_complexity(self, image_path: str, context_hints: Optional[Dict[str, Any]] = None) -> ComplexityAnalysisResult:
        """이미지 복잡도 종합 분석"""
        try:
            # 이미지 로드 및 기본 처리
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return self._create_fallback_result()
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 각 복잡도 메트릭 계산
            table_complexity = self._analyze_table_complexity(gray)
            text_density = self._analyze_text_density(gray)
            language_complexity = self._analyze_language_complexity(image_path, context_hints)
            structure_complexity = self._analyze_structure_complexity(gray)
            
            # 전체 복잡도 계산
            overall_complexity = self._calculate_overall_complexity(
                table_complexity, text_density, language_complexity, structure_complexity
            )
            
            # 분석 메타데이터 생성
            analysis_metadata = self._generate_analysis_metadata(
                image, gray, image_path, context_hints
            )
            
            # 추천사항 생성
            recommendations = self._generate_recommendations(
                table_complexity, text_density, language_complexity, 
                structure_complexity, overall_complexity
            )
            
            return ComplexityAnalysisResult(
                table_complexity=table_complexity,
                text_density=text_density,
                language_complexity=language_complexity,
                structure_complexity=structure_complexity,
                overall_complexity=overall_complexity,
                analysis_metadata=analysis_metadata,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Complexity analysis failed: {e}")
            return self._create_fallback_result(error=str(e))
    
    def _analyze_table_complexity(self, gray_image: np.ndarray) -> float:
        """테이블 복잡도 분석"""
        try:
            # 엣지 감지
            edges = cv2.Canny(
                gray_image, 
                self.table_params['canny_low_threshold'],
                self.table_params['canny_high_threshold']
            )
            
            # 수평선 감지
            horizontal_kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT, 
                self.table_params['horizontal_kernel_size']
            )
            h_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
            
            # 수직선 감지
            vertical_kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT,
                self.table_params['vertical_kernel_size']
            )
            v_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vertical_kernel)
            
            # 교차점 계산 (테이블 복잡도의 지표)
            intersection = cv2.bitwise_and(h_lines, v_lines)
            intersection_count = np.sum(intersection > 0)
            
            # 이미지 크기 대비 정규화
            image_area = gray_image.shape[0] * gray_image.shape[1]
            complexity_score = intersection_count / image_area
            
            # 정규화 및 제한
            normalized_score = complexity_score * self.table_params['complexity_normalization_factor']
            return min(normalized_score, 1.0)
            
        except Exception as e:
            logger.error(f"Table complexity analysis failed: {e}")
            return 0.5  # 기본값
    
    def _analyze_text_density(self, gray_image: np.ndarray) -> float:
        """텍스트 밀도 분석"""
        try:
            # OTSU 임계값을 사용한 이진화
            _, thresh = cv2.threshold(
                gray_image, 0, 255, 
                cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            
            # 텍스트 영역 비율 계산 (검은 픽셀 = 텍스트)
            text_pixels = np.sum(thresh == 0)
            total_pixels = thresh.shape[0] * thresh.shape[1]
            
            if total_pixels == 0:
                return 0.0
            
            density = text_pixels / total_pixels
            
            # 정규화 (일반적으로 텍스트 밀도는 50% 미만)
            normalized_density = min(density * 2, 1.0)
            
            return normalized_density
            
        except Exception as e:
            logger.error(f"Text density analysis failed: {e}")
            return 0.5  # 기본값
    
    def _analyze_language_complexity(self, image_path: str, 
                                   context_hints: Optional[Dict[str, Any]] = None) -> float:
        """언어 복잡도 분석"""
        try:
            filename = Path(image_path).name.lower()
            
            # 컨텍스트 힌트에서 언어 정보 확인
            detected_language = None
            max_confidence = 0.0
            
            if context_hints and 'language' in context_hints:
                detected_language = context_hints['language']
                max_confidence = 0.9
            else:
                # 파일명 기반 언어 감지
                for lang_type, config in self.language_indicators.items():
                    for keyword in config['keywords']:
                        if keyword in filename:
                            if config['confidence'] > max_confidence:
                                detected_language = lang_type
                                max_confidence = config['confidence']
            
            # 감지된 언어의 복잡도 점수 반환
            if detected_language and detected_language in self.language_indicators:
                base_score = self.language_indicators[detected_language]['complexity_score']
                return base_score * max_confidence
            
            # 기본 복잡도 (영어 가정)
            return 0.4
            
        except Exception as e:
            logger.error(f"Language complexity analysis failed: {e}")
            return 0.5  # 기본값
    
    def _analyze_structure_complexity(self, gray_image: np.ndarray) -> float:
        """구조적 복잡도 분석"""
        try:
            # 컨투어 찾기
            contours, _ = cv2.findContours(
                gray_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )
            
            # 의미있는 크기의 컨투어만 필터링
            min_area = self.structure_params['min_contour_area']
            significant_contours = [
                c for c in contours if cv2.contourArea(c) > min_area
            ]
            
            # 이미지 크기 대비 컨투어 밀도 계산
            image_area = gray_image.shape[0] * gray_image.shape[1]
            normalization_factor = self.structure_params['contour_normalization_factor']
            
            complexity = len(significant_contours) / (image_area / normalization_factor)
            
            # 추가 구조적 특성 분석
            hierarchy_complexity = self._analyze_contour_hierarchy(contours)
            shape_complexity = self._analyze_shape_complexity(significant_contours)
            
            # 가중 평균
            final_complexity = (
                complexity * 0.5 + 
                hierarchy_complexity * 0.3 + 
                shape_complexity * 0.2
            )
            
            return min(final_complexity, 1.0)
            
        except Exception as e:
            logger.error(f"Structure complexity analysis failed: {e}")
            return 0.5  # 기본값
    
    def _analyze_contour_hierarchy(self, contours) -> float:
        """컨투어 계층 구조 복잡도 분석"""
        try:
            if not contours:
                return 0.0
            
            # 중첩 레벨 계산 (간단한 휴리스틱)
            nested_count = 0
            for i, contour in enumerate(contours):
                for j, other_contour in enumerate(contours):
                    if i != j:
                        # 한 컨투어가 다른 컨투어 안에 있는지 확인
                        if cv2.contourArea(contour) < cv2.contourArea(other_contour):
                            # 간단한 포함 관계 확인
                            nested_count += 1
            
            # 정규화
            hierarchy_complexity = nested_count / max(len(contours), 1)
            return min(hierarchy_complexity, 1.0)
            
        except Exception as e:
            logger.error(f"Contour hierarchy analysis failed: {e}")
            return 0.0
    
    def _analyze_shape_complexity(self, contours) -> float:
        """도형 복잡도 분석"""
        try:
            if not contours:
                return 0.0
            
            complexity_scores = []
            
            for contour in contours:
                # 근사 곡선으로 복잡도 측정
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # 꼭짓점 수로 복잡도 측정
                vertex_complexity = min(len(approx) / 20.0, 1.0)
                
                # 종횡비로 복잡도 측정
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = max(w, h) / max(min(w, h), 1)
                aspect_complexity = min(aspect_ratio / 10.0, 1.0)
                
                # 개별 도형의 복잡도
                shape_complexity = (vertex_complexity + aspect_complexity) / 2
                complexity_scores.append(shape_complexity)
            
            # 평균 복잡도
            return sum(complexity_scores) / len(complexity_scores) if complexity_scores else 0.0
            
        except Exception as e:
            logger.error(f"Shape complexity analysis failed: {e}")
            return 0.0
    
    def _calculate_overall_complexity(self, table_complexity: float, text_density: float,
                                    language_complexity: float, structure_complexity: float) -> float:
        """전체 복잡도 계산"""
        # 가중치 설정 (중요도에 따라)
        weights = {
            'table': 0.3,
            'text': 0.25,
            'language': 0.25,
            'structure': 0.2
        }
        
        overall = (
            table_complexity * weights['table'] +
            text_density * weights['text'] +
            language_complexity * weights['language'] +
            structure_complexity * weights['structure']
        )
        
        return min(overall, 1.0)
    
    def _generate_analysis_metadata(self, image: np.ndarray, gray: np.ndarray,
                                  image_path: str, context_hints: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """분석 메타데이터 생성"""
        try:
            return {
                'image_dimensions': {
                    'width': image.shape[1],
                    'height': image.shape[0],
                    'channels': image.shape[2] if len(image.shape) > 2 else 1,
                    'total_pixels': image.shape[0] * image.shape[1]
                },
                'file_info': {
                    'path': image_path,
                    'filename': Path(image_path).name,
                    'extension': Path(image_path).suffix
                },
                'analysis_params': {
                    'thresholds': {
                        'table_complexity': self.thresholds.table_complexity,
                        'text_density': self.thresholds.text_density,
                        'language_complexity': self.thresholds.language_complexity,
                        'structure_complexity': self.thresholds.structure_complexity
                    }
                },
                'context_hints': context_hints or {},
                'image_statistics': {
                    'mean_brightness': float(np.mean(gray)),
                    'brightness_std': float(np.std(gray)),
                    'min_brightness': int(np.min(gray)),
                    'max_brightness': int(np.max(gray))
                }
            }
        except Exception as e:
            logger.error(f"Metadata generation failed: {e}")
            return {'error': str(e)}
    
    def _generate_recommendations(self, table_complexity: float, text_density: float,
                                language_complexity: float, structure_complexity: float,
                                overall_complexity: float) -> Dict[str, Any]:
        """처리 추천사항 생성"""
        recommendations = {
            'processing_tier_recommendation': 'tier2',
            'special_processing_needed': [],
            'optimization_suggestions': [],
            'warnings': []
        }
        
        # 처리 계층 추천
        if overall_complexity > self.thresholds.overall_threshold:
            recommendations['processing_tier_recommendation'] = 'tier3'
        
        # 특별 처리 필요 사항
        if table_complexity > self.thresholds.table_complexity:
            recommendations['special_processing_needed'].append('table_structure_analysis')
            recommendations['optimization_suggestions'].append('Use specialized table OCR models')
        
        if text_density > self.thresholds.text_density:
            recommendations['special_processing_needed'].append('high_density_text_processing')
            recommendations['optimization_suggestions'].append('Apply text region segmentation')
        
        if language_complexity > self.thresholds.language_complexity:
            recommendations['special_processing_needed'].append('multilingual_processing')
            recommendations['optimization_suggestions'].append('Use language-specific OCR models')
        
        if structure_complexity > self.thresholds.structure_complexity:
            recommendations['special_processing_needed'].append('complex_layout_analysis')
            recommendations['optimization_suggestions'].append('Apply advanced layout detection')
        
        # 경고사항
        if overall_complexity > 0.9:
            recommendations['warnings'].append('Very high complexity - consider manual review')
        
        if table_complexity > 0.8 and text_density > 0.8:
            recommendations['warnings'].append('Complex table with dense text - high error risk')
        
        return recommendations
    
    def _create_fallback_result(self, error: Optional[str] = None) -> ComplexityAnalysisResult:
        """fallback 결과 생성"""
        return ComplexityAnalysisResult(
            table_complexity=0.5,
            text_density=0.5,
            language_complexity=0.5,
            structure_complexity=0.5,
            overall_complexity=0.5,
            analysis_metadata={'error': error} if error else {},
            recommendations={
                'processing_tier_recommendation': 'tier2',
                'special_processing_needed': [],
                'optimization_suggestions': ['Manual analysis recommended due to analysis failure'],
                'warnings': ['Complexity analysis failed - using default values']
            }
        )
    
    def get_complexity_threshold_recommendations(self, image_type: str = "general") -> ComplexityThresholds:
        """이미지 타입별 복잡도 임계값 추천"""
        threshold_presets = {
            "financial_document": ComplexityThresholds(
                table_complexity=0.6,
                text_density=0.7,
                language_complexity=0.5,
                structure_complexity=0.7,
                overall_threshold=0.6
            ),
            "technical_drawing": ComplexityThresholds(
                table_complexity=0.8,
                text_density=0.9,
                language_complexity=0.4,
                structure_complexity=0.8,
                overall_threshold=0.7
            ),
            "mixed_content": ComplexityThresholds(
                table_complexity=0.7,
                text_density=0.8,
                language_complexity=0.6,
                structure_complexity=0.75,
                overall_threshold=0.65
            ),
            "general": ComplexityThresholds()  # 기본값
        }
        
        return threshold_presets.get(image_type, threshold_presets["general"])
    
    def analyze_batch_complexity(self, image_paths: list[str], 
                                context_hints: Optional[Dict[str, Any]] = None) -> Dict[str, ComplexityAnalysisResult]:
        """배치 복잡도 분석"""
        results = {}
        
        for image_path in image_paths:
            try:
                result = self.analyze_complexity(image_path, context_hints)
                results[image_path] = result
            except Exception as e:
                logger.error(f"Batch analysis failed for {image_path}: {e}")
                results[image_path] = self._create_fallback_result(error=str(e))
        
        return results
    
    def get_complexity_distribution_stats(self, results: Dict[str, ComplexityAnalysisResult]) -> Dict[str, Any]:
        """복잡도 분포 통계"""
        if not results:
            return {}
        
        complexities = [result.overall_complexity for result in results.values()]
        
        return {
            'total_images': len(complexities),
            'mean_complexity': np.mean(complexities),
            'std_complexity': np.std(complexities),
            'min_complexity': np.min(complexities),
            'max_complexity': np.max(complexities),
            'complexity_distribution': {
                'low_complexity': sum(1 for c in complexities if c < 0.3),
                'medium_complexity': sum(1 for c in complexities if 0.3 <= c < 0.7),
                'high_complexity': sum(1 for c in complexities if c >= 0.7)
            },
            'tier3_recommended': sum(1 for result in results.values() 
                                   if result.recommendations['processing_tier_recommendation'] == 'tier3')
        }