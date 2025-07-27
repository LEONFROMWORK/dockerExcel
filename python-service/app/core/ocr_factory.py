"""
OCR 시스템 팩토리 및 레지스트리
Open/Closed Principle과 Dependency Inversion Principle 구현
"""

import importlib
import logging
from typing import Dict, List, Optional, Type, Any, Protocol
from abc import ABC, abstractmethod

from .ocr_interfaces import (
    OCRProcessor, TextCorrector, DocumentAnalyzer, CacheProvider, MetricsCollector,
    OCROptions, OCRResult, CorrectionContext, CorrectionResult,
    LanguageCode, ProcessingTier, DocumentType
)
from .ocr_config import get_config_manager, OCREngineConfig

logger = logging.getLogger(__name__)


class OCREngineRegistry:
    """OCR 엔진 레지스트리 - 플러그인 아키텍처 구현"""
    
    def __init__(self):
        self._processors: Dict[str, Type[OCRProcessor]] = {}
        self._correctors: Dict[str, Type[TextCorrector]] = {}
        self._analyzers: Dict[str, Type[DocumentAnalyzer]] = {}
        self._instances: Dict[str, Any] = {}  # 싱글톤 인스턴스 캐시
    
    def register_processor(self, name: str, processor_class: Type[OCRProcessor]):
        """OCR 처리기 등록"""
        self._processors[name] = processor_class
        logger.info(f"OCR processor registered: {name}")
    
    def register_corrector(self, name: str, corrector_class: Type[TextCorrector]):
        """텍스트 교정기 등록"""
        self._correctors[name] = corrector_class
        logger.info(f"Text corrector registered: {name}")
    
    def register_analyzer(self, name: str, analyzer_class: Type[DocumentAnalyzer]):
        """문서 분석기 등록"""
        self._analyzers[name] = analyzer_class
        logger.info(f"Document analyzer registered: {name}")
    
    def get_processor_class(self, name: str) -> Optional[Type[OCRProcessor]]:
        """OCR 처리기 클래스 조회"""
        return self._processors.get(name)
    
    def get_corrector_class(self, name: str) -> Optional[Type[TextCorrector]]:
        """텍스트 교정기 클래스 조회"""
        return self._correctors.get(name)
    
    def get_analyzer_class(self, name: str) -> Optional[Type[DocumentAnalyzer]]:
        """문서 분석기 클래스 조회"""
        return self._analyzers.get(name)
    
    def list_processors(self) -> List[str]:
        """등록된 OCR 처리기 목록"""
        return list(self._processors.keys())
    
    def list_correctors(self) -> List[str]:
        """등록된 텍스트 교정기 목록"""
        return list(self._correctors.keys())
    
    def list_analyzers(self) -> List[str]:
        """등록된 문서 분석기 목록"""
        return list(self._analyzers.keys())


class DependencyContainer:
    """의존성 주입 컨테이너"""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, callable] = {}
    
    def register_singleton(self, service_type: Type, instance: Any):
        """싱글톤 서비스 등록"""
        self._services[service_type] = instance
    
    def register_factory(self, service_type: Type, factory: callable):
        """팩토리 함수 등록"""
        self._factories[service_type] = factory
    
    def get(self, service_type: Type) -> Any:
        """서비스 인스턴스 조회"""
        # 싱글톤 인스턴스 확인
        if service_type in self._services:
            return self._services[service_type]
        
        # 팩토리 함수로 생성
        if service_type in self._factories:
            instance = self._factories[service_type]()
            return instance
        
        raise ValueError(f"Service not registered: {service_type}")
    
    def get_optional(self, service_type: Type) -> Optional[Any]:
        """옵셔널 서비스 조회"""
        try:
            return self.get(service_type)
        except ValueError:
            return None


