#!/usr/bin/env python3
"""
배치 처리 API 엔드포인트
Batch Processing API Endpoints

다중 문서 배치 처리를 위한 RESTful API
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional, Union
import os
import tempfile
import shutil
import json
import logging
from pathlib import Path
import asyncio
from datetime import datetime

from app.services.batch_document_processor import (
    batch_processor, 
    DocumentType, 
    JobStatus
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/create-job", response_model=Dict[str, Any])
async def create_batch_job(
    name: str = Form(...),
    document_type: str = Form("full_analysis"),
    language: str = Form("kor"),
    files: List[UploadFile] = File(...),
    priorities: Optional[str] = Form("[]")  # JSON 문자열로 우선순위 리스트
):
    """
    배치 처리 작업 생성
    
    Args:
        name: 작업 이름
        document_type: 문서 처리 타입 (ocr_only, table_analysis, chart_analysis, full_analysis)
        language: OCR 언어 코드
        files: 처리할 파일들
        priorities: 각 파일의 우선순위 (JSON 배열)
        
    Returns:
        생성된 작업 정보
    """
    try:
        # 파일 검증
        if not files:
            raise HTTPException(status_code=400, detail="파일이 제공되지 않았습니다")
        
        if len(files) > 100:  # 최대 100개 파일 제한
            raise HTTPException(status_code=400, detail="한 번에 최대 100개 파일까지 처리할 수 있습니다")
        
        # 문서 타입 검증
        try:
            doc_type = DocumentType(document_type)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 문서 타입: {document_type}"
            )
        
        # 우선순위 파싱
        try:
            priority_levels = json.loads(priorities) if priorities != "[]" else None
            if priority_levels and len(priority_levels) != len(files):
                priority_levels = None  # 길이가 맞지 않으면 무시
        except json.JSONDecodeError:
            priority_levels = None
        
        # 임시 디렉토리 생성
        temp_dir = Path(tempfile.mkdtemp(prefix="batch_job_"))
        file_paths = []
        
        try:
            # 파일들을 임시 디렉토리에 저장
            for i, file in enumerate(files):
                # 파일 타입 검증
                if not file.content_type or not file.content_type.startswith("image/"):
                    logger.warning(f"이미지가 아닌 파일 건너뛰기: {file.filename}")
                    continue
                
                # 안전한 파일명 생성
                safe_filename = f"file_{i:04d}_{file.filename}"
                file_path = temp_dir / safe_filename
                
                # 파일 저장
                with open(file_path, "wb") as temp_file:
                    content = await file.read()
                    temp_file.write(content)
                
                file_paths.append(str(file_path))
        
        except Exception as e:
            # 임시 파일들 정리
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"파일 저장 실패: {str(e)}")
        
        if not file_paths:
            # 임시 파일들 정리
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail="처리할 수 있는 이미지 파일이 없습니다")
        
        logger.info(f"배치 작업 생성 요청: {name} ({len(file_paths)}개 파일)")
        
        # 배치 작업 생성
        job_id = batch_processor.create_batch_job(
            name=name,
            file_paths=file_paths,
            document_type=doc_type,
            language=language,
            priority_levels=priority_levels
        )
        
        return {
            "success": True,
            "job_id": job_id,
            "message": f"배치 작업이 생성되었습니다",
            "job_info": {
                "name": name,
                "document_type": document_type,
                "language": language,
                "total_files": len(file_paths),
                "temp_directory": str(temp_dir)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"배치 작업 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"작업 생성 중 오류 발생: {str(e)}")


@router.post("/start-job/{job_id}", response_model=Dict[str, Any])
async def start_batch_job(job_id: str, background_tasks: BackgroundTasks):
    """
    배치 작업 시작
    
    Args:
        job_id: 작업 ID
        background_tasks: FastAPI 백그라운드 작업
        
    Returns:
        작업 시작 확인
    """
    try:
        # 작업 존재 확인
        job_status = batch_processor.get_job_status(job_id)
        
        if job_status["status"] != JobStatus.PENDING.value:
            raise HTTPException(
                status_code=400, 
                detail=f"작업을 시작할 수 없습니다. 현재 상태: {job_status['status']}"
            )
        
        # 백그라운드에서 작업 실행
        background_tasks.add_task(execute_batch_job, job_id)
        
        logger.info(f"배치 작업 시작: {job_id}")
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "배치 작업이 시작되었습니다",
            "status": "running"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"배치 작업 시작 실패: {job_id} - {e}")
        raise HTTPException(status_code=500, detail=f"작업 시작 실패: {str(e)}")


async def execute_batch_job(job_id: str):
    """백그라운드에서 실행되는 배치 작업"""
    try:
        def progress_callback(job_id: str, progress: float, info: Dict):
            logger.info(f"작업 진행률: {job_id} - {progress:.1f}% "
                       f"(완료: {info['completed']}, 실패: {info['failed']})")
        
        # 배치 작업 실행
        result = await batch_processor.process_batch_job(job_id, progress_callback)
        logger.info(f"배치 작업 완료: {job_id} - 성공률: {result['success_rate']:.1f}%")
        
    except Exception as e:
        logger.error(f"배치 작업 실행 실패: {job_id} - {e}")


@router.get("/job/{job_id}/status", response_model=Dict[str, Any])
async def get_job_status(job_id: str):
    """
    작업 상태 조회
    
    Args:
        job_id: 작업 ID
        
    Returns:
        작업 상태 정보
    """
    try:
        status = batch_processor.get_job_status(job_id)
        return {
            "success": True,
            "job_status": status
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"작업 상태 조회 실패: {job_id} - {e}")
        raise HTTPException(status_code=500, detail=f"상태 조회 실패: {str(e)}")


@router.get("/job/{job_id}/results", response_model=Dict[str, Any])
async def get_job_results(job_id: str, include_details: bool = True):
    """
    작업 결과 조회
    
    Args:
        job_id: 작업 ID
        include_details: 상세 결과 포함 여부
        
    Returns:
        작업 결과
    """
    try:
        status = batch_processor.get_job_status(job_id)
        
        if status["status"] not in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
            raise HTTPException(
                status_code=400, 
                detail=f"작업이 완료되지 않았습니다. 현재 상태: {status['status']}"
            )
        
        # 상세 결과 가져오기
        with batch_processor.job_lock:
            job = batch_processor.active_jobs.get(job_id)
            if job is None:
                job = batch_processor._load_job_from_disk(job_id)
                if job is None:
                    raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        # 결과 구성
        result = {
            "success": True,
            "job_id": job_id,
            "job_status": status,
            "summary": {
                "total_documents": job.total_tasks,
                "successful_documents": job.completed_tasks,
                "failed_documents": job.failed_tasks,
                "success_rate": job.success_rate,
                "processing_time": job.processing_time
            }
        }
        
        if include_details:
            # 각 문서의 처리 결과
            task_results = []
            for task in job.tasks:
                task_result = {
                    "task_id": task.task_id,
                    "file_path": os.path.basename(task.file_path),  # 보안상 파일명만
                    "status": task.status.value,
                    "processing_time": task.processing_time,
                    "retry_count": task.retry_count
                }
                
                if task.status == JobStatus.COMPLETED and task.result:
                    task_result["result"] = task.result
                elif task.status == JobStatus.FAILED and task.error_message:
                    task_result["error"] = task.error_message
                
                task_results.append(task_result)
            
            result["task_results"] = task_results
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 결과 조회 실패: {job_id} - {e}")
        raise HTTPException(status_code=500, detail=f"결과 조회 실패: {str(e)}")


@router.post("/job/{job_id}/cancel")
async def cancel_job(job_id: str):
    """작업 취소"""
    try:
        success = batch_processor.cancel_job(job_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="작업을 취소할 수 없습니다")
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "작업이 취소되었습니다"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 취소 실패: {job_id} - {e}")
        raise HTTPException(status_code=500, detail=f"작업 취소 실패: {str(e)}")


@router.post("/job/{job_id}/pause")
async def pause_job(job_id: str):
    """작업 일시정지"""
    try:
        success = batch_processor.pause_job(job_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="작업을 일시정지할 수 없습니다")
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "작업이 일시정지되었습니다"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 일시정지 실패: {job_id} - {e}")
        raise HTTPException(status_code=500, detail=f"작업 일시정지 실패: {str(e)}")


@router.post("/job/{job_id}/resume")
async def resume_job(job_id: str):
    """작업 재개"""
    try:
        success = batch_processor.resume_job(job_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="작업을 재개할 수 없습니다")
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "작업이 재개되었습니다"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 재개 실패: {job_id} - {e}")
        raise HTTPException(status_code=500, detail=f"작업 재개 실패: {str(e)}")


@router.get("/jobs", response_model=Dict[str, Any])
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    작업 목록 조회
    
    Args:
        status: 상태 필터 (pending, running, completed, failed, cancelled, paused)
        limit: 반환할 작업 수 제한
        offset: 오프셋
        
    Returns:
        작업 목록
    """
    try:
        # 상태 필터 검증
        status_filter = None
        if status:
            try:
                status_filter = JobStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"잘못된 상태: {status}")
        
        # 작업 목록 조회
        all_jobs = batch_processor.list_jobs(status_filter)
        
        # 페이징 적용
        total_jobs = len(all_jobs)
        jobs = all_jobs[offset:offset + limit]
        
        return {
            "success": True,
            "total_jobs": total_jobs,
            "returned_jobs": len(jobs),
            "offset": offset,
            "limit": limit,
            "jobs": jobs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"목록 조회 실패: {str(e)}")


