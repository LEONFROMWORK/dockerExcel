"""
AI Failover System Monitoring API
AI 모델 페일오버 시스템의 상태를 모니터링하고 관리하는 엔드포인트
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from app.services.ai_failover_service import ai_failover_service, ModelTier, ModelProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai-failover", tags=["AI Failover"])

# Request/Response 모델들
class HealthCheckRequest(BaseModel):
    provider: Optional[str] = Field(None, description="특정 제공업체만 체크 (선택적)")
    force_check: bool = Field(False, description="강제 헬스체크 실행")

class ModelTestRequest(BaseModel):
    messages: List[Dict[str, str]] = Field(..., description="테스트용 메시지")
    temperature: Optional[float] = Field(0.7, description="생성 온도")
    max_tokens: Optional[int] = Field(100, description="최대 토큰 수")
    required_tier: Optional[str] = Field(None, description="필요한 모델 등급")
    supports_vision: Optional[bool] = Field(None, description="비전 지원 필요 여부")

class ModelConfigUpdateRequest(BaseModel):
    provider: str = Field(..., description="모델 제공업체")
    model_name: str = Field(..., description="모델 이름")
    enabled: Optional[bool] = Field(None, description="활성화 상태")
    priority: Optional[int] = Field(None, description="우선순위")

# API 엔드포인트들

@router.get("/status", 
           summary="AI 페일오버 시스템 전체 상태")
async def get_system_status():
    """
    AI 페일오버 시스템의 전체 상태를 반환합니다.
    
    - 전체/정상/비정상 모델 수
    - 제공업체별 상태
    - 개별 모델 상세 정보
    """
    try:
        status = ai_failover_service.get_system_status()
        
        return JSONResponse(content={
            "success": True,
            "data": status,
            "message": "AI 페일오버 시스템 상태를 성공적으로 조회했습니다"
        })
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"시스템 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/models/available",
           summary="사용 가능한 AI 모델 목록")
async def get_available_models(
    tier: Optional[str] = None,
    supports_vision: Optional[bool] = None,
    supports_function_calling: Optional[bool] = None
):
    """
    현재 사용 가능한 AI 모델들의 목록을 반환합니다.
    
    - **tier**: 모델 등급 필터링 (premium, standard, budget, fallback)
    - **supports_vision**: 비전 지원 필터링
    - **supports_function_calling**: 함수 호출 지원 필터링
    """
    try:
        # 문자열을 ModelTier enum으로 변환
        tier_enum = None
        if tier:
            try:
                tier_enum = ModelTier(tier.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tier: {tier}. Valid options: premium, standard, budget, fallback"
                )
        
        available_models = ai_failover_service.get_available_models(
            tier=tier_enum,
            supports_vision=supports_vision,
            supports_function_calling=supports_function_calling
        )
        
        # ModelConfig 객체를 딕셔너리로 변환
        models_data = []
        for model in available_models:
            models_data.append({
                "provider": model.provider.value,
                "model_name": model.model_name,
                "tier": model.tier.value,
                "max_tokens": model.max_tokens,
                "temperature": model.temperature,
                "supports_vision": model.supports_vision,
                "supports_function_calling": model.supports_function_calling,
                "cost_per_1k_tokens": model.cost_per_1k_tokens,
                "rate_limit_rpm": model.rate_limit_rpm,
                "priority": model.priority,
                "enabled": model.enabled
            })
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "models": models_data,
                "total_count": len(models_data),
                "filters_applied": {
                    "tier": tier,
                    "supports_vision": supports_vision,
                    "supports_function_calling": supports_function_calling
                }
            },
            "message": f"{len(models_data)}개의 사용 가능한 모델을 찾았습니다"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get available models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"사용 가능한 모델 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/health-check",
            summary="AI 모델 헬스체크 실행")
async def perform_health_check(
    background_tasks: BackgroundTasks,
    request: HealthCheckRequest
):
    """
    AI 모델들의 헬스체크를 수동으로 실행합니다.
    
    - **provider**: 특정 제공업체만 체크할 경우 지정
    - **force_check**: 정상 모델도 강제로 재체크
    """
    try:
        if request.force_check:
            # 백그라운드에서 전체 헬스체크 실행
            background_tasks.add_task(ai_failover_service._perform_health_checks)
            
            return JSONResponse(content={
                "success": True,
                "message": "전체 AI 모델 헬스체크가 백그라운드에서 시작되었습니다",
                "background_task": True
            })
        else:
            # 현재 상태만 반환
            status = ai_failover_service.get_system_status()
            
            unhealthy_models = [
                model_key for model_key, model_info in status["models"].items()
                if not model_info["is_healthy"]
            ]
            
            return JSONResponse(content={
                "success": True,
                "data": {
                    "healthy_models": status["healthy_models"],
                    "unhealthy_models": status["unhealthy_models"],
                    "unhealthy_model_list": unhealthy_models,
                    "providers": status["providers"]
                },
                "message": f"헬스체크 완료: {status['healthy_models']}/{status['total_models']} 모델이 정상 상태입니다"
            })
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"헬스체크 실행 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/test",
            summary="AI 모델 페일오버 테스트")
async def test_failover_system(request: ModelTestRequest):
    """
    AI 페일오버 시스템을 실제 요청으로 테스트합니다.
    
    지정된 조건에 맞는 모델들을 순서대로 시도하며 페일오버 동작을 확인합니다.
    """
    try:
        # ModelTier enum 변환
        tier_enum = None
        if request.required_tier:
            try:
                tier_enum = ModelTier(request.required_tier.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tier: {request.required_tier}"
                )
        
        # 페일오버 시스템을 통한 완성 요청
        start_time = time.time()
        
        result = await ai_failover_service.chat_completion_with_failover(
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            required_tier=tier_enum,
            supports_vision=request.supports_vision,
            stream=False
        )
        
        response_time = time.time() - start_time
        
        # 시스템 상태 확인
        status = ai_failover_service.get_system_status()
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "result": result,
                "response_time_seconds": response_time,
                "system_status": {
                    "healthy_models": status["healthy_models"],
                    "total_models": status["total_models"]
                },
                "test_parameters": {
                    "required_tier": request.required_tier,
                    "supports_vision": request.supports_vision,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens
                }
            },
            "message": "페일오버 시스템 테스트가 성공적으로 완료되었습니다"
        })
        
    except Exception as e:
        logger.error(f"Failover test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"페일오버 테스트 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/providers",
           summary="AI 제공업체 목록 및 상태")
async def get_providers_status():
    """
    사용 가능한 AI 제공업체들의 목록과 연결 상태를 반환합니다.
    """
    try:
        status = ai_failover_service.get_system_status()
        
        # 제공업체별 상세 정보 생성
        providers_detail = {}
        for provider_name, provider_info in status["providers"].items():
            providers_detail[provider_name] = {
                **provider_info,
                "models": []
            }
        
        # 각 제공업체의 모델 목록 추가
        for model_key, model_info in status["models"].items():
            provider = model_info["provider"]
            if provider in providers_detail:
                providers_detail[provider]["models"].append({
                    "model_name": model_info["model_name"],
                    "tier": model_info["tier"],
                    "is_healthy": model_info["is_healthy"],
                    "success_count": model_info["success_count"],
                    "failure_count": model_info["failure_count"]
                })
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "providers": providers_detail,
                "summary": {
                    "total_providers": len(providers_detail),
                    "connected_providers": sum(
                        1 for p in providers_detail.values() if p["available"]
                    ),
                    "total_healthy_models": sum(
                        p["healthy"] for p in providers_detail.values()
                    )
                }
            },
            "message": "AI 제공업체 상태를 성공적으로 조회했습니다"
        })
        
    except Exception as e:
        logger.error(f"Failed to get providers status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"제공업체 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/metrics",
           summary="AI 페일오버 시스템 메트릭스")
async def get_system_metrics():
    """
    AI 페일오버 시스템의 성능 메트릭스를 반환합니다.
    
    - 모델별 성공/실패율
    - 평균 응답 시간
    - 사용 통계
    """
    try:
        status = ai_failover_service.get_system_status()
        
        # 메트릭스 계산
        total_requests = 0
        total_successes = 0
        total_failures = 0
        avg_response_times = []
        
        model_metrics = {}
        
        for model_key, model_info in status["models"].items():
            success_count = model_info["success_count"]
            failure_count = model_info["failure_count"]
            total_count = success_count + failure_count
            
            total_requests += total_count
            total_successes += success_count
            total_failures += failure_count
            
            if model_info["avg_response_time"] > 0:
                avg_response_times.append(model_info["avg_response_time"])
            
            # 성공률 계산
            success_rate = (success_count / total_count * 100) if total_count > 0 else 0
            
            model_metrics[model_key] = {
                "provider": model_info["provider"],
                "model_name": model_info["model_name"],
                "tier": model_info["tier"],
                "total_requests": total_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": round(success_rate, 2),
                "avg_response_time": model_info["avg_response_time"],
                "is_healthy": model_info["is_healthy"],
                "consecutive_failures": model_info["consecutive_failures"]
            }
        
        # 전체 시스템 메트릭스
        overall_success_rate = (total_successes / total_requests * 100) if total_requests > 0 else 0
        overall_avg_response_time = sum(avg_response_times) / len(avg_response_times) if avg_response_times else 0
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "overall_metrics": {
                    "total_requests": total_requests,
                    "total_successes": total_successes,
                    "total_failures": total_failures,
                    "overall_success_rate": round(overall_success_rate, 2),
                    "overall_avg_response_time": round(overall_avg_response_time, 3),
                    "healthy_models": status["healthy_models"],
                    "total_models": status["total_models"]
                },
                "model_metrics": model_metrics,
                "provider_summary": status["providers"]
            },
            "message": "AI 페일오버 시스템 메트릭스를 성공적으로 조회했습니다"
        })
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"시스템 메트릭스 조회 중 오류가 발생했습니다: {str(e)}"
        )

# Note: Exception handlers should be added to the main app, not router
# These will be moved to main.py if needed

import time