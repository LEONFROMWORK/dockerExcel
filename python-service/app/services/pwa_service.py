"""
PWA (Progressive Web App) 관리 서비스
PWA Management Service
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class PWAService:
    """PWA 기능 관리 서비스"""

    def __init__(self):
        self.installation_stats = {
            "total_installs": 0,
            "daily_installs": 0,
            "install_sources": {},
            "user_agents": {},
            "platforms": {},
        }

        self.push_subscriptions = {}
        self.update_notifications = []
        self.offline_cache_stats = {"cache_hits": 0, "cache_misses": 0, "total_size": 0}

    async def track_installation(self, install_data: Dict[str, Any]) -> Dict[str, Any]:
        """PWA 설치 추적"""

        try:
            install_id = str(uuid.uuid4())
            user_agent = install_data.get("user_agent", "unknown")
            platform = install_data.get("platform", "unknown")
            source = install_data.get("source", "unknown")
            install_time = datetime.now()

            # 설치 통계 업데이트
            self.installation_stats["total_installs"] += 1
            self.installation_stats["daily_installs"] += 1

            # 소스별 통계
            if source in self.installation_stats["install_sources"]:
                self.installation_stats["install_sources"][source] += 1
            else:
                self.installation_stats["install_sources"][source] = 1

            # 플랫폼별 통계
            if platform in self.installation_stats["platforms"]:
                self.installation_stats["platforms"][platform] += 1
            else:
                self.installation_stats["platforms"][platform] = 1

            # 사용자 에이전트 통계
            browser = self._extract_browser_from_ua(user_agent)
            if browser in self.installation_stats["user_agents"]:
                self.installation_stats["user_agents"][browser] += 1
            else:
                self.installation_stats["user_agents"][browser] = 1

            installation_record = {
                "install_id": install_id,
                "user_agent": user_agent,
                "platform": platform,
                "source": source,
                "install_time": install_time.isoformat(),
                "features_available": self._get_available_features(user_agent),
            }

            logger.info(f"PWA 설치 기록: {install_id} - {platform} - {browser}")

            return {"status": "success", "install_record": installation_record}

        except Exception as e:
            logger.error(f"PWA 설치 추적 실패: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def register_push_subscription(
        self, subscription_data: Dict[str, Any], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """푸시 알림 구독 등록"""

        try:
            subscription_id = str(uuid.uuid4())
            endpoint = subscription_data.get("endpoint")
            keys = subscription_data.get("keys", {})

            if not endpoint:
                raise ValueError("푸시 엔드포인트가 필요합니다")

            subscription_record = {
                "subscription_id": subscription_id,
                "user_id": user_id or f"anonymous_{subscription_id[:8]}",
                "endpoint": endpoint,
                "keys": keys,
                "created_at": datetime.now().isoformat(),
                "last_used": datetime.now().isoformat(),
                "preferences": {
                    "analysis_complete": True,
                    "error_notifications": True,
                    "template_updates": False,
                    "system_maintenance": True,
                    "marketing": False,
                },
                "delivery_stats": {"sent": 0, "delivered": 0, "failed": 0},
            }

            self.push_subscriptions[subscription_id] = subscription_record

            logger.info(f"푸시 구독 등록: {subscription_id}")

            return {
                "status": "success",
                "subscription_id": subscription_id,
                "subscription_record": subscription_record,
            }

        except Exception as e:
            logger.error(f"푸시 구독 등록 실패: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def send_push_notification(
        self,
        message: str,
        notification_type: str = "general",
        target_users: Optional[List[str]] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """푸시 알림 전송"""

        try:
            notification_id = str(uuid.uuid4())
            send_time = datetime.now()

            # 알림 데이터 구성
            notification_payload = {
                "id": notification_id,
                "message": message,
                "type": notification_type,
                "timestamp": send_time.isoformat(),
                "custom_data": custom_data or {},
                "actions": self._get_notification_actions(notification_type),
            }

            sent_count = 0
            failed_count = 0

            # 구독자별 전송
            for subscription_id, subscription in self.push_subscriptions.items():
                try:
                    # 타겟 사용자 필터링
                    if target_users and subscription["user_id"] not in target_users:
                        continue

                    # 사용자 알림 설정 확인
                    preferences = subscription.get("preferences", {})
                    notification_key = f"{notification_type}_notifications"
                    if not preferences.get(notification_key, True):
                        continue

                    # 실제 푸시 전송 (Web Push Protocol 구현 필요)
                    success = await self._send_individual_push(
                        subscription, notification_payload
                    )

                    if success:
                        sent_count += 1
                        subscription["delivery_stats"]["sent"] += 1
                        subscription["last_used"] = send_time.isoformat()
                    else:
                        failed_count += 1
                        subscription["delivery_stats"]["failed"] += 1

                except Exception as e:
                    logger.error(f"개별 푸시 전송 실패 {subscription_id}: {str(e)}")
                    failed_count += 1

            result = {
                "status": "success",
                "notification_id": notification_id,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "total_subscriptions": len(self.push_subscriptions),
                "send_time": send_time.isoformat(),
            }

            logger.info(
                f"푸시 알림 전송 완료: {notification_id} - 성공: {sent_count}, 실패: {failed_count}"
            )

            return result

        except Exception as e:
            logger.error(f"푸시 알림 전송 실패: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def check_for_updates(self, current_version: str) -> Dict[str, Any]:
        """앱 업데이트 확인"""

        try:
            # 실제로는 버전 관리 시스템에서 가져와야 함
            latest_version = "1.0.1"  # 현재 최신 버전

            update_available = current_version != latest_version

            if update_available:
                update_info = {
                    "available": True,
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "release_date": "2025-01-25",
                    "size": "2.5MB",
                    "type": "minor",  # major, minor, patch
                    "critical": False,
                    "release_notes": [
                        "Excel 분석 성능 30% 향상",
                        "새로운 금융 템플릿 5개 추가",
                        "오프라인 모드 안정성 개선",
                        "다국어 지원 확장 (베트남어, 태국어)",
                        "UI/UX 개선 및 버그 수정",
                    ],
                    "breaking_changes": [],
                    "download_url": "/pwa/update",
                    "auto_update": True,
                    "requires_restart": False,
                }

                # 업데이트 알림 큐에 추가
                self.update_notifications.append(
                    {
                        "notification_id": str(uuid.uuid4()),
                        "version": latest_version,
                        "created_at": datetime.now().isoformat(),
                        "target_version": current_version,
                    }
                )
            else:
                update_info = {
                    "available": False,
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "last_check": datetime.now().isoformat(),
                }

            return {"status": "success", "update_info": update_info}

        except Exception as e:
            logger.error(f"업데이트 확인 실패: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def get_offline_capabilities(self) -> Dict[str, Any]:
        """오프라인 기능 정보 제공"""

        try:
            capabilities = {
                "cache_strategy": {
                    "static_files": "cache_first",
                    "api_calls": "network_first_cache_fallback",
                    "user_data": "cache_first_network_update",
                },
                "cached_resources": {
                    "pages": [
                        "/",
                        "/upload",
                        "/templates",
                        "/dashboard",
                        "/settings",
                        "/help",
                    ],
                    "api_endpoints": [
                        "/api/v1/health",
                        "/api/v1/i18n/languages",
                        "/api/v1/excel-templates/categories",
                        "/api/v1/pwa/offline",
                    ],
                    "static_assets": [
                        "/static/css/main.css",
                        "/static/js/main.js",
                        "/static/icons/*.png",
                        "/manifest.json",
                    ],
                },
                "background_sync": {
                    "enabled": True,
                    "sync_tags": [
                        "excel-analysis-sync",
                        "user-preferences-sync",
                        "template-downloads-sync",
                        "feedback-sync",
                    ],
                    "retry_intervals": [5, 10, 30, 60, 300],  # 초 단위
                },
                "storage": {
                    "cache_api": "15MB",
                    "indexeddb": "50MB",
                    "localstorage": "10MB",
                    "estimated_total": "75MB",
                },
                "offline_features": [
                    "이전 분석 결과 조회",
                    "템플릿 목록 및 미리보기",
                    "사용자 설정 관리",
                    "도움말 및 가이드",
                    "분석 요청 대기열 관리",
                ],
                "limitations": [
                    "새로운 Excel 파일 분석 불가",
                    "AI 기능 이용 불가",
                    "실시간 템플릿 업데이트 불가",
                    "클라우드 동기화 불가",
                ],
            }

            return {
                "status": "success",
                "capabilities": capabilities,
                "cache_stats": self.offline_cache_stats,
            }

        except Exception as e:
            logger.error(f"오프라인 기능 정보 조회 실패: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def get_installation_analytics(self) -> Dict[str, Any]:
        """PWA 설치 분석 데이터"""

        try:
            analytics = {
                "overview": {
                    "total_installs": self.installation_stats["total_installs"],
                    "daily_installs": self.installation_stats["daily_installs"],
                    "active_subscriptions": len(self.push_subscriptions),
                    "cache_efficiency": self._calculate_cache_efficiency(),
                },
                "install_sources": self.installation_stats["install_sources"],
                "platforms": self.installation_stats["platforms"],
                "browsers": self.installation_stats["user_agents"],
                "push_statistics": self._get_push_statistics(),
                "engagement_metrics": {
                    "avg_session_duration": "12m 34s",
                    "daily_active_users": 245,
                    "retention_rate": {"day_1": 85.2, "day_7": 67.8, "day_30": 45.3},
                },
                "feature_usage": {
                    "offline_mode": 78.5,
                    "push_notifications": 56.3,
                    "install_to_homescreen": 34.7,
                    "background_sync": 42.1,
                },
            }

            return {
                "status": "success",
                "analytics": analytics,
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"설치 분석 데이터 조회 실패: {str(e)}")
            return {"status": "error", "error": str(e)}

    def _extract_browser_from_ua(self, user_agent: str) -> str:
        """User Agent에서 브라우저 추출"""

        user_agent_lower = user_agent.lower()

        if "chrome" in user_agent_lower and "edg" not in user_agent_lower:
            return "Chrome"
        elif "firefox" in user_agent_lower:
            return "Firefox"
        elif "safari" in user_agent_lower and "chrome" not in user_agent_lower:
            return "Safari"
        elif "edg" in user_agent_lower:
            return "Edge"
        elif "opera" in user_agent_lower:
            return "Opera"
        else:
            return "Unknown"

    def _get_available_features(self, user_agent: str) -> List[str]:
        """사용자 환경에서 사용 가능한 PWA 기능"""

        browser = self._extract_browser_from_ua(user_agent)

        base_features = [
            "service_worker",
            "cache_api",
            "offline_support",
            "responsive_design",
        ]

        # 브라우저별 추가 기능
        if browser in ["Chrome", "Edge"]:
            base_features.extend(
                [
                    "push_notifications",
                    "background_sync",
                    "install_prompt",
                    "file_handling",
                    "web_share",
                ]
            )
        elif browser == "Firefox":
            base_features.extend(["push_notifications", "install_prompt"])
        elif browser == "Safari":
            base_features.extend(["push_notifications", "install_prompt"])

        return base_features

    def _get_notification_actions(self, notification_type: str) -> List[Dict[str, str]]:
        """알림 타입별 액션 버튼"""

        action_maps = {
            "analysis_complete": [
                {"action": "view_result", "title": "결과 보기"},
                {"action": "dismiss", "title": "닫기"},
            ],
            "error_alert": [
                {"action": "view_error", "title": "오류 보기"},
                {"action": "retry", "title": "다시 시도"},
                {"action": "dismiss", "title": "닫기"},
            ],
            "template_update": [
                {"action": "view_templates", "title": "템플릿 보기"},
                {"action": "dismiss", "title": "나중에"},
            ],
            "system_maintenance": [
                {"action": "view_details", "title": "자세히"},
                {"action": "dismiss", "title": "확인"},
            ],
        }

        return action_maps.get(
            notification_type, [{"action": "dismiss", "title": "닫기"}]
        )

    async def _send_individual_push(
        self, subscription: Dict[str, Any], payload: Dict[str, Any]
    ) -> bool:
        """개별 푸시 알림 전송"""

        try:
            # 실제 Web Push Protocol 구현
            # 여기서는 시뮬레이션

            subscription["endpoint"]
            subscription["keys"]

            # 푸시 서비스에 요청 전송
            # await send_web_push(endpoint, keys, payload)

            logger.debug(f"푸시 전송 시뮬레이션: {subscription['subscription_id']}")

            # 성공 시뮬레이션 (실제로는 HTTP 응답 코드 확인)
            return True

        except Exception as e:
            logger.error(f"개별 푸시 전송 실패: {str(e)}")
            return False

    def _calculate_cache_efficiency(self) -> float:
        """캐시 효율성 계산"""

        total_requests = (
            self.offline_cache_stats["cache_hits"]
            + self.offline_cache_stats["cache_misses"]
        )

        if total_requests == 0:
            return 0.0

        return (self.offline_cache_stats["cache_hits"] / total_requests) * 100

    def _get_push_statistics(self) -> Dict[str, Any]:
        """푸시 알림 통계"""

        total_sent = sum(
            sub["delivery_stats"]["sent"] for sub in self.push_subscriptions.values()
        )
        total_delivered = sum(
            sub["delivery_stats"]["delivered"]
            for sub in self.push_subscriptions.values()
        )
        total_failed = sum(
            sub["delivery_stats"]["failed"] for sub in self.push_subscriptions.values()
        )

        return {
            "total_subscriptions": len(self.push_subscriptions),
            "notifications_sent": total_sent,
            "notifications_delivered": total_delivered,
            "notifications_failed": total_failed,
            "delivery_rate": (
                (total_delivered / total_sent * 100) if total_sent > 0 else 0
            ),
            "active_subscriptions": len(
                [
                    sub
                    for sub in self.push_subscriptions.values()
                    if datetime.fromisoformat(sub["last_used"])
                    > datetime.now() - timedelta(days=30)
                ]
            ),
        }

    async def cleanup_expired_subscriptions(self):
        """만료된 구독 정리"""

        try:
            current_time = datetime.now()
            expired_threshold = current_time - timedelta(days=90)  # 90일 후 만료

            expired_subscriptions = []

            for subscription_id, subscription in list(self.push_subscriptions.items()):
                last_used = datetime.fromisoformat(subscription["last_used"])

                if last_used < expired_threshold:
                    expired_subscriptions.append(subscription_id)
                    del self.push_subscriptions[subscription_id]

            logger.info(f"만료된 푸시 구독 정리: {len(expired_subscriptions)}개")

            return {
                "status": "success",
                "expired_count": len(expired_subscriptions),
                "remaining_count": len(self.push_subscriptions),
            }

        except Exception as e:
            logger.error(f"만료된 구독 정리 실패: {str(e)}")
            return {"status": "error", "error": str(e)}


# 전역 PWA 서비스 인스턴스
pwa_service = PWAService()


# 백그라운드 작업 스케줄러
async def schedule_pwa_maintenance():
    """PWA 유지보수 작업 스케줄러"""

    while True:
        try:
            # 매일 자정에 실행
            await asyncio.sleep(86400)  # 24시간

            # 만료된 구독 정리
            await pwa_service.cleanup_expired_subscriptions()

            # 일일 설치 통계 리셋
            pwa_service.installation_stats["daily_installs"] = 0

            logger.info("PWA 유지보수 작업 완료")

        except Exception as e:
            logger.error(f"PWA 유지보수 작업 실패: {str(e)}")
            await asyncio.sleep(3600)  # 1시간 후 재시도
