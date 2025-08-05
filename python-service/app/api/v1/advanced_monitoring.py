"""
고급 모니터링 API 엔드포인트
실시간 작업 상태, 메트릭, 알림 관리
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
import logging
import json

from app.services.advanced_monitoring_service import (
    get_monitoring_service,
    AlertSeverity,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 요청/응답 모델 =====


class AlertAcknowledgeRequest(BaseModel):
    """알림 확인 요청"""

    alert_id: str


class JobProgressUpdateRequest(BaseModel):
    """작업 진행률 업데이트 요청"""

    job_id: str
    progress_percent: float
    current_stage: Optional[str] = None
    stages_completed: Optional[int] = None
    total_stages: Optional[int] = None
    error_message: Optional[str] = None
    warning_message: Optional[str] = None


# ===== 모니터링 서비스 초기화 =====

monitoring_service = get_monitoring_service()


@router.on_event("startup")
async def startup_monitoring():
    """API 시작 시 모니터링 서비스 시작"""
    try:
        monitoring_service.start_monitoring()
        logger.info("고급 모니터링 서비스 API 시작됨")
    except Exception as e:
        logger.error(f"모니터링 서비스 시작 실패: {e}")


@router.on_event("shutdown")
async def shutdown_monitoring():
    """API 종료 시 모니터링 서비스 정지"""
    try:
        monitoring_service.stop_monitoring()
        logger.info("고급 모니터링 서비스 API 종료됨")
    except Exception as e:
        logger.error(f"모니터링 서비스 종료 실패: {e}")


# ===== WebSocket 엔드포인트 =====


@router.websocket("/real-time")
async def websocket_monitoring(websocket: WebSocket):
    """
    실시간 모니터링 데이터 WebSocket
    클라이언트에게 실시간으로 알림과 메트릭을 전송합니다.
    """
    await websocket.accept()

    # WebSocket 알림 핸들러에 클라이언트 추가
    ws_handler = monitoring_service.get_websocket_handler()
    if ws_handler:
        ws_handler.add_client(websocket)

    try:
        # 초기 대시보드 데이터 전송
        initial_data = monitoring_service.get_monitoring_dashboard()
        await websocket.send_text(
            json.dumps({"type": "dashboard", "data": initial_data})
        )

        # 클라이언트 메시지 처리 (ping/pong, 설정 변경 등)
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)

                if data.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps(
                            {"type": "pong", "timestamp": datetime.now().isoformat()}
                        )
                    )

                elif data.get("type") == "request_dashboard":
                    dashboard_data = monitoring_service.get_monitoring_dashboard()
                    await websocket.send_text(
                        json.dumps({"type": "dashboard", "data": dashboard_data})
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket 메시지 처리 오류: {e}")
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket 연결 오류: {e}")

    finally:
        # 클라이언트 제거
        if ws_handler:
            ws_handler.remove_client(websocket)


# ===== REST API 엔드포인트 =====


@router.get("/dashboard")
async def get_monitoring_dashboard() -> Dict[str, Any]:
    """
    모니터링 대시보드 데이터 조회
    전체 시스템 상태, 메트릭, 알림 정보를 제공합니다.
    """
    try:
        dashboard_data = monitoring_service.get_monitoring_dashboard()

        return {"success": True, "data": dashboard_data}

    except Exception as e:
        logger.error(f"대시보드 데이터 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"대시보드 데이터 조회 실패: {str(e)}"
        )


@router.get("/metrics/{metric_name}/history")
async def get_metric_history(
    metric_name: str, minutes: int = Query(60, description="조회할 기간 (분)")
) -> Dict[str, Any]:
    """특정 메트릭의 히스토리 조회"""
    try:
        if minutes > 1440:  # 최대 24시간
            raise HTTPException(
                status_code=400, detail="최대 1440분(24시간)까지 조회 가능합니다"
            )

        history = monitoring_service.get_metric_history(metric_name, minutes)

        return {
            "success": True,
            "data": {
                "metric_name": metric_name,
                "period_minutes": minutes,
                "data_points": len(history),
                "history": history,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"메트릭 히스토리 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"메트릭 히스토리 조회 실패: {str(e)}"
        )


@router.get("/alerts")
async def get_alerts(
    active_only: bool = Query(False, description="활성 알림만 조회")
) -> Dict[str, Any]:
    """알림 목록 조회"""
    try:
        if active_only:
            alerts = [
                alert.to_dict() for alert in monitoring_service.active_alerts.values()
            ]
            total_count = len(alerts)
        else:
            # 최근 50개 알림
            alerts = [
                alert.to_dict()
                for alert in list(monitoring_service.alert_history)[-50:]
            ]
            total_count = len(monitoring_service.alert_history)

        return {
            "success": True,
            "data": {
                "alerts": alerts,
                "total_count": total_count,
                "active_count": len(monitoring_service.active_alerts),
                "showing": len(alerts),
            },
        }

    except Exception as e:
        logger.error(f"알림 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"알림 조회 실패: {str(e)}")


@router.post("/alerts/acknowledge")
async def acknowledge_alert(request: AlertAcknowledgeRequest) -> Dict[str, Any]:
    """알림 확인 처리"""
    try:
        success = monitoring_service.acknowledge_alert(request.alert_id)

        if success:
            return {
                "success": True,
                "message": "알림이 확인되었습니다",
                "alert_id": request.alert_id,
            }
        else:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"알림 확인 실패: {e}")
        raise HTTPException(status_code=500, detail=f"알림 확인 실패: {str(e)}")


@router.delete("/alerts/{alert_id}")
async def resolve_alert(alert_id: str) -> Dict[str, Any]:
    """알림 해결 처리"""
    try:
        success = monitoring_service.resolve_alert(alert_id)

        if success:
            return {
                "success": True,
                "message": "알림이 해결되었습니다",
                "alert_id": alert_id,
            }
        else:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"알림 해결 실패: {e}")
        raise HTTPException(status_code=500, detail=f"알림 해결 실패: {str(e)}")


@router.get("/job-progress")
async def get_all_job_progress() -> Dict[str, Any]:
    """모든 활성 작업의 진행률 조회"""
    try:
        active_progress = monitoring_service.progress_tracker.get_all_active_progress()

        return {
            "success": True,
            "data": {
                "active_jobs": [progress.to_dict() for progress in active_progress],
                "total_count": len(active_progress),
            },
        }

    except Exception as e:
        logger.error(f"작업 진행률 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"작업 진행률 조회 실패: {str(e)}")


@router.get("/job-progress/{job_id}")
async def get_job_progress(job_id: str) -> Dict[str, Any]:
    """특정 작업의 진행률 조회"""
    try:
        progress = monitoring_service.progress_tracker.get_job_progress(job_id)

        if progress:
            return {"success": True, "data": progress.to_dict()}
        else:
            raise HTTPException(
                status_code=404, detail="작업 진행률 정보를 찾을 수 없습니다"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 진행률 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"작업 진행률 조회 실패: {str(e)}")


@router.post("/job-progress/update")
async def update_job_progress(request: JobProgressUpdateRequest) -> Dict[str, Any]:
    """
    작업 진행률 업데이트
    외부 시스템이나 작업 자체에서 진행률을 업데이트할 때 사용합니다.
    """
    try:
        monitoring_service.progress_tracker.update_job_progress(
            job_id=request.job_id,
            progress_percent=request.progress_percent,
            current_stage=request.current_stage or "",
            stages_completed=request.stages_completed or 0,
            total_stages=request.total_stages or 1,
            error_message=request.error_message or "",
            warning_message=request.warning_message or "",
        )

        return {
            "success": True,
            "message": "작업 진행률이 업데이트되었습니다",
            "job_id": request.job_id,
        }

    except Exception as e:
        logger.error(f"작업 진행률 업데이트 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"작업 진행률 업데이트 실패: {str(e)}"
        )


@router.get("/system-health")
async def get_system_health() -> Dict[str, Any]:
    """시스템 건강 상태 간단 조회"""
    try:
        dashboard_data = monitoring_service.get_monitoring_dashboard()
        system_summary = dashboard_data["system_summary"]

        # 건강 상태별 권장사항
        recommendations = []
        health_status = system_summary["overall_health"]

        if health_status == "critical":
            recommendations.extend(
                [
                    "즉시 시스템 점검이 필요합니다",
                    "실행 중인 작업을 일시 중단하는 것을 고려하세요",
                    "시스템 관리자에게 연락하세요",
                ]
            )
        elif health_status == "warning":
            recommendations.extend(
                [
                    "시스템 상태를 주의 깊게 모니터링하세요",
                    "새 작업 제출을 제한하는 것을 고려하세요",
                    "리소스 사용량을 확인하세요",
                ]
            )
        else:
            recommendations.append("시스템이 정상적으로 작동하고 있습니다")

        return {
            "success": True,
            "data": {
                "overall_health": health_status,
                "cpu_usage_percent": system_summary["cpu_usage"],
                "memory_usage_percent": system_summary["memory_usage"],
                "active_jobs": system_summary["active_jobs"],
                "queue_size": system_summary["queue_size"],
                "success_rate_percent": system_summary["success_rate"],
                "active_alerts_count": len(monitoring_service.active_alerts),
                "recommendations": recommendations,
            },
        }

    except Exception as e:
        logger.error(f"시스템 건강 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"시스템 건강 상태 조회 실패: {str(e)}"
        )


@router.get("/performance-summary")
async def get_performance_summary(
    hours: int = Query(1, description="조회할 시간 (시간)")
) -> Dict[str, Any]:
    """성능 요약 정보"""
    try:
        if hours > 24:
            raise HTTPException(
                status_code=400, detail="최대 24시간까지 조회 가능합니다"
            )

        minutes = hours * 60

        # 주요 메트릭의 히스토리 조회
        metrics_to_check = [
            "system.cpu.usage",
            "system.memory.usage",
            "batch.active.jobs",
            "batch.queue.size",
            "batch.success.rate",
        ]

        metric_summaries = {}
        for metric_name in metrics_to_check:
            history = monitoring_service.get_metric_history(metric_name, minutes)

            if history:
                values = [item["value"] for item in history]
                metric_summaries[metric_name] = {
                    "current": values[-1] if values else 0,
                    "average": sum(values) / len(values),
                    "minimum": min(values),
                    "maximum": max(values),
                    "data_points": len(values),
                }

        # 알림 요약
        alert_summary = {
            "total_alerts": len(monitoring_service.alert_history),
            "active_alerts": len(monitoring_service.active_alerts),
            "critical_alerts": len(
                [
                    alert
                    for alert in monitoring_service.active_alerts.values()
                    if alert.severity == AlertSeverity.CRITICAL
                ]
            ),
        }

        return {
            "success": True,
            "data": {
                "period_hours": hours,
                "metric_summaries": metric_summaries,
                "alert_summary": alert_summary,
                "monitoring_status": {
                    "enabled": monitoring_service.monitoring_enabled,
                    "interval_seconds": monitoring_service.monitoring_interval,
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"성능 요약 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"성능 요약 조회 실패: {str(e)}")


@router.post("/monitoring/restart")
async def restart_monitoring() -> Dict[str, Any]:
    """모니터링 서비스 재시작"""
    try:
        monitoring_service.stop_monitoring()
        monitoring_service.start_monitoring()

        return {"success": True, "message": "모니터링 서비스가 재시작되었습니다"}

    except Exception as e:
        logger.error(f"모니터링 재시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"모니터링 재시작 실패: {str(e)}")


@router.get("/monitoring/status")
async def get_monitoring_status() -> Dict[str, Any]:
    """모니터링 서비스 상태 조회"""
    try:
        return {
            "success": True,
            "data": {
                "monitoring_enabled": monitoring_service.monitoring_enabled,
                "monitoring_interval": monitoring_service.monitoring_interval,
                "alert_cooldown": monitoring_service.alert_cooldown,
                "total_metrics_collected": sum(
                    len(metrics)
                    for metrics in monitoring_service.metrics_history.values()
                ),
                "total_alerts_sent": len(monitoring_service.alert_history),
                "active_alerts": len(monitoring_service.active_alerts),
                "metric_collectors": len(monitoring_service.metric_collectors),
                "alert_handlers": len(monitoring_service.alert_handlers),
                "alert_thresholds": monitoring_service.alert_thresholds,
            },
        }

    except Exception as e:
        logger.error(f"모니터링 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"모니터링 상태 조회 실패: {str(e)}"
        )


# ===== 내부 함수 =====


def _format_alert_severity_icon(severity: AlertSeverity) -> str:
    """알림 심각도별 아이콘 반환"""
    icons = {
        AlertSeverity.INFO: "ℹ️",
        AlertSeverity.WARNING: "⚠️",
        AlertSeverity.CRITICAL: "🚨",
        AlertSeverity.EMERGENCY: "🔥",
    }
    return icons.get(severity, "📢")
