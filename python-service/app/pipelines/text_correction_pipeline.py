"""
텍스트 교정 파이프라인
Chain of Responsibility Pattern + Dependency Injection 적용
"""

import logging
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.dependency_injection import DIContainer, resolve_service
from ..core.ocr_interfaces import TextCorrector, CorrectionContext, CorrectionResult
from ..services.text_correctors.rule_based_corrector import RuleBasedCorrector
from ..services.text_correctors.bert_text_corrector import BERTTextCorrector
from ..services.text_correctors.openai_text_corrector import OpenAITextCorrector

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    """파이프라인 단계"""
    name: str
    corrector: TextCorrector
    enabled: bool = True
    priority: int = 0


class TextCorrectionPipeline:
    """텍스트 교정 파이프라인 - SOLID 원칙 적용"""
    
    def __init__(self, container: Optional[DIContainer] = None):
        """
        초기화
        
        Args:
            container: 의존성 주입 컨테이너
        """
        self.container = container or DIContainer()
        self.stages: List[PipelineStage] = []
        self._register_default_correctors()
        self._setup_default_pipeline()
    
    def _register_default_correctors(self) -> None:
        """기본 교정기들 등록"""
        # Rule-based Corrector 등록
        if not self.container.is_registered(RuleBasedCorrector):
            self.container.register(
                RuleBasedCorrector,
                lambda: RuleBasedCorrector()
            )
        
        # BERT Corrector 등록
        if not self.container.is_registered(BERTTextCorrector):
            self.container.register(
                BERTTextCorrector,
                lambda: BERTTextCorrector()
            )
        
        # OpenAI Corrector 등록
        if not self.container.is_registered(OpenAITextCorrector):
            self.container.register(
                OpenAITextCorrector,
                lambda: OpenAITextCorrector()
            )
    
    def _setup_default_pipeline(self) -> None:
        """기본 파이프라인 설정"""
        # 1단계: 규칙 기반 교정 (빠르고 안전)
        self.add_stage(
            "rule_based_correction",
            self.container.resolve(RuleBasedCorrector),
            priority=1
        )
        
        # 2단계: BERT 기반 교정 (중간 수준)
        self.add_stage(
            "bert_correction",
            self.container.resolve(BERTTextCorrector),
            priority=2,
            enabled=False  # 기본적으로 비활성화
        )
        
        # 3단계: OpenAI 교정 (고급, 비용이 높음)
        self.add_stage(
            "openai_correction",
            self.container.resolve(OpenAITextCorrector),
            priority=3,
            enabled=False  # 기본적으로 비활성화
        )
    
    def add_stage(self, name: str, corrector: TextCorrector, 
                  priority: int = 0, enabled: bool = True) -> None:
        """파이프라인 단계 추가"""
        stage = PipelineStage(
            name=name,
            corrector=corrector,
            enabled=enabled,
            priority=priority
        )
        
        self.stages.append(stage)
        # 우선순위 순으로 정렬
        self.stages.sort(key=lambda s: s.priority)
        
        logger.info(f"Added pipeline stage: {name} (priority: {priority})")
    
    def remove_stage(self, name: str) -> bool:
        """파이프라인 단계 제거"""
        for i, stage in enumerate(self.stages):
            if stage.name == name:
                del self.stages[i]
                logger.info(f"Removed pipeline stage: {name}")
                return True
        return False
    
    def enable_stage(self, name: str) -> bool:
        """파이프라인 단계 활성화"""
        for stage in self.stages:
            if stage.name == name:
                stage.enabled = True
                logger.info(f"Enabled pipeline stage: {name}")
                return True
        return False
    
    def disable_stage(self, name: str) -> bool:
        """파이프라인 단계 비활성화"""
        for stage in self.stages:
            if stage.name == name:
                stage.enabled = False
                logger.info(f"Disabled pipeline stage: {name}")
                return True
        return False
    
    async def process_text(self, text: str, context: CorrectionContext) -> CorrectionResult:
        """텍스트 교정 파이프라인 실행"""
        if not text.strip():
            return CorrectionResult(
                corrected_text="",
                confidence=1.0,
                corrections_made=[],
                processing_metadata={"pipeline_stages": []}
            )
        
        current_text = text
        all_corrections = []
        pipeline_metadata = []
        overall_confidence = 1.0
        
        try:
            for stage in self.stages:
                if not stage.enabled:
                    continue
                
                stage_start_time = self._get_current_time()
                
                try:
                    # 각 단계별 교정 실행
                    stage_result = await stage.corrector.correct_text(current_text, context)
                    
                    # 결과 병합
                    if stage_result.corrected_text != current_text:
                        current_text = stage_result.corrected_text
                        all_corrections.extend(stage_result.corrections_made)
                        overall_confidence = min(overall_confidence, stage_result.confidence)
                    
                    # 메타데이터 수집
                    stage_metadata = {
                        "stage_name": stage.name,
                        "processing_time": self._get_current_time() - stage_start_time,
                        "corrections_count": len(stage_result.corrections_made),
                        "confidence": stage_result.confidence,
                        "text_length_before": len(text) if pipeline_metadata == [] else len(pipeline_metadata[-1].get("text_after", text)),
                        "text_length_after": len(stage_result.corrected_text)
                    }
                    pipeline_metadata.append(stage_metadata)
                    
                    logger.debug(f"Pipeline stage {stage.name} completed: {len(stage_result.corrections_made)} corrections")
                    
                except Exception as e:
                    logger.error(f"Pipeline stage {stage.name} failed: {e}")
                    # 에러가 있어도 다음 단계 계속 진행
                    stage_metadata = {
                        "stage_name": stage.name,
                        "error": str(e),
                        "processing_time": self._get_current_time() - stage_start_time
                    }
                    pipeline_metadata.append(stage_metadata)
                    continue
            
            # 최종 결과 생성
            return CorrectionResult(
                corrected_text=current_text,
                confidence=overall_confidence,
                corrections_made=all_corrections,
                processing_metadata={
                    "pipeline_stages": pipeline_metadata,
                    "total_stages_executed": len([s for s in pipeline_metadata if "error" not in s]),
                    "total_corrections": len(all_corrections),
                    "original_length": len(text),
                    "final_length": len(current_text)
                }
            )
            
        except Exception as e:
            logger.error(f"Text correction pipeline failed: {e}")
            return CorrectionResult(
                corrected_text=text,  # 원본 텍스트 반환
                confidence=0.0,
                corrections_made=[],
                processing_metadata={"error": str(e), "pipeline_stages": pipeline_metadata}
            )
    
    def configure_for_language(self, language: str) -> None:
        """언어별 파이프라인 설정"""
        language_configs = {
            'korean': {
                'rule_based_correction': True,
                'bert_correction': True,
                'openai_correction': False
            },
            'english': {
                'rule_based_correction': True,
                'bert_correction': False,
                'openai_correction': False
            },
            'chinese': {
                'rule_based_correction': True,
                'bert_correction': False,
                'openai_correction': True
            },
            'japanese': {
                'rule_based_correction': True,
                'bert_correction': False,
                'openai_correction': True
            }
        }
        
        config = language_configs.get(language, language_configs['korean'])
        
        for stage_name, enabled in config.items():
            if enabled:
                self.enable_stage(stage_name)
            else:
                self.disable_stage(stage_name)
        
        logger.info(f"Configured pipeline for language: {language}")
    
    def configure_for_document_type(self, document_type: str) -> None:
        """문서 타입별 파이프라인 설정"""
        document_configs = {
            'financial': {
                'rule_based_correction': True,
                'bert_correction': False,
                'openai_correction': True  # 재무 문서는 정확도가 중요
            },
            'technical': {
                'rule_based_correction': True,
                'bert_correction': True,
                'openai_correction': False
            },
            'general': {
                'rule_based_correction': True,
                'bert_correction': False,
                'openai_correction': False
            }
        }
        
        config = document_configs.get(document_type, document_configs['general'])
        
        for stage_name, enabled in config.items():
            if enabled:
                self.enable_stage(stage_name)
            else:
                self.disable_stage(stage_name)
        
        logger.info(f"Configured pipeline for document type: {document_type}")
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """파이프라인 정보 반환"""
        return {
            "total_stages": len(self.stages),
            "enabled_stages": len([s for s in self.stages if s.enabled]),
            "stages": [
                {
                    "name": stage.name,
                    "enabled": stage.enabled,
                    "priority": stage.priority,
                    "corrector_type": type(stage.corrector).__name__
                }
                for stage in self.stages
            ]
        }
    
    def _get_current_time(self) -> float:
        """현재 시간 반환 (성능 측정용)"""
        import time
        return time.time()


