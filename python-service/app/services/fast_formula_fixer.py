"""
Fast Formula Fixer Service
고성능 수식 자동 수정 시스템 - 캐싱과 병렬 처리로 최적화
"""

import asyncio
import functools
import hashlib
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import re
import logging

from .smart_formula_fixer import SmartFormulaFixer, FormulaFixResult
from .excel_error_detector import ExcelError

@dataclass
class FixCache:
    """수식 수정 캐시"""
    formula_hash: str
    fix_result: FormulaFixResult
    hit_count: int = 0

class FastFormulaFixer(SmartFormulaFixer):
    """고성능 수식 자동 수정 시스템"""
    
    def __init__(self, max_workers: int = 4, cache_size: int = 1000):
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.fix_cache: Dict[str, FixCache] = {}
        self.max_cache_size = cache_size
        self.pattern_cache = self._precompile_patterns()
        self.optimization_patterns = self._compile_optimization_patterns()
        
    def _precompile_patterns(self) -> Dict[str, re.Pattern]:
        """정규식 패턴을 사전 컴파일하여 성능 향상"""
        return {
            'division': re.compile(r'([A-Z]+\d+)/([A-Z]+\d+)'),
            'vlookup': re.compile(r'VLOOKUP\s*\((.*?)\)', re.IGNORECASE),
            'match': re.compile(r'MATCH\s*\((.*?)\)', re.IGNORECASE),
            'cell_ref': re.compile(r'(?:(?:\'[^\']+\'|[A-Za-z_]\w*)!)?(?:\$?[A-Z]+\$?\d+(?::\$?[A-Z]+\$?\d+)?|\$?[A-Z]+:\$?[A-Z]+|\d+:\d+)'),
            'currency': re.compile(r'[₩$€£¥]'),
            'date': re.compile(r'\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}'),
            'array_formula': re.compile(r'^\{=.*\}$'),
            'dynamic_array': re.compile(r'SORT|FILTER|UNIQUE|SEQUENCE|RANDARRAY', re.IGNORECASE),
            'external_data': re.compile(r'WEBSERVICE|FILTERXML|RTD', re.IGNORECASE),
            'range_error': re.compile(r'([A-Z]+\d+)\s+([A-Z]+\d+)'),
            'sqrt': re.compile(r'SQRT\s*\((.*?)\)', re.IGNORECASE),
            'if_nested': re.compile(r'IF\(', re.IGNORECASE)
        }
    
    def _get_formula_hash(self, formula: str, error_type: str) -> str:
        """수식과 오류 타입의 해시 생성"""
        content = f"{formula}:{error_type}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_fix(self, formula: str, error_type: str) -> Optional[FormulaFixResult]:
        """캐시에서 수정 결과 조회"""
        hash_key = self._get_formula_hash(formula, error_type)
        if hash_key in self.fix_cache:
            cache_entry = self.fix_cache[hash_key]
            cache_entry.hit_count += 1
            return cache_entry.fix_result
        return None
    
    def _cache_fix_result(self, formula: str, error_type: str, result: FormulaFixResult):
        """수정 결과를 캐시에 저장"""
        # 캐시 크기 제한
        if len(self.fix_cache) >= self.max_cache_size:
            # LRU 방식: 가장 적게 사용된 항목 제거
            min_hit = min(self.fix_cache.values(), key=lambda x: x.hit_count)
            del self.fix_cache[min_hit.formula_hash]
        
        hash_key = self._get_formula_hash(formula, error_type)
        self.fix_cache[hash_key] = FixCache(
            formula_hash=hash_key,
            fix_result=result
        )
    
    async def fix_formula_errors_batch(self, workbook, errors: List[ExcelError]) -> Dict[str, Any]:
        """배치 처리로 여러 수식 오류를 병렬로 수정"""
        
        fix_results = {
            'fixed_formulas': [],
            'failed_fixes': [],
            'optimization_suggestions': [],
            'summary': {
                'total_processed': 0,
                'successfully_fixed': 0,
                'failed_fixes': 0,
                'optimizations_applied': 0,
                'cache_hits': 0
            }
        }
        
        # 수식 오류만 필터링
        formula_errors = [e for e in errors if e.error_type in ['formula_error', 'inefficient_formula']]
        
        # 병렬 처리를 위한 태스크 생성
        tasks = []
        for error in formula_errors:
            task = self._process_single_error_async(workbook, error, fix_results)
            tasks.append(task)
        
        # 모든 태스크 병렬 실행
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        return fix_results
    
    async def _process_single_error_async(self, workbook, error: ExcelError, fix_results: Dict[str, Any]):
        """단일 오류를 비동기로 처리"""
        try:
            sheet_name, cell_ref = error.location.split('!')
            sheet = workbook[sheet_name]
            cell = sheet[cell_ref]
            
            # 캐시 확인
            cached_fix = self._get_cached_fix(str(cell.value), error.error_type)
            if cached_fix:
                fix_results['summary']['cache_hits'] += 1
                fix_result = cached_fix
            else:
                # 새로운 수정 수행
                if error.error_type == 'formula_error':
                    fix_result = await self._fix_single_formula_error_fast(cell, error)
                elif error.error_type == 'inefficient_formula':
                    fix_result = await self._optimize_single_formula_fast(cell, error)
                else:
                    fix_result = None
                
                # 결과 캐싱
                if fix_result:
                    self._cache_fix_result(str(cell.value), error.error_type, fix_result)
            
            # 결과 처리
            if fix_result and fix_result.test_passed:
                cell.value = fix_result.fixed_formula
                fix_results['fixed_formulas'].append({
                    'location': error.location,
                    'original': fix_result.original_formula,
                    'fixed': fix_result.fixed_formula,
                    'fix_type': fix_result.fix_type,
                    'confidence': fix_result.confidence,
                    'explanation': fix_result.explanation
                })
                fix_results['summary']['successfully_fixed'] += 1
            else:
                fix_results['failed_fixes'].append({
                    'location': error.location,
                    'error': error.description,
                    'reason': '자동 수정 실패 - 수동 검토 필요'
                })
                fix_results['summary']['failed_fixes'] += 1
            
            fix_results['summary']['total_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"수식 수정 중 오류: {str(e)}")
            fix_results['failed_fixes'].append({
                'location': error.location,
                'error': str(e),
                'reason': '수정 처리 중 예외 발생'
            })
    
    async def _fix_single_formula_error_fast(self, cell, error: ExcelError) -> Optional[FormulaFixResult]:
        """최적화된 단일 수식 오류 수정"""
        
        original_formula = str(cell.value)
        error_type = self._extract_error_type_fast(original_formula)
        
        if error_type in self.fix_patterns:
            # 패턴 기반 수정 (빠른 처리)
            pattern_fix = self.fix_patterns[error_type](original_formula, cell)
            if pattern_fix:
                return pattern_fix
        
        # AI 기반 수정은 필요시에만 (느린 처리)
        if error.auto_fixable and error.fix_confidence > 0.7:
            return await self._ai_fix_formula(original_formula, cell, error)
        
        return None
    
    async def _optimize_single_formula_fast(self, cell, error: ExcelError) -> Optional[FormulaFixResult]:
        """최적화된 단일 수식 최적화"""
        
        original_formula = str(cell.value)
        
        # 빠른 패턴 매칭으로 최적화 대상 확인
        for pattern_name, optimizer in self.optimization_patterns.items():
            if self._formula_matches_pattern_fast(original_formula, pattern_name):
                optimization = optimizer(original_formula, cell)
                if optimization:
                    return optimization
        
        return None
    
    def _extract_error_type_fast(self, formula: str) -> Optional[str]:
        """빠른 오류 타입 추출"""
        # 해시맵 기반 빠른 검색
        for error_type in ['#DIV/0!', '#N/A', '#NAME?', '#REF!', '#VALUE!', '#NUM!', '#NULL!', '#SPILL!', '#CALC!', '#GETTING_DATA']:
            if error_type in formula:
                return error_type
        return None
    
    def _formula_matches_pattern_fast(self, formula: str, pattern_name: str) -> bool:
        """사전 컴파일된 패턴으로 빠른 매칭"""
        
        pattern_checks = {
            'vlookup_to_xlookup': lambda f: self.pattern_cache['vlookup'].search(f) is not None,
            'nested_if': lambda f: len(self.pattern_cache['if_nested'].findall(f)) > 3,
            'inefficient_range': lambda f: ':' in f and ('1048576' in f or '16384' in f),
            'array_formula': lambda f: self.pattern_cache['array_formula'].match(f) is not None
        }
        
        return pattern_checks.get(pattern_name, lambda f: False)(formula)
    
    def cleanup(self):
        """리소스 정리"""
        self.executor.shutdown(wait=True)
        self.fix_cache.clear()