"""
전략적 배치 작업 관리 시스템
비즈니스 가치 중심의 실용적 배치 처리 및 모니터링
SOLID 원칙 기반, 서비스 경쟁력 최대화 목표
"""

import time
import logging
import asyncio
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
from datetime import datetime, timedelta
import heapq
from collections import defaultdict, deque
import psutil
import json

logger = logging.getLogger(__name__)

# ===== 비즈니스 중심 데이터 모델 =====

class JobPriority(Enum):
    """작업 우선순위 - 비즈니스 가치 기준"""
    CRITICAL = 1      # 매출 직결 작업 (고객 요청, 결제 처리)
    HIGH = 2          # 운영 핵심 작업 (데이터 백업, 보고서 생성)
    NORMAL = 3        # 일반 업무 작업 (데이터 처리, 분석)
    LOW = 4           # 유지보수 작업 (정리, 최적화)

class JobStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class JobType(Enum):
    """작업 유형 - 비즈니스 카테고리"""
    CUSTOMER_DATA = "customer_data"      # 고객 데이터 처리
    FINANCIAL_REPORT = "financial_report" # 재무 보고서 생성
    OCR_PROCESSING = "ocr_processing"    # OCR 대량 처리
    DATA_MIGRATION = "data_migration"    # 데이터 이관
    SYSTEM_MAINTENANCE = "system_maintenance" # 시스템 유지보수

@dataclass
class BusinessMetrics:
    """비즈니스 메트릭"""
    revenue_impact: float = 0.0        # 매출 영향도 (USD)
    customer_count: int = 0            # 영향받는 고객 수
    processing_cost: float = 0.0       # 처리 비용 (USD)
    sla_deadline: Optional[datetime] = None  # SLA 마감시간
    business_value_score: float = 0.0  # 비즈니스 가치 점수
    
    @property
    def roi_potential(self) -> float:
        """ROI 잠재력 계산"""
        if self.processing_cost <= 0:
            return float('inf')
        return self.revenue_impact / self.processing_cost

@dataclass
class BatchJob:
    """배치 작업 정의"""
    job_id: str
    job_type: JobType
    priority: JobPriority
    status: JobStatus = JobStatus.PENDING
    
    # 작업 내용
    task_function: Callable = None
    task_args: tuple = ()
    task_kwargs: dict = field(default_factory=dict)
    
    # 비즈니스 정보
    business_metrics: BusinessMetrics = field(default_factory=BusinessMetrics)
    description: str = ""
    customer_id: Optional[str] = None
    
    # 실행 정보
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_duration: int = 300  # 예상 소요시간 (초)
    
    # 리소스 요구사항
    cpu_requirement: float = 1.0      # CPU 코어 수
    memory_requirement: int = 512     # 메모리 MB
    
    # 재시도 설정
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: int = 60  # 재시도 간격 (초)
    
    # 결과
    result: Any = None
    error_message: str = ""
    execution_log: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.job_id:
            self.job_id = f"{self.job_type.value}_{int(time.time())}"
    
    @property
    def is_urgent(self) -> bool:
        """긴급 작업 여부"""
        if self.business_metrics.sla_deadline:
            time_left = self.business_metrics.sla_deadline - datetime.now()
            return time_left.total_seconds() < 3600  # 1시간 미만
        return self.priority in [JobPriority.CRITICAL, JobPriority.HIGH]
    
    @property
    def business_score(self) -> float:
        """비즈니스 점수 계산"""
        base_score = self.business_metrics.business_value_score
        
        # 우선순위 가중치
        priority_weight = {
            JobPriority.CRITICAL: 4.0,
            JobPriority.HIGH: 3.0,
            JobPriority.NORMAL: 2.0,
            JobPriority.LOW: 1.0
        }
        
        # 긴급도 가중치
        urgency_weight = 2.0 if self.is_urgent else 1.0
        
        # 고객 영향도 가중치
        customer_weight = min(self.business_metrics.customer_count / 100, 3.0)
        
        return base_score * priority_weight[self.priority] * urgency_weight * (1 + customer_weight)

# ===== 인터페이스 정의 (Interface Segregation Principle) =====

class JobScheduler(ABC):
    """작업 스케줄러 인터페이스"""
    
    @abstractmethod
    def submit_job(self, job: BatchJob) -> str:
        """작업 제출"""
        pass
    
    @abstractmethod
    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """작업 상태 조회"""
        pass
    
    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """작업 취소"""
        pass

