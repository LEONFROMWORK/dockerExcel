"""
OCR 서비스 팩토리
Factory Pattern + Dependency Injection 적용
"""

import logging
from typing import Dict, Type, Optional, Any, List
from dataclasses import dataclass
from enum import Enum

from ..core.dependency_injection import DIContainer, resolve_service, register_service
from ..core.ocr_interfaces import OCRProcessor, TextCorrector, DocumentAnalyzer, OCROptions
from ..services.complexity_analyzers.image_complexity_analyzer import ImageComplexityAnalyzer
from ..services.decision_engines.ocr_decision_engine import OCRDecisionEngine
from ..services.tier_processors.tier2_processor import Tier2Processor
from ..services.tier_processors.tier3_processor import Tier3Processor
from ..services.result_aggregators.result_aggregator import ResultAggregator

logger = logging.getLogger(__name__)


class ProcessingStrategy(Enum):
    """OCR 처리 전략"""
    SINGLE_TIER = "single_tier"
    TWO_TIER = "two_tier"
    THREE_TIER = "three_tier"
    ADAPTIVE = "adaptive"


@dataclass
class OCRServiceConfiguration:
    """OCR 서비스 설정"""
    strategy: ProcessingStrategy = ProcessingStrategy.ADAPTIVE
    enable_caching: bool = True
    enable_preprocessing: bool = True
    enable_postprocessing: bool = True
    default_language: str = "korean"
    quality_threshold: float = 0.85
    complexity_threshold: float = 0.7
    max_retry_attempts: int = 3
    enable_metrics: bool = True


