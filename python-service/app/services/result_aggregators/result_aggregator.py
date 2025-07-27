"""
OCR 결과 통합기
TwoTierOCRService에서 분리된 결과 통합 및 최종 처리 로직
Single Responsibility Principle 적용
"""

import logging
import hashlib
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessingTier(Enum):
    """처리 계층"""
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"
    FAILED = "failed"


class ContentType(Enum):
    """컨텐츠 타입"""
    PLAIN_TEXT = "plain_text"
    STRUCTURED_TEXT = "structured_text"
    MARKDOWN_TABLE = "markdown_table"
    ENHANCED_TEXT = "enhanced_text"
    ERROR = "error"


@dataclass
class AggregationOptions:
    """통합 옵션"""
    prefer_higher_tier: bool = True
    confidence_weight: float = 0.4
    completeness_weight: float = 0.3
    quality_weight: float = 0.3
    enable_result_validation: bool = True
    enable_caching: bool = True
    cache_ttl_hours: int = 24


@dataclass
class FinalResult:
    """최종 통합 결과"""
    success: bool
    processing_tier: ProcessingTier
    extracted_content: str
    extracted_content_type: ContentType
    table_data: List[Any]
    entities: List[Dict[str, Any]]
    final_confidence: float
    tier2_result: Optional[Dict[str, Any]]
    tier3_result: Optional[Dict[str, Any]]
    complexity_metrics: Dict[str, Any]
    upgrade_decision: Dict[str, Any]
    processing_metadata: Dict[str, Any]
    error: Optional[str] = None


class ResultAggregator:
    """OCR 결과 통합기 - SOLID 원칙 적용"""
    
    def __init__(self, options: Optional[AggregationOptions] = None):
        """
        초기화
        
        Args:
            options: 통합 옵션
        """
        self.options = options or AggregationOptions()
        
        # 결과 캐시 (간단한 메모리 캐시)
        self.result_cache = {} if self.options.enable_caching else None
        
        # 품질 평가 기준
        self.quality_criteria = {
            'text_completeness': {
                'min_length': 10,
                'max_empty_ratio': 0.1,
                'weight': 0.3
            },
            'table_structure': {
                'min_rows': 2,
                'min_columns': 2,
                'weight': 0.25
            },
            'entity_extraction': {
                'min_entities': 1,
                'confidence_threshold': 0.7,
                'weight': 0.2
            },
            'consistency': {
                'tier_agreement_threshold': 0.6,
                'weight': 0.25
            }
        }
        
        # 컨텐츠 타입 결정 규칙
        self.content_type_rules = [
            ('table_data', lambda r: len(r.get('table_data', [])) > 0, ContentType.MARKDOWN_TABLE),
            ('entities', lambda r: len(r.get('entities', [])) > 0, ContentType.ENHANCED_TEXT),
            ('structured', lambda r: self._has_structured_content(r.get('text', '')), ContentType.STRUCTURED_TEXT),
            ('plain', lambda r: True, ContentType.PLAIN_TEXT)
        ]
    
    def aggregate_results(self, tier2_result: Optional[Dict[str, Any]] = None,
                         tier3_result: Optional[Dict[str, Any]] = None,
                         complexity_metrics: Optional[Dict[str, Any]] = None,
                         upgrade_decision: Optional[Dict[str, Any]] = None,
                         processing_metadata: Optional[Dict[str, Any]] = None,
                         cache_key: Optional[str] = None) -> FinalResult:
        """OCR 결과들을 통합하여 최종 결과 생성"""
        try:
            # 캐시 확인
            if self.result_cache and cache_key and cache_key in self.result_cache:
                logger.info(f"Returning cached result for key: {cache_key}")
                return self.result_cache[cache_key]
            
            # 기본값 설정
            complexity_metrics = complexity_metrics or {}
            upgrade_decision = upgrade_decision or {}
            processing_metadata = processing_metadata or {}
            
            # 1. 사용할 결과 선택
            selected_result, processing_tier = self._select_best_result(
                tier2_result, tier3_result
            )
            
            # 2. 콘텐츠 추출 및 정제
            content_info = self._extract_content(selected_result, tier2_result, tier3_result)
            
            # 3. 테이블 데이터 통합
            table_data = self._aggregate_table_data(tier2_result, tier3_result, selected_result)
            
            # 4. 엔티티 정보 통합
            entities = self._aggregate_entities(tier2_result, tier3_result, selected_result)
            
            # 5. 최종 신뢰도 계산
            final_confidence = self._calculate_final_confidence(
                tier2_result, tier3_result, selected_result, processing_tier
            )
            
            # 6. 콘텐츠 타입 결정
            content_type = self._determine_content_type(content_info, table_data, entities)
            
            # 7. 결과 검증
            if self.options.enable_result_validation:
                validation_result = self._validate_final_result(
                    content_info, table_data, entities, final_confidence
                )
                if not validation_result['valid']:
                    logger.warning(f"Result validation failed: {validation_result['issues']}")
            
            # 8. 메타데이터 보강
            enhanced_metadata = self._enhance_metadata(
                processing_metadata, tier2_result, tier3_result, 
                selected_result, processing_tier
            )
            
            # 9. 최종 결과 생성
            final_result = FinalResult(
                success=selected_result.get('success', False) if selected_result else False,
                processing_tier=processing_tier,
                extracted_content=content_info['text'],
                extracted_content_type=content_type,
                table_data=table_data,
                entities=entities,
                final_confidence=final_confidence,
                tier2_result=tier2_result,
                tier3_result=tier3_result,
                complexity_metrics=complexity_metrics,
                upgrade_decision=upgrade_decision,
                processing_metadata=enhanced_metadata,
                error=selected_result.get('error') if selected_result else "No valid results"
            )
            
            # 10. 캐시 저장
            if self.result_cache and cache_key:
                self.result_cache[cache_key] = final_result
                logger.debug(f"Result cached with key: {cache_key}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Result aggregation failed: {e}")
            return self._create_error_result(str(e), tier2_result, tier3_result)
    
    def _select_best_result(self, tier2_result: Optional[Dict[str, Any]],
                          tier3_result: Optional[Dict[str, Any]]) -> tuple[Optional[Dict[str, Any]], ProcessingTier]:
        """최적 결과 선택"""
        try:
            # Tier 3 결과가 성공적이면 우선 선택
            if (tier3_result and tier3_result.get('success') and 
                self.options.prefer_higher_tier):
                
                tier3_quality = self._assess_result_quality(tier3_result)
                logger.info(f"Using Tier 3 result (quality: {tier3_quality:.3f})")
                return tier3_result, ProcessingTier.TIER3
            
            # Tier 2 결과 확인
            if tier2_result and tier2_result.get('success'):
                tier2_quality = self._assess_result_quality(tier2_result)
                
                # Tier 3가 있지만 품질이 낮은 경우 Tier 2와 비교
                if tier3_result and tier3_result.get('success'):
                    tier3_quality = self._assess_result_quality(tier3_result)
                    
                    if tier2_quality > tier3_quality:
                        logger.info(f"Using Tier 2 result over Tier 3 (quality: {tier2_quality:.3f} vs {tier3_quality:.3f})")
                        return tier2_result, ProcessingTier.TIER2
                    else:
                        logger.info(f"Using Tier 3 result (quality: {tier3_quality:.3f})")
                        return tier3_result, ProcessingTier.TIER3
                else:
                    logger.info(f"Using Tier 2 result (quality: {tier2_quality:.3f})")
                    return tier2_result, ProcessingTier.TIER2
            
            # 둘 다 실패한 경우
            logger.warning("Both Tier 2 and Tier 3 results failed or unavailable")
            return None, ProcessingTier.FAILED
            
        except Exception as e:
            logger.error(f"Result selection failed: {e}")
            return None, ProcessingTier.FAILED
    
    def _assess_result_quality(self, result: Dict[str, Any]) -> float:
        """결과 품질 평가"""
        try:
            quality_scores = []
            
            # 1. 텍스트 완성도
            text = result.get('text', '')
            text_score = self._assess_text_quality(text)
            quality_scores.append(text_score * self.quality_criteria['text_completeness']['weight'])
            
            # 2. 테이블 구조 품질
            tables = result.get('tables', []) or result.get('table_data', [])
            table_score = self._assess_table_quality(tables)
            quality_scores.append(table_score * self.quality_criteria['table_structure']['weight'])
            
            # 3. 엔티티 추출 품질
            entities = result.get('entities', [])
            entity_score = self._assess_entity_quality(entities)
            quality_scores.append(entity_score * self.quality_criteria['entity_extraction']['weight'])
            
            # 4. 신뢰도 점수
            confidence = result.get('confidence', 0)
            quality_scores.append(confidence * 0.25)
            
            return sum(quality_scores)
            
        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return 0.0
    
    def _assess_text_quality(self, text: str) -> float:
        """텍스트 품질 평가"""
        if not text:
            return 0.0
        
        criteria = self.quality_criteria['text_completeness']
        
        # 길이 점수
        length_score = min(len(text) / criteria['min_length'], 1.0)
        
        # 빈 줄 비율 점수
        lines = text.split('\n')
        empty_lines = sum(1 for line in lines if not line.strip())
        empty_ratio = empty_lines / len(lines) if lines else 0
        empty_score = max(1.0 - empty_ratio / criteria['max_empty_ratio'], 0.0)
        
        # 문자 다양성 점수 (간단한 휴리스틱)
        unique_chars = len(set(text.lower()))
        diversity_score = min(unique_chars / 50, 1.0)  # 50개 이상의 고유 문자면 1.0
        
        return (length_score + empty_score + diversity_score) / 3
    
    def _assess_table_quality(self, tables: List[Any]) -> float:
        """테이블 품질 평가"""
        if not tables:
            return 0.0
        
        criteria = self.quality_criteria['table_structure']
        scores = []
        
        for table in tables:
            if isinstance(table, dict):
                headers = table.get('headers', [])
                rows = table.get('rows', [])
                
                # 행/열 개수 점수
                row_score = min(len(rows) / criteria['min_rows'], 1.0) if rows else 0
                col_score = min(len(headers) / criteria['min_columns'], 1.0) if headers else 0
                
                # 데이터 일관성 점수
                if rows and headers:
                    consistent_rows = sum(1 for row in rows if len(row) == len(headers))
                    consistency_score = consistent_rows / len(rows)
                else:
                    consistency_score = 0
                
                table_score = (row_score + col_score + consistency_score) / 3
                scores.append(table_score)
            
            elif isinstance(table, list) and table:
                # 간단한 2D 배열 형태
                row_score = min(len(table) / criteria['min_rows'], 1.0)
                col_score = min(len(table[0]) / criteria['min_columns'], 1.0) if table[0] else 0
                scores.append((row_score + col_score) / 2)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _assess_entity_quality(self, entities: List[Dict[str, Any]]) -> float:
        """엔티티 품질 평가"""
        if not entities:
            return 0.0
        
        criteria = self.quality_criteria['entity_extraction']
        
        # 엔티티 개수 점수
        count_score = min(len(entities) / criteria['min_entities'], 1.0)
        
        # 신뢰도 점수
        high_confidence_entities = [
            e for e in entities 
            if e.get('confidence', 0) >= criteria['confidence_threshold']
        ]
        confidence_score = len(high_confidence_entities) / len(entities)
        
        # 타입 다양성 점수
        entity_types = set(e.get('type', 'unknown') for e in entities)
        diversity_score = min(len(entity_types) / 3, 1.0)  # 3개 이상 타입이면 1.0
        
        return (count_score + confidence_score + diversity_score) / 3
    
    def _extract_content(self, selected_result: Optional[Dict[str, Any]],
                        tier2_result: Optional[Dict[str, Any]],
                        tier3_result: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """콘텐츠 추출 및 정제"""
        try:
            if not selected_result:
                return {'text': '', 'source': 'none'}
            
            text = selected_result.get('text', '')
            
            # 텍스트 후처리
            cleaned_text = self._clean_text(text)
            
            # 보완 정보 추가 (다른 tier에서)
            if selected_result == tier2_result and tier3_result:
                # Tier 2를 선택했지만 Tier 3 결과도 있는 경우
                tier3_text = tier3_result.get('text', '')
                if tier3_text and len(tier3_text) > len(cleaned_text) * 1.2:
                    # Tier 3 텍스트가 20% 이상 더 길면 참고
                    supplementary_info = self._extract_supplementary_info(cleaned_text, tier3_text)
                    if supplementary_info:
                        cleaned_text += f"\n\n[보완 정보]\n{supplementary_info}"
            
            return {
                'text': cleaned_text,
                'source': selected_result.get('processing_method', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            return {'text': '', 'source': 'error'}
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정제"""
        import re
        
        if not text:
            return ''
        
        # 기본 정제
        cleaned = text.strip()
        
        # 과도한 공백 제거
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n[ \t]+', '\n', cleaned)
        
        # 특수 문자 정리
        cleaned = re.sub(r'[^\w\s가-힣,.!?:;()\-\n\t]', '', cleaned)
        
        return cleaned
    
    def _extract_supplementary_info(self, main_text: str, supplementary_text: str) -> str:
        """보완 정보 추출"""
        try:
            # 간단한 차이점 추출 (실제로는 더 정교한 알고리즘 필요)
            main_lines = set(main_text.split('\n'))
            supp_lines = set(supplementary_text.split('\n'))
            
            additional_lines = supp_lines - main_lines
            
            # 의미있는 추가 정보만 선택
            meaningful_additions = [
                line for line in additional_lines 
                if len(line.strip()) > 10 and not line.strip().startswith('[')
            ]
            
            return '\n'.join(meaningful_additions[:3])  # 최대 3줄
            
        except Exception as e:
            logger.error(f"Supplementary info extraction failed: {e}")
            return ''
    
    def _aggregate_table_data(self, tier2_result: Optional[Dict[str, Any]],
                            tier3_result: Optional[Dict[str, Any]],
                            selected_result: Optional[Dict[str, Any]]) -> List[Any]:
        """테이블 데이터 통합"""
        try:
            all_tables = []
            
            # 선택된 결과의 테이블
            if selected_result:
                main_tables = (selected_result.get('tables', []) or 
                             selected_result.get('table_data', []))
                if main_tables:
                    all_tables.extend(main_tables)
            
            # 다른 tier의 추가 테이블 (중복 제거)
            other_result = tier3_result if selected_result == tier2_result else tier2_result
            if other_result:
                other_tables = (other_result.get('tables', []) or 
                              other_result.get('table_data', []))
                
                for table in other_tables:
                    if not self._is_duplicate_table(table, all_tables):
                        all_tables.append(table)
            
            # 테이블 품질 검증 및 정제
            validated_tables = []
            for table in all_tables:
                cleaned_table = self._clean_table_data(table)
                if cleaned_table and self._validate_table_structure(cleaned_table):
                    validated_tables.append(cleaned_table)
            
            return validated_tables
            
        except Exception as e:
            logger.error(f"Table data aggregation failed: {e}")
            return []
    
    def _is_duplicate_table(self, table: Any, existing_tables: List[Any]) -> bool:
        """테이블 중복 확인"""
        try:
            # 간단한 중복 확인 로직
            for existing in existing_tables:
                if self._calculate_table_similarity(table, existing) > 0.8:
                    return True
            return False
            
        except Exception as e:
            logger.error(f"Duplicate table check failed: {e}")
            return False
    
    def _calculate_table_similarity(self, table1: Any, table2: Any) -> float:
        """테이블 유사도 계산"""
        try:
            # 두 테이블을 표준 형태로 변환
            t1_data = self._normalize_table_format(table1)
            t2_data = self._normalize_table_format(table2)
            
            if not t1_data or not t2_data:
                return 0.0
            
            # 크기 비교
            size_similarity = min(len(t1_data), len(t2_data)) / max(len(t1_data), len(t2_data))
            
            # 내용 비교 (첫 몇 행)
            content_similarity = 0.0
            compare_rows = min(3, len(t1_data), len(t2_data))
            
            if compare_rows > 0:
                matches = 0
                total_cells = 0
                
                for i in range(compare_rows):
                    row1 = t1_data[i] if i < len(t1_data) else []
                    row2 = t2_data[i] if i < len(t2_data) else []
                    
                    for j in range(min(len(row1), len(row2))):
                        total_cells += 1
                        if str(row1[j]).strip() == str(row2[j]).strip():
                            matches += 1
                
                content_similarity = matches / total_cells if total_cells > 0 else 0.0
            
            return (size_similarity + content_similarity) / 2
            
        except Exception as e:
            logger.error(f"Table similarity calculation failed: {e}")
            return 0.0
    
    def _normalize_table_format(self, table: Any) -> Optional[List[List[str]]]:
        """테이블을 표준 형태로 변환"""
        try:
            if isinstance(table, dict):
                headers = table.get('headers', [])
                rows = table.get('rows', [])
                
                normalized = []
                if headers:
                    normalized.append([str(h) for h in headers])
                if rows:
                    normalized.extend([[str(cell) for cell in row] for row in rows])
                
                return normalized
            
            elif isinstance(table, list):
                return [[str(cell) for cell in row] for row in table if row]
            
            return None
            
        except Exception as e:
            logger.error(f"Table format normalization failed: {e}")
            return None
    
    def _clean_table_data(self, table: Any) -> Optional[Dict[str, Any]]:
        """테이블 데이터 정제"""
        try:
            if isinstance(table, dict):
                cleaned = table.copy()
                
                # 헤더 정제
                if 'headers' in cleaned:
                    headers = [str(h).strip() for h in cleaned['headers'] if str(h).strip()]
                    cleaned['headers'] = headers
                
                # 행 데이터 정제
                if 'rows' in cleaned:
                    cleaned_rows = []
                    for row in cleaned['rows']:
                        cleaned_row = [str(cell).strip() for cell in row if str(cell).strip()]
                        if cleaned_row:
                            cleaned_rows.append(cleaned_row)
                    cleaned['rows'] = cleaned_rows
                    cleaned['row_count'] = len(cleaned_rows)
                    cleaned['column_count'] = len(cleaned.get('headers', []))
                
                return cleaned
            
            elif isinstance(table, list):
                cleaned_rows = []
                for row in table:
                    cleaned_row = [str(cell).strip() for cell in row if str(cell).strip()]
                    if cleaned_row:
                        cleaned_rows.append(cleaned_row)
                
                if cleaned_rows:
                    return {
                        'headers': cleaned_rows[0] if len(cleaned_rows) > 1 else [],
                        'rows': cleaned_rows[1:] if len(cleaned_rows) > 1 else cleaned_rows,
                        'row_count': len(cleaned_rows) - (1 if len(cleaned_rows) > 1 else 0),
                        'column_count': len(cleaned_rows[0]) if cleaned_rows else 0,
                        'source': 'aggregated'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Table data cleaning failed: {e}")
            return None
    
    def _validate_table_structure(self, table: Dict[str, Any]) -> bool:
        """테이블 구조 검증"""
        try:
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            
            # 최소 요구사항 확인
            if not headers and not rows:
                return False
            
            if len(rows) < 1:
                return False
            
            # 열 일관성 확인
            if headers:
                expected_cols = len(headers)
                consistent_rows = sum(1 for row in rows if len(row) == expected_cols)
                consistency_ratio = consistent_rows / len(rows)
                return consistency_ratio >= 0.7  # 70% 이상 일관성
            
            return True
            
        except Exception as e:
            logger.error(f"Table structure validation failed: {e}")
            return False
    
    def _aggregate_entities(self, tier2_result: Optional[Dict[str, Any]],
                          tier3_result: Optional[Dict[str, Any]],
                          selected_result: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """엔티티 정보 통합"""
        try:
            all_entities = []
            
            # 선택된 결과의 엔티티
            if selected_result:
                main_entities = selected_result.get('entities', [])
                if main_entities:
                    all_entities.extend(main_entities)
            
            # 다른 tier의 추가 엔티티
            other_result = tier3_result if selected_result == tier2_result else tier2_result
            if other_result:
                other_entities = other_result.get('entities', [])
                
                for entity in other_entities:
                    if not self._is_duplicate_entity(entity, all_entities):
                        all_entities.append(entity)
            
            # 엔티티 정제 및 검증
            cleaned_entities = self._clean_entities(all_entities)
            
            # 신뢰도 순으로 정렬
            cleaned_entities.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            
            return cleaned_entities
            
        except Exception as e:
            logger.error(f"Entity aggregation failed: {e}")
            return []
    
    def _is_duplicate_entity(self, entity: Dict[str, Any], existing_entities: List[Dict[str, Any]]) -> bool:
        """엔티티 중복 확인"""
        try:
            entity_value = str(entity.get('value', '')).strip().lower()
            entity_type = entity.get('type', 'unknown')
            
            for existing in existing_entities:
                existing_value = str(existing.get('value', '')).strip().lower()
                existing_type = existing.get('type', 'unknown')
                
                if entity_value == existing_value and entity_type == existing_type:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Entity duplicate check failed: {e}")
            return False
    
    def _clean_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """엔티티 정제"""
        cleaned = []
        
        try:
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                
                value = str(entity.get('value', '')).strip()
                if not value:
                    continue
                
                cleaned_entity = {
                    'type': entity.get('type', 'unknown'),
                    'value': value,
                    'confidence': min(float(entity.get('confidence', 0.5)), 1.0)
                }
                
                if 'position' in entity:
                    cleaned_entity['position'] = entity['position']
                
                cleaned.append(cleaned_entity)
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Entity cleaning failed: {e}")
            return entities
    
    def _calculate_final_confidence(self, tier2_result: Optional[Dict[str, Any]],
                                  tier3_result: Optional[Dict[str, Any]],
                                  selected_result: Optional[Dict[str, Any]],
                                  processing_tier: ProcessingTier) -> float:
        """최종 신뢰도 계산"""
        try:
            if not selected_result:
                return 0.0
            
            base_confidence = selected_result.get('confidence', 0)
            
            # 처리 계층에 따른 가중치
            tier_weights = {
                ProcessingTier.TIER3: 0.95,
                ProcessingTier.TIER2: 0.85,
                ProcessingTier.TIER1: 0.75,
                ProcessingTier.FAILED: 0.0
            }
            
            tier_weight = tier_weights.get(processing_tier, 0.5)
            
            # 결과 품질 점수
            quality_score = self._assess_result_quality(selected_result)
            
            # 일관성 점수 (두 tier 결과가 모두 있는 경우)
            consistency_score = 1.0
            if tier2_result and tier3_result:
                consistency_score = self._calculate_tier_consistency(tier2_result, tier3_result)
            
            # 가중 평균
            final_confidence = (
                base_confidence * self.options.confidence_weight +
                quality_score * self.options.quality_weight +
                consistency_score * (1.0 - self.options.confidence_weight - self.options.quality_weight)
            ) * tier_weight
            
            return min(final_confidence, 1.0)
            
        except Exception as e:
            logger.error(f"Final confidence calculation failed: {e}")
            return 0.5
    
    def _calculate_tier_consistency(self, tier2_result: Dict[str, Any], 
                                  tier3_result: Dict[str, Any]) -> float:
        """Tier 간 일관성 계산"""
        try:
            text2 = tier2_result.get('text', '')
            text3 = tier3_result.get('text', '')
            
            if not text2 or not text3:
                return 0.5
            
            # 간단한 단어 기반 유사도
            words2 = set(text2.lower().split())
            words3 = set(text3.lower().split())
            
            if not words2 and not words3:
                return 1.0
            
            intersection = words2.intersection(words3)
            union = words2.union(words3)
            
            similarity = len(intersection) / len(union) if union else 0.0
            return similarity
            
        except Exception as e:
            logger.error(f"Tier consistency calculation failed: {e}")
            return 0.5
    
    def _determine_content_type(self, content_info: Dict[str, str],
                              table_data: List[Any], entities: List[Dict[str, Any]]) -> ContentType:
        """콘텐츠 타입 결정"""
        try:
            result_context = {
                'text': content_info.get('text', ''),
                'table_data': table_data,
                'entities': entities
            }
            
            for rule_name, condition, content_type in self.content_type_rules:
                if condition(result_context):
                    logger.debug(f"Content type determined: {content_type.value} (rule: {rule_name})")
                    return content_type
            
            return ContentType.PLAIN_TEXT
            
        except Exception as e:
            logger.error(f"Content type determination failed: {e}")
            return ContentType.PLAIN_TEXT
    
    def _has_structured_content(self, text: str) -> bool:
        """구조화된 콘텐츠 여부 확인"""
        import re
        
        # 구조화된 패턴 확인
        structured_patterns = [
            r'^\d+\.\s+',  # 번호 목록
            r'^[-*]\s+',   # 불릿 목록
            r'#{1,6}\s+',  # 마크다운 헤더
            r'\|.*\|',     # 테이블 형태
        ]
        
        lines = text.split('\n')
        structured_lines = 0
        
        for line in lines:
            for pattern in structured_patterns:
                if re.match(pattern, line.strip()):
                    structured_lines += 1
                    break
        
        # 30% 이상이 구조화된 라인이면 구조화된 콘텐츠로 판단
        return (structured_lines / len(lines)) > 0.3 if lines else False
    
    def _validate_final_result(self, content_info: Dict[str, str],
                             table_data: List[Any], entities: List[Dict[str, Any]],
                             final_confidence: float) -> Dict[str, Any]:
        """최종 결과 검증"""
        try:
            issues = []
            
            # 텍스트 검증
            text = content_info.get('text', '')
            if not text or len(text) < 5:
                issues.append("텍스트가 너무 짧거나 비어있음")
            
            # 신뢰도 검증
            if final_confidence < 0.3:
                issues.append(f"신뢰도가 너무 낮음: {final_confidence:.2f}")
            
            # 테이블 검증
            if table_data:
                for i, table in enumerate(table_data):
                    if not self._validate_table_structure(table):
                        issues.append(f"테이블 {i+1} 구조가 불완전함")
            
            # 엔티티 검증
            if entities:
                low_confidence_entities = [
                    e for e in entities if e.get('confidence', 0) < 0.5
                ]
                if len(low_confidence_entities) > len(entities) * 0.5:
                    issues.append("엔티티의 신뢰도가 전반적으로 낮음")
            
            return {
                'valid': len(issues) == 0,
                'issues': issues,
                'warnings': [issue for issue in issues if '낮음' in issue]
            }
            
        except Exception as e:
            logger.error(f"Result validation failed: {e}")
            return {'valid': False, 'issues': [f"검증 실패: {e}"], 'warnings': []}
    
    def _enhance_metadata(self, processing_metadata: Dict[str, Any],
                         tier2_result: Optional[Dict[str, Any]],
                         tier3_result: Optional[Dict[str, Any]],
                         selected_result: Optional[Dict[str, Any]],
                         processing_tier: ProcessingTier) -> Dict[str, Any]:
        """메타데이터 보강"""
        try:
            enhanced = processing_metadata.copy()
            
            enhanced.update({
                'aggregation_info': {
                    'selected_tier': processing_tier.value,
                    'tier2_available': tier2_result is not None and tier2_result.get('success', False),
                    'tier3_available': tier3_result is not None and tier3_result.get('success', False),
                    'aggregation_method': 'quality_based_selection'
                },
                'result_statistics': {
                    'text_length': len(selected_result.get('text', '')) if selected_result else 0,
                    'table_count': len(selected_result.get('tables', [])) if selected_result else 0,
                    'entity_count': len(selected_result.get('entities', [])) if selected_result else 0
                },
                'quality_assessment': {
                    'tier2_quality': self._assess_result_quality(tier2_result) if tier2_result else 0,
                    'tier3_quality': self._assess_result_quality(tier3_result) if tier3_result else 0,
                    'selected_quality': self._assess_result_quality(selected_result) if selected_result else 0
                }
            })
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Metadata enhancement failed: {e}")
            return processing_metadata
    
    def _create_error_result(self, error_message: str,
                           tier2_result: Optional[Dict[str, Any]],
                           tier3_result: Optional[Dict[str, Any]]) -> FinalResult:
        """오류 결과 생성"""
        return FinalResult(
            success=False,
            processing_tier=ProcessingTier.FAILED,
            extracted_content="",
            extracted_content_type=ContentType.ERROR,
            table_data=[],
            entities=[],
            final_confidence=0.0,
            tier2_result=tier2_result,
            tier3_result=tier3_result,
            complexity_metrics={},
            upgrade_decision={},
            processing_metadata={'aggregation_error': error_message},
            error=error_message
        )
    
    def generate_cache_key(self, image_path: str, context_tags: List[str]) -> str:
        """캐시 키 생성"""
        try:
            # 파일 해시와 컨텍스트 태그로 고유 키 생성
            with open(image_path, 'rb') as f:
                file_content = f.read()
                file_hash = hashlib.md5(file_content).hexdigest()
            
            context_str = ','.join(sorted(context_tags))
            context_hash = hashlib.md5(context_str.encode()).hexdigest()
            
            return f"aggregated_{file_hash}_{context_hash}"
            
        except Exception as e:
            logger.error(f"Cache key generation failed: {e}")
            return f"fallback_{hash(image_path)}_{hash(str(context_tags))}"
    
    def clear_cache(self):
        """캐시 초기화"""
        if self.result_cache:
            self.result_cache.clear()
            logger.info("Result cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        if not self.result_cache:
            return {'cache_enabled': False}
        
        return {
            'cache_enabled': True,
            'cache_size': len(self.result_cache),
            'cache_keys': list(self.result_cache.keys())
        }