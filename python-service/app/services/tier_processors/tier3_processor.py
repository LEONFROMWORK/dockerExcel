"""
Tier 3 OCR 처리기 (OpenAI GPT-4 Vision)
TwoTierOCRService에서 분리된 OpenAI Vision 전용 처리 로직
Single Responsibility Principle 적용
"""

import base64
import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import re

logger = logging.getLogger(__name__)

# OpenAI imports
try:
    import openai
    from openai import OpenAI
    OPENAI_VISION_AVAILABLE = True
    logger.info("OpenAI Vision successfully loaded")
except ImportError:
    OPENAI_VISION_AVAILABLE = False
    logger.warning("OpenAI not available. Install with: pip install openai")


@dataclass
class Tier3ProcessingOptions:
    """Tier 3 처리 옵션"""
    model: str = "gpt-4-vision-preview"
    max_tokens: int = 2000
    temperature: float = 0.1
    detail_level: str = "high"  # low, high, auto
    language_preference: str = "korean"
    enable_table_extraction: bool = True
    enable_entity_extraction: bool = True
    context_aware_prompting: bool = True


@dataclass
class Tier3Result:
    """Tier 3 처리 결과"""
    success: bool
    text: str
    tables: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
    confidence: float
    processing_method: str
    usage_metadata: Dict[str, Any]
    error: Optional[str] = None
    processing_metadata: Dict[str, Any] = None


