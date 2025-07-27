"""
PWA (Progressive Web App) API 엔드포인트
Progressive Web App API Endpoints
"""

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, List, Any, Optional
import logging
import json
import os
from datetime import datetime, timedelta
import uuid

from ...core.i18n_dependencies import get_i18n_context, I18nContext

router = APIRouter()
logger = logging.getLogger(__name__)

# PWA 설치 통계
pwa_stats = {
    "installs": 0,
    "active_users": set(),
    "push_subscriptions": {},
    "last_updated": datetime.now()
}


@router.get("/manifest.json")
async def get_manifest(
    request: Request,
    i18n: I18nContext = Depends(get_i18n_context)
):
    """PWA 매니페스트 파일 제공"""
    
    try:
        manifest_path = os.path.join(
            os.path.dirname(__file__),
            "../../pwa/manifest.json"
        )
        
        # 기본 매니페스트 로드
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        # 언어별 매니페스트 커스터마이징
        if i18n.language != "ko":
            manifest = localize_manifest(manifest, i18n.language)
        
        # 동적 start_url 설정
        base_url = str(request.base_url).rstrip('/')
        manifest["start_url"] = f"{base_url}/"
        manifest["scope"] = f"{base_url}/"
        
        # 아이콘 URL 절대 경로로 변경
        for icon in manifest.get("icons", []):
            if icon["src"].startswith("/"):
                icon["src"] = f"{base_url}{icon['src']}"
        
        return JSONResponse(
            content=manifest,
            headers={
                "Content-Type": "application/manifest+json",
                "Cache-Control": "max-age=86400"  # 24시간 캐시
            }
        )
        
    except Exception as e:
        logger.error(f"매니페스트 제공 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="매니페스트를 로드할 수 없습니다")


@router.get("/service-worker.js")
async def get_service_worker():
    """Service Worker 스크립트 제공"""
    
    try:
        sw_path = os.path.join(
            os.path.dirname(__file__),
            "../../pwa/service_worker.js"
        )
        
        return FileResponse(
            sw_path,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Service-Worker-Allowed": "/"
            }
        )
        
    except Exception as e:
        logger.error(f"Service Worker 제공 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="Service Worker를 로드할 수 없습니다")


@router.post("/install")
async def track_pwa_install(
    install_data: Dict[str, Any],
    i18n: I18nContext = Depends(get_i18n_context)
):
    """PWA 설치 추적"""
    
    try:
        user_agent = install_data.get("user_agent", "unknown")
        platform = install_data.get("platform", "unknown")
        install_time = datetime.now()
        
        # 설치 통계 업데이트
        pwa_stats["installs"] += 1
        pwa_stats["last_updated"] = install_time
        
        install_id = str(uuid.uuid4())
        
        logger.info(f"PWA 설치 기록: {install_id}, Platform: {platform}")
        
        return {
            "status": "success",
            "message": i18n.get_text("common.success"),
            "install_id": install_id,
            "timestamp": install_time.isoformat(),
            "features_enabled": {
                "offline_support": True,
                "push_notifications": True,
                "background_sync": True,
                "file_handling": True
            }
        }
        
    except Exception as e:
        logger.error(f"PWA 설치 추적 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)


@router.post("/push/subscribe")
async def subscribe_push_notifications(
    subscription_data: Dict[str, Any],
    user_id: Optional[str] = None,
    i18n: I18nContext = Depends(get_i18n_context)
):
    """푸시 알림 구독"""
    
    try:
        endpoint = subscription_data.get("endpoint")
        keys = subscription_data.get("keys", {})
        
        if not endpoint:
            error_message = i18n.get_text("validation.required")
            raise HTTPException(status_code=400, detail=error_message)
        
        subscription_id = str(uuid.uuid4())
        user_key = user_id or f"anonymous_{subscription_id[:8]}"
        
        # 구독 정보 저장
        pwa_stats["push_subscriptions"][subscription_id] = {
            "user_id": user_key,
            "endpoint": endpoint,
            "keys": keys,
            "subscribed_at": datetime.now().isoformat(),
            "preferences": {
                "analysis_complete": True,
                "error_alerts": True,
                "template_updates": False,
                "system_maintenance": True
            }
        }
        
        logger.info(f"푸시 알림 구독: {subscription_id} for user {user_key}")
        
        return {
            "status": "success",
            "message": i18n.get_text("common.success"),
            "subscription_id": subscription_id,
            "supported_features": [
                "analysis_notifications",
                "error_alerts", 
                "template_updates",
                "system_notifications"
            ]
        }
        
    except Exception as e:
        logger.error(f"푸시 알림 구독 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)


@router.delete("/push/unsubscribe/{subscription_id}")
async def unsubscribe_push_notifications(
    subscription_id: str,
    i18n: I18nContext = Depends(get_i18n_context)
):
    """푸시 알림 구독 해제"""
    
    try:
        if subscription_id in pwa_stats["push_subscriptions"]:
            del pwa_stats["push_subscriptions"][subscription_id]
            logger.info(f"푸시 알림 구독 해제: {subscription_id}")
            
            return {
                "status": "success",
                "message": i18n.get_text("common.success"),
                "subscription_id": subscription_id
            }
        else:
            error_message = i18n.get_error_message("not_found")
            raise HTTPException(status_code=404, detail=error_message)
            
    except Exception as e:
        logger.error(f"푸시 알림 구독 해제 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)


@router.post("/push/send")
async def send_push_notification(
    notification_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    i18n: I18nContext = Depends(get_i18n_context)
):
    """푸시 알림 전송 (관리자용)"""
    
    try:
        message = notification_data.get("message", "")
        notification_type = notification_data.get("type", "general")
        target_users = notification_data.get("target_users", [])
        
        if not message:
            error_message = i18n.get_text("validation.required")
            raise HTTPException(status_code=400, detail=error_message)
        
        # 백그라운드에서 알림 전송
        background_tasks.add_task(
            send_push_to_subscribers,
            message,
            notification_type,
            target_users
        )
        
        return {
            "status": "success",
            "message": i18n.get_text("common.success"),
            "notification_type": notification_type,
            "estimated_recipients": len(pwa_stats["push_subscriptions"])
        }
        
    except Exception as e:
        logger.error(f"푸시 알림 전송 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)


@router.get("/stats")
async def get_pwa_stats(i18n: I18nContext = Depends(get_i18n_context)):
    """PWA 사용 통계"""
    
    try:
        stats = {
            "total_installs": pwa_stats["installs"],
            "active_push_subscriptions": len(pwa_stats["push_subscriptions"]),
            "last_updated": pwa_stats["last_updated"].isoformat(),
            "features": {
                "service_worker": True,
                "offline_support": True,
                "push_notifications": True,
                "background_sync": True,
                "file_handling": True,
                "install_prompt": True
            },
            "browser_support": {
                "chrome": True,
                "firefox": True,
                "safari": True,
                "edge": True
            }
        }
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "language": i18n.language,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"PWA 통계 조회 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)


@router.post("/cache/clear")
async def clear_pwa_cache(
    cache_types: List[str] = None,
    i18n: I18nContext = Depends(get_i18n_context)
):
    """PWA 캐시 삭제"""
    
    try:
        if not cache_types:
            cache_types = ["static", "dynamic", "api"]
        
        # 클라이언트에게 캐시 삭제 요청 전송
        cache_clear_message = {
            "type": "CLEAR_CACHE",
            "cache_types": cache_types,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "message": i18n.get_text("common.success"),
            "cache_types_cleared": cache_types,
            "instruction": "클라이언트에서 캐시 삭제를 실행하세요",
            "cache_clear_message": cache_clear_message
        }
        
    except Exception as e:
        logger.error(f"PWA 캐시 삭제 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)


@router.get("/update/check")
async def check_pwa_update(
    current_version: str = "1.0.0",
    i18n: I18nContext = Depends(get_i18n_context)
):
    """PWA 업데이트 확인"""
    
    try:
        # 현재 앱 버전
        app_version = "1.0.0"  # 실제로는 설정에서 가져와야 함
        
        update_available = current_version != app_version
        
        update_info = {
            "update_available": update_available,
            "current_version": current_version,
            "latest_version": app_version,
            "release_notes": [
                "Excel 분석 성능 개선",
                "새로운 템플릿 추가",
                "다국어 지원 강화",
                "오프라인 기능 향상"
            ] if update_available else [],
            "update_size": "2.5MB" if update_available else "0MB",
            "required": False,
            "auto_update": True
        }
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "language": i18n.language,
            "update_info": update_info
        }
        
    except Exception as e:
        logger.error(f"PWA 업데이트 확인 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)


@router.get("/offline")
async def get_offline_capabilities(i18n: I18nContext = Depends(get_i18n_context)):
    """오프라인 기능 정보"""
    
    try:
        offline_features = {
            "cached_pages": [
                "/",
                "/upload",
                "/templates", 
                "/dashboard",
                "/settings"
            ],
            "cached_apis": [
                "/api/v1/health",
                "/api/v1/i18n/languages",
                "/api/v1/excel-templates/categories"
            ],
            "offline_storage": {
                "analysis_results": "IndexedDB",
                "user_preferences": "LocalStorage",
                "cached_templates": "CacheAPI"
            },
            "background_sync": {
                "enabled": True,
                "sync_tags": [
                    "excel-analysis-sync",
                    "user-preferences-sync",
                    "template-downloads-sync"
                ]
            },
            "estimated_cache_size": "15MB",
            "max_offline_duration": "30 days"
        }
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "language": i18n.language,
            "offline_capabilities": offline_features
        }
        
    except Exception as e:
        logger.error(f"오프라인 기능 정보 조회 실패: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)


# 헬퍼 함수들

def localize_manifest(manifest: Dict[str, Any], language: str) -> Dict[str, Any]:
    """매니페스트 현지화"""
    
    translations = {
        "en": {
            "name": "Excel Unified - AI-Powered Excel Analysis",
            "short_name": "ExcelUnified",
            "description": "AI-powered Excel file analysis, error detection, and intelligent template generation",
            "lang": "en-US"
        },
        "ja": {
            "name": "Excel Unified - AI駆動Excel分析",
            "short_name": "ExcelUnified",
            "description": "AI駆動のExcelファイル分析、エラー検出、インテリジェントテンプレート生成",
            "lang": "ja-JP"
        },
        "zh": {
            "name": "Excel Unified - AI驱动Excel分析",
            "short_name": "ExcelUnified", 
            "description": "AI驱动的Excel文件分析、错误检测和智能模板生成",
            "lang": "zh-CN"
        }
    }
    
    if language in translations:
        localized = manifest.copy()
        localized.update(translations[language])
        return localized
    
    return manifest


async def send_push_to_subscribers(
    message: str,
    notification_type: str,
    target_users: List[str]
):
    """구독자들에게 푸시 알림 전송"""
    
    try:
        # 실제 푸시 알림 전송 로직
        # Web Push Protocol 구현 필요
        
        sent_count = 0
        failed_count = 0
        
        for subscription_id, subscription in pwa_stats["push_subscriptions"].items():
            try:
                # 타겟 사용자 필터링
                if target_users and subscription["user_id"] not in target_users:
                    continue
                
                # 알림 타입별 사용자 설정 확인
                preferences = subscription.get("preferences", {})
                if not preferences.get(f"{notification_type}_notifications", True):
                    continue
                
                # 실제 푸시 전송 (여기서는 로그만 출력)
                logger.info(f"푸시 알림 전송: {subscription_id} - {message}")
                sent_count += 1
                
            except Exception as e:
                logger.error(f"개별 푸시 전송 실패 {subscription_id}: {str(e)}")
                failed_count += 1
        
        logger.info(f"푸시 알림 전송 완료: 성공 {sent_count}, 실패 {failed_count}")
        
    except Exception as e:
        logger.error(f"푸시 알림 배치 전송 실패: {str(e)}")


@router.get("/health")
async def pwa_service_health():
    """PWA 서비스 상태 확인"""
    
    try:
        return {
            "status": "healthy",
            "service": "pwa",
            "timestamp": datetime.now().isoformat(),
            "features": {
                "manifest": True,
                "service_worker": True,
                "push_notifications": True,
                "offline_support": True,
                "background_sync": True
            },
            "statistics": {
                "total_installs": pwa_stats["installs"],
                "active_subscriptions": len(pwa_stats["push_subscriptions"])
            }
        }
        
    except Exception as e:
        logger.error(f"PWA 서비스 상태 확인 실패: {str(e)}")
        return {
            "status": "unhealthy", 
            "service": "pwa",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }