"""
Tier 2 OCR 처리기 (PaddleOCR + PP-Structure)
TwoTierOCRService에서 분리된 PaddleOCR 전용 처리 로직
Single Responsibility Principle 적용
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# PaddleOCR imports
try:
    from paddleocr import PaddleOCR, PPStructureV3
    PADDLE_AVAILABLE = True
    logger.info("PaddleOCR successfully loaded")
except ImportError:
    PADDLE_AVAILABLE = False
    logger.warning("PaddleOCR not available. Install with: pip install paddlepaddle paddleocr")


@dataclass
class Tier2ProcessingOptions:
    """Tier 2 처리 옵션"""
    language: str = 'korean'
    use_angle_cls: bool = True
    use_gpu: bool = True
    show_log: bool = False
    enable_structure_analysis: bool = True
    confidence_threshold: float = 0.6
    context_tags: List[str] = None


@dataclass
class Tier2Result:
    """Tier 2 처리 결과"""
    success: bool
    text: str
    table_data: List[List[str]]
    confidence: float
    korean_accuracy: float
    structure_result: Optional[Any]
    processing_method: str
    extracted_lines: int
    korean_char_ratio: float
    error: Optional[str] = None
    processing_metadata: Dict[str, Any] = None


class Tier2Processor:
    """Tier 2 OCR 처리기 - PaddleOCR + PP-Structure 전용"""
    
    def __init__(self, options: Optional[Tier2ProcessingOptions] = None):
        """
        초기화
        
        Args:
            options: Tier 2 처리 옵션
        """
        self.options = options or Tier2ProcessingOptions()
        
        # PaddleOCR 초기화
        if PADDLE_AVAILABLE:
            try:
                self.paddle_ocr = PaddleOCR(
                    use_angle_cls=self.options.use_angle_cls,
                    lang=self.options.language,
                    show_log=self.options.show_log,
                    use_gpu=self.options.use_gpu
                )
                logger.info(f"✅ PaddleOCR initialized with {self.options.language} language support")
            except Exception as e:
                logger.error(f"PaddleOCR initialization failed: {e}")
                self.paddle_ocr = None
            
            # PP-Structure 초기화
            if self.options.enable_structure_analysis:
                try:
                    self.pp_structure = PPStructureV3(
                        lang=self.options.language,
                        show_log=self.options.show_log,
                        use_gpu=self.options.use_gpu
                    )
                    logger.info("✅ PP-Structure initialized")
                except Exception as e:
                    logger.error(f"PP-Structure initialization failed: {e}")
                    self.pp_structure = None
            else:
                self.pp_structure = None
        else:
            self.paddle_ocr = None
            self.pp_structure = None
            logger.error("❌ PaddleOCR not available")
        
        # 언어별 처리 파라미터
        self.language_params = {
            'korean': {
                'char_range': ('\uac00', '\ud7af'),
                'accuracy_weight': 0.8,
                'common_chars': ['의', '가', '를', '이', '은', '는', '에', '와']
            },
            'chinese': {
                'char_range': ('\u4e00', '\u9fff'),
                'accuracy_weight': 0.7,
                'common_chars': ['的', '一', '是', '在', '不', '了', '有', '和']
            },
            'japanese': {
                'char_range': ('\u3040', '\u30ff'),
                'accuracy_weight': 0.75,
                'common_chars': ['の', 'に', 'は', 'を', 'た', 'が', 'で', 'て']
            },
            'english': {
                'char_range': ('A', 'z'),
                'accuracy_weight': 0.9,
                'common_chars': ['the', 'and', 'of', 'to', 'a', 'in', 'is', 'it']
            }
        }
    
    def process_image(self, image_path: str, context_tags: Optional[List[str]] = None) -> Tier2Result:
        """이미지 OCR 처리 (Tier 2)"""
        if not self.paddle_ocr:
            return Tier2Result(
                success=False,
                text="",
                table_data=[],
                confidence=0,
                korean_accuracy=0,
                structure_result=None,
                processing_method="tier2_paddleocr",
                extracted_lines=0,
                korean_char_ratio=0,
                error="PaddleOCR not available"
            )
        
        try:
            logger.info(f"Starting Tier 2 processing for: {image_path}")
            
            # 컨텍스트 태그 설정
            effective_context_tags = context_tags or self.options.context_tags or []
            
            # 1. 구조 분석 (PP-Structure)
            structure_result = None
            if self.pp_structure:
                structure_result = self._analyze_structure(image_path)
            
            # 2. OCR 텍스트 추출
            ocr_result = self._extract_text(image_path)
            
            # 3. 결과 처리 및 분석
            processed_result = self._process_ocr_results(
                ocr_result, structure_result, effective_context_tags
            )
            
            # 4. 테이블 데이터 추출
            table_data = self._extract_table_data(structure_result, processed_result)
            
            # 5. 품질 메트릭 계산
            quality_metrics = self._calculate_quality_metrics(
                processed_result, self.options.language
            )
            
            # 6. 처리 메타데이터 생성
            metadata = self._generate_processing_metadata(
                image_path, effective_context_tags, structure_result, quality_metrics
            )
            
            return Tier2Result(
                success=True,
                text=processed_result['text'],
                table_data=table_data,
                confidence=quality_metrics['confidence'],
                korean_accuracy=quality_metrics['language_accuracy'],
                structure_result=structure_result,
                processing_method="tier2_paddleocr_ppstructure",
                extracted_lines=quality_metrics['line_count'],
                korean_char_ratio=quality_metrics['language_char_ratio'],
                processing_metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Tier 2 processing failed for {image_path}: {e}")
            return Tier2Result(
                success=False,
                text="",
                table_data=[],
                confidence=0,
                korean_accuracy=0,
                structure_result=None,
                processing_method="tier2_paddleocr",
                extracted_lines=0,
                korean_char_ratio=0,
                error=str(e)
            )
    
    def _analyze_structure(self, image_path: str) -> Optional[Any]:
        """PP-Structure로 문서 구조 분석"""
        try:
            if not self.pp_structure:
                return None
            
            logger.debug(f"Analyzing structure for: {image_path}")
            structure_result = self.pp_structure(image_path)
            
            logger.info(f"Structure analysis completed. Found {len(structure_result)} elements")
            return structure_result
            
        except Exception as e:
            logger.error(f"Structure analysis failed: {e}")
            return None
    
    def _extract_text(self, image_path: str) -> Optional[Any]:
        """PaddleOCR로 텍스트 추출"""
        try:
            logger.debug(f"Extracting text from: {image_path}")
            ocr_result = self.paddle_ocr.ocr(image_path)
            
            if ocr_result and ocr_result[0]:
                logger.info(f"OCR completed. Found {len(ocr_result[0])} text lines")
            else:
                logger.warning("No text detected by OCR")
            
            return ocr_result
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise
    
    def _process_ocr_results(self, ocr_result: Any, structure_result: Optional[Any],
                           context_tags: List[str]) -> Dict[str, Any]:
        """OCR 결과 처리 및 정제"""
        extracted_text = []
        confidence_scores = []
        bbox_info = []
        
        try:
            if ocr_result and ocr_result[0]:
                for line in ocr_result[0]:
                    if len(line) >= 2:
                        bbox = line[0]  # 바운딩 박스 정보
                        text_info = line[1]
                        
                        text = text_info[0]
                        confidence = text_info[1]
                        
                        # 신뢰도 필터링
                        if confidence >= self.options.confidence_threshold:
                            extracted_text.append(text)
                            confidence_scores.append(confidence)
                            bbox_info.append({
                                'text': text,
                                'confidence': confidence,
                                'bbox': bbox
                            })
            
            # 컨텍스트 기반 후처리
            processed_text = self._apply_context_processing(extracted_text, context_tags)
            
            return {
                'text': '\n'.join(processed_text),
                'raw_text_lines': extracted_text,
                'confidence_scores': confidence_scores,
                'bbox_info': bbox_info,
                'line_count': len(extracted_text)
            }
            
        except Exception as e:
            logger.error(f"OCR result processing failed: {e}")
            return {
                'text': '',
                'raw_text_lines': [],
                'confidence_scores': [],
                'bbox_info': [],
                'line_count': 0
            }
    
    def _apply_context_processing(self, text_lines: List[str], context_tags: List[str]) -> List[str]:
        """컨텍스트 기반 텍스트 후처리"""
        processed_lines = text_lines.copy()
        
        try:
            # Excel 관련 후처리
            if 'excel' in context_tags:
                processed_lines = self._process_excel_context(processed_lines)
            
            # 테이블 관련 후처리
            if 'table' in context_tags:
                processed_lines = self._process_table_context(processed_lines)
            
            # 재무 관련 후처리
            if 'financial' in context_tags:
                processed_lines = self._process_financial_context(processed_lines)
            
            # 한국어 관련 후처리
            if 'korean' in context_tags or self.options.language == 'korean':
                processed_lines = self._process_korean_context(processed_lines)
            
            return processed_lines
            
        except Exception as e:
            logger.error(f"Context processing failed: {e}")
            return text_lines
    
    def _process_excel_context(self, text_lines: List[str]) -> List[str]:
        """Excel 컨텍스트 후처리"""
        import re
        
        processed = []
        for line in text_lines:
            # 셀 참조 패턴 정리 (A1, B2 등)
            line = re.sub(r'\b([A-Z]+)(\d+)\b', r'\1\2', line)
            
            # 수식 패턴 정리
            line = re.sub(r'=\s*([A-Z]+\d+)', r'=\1', line)
            
            processed.append(line)
        
        return processed
    
    def _process_table_context(self, text_lines: List[str]) -> List[str]:
        """테이블 컨텍스트 후처리"""
        import re
        
        processed = []
        for line in text_lines:
            # 테이블 구분자 정리
            line = re.sub(r'\s{2,}', '\t', line)  # 여러 공백을 탭으로
            line = re.sub(r'\|\s*', '|', line)  # 파이프 구분자 정리
            
            processed.append(line)
        
        return processed
    
    def _process_financial_context(self, text_lines: List[str]) -> List[str]:
        """재무 컨텍스트 후처리"""
        import re
        
        processed = []
        for line in text_lines:
            # 통화 표기 정리
            line = re.sub(r'(\d+)\s*(원|won)', r'\1원', line)
            line = re.sub(r'\$\s*(\d+)', r'$\1', line)
            
            # 회계 용어 정리
            financial_terms = {
                '자산총계': '자산총계',
                '부채총계': '부채총계',
                '자본총계': '자본총계',
                '매출액': '매출액',
                '순이익': '순이익'
            }
            
            for term, normalized in financial_terms.items():
                line = re.sub(f'{term}', normalized, line, flags=re.IGNORECASE)
            
            processed.append(line)
        
        return processed
    
    def _process_korean_context(self, text_lines: List[str]) -> List[str]:
        """한국어 컨텍스트 후처리"""
        import re
        
        processed = []
        for line in text_lines:
            # 자소 분리 문제 해결 (간단한 케이스)
            line = re.sub(r'ㄱ', 'ᆨ', line)  # 종성 처리
            line = re.sub(r'ㄴ', 'ᆫ', line)
            line = re.sub(r'ㄷ', 'ᆮ', line)
            line = re.sub(r'ㄹ', 'ᆯ', line)
            
            # 한글 조사 정리
            line = re.sub(r'\s+(의|가|을|를|이|은|는)\s+', r'\1 ', line)
            
            processed.append(line)
        
        return processed
    
    def _extract_table_data(self, structure_result: Optional[Any], 
                          processed_result: Dict[str, Any]) -> List[List[str]]:
        """테이블 데이터 추출"""
        tables = []
        
        try:
            # PP-Structure 결과에서 테이블 추출
            if structure_result:
                for item in structure_result:
                    if item.get('type') == 'table' and 'res' in item:
                        table_data = self._parse_structure_table(item['res'])
                        if table_data:
                            tables.extend(table_data)
            
            # OCR 텍스트에서 테이블 추출 (fallback)
            if not tables:
                text_tables = self._extract_tables_from_text(processed_result['text'])
                tables.extend(text_tables)
            
            return tables if tables else []
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return []
    
    def _parse_structure_table(self, structure_table: Any) -> List[List[str]]:
        """PP-Structure 테이블 데이터 파싱"""
        try:
            table_data = []
            
            for row in structure_table:
                row_data = []
                for cell in row:
                    if isinstance(cell, dict) and 'text' in cell:
                        row_data.append(cell['text'].strip())
                    elif isinstance(cell, str):
                        row_data.append(cell.strip())
                    else:
                        row_data.append(str(cell).strip())
                
                if row_data and any(cell for cell in row_data):  # 빈 행 제외
                    table_data.append(row_data)
            
            return table_data
            
        except Exception as e:
            logger.error(f"Structure table parsing failed: {e}")
            return []
    
    def _extract_tables_from_text(self, text: str) -> List[List[str]]:
        """텍스트에서 테이블 구조 추출"""
        try:
            lines = text.split('\n')
            table_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 탭이나 여러 공백으로 구분된 라인을 테이블로 간주
                if '\t' in line:
                    cells = [cell.strip() for cell in line.split('\t') if cell.strip()]
                elif '  ' in line:  # 두 개 이상 공백
                    cells = [cell.strip() for cell in line.split('  ') if cell.strip()]
                else:
                    continue
                
                if len(cells) >= 2:  # 최소 2개 셀
                    table_lines.append(cells)
            
            return table_lines
            
        except Exception as e:
            logger.error(f"Text table extraction failed: {e}")
            return []
    
    def _calculate_quality_metrics(self, processed_result: Dict[str, Any], 
                                 language: str) -> Dict[str, Any]:
        """품질 메트릭 계산"""
        try:
            text = processed_result['text']
            confidence_scores = processed_result['confidence_scores']
            
            # 평균 신뢰도
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            # 언어별 정확도
            language_accuracy, char_ratio = self._calculate_language_accuracy(text, language)
            
            # 텍스트 품질 점수
            text_quality = self._calculate_text_quality_score(text)
            
            # 구조적 일관성 점수
            structure_consistency = self._calculate_structure_consistency(processed_result['raw_text_lines'])
            
            return {
                'confidence': avg_confidence,
                'language_accuracy': language_accuracy,
                'language_char_ratio': char_ratio,
                'text_quality': text_quality,
                'structure_consistency': structure_consistency,
                'line_count': processed_result['line_count'],
                'overall_quality': (avg_confidence + language_accuracy + text_quality + structure_consistency) / 4
            }
            
        except Exception as e:
            logger.error(f"Quality metrics calculation failed: {e}")
            return {
                'confidence': 0,
                'language_accuracy': 0,
                'language_char_ratio': 0,
                'text_quality': 0,
                'structure_consistency': 0,
                'line_count': 0,
                'overall_quality': 0
            }
    
    def _calculate_language_accuracy(self, text: str, language: str) -> Tuple[float, float]:
        """언어별 정확도 계산"""
        if not text or language not in self.language_params:
            return 0.0, 0.0
        
        params = self.language_params[language]
        char_range = params['char_range']
        
        # 해당 언어 문자 비율 계산
        language_chars = 0
        total_chars = 0
        
        for char in text:
            if char.isalpha() or ord(char) >= 0x80:  # 알파벳 또는 비ASCII 문자
                total_chars += 1
                if char_range[0] <= char <= char_range[1]:
                    language_chars += 1
        
        if total_chars == 0:
            return 0.0, 0.0
        
        char_ratio = language_chars / total_chars
        
        # 일반적인 단어/문자 패턴 확인
        common_pattern_score = 0.0
        if language == 'korean':
            # 한국어 조사, 어미 패턴 확인
            korean_patterns = ['의', '가', '을', '를', '이', '은', '는', '에', '와', '과', '도', '만']
            found_patterns = sum(1 for pattern in korean_patterns if pattern in text)
            common_pattern_score = min(found_patterns / len(korean_patterns), 1.0)
        
        # 최종 정확도 = 문자 비율 + 패턴 점수
        accuracy = (char_ratio * 0.7 + common_pattern_score * 0.3) * params['accuracy_weight']
        
        return min(accuracy, 1.0), char_ratio
    
    def _calculate_text_quality_score(self, text: str) -> float:
        """텍스트 품질 점수 계산"""
        if not text:
            return 0.0
        
        import re
        
        # 문제가 있는 패턴들
        problematic_patterns = [
            r'[0-9][a-zA-Z][0-9]',  # 숫자-문자-숫자 혼합
            r'[!@#$%^&*()]{3,}',    # 연속 특수문자
            r'\s{5,}',              # 과도한 공백
            r'[.]{3,}',             # 연속 점
        ]
        
        problem_count = 0
        for pattern in problematic_patterns:
            problem_count += len(re.findall(pattern, text))
        
        # 문제 비율 계산
        problem_ratio = problem_count / max(len(text.split()), 1)
        quality_score = max(1.0 - problem_ratio * 2, 0.0)
        
        return quality_score
    
    def _calculate_structure_consistency(self, text_lines: List[str]) -> float:
        """구조적 일관성 점수 계산"""
        if not text_lines:
            return 0.0
        
        # 라인 길이 일관성
        line_lengths = [len(line) for line in text_lines]
        if not line_lengths:
            return 0.0
        
        avg_length = sum(line_lengths) / len(line_lengths)
        length_variance = sum((length - avg_length) ** 2 for length in line_lengths) / len(line_lengths)
        length_consistency = max(1.0 - length_variance / (avg_length ** 2 + 1), 0.0)
        
        # 빈 라인 비율
        empty_lines = sum(1 for line in text_lines if not line.strip())
        empty_ratio = empty_lines / len(text_lines)
        empty_consistency = max(1.0 - empty_ratio, 0.0)
        
        return (length_consistency + empty_consistency) / 2
    
    def _generate_processing_metadata(self, image_path: str, context_tags: List[str],
                                    structure_result: Optional[Any],
                                    quality_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """처리 메타데이터 생성"""
        return {
            'image_info': {
                'path': image_path,
                'filename': Path(image_path).name
            },
            'processing_config': {
                'language': self.options.language,
                'use_angle_cls': self.options.use_angle_cls,
                'use_gpu': self.options.use_gpu,
                'confidence_threshold': self.options.confidence_threshold,
                'structure_analysis_enabled': self.options.enable_structure_analysis
            },
            'context_tags': context_tags,
            'structure_elements': len(structure_result) if structure_result else 0,
            'quality_metrics': quality_metrics,
            'paddle_version': self._get_paddle_version(),
            'processing_tier': 'tier2'
        }
    
    def _get_paddle_version(self) -> Optional[str]:
        """PaddleOCR 버전 정보"""
        try:
            import paddleocr
            return getattr(paddleocr, '__version__', 'unknown')
        except:
            return None
    
    def is_available(self) -> bool:
        """처리기 사용 가능 여부"""
        return PADDLE_AVAILABLE and self.paddle_ocr is not None
    
    def get_supported_languages(self) -> List[str]:
        """지원되는 언어 목록"""
        return ['korean', 'english', 'chinese', 'japanese', 'german', 'french', 'spanish']
    
    def update_language(self, language: str) -> bool:
        """언어 설정 업데이트"""
        if language not in self.get_supported_languages():
            logger.error(f"Unsupported language: {language}")
            return False
        
        try:
            # 새로운 언어로 OCR 재초기화
            self.options.language = language
            
            if PADDLE_AVAILABLE:
                self.paddle_ocr = PaddleOCR(
                    use_angle_cls=self.options.use_angle_cls,
                    lang=language,
                    show_log=self.options.show_log,
                    use_gpu=self.options.use_gpu
                )
                
                if self.options.enable_structure_analysis:
                    self.pp_structure = PPStructureV3(
                        lang=language,
                        show_log=self.options.show_log,
                        use_gpu=self.options.use_gpu
                    )
                
                logger.info(f"Language updated to: {language}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Language update failed: {e}")
            return False