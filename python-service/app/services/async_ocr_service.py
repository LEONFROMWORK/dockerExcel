"""
비동기 OCR 배치 처리 서비스
asyncio와 ThreadPoolExecutor를 사용한 병렬 OCR 처리
"""

import asyncio
import concurrent.futures
import os
import time
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass
from .multilingual_two_tier_service import MultilingualTwoTierService
from .ocr_cache_service import ocr_cache
from .ocr_retry_service import OCRRetryService, RetryConfig

logger = logging.getLogger(__name__)

@dataclass
class OCRTask:
    """OCR 작업 단위"""
    file_path: str
    image_data: bytes
    task_id: str
    metadata: Dict[str, Any] = None

@dataclass
class OCRResult:
    """OCR 결과"""
    task_id: str
    file_path: str
    success: bool
    result: Dict[str, Any] = None
    error: str = None
    processing_time: float = 0.0
    cached: bool = False

class AsyncOCRService:
    """비동기 OCR 배치 처리 서비스"""
    
    def __init__(self, max_workers: int = 4):
        """
        Args:
            max_workers: 동시 처리할 최대 워커 수
        """
        self.max_workers = max_workers
        self.ocr_service = MultilingualTwoTierService()
        self._executor = None
        
        # 비동기 환경에서 재시도 설정
        retry_config = RetryConfig(
            max_attempts=2,  # 비동기에서는 더 적은 재시도
            base_delay=0.5,
            max_delay=10.0,
            backoff_multiplier=1.5,
            jitter=True,
            timeout=15.0
        )
        self.retry_service = OCRRetryService(retry_config)
        
        logger.info(f"AsyncOCRService 초기화 완료 (max_workers: {max_workers})")
    
    def __enter__(self):
        """Context manager 진입"""
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="OCR-Worker"
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
    
    async def __aenter__(self):
        """Async context manager 진입"""
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="OCR-Worker"
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager 종료"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
    
    async def _process_single_ocr_with_retry(self, task: OCRTask) -> OCRResult:
        """재시도 로직이 적용된 단일 OCR 작업 처리"""
        start_time = time.time()
        
        retry_result = await self.retry_service.retry_with_backoff(
            self._process_single_ocr_internal, task
        )
        
        processing_time = time.time() - start_time
        
        if retry_result.success:
            ocr_result = retry_result.data
            return OCRResult(
                task_id=task.task_id,
                file_path=task.file_path,
                success=True,
                result=ocr_result,
                processing_time=processing_time,
                cached=ocr_result.get('cached', False)
            )
        else:
            logger.error(f"재시도 후 OCR 실패 [{task.task_id}]: {retry_result.error_message}")
            return OCRResult(
                task_id=task.task_id,
                file_path=task.file_path,
                success=False,
                error=f"재시도 후 실패: {retry_result.error_message}",
                processing_time=processing_time
            )
    
    def _process_single_ocr_internal(self, task: OCRTask) -> Dict[str, Any]:
        """내부 OCR 처리 함수 (재시도 대상)"""
        # OCR 처리 실행
        ocr_result = self.ocr_service.extract_text(task.image_data)
        
        if not ocr_result.get('success', False):
            raise Exception(f"OCR 처리 실패: {ocr_result.get('error', 'Unknown error')}")
        
        return ocr_result
    
    def _process_single_ocr(self, task: OCRTask) -> OCRResult:
        """동기 버전 - 기존 호환성 유지"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._process_single_ocr_with_retry(task))
        finally:
            loop.close()
    
    async def process_batch_async(self, tasks: List[OCRTask]) -> List[OCRResult]:
        """비동기 배치 OCR 처리"""
        if not self._executor:
            raise RuntimeError("AsyncOCRService는 context manager로 사용해야 합니다")
        
        if not tasks:
            return []
        
        logger.info(f"비동기 배치 OCR 시작: {len(tasks)}개 작업")
        start_time = time.time()
        
        # 비동기 실행을 위한 루프 생성
        loop = asyncio.get_event_loop()
        
        # 모든 작업을 비동기로 실행 (재시도 로직 적용)
        futures = [
            self._process_single_ocr_with_retry(task)
            for task in tasks
        ]
        
        # 모든 작업 완료 대기
        results = await asyncio.gather(*futures, return_exceptions=True)
        
        # 예외 처리된 결과들을 OCRResult로 변환
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(OCRResult(
                    task_id=tasks[i].task_id,
                    file_path=tasks[i].file_path,
                    success=False,
                    error=str(result),
                    processing_time=0.0
                ))
            else:
                processed_results.append(result)
        
        total_time = time.time() - start_time
        successful = sum(1 for r in processed_results if r.success)
        cached_hits = sum(1 for r in processed_results if r.cached)
        
        logger.info(f"배치 OCR 완료: {successful}/{len(tasks)} 성공, "
                   f"{cached_hits} 캐시 히트, {total_time:.2f}초")
        
        return processed_results
    
    def create_tasks_from_directory(self, directory: str, max_files: int = None) -> List[OCRTask]:
        """디렉토리에서 OCR 작업 생성"""
        if not os.path.exists(directory):
            logger.error(f"디렉토리가 존재하지 않습니다: {directory}")
            return []
        
        tasks = []
        supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        
        # 이미지 파일 찾기
        image_files = []
        for file_name in os.listdir(directory):
            file_path = os.path.join(directory, file_name)
            if (os.path.isfile(file_path) and 
                os.path.splitext(file_name)[1].lower() in supported_extensions):
                image_files.append(file_path)
        
        # 파일 수 제한
        if max_files:
            image_files = image_files[:max_files]
        
        # OCR 작업 생성
        for i, file_path in enumerate(image_files):
            try:
                with open(file_path, 'rb') as f:
                    image_data = f.read()
                
                task = OCRTask(
                    file_path=file_path,
                    image_data=image_data,
                    task_id=f"task_{i:03d}_{os.path.basename(file_path)}",
                    metadata={'file_size': len(image_data)}
                )
                tasks.append(task)
                
            except Exception as e:
                logger.error(f"이미지 파일 읽기 실패 [{file_path}]: {e}")
        
        logger.info(f"OCR 작업 생성 완료: {len(tasks)}개")
        return tasks
    
    def get_performance_stats(self, results: List[OCRResult]) -> Dict[str, Any]:
        """성능 통계 계산"""
        if not results:
            return {}
        
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        cached = [r for r in results if r.cached]
        
        processing_times = [r.processing_time for r in results if r.processing_time > 0]
        
        stats = {
            'total_tasks': len(results),
            'successful_tasks': len(successful),
            'failed_tasks': len(failed),
            'cache_hits': len(cached),
            'success_rate': len(successful) / len(results) * 100 if results else 0,
            'cache_hit_rate': len(cached) / len(results) * 100 if results else 0,
            'total_processing_time': sum(processing_times),
            'average_processing_time': sum(processing_times) / len(processing_times) if processing_times else 0,
            'min_processing_time': min(processing_times) if processing_times else 0,
            'max_processing_time': max(processing_times) if processing_times else 0
        }
        
        return stats

# 편의 함수들
async def process_directory_async(directory: str, max_files: int = None, max_workers: int = 4) -> List[OCRResult]:
    """디렉토리의 이미지들을 비동기로 OCR 처리"""
    async with AsyncOCRService(max_workers=max_workers) as service:
        tasks = service.create_tasks_from_directory(directory, max_files)
        if not tasks:
            return []
        
        results = await service.process_batch_async(tasks)
        return results

def process_directory_sync(directory: str, max_files: int = None, max_workers: int = 4) -> List[OCRResult]:
    """디렉토리의 이미지들을 동기적으로 OCR 처리 (asyncio 래퍼)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(
            process_directory_async(directory, max_files, max_workers)
        )
    finally:
        loop.close()