@router.get("/statistics", response_model=Dict[str, Any])
async def get_batch_statistics():
    """배치 처리 통계 조회"""
    try:
        stats = batch_processor.get_batch_statistics()
        
        return {
            "success": True,
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.get("/supported-types", response_model=Dict[str, Any])
async def get_supported_document_types():
    """지원되는 문서 처리 타입 조회"""
    return {
        "success": True,
        "document_types": {
            "ocr_only": {
                "name": "OCR 전용",
                "description": "텍스트 인식만 수행",
                "features": ["다국어 OCR", "텍스트 추출", "신뢰도 점수"]
            },
            "table_analysis": {
                "name": "표 분석",
                "description": "표 구조 인식 및 데이터 추출",
                "features": ["표 경계 감지", "셀 구조 분석", "헤더 인식", "데이터 추출"]
            },
            "chart_analysis": {
                "name": "차트 분석",
                "description": "차트/그래프 인식 및 데이터 추출",
                "features": ["차트 타입 감지", "데이터 포인트 추출", "축 정보", "범례 인식"]
            },
            "full_analysis": {
                "name": "전체 분석",
                "description": "OCR, 표, 차트 분석을 모두 수행",
                "features": ["모든 기능 포함", "종합적 문서 분석", "구조화된 데이터 출력"]
            }
        },
        "supported_languages": [
            "kor", "eng", "chi_sim", "chi_tra", "jpn", "ara", 
            "spa", "por", "fra", "deu", "ita", "vie"
        ]
    }


@router.get("/health")
async def batch_health_check():
    """배치 처리 서비스 상태 확인"""
    try:
        stats = batch_processor.get_batch_statistics()
        
        return {
            "status": "healthy",
            "service": "batch_processing",
            "version": "1.0.0",
            "active_jobs": stats["active_jobs"],
            "total_processed": stats["total_documents_processed"],
            "uptime_hours": round(stats["uptime_seconds"] / 3600, 2),
            "features": [
                "multi_document_processing",
                "progress_tracking",
                "error_handling",
                "retry_mechanism",
                "job_management"
            ]
        }
        
    except Exception as e:
        logger.error(f"건강 상태 확인 실패: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }