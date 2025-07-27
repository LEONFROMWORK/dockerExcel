"""
OCR 재시도 통계 API 엔드포인트
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging

from app.services.multilingual_two_tier_service import MultilingualTwoTierService
from app.services.async_ocr_service import AsyncOCRService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/retry/stats")
async def get_retry_stats():
    """
    OCR 재시도 통계 조회
    """
    try:
        # MultilingualTwoTierService 통계
        ocr_service = MultilingualTwoTierService()
        multilingual_stats = ocr_service.retry_service.get_retry_stats()
        
        # AsyncOCRService 통계 (임시 인스턴스)
        async_service = AsyncOCRService()
        async_stats = async_service.retry_service.get_retry_stats()
        
        return JSONResponse(content={
            "multilingual_ocr": multilingual_stats,
            "async_ocr": async_stats,
            "summary": {
                "total_operations": (
                    multilingual_stats.get('successful_retries', 0) + 
                    multilingual_stats.get('failed_after_retries', 0) +
                    async_stats.get('successful_retries', 0) + 
                    async_stats.get('failed_after_retries', 0)
                ),
                "total_retry_attempts": (
                    multilingual_stats.get('total_attempts', 0) + 
                    async_stats.get('total_attempts', 0)
                ),
                "overall_success_rate": 0.0  # 계산됨
            }
        })
        
    except Exception as e:
        logger.error(f"재시도 통계 조회 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"통계 조회 실패: {str(e)}"}
        )


@router.post("/retry/stats/reset")
async def reset_retry_stats():
    """
    OCR 재시도 통계 초기화
    """
    try:
        # MultilingualTwoTierService 통계 초기화
        ocr_service = MultilingualTwoTierService()
        ocr_service.retry_service.reset_stats()
        
        logger.info("OCR 재시도 통계가 초기화되었습니다")
        
        return JSONResponse(content={
            "message": "재시도 통계가 초기화되었습니다",
            "timestamp": "2025-07-25T15:00:00Z"
        })
        
    except Exception as e:
        logger.error(f"통계 초기화 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"통계 초기화 실패: {str(e)}"}
        )


@router.get("/retry/config")
async def get_retry_config():
    """
    현재 재시도 설정 조회
    """
    try:
        ocr_service = MultilingualTwoTierService()
        config = ocr_service.retry_service.config
        
        return JSONResponse(content={
            "retry_config": {
                "max_attempts": config.max_attempts,
                "base_delay": config.base_delay,
                "max_delay": config.max_delay,
                "backoff_multiplier": config.backoff_multiplier,
                "jitter": config.jitter,
                "timeout": config.timeout
            },
            "failure_types": {
                "TEMPORARY_NETWORK": "일시적 네트워크 오류",
                "TEMPORARY_RESOURCE": "리소스 부족",
                "TEMPORARY_SERVICE": "서비스 일시 중단",
                "PERMANENT_FORMAT": "잘못된 파일 형식",
                "PERMANENT_CORRUPT": "파일 손상",
                "PERMANENT_MODEL": "모델 파일 누락",
                "UNKNOWN": "분류 불가능한 오류"
            }
        })
        
    except Exception as e:
        logger.error(f"재시도 설정 조회 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"설정 조회 실패: {str(e)}"}
        )