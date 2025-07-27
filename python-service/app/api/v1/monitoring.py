"""
실시간 모니터링 대시보드 API 엔드포인트

관리자용 실시간 모니터링 기능:
- 실시간 대시보드 HTML 제공
- 메트릭 API 데이터 제공  
- 과거 데이터 조회
- 모니터링 제어
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from app.services.real_time_monitoring_service import (
    get_monitoring_service,
    OCRMetricsCollector
)

# 라우터 생성
router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """
    실시간 모니터링 대시보드 HTML 페이지
    
    관리자용 대시보드로 다음 정보를 실시간으로 표시:
    - OCR 처리량 및 성공률
    - 시스템 리소스 사용량
    - 언어별 성능 통계
    - 실시간 알림
    """
    try:
        monitoring_service = get_monitoring_service()
        dashboard_html = await monitoring_service.get_current_dashboard()
        return HTMLResponse(content=dashboard_html)
    
    except Exception as e:
        logger.error(f"대시보드 생성 실패: {e}")
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>모니터링 오류</title></head>
        <body>
            <h1>모니터링 대시보드 오류</h1>
            <p>대시보드를 로드할 수 없습니다: {str(e)}</p>
            <p><a href="/api/v1/monitoring/dashboard">새로고침</a></p>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)

@router.get("/metrics")
async def get_current_metrics():
    """
    현재 시스템 메트릭 조회 (JSON API)
    
    Returns:
        Dict: OCR 메트릭, 시스템 메트릭, 타임스탬프
    """
    try:
        monitoring_service = get_monitoring_service()
        metrics = await monitoring_service.get_metrics_api()
        
        return JSONResponse(content={
            "success": True,
            "data": metrics,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"메트릭 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"메트릭 조회 실패: {str(e)}")

@router.get("/historical")
async def get_historical_metrics(
    hours: int = Query(default=1, ge=1, le=24, description="조회할 시간 범위 (시간)")
):
    """
    과거 메트릭 데이터 조회
    
    Args:
        hours: 조회할 시간 범위 (1-24시간)
    
    Returns:
        List[Dict]: 시간대별 메트릭 데이터
    """
    try:
        monitoring_service = get_monitoring_service()
        historical_data = await monitoring_service.get_historical_data(hours)
        
        return JSONResponse(content={
            "success": True,
            "data": historical_data,
            "hours": hours,
            "total_records": len(historical_data),
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"과거 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"과거 데이터 조회 실패: {str(e)}")

@router.post("/start")
async def start_monitoring(
    background_tasks: BackgroundTasks,
    interval_seconds: int = Query(default=30, ge=10, le=300, description="모니터링 간격 (초)")
):
    """
    실시간 모니터링 시작
    
    Args:
        interval_seconds: 모니터링 수집 간격 (10-300초)
    """
    try:
        monitoring_service = get_monitoring_service()
        background_tasks.add_task(monitoring_service.start_monitoring, interval_seconds)
        
        return JSONResponse(content={
            "success": True,
            "message": f"실시간 모니터링이 {interval_seconds}초 간격으로 시작되었습니다.",
            "interval_seconds": interval_seconds,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"모니터링 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"모니터링 시작 실패: {str(e)}")

@router.post("/stop")
async def stop_monitoring():
    """
    실시간 모니터링 중지
    """
    try:
        monitoring_service = get_monitoring_service()
        await monitoring_service.stop_monitoring()
        
        return JSONResponse(content={
            "success": True,
            "message": "실시간 모니터링이 중지되었습니다.",
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"모니터링 중지 실패: {e}")
        raise HTTPException(status_code=500, detail=f"모니터링 중지 실패: {str(e)}")

@router.get("/status")
async def get_monitoring_status():
    """
    모니터링 상태 확인
    
    Returns:
        Dict: 모니터링 활성 상태 및 기본 정보
    """
    try:
        monitoring_service = get_monitoring_service()
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "monitoring_active": monitoring_service.monitoring_active,
                "service_status": "running",
                "supported_metrics": [
                    "ocr_requests",
                    "success_rate", 
                    "processing_time",
                    "language_performance",
                    "cpu_usage",
                    "memory_usage",
                    "disk_usage",
                    "network_io"
                ]
            },
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"모니터링 상태 확인 실패: {e}")
        raise HTTPException(status_code=500, detail=f"모니터링 상태 확인 실패: {str(e)}")

@router.get("/languages")
async def get_language_statistics():
    """
    언어별 상세 통계 조회
    
    Returns:
        Dict: 각 언어별 처리 통계
    """
    try:
        monitoring_service = get_monitoring_service()
        
        # OCR 컬렉터에서 언어별 데이터 직접 조회
        if hasattr(monitoring_service.ocr_collector, 'language_data'):
            language_stats = dict(monitoring_service.ocr_collector.language_data)
        else:
            language_stats = {}
        
        # 통계 계산
        processed_stats = {}
        for lang, stats in language_stats.items():
            requests = stats.get('requests', 0)
            successes = stats.get('successes', 0)
            
            processed_stats[lang] = {
                "total_requests": requests,
                "successful_requests": successes,
                "failed_requests": requests - successes,
                "success_rate": (successes / requests * 100) if requests > 0 else 0.0,
                "average_processing_time": stats.get('avg_time', 0.0)
            }
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "language_statistics": processed_stats,
                "total_languages": len(processed_stats),
                "most_used_language": max(processed_stats.items(), key=lambda x: x[1]['total_requests'])[0] if processed_stats else None
            },
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"언어별 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"언어별 통계 조회 실패: {str(e)}")

@router.post("/record-request")
async def record_ocr_request(
    language: str,
    success: bool,
    processing_time: float
):
    """
    OCR 요청 결과 기록 (내부 API)
    
    OCR 처리 서비스에서 호출하여 모니터링 데이터에 기록
    
    Args:
        language: 처리 언어
        success: 성공 여부
        processing_time: 처리 시간 (초)
    """
    try:
        monitoring_service = get_monitoring_service()
        
        # OCR 컬렉터에 직접 기록
        if hasattr(monitoring_service.ocr_collector, 'record_request'):
            monitoring_service.ocr_collector.record_request(language, success, processing_time)
        
        return JSONResponse(content={
            "success": True,
            "message": "OCR 요청이 기록되었습니다.",
            "recorded": {
                "language": language,
                "success": success,
                "processing_time": processing_time
            },
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"OCR 요청 기록 실패: {e}")
        raise HTTPException(status_code=500, detail=f"OCR 요청 기록 실패: {str(e)}")

@router.get("/health")
async def monitoring_health_check():
    """
    모니터링 서비스 헬스 체크
    """
    try:
        monitoring_service = get_monitoring_service()
        
        # 기본 메트릭 수집 테스트
        test_metrics = await monitoring_service.get_metrics_api()
        
        return JSONResponse(content={
            "success": True,
            "status": "healthy",
            "service": "Real-time Monitoring Service",
            "version": "1.0.0",
            "features": [
                "실시간 대시보드",
                "메트릭 수집", 
                "임계값 알림",
                "언어별 통계",
                "시스템 모니터링"
            ],
            "test_result": "메트릭 수집 정상",
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"모니터링 헬스체크 실패: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )