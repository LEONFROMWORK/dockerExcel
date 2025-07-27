"""
비동기 OCR 배치 처리 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import os
import logging
import time
from app.services.async_ocr_service import AsyncOCRService, process_directory_async

logger = logging.getLogger(__name__)
router = APIRouter()

# 진행 중인 작업 추적용 메모리 저장소 (실제 운영에서는 Redis 사용)
active_jobs = {}

class BatchOCRRequest(BaseModel):
    directory: str
    max_files: Optional[int] = None
    max_workers: Optional[int] = 4

class BatchOCRResponse(BaseModel):
    job_id: str
    status: str
    message: str
    total_tasks: int
    estimated_time: Optional[float] = None

@router.post("/batch/directory")
async def process_directory_batch(request: BatchOCRRequest):
    """
    디렉토리의 이미지들을 배치로 OCR 처리
    """
    try:
        # 디렉토리 존재 확인
        if not os.path.exists(request.directory):
            raise HTTPException(
                status_code=400,
                detail=f"디렉토리가 존재하지 않습니다: {request.directory}"
            )
        
        # 작업 ID 생성
        job_id = f"batch_ocr_{int(time.time())}_{len(active_jobs)}"
        
        # 이미지 파일 수 확인
        supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        image_files = [
            f for f in os.listdir(request.directory)
            if os.path.splitext(f)[1].lower() in supported_extensions
        ]
        
        total_files = len(image_files)
        if request.max_files:
            total_files = min(total_files, request.max_files)
        
        if total_files == 0:
            raise HTTPException(
                status_code=400,
                detail="처리할 이미지 파일이 없습니다"
            )
        
        # 작업 상태 초기화
        active_jobs[job_id] = {
            'status': 'processing',
            'total_tasks': total_files,
            'completed_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'cache_hits': 0,
            'start_time': time.time(),
            'results': []
        }
        
        # 비동기 처리 시작
        asyncio.create_task(
            _process_batch_job(
                job_id, 
                request.directory,
                request.max_files,
                request.max_workers
            )
        )
        
        # 예상 처리 시간 계산 (파일당 평균 1초 가정, 워커 수만큼 병렬)
        estimated_time = total_files / request.max_workers
        
        logger.info(f"배치 OCR 작업 시작: {job_id} ({total_files}개 파일)")
        
        return JSONResponse(content={
            "job_id": job_id,
            "status": "processing",
            "message": f"배치 OCR 처리를 시작했습니다",
            "total_tasks": total_files,
            "estimated_time": estimated_time
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"배치 OCR 요청 처리 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"배치 OCR 처리 실패: {str(e)}"
        )

async def _process_batch_job(job_id: str, directory: str, max_files: int, max_workers: int):
    """배치 작업 실제 처리 (백그라운드)"""
    try:
        # OCR 처리 실행
        results = await process_directory_async(directory, max_files, max_workers)
        
        # 결과 통계 계산
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        cached = sum(1 for r in results if r.cached)
        
        # 작업 상태 업데이트
        active_jobs[job_id].update({
            'status': 'completed',
            'completed_tasks': len(results),
            'successful_tasks': successful,
            'failed_tasks': failed,
            'cache_hits': cached,
            'end_time': time.time(),
            'results': [
                {
                    'task_id': r.task_id,
                    'file_path': r.file_path,
                    'success': r.success,
                    'processing_time': r.processing_time,
                    'cached': r.cached,
                    'error': r.error,
                    'text': r.result.get('text', '') if r.result else '',
                    'text_length': len(r.result.get('text', '')) if r.result else 0,
                    'language': r.result.get('language') if r.result else None,
                    'confidence': r.result.get('confidence') if r.result else 0
                }
                for r in results
            ]
        })
        
        logger.info(f"배치 OCR 작업 완료: {job_id} ({successful}/{len(results)} 성공)")
        
    except Exception as e:
        logger.error(f"배치 OCR 작업 실패 [{job_id}]: {e}")
        active_jobs[job_id].update({
            'status': 'failed',
            'error': str(e),
            'end_time': time.time()
        })

@router.get("/batch/status/{job_id}")
async def get_batch_status(job_id: str):
    """
    배치 작업 상태 조회
    """
    if job_id not in active_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"작업을 찾을 수 없습니다: {job_id}"
        )
    
    job_info = active_jobs[job_id].copy()
    
    # 진행률 계산
    if job_info['total_tasks'] > 0:
        progress = (job_info['completed_tasks'] / job_info['total_tasks']) * 100
        job_info['progress_percent'] = round(progress, 2)
    
    # 처리 시간 계산
    if 'end_time' in job_info:
        job_info['total_time'] = job_info['end_time'] - job_info['start_time']
    else:
        job_info['elapsed_time'] = time.time() - job_info['start_time']
    
    return JSONResponse(content=job_info)

@router.get("/batch/results/{job_id}")
async def get_batch_results(job_id: str, include_details: bool = Query(False)):
    """
    배치 작업 결과 조회
    """
    if job_id not in active_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"작업을 찾을 수 없습니다: {job_id}"
        )
    
    job_info = active_jobs[job_id]
    
    if job_info['status'] == 'processing':
        raise HTTPException(
            status_code=202,
            detail="작업이 아직 진행 중입니다"
        )
    
    if job_info['status'] == 'failed':
        raise HTTPException(
            status_code=500,
            detail=f"작업이 실패했습니다: {job_info.get('error', '알 수 없는 오류')}"
        )
    
    # 결과 요약
    summary = {
        'job_id': job_id,
        'status': job_info['status'],
        'total_tasks': job_info['total_tasks'],
        'completed_tasks': job_info['completed_tasks'],
        'successful_tasks': job_info['successful_tasks'],
        'failed_tasks': job_info['failed_tasks'],
        'cache_hits': job_info['cache_hits'],
        'success_rate': round((job_info['successful_tasks'] / job_info['total_tasks']) * 100, 2) if job_info['total_tasks'] > 0 else 0,
        'cache_hit_rate': round((job_info['cache_hits'] / job_info['total_tasks']) * 100, 2) if job_info['total_tasks'] > 0 else 0,
        'total_time': job_info.get('end_time', time.time()) - job_info['start_time']
    }
    
    if include_details:
        summary['results'] = job_info['results']
    
    return JSONResponse(content=summary)

@router.delete("/batch/job/{job_id}")
async def cleanup_batch_job(job_id: str):
    """
    완료된 배치 작업 정리
    """
    if job_id not in active_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"작업을 찾을 수 없습니다: {job_id}"
        )
    
    job_status = active_jobs[job_id]['status']
    if job_status == 'processing':
        raise HTTPException(
            status_code=400,
            detail="진행 중인 작업은 삭제할 수 없습니다"
        )
    
    del active_jobs[job_id]
    
    return JSONResponse(content={
        "message": f"작업 {job_id}가 정리되었습니다",
        "job_id": job_id
    })

@router.get("/batch/jobs")
async def list_batch_jobs():
    """
    모든 배치 작업 목록 조회
    """
    jobs = []
    for job_id, job_info in active_jobs.items():
        job_summary = {
            'job_id': job_id,
            'status': job_info['status'],
            'total_tasks': job_info['total_tasks'],
            'completed_tasks': job_info['completed_tasks'],
            'start_time': job_info['start_time']
        }
        
        if 'end_time' in job_info:
            job_summary['end_time'] = job_info['end_time']
            job_summary['total_time'] = job_info['end_time'] - job_info['start_time']
        else:
            job_summary['elapsed_time'] = time.time() - job_info['start_time']
        
        jobs.append(job_summary)
    
    return JSONResponse(content={
        "active_jobs": len([j for j in jobs if j['status'] == 'processing']),
        "completed_jobs": len([j for j in jobs if j['status'] == 'completed']),
        "failed_jobs": len([j for j in jobs if j['status'] == 'failed']),
        "jobs": jobs
    })