class Tier3Processor:
    """Tier 3 OCR 처리기 - OpenAI GPT-4 Vision 전용"""
    
    def __init__(self, options: Optional[Tier3ProcessingOptions] = None):
        """
        초기화
        
        Args:
            options: Tier 3 처리 옵션
        """
        self.options = options or Tier3ProcessingOptions()
        
        # OpenAI 클라이언트 초기화
        if OPENAI_VISION_AVAILABLE:
            try:
                openai_api_key = os.getenv('OPENAI_API_KEY')
                
                if openai_api_key:
                    self.openai_client = OpenAI(api_key=openai_api_key)
                    logger.info("✅ OpenAI Vision initialized")
                else:
                    self.openai_client = None
                    logger.warning("⚠️ OpenAI API key not configured")
            except Exception as e:
                self.openai_client = None
                logger.error(f"❌ OpenAI Vision initialization failed: {e}")
        else:
            self.openai_client = None
        
        # 언어별 프롬프트 템플릿
        self.language_prompts = {
            'korean': {
                'base': "이 이미지를 분석하여 한국어 텍스트와 테이블 데이터를 정확하게 추출해주세요.",
                'focus': "특히 한국어 텍스트 인식에 집중하고, 한글 자소 분리나 오타를 주의깊게 처리해주세요.",
                'format': "추출된 텍스트와 테이블을 명확하게 구분하여 제시해주세요."
            },
            'english': {
                'base': "Please analyze this image and accurately extract English text and table data.",
                'focus': "Focus on precise text recognition and maintain original formatting.",
                'format': "Present extracted text and tables in a clear, structured format."
            },
            'chinese': {
                'base': "请分析此图像并准确提取中文文本和表格数据。",
                'focus': "特别注意中文字符识别的准确性，包括简体和繁体字。",
                'format': "请清晰地区分并呈现提取的文本和表格。"
            },
            'japanese': {
                'base': "この画像を分析して日本語テキストと表データを正確に抽出してください。",
                'focus': "ひらがな、カタカナ、漢字の認識精度に特に注意してください。",
                'format': "抽出されたテキストと表を明確に区別して提示してください。"
            }
        }
        
        # 컨텍스트별 특수 지시사항
        self.context_instructions = {
            'excel': {
                'korean': "이는 Excel 관련 이미지입니다. 셀 내용, 수식, 그리고 셀 참조를 정확히 추출해주세요.",
                'english': "This is an Excel-related image. Please accurately extract cell contents, formulas, and cell references."
            },
            'financial': {
                'korean': "재무 관련 문서입니다. 숫자, 통화 표기, 회계 용어를 특별히 주의해서 인식해주세요.",
                'english': "This is a financial document. Please pay special attention to numbers, currency notations, and accounting terms."
            },
            'table': {
                'korean': "복잡한 테이블 구조가 있을 수 있습니다. 행과 열의 관계를 정확히 파악해주세요.",
                'english': "There may be complex table structures. Please accurately identify row and column relationships."
            },
            'form': {
                'korean': "양식이나 서식 문서입니다. 항목명과 입력값을 구분해서 추출해주세요.",
                'english': "This is a form document. Please distinguish between field names and input values."
            }
        }
        
        # 출력 형식 템플릿
        self.output_formats = {
            'structured': {
                'korean': """
응답을 다음 JSON 형식으로 해주세요:
{
    "extracted_text": "추출된 전체 텍스트",
    "tables": [
        {
            "headers": ["헤더1", "헤더2", "헤더3"],
            "rows": [
                ["데이터1", "데이터2", "데이터3"],
                ["데이터4", "데이터5", "데이터6"]
            ],
            "caption": "테이블 설명"
        }
    ],
    "entities": [
        {
            "type": "날짜|금액|인명|기관명|기타",
            "value": "추출된 값",
            "confidence": 0.95
        }
    ],
    "summary": "문서 내용 요약"
}
""",
                'english': """
Please respond in the following JSON format:
{
    "extracted_text": "Complete extracted text",
    "tables": [
        {
            "headers": ["Header1", "Header2", "Header3"],
            "rows": [
                ["Data1", "Data2", "Data3"],
                ["Data4", "Data5", "Data6"]
            ],
            "caption": "Table description"
        }
    ],
    "entities": [
        {
            "type": "date|amount|person|organization|other",
            "value": "extracted value",
            "confidence": 0.95
        }
    ],
    "summary": "Document content summary"
}
"""
            }
        }
    
    def process_image(self, image_path: str, tier2_result: Optional[Dict[str, Any]] = None,
                     context_tags: Optional[List[str]] = None) -> Tier3Result:
        """이미지 OCR 처리 (Tier 3)"""
        if not self.openai_client:
            return Tier3Result(
                success=False,
                text="",
                tables=[],
                entities=[],
                confidence=0,
                processing_method="tier3_openai_vision",
                usage_metadata={},
                error="OpenAI Vision not available"
            )
        
        try:
            logger.info(f"Starting Tier 3 processing for: {image_path}")
            
            # 1. 이미지 인코딩
            image_content = self._encode_image(image_path)
            
            # 2. 프롬프트 생성
            prompt = self._build_vision_prompt(tier2_result, context_tags or [])
            
            # 3. OpenAI Vision API 호출
            response = self._call_openai_vision_api(image_content, prompt)
            
            # 4. 응답 파싱
            parsed_result = self._parse_vision_response(response)
            
            # 5. 결과 후처리
            processed_result = self._post_process_results(parsed_result, context_tags or [])
            
            # 6. 품질 검증
            quality_score = self._validate_result_quality(processed_result, tier2_result)
            
            # 7. 메타데이터 생성
            metadata = self._generate_processing_metadata(
                image_path, context_tags or [], response, quality_score
            )
            
            return Tier3Result(
                success=True,
                text=processed_result['text'],
                tables=processed_result['tables'],
                entities=processed_result['entities'],
                confidence=quality_score,
                processing_method="tier3_openai_gpt4_vision",
                usage_metadata=self._extract_usage_metadata(response),
                processing_metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Tier 3 processing failed for {image_path}: {e}")
            return Tier3Result(
                success=False,
                text="",
                tables=[],
                entities=[],
                confidence=0,
                processing_method="tier3_openai_vision",
                usage_metadata={},
                error=str(e)
            )
    
    def _encode_image(self, image_path: str) -> str:
        """이미지를 base64로 인코딩"""
        try:
            with open(image_path, 'rb') as image_file:
                image_content = base64.b64encode(image_file.read()).decode('utf-8')
            
            logger.debug(f"Image encoded: {len(image_content)} characters")
            return image_content
            
        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            raise
    
    def _build_vision_prompt(self, tier2_result: Optional[Dict[str, Any]], 
                           context_tags: List[str]) -> str:
        """OpenAI Vision용 프롬프트 생성"""
        try:
            language = self.options.language_preference
            language_config = self.language_prompts.get(language, self.language_prompts['korean'])
            
            # 기본 프롬프트
            prompt_parts = [
                language_config['base'],
                "",
                language_config['focus'],
                ""
            ]
            
            # 컨텍스트별 지시사항 추가
            context_instructions = []
            for tag in context_tags:
                if tag in self.context_instructions:
                    instruction = self.context_instructions[tag].get(language, 
                        self.context_instructions[tag].get('korean', ''))
                    if instruction:
                        context_instructions.append(instruction)
            
            if context_instructions:
                prompt_parts.append("추가 지시사항:")
                prompt_parts.extend(context_instructions)
                prompt_parts.append("")
            
            # Tier 2 결과 참고 (있는 경우)
            if tier2_result and tier2_result.get('success') and tier2_result.get('text'):
                tier2_text = tier2_result['text'][:300]  # 처음 300자만
                prompt_parts.extend([
                    "참고: 기본 OCR 결과:",
                    f"```{tier2_text}...```",
                    "위 결과를 참고하되, 더 정확하고 상세한 분석을 제공해주세요.",
                    ""
                ])
            
            # 출력 형식 지시
            if self.options.enable_table_extraction or self.options.enable_entity_extraction:
                format_template = self.output_formats['structured'].get(language,
                    self.output_formats['structured']['korean'])
                prompt_parts.append(format_template)
            else:
                prompt_parts.extend([
                    language_config['format'],
                    "단순한 텍스트 추출만 필요한 경우 일반 텍스트로 응답해주세요."
                ])
            
            return '\n'.join(prompt_parts)
            
        except Exception as e:
            logger.error(f"Prompt building failed: {e}")
            return "Please extract text from this image accurately."
    
    def _call_openai_vision_api(self, image_content: str, prompt: str) -> Any:
        """OpenAI Vision API 호출"""
        try:
            # MIME 타입 결정
            mime_type = "image/jpeg"  # 기본값
            
            response = self.openai_client.chat.completions.create(
                model=self.options.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_content}",
                                    "detail": self.options.detail_level
                                }
                            }
                        ]
                    }
                ],
                max_tokens=self.options.max_tokens,
                temperature=self.options.temperature
            )
            
            logger.info("OpenAI Vision API call completed successfully")
            return response
            
        except Exception as e:
            logger.error(f"OpenAI Vision API call failed: {e}")
            raise
    
    def _parse_vision_response(self, response: Any) -> Dict[str, Any]:
        """OpenAI Vision 응답 파싱"""
        try:
            content = response.choices[0].message.content
            
            # JSON 응답 시도
            if self.options.enable_table_extraction or self.options.enable_entity_extraction:
                try:
                    # JSON 블록 추출
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        # 직접 JSON 파싱 시도
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start != -1 and json_end > json_start:
                            json_str = content[json_start:json_end]
                        else:
                            raise ValueError("No JSON found")
                    
                    parsed_json = json.loads(json_str)
                    return {
                        'text': parsed_json.get('extracted_text', content),
                        'tables': parsed_json.get('tables', []),
                        'entities': parsed_json.get('entities', []),
                        'summary': parsed_json.get('summary', ''),
                        'raw_response': content
                    }
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"JSON parsing failed, falling back to text extraction: {e}")
            
            # 일반 텍스트 처리
            tables = self._extract_tables_from_text(content)
            entities = self._extract_entities_from_text(content) if self.options.enable_entity_extraction else []
            
            return {
                'text': content,
                'tables': tables,
                'entities': entities,
                'summary': '',
                'raw_response': content
            }
            
        except Exception as e:
            logger.error(f"Vision response parsing failed: {e}")
            return {
                'text': '',
                'tables': [],
                'entities': [],
                'summary': '',
                'raw_response': str(response) if response else ''
            }
    
    def _extract_tables_from_text(self, text: str) -> List[Dict[str, Any]]:
        """텍스트에서 테이블 추출"""
        tables = []
        
        try:
            # 마크다운 테이블 패턴 찾기
            table_pattern = r'(\|[^\n]*\|(?:\n\|[^\n]*\|)*)'
            table_matches = re.findall(table_pattern, text, re.MULTILINE)
            
            for i, match in enumerate(table_matches):
                table_data = self._parse_markdown_table(match)
                if table_data:
                    tables.append({
                        'headers': table_data.get('headers', []),
                        'rows': table_data.get('rows', []),
                        'caption': f"Table {i+1}",
                        'row_count': len(table_data.get('rows', [])),
                        'column_count': len(table_data.get('headers', [])),
                        'source': 'vision_markdown_extraction'
                    })
            
            # 간단한 테이블 패턴도 시도
            if not tables:
                simple_tables = self._extract_simple_tables(text)
                tables.extend(simple_tables)
            
            return tables
            
        except Exception as e:
            logger.error(f"Table extraction from text failed: {e}")
            return []
    
    def _parse_markdown_table(self, table_text: str) -> Optional[Dict[str, Any]]:
        """마크다운 테이블 파싱"""
        try:
            lines = table_text.strip().split('\n')
            if len(lines) < 2:
                return None
            
            # 헤더 추출
            header_line = lines[0]
            headers = [cell.strip() for cell in header_line.split('|')[1:-1]]
            
            # 데이터 행 추출 (구분선 스킵)
            rows = []
            for line in lines[2:]:  # 첫 번째는 헤더, 두 번째는 구분선
                if re.match(r'^\s*\|[\s\-\|:]*\|\s*$', line):
                    continue  # 구분선 스킵
                
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if cells and len(cells) == len(headers):
                    rows.append(cells)
            
            if headers and rows:
                return {'headers': headers, 'rows': rows}
            
            return None
            
        except Exception as e:
            logger.error(f"Markdown table parsing failed: {e}")
            return None
    
    def _extract_simple_tables(self, text: str) -> List[Dict[str, Any]]:
        """간단한 테이블 패턴 추출"""
        tables = []
        
        try:
            lines = text.split('\n')
            table_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    if table_lines and len(table_lines) >= 2:
                        table = self._process_simple_table_lines(table_lines)
                        if table:
                            tables.append(table)
                    table_lines = []
                    continue
                
                # 테이블 라인 감지 (탭, 여러 공백, 특정 구분자)
                if '\t' in line or re.search(r'\s{3,}', line) or line.count('|') >= 2:
                    table_lines.append(line)
                else:
                    if table_lines and len(table_lines) >= 2:
                        table = self._process_simple_table_lines(table_lines)
                        if table:
                            tables.append(table)
                    table_lines = []
            
            # 마지막 테이블 처리
            if table_lines and len(table_lines) >= 2:
                table = self._process_simple_table_lines(table_lines)
                if table:
                    tables.append(table)
            
            return tables
            
        except Exception as e:
            logger.error(f"Simple table extraction failed: {e}")
            return []
    
    def _process_simple_table_lines(self, lines: List[str]) -> Optional[Dict[str, Any]]:
        """간단한 테이블 라인들 처리"""
        try:
            processed_rows = []
            
            for line in lines:
                if '\t' in line:
                    cells = [cell.strip() for cell in line.split('\t') if cell.strip()]
                elif '|' in line:
                    cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                else:
                    cells = [cell.strip() for cell in re.split(r'\s{2,}', line) if cell.strip()]
                
                if cells and len(cells) >= 2:
                    processed_rows.append(cells)
            
            if len(processed_rows) < 2:
                return None
            
            # 첫 번째 행을 헤더로 가정
            headers = processed_rows[0]
            rows = processed_rows[1:]
            
            # 열 개수 일관성 확인
            expected_cols = len(headers)
            consistent_rows = [row for row in rows if len(row) == expected_cols]
            
            if len(consistent_rows) < len(rows) * 0.7:  # 70% 이상 일관성
                return None
            
            return {
                'headers': headers,
                'rows': consistent_rows,
                'caption': 'Extracted Table',
                'row_count': len(consistent_rows),
                'column_count': len(headers),
                'source': 'vision_simple_extraction'
            }
            
        except Exception as e:
            logger.error(f"Simple table processing failed: {e}")
            return None
    
    def _extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """텍스트에서 엔티티 추출"""
        entities = []
        
        try:
            # 날짜 패턴
            date_patterns = [
                r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}',
                r'\d{1,2}[-/.]\d{1,2}[-/.]\d{4}',
                r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일'
            ]
            
            for pattern in date_patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    entities.append({
                        'type': 'date',
                        'value': match.group(),
                        'confidence': 0.9,
                        'position': {'start': match.start(), 'end': match.end()}
                    })
            
            # 금액 패턴
            amount_patterns = [
                r'\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
                r'\d{1,3}(?:,\d{3})*\s*원',
                r'\d+(?:,\d{3})*(?:\.\d+)?\s*(?:천원|만원|억원|조원)'
            ]
            
            for pattern in amount_patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    entities.append({
                        'type': 'amount',
                        'value': match.group(),
                        'confidence': 0.85,
                        'position': {'start': match.start(), 'end': match.end()}
                    })
            
            # 이메일 패턴
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            matches = re.finditer(email_pattern, text)
            for match in matches:
                entities.append({
                    'type': 'email',
                    'value': match.group(),
                    'confidence': 0.95,
                    'position': {'start': match.start(), 'end': match.end()}
                })
            
            return entities
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    def _post_process_results(self, parsed_result: Dict[str, Any], 
                            context_tags: List[str]) -> Dict[str, Any]:
        """결과 후처리"""
        try:
            processed = parsed_result.copy()
            
            # 텍스트 정제
            if 'text' in processed:
                processed['text'] = self._clean_extracted_text(processed['text'], context_tags)
            
            # 테이블 데이터 정제
            if 'tables' in processed:
                processed['tables'] = self._clean_table_data(processed['tables'])
            
            # 엔티티 중복 제거 및 정제
            if 'entities' in processed:
                processed['entities'] = self._clean_entities(processed['entities'])
            
            return processed
            
        except Exception as e:
            logger.error(f"Result post-processing failed: {e}")
            return parsed_result
    
    def _clean_extracted_text(self, text: str, context_tags: List[str]) -> str:
        """추출된 텍스트 정제"""
        try:
            # 기본 정제
            cleaned = text.strip()
            
            # 과도한 공백 제거
            cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
            cleaned = re.sub(r'[ \t]+', ' ', cleaned)
            
            # 컨텍스트별 정제
            if 'financial' in context_tags:
                # 통화 표기 정리
                cleaned = re.sub(r'(\d+)\s*원', r'\1원', cleaned)
                cleaned = re.sub(r'\$\s*(\d+)', r'$\1', cleaned)
            
            if 'korean' in context_tags:
                # 한국어 조사 공백 정리
                cleaned = re.sub(r'\s+(의|가|을|를|이|은|는|에|와|과)\s+', r'\1 ', cleaned)
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Text cleaning failed: {e}")
            return text
    
    def _clean_table_data(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """테이블 데이터 정제"""
        cleaned_tables = []
        
        try:
            for table in tables:
                if not isinstance(table, dict):
                    continue
                
                cleaned_table = table.copy()
                
                # 헤더 정제
                if 'headers' in cleaned_table:
                    cleaned_table['headers'] = [
                        header.strip() for header in cleaned_table['headers'] if header.strip()
                    ]
                
                # 행 데이터 정제
                if 'rows' in cleaned_table:
                    cleaned_rows = []
                    for row in cleaned_table['rows']:
                        cleaned_row = [cell.strip() for cell in row if isinstance(cell, str)]
                        if cleaned_row:  # 빈 행 제외
                            cleaned_rows.append(cleaned_row)
                    cleaned_table['rows'] = cleaned_rows
                    cleaned_table['row_count'] = len(cleaned_rows)
                
                if cleaned_table.get('headers') or cleaned_table.get('rows'):
                    cleaned_tables.append(cleaned_table)
            
            return cleaned_tables
            
        except Exception as e:
            logger.error(f"Table data cleaning failed: {e}")
            return tables
    
    def _clean_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """엔티티 데이터 정제 및 중복 제거"""
        try:
            cleaned_entities = []
            seen_values = set()
            
            for entity in entities:
                if not isinstance(entity, dict) or 'value' not in entity:
                    continue
                
                value = entity['value'].strip()
                if not value or value in seen_values:
                    continue
                
                seen_values.add(value)
                
                cleaned_entity = {
                    'type': entity.get('type', 'unknown'),
                    'value': value,
                    'confidence': min(entity.get('confidence', 0.5), 1.0),
                }
                
                if 'position' in entity:
                    cleaned_entity['position'] = entity['position']
                
                cleaned_entities.append(cleaned_entity)
            
            # 신뢰도 순으로 정렬
            cleaned_entities.sort(key=lambda x: x['confidence'], reverse=True)
            
            return cleaned_entities
            
        except Exception as e:
            logger.error(f"Entity cleaning failed: {e}")
            return entities
    
    def _validate_result_quality(self, processed_result: Dict[str, Any],
                               tier2_result: Optional[Dict[str, Any]]) -> float:
        """결과 품질 검증"""
        try:
            quality_factors = []
            
            # 텍스트 품질
            text = processed_result.get('text', '')
            if text:
                text_quality = min(len(text) / 100, 1.0)  # 기본 점수
                quality_factors.append(text_quality * 0.4)
            
            # 테이블 품질
            tables = processed_result.get('tables', [])
            if tables:
                table_quality = min(len(tables) * 0.3, 1.0)
                quality_factors.append(table_quality * 0.3)
            
            # 엔티티 품질
            entities = processed_result.get('entities', [])
            if entities:
                entity_quality = min(len(entities) * 0.2, 1.0)
                quality_factors.append(entity_quality * 0.2)
            
            # Tier 2와의 일관성 (있는 경우)
            if tier2_result and tier2_result.get('text'):
                consistency = self._calculate_consistency_score(
                    text, tier2_result['text']
                )
                quality_factors.append(consistency * 0.1)
            
            # GPT-4 Vision은 일반적으로 높은 품질
            base_quality = 0.95
            
            if quality_factors:
                calculated_quality = sum(quality_factors)
                return min(base_quality, calculated_quality + 0.7)
            
            return base_quality
            
        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return 0.9  # 기본 높은 품질
    
    def _calculate_consistency_score(self, vision_text: str, tier2_text: str) -> float:
        """Tier 2 결과와의 일관성 점수"""
        try:
            if not vision_text or not tier2_text:
                return 0.5
            
            # 간단한 단어 기반 유사도
            vision_words = set(vision_text.lower().split())
            tier2_words = set(tier2_text.lower().split())
            
            if not vision_words and not tier2_words:
                return 1.0
            
            intersection = vision_words.intersection(tier2_words)
            union = vision_words.union(tier2_words)
            
            similarity = len(intersection) / len(union) if union else 0.0
            return similarity
            
        except Exception as e:
            logger.error(f"Consistency calculation failed: {e}")
            return 0.5
    
    def _extract_usage_metadata(self, response: Any) -> Dict[str, Any]:
        """사용량 메타데이터 추출"""
        try:
            if hasattr(response, 'usage'):
                usage = response.usage
                return {
                    'prompt_tokens': usage.prompt_tokens,
                    'completion_tokens': usage.completion_tokens,
                    'total_tokens': usage.total_tokens,
                    'model': self.options.model
                }
            return {}
            
        except Exception as e:
            logger.error(f"Usage metadata extraction failed: {e}")
            return {}
    
    def _generate_processing_metadata(self, image_path: str, context_tags: List[str],
                                    response: Any, quality_score: float) -> Dict[str, Any]:
        """처리 메타데이터 생성"""
        return {
            'image_info': {
                'path': image_path,
                'filename': Path(image_path).name
            },
            'processing_config': {
                'model': self.options.model,
                'max_tokens': self.options.max_tokens,
                'temperature': self.options.temperature,
                'detail_level': self.options.detail_level,
                'language_preference': self.options.language_preference
            },
            'context_tags': context_tags,
            'quality_score': quality_score,
            'openai_model': self.options.model,
            'processing_tier': 'tier3'
        }
    
    def is_available(self) -> bool:
        """처리기 사용 가능 여부"""
        return OPENAI_VISION_AVAILABLE and self.openai_client is not None
    
    def get_supported_models(self) -> List[str]:
        """지원되는 모델 목록"""
        return ["gpt-4-vision-preview", "gpt-4o", "gpt-4o-mini"]
    
    def update_model(self, model: str) -> bool:
        """모델 설정 업데이트"""
        if model not in self.get_supported_models():
            logger.error(f"Unsupported model: {model}")
            return False
        
        self.options.model = model
        logger.info(f"Model updated to: {model}")
        return True