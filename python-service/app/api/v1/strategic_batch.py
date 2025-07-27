"""
전략적 배치 작업 관리 API
비즈니스 가치 중심의 배치 처리 및 모니터링 엔드포인트
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

from app.services.strategic_batch_manager import (
    get_batch_manager, 
    JobType, 
    JobPriority,
    JobStatus
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 요청/응답 모델 =====

class JobSubmissionRequest(BaseModel):
    """작업 제출 요청"""
    job_type: str = Field(..., description="작업 유형 (customer_data, financial_report, ocr_processing, data_migration, system_maintenance)")
    priority: str = Field(..., description="우선순위 (CRITICAL, HIGH, NORMAL, LOW)")
    description: str = Field("", description="작업 설명")
    customer_id: Optional[str] = Field(None, description="고객 ID")
    
    # 비즈니스 메트릭
    revenue_impact: float = Field(0.0, description="매출 영향도 (USD)")
    customer_count: int = Field(0, description="영향받는 고객 수")
    processing_cost: float = Field(10.0, description="처리 비용 (USD)")
    sla_hours: Optional[int] = Field(None, description="SLA 마감 시간 (시간)")
    
    # 리소스 요구사항
    estimated_duration_minutes: int = Field(5, description="예상 소요시간 (분)")
    cpu_requirement: float = Field(1.0, description="CPU 요구사항 (코어)")
    memory_requirement: int = Field(512, description="메모리 요구사항 (MB)")

class JobStatusResponse(BaseModel):
    """작업 상태 응답"""
    job_id: str
    status: str
    progress_percent: Optional[float] = None
    error_message: Optional[str] = None

class BusinessDashboardResponse(BaseModel):
    """비즈니스 대시보드 응답"""
    timestamp: str
    system_health: str
    total_jobs: Dict[str, int]
    resource_usage: Dict[str, float]
    roi_metrics: Dict[str, Any]
    active_jobs: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]

# ===== 배치 매니저 초기화 =====

batch_manager = get_batch_manager()

@router.on_event("startup")
async def startup_batch_manager():
    """API 시작 시 배치 매니저 시작"""
    try:
        batch_manager.start()
        logger.info("전략적 배치 매니저 API 시작됨")
    except Exception as e:
        logger.error(f"배치 매니저 시작 실패: {e}")

@router.on_event("shutdown")
async def shutdown_batch_manager():
    """API 종료 시 배치 매니저 정지"""
    try:
        batch_manager.stop()
        logger.info("전략적 배치 매니저 API 종료됨")
    except Exception as e:
        logger.error(f"배치 매니저 종료 실패: {e}")

# ===== API 엔드포인트 =====

@router.post("/submit-job")
async def submit_batch_job(request: JobSubmissionRequest) -> Dict[str, Any]:
    """
    배치 작업 제출
    비즈니스 가치를 기반으로 우선순위가 자동 계산됩니다.
    """
    try:
        # 작업 유형 검증
        try:
            job_type = JobType(request.job_type)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"유효하지 않은 작업 유형: {request.job_type}"
            )
        
        # 우선순위 검증
        try:
            priority = JobPriority[request.priority]
        except KeyError:
            raise HTTPException(
                status_code=400, 
                detail=f"유효하지 않은 우선순위: {request.priority}"
            )
        
        # SLA 마감시간 계산
        sla_deadline = None
        if request.sla_hours:
            sla_deadline = datetime.now() + timedelta(hours=request.sla_hours)
        
        # 작업 제출
        job_id = batch_manager.submit_job(
            job_type=job_type,
            priority=priority,
            description=request.description,
            customer_id=request.customer_id,
            revenue_impact=request.revenue_impact,
            customer_count=request.customer_count,
            processing_cost=request.processing_cost,
            sla_deadline=sla_deadline,
            estimated_duration=request.estimated_duration_minutes * 60,
            cpu_requirement=request.cpu_requirement,
            memory_requirement=request.memory_requirement
        )
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "작업이 성공적으로 제출되었습니다",
            "estimated_completion": (
                datetime.now() + timedelta(minutes=request.estimated_duration_minutes)
            ).isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 제출 실패: {e}")
        raise HTTPException(status_code=500, detail=f"작업 제출 실패: {str(e)}")

@router.get("/job-status/{job_id}")
async def get_job_status(job_id: str) -> JobStatusResponse:
    """특정 작업의 상태 조회"""
    try:
        status = batch_manager.scheduler.get_job_status(job_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        # 작업 세부 정보 가져오기
        job = batch_manager.scheduler.job_history.get(job_id)
        progress_percent = None
        error_message = None
        
        if job:
            if job.status == JobStatus.RUNNING and job.started_at:
                runtime = (datetime.now() - job.started_at).total_seconds()
                progress_percent = min(runtime / job.estimated_duration, 1.0) * 100
            
            error_message = job.error_message if job.error_message else None
        
        return JobStatusResponse(
            job_id=job_id,
            status=status.value,
            progress_percent=progress_percent,
            error_message=error_message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"상태 조회 실패: {str(e)}")

@router.delete("/cancel-job/{job_id}")
async def cancel_job(job_id: str) -> Dict[str, Any]:
    """작업 취소"""
    try:
        success = batch_manager.scheduler.cancel_job(job_id)
        
        if success:
            return {
                "success": True,
                "message": "작업이 취소되었습니다",
                "job_id": job_id
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail="작업을 취소할 수 없습니다 (이미 실행 중이거나 완료됨)"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 취소 실패: {e}")
        raise HTTPException(status_code=500, detail=f"작업 취소 실패: {str(e)}")

@router.get("/business-dashboard")
async def get_business_dashboard() -> Dict[str, Any]:
    """
    비즈니스 대시보드 데이터
    전반적인 배치 처리 현황과 비즈니스 메트릭을 제공합니다.
    """
    try:
        dashboard_data = batch_manager.get_business_dashboard()
        
        # 응답 데이터 포맷팅
        return {
            "success": True,
            "data": dashboard_data,
            "summary": {
                "system_health": dashboard_data["system_health"],
                "total_jobs_in_queue": dashboard_data["scheduler_stats"]["queue_size"],
                "active_jobs_count": dashboard_data["scheduler_stats"]["active_jobs"],
                "total_completed": dashboard_data["scheduler_stats"]["total_completed"],
                "cpu_usage_percent": dashboard_data["resource_stats"].get("system_cpu_percent", 0),
                "memory_usage_percent": dashboard_data["resource_stats"].get("system_memory_percent", 0),
                "alerts_count": len(dashboard_data["alerts"])
            }
        }
    
    except Exception as e:
        logger.error(f"대시보드 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"대시보드 데이터 조회 실패: {str(e)}")

@router.get("/active-jobs")
async def get_active_jobs() -> Dict[str, Any]:
    """현재 실행 중인 작업 목록"""
    try:
        active_jobs = []
        
        with batch_manager.scheduler.active_lock:
            current_time = datetime.now()
            
            for job in batch_manager.scheduler.active_jobs.values():
                runtime = (current_time - job.started_at).total_seconds() if job.started_at else 0
                progress = min(runtime / job.estimated_duration, 1.0) * 100
                
                active_jobs.append({
                    "job_id": job.job_id,
                    "job_type": job.job_type.value,
                    "priority": job.priority.value,
                    "description": job.description,
                    "customer_id": job.customer_id,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "runtime_minutes": round(runtime / 60, 1),
                    "progress_percent": round(progress, 1),
                    "estimated_completion": (
                        job.started_at + timedelta(seconds=job.estimated_duration)
                    ).isoformat() if job.started_at else None,
                    "business_metrics": {
                        "revenue_impact": job.business_metrics.revenue_impact,
                        "customer_count": job.business_metrics.customer_count,
                        "business_value_score": job.business_metrics.business_value_score
                    }
                })
        
        return {
            "success": True,
            "active_jobs": active_jobs,
            "total_count": len(active_jobs)
        }
    
    except Exception as e:
        logger.error(f"활성 작업 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"활성 작업 조회 실패: {str(e)}")

@router.get("/job-queue")
async def get_job_queue(limit: int = Query(20, description="조회할 작업 수")) -> Dict[str, Any]:
    """대기 중인 작업 큐 상태"""
    try:
        queue_jobs = []
        
        with batch_manager.scheduler.queue_lock:
            # 힙에서 상위 N개 작업 정보 추출 (실제로는 제거하지 않음)
            temp_queue = batch_manager.scheduler.job_queue.copy()
            
            for i in range(min(limit, len(temp_queue))):
                if temp_queue:
                    neg_score, submit_time, job = temp_queue[i]
                    business_score = -neg_score
                    
                    if job.status != JobStatus.CANCELLED:
                        queue_jobs.append({
                            "job_id": job.job_id,
                            "job_type": job.job_type.value,
                            "priority": job.priority.value,
                            "business_score": round(business_score, 2),
                            "description": job.description,
                            "customer_id": job.customer_id,
                            "submitted_at": datetime.fromtimestamp(submit_time).isoformat(),
                            "estimated_duration_minutes": job.estimated_duration / 60,
                            "is_urgent": job.is_urgent,
                            "business_metrics": {
                                "revenue_impact": job.business_metrics.revenue_impact,
                                "customer_count": job.business_metrics.customer_count,
                                "roi_potential": job.business_metrics.roi_potential
                            }
                        })
        
        return {
            "success": True,
            "queue_jobs": sorted(queue_jobs, key=lambda x: x["business_score"], reverse=True),
            "total_in_queue": len(batch_manager.scheduler.job_queue),
            "showing": len(queue_jobs)
        }
    
    except Exception as e:
        logger.error(f"작업 큐 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"작업 큐 조회 실패: {str(e)}")

@router.get("/roi-analysis")
async def get_roi_analysis() -> Dict[str, Any]:
    """ROI 분석 보고서"""
    try:
        roi_analysis = batch_manager.business_analyzer.get_roi_analysis(
            batch_manager.scheduler.completed_jobs
        )
        
        if roi_analysis.get("status") == "no_data":
            return {
                "success": True,
                "message": "분석할 완료된 작업이 없습니다",
                "data": {
                    "total_completed_jobs": 0,
                    "overall_roi": 0,
                    "total_revenue_impact": 0,
                    "total_processing_cost": 0
                }
            }
        
        return {
            "success": True,
            "data": roi_analysis,
            "insights": _generate_roi_insights(roi_analysis)
        }
    
    except Exception as e:
        logger.error(f"ROI 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"ROI 분석 실패: {str(e)}")

@router.get("/system-health")
async def get_system_health() -> Dict[str, Any]:
    """시스템 건강 상태 및 리소스 사용량"""
    try:
        resource_stats = batch_manager.resource_manager.get_resource_stats()
        scheduler_stats = batch_manager.scheduler.get_scheduler_stats()
        system_health = batch_manager._get_system_health()
        alerts = batch_manager._check_alerts()
        
        return {
            "success": True,
            "health_status": system_health,
            "resource_usage": {
                "cpu_percent": resource_stats.get("system_cpu_percent", 0),
                "memory_percent": resource_stats.get("system_memory_percent", 0),
                "available_cpu_cores": resource_stats.get("available_cpu_cores", 0),
                "available_memory_gb": resource_stats.get("available_memory_gb", 0),
                "allocated_jobs": resource_stats.get("active_jobs", 0)
            },
            "scheduler_status": {
                "workers_running": scheduler_stats["workers_running"],
                "max_concurrent_jobs": scheduler_stats["max_concurrent_jobs"],
                "queue_size": scheduler_stats["queue_size"],
                "active_jobs": scheduler_stats["active_jobs"]
            },
            "alerts": alerts,
            "recommendations": _generate_system_recommendations(resource_stats, scheduler_stats, alerts)
        }
    
    except Exception as e:
        logger.error(f"시스템 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"시스템 상태 조회 실패: {str(e)}")

@router.post("/demo-jobs")
async def create_demo_jobs() -> Dict[str, Any]:
    """
    데모용 샘플 작업 생성
    다양한 작업 유형과 우선순위로 테스트 작업을 생성합니다.
    """
    try:
        demo_jobs = [
            {
                "job_type": JobType.CUSTOMER_DATA,
                "priority": JobPriority.CRITICAL,
                "description": "고급 고객 데이터 처리",
                "revenue_impact": 5000.0,
                "customer_count": 100,
                "sla_deadline": datetime.now() + timedelta(hours=1)
            },
            {
                "job_type": JobType.FINANCIAL_REPORT,
                "priority": JobPriority.HIGH,
                "description": "월간 재무 보고서 생성",
                "revenue_impact": 2000.0,
                "customer_count": 10,
                "sla_deadline": datetime.now() + timedelta(hours=4)
            },
            {
                "job_type": JobType.OCR_PROCESSING,
                "priority": JobPriority.NORMAL,
                "description": "문서 OCR 배치 처리",
                "revenue_impact": 500.0,
                "customer_count": 50
            },
            {
                "job_type": JobType.DATA_MIGRATION,
                "priority": JobPriority.LOW,
                "description": "레거시 데이터 이관",
                "revenue_impact": 100.0,
                "customer_count": 5
            },
            {
                "job_type": JobType.SYSTEM_MAINTENANCE,
                "priority": JobPriority.LOW,
                "description": "시스템 정리 및 최적화",
                "revenue_impact": 0.0,
                "customer_count": 0
            }
        ]
        
        created_jobs = []
        for demo_job in demo_jobs:
            job_id = batch_manager.submit_job(**demo_job)
            created_jobs.append({
                "job_id": job_id,
                "description": demo_job["description"],
                "priority": demo_job["priority"].name
            })
        
        return {
            "success": True,
            "message": f"{len(created_jobs)}개의 데모 작업이 생성되었습니다",
            "created_jobs": created_jobs
        }
    
    except Exception as e:
        logger.error(f"데모 작업 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"데모 작업 생성 실패: {str(e)}")

# ===== 도우미 함수 =====

def _generate_roi_insights(roi_analysis: Dict[str, Any]) -> List[str]:
    """ROI 분석 인사이트 생성"""
    insights = []
    
    try:
        roi = roi_analysis.get("overall_roi", 0)
        success_rate = roi_analysis.get("success_rate_percent", 0)
        
        if roi > 5:
            insights.append("우수한 투자 수익률을 달성하고 있습니다.")
        elif roi > 2:
            insights.append("양호한 투자 수익률을 보이고 있습니다.")
        else:
            insights.append("투자 수익률 개선이 필요합니다.")
        
        if success_rate > 95:
            insights.append("작업 성공률이 매우 높습니다.")
        elif success_rate > 85:
            insights.append("작업 성공률이 양호합니다.")
        else:
            insights.append("작업 실패율이 높아 원인 분석이 필요합니다.")
        
        # 작업 유형별 분석
        type_analysis = roi_analysis.get("type_analysis", {})
        if type_analysis:
            best_type = max(type_analysis.items(), key=lambda x: x[1].get("revenue", 0))
            insights.append(f"가장 높은 수익을 창출하는 작업 유형은 {best_type[0]}입니다.")
    
    except Exception as e:
        logger.warning(f"인사이트 생성 실패: {e}")
        insights.append("인사이트 분석 중 오류가 발생했습니다.")
    
    return insights

def _generate_system_recommendations(
    resource_stats: Dict[str, Any], 
    scheduler_stats: Dict[str, Any], 
    alerts: List[Dict[str, Any]]
) -> List[str]:
    """시스템 권장사항 생성"""
    recommendations = []
    
    try:
        cpu_usage = resource_stats.get("system_cpu_percent", 0)
        memory_usage = resource_stats.get("system_memory_percent", 0)
        queue_size = scheduler_stats.get("queue_size", 0)
        
        # 리소스 기반 권장사항
        if cpu_usage > 80:
            recommendations.append("CPU 사용률이 높습니다. 워커 수를 줄이거나 서버 리소스를 증설하세요.")
        
        if memory_usage > 80:
            recommendations.append("메모리 사용률이 높습니다. 메모리 집약적 작업을 분산하세요.")
        
        # 큐 기반 권장사항
        if queue_size > 50:
            recommendations.append("작업 대기열이 길어지고 있습니다. 워커 수를 늘리는 것을 고려하세요.")
        elif queue_size == 0:
            recommendations.append("모든 작업이 처리되었습니다. 시스템이 원활하게 작동 중입니다.")
        
        # 알림 기반 권장사항
        if len(alerts) > 3:
            recommendations.append("여러 알림이 발생했습니다. 시스템 상태를 점검하세요.")
        
        if not recommendations:
            recommendations.append("시스템이 최적 상태로 운영되고 있습니다.")
    
    except Exception as e:
        logger.warning(f"권장사항 생성 실패: {e}")
        recommendations.append("권장사항 생성 중 오류가 발생했습니다.")
    
    return recommendations