class OCRServiceFactory:
    """OCR 서비스 팩토리 - 설정 기반 서비스 생성"""
    
    def __init__(self, registry: OCREngineRegistry, container: DependencyContainer):
        self.registry = registry
        self.container = container
        self.config_manager = get_config_manager()
        self._load_engines_from_config()
    
    def _load_engines_from_config(self):
        """설정에서 엔진 로드 및 등록"""
        try:
            config = self.config_manager.get_config()
            
            for engine_config in config.engines:
                if not engine_config.enabled:
                    continue
                
                try:
                    # 동적 클래스 로드
                    module_path, class_name = engine_config.engine_class.rsplit('.', 1)
                    module = importlib.import_module(module_path)
                    engine_class = getattr(module, class_name)
                    
                    # 레지스트리에 등록
                    self.registry.register_processor(engine_config.engine_name, engine_class)
                    
                    logger.info(f"Loaded OCR engine: {engine_config.engine_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to load engine {engine_config.engine_name}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to load engines from config: {e}")
    
    def create_processor(self, engine_name: str, **kwargs) -> Optional[OCRProcessor]:
        """OCR 처리기 생성"""
        processor_class = self.registry.get_processor_class(engine_name)
        if not processor_class:
            logger.error(f"OCR processor not found: {engine_name}")
            return None
        
        try:
            # 의존성 주입
            cache_provider = self.container.get_optional(CacheProvider)
            metrics_collector = self.container.get_optional(MetricsCollector)
            
            # 엔진별 설정 조회
            engine_config = self.config_manager.get_engine_config(engine_name)
            config_params = engine_config.config if engine_config else {}
            
            # 파라미터 병합
            params = {**config_params, **kwargs}
            if cache_provider:
                params['cache_provider'] = cache_provider
            if metrics_collector:
                params['metrics_collector'] = metrics_collector
            
            return processor_class(**params)
            
        except Exception as e:
            logger.error(f"Failed to create processor {engine_name}: {e}")
            return None
    
    def create_corrector(self, corrector_name: str, **kwargs) -> Optional[TextCorrector]:
        """텍스트 교정기 생성"""
        corrector_class = self.registry.get_corrector_class(corrector_name)
        if not corrector_class:
            logger.error(f"Text corrector not found: {corrector_name}")
            return None
        
        try:
            metrics_collector = self.container.get_optional(MetricsCollector)
            params = kwargs.copy()
            if metrics_collector:
                params['metrics_collector'] = metrics_collector
            
            return corrector_class(**params)
            
        except Exception as e:
            logger.error(f"Failed to create corrector {corrector_name}: {e}")
            return None
    
    def create_analyzer(self, analyzer_name: str, **kwargs) -> Optional[DocumentAnalyzer]:
        """문서 분석기 생성"""
        analyzer_class = self.registry.get_analyzer_class(analyzer_name)
        if not analyzer_class:
            logger.error(f"Document analyzer not found: {analyzer_name}")
            return None
        
        try:
            return analyzer_class(**kwargs)
        except Exception as e:
            logger.error(f"Failed to create analyzer {analyzer_name}: {e}")
            return None
    
    def create_best_processor_for_document(self, document_type: DocumentType, 
                                         language: LanguageCode) -> Optional[OCRProcessor]:
        """문서 타입과 언어에 최적화된 처리기 생성"""
        preferred_engines = self.config_manager.get_preferred_engines_for_document(document_type)
        
        for engine_name in preferred_engines:
            processor = self.create_processor(engine_name)
            if processor and processor.supports_language(language):
                logger.info(f"Selected processor {engine_name} for {document_type.value} in {language.value}")
                return processor
        
        # fallback: 첫 번째 사용 가능한 처리기
        enabled_engines = self.config_manager.get_enabled_engines()
        for engine_config in enabled_engines:
            processor = self.create_processor(engine_config.engine_name)
            if processor and processor.supports_language(language):
                logger.warning(f"Fallback to processor {engine_config.engine_name}")
                return processor
        
        logger.error(f"No suitable processor found for {document_type.value} in {language.value}")
        return None