class OCRServiceFactory:
    """OCR 서비스 팩토리 - SOLID 원칙 적용"""
    
    def __init__(self, container: Optional[DIContainer] = None):
        """
        초기화
        
        Args:
            container: 의존성 주입 컨테이너
        """
        self.container = container or DIContainer()
        self._register_default_services()
        
        # 지원되는 처리 전략
        self.supported_strategies = {
            ProcessingStrategy.SINGLE_TIER: self._create_single_tier_processor,
            ProcessingStrategy.TWO_TIER: self._create_two_tier_processor,
            ProcessingStrategy.THREE_TIER: self._create_three_tier_processor,
            ProcessingStrategy.ADAPTIVE: self._create_adaptive_processor
        }
        
        # 언어별 기본 설정
        self.language_configs = {
            'korean': {
                'complexity_threshold': 0.7,
                'quality_threshold': 0.85,
                'preferred_models': ['paddle_korean', 'openai_vision']
            },
            'english': {
                'complexity_threshold': 0.6,
                'quality_threshold': 0.9,
                'preferred_models': ['tesseract', 'paddle_english']
            },
            'chinese': {
                'complexity_threshold': 0.75,
                'quality_threshold': 0.8,
                'preferred_models': ['paddle_chinese', 'openai_vision']
            },
            'japanese': {
                'complexity_threshold': 0.8,
                'quality_threshold': 0.8,
                'preferred_models': ['paddle_japanese', 'openai_vision']
            }
        }
    
    def create_ocr_service(self, config: OCRServiceConfiguration) -> 'OCRService':
        """OCR 서비스 생성"""
        try:
            # 전략에 따른 처리기 생성
            if config.strategy not in self.supported_strategies:
                raise ValueError(f"Unsupported strategy: {config.strategy}")
            
            processor = self.supported_strategies[config.strategy](config)
            
            # OCR 서비스 생성
            service = OCRService(
                processor=processor,
                config=config,
                container=self.container
            )
            
            logger.info(f"Created OCR service with strategy: {config.strategy}")
            return service
            
        except Exception as e:
            logger.error(f"Failed to create OCR service: {e}")
            raise
    
    def _register_default_services(self) -> None:
        """기본 서비스들 등록"""
        # 복잡도 분석기 등록
        if not self.container.is_registered(ImageComplexityAnalyzer):
            self.container.register(
                ImageComplexityAnalyzer,
                lambda: ImageComplexityAnalyzer()
            )
        
        # 결정 엔진 등록
        if not self.container.is_registered(OCRDecisionEngine):
            self.container.register(
                OCRDecisionEngine,
                lambda: OCRDecisionEngine()
            )
        
        # Tier 2 처리기 등록
        if not self.container.is_registered(Tier2Processor):
            self.container.register(
                Tier2Processor,
                lambda: Tier2Processor()
            )
        
        # Tier 3 처리기 등록
        if not self.container.is_registered(Tier3Processor):
            self.container.register(
                Tier3Processor,
                lambda: Tier3Processor()
            )
        
        # 결과 집계기 등록
        if not self.container.is_registered(ResultAggregator):
            self.container.register(
                ResultAggregator,
                lambda: ResultAggregator()
            )
    
    def _create_single_tier_processor(self, config: OCRServiceConfiguration) -> 'SingleTierProcessor':
        """단일 계층 처리기 생성"""
        return SingleTierProcessor(
            tier2_processor=self.container.resolve(Tier2Processor),
            config=config
        )
    
    def _create_two_tier_processor(self, config: OCRServiceConfiguration) -> 'TwoTierProcessor':
        """2계층 처리기 생성"""
        return TwoTierProcessor(
            complexity_analyzer=self.container.resolve(ImageComplexityAnalyzer),
            decision_engine=self.container.resolve(OCRDecisionEngine),
            tier2_processor=self.container.resolve(Tier2Processor),
            tier3_processor=self.container.resolve(Tier3Processor),
            result_aggregator=self.container.resolve(ResultAggregator),
            config=config
        )
    
    def _create_three_tier_processor(self, config: OCRServiceConfiguration) -> 'ThreeTierProcessor':
        """3계층 처리기 생성"""
        return ThreeTierProcessor(
            complexity_analyzer=self.container.resolve(ImageComplexityAnalyzer),
            decision_engine=self.container.resolve(OCRDecisionEngine),
            tier2_processor=self.container.resolve(Tier2Processor),
            tier3_processor=self.container.resolve(Tier3Processor),
            result_aggregator=self.container.resolve(ResultAggregator),
            config=config
        )
    
    def _create_adaptive_processor(self, config: OCRServiceConfiguration) -> 'AdaptiveProcessor':
        """적응형 처리기 생성"""
        return AdaptiveProcessor(
            complexity_analyzer=self.container.resolve(ImageComplexityAnalyzer),
            decision_engine=self.container.resolve(OCRDecisionEngine),
            tier2_processor=self.container.resolve(Tier2Processor),
            tier3_processor=self.container.resolve(Tier3Processor),
            result_aggregator=self.container.resolve(ResultAggregator),
            config=config
        )
    
    def get_language_config(self, language: str) -> Dict[str, Any]:
        """언어별 설정 가져오기"""
        return self.language_configs.get(language, self.language_configs['korean'])
    
    def register_custom_processor(self, strategy: ProcessingStrategy, 
                                factory_func: callable) -> None:
        """커스텀 처리기 등록"""
        self.supported_strategies[strategy] = factory_func
        logger.info(f"Registered custom processor for strategy: {strategy}")
    
    def create_configured_service_for_language(self, language: str) -> 'OCRService':
        """언어별 최적화된 서비스 생성"""
        lang_config = self.get_language_config(language)
        
        config = OCRServiceConfiguration(
            strategy=ProcessingStrategy.ADAPTIVE,
            default_language=language,
            quality_threshold=lang_config['quality_threshold'],
            complexity_threshold=lang_config['complexity_threshold']
        )
        
        return self.create_ocr_service(config)


# OCR 처리기 클래스들
class SingleTierProcessor:
    """단일 계층 OCR 처리기"""
    
    def __init__(self, tier2_processor: Tier2Processor, config: OCRServiceConfiguration):
        self.tier2_processor = tier2_processor
        self.config = config
    
    async def process_image(self, image_path: str, options: OCROptions) -> Any:
        """이미지 처리"""
        try:
            result = self.tier2_processor.process_image(image_path, options.context_tags)
            return result
        except Exception as e:
            logger.error(f"Single tier processing failed: {e}")
            raise