class PipelineBuilder:
    """파이프라인 빌더 - Builder Pattern"""
    
    def __init__(self, container: Optional[DIContainer] = None):
        self.container = container or DIContainer()
        self.pipeline = TextCorrectionPipeline(self.container)
        self.pipeline.stages.clear()  # 기본 설정 제거
    
    def add_rule_based_correction(self, priority: int = 1) -> 'PipelineBuilder':
        """규칙 기반 교정 추가"""
        corrector = self.container.resolve(RuleBasedCorrector)
        self.pipeline.add_stage("rule_based_correction", corrector, priority)
        return self
    
    def add_bert_correction(self, priority: int = 2) -> 'PipelineBuilder':
        """BERT 교정 추가"""
        corrector = self.container.resolve(BERTTextCorrector)
        self.pipeline.add_stage("bert_correction", corrector, priority)
        return self
    
    def add_openai_correction(self, priority: int = 3) -> 'PipelineBuilder':
        """OpenAI 교정 추가"""
        corrector = self.container.resolve(OpenAITextCorrector)
        self.pipeline.add_stage("openai_correction", corrector, priority)
        return self
    
    def add_custom_corrector(self, name: str, corrector: TextCorrector, 
                           priority: int = 0) -> 'PipelineBuilder':
        """커스텀 교정기 추가"""
        self.pipeline.add_stage(name, corrector, priority)
        return self
    
    def build(self) -> TextCorrectionPipeline:
        """파이프라인 생성"""
        return self.pipeline


# 미리 정의된 파이프라인 설정
class PredefinedPipelines:
    """미리 정의된 파이프라인들"""
    
    @staticmethod
    def create_fast_pipeline(container: Optional[DIContainer] = None) -> TextCorrectionPipeline:
        """빠른 처리용 파이프라인"""
        return (PipelineBuilder(container)
                .add_rule_based_correction(priority=1)
                .build())
    
    @staticmethod
    def create_balanced_pipeline(container: Optional[DIContainer] = None) -> TextCorrectionPipeline:
        """균형잡힌 파이프라인"""
        return (PipelineBuilder(container)
                .add_rule_based_correction(priority=1)
                .add_bert_correction(priority=2)
                .build())
    
    @staticmethod
    def create_premium_pipeline(container: Optional[DIContainer] = None) -> TextCorrectionPipeline:
        """고품질 파이프라인"""
        return (PipelineBuilder(container)
                .add_rule_based_correction(priority=1)
                .add_bert_correction(priority=2)
                .add_openai_correction(priority=3)
                .build())
    
    @staticmethod
    def create_financial_pipeline(container: Optional[DIContainer] = None) -> TextCorrectionPipeline:
        """재무 문서용 파이프라인"""
        pipeline = (PipelineBuilder(container)
                   .add_rule_based_correction(priority=1)
                   .add_openai_correction(priority=2)
                   .build())
        pipeline.configure_for_document_type('financial')
        return pipeline