class TextCorrectionPipeline:
    """텍스트 교정 파이프라인 - 여러 교정기를 순차적으로 적용"""
    
    def __init__(self, correctors: List[TextCorrector]):
        self.correctors = correctors
    
    async def correct(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """파이프라인을 통한 순차적 교정"""
        current_text = text
        all_corrections = []
        overall_confidence = 1.0
        processing_time = 0.0
        method_used = "pipeline"
        
        for corrector in self.correctors:
            if not corrector.supports_language(context.language):
                continue
            
            try:
                result = await corrector.correct_text(current_text, context)
                
                current_text = result.corrected_text
                all_corrections.extend(result.corrections)
                overall_confidence *= result.overall_confidence
                processing_time += result.processing_time
                
                # 컨텍스트 업데이트 (교정된 텍스트로)
                context.surrounding_text = current_text
                
            except Exception as e:
                logger.error(f"Correction failed in pipeline: {e}")
                continue
        
        return CorrectionResult(
            corrected_text=current_text,
            corrections=all_corrections,
            overall_confidence=overall_confidence,
            method_used=method_used,
            processing_time=processing_time
        )


class OCROrchestrator:
    """OCR 오케스트레이터 - 전체 OCR 프로세스 조율"""
    
    def __init__(self, factory: OCRServiceFactory):
        self.factory = factory
        self.config_manager = get_config_manager()
    
    async def process_document(self, image_path: str, options: OCROptions) -> OCRResult:
        """문서 처리 전체 흐름 조율"""
        try:
            # 1. 문서 타입 결정 (간단한 휴리스틱)
            document_type = self._determine_document_type(image_path, options)
            
            # 2. 최적 OCR 처리기 선택
            processor = self.factory.create_best_processor_for_document(document_type, options.language)
            if not processor:
                raise ValueError(f"No suitable processor found for {document_type}")
            
            # 3. OCR 처리
            ocr_result = await processor.process_image(image_path, options)
            
            if not ocr_result.success:
                return ocr_result
            
            # 4. 텍스트 교정 (활성화된 경우)
            if options.correction_enabled:
                corrected_result = await self._apply_text_correction(
                    ocr_result, document_type, options
                )
                ocr_result = corrected_result
            
            # 5. 문서 분석 (테이블, 구조 등)
            if options.detect_tables or options.detect_charts:
                analyzed_result = await self._analyze_document_structure(
                    ocr_result, image_path, options
                )
                ocr_result = analyzed_result
            
            ocr_result.document_type = document_type
            return ocr_result
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return OCRResult(
                text="",
                confidence=0.0,
                success=False,
                error_message=str(e),
                document_type=DocumentType.UNKNOWN
            )
    
    def _determine_document_type(self, image_path: str, options: OCROptions) -> DocumentType:
        """문서 타입 결정 (간단한 휴리스틱)"""
        # 컨텍스트 태그 기반 추정
        for tag in options.context_tags:
            if 'financial' in tag.lower() or 'statement' in tag.lower():
                return DocumentType.FINANCIAL_STATEMENT
            elif 'invoice' in tag.lower():
                return DocumentType.INVOICE
            elif 'contract' in tag.lower():
                return DocumentType.CONTRACT
            elif 'table' in tag.lower():
                return DocumentType.TABLE
            elif 'chart' in tag.lower():
                return DocumentType.CHART
        
        # 파일명 기반 추정
        filename = image_path.lower()
        if any(keyword in filename for keyword in ['balance', 'income', 'statement', 'financial']):
            return DocumentType.FINANCIAL_STATEMENT
        elif any(keyword in filename for keyword in ['invoice', 'bill', 'receipt']):
            return DocumentType.INVOICE
        elif any(keyword in filename for keyword in ['contract', 'agreement']):
            return DocumentType.CONTRACT
        
        return DocumentType.UNKNOWN
    
    async def _apply_text_correction(self, ocr_result: OCRResult, 
                                   document_type: DocumentType, 
                                   options: OCROptions) -> OCRResult:
        """텍스트 교정 적용"""
        try:
            # 교정 컨텍스트 생성
            from .ocr_interfaces import create_correction_context
            context = create_correction_context(
                document_type=document_type,
                language=options.language,
                surrounding_text=ocr_result.text
            )
            
            # 교정기 생성
            correction_method = options.correction_method.value
            corrector = self.factory.create_corrector(correction_method)
            
            if corrector:
                correction_result = await corrector.correct_text(ocr_result.text, context)
                ocr_result.text = correction_result.corrected_text
                ocr_result.corrections = correction_result.corrections
                ocr_result.confidence *= correction_result.overall_confidence
            
            return ocr_result
            
        except Exception as e:
            logger.error(f"Text correction failed: {e}")
            return ocr_result
    
    async def _analyze_document_structure(self, ocr_result: OCRResult, 
                                        image_path: str, 
                                        options: OCROptions) -> OCRResult:
        """문서 구조 분석"""
        try:
            # 문서 분석기 생성 (기본 분석기 사용)
            analyzer = self.factory.create_analyzer("default_analyzer")
            
            if analyzer:
                if options.detect_tables:
                    tables = analyzer.extract_tables(ocr_result.text, image_path)
                    ocr_result.tables.extend(tables)
            
            return ocr_result
            
        except Exception as e:
            logger.error(f"Document structure analysis failed: {e}")
            return ocr_result


# 전역 인스턴스들
_registry: Optional[OCREngineRegistry] = None
_container: Optional[DependencyContainer] = None
_factory: Optional[OCRServiceFactory] = None
_orchestrator: Optional[OCROrchestrator] = None


def get_ocr_registry() -> OCREngineRegistry:
    """전역 OCR 레지스트리 반환"""
    global _registry
    if _registry is None:
        _registry = OCREngineRegistry()
    return _registry


def get_dependency_container() -> DependencyContainer:
    """전역 의존성 컨테이너 반환"""
    global _container
    if _container is None:
        _container = DependencyContainer()
    return _container


def get_ocr_factory() -> OCRServiceFactory:
    """전역 OCR 팩토리 반환"""
    global _factory
    if _factory is None:
        registry = get_ocr_registry()
        container = get_dependency_container()
        _factory = OCRServiceFactory(registry, container)
    return _factory


def get_ocr_orchestrator() -> OCROrchestrator:
    """전역 OCR 오케스트레이터 반환"""
    global _orchestrator
    if _orchestrator is None:
        factory = get_ocr_factory()
        _orchestrator = OCROrchestrator(factory)
    return _orchestrator


def setup_default_services():
    """기본 서비스들 설정"""
    container = get_dependency_container()
    
    # 기본 캐시 제공자 등록 (옵셔널)
    try:
        from app.services.ocr_cache_service import OCRCacheService
        cache_service = OCRCacheService()
        container.register_singleton(CacheProvider, cache_service)
    except ImportError:
        logger.warning("OCR cache service not available")
    
    # 기본 메트릭 수집기 등록 (옵셔널)
    try:
        from app.services.real_time_monitoring_service import get_monitoring_service
        monitoring_service = get_monitoring_service()
        if hasattr(monitoring_service, 'ocr_collector'):
            container.register_singleton(MetricsCollector, monitoring_service.ocr_collector)
    except ImportError:
        logger.warning("Metrics collector not available")


# 초기화 함수
def initialize_ocr_system():
    """OCR 시스템 초기화"""
    logger.info("Initializing OCR system...")
    
    # 기본 서비스 설정
    setup_default_services()
    
    # 팩토리 초기화 (설정에서 엔진 로드)
    get_ocr_factory()
    
    logger.info("OCR system initialized successfully")