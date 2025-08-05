"""
Insights API endpoints
프로액티브 인사이트 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.services.insights import (
    get_pattern_analyzer,
    get_error_predictor,
    get_optimization_advisor,
    get_proactive_notifier,
    UserAction,
)
from app.services.context import get_enhanced_context_manager
from app.core.responses import ResponseBuilder

logger = logging.getLogger(__name__)

router = APIRouter()


class RecordActionRequest(BaseModel):
    """사용자 액션 기록 요청"""

    session_id: str
    action_type: str
    target: str
    details: Optional[Dict[str, Any]] = None


class GetInsightsRequest(BaseModel):
    """인사이트 조회 요청"""

    session_id: str
    insight_types: Optional[List[str]] = None  # patterns, predictions, optimizations


class NotificationActionRequest(BaseModel):
    """알림 액션 요청"""

    session_id: str
    notification_id: str
    action: str  # read, dismiss, snooze


@router.post("/record-action")
async def record_user_action(request: RecordActionRequest) -> Dict[str, Any]:
    """
    사용자 액션 기록
    패턴 분석을 위한 사용자 행동 추적
    """
    try:
        pattern_analyzer = get_pattern_analyzer()

        # UserAction 생성
        action = UserAction(
            timestamp=datetime.now(),
            action_type=request.action_type,
            target=request.target,
            details=request.details or {},
            session_id=request.session_id,
        )

        # 액션 기록
        pattern_analyzer.record_action(request.session_id, action)

        return ResponseBuilder.success(
            data={"timestamp": action.timestamp.isoformat()},
            message="액션이 기록되었습니다",
        )

    except Exception as e:
        logger.error(f"액션 기록 실패: {str(e)}")
        error_response = ResponseBuilder.from_exception(e)
        raise HTTPException(status_code=500, detail=error_response)


@router.post("/get-insights")
async def get_proactive_insights(request: GetInsightsRequest) -> Dict[str, Any]:
    """
    프로액티브 인사이트 조회
    패턴, 예측, 최적화 제안 등을 한번에 조회
    """
    try:
        # 컨텍스트 가져오기
        context_manager = get_enhanced_context_manager()
        enhanced_context = await context_manager.get_enhanced_context(
            request.session_id
        )

        if not enhanced_context or "error" in enhanced_context:
            return ResponseBuilder.error(
                message="세션 컨텍스트를 찾을 수 없습니다",
                error_code="NO_SESSION_CONTEXT",
                details={"insights": {}},
            )

        workbook_context = enhanced_context.get("workbook_context")
        if not workbook_context:
            return ResponseBuilder.error(
                message="워크북 컨텍스트가 없습니다",
                error_code="NO_WORKBOOK_CONTEXT",
                details={"insights": {}},
            )

        insights = {}
        insight_types = request.insight_types or [
            "patterns",
            "predictions",
            "optimizations",
        ]

        # 1. 패턴 분석
        if "patterns" in insight_types:
            pattern_analyzer = get_pattern_analyzer()
            patterns = await pattern_analyzer.analyze_user_actions(
                request.session_id, workbook_context
            )
            insights["patterns"] = pattern_analyzer.get_pattern_insights(
                request.session_id
            )

        # 2. 오류 예측
        if "predictions" in insight_types:
            error_predictor = get_error_predictor()
            # 최근 변경 셀 시뮬레이션
            changed_cells = [
                "Sheet1!A1",
                "Sheet1!B1",
            ]  # 실제로는 컨텍스트에서 가져와야 함
            predictions = await error_predictor.predict_errors(
                workbook_context, changed_cells
            )
            insights["predictions"] = error_predictor.get_prediction_summary(
                request.session_id
            )

        # 3. 최적화 제안
        if "optimizations" in insight_types:
            optimization_advisor = get_optimization_advisor()
            optimizations = await optimization_advisor.analyze_for_optimizations(
                workbook_context
            )
            insights["optimizations"] = optimization_advisor.get_optimization_summary(
                workbook_context.file_id
            )

        return ResponseBuilder.success(
            data={
                "session_id": request.session_id,
                "insights": insights,
                "timestamp": datetime.now().isoformat(),
            },
            message="인사이트가 성공적으로 조회되었습니다",
        )

    except Exception as e:
        logger.error(f"인사이트 조회 실패: {str(e)}")
        error_response = ResponseBuilder.from_exception(e)
        raise HTTPException(status_code=500, detail=error_response)


@router.get("/notifications/{session_id}")
async def get_notifications(
    session_id: str, unread_only: bool = False
) -> Dict[str, Any]:
    """
    프로액티브 알림 조회
    """
    try:
        notifier = get_proactive_notifier()
        notifications = notifier.get_notifications(session_id, unread_only)

        return {
            "status": "success",
            "session_id": session_id,
            "notifications": notifications,
            "total": len(notifications),
            "unread": len([n for n in notifications if not n.get("read", False)]),
        }

    except Exception as e:
        logger.error(f"알림 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/action")
async def handle_notification_action(
    request: NotificationActionRequest,
) -> Dict[str, Any]:
    """
    알림 액션 처리 (읽음, 해제, 연기 등)
    """
    try:
        notifier = get_proactive_notifier()

        if request.action == "read":
            notifier.mark_notification_read(request.session_id, request.notification_id)
            message = "알림을 읽음으로 표시했습니다"
        elif request.action == "dismiss":
            notifier.dismiss_notification(request.session_id, request.notification_id)
            message = "알림을 해제했습니다"
        else:
            message = f"알 수 없는 액션: {request.action}"

        return {
            "status": "success",
            "message": message,
            "notification_id": request.notification_id,
        }

    except Exception as e:
        logger.error(f"알림 액션 처리 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-monitoring/{session_id}")
async def start_session_monitoring(session_id: str) -> Dict[str, Any]:
    """
    세션 모니터링 시작
    백그라운드에서 프로액티브 체크 수행
    """
    try:
        import asyncio

        notifier = get_proactive_notifier()

        # 백그라운드 태스크로 모니터링 시작
        asyncio.create_task(notifier.monitor_session(session_id))

        return {
            "status": "success",
            "message": "세션 모니터링이 시작되었습니다",
            "session_id": session_id,
        }

    except Exception as e:
        logger.error(f"모니터링 시작 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-optimization")
async def apply_optimization(file_id: str, optimization_id: str) -> Dict[str, Any]:
    """
    최적화 자동 적용
    """
    try:
        optimization_advisor = get_optimization_advisor()
        result = await optimization_advisor.apply_optimization(file_id, optimization_id)

        return result

    except Exception as e:
        logger.error(f"최적화 적용 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights-summary/{session_id}")
async def get_insights_summary(session_id: str) -> Dict[str, Any]:
    """
    인사이트 요약 대시보드용 데이터
    """
    try:
        # 각 서비스에서 요약 정보 수집
        pattern_analyzer = get_pattern_analyzer()
        error_predictor = get_error_predictor()
        optimization_advisor = get_optimization_advisor()
        notifier = get_proactive_notifier()

        # 컨텍스트 확인
        context_manager = get_enhanced_context_manager()
        enhanced_context = await context_manager.get_enhanced_context(session_id)

        file_id = None
        if enhanced_context and enhanced_context.get("workbook_context"):
            file_id = enhanced_context["workbook_context"].get("file_id")

        # 요약 데이터 수집
        patterns = pattern_analyzer.get_pattern_insights(session_id)
        predictions = error_predictor.get_prediction_summary(session_id)
        optimizations = (
            optimization_advisor.get_optimization_summary(file_id) if file_id else {}
        )
        notifications = notifier.get_notifications(session_id, unread_only=True)

        return {
            "status": "success",
            "session_id": session_id,
            "summary": {
                "active_patterns": len(patterns.get("patterns", [])),
                "risk_predictions": predictions.get("high_risks", 0),
                "optimization_opportunities": optimizations.get("total_suggestions", 0),
                "unread_notifications": len(notifications),
                "insights_available": any(
                    [
                        patterns.get("has_insights"),
                        predictions.get("has_predictions"),
                        optimizations.get("has_suggestions"),
                    ]
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"인사이트 요약 조회 실패: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "summary": {
                "active_patterns": 0,
                "risk_predictions": 0,
                "optimization_opportunities": 0,
                "unread_notifications": 0,
                "insights_available": False,
            },
        }
