"""
언어 설정 로더
Configuration Management + Plugin Architecture 적용
"""

import logging
import yaml
import json
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class LanguageConfig:
    """언어별 설정"""
    language_code: str
    language_name: str
    native_name: str
    writing_direction: str = "ltr"  # ltr, rtl
    confidence_threshold: float = 0.85
    quality_threshold: float = 0.8
    complexity_threshold: float = 0.7
    preferred_engines: List[str] = None
    preprocessing_rules: Dict[str, Any] = None
    postprocessing_rules: Dict[str, Any] = None
    correction_rules: Dict[str, Any] = None
    financial_terms: List[str] = None
    common_patterns: Dict[str, str] = None
    character_sets: Dict[str, str] = None
    
    def __post_init__(self):
        if self.preferred_engines is None:
            self.preferred_engines = []
        if self.preprocessing_rules is None:
            self.preprocessing_rules = {}
        if self.postprocessing_rules is None:
            self.postprocessing_rules = {}
        if self.correction_rules is None:
            self.correction_rules = {}
        if self.financial_terms is None:
            self.financial_terms = []
        if self.common_patterns is None:
            self.common_patterns = {}
        if self.character_sets is None:
            self.character_sets = {}


class ConfigLoader(ABC):
    """설정 로더 추상 클래스"""
    
    @abstractmethod
    def load(self, config_path: Path) -> Dict[str, LanguageConfig]:
        """설정 로드"""
        pass
    
    @abstractmethod
    def save(self, config_path: Path, configs: Dict[str, LanguageConfig]) -> None:
        """설정 저장"""
        pass
    
    @abstractmethod
    def supports_format(self, file_path: Path) -> bool:
        """파일 형식 지원 여부"""
        pass


class YAMLConfigLoader(ConfigLoader):
    """YAML 설정 로더"""
    
    def load(self, config_path: Path) -> Dict[str, LanguageConfig]:
        """YAML 파일에서 언어 설정 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            configs = {}
            languages = data.get('languages', {})
            
            for lang_code, lang_data in languages.items():
                config = LanguageConfig(
                    language_code=lang_code,
                    language_name=lang_data.get('language_name', lang_code),
                    native_name=lang_data.get('native_name', lang_code),
                    writing_direction=lang_data.get('writing_direction', 'ltr'),
                    confidence_threshold=lang_data.get('confidence_threshold', 0.85),
                    quality_threshold=lang_data.get('quality_threshold', 0.8),
                    complexity_threshold=lang_data.get('complexity_threshold', 0.7),
                    preferred_engines=lang_data.get('preferred_engines', []),
                    preprocessing_rules=lang_data.get('preprocessing_rules', {}),
                    postprocessing_rules=lang_data.get('postprocessing_rules', {}),
                    correction_rules=lang_data.get('correction_rules', {}),
                    financial_terms=lang_data.get('financial_terms', []),
                    common_patterns=lang_data.get('common_patterns', {}),
                    character_sets=lang_data.get('character_sets', {})
                )
                configs[lang_code] = config
            
            logger.info(f"Loaded {len(configs)} language configurations from {config_path}")
            return configs
            
        except Exception as e:
            logger.error(f"Failed to load YAML config from {config_path}: {e}")
            return {}
    
    def save(self, config_path: Path, configs: Dict[str, LanguageConfig]) -> None:
        """YAML 파일로 언어 설정 저장"""
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'languages': {
                    lang_code: asdict(config)
                    for lang_code, config in configs.items()
                }
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Saved {len(configs)} language configurations to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save YAML config to {config_path}: {e}")
            raise
    
    def supports_format(self, file_path: Path) -> bool:
        """YAML 파일 형식 지원 여부"""
        return file_path.suffix.lower() in ['.yaml', '.yml']


class JSONConfigLoader(ConfigLoader):
    """JSON 설정 로더"""
    
    def load(self, config_path: Path) -> Dict[str, LanguageConfig]:
        """JSON 파일에서 언어 설정 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            configs = {}
            languages = data.get('languages', {})
            
            for lang_code, lang_data in languages.items():
                config = LanguageConfig(**lang_data)
                configs[lang_code] = config
            
            logger.info(f"Loaded {len(configs)} language configurations from {config_path}")
            return configs
            
        except Exception as e:
            logger.error(f"Failed to load JSON config from {config_path}: {e}")
            return {}
    
    def save(self, config_path: Path, configs: Dict[str, LanguageConfig]) -> None:
        """JSON 파일로 언어 설정 저장"""
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'languages': {
                    lang_code: asdict(config)
                    for lang_code, config in configs.items()
                }
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(configs)} language configurations to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save JSON config to {config_path}: {e}")
            raise
    
    def supports_format(self, file_path: Path) -> bool:
        """JSON 파일 형식 지원 여부"""
        return file_path.suffix.lower() == '.json'


