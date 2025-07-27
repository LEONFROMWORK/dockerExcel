"""
최적화된 다국어 OCR 서비스
기존 MultilingualTwoTierService에 성능 최적화 적용
SOLID 원칙과 Context-first 접근법 기반
"""

import time
import logging
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from app.core.performance_optimization import (
    OCRPerformanceOptimizer,
    OptimizationConfig,
    PerformanceOptimizerFactory
)
from app.services.multilingual_two_tier_service import MultilingualTwoTierService
from app.core.ocr_interfaces import ProcessingResult

logger = logging.getLogger(__name__)

@dataclass
class OptimizedProcessingResult(ProcessingResult):
    """최적화된 처리 결과"""
    optimization_stats: Dict[str, Any] = None
    cache_used: bool = False
    processing_time_breakdown: Dict[str, float] = None

class OptimizedMultilingualOCRService:
    """최적화된 다국어 OCR 서비스 - 성능 최적화 통합"""
    
    def __init__(self, optimization_level: str = "standard"):
        # 기존 서비스 초기화
        self.base_service = MultilingualTwoTierService()
        
        # 성능 최적화 시스템 초기화
        self.optimizer = PerformanceOptimizerFactory.create_optimizer(optimization_level)
        
        # 이미지 전처리 캐시
        self.preprocessing_cache = {}
        
        # 배치 처리 설정
        self.batch_processing_enabled = True
        self.current_batch = []
        self.batch_size = 8
        
        logger.info(f"최적화된 다국어 OCR 서비스 초기화 완료 (레벨: {optimization_level})")
    
    def _generate_cache_key(self, image_path: str, language: str, context: List[str]) -> str:
        """캐시 키 생성 - 이미지 해시 + 설정 해시"""
        try:
            # 이미지 파일 해시
            with open(image_path, 'rb') as f:
                image_hash = hashlib.md5(f.read()).hexdigest()
            
            # 설정 해시
            config_str = f"{language}:{':'.join(sorted(context))}"
            config_hash = hashlib.md5(config_str.encode()).hexdigest()
            
            return f"ocr_{image_hash}_{config_hash}"
        
        except Exception as e:
            logger.warning(f"캐시 키 생성 실패: {e}")
            return f"ocr_fallback_{int(time.time())}"
    
    def _optimize_image_preprocessing(self, image_path: str) -> Dict[str, Any]:
        """이미지 전처리 최적화 - 중복 전처리 방지"""
        preprocessing_key = f"preprocess_{hashlib.md5(image_path.encode()).hexdigest()}"
        
        # 전처리 결과 캐시 확인
        if preprocessing_key in self.preprocessing_cache:
            logger.debug(f"전처리 캐시 히트: {image_path}")
            return self.preprocessing_cache[preprocessing_key]
        
        timing_id = self.optimizer.start_operation_timing("image_preprocessing")
        
        try:
            # 실제 전처리 로직 (간소화된 버전)
            import cv2
            image = cv2.imread(image_path)
            
            if image is None:
                raise ValueError(f"이미지 로드 실패: {image_path}")
            
            # 기본 전처리
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            height, width = gray.shape
            
            preprocessing_result = {
                'image_size': (width, height),
                'image_path': image_path,
                'complexity_score': self._calculate_image_complexity(gray),
                'preprocessing_time': self.optimizer.end_operation_timing(timing_id)
            }
            
            # 캐시에 저장 (메모리 사용량 고려하여 결과만 저장)
            self.preprocessing_cache[preprocessing_key] = preprocessing_result
            
            return preprocessing_result
        
        except Exception as e:
            self.optimizer.end_operation_timing(timing_id)
            logger.error(f"이미지 전처리 실패: {e}")
            return {'error': str(e)}
    
    def _calculate_image_complexity(self, gray_image) -> float:
        """이미지 복잡도 계산 - 벡터화된 연산 사용"""
        try:
            import cv2
            import numpy as np
            
            # 에지 밀도 계산 (벡터화)
            edges = cv2.Canny(gray_image, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            # 텍스처 복잡도 (간단한 분산 기반)
            texture_complexity = np.std(gray_image) / 255.0
            
            # 전체 복잡도 점수
            complexity = (edge_density * 0.6 + texture_complexity * 0.4)
            
            return min(complexity, 1.0)
        
        except Exception as e:
            logger.warning(f"복잡도 계산 실패: {e}")
            return 0.5  # 기본값
    
    def process_image(
        self, 
        image_path: str, 
        language: str = "auto",
        context_tags: List[str] = None
    ) -> OptimizedProcessingResult:
        """최적화된 이미지 처리"""
        
        context_tags = context_tags or []
        overall_timing_id = self.optimizer.start_operation_timing("total_processing")
        
        # 처리 시간 세부 분석
        time_breakdown = {}
        
        try:
            # 1. 캐시 확인
            cache_timing_id = self.optimizer.start_operation_timing("cache_lookup")
            cache_key = self._generate_cache_key(image_path, language, context_tags)
            cached_result = self.optimizer.get_cached_result(cache_key)
            time_breakdown['cache_lookup'] = self.optimizer.end_operation_timing(cache_timing_id)
            
            if cached_result:
                logger.info(f"캐시 히트: {image_path}")
                cached_result.cache_used = True
                cached_result.processing_time_breakdown = time_breakdown
                return cached_result
            
            # 2. 이미지 전처리 최적화
            preprocess_timing_id = self.optimizer.start_operation_timing("preprocessing")
            preprocessing_result = self._optimize_image_preprocessing(image_path)
            time_breakdown['preprocessing'] = self.optimizer.end_operation_timing(preprocess_timing_id)
            
            if 'error' in preprocessing_result:
                return OptimizedProcessingResult(
                    success=False,
                    error_message=preprocessing_result['error'],
                    processing_time_breakdown=time_breakdown
                )
            
            # 3. 기존 OCR 서비스 호출
            ocr_timing_id = self.optimizer.start_operation_timing("ocr_processing")
            
            # MultilingualTwoTierService 호출
            base_result = self.base_service.process_image(
                image_path=image_path,
                target_language=language,
                context_tags=context_tags
            )
            
            time_breakdown['ocr_processing'] = self.optimizer.end_operation_timing(ocr_timing_id)
            
            # 4. 결과 후처리 최적화
            postprocess_timing_id = self.optimizer.start_operation_timing("postprocessing")
            
            # 텍스트 배치 분석 (벡터화된 처리)
            if base_result.get('success') and base_result.get('data', {}).get('detected_texts'):
                detected_texts = base_result['data']['detected_texts']
                text_list = [item.get('text', '') for item in detected_texts]
                
                # 최적화된 텍스트 분석
                text_analysis = self.optimizer.optimize_text_batch(text_list)
            else:
                text_analysis = {}
            
            time_breakdown['postprocessing'] = self.optimizer.end_operation_timing(postprocess_timing_id)
            
            # 5. 최적화된 결과 구성
            total_time = self.optimizer.end_operation_timing(overall_timing_id)
            
            optimized_result = OptimizedProcessingResult(
                success=base_result.get('success', False),
                data=base_result.get('data', {}),
                error_message=base_result.get('error'),
                processing_metadata={
                    **base_result.get('processing_metadata', {}),
                    'optimization_applied': True,
                    'preprocessing_stats': preprocessing_result,
                    'text_analysis': text_analysis,
                    'total_processing_time': total_time
                },
                optimization_stats=self.optimizer.get_performance_summary(),
                cache_used=False,
                processing_time_breakdown=time_breakdown
            )
            
            # 6. 결과 캐싱
            cache_timing_id = self.optimizer.start_operation_timing("cache_storage")
            self.optimizer.cache_result(cache_key, optimized_result)
            time_breakdown['cache_storage'] = self.optimizer.end_operation_timing(cache_timing_id)
            
            return optimized_result
        
        except Exception as e:
            self.optimizer.end_operation_timing(overall_timing_id)
            logger.error(f"최적화된 OCR 처리 실패: {e}")
            
            return OptimizedProcessingResult(
                success=False,
                error_message=str(e),
                processing_time_breakdown=time_breakdown
            )
    
    def process_image_batch(
        self, 
        image_paths: List[str], 
        language: str = "auto",
        context_tags: List[str] = None
    ) -> List[OptimizedProcessingResult]:
        """배치 이미지 처리 - 메모리 및 I/O 최적화"""
        
        if not image_paths:
            return []
        
        batch_timing_id = self.optimizer.start_operation_timing("batch_processing")
        context_tags = context_tags or []
        
        try:
            results = []
            
            # 배치 단위로 처리
            for i in range(0, len(image_paths), self.batch_size):
                batch_paths = image_paths[i:i + self.batch_size]
                
                batch_results = []
                for image_path in batch_paths:
                    result = self.process_image(image_path, language, context_tags)
                    batch_results.append(result)
                
                results.extend(batch_results)
                
                # 메모리 정리 (가비지 컬렉션 힌트)
                if i % (self.batch_size * 4) == 0:
                    import gc
                    gc.collect()
            
            processing_time = self.optimizer.end_operation_timing(batch_timing_id)
            logger.info(f"배치 처리 완료: {len(image_paths)}개 이미지, {processing_time:.2f}초")
            
            return results
        
        except Exception as e:
            self.optimizer.end_operation_timing(batch_timing_id)
            logger.error(f"배치 처리 실패: {e}")
            return []
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """최적화 통계 정보"""
        base_stats = self.optimizer.get_performance_summary()
        
        additional_stats = {
            'preprocessing_cache_size': len(self.preprocessing_cache),
            'batch_processing_enabled': self.batch_processing_enabled,
            'batch_size': self.batch_size,
            'service_type': 'OptimizedMultilingualOCRService'
        }
        
        return {**base_stats, **additional_stats}
    
    def clear_caches(self) -> None:
        """모든 캐시 정리"""
        self.preprocessing_cache.clear()
        if hasattr(self.optimizer, 'cache') and self.optimizer.cache:
            self.optimizer.cache.clear()
        logger.info("모든 캐시가 정리되었습니다.")
    
    def update_optimization_config(self, new_config: OptimizationConfig) -> None:
        """최적화 설정 업데이트"""
        # 기존 최적화기 정리
        self.optimizer.cleanup()
        
        # 새로운 설정으로 최적화기 재생성
        self.optimizer = PerformanceOptimizerFactory.create_optimizer(
            custom_config=new_config
        )
        
        logger.info(f"최적화 설정 업데이트 완료: {new_config}")
    
    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.optimizer.cleanup()
        except:
            pass