class TwoTierProcessor:
    """2계층 OCR 처리기"""
    
    def __init__(self, complexity_analyzer: ImageComplexityAnalyzer,
                 decision_engine: OCRDecisionEngine,
                 tier2_processor: Tier2Processor,
                 tier3_processor: Tier3Processor,
                 result_aggregator: ResultAggregator,
                 config: OCRServiceConfiguration):
        self.complexity_analyzer = complexity_analyzer
        self.decision_engine = decision_engine
        self.tier2_processor = tier2_processor
        self.tier3_processor = tier3_processor
        self.result_aggregator = result_aggregator
        self.config = config
    
    async def process_image(self, image_path: str, options: OCROptions) -> Any:
        """이미지 처리"""
        try:
            # 1. 복잡도 분석
            complexity_result = self.complexity_analyzer.analyze_complexity(
                image_path, options.context_hints
            )
            
            # 2. Tier 2 처리
            tier2_result = self.tier2_processor.process_image(image_path, options.context_tags)
            
            # 3. 업그레이드 결정
            decision = self.decision_engine.should_upgrade_to_tier3(
                tier2_result.__dict__, 
                complexity_result.__dict__,
                options.context_hints
            )
            
            # 4. 필요시 Tier 3 처리
            tier3_result = None
            if decision.should_upgrade:
                tier3_result = self.tier3_processor.process_image(
                    image_path, tier2_result.__dict__, options.context_tags
                )
            
            # 5. 결과 집계
            final_result = self.result_aggregator.aggregate_results(
                tier2_result, tier3_result, complexity_result, decision
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Two tier processing failed: {e}")
            raise


class ThreeTierProcessor:
    """3계층 OCR 처리기 (Tesseract + PaddleOCR + OpenAI)"""
    
    def __init__(self, complexity_analyzer: ImageComplexityAnalyzer,
                 decision_engine: OCRDecisionEngine,
                 tier2_processor: Tier2Processor,
                 tier3_processor: Tier3Processor,
                 result_aggregator: ResultAggregator,
                 config: OCRServiceConfiguration):
        self.complexity_analyzer = complexity_analyzer
        self.decision_engine = decision_engine
        self.tier2_processor = tier2_processor
        self.tier3_processor = tier3_processor
        self.result_aggregator = result_aggregator
        self.config = config
    
    async def process_image(self, image_path: str, options: OCROptions) -> Any:
        """이미지 처리 (3단계)"""
        # 현재는 2계층과 동일하게 구현
        # 향후 Tesseract Tier 1 추가 예정
        return await TwoTierProcessor(
            self.complexity_analyzer,
            self.decision_engine,
            self.tier2_processor,
            self.tier3_processor,
            self.result_aggregator,
            self.config
        ).process_image(image_path, options)


class AdaptiveProcessor:
    """적응형 OCR 처리기"""
    
    def __init__(self, complexity_analyzer: ImageComplexityAnalyzer,
                 decision_engine: OCRDecisionEngine,
                 tier2_processor: Tier2Processor,
                 tier3_processor: Tier3Processor,
                 result_aggregator: ResultAggregator,
                 config: OCRServiceConfiguration):
        self.complexity_analyzer = complexity_analyzer
        self.decision_engine = decision_engine
        self.tier2_processor = tier2_processor
        self.tier3_processor = tier3_processor
        self.result_aggregator = result_aggregator
        self.config = config
    
    async def process_image(self, image_path: str, options: OCROptions) -> Any:
        """적응형 이미지 처리"""
        try:
            # 1. 사전 복잡도 분석으로 전략 결정
            complexity_result = self.complexity_analyzer.analyze_complexity(
                image_path, options.context_hints
            )
            
            # 2. 복잡도에 따른 전략 선택
            if complexity_result.overall_complexity < 0.3:
                # 단순한 문서 - Tier 2만 사용
                tier2_result = self.tier2_processor.process_image(image_path, options.context_tags)
                return self.result_aggregator.aggregate_results(
                    tier2_result, None, complexity_result, None
                )
            
            elif complexity_result.overall_complexity > 0.8:
                # 매우 복잡한 문서 - 바로 Tier 3 사용
                tier3_result = self.tier3_processor.process_image(
                    image_path, None, options.context_tags
                )
                return self.result_aggregator.aggregate_results(
                    None, tier3_result, complexity_result, None
                )
            
            else:
                # 중간 복잡도 - 2단계 처리
                return await TwoTierProcessor(
                    self.complexity_analyzer,
                    self.decision_engine,
                    self.tier2_processor,
                    self.tier3_processor,
                    self.result_aggregator,
                    self.config
                ).process_image(image_path, options)
                
        except Exception as e:
            logger.error(f"Adaptive processing failed: {e}")
            raise


class OCRService:
    """통합 OCR 서비스"""
    
    def __init__(self, processor, config: OCRServiceConfiguration, container: DIContainer):
        self.processor = processor
        self.config = config
        self.container = container
        self.metrics = {'total_processed': 0, 'total_errors': 0}
    
    async def process_image(self, image_path: str, options: Optional[OCROptions] = None) -> Any:
        """이미지 OCR 처리"""
        if options is None:
            options = OCROptions(language=self.config.default_language)
        
        try:
            self.metrics['total_processed'] += 1
            result = await self.processor.process_image(image_path, options)
            return result
            
        except Exception as e:
            self.metrics['total_errors'] += 1
            logger.error(f"OCR service processing failed: {e}")
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 반환"""
        return self.metrics.copy()