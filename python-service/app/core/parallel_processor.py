"""
병렬 처리 시스템
대용량 파일과 배치 작업을 위한 병렬 처리
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Callable, Any, Dict, Optional
import multiprocessing
from functools import partial
import logging
from dataclasses import dataclass
from enum import Enum
import time

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """처리 모드"""
    SEQUENTIAL = "sequential"
    THREAD_PARALLEL = "thread_parallel"
    PROCESS_PARALLEL = "process_parallel"
    ASYNC_PARALLEL = "async_parallel"


@dataclass
class ProcessingResult:
    """처리 결과"""
    success: bool
    result: Any
    error: Optional[str] = None
    processing_time: float = 0


class ParallelProcessor:
    """병렬 처리 관리자"""
    
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=self.max_workers)
    
    async def process_batch_async(
        self,
        items: List[Any],
        processor_func: Callable,
        mode: ProcessingMode = ProcessingMode.ASYNC_PARALLEL,
        chunk_size: int = 10
    ) -> List[ProcessingResult]:
        """배치 비동기 처리"""
        
        start_time = time.time()
        
        if mode == ProcessingMode.SEQUENTIAL:
            results = await self._process_sequential_async(items, processor_func)
        elif mode == ProcessingMode.THREAD_PARALLEL:
            results = await self._process_thread_parallel(items, processor_func)
        elif mode == ProcessingMode.PROCESS_PARALLEL:
            results = await self._process_process_parallel(items, processor_func)
        else:  # ASYNC_PARALLEL
            results = await self._process_async_parallel(items, processor_func, chunk_size)
        
        total_time = time.time() - start_time
        logger.info(f"배치 처리 완료: {len(items)}개 항목, {total_time:.2f}초, 모드: {mode.value}")
        
        return results
    
    async def _process_sequential_async(
        self,
        items: List[Any],
        processor_func: Callable
    ) -> List[ProcessingResult]:
        """순차 처리"""
        results = []
        
        for item in items:
            start = time.time()
            try:
                if asyncio.iscoroutinefunction(processor_func):
                    result = await processor_func(item)
                else:
                    result = processor_func(item)
                
                results.append(ProcessingResult(
                    success=True,
                    result=result,
                    processing_time=time.time() - start
                ))
            except Exception as e:
                results.append(ProcessingResult(
                    success=False,
                    result=None,
                    error=str(e),
                    processing_time=time.time() - start
                ))
        
        return results
    
    async def _process_thread_parallel(
        self,
        items: List[Any],
        processor_func: Callable
    ) -> List[ProcessingResult]:
        """스레드 병렬 처리"""
        loop = asyncio.get_event_loop()
        
        async def process_item(item):
            start = time.time()
            try:
                result = await loop.run_in_executor(
                    self.thread_executor,
                    processor_func,
                    item
                )
                return ProcessingResult(
                    success=True,
                    result=result,
                    processing_time=time.time() - start
                )
            except Exception as e:
                return ProcessingResult(
                    success=False,
                    result=None,
                    error=str(e),
                    processing_time=time.time() - start
                )
        
        tasks = [process_item(item) for item in items]
        return await asyncio.gather(*tasks)
    
    async def _process_process_parallel(
        self,
        items: List[Any],
        processor_func: Callable
    ) -> List[ProcessingResult]:
        """프로세스 병렬 처리"""
        loop = asyncio.get_event_loop()
        
        # 프로세스 간 통신을 위해 함수를 피클 가능하게 만들기
        if hasattr(processor_func, '__name__'):
            func_name = processor_func.__name__
        else:
            # 람다나 로컬 함수의 경우 프로세스 병렬 처리 불가
            logger.warning("프로세스 병렬 처리는 피클 가능한 함수만 지원합니다. 스레드 병렬로 전환합니다.")
            return await self._process_thread_parallel(items, processor_func)
        
        results = []
        
        # 청크로 나누어 처리
        chunk_size = max(1, len(items) // self.max_workers)
        chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
        
        for chunk in chunks:
            chunk_results = await loop.run_in_executor(
                self.process_executor,
                self._process_chunk_sync,
                chunk,
                processor_func
            )
            results.extend(chunk_results)
        
        return results
    
    @staticmethod
    def _process_chunk_sync(chunk: List[Any], processor_func: Callable) -> List[ProcessingResult]:
        """동기 청크 처리 (프로세스 실행용)"""
        results = []
        
        for item in chunk:
            start = time.time()
            try:
                result = processor_func(item)
                results.append(ProcessingResult(
                    success=True,
                    result=result,
                    processing_time=time.time() - start
                ))
            except Exception as e:
                results.append(ProcessingResult(
                    success=False,
                    result=None,
                    error=str(e),
                    processing_time=time.time() - start
                ))
        
        return results
    
    async def _process_async_parallel(
        self,
        items: List[Any],
        processor_func: Callable,
        chunk_size: int
    ) -> List[ProcessingResult]:
        """비동기 병렬 처리"""
        
        async def process_item(item):
            start = time.time()
            try:
                if asyncio.iscoroutinefunction(processor_func):
                    result = await processor_func(item)
                else:
                    result = processor_func(item)
                
                return ProcessingResult(
                    success=True,
                    result=result,
                    processing_time=time.time() - start
                )
            except Exception as e:
                return ProcessingResult(
                    success=False,
                    result=None,
                    error=str(e),
                    processing_time=time.time() - start
                )
        
        # 청크 단위로 처리하여 동시 실행 수 제한
        results = []
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            chunk_tasks = [process_item(item) for item in chunk]
            chunk_results = await asyncio.gather(*chunk_tasks)
            results.extend(chunk_results)
        
        return results
    
    def process_excel_files_parallel(
        self,
        file_paths: List[str],
        analysis_func: Callable,
        mode: ProcessingMode = ProcessingMode.THREAD_PARALLEL
    ) -> Dict[str, ProcessingResult]:
        """Excel 파일 병렬 처리"""
        
        async def process_files():
            results = await self.process_batch_async(
                file_paths,
                analysis_func,
                mode
            )
            
            # 파일 경로를 키로 하는 딕셔너리로 변환
            return {
                file_path: result
                for file_path, result in zip(file_paths, results)
            }
        
        # 이벤트 루프에서 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_files())
        finally:
            loop.close()
    
    def shutdown(self):
        """실행자 종료"""
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)


class ExcelBatchProcessor:
    """Excel 전용 배치 처리기"""
    
    def __init__(self):
        self.processor = ParallelProcessor()
    
    async def batch_analyze_errors(
        self,
        file_paths: List[str],
        error_detector: Any
    ) -> Dict[str, Any]:
        """배치 오류 분석"""
        
        async def analyze_file(file_path: str):
            return await error_detector.detect_all_errors(file_path)
        
        results = await self.processor.process_batch_async(
            file_paths,
            analyze_file,
            ProcessingMode.ASYNC_PARALLEL,
            chunk_size=5
        )
        
        return self._aggregate_results(file_paths, results)
    
    async def batch_compare_files(
        self,
        file_pairs: List[tuple],
        comparison_engine: Any
    ) -> Dict[str, Any]:
        """배치 파일 비교"""
        
        async def compare_pair(pair: tuple):
            expected_file, actual_file = pair
            return await comparison_engine.compare_files(
                expected_file,
                actual_file
            )
        
        results = await self.processor.process_batch_async(
            file_pairs,
            compare_pair,
            ProcessingMode.THREAD_PARALLEL
        )
        
        return self._aggregate_comparison_results(file_pairs, results)
    
    async def batch_optimize_formulas(
        self,
        file_paths: List[str],
        formula_analyzer: Any
    ) -> Dict[str, Any]:
        """배치 수식 최적화"""
        
        async def analyze_formulas(file_path: str):
            return await formula_analyzer.analyze_workbook(file_path)
        
        results = await self.processor.process_batch_async(
            file_paths,
            analyze_formulas,
            ProcessingMode.ASYNC_PARALLEL,
            chunk_size=3
        )
        
        return self._aggregate_formula_results(file_paths, results)
    
    def _aggregate_results(
        self,
        file_paths: List[str],
        results: List[ProcessingResult]
    ) -> Dict[str, Any]:
        """결과 집계"""
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_processing_time = sum(r.processing_time for r in results)
        
        # 오류 통계
        total_errors = 0
        error_types = {}
        
        for result in results:
            if result.success and result.result:
                errors = result.result.get('errors', [])
                total_errors += len(errors)
                
                for error in errors:
                    error_type = error.get('type', 'unknown')
                    error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "summary": {
                "total_files": len(file_paths),
                "successful": successful,
                "failed": failed,
                "total_errors": total_errors,
                "error_types": error_types,
                "total_processing_time": total_processing_time,
                "avg_processing_time": total_processing_time / len(results) if results else 0
            },
            "details": [
                {
                    "file": file_path,
                    "success": result.success,
                    "processing_time": result.processing_time,
                    "errors": result.result.get('errors', []) if result.success else [],
                    "error_message": result.error
                }
                for file_path, result in zip(file_paths, results)
            ]
        }
    
    def _aggregate_comparison_results(
        self,
        file_pairs: List[tuple],
        results: List[ProcessingResult]
    ) -> Dict[str, Any]:
        """비교 결과 집계"""
        
        total_differences = 0
        avg_match_percentage = 0
        successful_comparisons = 0
        
        for result in results:
            if result.success and result.result:
                total_differences += result.result.differences_found
                avg_match_percentage += result.result.match_percentage
                successful_comparisons += 1
        
        if successful_comparisons > 0:
            avg_match_percentage /= successful_comparisons
        
        return {
            "summary": {
                "total_comparisons": len(file_pairs),
                "successful": successful_comparisons,
                "failed": len(results) - successful_comparisons,
                "total_differences": total_differences,
                "avg_match_percentage": avg_match_percentage
            },
            "comparisons": [
                {
                    "expected": pair[0],
                    "actual": pair[1],
                    "success": result.success,
                    "differences": result.result.differences_found if result.success else None,
                    "match_percentage": result.result.match_percentage if result.success else None,
                    "error": result.error
                }
                for pair, result in zip(file_pairs, results)
            ]
        }
    
    def _aggregate_formula_results(
        self,
        file_paths: List[str],
        results: List[ProcessingResult]
    ) -> Dict[str, Any]:
        """수식 분석 결과 집계"""
        
        total_formulas = 0
        complexity_distribution = {}
        optimization_opportunities = []
        
        for result in results:
            if result.success and result.result:
                total_formulas += result.result.total_formulas
                
                # 복잡도 분포 병합
                for level, count in result.result.complexity_distribution.items():
                    key = level.value if hasattr(level, 'value') else str(level)
                    complexity_distribution[key] = complexity_distribution.get(key, 0) + count
                
                # 최적화 기회 수집
                optimization_opportunities.extend(result.result.optimization_opportunities)
        
        return {
            "summary": {
                "total_files": len(file_paths),
                "total_formulas": total_formulas,
                "complexity_distribution": complexity_distribution,
                "optimization_opportunity_count": len(optimization_opportunities)
            },
            "top_optimizations": optimization_opportunities[:10],
            "file_results": [
                {
                    "file": file_path,
                    "success": result.success,
                    "formula_count": result.result.total_formulas if result.success else 0,
                    "error": result.error
                }
                for file_path, result in zip(file_paths, results)
            ]
        }