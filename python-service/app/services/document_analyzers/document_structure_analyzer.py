"""
문서 구조 분석기
TransformerOCRService에서 분리된 문서 구조 분석 로직
Single Responsibility Principle 적용
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from app.core.ocr_interfaces import (
    LanguageCode, DocumentType, TableData
)

logger = logging.getLogger(__name__)


class DocumentSection(Enum):
    """문서 섹션 타입"""
    HEADER = "header"
    TITLE = "title"
    SUBTITLE = "subtitle"
    BODY = "body"
    TABLE = "table"
    LIST = "list"
    FOOTER = "footer"
    SIGNATURE = "signature"
    DATE = "date"
    AMOUNT = "amount"
    UNKNOWN = "unknown"


@dataclass
class DocumentElement:
    """문서 요소"""
    content: str
    section_type: DocumentSection
    confidence: float
    position: Dict[str, int]  # start, end positions
    metadata: Dict[str, Any]


@dataclass
class DocumentStructure:
    """문서 구조"""
    elements: List[DocumentElement]
    document_type: DocumentType
    layout_confidence: float
    tables: List[TableData]
    hierarchical_structure: Dict[str, Any]


class DocumentStructureAnalyzer:
    """문서 구조 분석기 - SOLID 원칙 적용"""
    
    def __init__(self):
        # 언어별 구조 패턴
        self.structure_patterns = {
            LanguageCode.KOREAN: {
                'title_patterns': [
                    r'^[가-힣\s]{2,20}(계산서|명세서|보고서|신청서|계약서)$',
                    r'^[가-힣\s]{2,30}(주식회사|기업|회사)\s*',
                    r'^\d{4}년\s*\d{1,2}월\s*[가-힣\s]{5,30}$'
                ],
                'header_patterns': [
                    r'^(제목|건명|안건|과목):\s*',
                    r'^(일자|날짜|기간):\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}',
                    r'^(담당자|작성자|신청인):\s*[가-힣]{2,10}'
                ],
                'amount_patterns': [
                    r'(합계|총액|금액|가격|단가):\s*[\d,]+\s*원',
                    r'[\d,]+\s*원',
                    r'\(\s*[\d,]+\s*\)',  # 괄호 표시 (손실)
                ],
                'date_patterns': [
                    r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
                    r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}',
                    r'\d{1,2}월\s*\d{1,2}일'
                ],
                'signature_patterns': [
                    r'(인)\s*$',
                    r'(서명|날인|도장)\s*$',
                    r'[가-힣]{2,10}\s*(주식회사|회사|기관)\s*(인)?\s*$'
                ]
            },
            LanguageCode.ENGLISH: {
                'title_patterns': [
                    r'^[A-Z][A-Za-z\s]{5,50}(Statement|Report|Invoice|Contract)$',
                    r'^[A-Z][A-Za-z\s&.]{5,50}(Inc\.|Corp\.|LLC|Ltd\.)$',
                    r'^(FINANCIAL|INCOME|BALANCE|CASH FLOW)\s+STATEMENT$'
                ],
                'header_patterns': [
                    r'^(Subject|Title|Re):\s*',
                    r'^(Date|Period|From|To):\s*\d{1,2}[-/.]\d{1,2}[-/.]\d{4}',
                    r'^(Prepared by|Author|Contact):\s*[A-Za-z\s]{2,30}'
                ],
                'amount_patterns': [
                    r'(Total|Amount|Price|Cost):\s*\$?[\d,]+(\.\d{2})?',
                    r'\$[\d,]+(\.\d{2})?',
                    r'\(\s*\$?[\d,]+(\.\d{2})?\s*\)',  # Negative amounts
                ],
                'date_patterns': [
                    r'\d{1,2}[-/.]\d{1,2}[-/.]\d{4}',
                    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}'
                ],
                'signature_patterns': [
                    r'Signature:\s*$',
                    r'Signed by:\s*[A-Za-z\s]+$',
                    r'[A-Za-z\s]{2,30}\s*(Inc\.|Corp\.|LLC)\s*$'
                ]
            }
        }
        
        # 테이블 감지 패턴
        self.table_indicators = [
            r'\t',  # 탭 구분
            r'\s{3,}',  # 여러 공백으로 구분
            r'\|',  # 파이프로 구분
            r'[-=]{3,}',  # 구분선
        ]
        
        # 리스트 감지 패턴
        self.list_patterns = [
            r'^\s*[\d]+\.\s+',  # 숫자 리스트
            r'^\s*[a-zA-Z]\.\s+',  # 알파벳 리스트
            r'^\s*[-*•]\s+',  # 불릿 리스트
            r'^\s*[가-힣]\.\s+',  # 한글 리스트
        ]
        
        # 문서 타입별 특화 패턴
        self.document_type_patterns = {
            DocumentType.FINANCIAL_STATEMENT: {
                'required_sections': ['title', 'amounts', 'date'],
                'key_terms': ['자산', '부채', '자본', '매출', '이익', 'assets', 'liabilities', 'equity', 'revenue', 'income'],
                'typical_structure': ['header', 'title', 'table', 'amounts', 'footer']
            },
            DocumentType.INVOICE: {
                'required_sections': ['title', 'amounts', 'date'],
                'key_terms': ['청구서', '송장', '세금계산서', 'invoice', 'bill', 'tax invoice'],
                'typical_structure': ['header', 'title', 'body', 'table', 'amounts', 'signature']
            },
            DocumentType.CONTRACT: {
                'required_sections': ['title', 'body', 'signature'],
                'key_terms': ['계약서', '협약서', '약정서', 'contract', 'agreement', 'terms'],
                'typical_structure': ['header', 'title', 'body', 'signature', 'date']
            }
        }
    
    def analyze_document_structure(self, text: str, language: LanguageCode, 
                                 document_type: DocumentType = DocumentType.UNKNOWN) -> DocumentStructure:
        """문서 구조 분석"""
        try:
            # 1. 텍스트를 라인별로 분할
            lines = text.split('\n')
            
            # 2. 각 라인 분석
            elements = []
            for i, line in enumerate(lines):
                element = self._analyze_line(line.strip(), i, language)
                if element:
                    elements.append(element)
            
            # 3. 테이블 구조 감지
            tables = self._detect_tables(text, language)
            
            # 4. 문서 타입 재검증
            if document_type == DocumentType.UNKNOWN:
                document_type = self._classify_document_type(elements, language)
            
            # 5. 계층 구조 생성
            hierarchical_structure = self._build_hierarchical_structure(elements, document_type)
            
            # 6. 레이아웃 신뢰도 계산
            layout_confidence = self._calculate_layout_confidence(elements, document_type)
            
            return DocumentStructure(
                elements=elements,
                document_type=document_type,
                layout_confidence=layout_confidence,
                tables=tables,
                hierarchical_structure=hierarchical_structure
            )
            
        except Exception as e:
            logger.error(f"Document structure analysis failed: {e}")
            return DocumentStructure(
                elements=[],
                document_type=DocumentType.UNKNOWN,
                layout_confidence=0.0,
                tables=[],
                hierarchical_structure={}
            )
    
    def _analyze_line(self, line: str, line_number: int, language: LanguageCode) -> Optional[DocumentElement]:
        """라인별 분석"""
        if not line:
            return None
        
        patterns = self.structure_patterns.get(language, {})
        
        # 1. 제목 패턴 확인
        for pattern in patterns.get('title_patterns', []):
            if re.match(pattern, line, re.IGNORECASE):
                return DocumentElement(
                    content=line,
                    section_type=DocumentSection.TITLE,
                    confidence=0.9,
                    position={'line': line_number, 'start': 0, 'end': len(line)},
                    metadata={'pattern_matched': pattern}
                )
        
        # 2. 헤더 패턴 확인
        for pattern in patterns.get('header_patterns', []):
            if re.match(pattern, line, re.IGNORECASE):
                return DocumentElement(
                    content=line,
                    section_type=DocumentSection.HEADER,
                    confidence=0.85,
                    position={'line': line_number, 'start': 0, 'end': len(line)},
                    metadata={'pattern_matched': pattern}
                )
        
        # 3. 금액 패턴 확인
        for pattern in patterns.get('amount_patterns', []):
            if re.search(pattern, line):
                return DocumentElement(
                    content=line,
                    section_type=DocumentSection.AMOUNT,
                    confidence=0.8,
                    position={'line': line_number, 'start': 0, 'end': len(line)},
                    metadata={'pattern_matched': pattern, 'contains_amount': True}
                )
        
        # 4. 날짜 패턴 확인
        for pattern in patterns.get('date_patterns', []):
            if re.search(pattern, line):
                return DocumentElement(
                    content=line,
                    section_type=DocumentSection.DATE,
                    confidence=0.85,
                    position={'line': line_number, 'start': 0, 'end': len(line)},
                    metadata={'pattern_matched': pattern, 'contains_date': True}
                )
        
        # 5. 서명 패턴 확인
        for pattern in patterns.get('signature_patterns', []):
            if re.search(pattern, line, re.IGNORECASE):
                return DocumentElement(
                    content=line,
                    section_type=DocumentSection.SIGNATURE,
                    confidence=0.8,
                    position={'line': line_number, 'start': 0, 'end': len(line)},
                    metadata={'pattern_matched': pattern}
                )
        
        # 6. 테이블 라인 확인
        if self._is_table_line(line):
            return DocumentElement(
                content=line,
                section_type=DocumentSection.TABLE,
                confidence=0.75,
                position={'line': line_number, 'start': 0, 'end': len(line)},
                metadata={'table_indicators': self._get_table_indicators(line)}
            )
        
        # 7. 리스트 라인 확인
        if self._is_list_line(line):
            return DocumentElement(
                content=line,
                section_type=DocumentSection.LIST,
                confidence=0.7,
                position={'line': line_number, 'start': 0, 'end': len(line)},
                metadata={'list_type': self._get_list_type(line)}
            )
        
        # 8. 기본 바디 텍스트
        return DocumentElement(
            content=line,
            section_type=DocumentSection.BODY,
            confidence=0.5,
            position={'line': line_number, 'start': 0, 'end': len(line)},
            metadata={}
        )
    
    def _is_table_line(self, line: str) -> bool:
        """테이블 라인 여부 확인"""
        for indicator in self.table_indicators:
            if re.search(indicator, line):
                return True
        
        # 숫자가 많고 규칙적인 패턴이 있는 경우
        numbers = re.findall(r'\d+', line)
        if len(numbers) >= 3:
            return True
        
        return False
    
    def _get_table_indicators(self, line: str) -> List[str]:
        """테이블 구분자 목록 반환"""
        indicators = []
        for indicator in self.table_indicators:
            if re.search(indicator, line):
                indicators.append(indicator)
        return indicators
    
    def _is_list_line(self, line: str) -> bool:
        """리스트 라인 여부 확인"""
        for pattern in self.list_patterns:
            if re.match(pattern, line):
                return True
        return False
    
    def _get_list_type(self, line: str) -> str:
        """리스트 타입 확인"""
        if re.match(r'^\s*[\d]+\.\s+', line):
            return 'numbered'
        elif re.match(r'^\s*[a-zA-Z]\.\s+', line):
            return 'alphabetic'
        elif re.match(r'^\s*[-*•]\s+', line):
            return 'bullet'
        elif re.match(r'^\s*[가-힣]\.\s+', line):
            return 'korean_alphabetic'
        return 'unknown'
    
    def _detect_tables(self, text: str, language: LanguageCode) -> List[TableData]:
        """테이블 구조 감지"""
        tables = []
        lines = text.split('\n')
        
        current_table_lines = []
        in_table = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if in_table and current_table_lines:
                    # 테이블 종료
                    table = self._parse_table_lines(current_table_lines)
                    if table:
                        tables.append(table)
                    current_table_lines = []
                    in_table = False
                continue
            
            if self._is_table_line(line):
                current_table_lines.append(line)
                in_table = True
            elif in_table:
                # 테이블 중간에 일반 텍스트가 오면 테이블 종료
                if current_table_lines:
                    table = self._parse_table_lines(current_table_lines)
                    if table:
                        tables.append(table)
                current_table_lines = []
                in_table = False
        
        # 마지막 테이블 처리
        if current_table_lines:
            table = self._parse_table_lines(current_table_lines)
            if table:
                tables.append(table)
        
        return tables
    
    def _parse_table_lines(self, lines: List[str]) -> Optional[TableData]:
        """테이블 라인들을 파싱하여 TableData 생성"""
        if not lines or len(lines) < 2:
            return None
        
        try:
            # 구분자 결정
            separator = self._determine_table_separator(lines)
            
            # 각 라인을 셀로 분할
            rows = []
            for line in lines:
                if separator == 'whitespace':
                    # 여러 공백으로 분할
                    cells = re.split(r'\s{2,}', line.strip())
                elif separator == 'tab':
                    cells = line.split('\t')
                elif separator == 'pipe':
                    cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                else:
                    # 기본적으로 공백으로 분할
                    cells = line.split()
                
                if cells:
                    rows.append([cell.strip() for cell in cells])
            
            if not rows:
                return None
            
            # 첫 번째 행을 헤더로 가정
            headers = rows[0]
            data_rows = rows[1:] if len(rows) > 1 else []
            
            # 열 개수 일관성 확인
            max_cols = max(len(row) for row in rows)
            consistent_cols = sum(1 for row in rows if len(row) == max_cols) / len(rows)
            
            if consistent_cols < 0.7:  # 70% 이상 일관성이 있어야 함
                return None
            
            return TableData(
                headers=headers,
                rows=data_rows,
                row_count=len(data_rows),
                column_count=len(headers),
                confidence=0.8 * consistent_cols,
                metadata={
                    'separator': separator,
                    'source': 'document_structure_analyzer',
                    'consistency_score': consistent_cols
                }
            )
            
        except Exception as e:
            logger.error(f"Table parsing failed: {e}")
            return None
    
    def _determine_table_separator(self, lines: List[str]) -> str:
        """테이블 구분자 결정"""
        # 탭 구분자 확인
        tab_count = sum(1 for line in lines if '\t' in line)
        if tab_count > len(lines) * 0.7:
            return 'tab'
        
        # 파이프 구분자 확인
        pipe_count = sum(1 for line in lines if '|' in line)
        if pipe_count > len(lines) * 0.7:
            return 'pipe'
        
        # 여러 공백 구분자 확인
        whitespace_count = sum(1 for line in lines if re.search(r'\s{2,}', line))
        if whitespace_count > len(lines) * 0.7:
            return 'whitespace'
        
        return 'space'
    
    def _classify_document_type(self, elements: List[DocumentElement], language: LanguageCode) -> DocumentType:
        """요소들을 기반으로 문서 타입 분류"""
        content_text = ' '.join(element.content for element in elements).lower()
        
        scores = {}
        
        for doc_type, config in self.document_type_patterns.items():
            score = 0
            
            # 키워드 매칭
            for term in config['key_terms']:
                if term.lower() in content_text:
                    score += 1
            
            # 필수 섹션 확인
            sections_found = set(element.section_type.value for element in elements)
            required_sections = set(config['required_sections'])
            section_match_ratio = len(sections_found.intersection(required_sections)) / len(required_sections)
            score += section_match_ratio * 3
            
            scores[doc_type] = score
        
        # 가장 높은 점수의 문서 타입 반환
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] > 1.0:  # 최소 임계값
                return best_type
        
        return DocumentType.UNKNOWN
    
    def _build_hierarchical_structure(self, elements: List[DocumentElement], 
                                    document_type: DocumentType) -> Dict[str, Any]:
        """계층적 문서 구조 생성"""
        structure = {
            'document_type': document_type.value,
            'sections': {},
            'flow': []
        }
        
        # 섹션별 그룹화
        for element in elements:
            section_name = element.section_type.value
            if section_name not in structure['sections']:
                structure['sections'][section_name] = []
            
            structure['sections'][section_name].append({
                'content': element.content,
                'confidence': element.confidence,
                'position': element.position,
                'metadata': element.metadata
            })
        
        # 문서 흐름 생성
        for element in elements:
            structure['flow'].append({
                'section': element.section_type.value,
                'content_preview': element.content[:50] + '...' if len(element.content) > 50 else element.content,
                'line': element.position.get('line', 0)
            })
        
        return structure
    
    def _calculate_layout_confidence(self, elements: List[DocumentElement], 
                                   document_type: DocumentType) -> float:
        """레이아웃 신뢰도 계산"""
        if not elements:
            return 0.0
        
        # 기본 신뢰도: 요소들의 평균 신뢰도
        avg_confidence = sum(element.confidence for element in elements) / len(elements)
        
        # 문서 타입별 구조 점수
        structure_score = 0.0
        
        if document_type in self.document_type_patterns:
            config = self.document_type_patterns[document_type]
            
            # 필수 섹션 존재 확인
            found_sections = set(element.section_type.value for element in elements)
            required_sections = set(config['required_sections'])
            structure_score = len(found_sections.intersection(required_sections)) / len(required_sections)
            
            # 전형적인 구조 순서 확인
            typical_structure = config.get('typical_structure', [])
            if typical_structure:
                actual_flow = [element.section_type.value for element in elements]
                order_score = self._calculate_order_similarity(actual_flow, typical_structure)
                structure_score = (structure_score + order_score) / 2
        
        # 최종 신뢰도: 평균 신뢰도와 구조 점수의 가중 평균
        final_confidence = avg_confidence * 0.6 + structure_score * 0.4
        
        return min(final_confidence, 1.0)
    
    def _calculate_order_similarity(self, actual: List[str], expected: List[str]) -> float:
        """구조 순서 유사도 계산"""
        if not actual or not expected:
            return 0.0
        
        # LCS (Longest Common Subsequence) 기반 유사도
        def lcs_length(seq1, seq2):
            m, n = len(seq1), len(seq2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if seq1[i-1] == seq2[j-1]:
                        dp[i][j] = dp[i-1][j-1] + 1
                    else:
                        dp[i][j] = max(dp[i-1][j], dp[i][j-1])
            
            return dp[m][n]
        
        lcs_len = lcs_length(actual, expected)
        similarity = lcs_len / max(len(actual), len(expected))
        
        return similarity
    
    def extract_key_information(self, structure: DocumentStructure, 
                              target_types: List[DocumentSection] = None) -> Dict[str, Any]:
        """구조에서 핵심 정보 추출"""
        if target_types is None:
            target_types = [DocumentSection.TITLE, DocumentSection.AMOUNT, 
                          DocumentSection.DATE, DocumentSection.SIGNATURE]
        
        key_info = {}
        
        for element in structure.elements:
            if element.section_type in target_types:
                section_name = element.section_type.value
                if section_name not in key_info:
                    key_info[section_name] = []
                
                key_info[section_name].append({
                    'content': element.content,
                    'confidence': element.confidence,
                    'metadata': element.metadata
                })
        
        # 테이블 정보 추가
        if structure.tables:
            key_info['tables'] = []
            for table in structure.tables:
                key_info['tables'].append({
                    'headers': table.headers,
                    'row_count': table.row_count,
                    'column_count': table.column_count,
                    'confidence': table.confidence
                })
        
        return key_info
    
    def get_document_summary(self, structure: DocumentStructure) -> Dict[str, Any]:
        """문서 구조 요약"""
        return {
            'document_type': structure.document_type.value,
            'total_elements': len(structure.elements),
            'section_counts': {
                section_type.value: sum(1 for elem in structure.elements 
                                      if elem.section_type == section_type)
                for section_type in DocumentSection
            },
            'table_count': len(structure.tables),
            'layout_confidence': structure.layout_confidence,
            'has_amounts': any(elem.section_type == DocumentSection.AMOUNT 
                             for elem in structure.elements),
            'has_dates': any(elem.section_type == DocumentSection.DATE 
                           for elem in structure.elements),
            'has_signatures': any(elem.section_type == DocumentSection.SIGNATURE 
                                for elem in structure.elements)
        }