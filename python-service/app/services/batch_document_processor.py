#!/usr/bin/env python3
"""
다중 문서 배치 처리 워크플로우
Multi-Document Batch Processing Workflow

대량 문서의 OCR, 표 분석, 차트 분석을 자동으로 처리하는 배치 시스템
"""

import asyncio
import uuid
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
import time
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

# 내부 서비스 임포트
from app.services.multilingual_two_tier_service import MultilingualTwoTierService
from app.services.table_structure_detector import table_detector
from app.services.chart_detector import chart_detector
from app.services.ocr_cache_service import ocr_cache

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """배치 작업 상태"""
    PENDING = "pending"      # 대기 중
    RUNNING = "running"      # 실행 중
    COMPLETED = "completed"  # 완료
    FAILED = "failed"        # 실패
    CANCELLED = "cancelled"  # 취소
    PAUSED = "paused"       # 일시정지


class DocumentType(Enum):
    """문서 처리 타입"""
    OCR_ONLY = "ocr_only"           # OCR만
    TABLE_ANALYSIS = "table_analysis"  # 표 분석
    CHART_ANALYSIS = "chart_analysis"  # 차트 분석
    FULL_ANALYSIS = "full_analysis"    # 전체 분석


@dataclass
class DocumentTask:
    """개별 문서 처리 작업"""
    task_id: str
    file_path: str
    document_type: DocumentType
    language: str = "kor"
    status: JobStatus = JobStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 0  # 0이 가장 높은 우선순위
    
    @property
    def processing_time(self) -> Optional[float]:
        """처리 시간 계산"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


@dataclass
class BatchJob:
    """배치 작업 정보"""
    job_id: str
    name: str
    tasks: List[DocumentTask]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    success_rate: float = 0.0
    estimated_completion: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        self.total_tasks = len(self.tasks)
    
    @property 
    def progress_percentage(self) -> float:
        """진행률 계산"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks + self.failed_tasks) / self.total_tasks * 100
    
    @property
    def processing_time(self) -> Optional[float]:
        """전체 처리 시간"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class BatchDocumentProcessor:
    """다중 문서 배치 처리기"""
    
    def __init__(self, max_workers: int = 4, storage_path: str = "/tmp/batch_jobs"):
        """
        초기화
        
        Args:
            max_workers: 최대 동시 처리 작업 수
            storage_path: 작업 상태 저장 경로
        """
        self.max_workers = max_workers
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 활성 작업 관리
        self.active_jobs: Dict[str, BatchJob] = {}
        self.job_lock = threading.Lock()
        
        # 처리 서비스들 초기화
        self.ocr_service = MultilingualTwoTierService()
        
        # 통계 정보
        self.stats = {
            "total_jobs": 0,
            "total_documents": 0,
            "successful_documents": 0,
            "failed_documents": 0,
            "average_processing_time": 0.0,
            "start_time": datetime.now()
        }
        
        logger.info(f"BatchDocumentProcessor 초기화: max_workers={max_workers}")
    
    def create_batch_job(
        self, 
        name: str, 
        file_paths: List[str], 
        document_type: DocumentType = DocumentType.FULL_ANALYSIS,
        language: str = "kor",
        priority_levels: Optional[List[int]] = None
    ) -> str:
        """
        배치 작업 생성
        
        Args:
            name: 작업 이름
            file_paths: 처리할 파일 경로 목록
            document_type: 문서 처리 타입
            language: OCR 언어
            priority_levels: 각 파일의 우선순위 (옵션)
            
        Returns:
            생성된 작업 ID
        """
        job_id = str(uuid.uuid4())
        
        # 문서 작업들 생성
        tasks = []
        for i, file_path in enumerate(file_paths):
            task_id = f"{job_id}_{i:04d}"
            priority = priority_levels[i] if priority_levels and i < len(priority_levels) else 0
            
            task = DocumentTask(
                task_id=task_id,
                file_path=file_path,
                document_type=document_type,
                language=language,
                priority=priority
            )
            tasks.append(task)
        
        # 우선순위로 정렬
        tasks.sort(key=lambda x: x.priority)
        
        # 배치 작업 생성
        batch_job = BatchJob(
            job_id=job_id,
            name=name,
            tasks=tasks
        )
        
        with self.job_lock:
            self.active_jobs[job_id] = batch_job
        
        # 디스크에 저장
        self._save_job_to_disk(batch_job)
        
        self.stats["total_jobs"] += 1
        self.stats["total_documents"] += len(tasks)
        
        logger.info(f"배치 작업 생성: {job_id} ({len(tasks)}개 문서)")
        return job_id
    
    async def process_batch_job(
        self, 
        job_id: str,
        progress_callback: Optional[Callable[[str, float, Dict], None]] = None
    ) -> Dict[str, Any]:
        """
        배치 작업 실행
        
        Args:
            job_id: 작업 ID
            progress_callback: 진행 상황 콜백 함수
            
        Returns:
            처리 결과
        """
        with self.job_lock:
            if job_id not in self.active_jobs:
                raise ValueError(f"작업을 찾을 수 없습니다: {job_id}")
            
            job = self.active_jobs[job_id]
            if job.status != JobStatus.PENDING:
                raise ValueError(f"작업이 이미 실행 중이거나 완료되었습니다: {job.status}")
            
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
        
        logger.info(f"배치 작업 시작: {job_id} ({job.total_tasks}개 문서)")
        
        try:
            # ThreadPoolExecutor로 병렬 처리
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 모든 작업 제출
                future_to_task = {
                    executor.submit(self._process_single_document, task): task
                    for task in job.tasks
                }
                
                # 완료된 작업들 처리
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    
                    try:
                        result = future.result()
                        task.result = result
                        task.status = JobStatus.COMPLETED
                        task.end_time = datetime.now()
                        
                        job.completed_tasks += 1
                        self.stats["successful_documents"] += 1
                        
                    except Exception as e:
                        logger.error(f"작업 실패 {task.task_id}: {e}")
                        task.error_message = str(e)
                        task.status = JobStatus.FAILED
                        task.end_time = datetime.now()
                        
                        job.failed_tasks += 1
                        self.stats["failed_documents"] += 1
                        
                        # 재시도 로직
                        if task.retry_count < task.max_retries:
                            logger.info(f"작업 재시도 {task.task_id} ({task.retry_count + 1}/{task.max_retries})")
                            task.retry_count += 1
                            task.status = JobStatus.PENDING
                            
                            # 재시도 작업 제출
                            new_future = executor.submit(self._process_single_document, task)
                            future_to_task[new_future] = task
                    
                    # 진행률 업데이트
                    job.success_rate = (job.completed_tasks / job.total_tasks) * 100 if job.total_tasks > 0 else 0
                    
                    # 완료 시간 추정
                    if job.completed_tasks > 0:
                        elapsed = (datetime.now() - job.started_at).total_seconds()
                        avg_time_per_task = elapsed / (job.completed_tasks + job.failed_tasks)
                        remaining_tasks = job.total_tasks - job.completed_tasks - job.failed_tasks
                        job.estimated_completion = datetime.now() + timedelta(seconds=avg_time_per_task * remaining_tasks)
                    
                    # 진행률 콜백 호출
                    if progress_callback:
                        progress_info = {
                            "completed": job.completed_tasks,
                            "failed": job.failed_tasks,
                            "total": job.total_tasks,
                            "success_rate": job.success_rate,
                            "estimated_completion": job.estimated_completion.isoformat() if job.estimated_completion else None
                        }
                        progress_callback(job_id, job.progress_percentage, progress_info)
                    
                    # 상태 저장
                    self._save_job_to_disk(job)
            
            # 작업 완료 처리
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            
            # 통계 업데이트
            if job.processing_time:
                total_time = self.stats["average_processing_time"] * (self.stats["total_jobs"] - 1)
                self.stats["average_processing_time"] = (total_time + job.processing_time) / self.stats["total_jobs"]
            
            logger.info(f"배치 작업 완료: {job_id} (성공률: {job.success_rate:.1f}%)")
            
            return {
                "job_id": job_id,
                "status": job.status.value,
                "total_tasks": job.total_tasks,
                "completed_tasks": job.completed_tasks,
                "failed_tasks": job.failed_tasks,
                "success_rate": job.success_rate,
                "processing_time": job.processing_time,
                "results": [asdict(task) for task in job.tasks]
            }
            
        except Exception as e:
            logger.error(f"배치 작업 실패: {job_id} - {e}")
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            raise
        finally:
            self._save_job_to_disk(job)
    
    def _process_single_document(self, task: DocumentTask) -> Dict[str, Any]:
        """
        개별 문서 처리
        
        Args:
            task: 문서 작업 정보
            
        Returns:
            처리 결과
        """
        task.start_time = datetime.now()
        task.status = JobStatus.RUNNING
        
        logger.info(f"문서 처리 시작: {task.task_id} ({task.file_path})")
        
        try:
            # 파일 존재 확인
            if not os.path.exists(task.file_path):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {task.file_path}")
            
            import cv2
            image = cv2.imread(task.file_path)
            if image is None:
                raise ValueError(f"이미지를 읽을 수 없습니다: {task.file_path}")
            
            result = {
                "task_id": task.task_id,
                "file_path": task.file_path,
                "document_type": task.document_type.value,
                "language": task.language,
                "processing_results": {}
            }
            
            # 문서 타입에 따른 처리
            if task.document_type in [DocumentType.OCR_ONLY, DocumentType.FULL_ANALYSIS]:
                # OCR 처리
                ocr_result = self.ocr_service.process_image_with_caching(
                    image_path=task.file_path,
                    language=task.language
                )
                result["processing_results"]["ocr"] = ocr_result
            
            if task.document_type in [DocumentType.TABLE_ANALYSIS, DocumentType.FULL_ANALYSIS]:
                # 표 분석
                tables = table_detector.detect_tables(image)
                table_results = []
                for i, table in enumerate(tables):
                    table_data = table_detector.to_structured_data(table)
                    table_results.append({
                        "table_id": i + 1,
                        "confidence": table.confidence,
                        "position": {
                            "x": table.x, "y": table.y,
                            "width": table.width, "height": table.height
                        },
                        "structure": table_data
                    })
                result["processing_results"]["tables"] = table_results
            
            if task.document_type in [DocumentType.CHART_ANALYSIS, DocumentType.FULL_ANALYSIS]:
                # 차트 분석
                charts = chart_detector.detect_charts(image)
                chart_results = []
                for i, chart in enumerate(charts):
                    chart_data = chart_detector.to_structured_data(chart)
                    chart_results.append({
                        "chart_id": i + 1,
                        "type": chart.chart_type,
                        "confidence": chart.confidence,
                        "position": {
                            "x": chart.x, "y": chart.y,
                            "width": chart.width, "height": chart.height
                        },
                        "data": chart_data
                    })
                result["processing_results"]["charts"] = chart_results
            
            # 처리 시간 기록
            processing_time = (datetime.now() - task.start_time).total_seconds()
            result["processing_time"] = processing_time
            
            logger.info(f"문서 처리 완료: {task.task_id} ({processing_time:.2f}초)")
            return result
            
        except Exception as e:
            logger.error(f"문서 처리 실패: {task.task_id} - {e}")
            logger.error(traceback.format_exc())
            raise
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        작업 상태 조회
        
        Args:
            job_id: 작업 ID
            
        Returns:
            작업 상태 정보
        """
        with self.job_lock:
            if job_id not in self.active_jobs:
                # 디스크에서 로드 시도
                job = self._load_job_from_disk(job_id)
                if job is None:
                    raise ValueError(f"작업을 찾을 수 없습니다: {job_id}")
                self.active_jobs[job_id] = job
            
            job = self.active_jobs[job_id]
        
        return {
            "job_id": job.job_id,
            "name": job.name,
            "status": job.status.value,
            "progress_percentage": job.progress_percentage,
            "total_tasks": job.total_tasks,
            "completed_tasks": job.completed_tasks,
            "failed_tasks": job.failed_tasks,
            "success_rate": job.success_rate,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "estimated_completion": job.estimated_completion.isoformat() if job.estimated_completion else None,
            "processing_time": job.processing_time
        }
    
    def cancel_job(self, job_id: str) -> bool:
        """
        작업 취소
        
        Args:
            job_id: 작업 ID
            
        Returns:
            취소 성공 여부
        """
        with self.job_lock:
            if job_id not in self.active_jobs:
                return False
            
            job = self.active_jobs[job_id]
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.CANCELLED
                self._save_job_to_disk(job)
                logger.info(f"작업 취소: {job_id}")
                return True
            
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """작업 일시정지"""
        with self.job_lock:
            if job_id not in self.active_jobs:
                return False
            
            job = self.active_jobs[job_id]
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.PAUSED
                self._save_job_to_disk(job)
                logger.info(f"작업 일시정지: {job_id}")
                return True
            
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """작업 재개"""
        with self.job_lock:
            if job_id not in self.active_jobs:
                return False
            
            job = self.active_jobs[job_id]
            if job.status == JobStatus.PAUSED:
                job.status = JobStatus.RUNNING
                self._save_job_to_disk(job)
                logger.info(f"작업 재개: {job_id}")
                return True
            
            return False
    
    def get_batch_statistics(self) -> Dict[str, Any]:
        """배치 처리 통계 반환"""
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
        
        return {
            "total_jobs": self.stats["total_jobs"],
            "active_jobs": len([j for j in self.active_jobs.values() if j.status == JobStatus.RUNNING]),
            "total_documents_processed": self.stats["total_documents"],
            "successful_documents": self.stats["successful_documents"],
            "failed_documents": self.stats["failed_documents"],
            "success_rate": (self.stats["successful_documents"] / max(1, self.stats["total_documents"])) * 100,
            "average_processing_time": self.stats["average_processing_time"],
            "uptime_seconds": uptime,
            "documents_per_hour": (self.stats["total_documents"] / max(1, uptime / 3600))
        }
    
    def _save_job_to_disk(self, job: BatchJob):
        """작업 상태를 디스크에 저장"""
        try:
            job_file = self.storage_path / f"{job.job_id}.json"
            job_data = {
                "job_id": job.job_id,
                "name": job.name,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "total_tasks": job.total_tasks,
                "completed_tasks": job.completed_tasks,
                "failed_tasks": job.failed_tasks,
                "success_rate": job.success_rate,
                "tasks": [asdict(task) for task in job.tasks]
            }
            
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(job_data, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"작업 저장 실패: {job.job_id} - {e}")
    
    def _load_job_from_disk(self, job_id: str) -> Optional[BatchJob]:
        """디스크에서 작업 상태 로드"""
        try:
            job_file = self.storage_path / f"{job_id}.json"
            if not job_file.exists():
                return None
            
            with open(job_file, 'r', encoding='utf-8') as f:
                job_data = json.load(f)
            
            # DocumentTask 객체들 재구성
            tasks = []
            for task_data in job_data["tasks"]:
                task_data["document_type"] = DocumentType(task_data["document_type"])
                task_data["status"] = JobStatus(task_data["status"])
                
                # datetime 필드 변환
                for field in ["start_time", "end_time"]:
                    if task_data[field]:
                        task_data[field] = datetime.fromisoformat(task_data[field])
                
                tasks.append(DocumentTask(**task_data))
            
            # BatchJob 객체 재구성
            job = BatchJob(
                job_id=job_data["job_id"],
                name=job_data["name"],
                tasks=tasks,
                status=JobStatus(job_data["status"]),
                created_at=datetime.fromisoformat(job_data["created_at"]),
                started_at=datetime.fromisoformat(job_data["started_at"]) if job_data["started_at"] else None,
                completed_at=datetime.fromisoformat(job_data["completed_at"]) if job_data["completed_at"] else None,
                total_tasks=job_data["total_tasks"],
                completed_tasks=job_data["completed_tasks"],
                failed_tasks=job_data["failed_tasks"],
                success_rate=job_data["success_rate"]
            )
            
            return job
            
        except Exception as e:
            logger.error(f"작업 로드 실패: {job_id} - {e}")
            return None
    
    def list_jobs(self, status_filter: Optional[JobStatus] = None) -> List[Dict[str, Any]]:
        """작업 목록 조회"""
        jobs = []
        
        # 메모리의 활성 작업들
        with self.job_lock:
            for job in self.active_jobs.values():
                if status_filter is None or job.status == status_filter:
                    jobs.append(self.get_job_status(job.job_id))
        
        # 디스크의 저장된 작업들도 확인
        for job_file in self.storage_path.glob("*.json"):
            job_id = job_file.stem
            if job_id not in self.active_jobs:
                try:
                    job = self._load_job_from_disk(job_id)
                    if job and (status_filter is None or job.status == status_filter):
                        jobs.append(self.get_job_status(job_id))
                except Exception as e:
                    logger.warning(f"작업 파일 로드 실패: {job_file} - {e}")
        
        # 생성 시간 순으로 정렬
        jobs.sort(key=lambda x: x["created_at"], reverse=True)
        return jobs


# 전역 인스턴스
batch_processor = BatchDocumentProcessor()