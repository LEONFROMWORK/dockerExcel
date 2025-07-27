"""
Tesseract OCR 엔진 구현
새로운 OCR 인터페이스를 구현하는 Tesseract 기반 처리기
"""

import pytesseract
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Any, Optional
import logging
import os
from pathlib import Path

from app.core.ocr_interfaces import (
    BaseOCRProcessor, OCROptions, OCRResult, ProcessingMetadata,
    LanguageCode, ProcessingTier, DocumentType, CacheProvider, MetricsCollector
)

logger = logging.getLogger(__name__)


class TesseractOCRProcessor(BaseOCRProcessor):
    """Tesseract 기반 OCR 처리기 - SOLID 원칙 적용"""
    
    def __init__(self, 
                 tessdata_path: Optional[str] = None,
                 custom_models_path: Optional[str] = None,
                 cache_provider: Optional[CacheProvider] = None,
                 metrics_collector: Optional[MetricsCollector] = None):
        """
        Tesseract OCR 처리기 초기화
        
        Args:
            tessdata_path: Tesseract 언어 모델 경로
            custom_models_path: 커스텀 훈련 모델 경로
            cache_provider: 캐시 제공자 (의존성 주입)
            metrics_collector: 메트릭 수집기 (의존성 주입)
        """
        super().__init__(cache_provider, metrics_collector)
        
        self.tessdata_path = tessdata_path or "/Users/kevin/excel-unified/tessdata_multilang"
        self.custom_models_path = custom_models_path or "/Users/kevin/excel-unified/tesstrain/data"
        
        # 경로 검증
        if not os.path.exists(self.tessdata_path):
            logger.warning(f"Tessdata path not found: {self.tessdata_path}")
        
        # 지원 언어 매핑
        self.language_mapping = {
            LanguageCode.KOREAN: {
                'standard': 'kor',
                'custom': 'korean_finance'
            },
            LanguageCode.ENGLISH: {
                'standard': 'eng',
                'custom': None
            },
            LanguageCode.CHINESE_SIMPLIFIED: {
                'standard': 'chi_sim',
                'custom': 'chi_sim_finance'
            },
            LanguageCode.CHINESE_TRADITIONAL: {
                'standard': 'chi_tra',
                'custom': 'chi_tra_finance'
            },
            LanguageCode.JAPANESE: {
                'standard': 'jpn',
                'custom': 'jpn_finance'
            },
            LanguageCode.SPANISH: {
                'standard': 'spa',
                'custom': 'spa_finance'
            },
            LanguageCode.PORTUGUESE: {
                'standard': 'por',
                'custom': 'por_finance'
            },
            LanguageCode.FRENCH: {
                'standard': 'fra',
                'custom': 'fra_finance'
            },
            LanguageCode.GERMAN: {
                'standard': 'deu',
                'custom': 'deu_finance'
            },
            LanguageCode.VIETNAMESE: {
                'standard': 'vie',
                'custom': 'vie_finance'
            },
            LanguageCode.ITALIAN: {
                'standard': 'ita',
                'custom': 'ita_finance'
            },
            LanguageCode.ARABIC: {
                'standard': 'ara',
                'custom': 'ara_finance'
            }
        }
    
    async def _process_image_impl(self, image_path: str, options: OCROptions) -> OCRResult:
        """Tesseract OCR 처리 구현"""
        try:
            # 1. 언어 결정
            lang_code = await self._determine_language(image_path, options.language)
            
            # 2. 이미지 전처리
            processed_image = self._preprocess_image(image_path)
            
            # 3. OCR 설정 구성
            tesseract_config = self._build_tesseract_config(options)
            tesseract_lang = self._get_tesseract_language(lang_code, options)
            
            # 4. OCR 수행 (Two-Tier 방식)
            text, confidence = await self._perform_two_tier_ocr(
                processed_image, tesseract_lang, tesseract_config, options
            )
            
            # 5. 결과 구성
            metadata = ProcessingMetadata(
                processing_time=0.0,  # 상위 클래스에서 설정
                processing_tier=ProcessingTier.TIER_ONE,
                model_used=f"tesseract_{tesseract_lang}",
                language_detected=lang_code,
                confidence_score=confidence
            )
            
            return OCRResult(
                text=text,
                confidence=confidence,
                success=True,
                metadata=metadata,
                document_type=DocumentType.UNKNOWN  # 상위 레벨에서 결정
            )
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise
    
    async def _determine_language(self, image_path: str, requested_language: LanguageCode) -> LanguageCode:
        """언어 결정"""
        if requested_language != LanguageCode.AUTO_DETECT:
            return requested_language
        
        # 간단한 언어 감지 (파일명 기반)
        filename = Path(image_path).name.lower()
        
        if any(keyword in filename for keyword in ['kor', 'korean', '한국']):
            return LanguageCode.KOREAN
        elif any(keyword in filename for keyword in ['chi', 'chinese', '중국']):
            return LanguageCode.CHINESE_SIMPLIFIED
        elif any(keyword in filename for keyword in ['jpn', 'japanese', '일본']):
            return LanguageCode.JAPANESE
        
        # 기본값: 한국어
        return LanguageCode.KOREAN
    
    def _preprocess_image(self, image_path: str) -> np.ndarray:
        """이미지 전처리"""
        try:
            # OpenCV로 이미지 로드
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Cannot load image: {image_path}")
            
            # 그레이스케일 변환
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 노이즈 제거
            denoised = cv2.medianBlur(gray, 3)
            
            # 이진화
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return binary
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            # 원본 이미지 반환
            image = cv2.imread(image_path)
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image is not None else None
    
    def _build_tesseract_config(self, options: OCROptions) -> str:
        """Tesseract 설정 구성"""
        config_parts = []
        
        # 기본 설정
        config_parts.append("--oem 3")  # OCR Engine Mode: LSTM + Legacy
        config_parts.append("--psm 6")  # Page Segmentation Mode: 단일 텍스트 블록
        
        # 컨텍스트 기반 설정 조정
        if "table" in options.context_tags:
            config_parts.append("--psm 6")  # 표 형태 텍스트
        elif "single_line" in options.context_tags:
            config_parts.append("--psm 8")  # 단일 라인
        elif "single_word" in options.context_tags:
            config_parts.append("--psm 10")  # 단일 단어
        
        # 신뢰도 임계값 설정
        config_parts.append(f"-c tessedit_char_whitelist= -c tessedit_char_blacklist=")
        
        return " ".join(config_parts)
    
    def _get_tesseract_language(self, language: LanguageCode, options: OCROptions) -> str:
        """Tesseract 언어 코드 결정"""
        if language not in self.language_mapping:
            language = LanguageCode.ENGLISH  # fallback
        
        lang_info = self.language_mapping[language]
        
        # 재무 문서이고 커스텀 모델이 있으면 사용
        if (options.use_financial_vocabulary and 
            lang_info['custom'] and 
            self._custom_model_exists(lang_info['custom'])):
            return lang_info['custom']
        
        return lang_info['standard']
    
    def _custom_model_exists(self, model_name: str) -> bool:
        """커스텀 모델 존재 확인"""
        if not self.custom_models_path:
            return False
        
        model_file = Path(self.custom_models_path) / f"{model_name}.traineddata"
        return model_file.exists()
    
    async def _perform_two_tier_ocr(self, image: np.ndarray, language: str, 
                                  config: str, options: OCROptions) -> tuple[str, float]:
        """Two-Tier OCR 수행"""
        
        # Tier 1: 커스텀 모델 시도
        if language.endswith('_finance') and self._custom_model_exists(language):
            try:
                text, confidence = self._perform_tesseract_ocr(image, language, config)
                
                if confidence >= options.confidence_threshold:
                    logger.info(f"Tier 1 success with custom model: {language}")
                    return text, confidence
                    
            except Exception as e:
                logger.warning(f"Tier 1 OCR failed with {language}: {e}")
        
        # Tier 2: 표준 모델 fallback
        standard_language = language.replace('_finance', '') if '_finance' in language else language
        
        try:
            text, confidence = self._perform_tesseract_ocr(image, standard_language, config)
            logger.info(f"Tier 2 success with standard model: {standard_language}")
            return text, confidence
            
        except Exception as e:
            logger.error(f"Tier 2 OCR failed with {standard_language}: {e}")
            return "", 0.0
    
    def _perform_tesseract_ocr(self, image: np.ndarray, language: str, config: str) -> tuple[str, float]:
        """실제 Tesseract OCR 수행"""
        try:
            # PIL Image로 변환
            pil_image = Image.fromarray(image)
            
            # Tessdata 경로 설정
            original_tessdata = os.environ.get('TESSDATA_PREFIX')
            os.environ['TESSDATA_PREFIX'] = self.tessdata_path
            
            try:
                # OCR 수행
                text = pytesseract.image_to_string(
                    pil_image,
                    lang=language,
                    config=config
                ).strip()
                
                # 신뢰도 점수 계산
                try:
                    data = pytesseract.image_to_data(
                        pil_image,
                        lang=language,
                        config=config,
                        output_type=pytesseract.Output.DICT
                    )
                    
                    # 평균 신뢰도 계산 (0보다 큰 값들만)
                    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                    confidence = np.mean(confidences) / 100.0 if confidences else 0.0
                    
                except:
                    # 신뢰도 계산 실패 시 텍스트 길이 기반 추정
                    confidence = min(len(text) / 100.0, 0.9) if text else 0.0
                
                return text, confidence
                
            finally:
                # 원래 환경변수 복원
                if original_tessdata:
                    os.environ['TESSDATA_PREFIX'] = original_tessdata
                elif 'TESSDATA_PREFIX' in os.environ:
                    del os.environ['TESSDATA_PREFIX']
                    
        except Exception as e:
            logger.error(f"Tesseract OCR execution failed: {e}")
            raise
    
    def supports_language(self, language: LanguageCode) -> bool:
        """언어 지원 여부 확인"""
        return language in self.language_mapping or language == LanguageCode.AUTO_DETECT
    
    def get_supported_languages(self) -> List[LanguageCode]:
        """지원 언어 목록"""
        return list(self.language_mapping.keys()) + [LanguageCode.AUTO_DETECT]
    
    def get_processing_tier(self) -> ProcessingTier:
        """처리 계층 반환"""
        return ProcessingTier.TIER_ONE