class ResourceManager(ABC):
    """리소스 관리자 인터페이스"""
    
    @abstractmethod
    def can_allocate(self, cpu: float, memory: int) -> bool:
        """리소스 할당 가능 여부"""
        pass
    
    @abstractmethod
    def allocate_resources(self, job_id: str, cpu: float, memory: int) -> bool:
        """리소스 할당"""
        pass
    
    @abstractmethod
    def release_resources(self, job_id: str) -> None:
        """리소스 해제"""
        pass

class BusinessAnalyzer(ABC):
    """비즈니스 분석기 인터페이스"""
    
    @abstractmethod
    def calculate_business_value(self, job: BatchJob) -> float:
        """비즈니스 가치 계산"""
        pass
    
    @abstractmethod
    def get_roi_analysis(self, completed_jobs: List[BatchJob]) -> Dict[str, Any]:
        """ROI 분석"""
        pass

# ===== 핵심 구현 (Single Responsibility Principle) =====

class SystemResourceManager(ResourceManager):
    """시스템 리소스 관리자"""
    
    def __init__(self, max_cpu_usage: float = 80.0, max_memory_usage: float = 80.0):
        self.max_cpu_usage = max_cpu_usage
        self.max_memory_usage = max_memory_usage
        self.allocated_resources: Dict[str, Dict[str, float]] = {}
        self.lock = threading.Lock()
    
    def can_allocate(self, cpu: float, memory: int) -> bool:
        """리소스 할당 가능 여부 확인"""
        try:
            current_cpu = psutil.cpu_percent(interval=1)
            current_memory = psutil.virtual_memory().percent
            
            with self.lock:
                allocated_cpu = sum(res['cpu'] for res in self.allocated_resources.values())
                allocated_memory = sum(res['memory'] for res in self.allocated_resources.values())
            
            projected_cpu = current_cpu + (cpu / psutil.cpu_count() * 100) + allocated_cpu
            projected_memory = current_memory + (memory / psutil.virtual_memory().total * 100) + allocated_memory
            
            return projected_cpu < self.max_cpu_usage and projected_memory < self.max_memory_usage
        
        except Exception as e:
            logger.warning(f"리소스 확인 실패: {e}")
            return True  # 기본적으로 허용
    
    def allocate_resources(self, job_id: str, cpu: float, memory: int) -> bool:
        """리소스 할당"""
        if not self.can_allocate(cpu, memory):
            return False
        
        with self.lock:
            self.allocated_resources[job_id] = {
                'cpu': cpu,
                'memory': memory,
                'allocated_at': time.time()
            }
        
        logger.info(f"리소스 할당됨 {job_id}: CPU {cpu}, Memory {memory}MB")
        return True
    
    def release_resources(self, job_id: str) -> None:
        """리소스 해제"""
        with self.lock:
            if job_id in self.allocated_resources:
                resources = self.allocated_resources.pop(job_id)
                logger.info(f"리소스 해제됨 {job_id}: {resources}")
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """리소스 사용 통계"""
        try:
            with self.lock:
                allocated_cpu = sum(res['cpu'] for res in self.allocated_resources.values())
                allocated_memory = sum(res['memory'] for res in self.allocated_resources.values())
            
            return {
                'system_cpu_percent': psutil.cpu_percent(),
                'system_memory_percent': psutil.virtual_memory().percent,
                'allocated_cpu_cores': allocated_cpu,
                'allocated_memory_mb': allocated_memory,
                'active_jobs': len(self.allocated_resources),
                'available_cpu_cores': psutil.cpu_count() - allocated_cpu,
                'available_memory_gb': psutil.virtual_memory().available / (1024**3)
            }
        except Exception as e:
            logger.error(f"리소스 통계 수집 실패: {e}")
            return {}

