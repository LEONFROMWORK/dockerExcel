"""
OCR 시스템 설정 관리
하드코딩된 설정을 외부화하여 Open/Closed Principle 구현
"""

import os
import json
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field, asdict
import logging

from .ocr_interfaces import (
    OCRSystemConfig, OCREngineConfig, LanguageCode, 
    DocumentType, ProcessingTier, CorrectionMethod
)

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """설정 관련 오류"""
    pass


class OCRConfigManager:
    """OCR 설정 관리자 - 설정의 중앙화된 관리"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self._config: Optional[OCRSystemConfig] = None
        self._load_config()
    
    def _get_default_config_path(self) -> str:
        """기본 설정 파일 경로"""
        # 환경변수에서 설정 파일 경로 확인
        config_path = os.environ.get('OCR_CONFIG_PATH')
        if config_path and os.path.exists(config_path):
            return config_path
        
        # 프로젝트 루트에서 설정 파일 찾기
        current_dir = Path(__file__).parent
        possible_paths = [
            current_dir / "ocr_config.yaml",
            current_dir / "ocr_config.json",
            current_dir.parent / "config" / "ocr_config.yaml",
            current_dir.parent / "config" / "ocr_config.json",
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        # 기본 설정으로 새 파일 생성
        default_path = current_dir / "ocr_config.yaml"
        self._create_default_config(str(default_path))
        return str(default_path)
    
    def _load_config(self):
        """설정 파일 로드"""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file not found: {self.config_path}. Creating default config.")
                self._create_default_config(self.config_path)
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)
            
            self._config = self._parse_config(config_data)
            logger.info(f"OCR configuration loaded from: {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config = self._create_default_system_config()
    
    def _parse_config(self, config_data: Dict[str, Any]) -> OCRSystemConfig:
        """설정 데이터를 OCRSystemConfig로 변환"""
        # 엔진 설정 파싱
        engines = []
        for engine_data in config_data.get('engines', []):
            engines.append(OCREngineConfig(
                engine_name=engine_data['name'],
                engine_class=engine_data['class'],
                enabled=engine_data.get('enabled', True),
                priority=engine_data.get('priority', 0),
                config=engine_data.get('config', {})
            ))
        
        # 언어 설정 파싱
        language_configs = {}
        for lang_code, lang_config in config_data.get('language_configs', {}).items():
            language_configs[lang_code] = lang_config
        
        # 문서 타입 설정 파싱
        document_type_configs = {}
        for doc_type_str, doc_config in config_data.get('document_type_configs', {}).items():
            try:
                doc_type = DocumentType(doc_type_str)
                document_type_configs[doc_type] = doc_config
            except ValueError:
                logger.warning(f"Unknown document type: {doc_type_str}")
        
        return OCRSystemConfig(
            engines=engines,
            default_language=LanguageCode(config_data.get('default_language', 'kor')),
            default_timeout=config_data.get('default_timeout', 30.0),
            cache_enabled=config_data.get('cache_enabled', True),
            cache_ttl=config_data.get('cache_ttl', 3600),
            metrics_enabled=config_data.get('metrics_enabled', True),
            language_configs=language_configs,
            document_type_configs=document_type_configs
        )
    
    def _create_default_config(self, config_path: str):
        """기본 설정 파일 생성"""
        default_config = self._create_default_system_config()
        config_data = asdict(default_config)
        
        # Enum 값들을 문자열로 변환
        config_data['default_language'] = default_config.default_language.value
        for engine in config_data['engines']:
            pass  # 이미 문자열 형태
        
        # DocumentType enum을 문자열로 변환
        doc_type_configs = {}
        for doc_type, config in default_config.document_type_configs.items():
            doc_type_configs[doc_type.value] = config
        config_data['document_type_configs'] = doc_type_configs
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Default configuration created: {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
            raise ConfigurationError(f"Cannot create default configuration: {e}")
    
    def _create_default_system_config(self) -> OCRSystemConfig:
        """기본 시스템 설정 생성"""
        return OCRSystemConfig(
            engines=[
                OCREngineConfig(
                    engine_name="tesseract_basic",
                    engine_class="app.services.ocr_engines.tesseract_engine.TesseractOCRProcessor",
                    enabled=True,
                    priority=3,
                    config={
                        "tessdata_path": "/usr/share/tesseract-ocr/4.00/tessdata",
                        "enabled_languages": ["kor", "eng", "chi_sim", "jpn"],
                        "custom_models_path": "/usr/share/tesseract-ocr/4.00/tessdata"
                    }
                ),
                OCREngineConfig(
                    engine_name="openai_vision",
                    engine_class="app.services.ocr_engines.openai_engine.OpenAIVisionProcessor",
                    enabled=True,
                    priority=1,
                    config={
                        "model": "gpt-4-vision-preview",
                        "max_tokens": 2000
                    }
                ),
                OCREngineConfig(
                    engine_name="transformer_ocr",
                    engine_class="app.services.ocr_engines.transformer_engine.TransformerOCRProcessor",
                    enabled=True,
                    priority=0,
                    config={
                        "bert_model": "klue/bert-base",
                        "use_openai_correction": True
                    }
                )
            ],
            default_language=LanguageCode.KOREAN,
            default_timeout=30.0,
            cache_enabled=True,
            cache_ttl=3600,
            metrics_enabled=True,
            language_configs={
                "kor": {
                    "financial_vocabulary_enabled": True,
                    "custom_model": "korean_finance",
                    "confidence_threshold": 0.7
                },
                "eng": {
                    "financial_vocabulary_enabled": True,
                    "custom_model": None,
                    "confidence_threshold": 0.8
                },
                "chi_sim": {
                    "financial_vocabulary_enabled": True,
                    "custom_model": "chi_sim_finance",
                    "confidence_threshold": 0.6
                },
                "jpn": {
                    "financial_vocabulary_enabled": True,
                    "custom_model": "jpn_finance",
                    "confidence_threshold": 0.65
                }
            },
            document_type_configs={
                DocumentType.FINANCIAL_STATEMENT: {
                    "preferred_engines": ["transformer_ocr", "openai_vision"],
                    "correction_method": "hybrid",
                    "table_detection": True,
                    "financial_vocabulary": True
                },
                DocumentType.INVOICE: {
                    "preferred_engines": ["tesseract_basic", "openai_vision"],
                    "correction_method": "rule_based",
                    "table_detection": True,
                    "financial_vocabulary": False
                },
                DocumentType.CONTRACT: {
                    "preferred_engines": ["openai_vision", "transformer_ocr"],
                    "correction_method": "openai",
                    "table_detection": False,
                    "financial_vocabulary": False
                }
            }
        )
    
    def get_config(self) -> OCRSystemConfig:
        """현재 설정 반환"""
        if self._config is None:
            raise ConfigurationError("Configuration not loaded")
        return self._config
    
    def get_engine_config(self, engine_name: str) -> Optional[OCREngineConfig]:
        """특정 엔진 설정 조회"""
        config = self.get_config()
        for engine in config.engines:
            if engine.engine_name == engine_name:
                return engine
        return None
    
    def get_enabled_engines(self) -> List[OCREngineConfig]:
        """활성화된 엔진 목록 (우선순위 순)"""
        config = self.get_config()
        enabled_engines = [engine for engine in config.engines if engine.enabled]
        return sorted(enabled_engines, key=lambda x: x.priority)
    
    def get_language_config(self, language: LanguageCode) -> Dict[str, Any]:
        """언어별 설정 조회"""
        config = self.get_config()
        return config.language_configs.get(language.value, {})
    
    def get_document_type_config(self, document_type: DocumentType) -> Dict[str, Any]:
        """문서 타입별 설정 조회"""
        config = self.get_config()
        return config.document_type_configs.get(document_type, {})
    
    def get_preferred_engines_for_document(self, document_type: DocumentType) -> List[str]:
        """문서 타입에 대한 선호 엔진 목록"""
        doc_config = self.get_document_type_config(document_type)
        preferred = doc_config.get('preferred_engines', [])
        
        if not preferred:
            # 기본적으로 우선순위 순으로 반환
            enabled_engines = self.get_enabled_engines()
            return [engine.engine_name for engine in enabled_engines]
        
        return preferred
    
    def reload_config(self):
        """설정 재로드"""
        self._load_config()
        logger.info("OCR configuration reloaded")
    
    def update_config(self, config: OCRSystemConfig):
        """설정 업데이트 및 저장"""
        self._config = config
        self._save_config()
    
    def _save_config(self):
        """현재 설정을 파일에 저장"""
        if self._config is None:
            return
        
        config_data = asdict(self._config)
        
        # Enum 값들을 문자열로 변환
        config_data['default_language'] = self._config.default_language.value
        
        # DocumentType enum을 문자열로 변환
        doc_type_configs = {}
        for doc_type, config in self._config.document_type_configs.items():
            doc_type_configs[doc_type.value] = config
        config_data['document_type_configs'] = doc_type_configs
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration saved to: {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise ConfigurationError(f"Cannot save configuration: {e}")


# 전역 설정 관리자 인스턴스
_config_manager: Optional[OCRConfigManager] = None


def get_config_manager() -> OCRConfigManager:
    """전역 설정 관리자 인스턴스 반환 (싱글톤)"""
    global _config_manager
    if _config_manager is None:
        _config_manager = OCRConfigManager()
    return _config_manager


def get_ocr_config() -> OCRSystemConfig:
    """현재 OCR 설정 반환"""
    return get_config_manager().get_config()


def reload_ocr_config():
    """OCR 설정 재로드"""
    get_config_manager().reload_config()


# 환경 변수 기반 설정 오버라이드
class EnvironmentConfigOverride:
    """환경 변수를 통한 설정 오버라이드"""
    
    @staticmethod
    def override_config(config: OCRSystemConfig) -> OCRSystemConfig:
        """환경 변수로 설정 오버라이드"""
        
        # 기본 설정 오버라이드
        if os.environ.get('OCR_DEFAULT_TIMEOUT'):
            config.default_timeout = float(os.environ['OCR_DEFAULT_TIMEOUT'])
        
        if os.environ.get('OCR_CACHE_ENABLED'):
            config.cache_enabled = os.environ['OCR_CACHE_ENABLED'].lower() == 'true'
        
        if os.environ.get('OCR_CACHE_TTL'):
            config.cache_ttl = int(os.environ['OCR_CACHE_TTL'])
        
        if os.environ.get('OCR_METRICS_ENABLED'):
            config.metrics_enabled = os.environ['OCR_METRICS_ENABLED'].lower() == 'true'
        
        # 개별 엔진 활성화/비활성화
        for engine in config.engines:
            env_key = f'OCR_ENGINE_{engine.engine_name.upper()}_ENABLED'
            if os.environ.get(env_key):
                engine.enabled = os.environ[env_key].lower() == 'true'
        
        return config