class TesseractTableProcessor(TesseractOCRProcessor):
    """Tesseract 기반 표 전용 처리기"""
    
    def _build_tesseract_config(self, options: OCROptions) -> str:
        """표 처리에 최적화된 설정"""
        config_parts = []
        
        # 표 처리 최적화 설정
        config_parts.append("--oem 3")
        config_parts.append("--psm 6")  # 단일 텍스트 블록 (표 적합)
        
        # 표 구조 인식을 위한 추가 설정
        config_parts.append("-c preserve_interword_spaces=1")
        config_parts.append("-c textord_tabfind_find_tables=1")
        
        return " ".join(config_parts)
    
    async def _process_image_impl(self, image_path: str, options: OCROptions) -> OCRResult:
        """표 구조를 고려한 OCR 처리"""
        # 기본 OCR 수행
        result = await super()._process_image_impl(image_path, options)
        
        if result.success and options.detect_tables:
            # 표 구조 감지 및 추가
            tables = self._extract_table_structure(result.text, image_path)
            result.tables = tables
        
        return result
    
    def _extract_table_structure(self, text: str, image_path: str) -> List:
        """텍스트에서 표 구조 추출 (간단한 구현)"""
        # 실제로는 더 복잡한 표 감지 알고리즘이 필요
        from app.core.ocr_interfaces import TableData
        
        lines = text.split('\n')
        table_lines = []
        
        for line in lines:
            # 탭이나 여러 공백으로 구분된 라인을 표로 간주
            if '\t' in line or '  ' in line:
                cells = [cell.strip() for cell in line.split('\t') if cell.strip()]
                if not cells:  # 탭이 없으면 공백으로 분할
                    cells = [cell.strip() for cell in line.split('  ') if cell.strip()]
                
                if len(cells) >= 2:  # 최소 2개 셀
                    table_lines.append(cells)
        
        if len(table_lines) >= 2:  # 최소 2행
            headers = table_lines[0]
            rows = table_lines[1:]
            
            return [TableData(
                headers=headers,
                rows=rows,
                row_count=len(rows),
                column_count=len(headers),
                confidence=0.7,
                metadata={'source': 'tesseract_table_processor'}
            )]
        
        return []