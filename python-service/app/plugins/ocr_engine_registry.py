"""
OCR 엔진 레지스트리
Plugin Architecture + Registry Pattern 적용
"""

import logging
from typing import Dict, Type, Optional, List, Any, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import importlib.util
import inspect
from pathlib import Path

from ..core.ocr_interfaces import OCRProcessor, OCROptions, OCRResult

logger = logging.getLogger(__name__)


class EngineCapability(Enum):
    """엔진 기능"""
    TEXT_RECOGNITION = "text_recognition"
    TABLE_DETECTION = "table_detection"
    FORM_PROCESSING = "form_processing"
    HANDWRITING_RECOGNITION = "handwriting_recognition"
    CHART_ANALYSIS = "chart_analysis"
    MULTILINGUAL_SUPPORT = "multilingual_support"
    HIGH_ACCURACY = "high_accuracy"
    FAST_PROCESSING = "fast_processing"


@dataclass
class EngineMetadata:
    """엔진 메타데이터"""
    name: str
    version: str
    description: str
    author: str
    supported_languages: List[str]
    capabilities: List[EngineCapability]
    performance_rating: float  # 0.0 ~ 1.0
    cost_rating: float  # 0.0 ~ 1.0 (낮을수록 저렴)
    required_dependencies: List[str]
    configuration_schema: Dict[str, Any]


class OCREngine(Protocol):
    """OCR 엔진 프로토콜"""
    
    @property
    def metadata(self) -> EngineMetadata:
        """엔진 메타데이터"""
        ...
    
    def is_available(self) -> bool:
        """엔진 사용 가능 여부"""
        ...
    
    async def process_image(self, image_path: str, options: OCROptions) -> OCRResult:
        """이미지 처리"""
        ...
    
    def configure(self, config: Dict[str, Any]) -> None:
        """엔진 설정"""
        ...


@dataclass
class EngineRegistration:
    """엔진 등록 정보"""
    engine_class: Type[OCREngine]
    metadata: EngineMetadata
    instance: Optional[OCREngine] = None
    enabled: bool = True
    priority: int = 0


class OCREngineRegistry:
    """OCR 엔진 레지스트리 - Plugin Architecture"""
    
    def __init__(self):
        self._engines: Dict[str, EngineRegistration] = {}
        self._default_engine: Optional[str] = None
        self._register_builtin_engines()
    
    def register_engine(self, engine_class: Type[OCREngine], 
                       metadata: Optional[EngineMetadata] = None) -> None:
        """엔진 등록"""
        try:
            # 엔진 클래스 검증
            if not self._validate_engine_class(engine_class):
                raise ValueError(f"Invalid engine class: {engine_class}")
            
            # 메타데이터 추출 또는 사용
            if metadata is None:
                metadata = self._extract_metadata_from_class(engine_class)
            
            # 등록
            registration = EngineRegistration(
                engine_class=engine_class,
                metadata=metadata,
                priority=self._calculate_priority(metadata)
            )
            
            self._engines[metadata.name] = registration
            
            # 기본 엔진 설정
            if self._default_engine is None:
                self._default_engine = metadata.name
            
            logger.info(f"Registered OCR engine: {metadata.name} v{metadata.version}")
            
        except Exception as e:
            logger.error(f"Failed to register engine {engine_class}: {e}")
            raise
    
    def unregister_engine(self, engine_name: str) -> bool:
        """엔진 등록 해제"""
        if engine_name in self._engines:
            del self._engines[engine_name]
            
            # 기본 엔진이 제거된 경우 다른 엔진으로 변경
            if self._default_engine == engine_name:
                self._default_engine = next(iter(self._engines.keys()), None)
            
            logger.info(f"Unregistered OCR engine: {engine_name}")
            return True
        return False
    
    def get_engine(self, engine_name: Optional[str] = None) -> OCREngine:
        """엔진 인스턴스 가져오기"""
        name = engine_name or self._default_engine
        
        if not name or name not in self._engines:
            raise ValueError(f"Engine not found: {name}")
        
        registration = self._engines[name]
        
        if not registration.enabled:
            raise ValueError(f"Engine disabled: {name}")
        
        # 싱글톤 패턴으로 인스턴스 관리
        if registration.instance is None:
            registration.instance = registration.engine_class()
        
        return registration.instance
    
    def find_engines_by_capability(self, capability: EngineCapability) -> List[str]:
        """기능별 엔진 찾기"""
        return [
            name for name, reg in self._engines.items()
            if capability in reg.metadata.capabilities and reg.enabled
        ]
    
    def find_engines_by_language(self, language: str) -> List[str]:
        """언어별 엔진 찾기"""
        return [
            name for name, reg in self._engines.items()
            if language in reg.metadata.supported_languages and reg.enabled
        ]
    
    def get_best_engine_for_task(self, language: str, 
                                capabilities: List[EngineCapability],
                                prefer_accuracy: bool = True) -> Optional[str]:
        """작업에 최적화된 엔진 찾기"""
        candidates = []
        
        for name, reg in self._engines.items():
            if not reg.enabled:
                continue
            
            # 언어 지원 확인
            if language not in reg.metadata.supported_languages:
                continue
            
            # 필요 기능 확인
            if not all(cap in reg.metadata.capabilities for cap in capabilities):
                continue
            
            candidates.append((name, reg))
        
        if not candidates:
            return None
        
        # 성능/비용 기준으로 정렬
        if prefer_accuracy:
            candidates.sort(key=lambda x: x[1].metadata.performance_rating, reverse=True)
        else:
            candidates.sort(key=lambda x: x[1].metadata.cost_rating)
        
        return candidates[0][0]
    
    def enable_engine(self, engine_name: str) -> bool:
        """엔진 활성화"""
        if engine_name in self._engines:
            self._engines[engine_name].enabled = True
            logger.info(f"Enabled engine: {engine_name}")
            return True
        return False
    
    def disable_engine(self, engine_name: str) -> bool:
        """엔진 비활성화"""
        if engine_name in self._engines:
            self._engines[engine_name].enabled = False
            logger.info(f"Disabled engine: {engine_name}")
            return True
        return False
    
    def set_default_engine(self, engine_name: str) -> bool:
        """기본 엔진 설정"""
        if engine_name in self._engines and self._engines[engine_name].enabled:
            self._default_engine = engine_name
            logger.info(f"Set default engine: {engine_name}")
            return True
        return False
    
    def get_engine_info(self, engine_name: str) -> Optional[Dict[str, Any]]:
        """엔진 정보 반환"""
        if engine_name not in self._engines:
            return None
        
        reg = self._engines[engine_name]
        metadata = reg.metadata
        
        return {
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "author": metadata.author,
            "supported_languages": metadata.supported_languages,
            "capabilities": [cap.value for cap in metadata.capabilities],
            "performance_rating": metadata.performance_rating,
            "cost_rating": metadata.cost_rating,
            "enabled": reg.enabled,
            "is_default": engine_name == self._default_engine,
            "available": reg.instance.is_available() if reg.instance else "unknown"
        }
    
    def list_engines(self) -> List[Dict[str, Any]]:
        """모든 엔진 목록"""
        return [
            self.get_engine_info(name) 
            for name in sorted(self._engines.keys())
        ]
    
    def load_plugins_from_directory(self, plugins_dir: Path) -> int:
        """디렉토리에서 플러그인 로드"""
        loaded_count = 0
        
        if not plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return 0
        
        for plugin_file in plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            
            try:
                if self._load_plugin_file(plugin_file):
                    loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_file}: {e}")
        
        logger.info(f"Loaded {loaded_count} plugins from {plugins_dir}")
        return loaded_count
    
    def _register_builtin_engines(self) -> None:
        """내장 엔진들 등록"""
        # Tier2Processor (PaddleOCR) 등록
        self.register_engine(
            Tier2EngineAdapter,
            EngineMetadata(
                name="paddleocr",
                version="2.7.0",
                description="PaddleOCR with PP-Structure support",
                author="PaddlePaddle Team",
                supported_languages=["korean", "english", "chinese", "japanese"],
                capabilities=[
                    EngineCapability.TEXT_RECOGNITION,
                    EngineCapability.TABLE_DETECTION,
                    EngineCapability.MULTILINGUAL_SUPPORT,
                    EngineCapability.FAST_PROCESSING
                ],
                performance_rating=0.8,
                cost_rating=0.1,
                required_dependencies=["paddleocr", "paddlepaddle"],
                configuration_schema={}
            )
        )
        
        # Tier3Processor (OpenAI Vision) 등록
        self.register_engine(
            Tier3EngineAdapter,
            EngineMetadata(
                name="openai_vision",
                version="1.0.0", 
                description="OpenAI GPT-4 Vision for high-accuracy OCR",
                author="OpenAI",
                supported_languages=["korean", "english", "chinese", "japanese", "arabic"],
                capabilities=[
                    EngineCapability.TEXT_RECOGNITION,
                    EngineCapability.TABLE_DETECTION,
                    EngineCapability.FORM_PROCESSING,
                    EngineCapability.CHART_ANALYSIS,
                    EngineCapability.MULTILINGUAL_SUPPORT,
                    EngineCapability.HIGH_ACCURACY
                ],
                performance_rating=0.95,
                cost_rating=0.9,
                required_dependencies=["openai"],
                configuration_schema={}
            )
        )
    
    def _validate_engine_class(self, engine_class: Type) -> bool:
        """엔진 클래스 유효성 검증"""
        # OCREngine 프로토콜 구현 확인
        required_methods = ['metadata', 'is_available', 'process_image', 'configure']
        
        for method_name in required_methods:
            if not hasattr(engine_class, method_name):
                logger.error(f"Engine class missing required method: {method_name}")
                return False
        
        return True
    
    def _extract_metadata_from_class(self, engine_class: Type) -> EngineMetadata:
        """클래스에서 메타데이터 추출"""
        # 기본 메타데이터 (실제로는 클래스의 속성이나 데코레이터에서 추출)
        return EngineMetadata(
            name=engine_class.__name__.lower(),
            version="1.0.0",
            description=engine_class.__doc__ or "Custom OCR Engine",
            author="Unknown",
            supported_languages=["english"],
            capabilities=[EngineCapability.TEXT_RECOGNITION],
            performance_rating=0.5,
            cost_rating=0.5,
            required_dependencies=[],
            configuration_schema={}
        )
    
    def _calculate_priority(self, metadata: EngineMetadata) -> int:
        """엔진 우선순위 계산"""
        # 성능과 기능을 기반으로 우선순위 계산
        priority = int(metadata.performance_rating * 100)
        priority += len(metadata.capabilities) * 10
        priority += len(metadata.supported_languages) * 5
        return priority
    
    def _load_plugin_file(self, plugin_file: Path) -> bool:
        """플러그인 파일 로드"""
        try:
            spec = importlib.util.spec_from_file_location(
                plugin_file.stem, plugin_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 모듈에서 OCREngine 클래스들 찾기
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (hasattr(obj, 'metadata') and 
                    hasattr(obj, 'process_image') and
                    name != 'OCREngine'):
                    self.register_engine(obj)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to load plugin file {plugin_file}: {e}")
            return False


# 내장 엔진 어댑터들
class Tier2EngineAdapter:
    """Tier2Processor 어댑터"""
    
    def __init__(self):
        from ..services.tier_processors.tier2_processor import Tier2Processor
        self._processor = Tier2Processor()
        self._metadata = EngineMetadata(
            name="tier2_paddle",
            version="1.0.0",
            description="Tier 2 PaddleOCR Processor",
            author="Excel Unified Team",
            supported_languages=["korean", "english", "chinese", "japanese"],
            capabilities=[
                EngineCapability.TEXT_RECOGNITION,
                EngineCapability.TABLE_DETECTION,
                EngineCapability.MULTILINGUAL_SUPPORT
            ],
            performance_rating=0.8,
            cost_rating=0.1,
            required_dependencies=["paddleocr"],
            configuration_schema={}
        )
    
    @property
    def metadata(self) -> EngineMetadata:
        return self._metadata
    
    def is_available(self) -> bool:
        return self._processor.is_available()
    
    async def process_image(self, image_path: str, options: OCROptions) -> OCRResult:
        result = self._processor.process_image(image_path, options.context_tags)
        
        # Tier2Result를 OCRResult로 변환
        return OCRResult(
            text=result.text,
            confidence=result.confidence,
            processing_metadata=result.processing_metadata or {},
            bounding_boxes=[],
            language_detected=options.language
        )
    
    def configure(self, config: Dict[str, Any]) -> None:
        # 설정 적용 로직
        pass


class Tier3EngineAdapter:
    """Tier3Processor 어댑터"""
    
    def __init__(self):
        from ..services.tier_processors.tier3_processor import Tier3Processor
        self._processor = Tier3Processor()
        self._metadata = EngineMetadata(
            name="tier3_openai",
            version="1.0.0", 
            description="Tier 3 OpenAI Vision Processor",
            author="Excel Unified Team",
            supported_languages=["korean", "english", "chinese", "japanese", "arabic"],
            capabilities=[
                EngineCapability.TEXT_RECOGNITION,
                EngineCapability.TABLE_DETECTION,
                EngineCapability.FORM_PROCESSING,
                EngineCapability.HIGH_ACCURACY
            ],
            performance_rating=0.95,
            cost_rating=0.9,
            required_dependencies=["openai"],
            configuration_schema={}
        )
    
    @property
    def metadata(self) -> EngineMetadata:
        return self._metadata
    
    def is_available(self) -> bool:
        return self._processor.is_available()
    
    async def process_image(self, image_path: str, options: OCROptions) -> OCRResult:
        result = self._processor.process_image(image_path, None, options.context_tags)
        
        # Tier3Result를 OCRResult로 변환
        return OCRResult(
            text=result.text,
            confidence=result.confidence,
            processing_metadata=result.processing_metadata or {},
            bounding_boxes=[],
            language_detected=options.language
        )
    
    def configure(self, config: Dict[str, Any]) -> None:
        # 설정 적용 로직
        pass


# 글로벌 레지스트리 인스턴스
_global_registry: Optional[OCREngineRegistry] = None


def get_engine_registry() -> OCREngineRegistry:
    """글로벌 엔진 레지스트리 가져오기"""
    global _global_registry
    if _global_registry is None:
        _global_registry = OCREngineRegistry()
    return _global_registry


def register_engine(engine_class: Type[OCREngine], 
                   metadata: Optional[EngineMetadata] = None) -> None:
    """글로벌 레지스트리에 엔진 등록"""
    get_engine_registry().register_engine(engine_class, metadata)


def get_engine(engine_name: Optional[str] = None) -> OCREngine:
    """글로벌 레지스트리에서 엔진 가져오기"""
    return get_engine_registry().get_engine(engine_name)