class BusinessValueAnalyzer(BusinessAnalyzer):
    """비즈니스 가치 분석기"""
    
    def __init__(self):
        self.historical_data: List[BatchJob] = []
        self.value_weights = {
            JobType.CUSTOMER_DATA: 1.5,      # 고객 데이터는 중요
            JobType.FINANCIAL_REPORT: 1.3,   # 재무 보고서는 중요
            JobType.OCR_PROCESSING: 1.0,     # OCR은 기본
            JobType.DATA_MIGRATION: 0.8,     # 이관은 상대적으로 낮음
            JobType.SYSTEM_MAINTENANCE: 0.6  # 유지보수는 가장 낮음
        }
    
    def calculate_business_value(self, job: BatchJob) -> float:
        """비즈니스 가치 계산"""
        base_value = 100.0  # 기본 점수
        
        # 작업 유형별 가중치
        type_multiplier = self.value_weights.get(job.job_type, 1.0)
        
        # 매출 영향도
        revenue_score = min(job.business_metrics.revenue_impact / 1000, 5.0)  # 최대 5점
        
        # 고객 영향도
        customer_score = min(job.business_metrics.customer_count / 50, 3.0)  # 최대 3점
        
        # 긴급도 점수
        urgency_score = 2.0 if job.is_urgent else 1.0
        
        # SLA 점수
        sla_score = 1.0
        if job.business_metrics.sla_deadline:
            time_left = job.business_metrics.sla_deadline - datetime.now()
            if time_left.total_seconds() < 1800:  # 30분 미만
                sla_score = 3.0
            elif time_left.total_seconds() < 3600:  # 1시간 미만
                sla_score = 2.0
        
        total_score = (base_value + revenue_score + customer_score) * type_multiplier * urgency_score * sla_score
        
        # 비즈니스 메트릭 업데이트
        job.business_metrics.business_value_score = total_score
        
        return total_score
    
    def get_roi_analysis(self, completed_jobs: List[BatchJob]) -> Dict[str, Any]:
        """ROI 분석"""
        if not completed_jobs:
            return {"status": "no_data"}
        
        total_revenue_impact = sum(job.business_metrics.revenue_impact for job in completed_jobs)
        total_processing_cost = sum(job.business_metrics.processing_cost for job in completed_jobs)
        total_customers_affected = sum(job.business_metrics.customer_count for job in completed_jobs)
        
        roi = (total_revenue_impact / total_processing_cost) if total_processing_cost > 0 else float('inf')
        
        # 작업 유형별 분석
        type_analysis = defaultdict(lambda: {'count': 0, 'revenue': 0, 'cost': 0, 'customers': 0})
        for job in completed_jobs:
            type_analysis[job.job_type.value]['count'] += 1
            type_analysis[job.job_type.value]['revenue'] += job.business_metrics.revenue_impact
            type_analysis[job.job_type.value]['cost'] += job.business_metrics.processing_cost
            type_analysis[job.job_type.value]['customers'] += job.business_metrics.customer_count
        
        # 성과 지표
        avg_completion_time = sum(
            (job.completed_at - job.started_at).total_seconds() 
            for job in completed_jobs 
            if job.completed_at and job.started_at
        ) / len(completed_jobs)
        
        success_rate = len([job for job in completed_jobs if job.status == JobStatus.COMPLETED]) / len(completed_jobs)
        
        return {
            'overall_roi': roi,
            'total_revenue_impact': total_revenue_impact,
            'total_processing_cost': total_processing_cost,
            'total_customers_affected': total_customers_affected,
            'total_jobs_completed': len(completed_jobs),
            'success_rate_percent': success_rate * 100,
            'avg_completion_time_minutes': avg_completion_time / 60,
            'type_analysis': dict(type_analysis),
            'top_value_jobs': sorted(
                completed_jobs, 
                key=lambda x: x.business_metrics.business_value_score, 
                reverse=True
            )[:5]
        }

