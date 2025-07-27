"""
OCR 시스템 핵심 인터페이스 정의
SOLID 원칙 적용을 위한 추상화 레이어

Interface Segregation Principle (ISP): 클라이언트가 사용하지 않는 메서드에 의존하지 않도록 인터페이스 분리
Dependency Inversion Principle (DIP): 구체 클래스가 아닌 추상화에 의존하도록 구조 설계
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ===== 열거형 정의 =====

class ProcessingTier(Enum):
    """OCR 처리 계층"""
    TIER_ONE = "tier_1"      # 기본 Tesseract
    TIER_TWO = "tier_2"      # PaddleOCR 또는 고급 엔진
    TIER_THREE = "tier_3"    # AI/Vision 기반 처리

class LanguageCode(Enum):
    """지원 언어 코드"""
    KOREAN = "kor"
    ENGLISH = "eng"
    CHINESE_SIMPLIFIED = "chi_sim"
    CHINESE_TRADITIONAL = "chi_tra"
    JAPANESE = "jpn"
    SPANISH = "spa"
    PORTUGUESE = "por"
    FRENCH = "fra"
    GERMAN = "deu"
    VIETNAMESE = "vie"
    ITALIAN = "ita"
    ARABIC = "ara"
    AUTO_DETECT = "auto"

class CorrectionMethod(Enum):
    """텍스트 교정 방법"""
    BERT_BASED = "bert"
    OPENAI_GPT = "openai"
    RULE_BASED = "rules"
    HYBRID = "hybrid"

class DocumentType(Enum):
    """문서 타입"""
    FINANCIAL_STATEMENT = "financial_statement"
    INVOICE = "invoice"
    CONTRACT = "contract"
    REPORT = "report"
    FORM = "form"
    TABLE = "table"
    CHART = "chart"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# ===== 데이터 모델 =====

@dataclass
class OCROptions:
    """OCR 처리 옵션 - 모든 OCR 처리에 공통으로 사용"""
    language: LanguageCode = LanguageCode.AUTO_DETECT
    processing_tier: Optional[ProcessingTier] = None  # None이면 자동 결정
    context_tags: List[str] = field(default_factory=list)
    correction_enabled: bool = True
    correction_method: CorrectionMethod = CorrectionMethod.HYBRID
    cache_enabled: bool = True
    timeout_seconds: float = 30.0
    confidence_threshold: float = 0.5
    
    # 고급 옵션
    use_financial_vocabulary: bool = True
    detect_tables: bool = True
    detect_charts: bool = True
    preserve_layout: bool = True


@dataclass
class TableData:
    """테이블 데이터 구조"""
    headers: List[str]
    rows: List[List[str]]
    row_count: int
    column_count: int
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextCorrection:
    """텍스트 교정 정보"""
    original: str
    corrected: str
    confidence: float
    method: CorrectionMethod
    reason: str
    position: Optional[Dict[str, int]] = None  # start, end positions


@dataclass
class ProcessingMetadata:
    """처리 메타데이터"""
    processing_time: float
    processing_tier: ProcessingTier
    model_used: str
    language_detected: LanguageCode
    confidence_score: float
    retry_count: int = 0
    cached: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OCRResult:
    """표준화된 OCR 결과 - 모든 OCR 서비스의 통일된 출력"""
    # 기본 결과
    text: str
    confidence: float
    success: bool
    
    # 구조화된 데이터
    tables: List[TableData] = field(default_factory=list)
    corrections: List[TextCorrection] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    
    # 메타데이터
    metadata: ProcessingMetadata = None
    error_message: Optional[str] = None
    
    # 문서 정보
    document_type: DocumentType = DocumentType.UNKNOWN
    layout_preserved: bool = False


@dataclass
class CorrectionContext:
    """텍스트 교정 컨텍스트"""
    document_type: DocumentType
    language: LanguageCode
    surrounding_text: str
    financial_context: bool = False
    custom_vocabulary: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.7


@dataclass
class CorrectionResult:
    """텍스트 교정 결과"""
    corrected_text: str
    corrections: List[TextCorrection]
    overall_confidence: float
    method_used: CorrectionMethod
    processing_time: float


# ===== 핵심 인터페이스 =====

@runtime_checkable
class OCRProcessor(Protocol):
    """OCR 처리 인터페이스 - 모든 OCR 엔진이 구현해야 할 기본 인터페이스"""
    
    async def process_image(self, image_path: str, options: OCROptions) -> OCRResult:
        """이미지에서 텍스트 추출"""
        ...
    
    def supports_language(self, language: LanguageCode) -> bool:
        """특정 언어 지원 여부 확인"""
        ...
    
    def get_supported_languages(self) -> List[LanguageCode]:
        """지원하는 언어 목록 반환"""
        ...
    
    def get_processing_tier(self) -> ProcessingTier:
        """현재 처리 계층 반환"""
        ...


@runtime_checkable  
class TextCorrector(Protocol):
    """텍스트 교정 인터페이스 - 다양한 교정 방법을 위한 인터페이스"""
    
    async def correct_text(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """텍스트 교정 수행"""
        ...
    
    def supports_language(self, language: LanguageCode) -> bool:
        """특정 언어 교정 지원 여부"""
        ...
    
    def get_correction_method(self) -> CorrectionMethod:
        """교정 방법 반환"""
        ...


@runtime_checkable
class DocumentAnalyzer(Protocol):
    """문서 분석 인터페이스 - 문서 구조 및 타입 분석"""
    
    async def analyze_document_structure(self, image_path: str, text: str) -> Dict[str, Any]:
        """문서 구조 분석"""
        ...
    
    def detect_document_type(self, text: str, image_path: str) -> DocumentType:
        """문서 타입 감지"""
        ...
    
    def extract_tables(self, text: str, image_path: str) -> List[TableData]:
        """테이블 추출"""
        ...


@runtime_checkable
class CacheProvider(Protocol):
    """캐시 제공자 인터페이스"""
    
    async def get(self, key: str) -> Optional[OCRResult]:
        """캐시에서 결과 조회"""
        ...
    
    async def set(self, key: str, result: OCRResult, ttl_seconds: int = 3600) -> bool:
        """캐시에 결과 저장"""
        ...
    
    async def invalidate(self, key: str) -> bool:
        """캐시 무효화"""
        ...


@runtime_checkable
class MetricsCollector(Protocol):
    """메트릭 수집 인터페이스"""
    
    def record_processing_time(self, duration: float, tier: ProcessingTier, language: LanguageCode):
        """처리 시간 기록"""
        ...
    
    def record_accuracy(self, confidence: float, tier: ProcessingTier, language: LanguageCode):
        """정확도 기록"""
        ...
    
    def record_error(self, error_type: str, tier: ProcessingTier, language: LanguageCode):
        """오류 기록"""
        ...


# ===== 추상 기본 클래스 =====

class BaseOCRProcessor(ABC):
    """OCR 처리기 기본 클래스 - 공통 기능 구현"""
    
    def __init__(self, cache_provider: Optional[CacheProvider] = None, 
                 metrics_collector: Optional[MetricsCollector] = None):
        self.cache_provider = cache_provider
        self.metrics_collector = metrics_collector
    
    async def process_image(self, image_path: str, options: OCROptions) -> OCRResult:
        """템플릿 메서드 패턴 - 공통 처리 흐름 정의"""
        start_time = datetime.now()
        
        try:
            # 1. 캐시 확인
            if options.cache_enabled and self.cache_provider:
                cache_key = self._generate_cache_key(image_path, options)
                cached_result = await self.cache_provider.get(cache_key)
                if cached_result:
                    cached_result.metadata.cached = True
                    return cached_result
            
            # 2. 실제 OCR 처리 (하위 클래스에서 구현)
            result = await self._process_image_impl(image_path, options)
            
            # 3. 메트릭 수집
            processing_time = (datetime.now() - start_time).total_seconds()
            if self.metrics_collector:
                self.metrics_collector.record_processing_time(
                    processing_time, 
                    self.get_processing_tier(), 
                    options.language
                )
                self.metrics_collector.record_accuracy(
                    result.confidence, 
                    self.get_processing_tier(), 
                    options.language
                )
            
            # 4. 캐시 저장
            if options.cache_enabled and self.cache_provider and result.success:
                await self.cache_provider.set(cache_key, result)
            
            return result
            
        except Exception as e:
            # 오류 메트릭 수집
            if self.metrics_collector:
                self.metrics_collector.record_error(
                    type(e).__name__, 
                    self.get_processing_tier(), 
                    options.language
                )
            
            return OCRResult(
                text="",
                confidence=0.0,
                success=False,
                error_message=str(e),
                metadata=ProcessingMetadata(
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    processing_tier=self.get_processing_tier(),
                    model_used=self.__class__.__name__,
                    language_detected=options.language,
                    confidence_score=0.0
                )
            )
    
    @abstractmethod
    async def _process_image_impl(self, image_path: str, options: OCROptions) -> OCRResult:
        """실제 OCR 처리 구현 - 하위 클래스에서 구현"""
        pass
    
    @abstractmethod
    def get_processing_tier(self) -> ProcessingTier:
        """처리 계층 반환"""
        pass
    
    def _generate_cache_key(self, image_path: str, options: OCROptions) -> str:
        """캐시 키 생성"""
        import hashlib
        
        # 파일 해시 + 옵션 해시
        with open(image_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        options_str = f"{options.language.value}_{options.processing_tier}_{','.join(options.context_tags)}"
        options_hash = hashlib.md5(options_str.encode()).hexdigest()
        
        return f"{file_hash}_{options_hash}"


class BaseTextCorrector(ABC):
    """텍스트 교정기 기본 클래스"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics_collector = metrics_collector
    
    async def correct_text(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """템플릿 메서드 패턴 - 공통 교정 흐름"""
        start_time = datetime.now()
        
        try:
            result = await self._correct_text_impl(text, context)
            result.processing_time = (datetime.now() - start_time).total_seconds()
            result.method_used = self.get_correction_method()
            
            return result
            
        except Exception as e:
            return CorrectionResult(
                corrected_text=text,  # 원본 텍스트 반환
                corrections=[],
                overall_confidence=0.0,
                method_used=self.get_correction_method(),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
    
    @abstractmethod
    async def _correct_text_impl(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """실제 교정 구현"""
        pass
    
    @abstractmethod
    def get_correction_method(self) -> CorrectionMethod:
        """교정 방법 반환"""
        pass


# ===== 설정 관리 =====

@dataclass
class OCREngineConfig:
    """OCR 엔진 설정"""
    engine_name: str
    engine_class: str
    enabled: bool = True
    priority: int = 0  # 낮을수록 우선순위 높음
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRSystemConfig:
    """OCR 시스템 전체 설정"""
    engines: List[OCREngineConfig] = field(default_factory=list)
    default_language: LanguageCode = LanguageCode.KOREAN
    default_timeout: float = 30.0
    cache_enabled: bool = True
    cache_ttl: int = 3600
    metrics_enabled: bool = True
    
    # 언어별 설정
    language_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 문서 타입별 설정
    document_type_configs: Dict[DocumentType, Dict[str, Any]] = field(default_factory=dict)


# ===== 유틸리티 함수 =====

def create_default_ocr_options(language: str = "auto") -> OCROptions:
    """기본 OCR 옵션 생성"""
    lang_code = LanguageCode.AUTO_DETECT
    if language != "auto":
        try:
            lang_code = LanguageCode(language)
        except ValueError:
            lang_code = LanguageCode.AUTO_DETECT
    
    return OCROptions(
        language=lang_code,
        context_tags=[],
        correction_enabled=True,
        correction_method=CorrectionMethod.HYBRID,
        cache_enabled=True,
        confidence_threshold=0.5
    )


def create_correction_context(document_type: DocumentType, language: LanguageCode, 
                            surrounding_text: str = "") -> CorrectionContext:
    """교정 컨텍스트 생성"""
    return CorrectionContext(
        document_type=document_type,
        language=language,
        surrounding_text=surrounding_text,
        financial_context=(document_type == DocumentType.FINANCIAL_STATEMENT),
        confidence_threshold=0.7
    )