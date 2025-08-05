"""
Proactive Notifier Service
프로액티브 알림 시스템
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import logging
from app.services.insights.pattern_analyzer import PatternAnalyzer, WorkPattern
from app.services.insights.error_predictor import ErrorPredictor, ErrorPrediction
from app.services.insights.optimization_advisor import (
    OptimizationAdvisor,
    OptimizationSuggestion,
)
from app.services.context import get_enhanced_context_manager
from app.core.interfaces import RiskLevel

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """알림 타입"""

    PATTERN_DETECTED = "pattern_detected"
    ERROR_PREDICTED = "error_predicted"
    OPTIMIZATION_AVAILABLE = "optimization_available"
    MILESTONE_REACHED = "milestone_reached"
    TIP = "tip"
    WARNING = "warning"


class NotificationPriority(Enum):
    """알림 우선순위"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ProactiveNotification:
    """프로액티브 알림"""

    id: str
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    actions: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    read: bool = False
    dismissed: bool = False


class ProactiveNotifier:
    """프로액티브 알림 관리자"""

    def __init__(self):
        self.pattern_analyzer = PatternAnalyzer()
        self.error_predictor = ErrorPredictor()
        self.optimization_advisor = OptimizationAdvisor()
        self.notifications: Dict[str, List[ProactiveNotification]] = {}
        self.notification_rules = self._init_notification_rules()
        self.last_check: Dict[str, datetime] = {}

    def _init_notification_rules(self) -> Dict[str, Dict[str, Any]]:
        """알림 규칙 초기화"""
        return {
            "check_interval": 30,  # 30초마다 체크
            "max_notifications_per_session": 10,
            "cooldown_period": 300,  # 5분 쿨다운
            "priority_thresholds": {
                "pattern_confidence": 0.7,
                "error_probability": 0.6,
                "optimization_priority": 3,
            },
        }

    async def monitor_session(self, session_id: str):
        """세션 모니터링 시작"""
        try:
            while True:
                # 체크 간격 대기
                await asyncio.sleep(self.notification_rules["check_interval"])

                # 컨텍스트 가져오기
                context_manager = get_enhanced_context_manager()
                enhanced_context = await context_manager.get_enhanced_context(
                    session_id
                )

                if not enhanced_context or "error" in enhanced_context:
                    continue

                workbook_context = enhanced_context.get("workbook_context")
                if not workbook_context:
                    continue

                # 프로액티브 체크 수행
                await self._perform_proactive_checks(session_id, workbook_context)

        except asyncio.CancelledError:
            logger.info(f"세션 {session_id} 모니터링 종료")
        except Exception as e:
            logger.error(f"세션 모니터링 오류: {str(e)}")

    async def _perform_proactive_checks(self, session_id: str, context: Any):
        """프로액티브 체크 수행"""
        # 쿨다운 체크
        last_check = self.last_check.get(session_id)
        if (
            last_check
            and (datetime.now() - last_check).seconds
            < self.notification_rules["cooldown_period"]
        ):
            return

        notifications = []

        # 1. 패턴 분석
        patterns = await self.pattern_analyzer.analyze_user_actions(session_id, context)
        pattern_notifications = self._create_pattern_notifications(patterns)
        notifications.extend(pattern_notifications)

        # 2. 오류 예측
        # 최근 변경된 셀 추적 필요 - 여기서는 시뮬레이션
        changed_cells = self._get_recently_changed_cells(session_id)
        if changed_cells:
            predictions = await self.error_predictor.predict_errors(
                context, changed_cells
            )
            error_notifications = self._create_error_notifications(predictions)
            notifications.extend(error_notifications)

        # 3. 최적화 제안
        optimizations = await self.optimization_advisor.analyze_for_optimizations(
            context
        )
        optimization_notifications = self._create_optimization_notifications(
            optimizations
        )
        notifications.extend(optimization_notifications)

        # 4. 마일스톤 체크
        milestone_notifications = self._check_milestones(session_id, context)
        notifications.extend(milestone_notifications)

        # 5. 컨텍스트 기반 팁
        tip_notifications = self._generate_contextual_tips(session_id, context)
        notifications.extend(tip_notifications)

        # 알림 저장 및 전송
        if notifications:
            self._store_notifications(session_id, notifications)
            await self._send_notifications(session_id, notifications[:3])  # 최대 3개

        self.last_check[session_id] = datetime.now()

    def _create_pattern_notifications(
        self, patterns: List[WorkPattern]
    ) -> List[ProactiveNotification]:
        """패턴 기반 알림 생성"""
        notifications = []

        for pattern in patterns:
            if (
                pattern.confidence
                >= self.notification_rules["priority_thresholds"]["pattern_confidence"]
            ):
                notification = ProactiveNotification(
                    id=f"pattern_{pattern.pattern_type.value}_{datetime.now().timestamp()}",
                    type=NotificationType.PATTERN_DETECTED,
                    priority=self._calculate_pattern_priority(pattern),
                    title=f"작업 패턴 감지: {pattern.description}",
                    message=f"{pattern.frequency}번의 반복 작업이 감지되었습니다. "
                    + (
                        pattern.suggestions[0]
                        if pattern.suggestions
                        else "최적화를 고려해보세요."
                    ),
                    actions=[
                        {"label": "자세히 보기", "action": "view_pattern_details"},
                        {"label": "무시", "action": "dismiss"},
                    ],
                    metadata={
                        "pattern_type": pattern.pattern_type.value,
                        "confidence": pattern.confidence,
                        "suggestions": pattern.suggestions,
                    },
                )
                notifications.append(notification)

        return notifications

    def _create_error_notifications(
        self, predictions: List[ErrorPrediction]
    ) -> List[ProactiveNotification]:
        """오류 예측 알림 생성"""
        notifications = []

        # 고위험 예측만 알림
        high_risk = [
            p for p in predictions if p.risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]
        ]

        for prediction in high_risk[:2]:  # 최대 2개
            notification = ProactiveNotification(
                id=f"error_{prediction.error_type}_{prediction.cell_address}_{datetime.now().timestamp()}",
                type=NotificationType.ERROR_PREDICTED,
                priority=self._risk_to_priority(prediction.risk_level),
                title=f"오류 위험 감지: {prediction.cell_address}",
                message=prediction.description
                + " "
                + (prediction.prevention_tips[0] if prediction.prevention_tips else ""),
                actions=[
                    {
                        "label": "수정하기",
                        "action": "fix_error",
                        "cell": prediction.cell_address,
                    },
                    {"label": "자세히 보기", "action": "view_error_details"},
                ],
                metadata={
                    "error_type": prediction.error_type,
                    "probability": prediction.probability,
                    "affected_cell": f"{prediction.sheet_name}!{prediction.cell_address}",
                    "prevention_tips": prediction.prevention_tips,
                },
            )
            notifications.append(notification)

        return notifications

    def _create_optimization_notifications(
        self, optimizations: List[OptimizationSuggestion]
    ) -> List[ProactiveNotification]:
        """최적화 제안 알림 생성"""
        notifications = []

        # 높은 우선순위 최적화만
        high_priority = [
            o
            for o in optimizations
            if o.priority
            >= self.notification_rules["priority_thresholds"]["optimization_priority"]
        ]

        for optimization in high_priority[:2]:  # 최대 2개
            notification = ProactiveNotification(
                id=f"opt_{optimization.type.value}_{datetime.now().timestamp()}",
                type=NotificationType.OPTIMIZATION_AVAILABLE,
                priority=NotificationPriority.MEDIUM,
                title=optimization.title,
                message=optimization.description
                + f" ({optimization.estimated_impact})",
                actions=[
                    (
                        {"label": "적용하기", "action": "apply_optimization"}
                        if optimization.auto_applicable
                        else None
                    ),
                    {"label": "자세히 보기", "action": "view_optimization_details"},
                    {"label": "나중에", "action": "snooze"},
                ],
                metadata={
                    "optimization_type": optimization.type.value,
                    "affected_cells": len(optimization.affected_cells),
                    "auto_applicable": optimization.auto_applicable,
                    "steps": optimization.implementation_steps,
                },
            )
            notification.actions = [a for a in notification.actions if a]  # None 제거
            notifications.append(notification)

        return notifications

    def _check_milestones(
        self, session_id: str, context: Any
    ) -> List[ProactiveNotification]:
        """마일스톤 체크"""
        notifications = []

        # 예시 마일스톤들
        milestones = {
            "first_100_formulas": {
                "condition": context.total_formulas >= 100,
                "title": "100개 수식 달성! 🎉",
                "message": "워크북에 100개의 수식이 포함되어 있습니다. 수식 관리 도구를 사용해보세요.",
            },
            "error_free": {
                "condition": context.total_errors == 0 and context.total_cells > 50,
                "title": "오류 없는 워크북! ✨",
                "message": "현재 워크북에 오류가 없습니다. 훌륭합니다!",
            },
            "large_dataset": {
                "condition": context.total_cells >= 1000,
                "title": "대용량 데이터셋",
                "message": "1000개 이상의 셀을 관리 중입니다. 성능 최적화를 고려해보세요.",
            },
        }

        # 이미 표시한 마일스톤 추적 필요
        for milestone_id, milestone in milestones.items():
            if milestone["condition"]:
                notification = ProactiveNotification(
                    id=f"milestone_{milestone_id}_{datetime.now().timestamp()}",
                    type=NotificationType.MILESTONE_REACHED,
                    priority=NotificationPriority.LOW,
                    title=milestone["title"],
                    message=milestone["message"],
                    actions=[{"label": "축하합니다!", "action": "acknowledge"}],
                )
                notifications.append(notification)
                break  # 한 번에 하나만

        return notifications

    def _generate_contextual_tips(
        self, session_id: str, context: Any
    ) -> List[ProactiveNotification]:
        """컨텍스트 기반 팁 생성"""
        tips = []

        # 시간대별 팁
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 11:
            tips.append(
                {
                    "title": "오전 작업 팁",
                    "message": "복잡한 수식 작업은 집중력이 높은 오전에 하는 것이 좋습니다.",
                }
            )
        elif 14 <= current_hour <= 16:
            tips.append(
                {
                    "title": "오후 작업 팁",
                    "message": "정기적인 저장을 잊지 마세요. Ctrl+S로 빠르게 저장할 수 있습니다.",
                }
            )

        # 작업 패턴 기반 팁
        if context.total_formulas > 50:
            tips.append(
                {
                    "title": "수식 관리 팁",
                    "message": "F9 키로 선택한 수식 부분만 계산해볼 수 있습니다.",
                }
            )

        # 랜덤하게 하나 선택
        if tips:
            import random

            selected_tip = random.choice(tips)

            notification = ProactiveNotification(
                id=f"tip_{datetime.now().timestamp()}",
                type=NotificationType.TIP,
                priority=NotificationPriority.LOW,
                title=selected_tip["title"],
                message=selected_tip["message"],
                actions=[
                    {"label": "도움이 되었어요", "action": "helpful"},
                    {"label": "닫기", "action": "close"},
                ],
            )
            return [notification]

        return []

    def _calculate_pattern_priority(self, pattern: WorkPattern) -> NotificationPriority:
        """패턴 우선순위 계산"""
        if pattern.confidence >= 0.9:
            return NotificationPriority.HIGH
        elif pattern.confidence >= 0.7:
            return NotificationPriority.MEDIUM
        else:
            return NotificationPriority.LOW

    def _risk_to_priority(self, risk_level: RiskLevel) -> NotificationPriority:
        """위험도를 우선순위로 변환"""
        mapping = {
            RiskLevel.HIGH: NotificationPriority.URGENT,
            RiskLevel.MEDIUM: NotificationPriority.HIGH,
            RiskLevel.LOW: NotificationPriority.MEDIUM,
            RiskLevel.NONE: NotificationPriority.LOW,
        }
        return mapping.get(risk_level, NotificationPriority.LOW)

    def _get_recently_changed_cells(self, session_id: str) -> List[str]:
        """최근 변경된 셀 조회 (시뮬레이션)"""
        # 실제 구현에서는 세션 스토어에서 조회
        return ["Sheet1!A1", "Sheet1!B1", "Sheet1!C1"]

    def _store_notifications(
        self, session_id: str, notifications: List[ProactiveNotification]
    ):
        """알림 저장"""
        if session_id not in self.notifications:
            self.notifications[session_id] = []

        # 최대 개수 제한
        max_notifications = self.notification_rules["max_notifications_per_session"]
        self.notifications[session_id].extend(notifications)

        # 오래된 것부터 제거
        if len(self.notifications[session_id]) > max_notifications:
            self.notifications[session_id] = self.notifications[session_id][
                -max_notifications:
            ]

    async def _send_notifications(
        self, session_id: str, notifications: List[ProactiveNotification]
    ):
        """알림 전송 (WebSocket 통해)"""
        try:
            from app.api.v1.context_websocket import broadcast_context_update

            for notification in notifications:
                await broadcast_context_update(
                    session_id,
                    "proactive_notification",
                    {
                        "notification": {
                            "id": notification.id,
                            "type": notification.type.value,
                            "priority": notification.priority.value,
                            "title": notification.title,
                            "message": notification.message,
                            "actions": notification.actions,
                            "timestamp": notification.timestamp.isoformat(),
                        }
                    },
                )

        except Exception as e:
            logger.error(f"알림 전송 실패: {str(e)}")

    def get_notifications(
        self, session_id: str, unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """알림 조회"""
        session_notifications = self.notifications.get(session_id, [])

        if unread_only:
            session_notifications = [n for n in session_notifications if not n.read]

        return [
            {
                "id": n.id,
                "type": n.type.value,
                "priority": n.priority.value,
                "title": n.title,
                "message": n.message,
                "timestamp": n.timestamp.isoformat(),
                "actions": n.actions,
                "read": n.read,
                "dismissed": n.dismissed,
            }
            for n in session_notifications
            if not n.dismissed
        ]

    def mark_notification_read(self, session_id: str, notification_id: str):
        """알림 읽음 표시"""
        if session_id in self.notifications:
            for notification in self.notifications[session_id]:
                if notification.id == notification_id:
                    notification.read = True
                    break

    def dismiss_notification(self, session_id: str, notification_id: str):
        """알림 해제"""
        if session_id in self.notifications:
            for notification in self.notifications[session_id]:
                if notification.id == notification_id:
                    notification.dismissed = True
                    break
