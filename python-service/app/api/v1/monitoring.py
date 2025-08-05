"""
Monitoring API endpoints
모니터링 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

from app.core.monitoring import metrics_collector, system_monitor, alert_manager
from app.core.responses import ResponseBuilder
from app.services.rate_limiter import rate_limit, RateLimitTier

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics")
@rate_limit(tier=RateLimitTier.BASIC, endpoint="/api/v1/monitoring/metrics")
async def get_metrics(endpoint: Optional[str] = None) -> Dict[str, Any]:
    """
    메트릭 조회

    Args:
        endpoint: 특정 엔드포인트의 메트릭만 조회 (옵션)
    """
    try:
        stats = metrics_collector.get_stats(endpoint)

        return ResponseBuilder.success(
            data=stats, message="Metrics retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system")
@rate_limit(tier=RateLimitTier.BASIC, endpoint="/api/v1/monitoring/system")
async def get_system_metrics() -> Dict[str, Any]:
    """시스템 메트릭 조회"""
    try:
        metrics = system_monitor.get_system_metrics()

        return ResponseBuilder.success(
            data=metrics, message="System metrics retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
@rate_limit(tier=RateLimitTier.BASIC, endpoint="/api/v1/monitoring/alerts")
async def get_alerts() -> Dict[str, Any]:
    """활성 알림 조회"""
    try:
        alerts = alert_manager.get_active_alerts()

        return ResponseBuilder.success(
            data={"active_alerts": alerts, "count": len(alerts)},
            message="Alerts retrieved successfully",
        )
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/check")
@rate_limit(tier=RateLimitTier.ADMIN, endpoint="/api/v1/monitoring/alerts/check")
async def check_alerts() -> Dict[str, Any]:
    """수동 알림 체크 실행"""
    try:
        await alert_manager.check_and_alert()

        return ResponseBuilder.success(
            data={"checked": True}, message="Alert check completed"
        )
    except Exception as e:
        logger.error(f"Failed to check alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """상세 헬스 체크"""
    try:
        # 시스템 메트릭
        system_metrics = system_monitor.get_system_metrics()

        # API 통계
        api_stats = metrics_collector.get_stats()

        # 활성 알림
        alerts = alert_manager.get_active_alerts()

        # 헬스 상태 판단
        health_status = "healthy"
        issues = []

        # CPU 체크
        if system_metrics.get("cpu", {}).get("percent", 0) > 80:
            health_status = "degraded"
            issues.append("High CPU usage")

        # 메모리 체크
        if system_metrics.get("memory", {}).get("percent", 0) > 85:
            health_status = "degraded"
            issues.append("High memory usage")

        # 에러율 체크
        if api_stats.get("error_rate", 0) > 0.05:
            health_status = "unhealthy"
            issues.append("High error rate")

        # 활성 알림 체크
        if len(alerts) > 0:
            health_status = "degraded" if health_status == "healthy" else health_status
            issues.append(f"{len(alerts)} active alerts")

        return {
            "status": health_status,
            "issues": issues,
            "metrics": {
                "system": {
                    "cpu_percent": system_metrics.get("cpu", {}).get("percent", 0),
                    "memory_percent": system_metrics.get("memory", {}).get(
                        "percent", 0
                    ),
                    "disk_percent": system_metrics.get("disk", {}).get("percent", 0),
                },
                "api": {
                    "total_requests": api_stats.get("total_requests", 0),
                    "error_rate": api_stats.get("error_rate", 0),
                    "uptime_seconds": api_stats.get("uptime_seconds", 0),
                },
                "alerts": {
                    "active_count": len(alerts),
                    "critical_count": sum(
                        1 for a in alerts if a.get("severity") == "critical"
                    ),
                },
            },
            "timestamp": system_metrics.get("timestamp"),
        }

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {"status": "unknown", "error": str(e)}


@router.get("/dashboard")
@rate_limit(tier=RateLimitTier.BASIC, endpoint="/api/v1/monitoring/dashboard")
async def monitoring_dashboard() -> Dict[str, Any]:
    """모니터링 대시보드 데이터"""
    try:
        # 시스템 메트릭
        system_metrics = system_monitor.get_system_metrics()

        # API 통계
        api_stats = metrics_collector.get_stats()

        # 활성 알림
        alerts = alert_manager.get_active_alerts()

        # 상위 5개 엔드포인트 (요청 수 기준)
        top_endpoints = sorted(
            api_stats.get("endpoints", {}).items(),
            key=lambda x: x[1].get("count", 0),
            reverse=True,
        )[:5]

        # 상위 5개 느린 엔드포인트 (P99 기준)
        slow_endpoints = sorted(
            api_stats.get("endpoints", {}).items(),
            key=lambda x: x[1].get("p99", 0),
            reverse=True,
        )[:5]

        # 오류율 높은 엔드포인트
        error_endpoints = [
            (ep, stats)
            for ep, stats in api_stats.get("endpoints", {}).items()
            if stats.get("error_rate", 0) > 0.01
        ]

        dashboard_data = {
            "overview": {
                "status": "operational",
                "uptime_hours": api_stats.get("uptime_seconds", 0) / 3600,
                "total_requests": api_stats.get("total_requests", 0),
                "total_errors": api_stats.get("total_errors", 0),
                "error_rate": api_stats.get("error_rate", 0),
            },
            "system": {
                "cpu": system_metrics.get("cpu", {}),
                "memory": system_metrics.get("memory", {}),
                "disk": system_metrics.get("disk", {}),
                "process": system_metrics.get("process", {}),
            },
            "top_endpoints": [
                {
                    "endpoint": ep,
                    "requests": stats.get("count", 0),
                    "avg_time": stats.get("avg_time", 0),
                    "error_rate": stats.get("error_rate", 0),
                }
                for ep, stats in top_endpoints
            ],
            "slow_endpoints": [
                {
                    "endpoint": ep,
                    "p99": stats.get("p99", 0),
                    "p90": stats.get("p90", 0),
                    "avg_time": stats.get("avg_time", 0),
                }
                for ep, stats in slow_endpoints
            ],
            "error_endpoints": [
                {
                    "endpoint": ep,
                    "error_rate": stats.get("error_rate", 0),
                    "errors": stats.get("errors", 0),
                    "last_error": stats.get("last_error"),
                }
                for ep, stats in error_endpoints
            ],
            "alerts": {
                "active": len(alerts),
                "critical": sum(1 for a in alerts if a.get("severity") == "critical"),
                "warning": sum(1 for a in alerts if a.get("severity") == "warning"),
                "recent": alerts[:5],  # 최근 5개
            },
            "timestamp": system_metrics.get("timestamp"),
        }

        return ResponseBuilder.success(
            data=dashboard_data, message="Dashboard data retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        return ResponseBuilder.error(
            message="Failed to retrieve dashboard data",
            error_code="DASHBOARD_ERROR",
            details={"error": str(e)},
        )
