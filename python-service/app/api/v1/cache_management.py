"""
Cache Management API
캐시 시스템 관리 및 모니터링
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging

from app.core.integrated_cache import integrated_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    캐시 통계 조회
    """
    try:
        stats = integrated_cache.get_stats()

        return {
            "status": "success",
            "stats": stats,
            "cache_config": {
                "max_memory_items": integrated_cache.max_memory_items,
                "ttl_config": integrated_cache.ttl_config,
            },
        }

    except Exception as e:
        logger.error(f"캐시 통계 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_cache(pattern: str = None) -> Dict[str, Any]:
    """
    캐시 초기화

    Args:
        pattern: 삭제할 키 패턴 (선택적)
    """
    try:
        if pattern:
            # 패턴 기반 삭제
            count = await integrated_cache.clear_pattern(pattern)
            message = f"{count}개의 캐시 항목이 삭제되었습니다 (패턴: {pattern})"
        else:
            # 전체 삭제는 위험하므로 패턴을 요구
            return {
                "status": "error",
                "message": "패턴을 지정해주세요. 전체 삭제는 허용되지 않습니다.",
            }

        return {"status": "success", "message": message}

    except Exception as e:
        logger.error(f"캐시 초기화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/warmup")
async def warmup_cache(keys: List[str]) -> Dict[str, Any]:
    """
    캐시 워밍업

    Args:
        keys: 미리 로드할 키 목록
    """
    try:
        await integrated_cache.warmup(keys)

        return {"status": "success", "message": f"{len(keys)}개의 키를 워밍업했습니다"}

    except Exception as e:
        logger.error(f"캐시 워밍업 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/key/{key}")
async def get_cache_key(key: str) -> Dict[str, Any]:
    """
    특정 캐시 키 조회

    Args:
        key: 조회할 키
    """
    try:
        # 메모리 캐시 확인
        memory_value = await integrated_cache.get(key, cache_level="memory")

        # Redis 캐시 확인
        redis_value = await integrated_cache.get(key, cache_level="redis")

        return {
            "status": "success",
            "key": key,
            "found_in_memory": memory_value is not None,
            "found_in_redis": redis_value is not None,
            "value": memory_value or redis_value,
        }

    except Exception as e:
        logger.error(f"캐시 키 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/key/{key}")
async def delete_cache_key(key: str) -> Dict[str, Any]:
    """
    특정 캐시 키 삭제

    Args:
        key: 삭제할 키
    """
    try:
        success = await integrated_cache.delete(key)

        return {
            "status": "success" if success else "partial_success",
            "message": f"캐시 키 '{key}' 삭제 {'완료' if success else '부분 완료'}",
        }

    except Exception as e:
        logger.error(f"캐시 키 삭제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
