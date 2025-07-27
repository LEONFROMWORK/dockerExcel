"""
컨텍스추얼 OCR 오케스트레이터
TransformerOCRService에서 분리된 메인 조율 로직
모든 OCR 구성 요소들을 통합하여 컨텍스트 기반 처리 제공
Single Responsibility Principle 적용
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.core.ocr_interfaces import (
    OCRProcessor, TextCorrector, BaseOCRProcessor,
    OCROptions, OCRResult, CorrectionContext, CorrectionResult,
    LanguageCode, DocumentType, ProcessingTier, CorrectionMethod,
    create_correction_context
)

# 분리된 컴포넌트들 import
from app.services.text_correctors.bert_corrector import BERTTextCorrector
from app.services.text_correctors.openai_corrector import OpenAITextCorrector
from app.services.text_correctors.rule_based_corrector import RuleBasedCorrector, FinancialRuleBasedCorrector
from app.services.document_analyzers.document_structure_analyzer import DocumentStructureAnalyzer, DocumentStructure
from app.services.financial_extractors.financial_terms_extractor import FinancialTermsExtractor, FinancialExtraction

logger = logging.getLogger(__name__)


class ProcessingStrategy(Enum):
    """처리 전략"""
    FAST = "fast"  # 빠른 처리 (기본 교정만)
    BALANCED = "balanced"  # 균형 잡힌 처리 (규칙 + BERT)
    COMPREHENSIVE = "comprehensive"  # 완전한 처리 (모든 교정기 + 분석)
    FINANCIAL = "financial"  # 재무 특화 처리


@dataclass
class ProcessingPipeline:
    """처리 파이프라인 정의"""
    correctors: List[str]  # 교정기 이름들
    enable_structure_analysis: bool
    enable_financial_extraction: bool
    enable_parallel_processing: bool
    confidence_threshold: float


@dataclass
class ContextualResult:
    """컨텍스트 기반 OCR 결과"""
    ocr_result: OCRResult
    correction_results: List[CorrectionResult]
    document_structure: Optional[DocumentStructure]
    financial_extraction: Optional[FinancialExtraction]
    processing_metadata: Dict[str, Any]
    overall_confidence: float
    processing_time: float


class ContextualOCROrchestrator(BaseOCRProcessor):
    """컨텍스트 기반 OCR 오케스트레이터 - 전체 처리 흐름 조율"""
    
    def __init__(self, 
                 base_processor: OCRProcessor,
                 cache_provider=None,
                 metrics_collector=None):
        """
        초기화
        
        Args:
            base_processor: 기본 OCR 처리기 (Tesseract, PaddleOCR 등)
            cache_provider: 캐시 제공자
            metrics_collector: 메트릭 수집기
        """
        super().__init__(cache_provider, metrics_collector)
        self.base_processor = base_processor
        
        # 교정기들 초기화
        self.correctors = {
            'rule_based': RuleBasedCorrector(metrics_collector),
            'financial_rule_based': FinancialRuleBasedCorrector(metrics_collector),
            'bert': BERTTextCorrector(metrics_collector),
            'openai': OpenAITextCorrector(metrics_collector)
        }
        
        # 분석기들 초기화
        self.structure_analyzer = DocumentStructureAnalyzer()
        self.financial_extractor = FinancialTermsExtractor()
        
        # 처리 전략별 파이프라인 정의
        self.processing_pipelines = {
            ProcessingStrategy.FAST: ProcessingPipeline(
                correctors=['rule_based'],
                enable_structure_analysis=False,
                enable_financial_extraction=False,
                enable_parallel_processing=True,
                confidence_threshold=0.6
            ),
            ProcessingStrategy.BALANCED: ProcessingPipeline(
                correctors=['rule_based', 'bert'],
                enable_structure_analysis=True,
                enable_financial_extraction=False,
                enable_parallel_processing=True,
                confidence_threshold=0.7
            ),
            ProcessingStrategy.COMPREHENSIVE: ProcessingPipeline(
                correctors=['rule_based', 'bert', 'openai'],
                enable_structure_analysis=True,
                enable_financial_extraction=True,
                enable_parallel_processing=True,
                confidence_threshold=0.8
            ),
            ProcessingStrategy.FINANCIAL: ProcessingPipeline(
                correctors=['financial_rule_based', 'bert', 'openai'],
                enable_structure_analysis=True,
                enable_financial_extraction=True,
                enable_parallel_processing=True,
                confidence_threshold=0.75
            )
        }
    
    async def _process_image_impl(self, image_path: str, options: OCROptions) -> OCRResult:
        """기본 OCR 처리기 인터페이스 구현"""
        contextual_result = await self.process_with_context(image_path, options)
        return contextual_result.ocr_result
    
    async def process_with_context(self, image_path: str, options: OCROptions,
                                 strategy: ProcessingStrategy = ProcessingStrategy.BALANCED) -> ContextualResult:
        """컨텍스트 기반 전체 처리"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 1. 처리 파이프라인 선택
            pipeline = self._select_pipeline(strategy, options)
            
            # 2. 기본 OCR 처리
            logger.info(f"Starting OCR processing with {strategy.value} strategy")
            ocr_result = await self.base_processor.process_image(image_path, options)
            
            if not ocr_result.success:
                return self._create_failed_result(ocr_result, start_time)
            
            # 3. 컨텍스트 생성
            context = self._create_processing_context(ocr_result, options)
            
            # 4. 병렬 처리 vs 순차 처리
            if pipeline.enable_parallel_processing:
                results = await self._process_parallel(ocr_result, context, pipeline, image_path)
            else:
                results = await self._process_sequential(ocr_result, context, pipeline, image_path)
            
            # 5. 결과 통합 및 최종 처리
            final_result = self._integrate_results(ocr_result, results, start_time)
            
            # 6. 품질 검증
            self._validate_final_result(final_result)
            
            logger.info(f"Contextual OCR completed with confidence: {final_result.overall_confidence:.3f}")
            return final_result
            
        except Exception as e:
            logger.error(f"Contextual OCR processing failed: {e}")
            return self._create_error_result(str(e), start_time)
    
    def _select_pipeline(self, strategy: ProcessingStrategy, options: OCROptions) -> ProcessingPipeline:
        """처리 파이프라인 선택"""
        # 기본 전략
        pipeline = self.processing_pipelines[strategy]
        
        # 옵션에 따른 동적 조정
        if options.use_financial_vocabulary:
            # 재무 용어 사용 시 재무 특화 교정기 추가
            if 'financial_rule_based' not in pipeline.correctors:
                pipeline.correctors.insert(0, 'financial_rule_based')
        
        if options.confidence_threshold > pipeline.confidence_threshold:
            # 더 높은 신뢰도 요구 시 더 많은 교정기 사용
            if strategy == ProcessingStrategy.FAST:
                pipeline.correctors.append('bert')
            elif strategy == ProcessingStrategy.BALANCED:
                pipeline.correctors.append('openai')
        
        return pipeline
    
    def _create_processing_context(self, ocr_result: OCRResult, options: OCROptions) -> CorrectionContext:
        """처리 컨텍스트 생성"""
        return create_correction_context(
            document_type=self._determine_document_type(ocr_result.text, options),
            language=options.language,
            surrounding_text=ocr_result.text,
            financial_context=options.use_financial_vocabulary,
            confidence_threshold=options.confidence_threshold,
            custom_vocabulary=getattr(options, 'custom_vocabulary', None)
        )
    
    def _determine_document_type(self, text: str, options: OCROptions) -> DocumentType:
        """문서 타입 결정"""
        # 컨텍스트 태그 기반
        for tag in options.context_tags:
            if 'financial' in tag.lower():
                return DocumentType.FINANCIAL_STATEMENT
            elif 'invoice' in tag.lower():
                return DocumentType.INVOICE
            elif 'contract' in tag.lower():
                return DocumentType.CONTRACT
        
        # 텍스트 내용 기반 추론
        text_lower = text.lower()
        financial_keywords = ['자산', '부채', '자본', '매출', '이익', 'assets', 'liabilities', 'revenue']
        invoice_keywords = ['청구서', '송장', '세금계산서', 'invoice', 'bill']
        contract_keywords = ['계약서', '협약', '약정', 'contract', 'agreement']
        
        if any(keyword in text_lower for keyword in financial_keywords):
            return DocumentType.FINANCIAL_STATEMENT
        elif any(keyword in text_lower for keyword in invoice_keywords):
            return DocumentType.INVOICE
        elif any(keyword in text_lower for keyword in contract_keywords):
            return DocumentType.CONTRACT
        
        return DocumentType.UNKNOWN
    
    async def _process_parallel(self, ocr_result: OCRResult, context: CorrectionContext,
                              pipeline: ProcessingPipeline, image_path: str) -> Dict[str, Any]:
        """병렬 처리"""
        tasks = []
        
        # 텍스트 교정 태스크들
        for corrector_name in pipeline.correctors:
            if corrector_name in self.correctors:
                corrector = self.correctors[corrector_name]
                task = asyncio.create_task(
                    corrector.correct_text(ocr_result.text, context),
                    name=f"correction_{corrector_name}"
                )
                tasks.append(task)
        
        # 문서 구조 분석 태스크
        if pipeline.enable_structure_analysis:
            task = asyncio.create_task(
                self._analyze_structure_async(ocr_result.text, context.language, context.document_type),
                name="structure_analysis"
            )
            tasks.append(task)
        
        # 재무 정보 추출 태스크
        if pipeline.enable_financial_extraction:
            task = asyncio.create_task(
                self._extract_financial_async(ocr_result.text, context.language, context.document_type),
                name="financial_extraction"
            )
            tasks.append(task)
        
        # 모든 태스크 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 분류
        return self._organize_parallel_results(tasks, results, pipeline)
    
    async def _process_sequential(self, ocr_result: OCRResult, context: CorrectionContext,
                                pipeline: ProcessingPipeline, image_path: str) -> Dict[str, Any]:
        """순차 처리"""
        results = {
            'corrections': [],
            'structure_analysis': None,
            'financial_extraction': None
        }
        
        current_text = ocr_result.text
        
        # 순차적 텍스트 교정
        for corrector_name in pipeline.correctors:
            if corrector_name in self.correctors:
                corrector = self.correctors[corrector_name]
                correction_result = await corrector.correct_text(current_text, context)
                results['corrections'].append(correction_result)
                
                # 다음 교정기를 위해 텍스트 업데이트
                if correction_result.overall_confidence > context.confidence_threshold:
                    current_text = correction_result.corrected_text
                    context.surrounding_text = current_text
        
        # 구조 분석
        if pipeline.enable_structure_analysis:
            results['structure_analysis'] = self.structure_analyzer.analyze_document_structure(
                current_text, context.language, context.document_type
            )
        
        # 재무 정보 추출
        if pipeline.enable_financial_extraction:
            results['financial_extraction'] = self.financial_extractor.extract_financial_information(
                current_text, context.language, context.document_type
            )
        
        return results
    
    async def _analyze_structure_async(self, text: str, language: LanguageCode, 
                                     document_type: DocumentType) -> DocumentStructure:
        """비동기 구조 분석"""
        return self.structure_analyzer.analyze_document_structure(text, language, document_type)
    
    async def _extract_financial_async(self, text: str, language: LanguageCode,
                                     document_type: DocumentType) -> FinancialExtraction:
        """비동기 재무 정보 추출"""
        return self.financial_extractor.extract_financial_information(text, language, document_type)
    
    def _organize_parallel_results(self, tasks: List, results: List, 
                                 pipeline: ProcessingPipeline) -> Dict[str, Any]:
        """병렬 처리 결과 정리"""
        organized = {
            'corrections': [],
            'structure_analysis': None,
            'financial_extraction': None
        }
        
        for task, result in zip(tasks, results):
            task_name = task.get_name()
            
            if isinstance(result, Exception):
                logger.error(f"Task {task_name} failed: {result}")
                continue
            
            if task_name.startswith('correction_'):
                organized['corrections'].append(result)
            elif task_name == 'structure_analysis':
                organized['structure_analysis'] = result
            elif task_name == 'financial_extraction':
                organized['financial_extraction'] = result
        
        return organized
    
    def _integrate_results(self, ocr_result: OCRResult, processing_results: Dict[str, Any],
                         start_time: float) -> ContextualResult:
        """결과 통합"""
        # 최고 품질의 교정 결과 선택
        best_correction = self._select_best_correction(processing_results['corrections'])
        
        # 최종 텍스트 결정
        final_text = best_correction.corrected_text if best_correction else ocr_result.text
        
        # OCR 결과 업데이트
        updated_ocr_result = OCRResult(
            text=final_text,
            confidence=ocr_result.confidence,
            success=True,
            metadata=ocr_result.metadata,
            corrections=best_correction.corrections if best_correction else [],
            tables=ocr_result.tables,
            document_type=ocr_result.document_type
        )
        
        # 전체 신뢰도 계산
        overall_confidence = self._calculate_overall_confidence(
            ocr_result, processing_results, best_correction
        )
        
        # 처리 메타데이터
        processing_metadata = {
            'strategy_used': 'contextual_processing',
            'correctors_applied': len(processing_results['corrections']),
            'structure_analyzed': processing_results['structure_analysis'] is not None,
            'financial_extracted': processing_results['financial_extraction'] is not None,
            'processing_time': asyncio.get_event_loop().time() - start_time
        }
        
        return ContextualResult(
            ocr_result=updated_ocr_result,
            correction_results=processing_results['corrections'],
            document_structure=processing_results['structure_analysis'],
            financial_extraction=processing_results['financial_extraction'],
            processing_metadata=processing_metadata,
            overall_confidence=overall_confidence,
            processing_time=processing_metadata['processing_time']
        )
    
    def _select_best_correction(self, corrections: List[CorrectionResult]) -> Optional[CorrectionResult]:
        """최고 품질의 교정 결과 선택"""
        if not corrections:
            return None
        
        # 신뢰도 기반 선택
        best_correction = max(corrections, key=lambda x: x.overall_confidence)
        
        # 최소 임계값 확인
        if best_correction.overall_confidence < 0.5:
            return None
        
        return best_correction
    
    def _calculate_overall_confidence(self, ocr_result: OCRResult, 
                                    processing_results: Dict[str, Any],
                                    best_correction: Optional[CorrectionResult]) -> float:
        """전체 신뢰도 계산"""
        # 기본 OCR 신뢰도
        base_confidence = ocr_result.confidence
        
        # 교정 신뢰도
        correction_confidence = best_correction.overall_confidence if best_correction else 0.0
        
        # 구조 분석 신뢰도
        structure_confidence = 0.0
        if processing_results['structure_analysis']:
            structure_confidence = processing_results['structure_analysis'].layout_confidence
        
        # 재무 추출 신뢰도
        financial_confidence = 0.0
        if processing_results['financial_extraction']:
            financial_confidence = processing_results['financial_extraction'].confidence
        
        # 가중 평균 계산
        weights = [0.4, 0.3, 0.2, 0.1]  # OCR, 교정, 구조, 재무
        confidences = [base_confidence, correction_confidence, structure_confidence, financial_confidence]
        
        # 실제 사용된 컴포넌트만 고려
        used_weights = []
        used_confidences = []
        
        # OCR은 항상 포함
        used_weights.append(weights[0])
        used_confidences.append(confidences[0])
        
        if best_correction:
            used_weights.append(weights[1])
            used_confidences.append(confidences[1])
        
        if processing_results['structure_analysis']:
            used_weights.append(weights[2])
            used_confidences.append(confidences[2])
        
        if processing_results['financial_extraction']:
            used_weights.append(weights[3])
            used_confidences.append(confidences[3])
        
        # 가중치 정규화
        total_weight = sum(used_weights)
        if total_weight == 0:
            return base_confidence
        
        normalized_weights = [w / total_weight for w in used_weights]
        
        return sum(w * c for w, c in zip(normalized_weights, used_confidences))
    
    def _validate_final_result(self, result: ContextualResult):
        """최종 결과 검증"""
        if result.overall_confidence < 0.3:
            logger.warning(f"Low overall confidence: {result.overall_confidence:.3f}")
        
        if result.processing_time > 30.0:  # 30초 초과
            logger.warning(f"Long processing time: {result.processing_time:.2f}s")
        
        # 재무 문서인데 재무 정보가 없는 경우
        if (result.ocr_result.document_type == DocumentType.FINANCIAL_STATEMENT and
            not result.financial_extraction):
            logger.warning("Financial document detected but no financial information extracted")
    
    def _create_failed_result(self, ocr_result: OCRResult, start_time: float) -> ContextualResult:
        """실패 결과 생성"""
        return ContextualResult(
            ocr_result=ocr_result,
            correction_results=[],
            document_structure=None,
            financial_extraction=None,
            processing_metadata={'error': 'OCR processing failed'},
            overall_confidence=0.0,
            processing_time=asyncio.get_event_loop().time() - start_time
        )
    
    def _create_error_result(self, error_message: str, start_time: float) -> ContextualResult:
        """오류 결과 생성"""
        return ContextualResult(
            ocr_result=OCRResult(
                text="",
                confidence=0.0,
                success=False,
                error_message=error_message
            ),
            correction_results=[],
            document_structure=None,
            financial_extraction=None,
            processing_metadata={'error': error_message},
            overall_confidence=0.0,
            processing_time=asyncio.get_event_loop().time() - start_time
        )
    
    def supports_language(self, language: LanguageCode) -> bool:
        """언어 지원 여부 확인"""
        return self.base_processor.supports_language(language)
    
    def get_supported_languages(self) -> List[LanguageCode]:
        """지원 언어 목록"""
        return self.base_processor.get_supported_languages()
    
    def get_processing_tier(self) -> ProcessingTier:
        """처리 계층 반환"""
        return ProcessingTier.TIER_ONE  # 최상위 계층
    
    async def process_batch(self, image_paths: List[str], options: OCROptions,
                          strategy: ProcessingStrategy = ProcessingStrategy.BALANCED) -> List[ContextualResult]:
        """배치 처리"""
        tasks = []
        for image_path in image_paths:
            task = asyncio.create_task(
                self.process_with_context(image_path, options, strategy),
                name=f"batch_process_{image_path}"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch processing failed: {result}")
                final_results.append(self._create_error_result(str(result), 0.0))
            else:
                final_results.append(result)
        
        return final_results
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        metrics = {}
        
        # 개별 교정기 메트릭
        for name, corrector in self.correctors.items():
            if hasattr(corrector, 'get_performance_metrics'):
                metrics[f'{name}_corrector'] = corrector.get_performance_metrics()
        
        # 기본 처리기 메트릭
        if hasattr(self.base_processor, 'get_performance_metrics'):
            metrics['base_processor'] = self.base_processor.get_performance_metrics()
        
        return metrics