class LanguageConfigLoader:
    """언어 설정 로더 - Plugin Architecture"""
    
    def __init__(self):
        self._loaders: List[ConfigLoader] = []
        self._configs: Dict[str, LanguageConfig] = {}
        self._config_sources: Dict[str, Path] = {}
        self._register_default_loaders()
        self._load_builtin_configs()
    
    def _register_default_loaders(self) -> None:
        """기본 로더들 등록"""
        self._loaders.extend([
            YAMLConfigLoader(),
            JSONConfigLoader()
        ])
    
    def register_loader(self, loader: ConfigLoader) -> None:
        """커스텀 로더 등록"""
        self._loaders.append(loader)
        logger.info(f"Registered config loader: {type(loader).__name__}")
    
    def load_config_file(self, config_path: Path) -> int:
        """설정 파일 로드"""
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}")
            return 0
        
        # 적절한 로더 찾기
        loader = self._find_loader_for_file(config_path)
        if not loader:
            logger.error(f"No loader found for file: {config_path}")
            return 0
        
        # 설정 로드
        configs = loader.load(config_path)
        loaded_count = 0
        
        for lang_code, config in configs.items():
            self._configs[lang_code] = config
            self._config_sources[lang_code] = config_path
            loaded_count += 1
        
        logger.info(f"Loaded {loaded_count} language configs from {config_path}")
        return loaded_count
    
    def load_config_directory(self, config_dir: Path) -> int:
        """설정 디렉토리 로드"""
        if not config_dir.exists():
            logger.warning(f"Config directory not found: {config_dir}")
            return 0
        
        total_loaded = 0
        
        # 지원되는 모든 설정 파일 로드
        for config_file in config_dir.glob("*"):
            if config_file.is_file() and self._find_loader_for_file(config_file):
                total_loaded += self.load_config_file(config_file)
        
        logger.info(f"Loaded {total_loaded} total language configs from {config_dir}")
        return total_loaded
    
    def get_language_config(self, language_code: str) -> Optional[LanguageConfig]:
        """언어 설정 가져오기"""
        return self._configs.get(language_code)
    
    def get_all_configs(self) -> Dict[str, LanguageConfig]:
        """모든 언어 설정 가져오기"""
        return self._configs.copy()
    
    def get_supported_languages(self) -> List[str]:
        """지원되는 언어 목록"""
        return list(self._configs.keys())
    
    def add_language_config(self, config: LanguageConfig) -> None:
        """언어 설정 추가"""
        self._configs[config.language_code] = config
        logger.info(f"Added language config: {config.language_code}")
    
    def remove_language_config(self, language_code: str) -> bool:
        """언어 설정 제거"""
        if language_code in self._configs:
            del self._configs[language_code]
            if language_code in self._config_sources:
                del self._config_sources[language_code]
            logger.info(f"Removed language config: {language_code}")
            return True
        return False
    
    def save_config_file(self, config_path: Path, 
                        language_codes: Optional[List[str]] = None) -> None:
        """설정 파일 저장"""
        loader = self._find_loader_for_file(config_path)
        if not loader:
            raise ValueError(f"No loader found for file: {config_path}")
        
        # 저장할 설정 선택
        if language_codes:
            configs_to_save = {
                code: config for code, config in self._configs.items()
                if code in language_codes
            }
        else:
            configs_to_save = self._configs
        
        loader.save(config_path, configs_to_save)
    
    def get_config_for_engines(self, engine_names: List[str]) -> Dict[str, LanguageConfig]:
        """특정 엔진들을 지원하는 언어 설정들"""
        matching_configs = {}
        
        for lang_code, config in self._configs.items():
            if any(engine in config.preferred_engines for engine in engine_names):
                matching_configs[lang_code] = config
        
        return matching_configs
    
    def get_config_summary(self) -> Dict[str, Any]:
        """설정 요약 정보"""
        return {
            "total_languages": len(self._configs),
            "supported_languages": list(self._configs.keys()),
            "rtl_languages": [
                code for code, config in self._configs.items()
                if config.writing_direction == "rtl"
            ],
            "config_sources": len(set(self._config_sources.values())),
            "average_confidence_threshold": sum(
                config.confidence_threshold for config in self._configs.values()
            ) / len(self._configs) if self._configs else 0
        }
    
    def _find_loader_for_file(self, file_path: Path) -> Optional[ConfigLoader]:
        """파일에 적합한 로더 찾기"""
        for loader in self._loaders:
            if loader.supports_format(file_path):
                return loader
        return None
    
    def _load_builtin_configs(self) -> None:
        """내장 언어 설정 로드"""
        builtin_configs = {
            "korean": LanguageConfig(
                language_code="korean",
                language_name="Korean",
                native_name="한국어",
                writing_direction="ltr",
                confidence_threshold=0.85,
                quality_threshold=0.8,
                complexity_threshold=0.7,
                preferred_engines=["paddleocr", "openai_vision"],
                preprocessing_rules={
                    "normalize_spaces": True,
                    "remove_noise": True
                },
                postprocessing_rules={
                    "fix_jamo_separation": True,
                    "normalize_particles": True
                },
                correction_rules={
                    "financial_terms": True,
                    "common_typos": True
                },
                financial_terms=[
                    "자산", "부채", "자본", "매출", "손익", "대차대조표", "손익계산서"
                ],
                common_patterns={
                    "currency": r"\\d+(?:,\\d{3})*원",
                    "percentage": r"\\d+(?:\\.\\d+)?%"
                },
                character_sets={
                    "hangul": "\\uAC00-\\uD7AF",
                    "jamo": "\\u1100-\\u11FF"
                }
            ),
            
            "english": LanguageConfig(
                language_code="english",
                language_name="English",
                native_name="English",
                writing_direction="ltr",
                confidence_threshold=0.9,
                quality_threshold=0.85,
                complexity_threshold=0.6,
                preferred_engines=["tesseract", "paddleocr"],
                preprocessing_rules={
                    "normalize_spaces": True,
                    "case_normalization": False
                },
                postprocessing_rules={
                    "spell_check": False,
                    "grammar_check": False
                },
                correction_rules={
                    "financial_terms": True,
                    "abbreviations": True
                },
                financial_terms=[
                    "assets", "liabilities", "equity", "revenue", "income", "balance sheet", "income statement"
                ],
                common_patterns={
                    "currency": r"\\$\\d+(?:,\\d{3})*(?:\\.\\d{2})?",
                    "percentage": r"\\d+(?:\\.\\d+)?%"
                }
            ),
            
            "chinese": LanguageConfig(
                language_code="chinese",
                language_name="Chinese (Simplified)",
                native_name="中文",
                writing_direction="ltr",
                confidence_threshold=0.8,
                quality_threshold=0.75,
                complexity_threshold=0.75,
                preferred_engines=["paddleocr", "openai_vision"],
                preprocessing_rules={
                    "normalize_spaces": True,
                    "traditional_to_simplified": False
                },
                postprocessing_rules={
                    "segment_words": True
                },
                correction_rules={
                    "financial_terms": True
                },
                financial_terms=[
                    "资产", "负债", "权益", "收入", "利润", "资产负债表", "利润表"
                ],
                character_sets={
                    "cjk": "\\u4E00-\\u9FFF"
                }
            ),
            
            "japanese": LanguageConfig(
                language_code="japanese",
                language_name="Japanese",
                native_name="日本語",
                writing_direction="ltr",
                confidence_threshold=0.8,
                quality_threshold=0.8,
                complexity_threshold=0.8,
                preferred_engines=["paddleocr", "openai_vision"],
                preprocessing_rules={
                    "normalize_spaces": True
                },
                postprocessing_rules={
                    "segment_words": True
                },
                correction_rules={
                    "financial_terms": True
                },
                financial_terms=[
                    "資産", "負債", "資本", "売上", "利益", "貸借対照表", "損益計算書"
                ],
                character_sets={
                    "hiragana": "\\u3040-\\u309F",
                    "katakana": "\\u30A0-\\u30FF",
                    "kanji": "\\u4E00-\\u9FAF"
                }
            ),
            
            "arabic": LanguageConfig(
                language_code="arabic",
                language_name="Arabic",
                native_name="العربية",
                writing_direction="rtl",
                confidence_threshold=0.75,
                quality_threshold=0.7,
                complexity_threshold=0.8,
                preferred_engines=["openai_vision"],
                preprocessing_rules={
                    "normalize_spaces": True,
                    "rtl_processing": True
                },
                postprocessing_rules={
                    "diacritic_handling": True
                },
                correction_rules={
                    "financial_terms": True
                },
                financial_terms=[
                    "الأصول", "الخصوم", "حقوق الملكية", "الإيرادات", "الأرباح"
                ],
                character_sets={
                    "arabic": "\\u0600-\\u06FF"
                }
            )
        }
        
        for config in builtin_configs.values():
            self._configs[config.language_code] = config
        
        logger.info(f"Loaded {len(builtin_configs)} builtin language configurations")


# 글로벌 설정 로더 인스턴스
_global_config_loader: Optional[LanguageConfigLoader] = None


def get_language_config_loader() -> LanguageConfigLoader:
    """글로벌 언어 설정 로더 가져오기"""
    global _global_config_loader
    if _global_config_loader is None:
        _global_config_loader = LanguageConfigLoader()
    return _global_config_loader


def get_language_config(language_code: str) -> Optional[LanguageConfig]:
    """언어 설정 가져오기"""
    return get_language_config_loader().get_language_config(language_code)


def get_supported_languages() -> List[str]:
    """지원되는 언어 목록"""
    return get_language_config_loader().get_supported_languages()