class PriorityJobScheduler(JobScheduler):
    """우선순위 기반 작업 스케줄러"""
    
    def __init__(self, resource_manager: ResourceManager, business_analyzer: BusinessAnalyzer):
        self.resource_manager = resource_manager
        self.business_analyzer = business_analyzer
        
        # 작업 큐 (우선순위 힙)
        self.job_queue: List[tuple] = []  # (negative_business_score, job)
        self.active_jobs: Dict[str, BatchJob] = {}
        self.completed_jobs: List[BatchJob] = []
        self.job_history: Dict[str, BatchJob] = {}
        
        # 동기화
        self.queue_lock = threading.Lock()
        self.active_lock = threading.Lock()
        
        # 워커 스레드
        self.max_concurrent_jobs = 5
        self.workers_running = False
        self.worker_threads: List[threading.Thread] = []
        
        # 통계
        self.stats = {
            'total_submitted': 0,
            'total_completed': 0,
            'total_failed': 0,
            'total_cancelled': 0
        }
    
    def start_workers(self) -> None:
        """워커 스레드 시작"""
        self.workers_running = True
        
        for i in range(self.max_concurrent_jobs):
            worker = threading.Thread(
                target=self._worker_loop, 
                name=f"BatchWorker-{i}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
        
        logger.info(f"{self.max_concurrent_jobs}개 배치 워커 시작됨")
    
    def stop_workers(self) -> None:
        """워커 스레드 정지"""
        self.workers_running = False
        
        for worker in self.worker_threads:
            worker.join(timeout=30)
        
        logger.info("모든 배치 워커 정지됨")
    
    def submit_job(self, job: BatchJob) -> str:
        """작업 제출"""
        # 비즈니스 가치 계산
        business_value = self.business_analyzer.calculate_business_value(job)
        
        with self.queue_lock:
            # 음수로 저장 (최대 힙을 최소 힙처럼 사용)
            heapq.heappush(self.job_queue, (-business_value, time.time(), job))
            self.job_history[job.job_id] = job
            self.stats['total_submitted'] += 1
        
        logger.info(f"작업 제출됨: {job.job_id} (우선순위: {business_value:.2f})")
        return job.job_id
    
    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """작업 상태 조회"""
        if job_id in self.job_history:
            return self.job_history[job_id].status
        return None
    
    def cancel_job(self, job_id: str) -> bool:
        """작업 취소"""
        # 큐에서 제거는 복잡하므로, 상태만 변경
        if job_id in self.job_history:
            job = self.job_history[job_id]
            if job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                self.stats['total_cancelled'] += 1
                logger.info(f"작업 취소됨: {job_id}")
                return True
        return False
    
    def _worker_loop(self) -> None:
        """워커 루프"""
        while self.workers_running:
            try:
                job = self._get_next_job()
                if job:
                    self._execute_job(job)
                else:
                    time.sleep(1)  # 작업이 없으면 대기
            except Exception as e:
                logger.error(f"워커 오류: {e}")
                time.sleep(5)
    
    def _get_next_job(self) -> Optional[BatchJob]:
        """다음 실행할 작업 가져오기"""
        with self.queue_lock:
            while self.job_queue:
                neg_score, submit_time, job = heapq.heappop(self.job_queue)
                
                # 취소된 작업 스킵
                if job.status == JobStatus.CANCELLED:
                    continue
                
                # 리소스 할당 가능 여부 확인
                if self.resource_manager.can_allocate(
                    job.cpu_requirement, 
                    job.memory_requirement
                ):
                    return job
                else:
                    # 리소스 부족 시 다시 큐에 넣기
                    heapq.heappush(self.job_queue, (neg_score, submit_time, job))
                    break
        
        return None
    
    def _execute_job(self, job: BatchJob) -> None:
        """작업 실행"""
        job_id = job.job_id
        
        try:
            # 리소스 할당
            if not self.resource_manager.allocate_resources(
                job_id, job.cpu_requirement, job.memory_requirement
            ):
                logger.warning(f"리소스 할당 실패: {job_id}")
                return
            
            # 작업 시작
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            
            with self.active_lock:
                self.active_jobs[job_id] = job
            
            logger.info(f"작업 시작: {job_id}")
            
            # 실제 작업 실행
            if job.task_function:
                start_time = time.time()
                job.result = job.task_function(*job.task_args, **job.task_kwargs)
                execution_time = time.time() - start_time
                
                job.execution_log.append(f"실행 완료: {execution_time:.2f}초")
            else:
                # 테스트용 더미 작업
                time.sleep(min(job.estimated_duration, 10))
                job.result = {"status": "success", "message": "더미 작업 완료"}
            
            # 작업 완료
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            self.stats['total_completed'] += 1
            
            logger.info(f"작업 완료: {job_id}")
        
        except Exception as e:
            # 작업 실패 처리
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()
            self.stats['total_failed'] += 1
            
            logger.error(f"작업 실패: {job_id} - {e}")
            
            # 재시도 로직
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = JobStatus.RETRYING
                
                # 재시도 작업을 큐에 다시 추가
                time.sleep(job.retry_delay)
                with self.queue_lock:
                    business_value = self.business_analyzer.calculate_business_value(job)
                    heapq.heappush(self.job_queue, (-business_value, time.time(), job))
                
                logger.info(f"작업 재시도 예약: {job_id} ({job.retry_count}/{job.max_retries})")
        
        finally:
            # 리소스 해제
            self.resource_manager.release_resources(job_id)
            
            # 활성 작업에서 제거
            with self.active_lock:
                if job_id in self.active_jobs:
                    completed_job = self.active_jobs.pop(job_id)
                    self.completed_jobs.append(completed_job)
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """스케줄러 통계"""
        with self.queue_lock:
            queue_size = len(self.job_queue)
        
        with self.active_lock:
            active_count = len(self.active_jobs)
        
        return {
            **self.stats,
            'queue_size': queue_size,
            'active_jobs': active_count,
            'completed_jobs': len(self.completed_jobs),
            'workers_running': self.workers_running,
            'max_concurrent_jobs': self.max_concurrent_jobs
        }

# ===== 통합 매니저 (Facade Pattern) =====

class StrategicBatchManager:
    """전략적 배치 작업 관리자 - 통합 인터페이스"""
    
    def __init__(self):
        # 컴포넌트 초기화
        self.resource_manager = SystemResourceManager()
        self.business_analyzer = BusinessValueAnalyzer()
        self.scheduler = PriorityJobScheduler(
            self.resource_manager, 
            self.business_analyzer
        )
        
        # 모니터링
        self.monitoring_enabled = True
        self.monitoring_interval = 30  # 30초마다 모니터링
        self.monitoring_thread: Optional[threading.Thread] = None
        
        # 알림 설정
        self.alert_thresholds = {
            'queue_size': 100,
            'failure_rate': 0.1,  # 10%
            'resource_usage': 0.9  # 90%
        }
        
        logger.info("전략적 배치 관리자 초기화 완료")
    
    def start(self) -> None:
        """배치 매니저 시작"""
        self.scheduler.start_workers()
        self._start_monitoring()
        logger.info("전략적 배치 관리자 시작됨")
    
    def stop(self) -> None:
        """배치 매니저 정지"""
        self.monitoring_enabled = False
        self.scheduler.stop_workers()
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        
        logger.info("전략적 배치 관리자 정지됨")
    
    def submit_job(
        self,
        job_type: JobType,
        priority: JobPriority,
        task_function: Callable = None,
        description: str = "",
        customer_id: Optional[str] = None,
        revenue_impact: float = 0.0,
        customer_count: int = 0,
        sla_deadline: Optional[datetime] = None,
        **kwargs
    ) -> str:
        """작업 제출 (간소화된 인터페이스)"""
        
        # 비즈니스 메트릭 구성
        business_metrics = BusinessMetrics(
            revenue_impact=revenue_impact,
            customer_count=customer_count,
            sla_deadline=sla_deadline,
            processing_cost=kwargs.get('processing_cost', 10.0)  # 기본 비용
        )
        
        # 배치 작업 생성
        job = BatchJob(
            job_id=kwargs.get('job_id', ''),
            job_type=job_type,
            priority=priority,
            task_function=task_function,
            task_args=kwargs.get('task_args', ()),
            task_kwargs=kwargs.get('task_kwargs', {}),
            business_metrics=business_metrics,
            description=description,
            customer_id=customer_id,
            estimated_duration=kwargs.get('estimated_duration', 300),
            cpu_requirement=kwargs.get('cpu_requirement', 1.0),
            memory_requirement=kwargs.get('memory_requirement', 512)
        )
        
        return self.scheduler.submit_job(job)
    
    def get_business_dashboard(self) -> Dict[str, Any]:
        """비즈니스 대시보드 데이터"""
        # 스케줄러 통계
        scheduler_stats = self.scheduler.get_scheduler_stats()
        
        # 리소스 통계
        resource_stats = self.resource_manager.get_resource_stats()
        
        # ROI 분석
        roi_analysis = self.business_analyzer.get_roi_analysis(
            self.scheduler.completed_jobs
        )
        
        # 실시간 상태
        current_time = datetime.now()
        active_jobs_info = []
        
        with self.scheduler.active_lock:
            for job in self.scheduler.active_jobs.values():
                runtime = (current_time - job.started_at).total_seconds() if job.started_at else 0
                progress = min(runtime / job.estimated_duration, 1.0) * 100
                
                active_jobs_info.append({
                    'job_id': job.job_id,
                    'type': job.job_type.value,
                    'priority': job.priority.value,
                    'progress_percent': round(progress, 1),
                    'customer_id': job.customer_id,
                    'revenue_impact': job.business_metrics.revenue_impact,
                    'runtime_minutes': round(runtime / 60, 1)
                })
        
        return {
            'timestamp': current_time.isoformat(),
            'scheduler_stats': scheduler_stats,
            'resource_stats': resource_stats,
            'roi_analysis': roi_analysis,
            'active_jobs': active_jobs_info,
            'system_health': self._get_system_health(),
            'alerts': self._check_alerts()
        }
    
    def _start_monitoring(self) -> None:
        """모니터링 시작"""
        def monitoring_loop():
            while self.monitoring_enabled:
                try:
                    self._collect_metrics()
                    time.sleep(self.monitoring_interval)
                except Exception as e:
                    logger.error(f"모니터링 오류: {e}")
        
        self.monitoring_thread = threading.Thread(
            target=monitoring_loop, 
            name="BatchMonitor",
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info("배치 모니터링 시작됨")
    
    def _collect_metrics(self) -> None:
        """메트릭 수집"""
        try:
            stats = self.scheduler.get_scheduler_stats()
            resource_stats = self.resource_manager.get_resource_stats()
            
            # 간단한 로깅 (실제로는 메트릭 저장소에 저장)
            logger.debug(f"배치 통계: 대기={stats['queue_size']}, "
                        f"실행중={stats['active_jobs']}, "
                        f"CPU={resource_stats.get('system_cpu_percent', 0):.1f}%, "
                        f"메모리={resource_stats.get('system_memory_percent', 0):.1f}%")
        
        except Exception as e:
            logger.error(f"메트릭 수집 실패: {e}")
    
    def _get_system_health(self) -> str:
        """시스템 건강 상태"""
        try:
            resource_stats = self.resource_manager.get_resource_stats()
            scheduler_stats = self.scheduler.get_scheduler_stats()
            
            cpu_usage = resource_stats.get('system_cpu_percent', 0)
            memory_usage = resource_stats.get('system_memory_percent', 0)
            queue_size = scheduler_stats['queue_size']
            
            if cpu_usage > 90 or memory_usage > 90:
                return "critical"
            elif queue_size > 50 or cpu_usage > 80 or memory_usage > 80:
                return "warning"
            else:
                return "healthy"
        
        except Exception:
            return "unknown"
    
    def _check_alerts(self) -> List[Dict[str, Any]]:
        """알림 확인"""
        alerts = []
        
        try:
            resource_stats = self.resource_manager.get_resource_stats()
            scheduler_stats = self.scheduler.get_scheduler_stats()
            
            # 큐 크기 알림
            if scheduler_stats['queue_size'] > self.alert_thresholds['queue_size']:
                alerts.append({
                    'type': 'queue_overload',
                    'severity': 'warning',
                    'message': f"작업 대기열 과부하: {scheduler_stats['queue_size']}개 작업 대기 중",
                    'value': scheduler_stats['queue_size']
                })
            
            # 실패율 알림
            total_jobs = scheduler_stats['total_completed'] + scheduler_stats['total_failed']
            if total_jobs > 0:
                failure_rate = scheduler_stats['total_failed'] / total_jobs
                if failure_rate > self.alert_thresholds['failure_rate']:
                    alerts.append({
                        'type': 'high_failure_rate',
                        'severity': 'critical',
                        'message': f"높은 실패율: {failure_rate*100:.1f}%",
                        'value': failure_rate
                    })
            
            # 리소스 사용률 알림
            cpu_usage = resource_stats.get('system_cpu_percent', 0) / 100
            memory_usage = resource_stats.get('system_memory_percent', 0) / 100
            
            if cpu_usage > self.alert_thresholds['resource_usage']:
                alerts.append({
                    'type': 'high_cpu_usage',
                    'severity': 'warning',
                    'message': f"높은 CPU 사용률: {cpu_usage*100:.1f}%",
                    'value': cpu_usage
                })
            
            if memory_usage > self.alert_thresholds['resource_usage']:
                alerts.append({
                    'type': 'high_memory_usage',
                    'severity': 'warning',
                    'message': f"높은 메모리 사용률: {memory_usage*100:.1f}%",
                    'value': memory_usage
                })
        
        except Exception as e:
            logger.error(f"알림 확인 실패: {e}")
        
        return alerts

# ===== 전역 인스턴스 =====

_global_batch_manager: Optional[StrategicBatchManager] = None

def get_batch_manager() -> StrategicBatchManager:
    """전역 배치 관리자 인스턴스 반환"""
    global _global_batch_manager
    
    if _global_batch_manager is None:
        _global_batch_manager = StrategicBatchManager()
    
    return _global_batch_manager

def shutdown_batch_manager() -> None:
    """전역 배치 관리자 종료"""
    global _global_batch_manager
    
    if _global_batch_manager is not None:
        _global_batch_manager.stop()
        _global_batch_manager = None