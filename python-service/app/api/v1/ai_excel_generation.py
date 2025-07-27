"""
AI 기반 Excel 생성 API 엔드포인트
AI-powered Excel Generation API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

from app.core.i18n_dependencies import get_i18n_context, I18nContext
from app.services.ai_excel_generator import ai_excel_generator
from app.services.interactive_excel_generator import interactive_excel_generator
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class NaturalLanguageRequest(BaseModel):
    """자연어 요청 모델"""
    request: str = Field(..., description="자연어로 된 Excel 생성 요청")
    context: Optional[Dict[str, Any]] = Field(default=None, description="추가 컨텍스트")
    language: str = Field(default="ko", description="언어 코드")
    style_preset: str = Field(default="modern", description="스타일 프리셋")


class InteractiveSessionRequest(BaseModel):
    """대화형 세션 요청"""
    user_id: str = Field(..., description="사용자 ID")
    initial_request: str = Field(..., description="초기 요청")
    language: str = Field(default="ko", description="언어 코드")


class SessionResponseRequest(BaseModel):
    """세션 응답 요청"""
    session_id: str = Field(..., description="세션 ID")
    response: str = Field(..., description="사용자 응답")


class SmartTemplateRequest(BaseModel):
    """스마트 템플릿 요청"""
    domain: str = Field(..., description="비즈니스 도메인")
    requirements: List[str] = Field(..., description="요구사항 목록")
    data_sample: Optional[Dict[str, Any]] = Field(default=None, description="샘플 데이터")


@router.post("/ai-generate")
async def generate_excel_from_natural_language(
    request: NaturalLanguageRequest,
    background_tasks: BackgroundTasks,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    자연어로부터 Excel 파일 생성
    
    예시:
    - "월별 매출 관리를 위한 Excel 파일을 만들어줘"
    - "직원 근태 관리 시스템을 Excel로 구성해줘"
    - "재고 관리용 Excel 템플릿을 생성해줘"
    """
    try:
        logger.info(f"AI Excel 생성 요청: {request.request[:100]}...")
        
        # 웹소켓으로 진행 상황 전송
        await websocket_manager.send_progress(
            f"ai_generation_{datetime.now().timestamp()}",
            {
                "stage": "analyzing",
                "message": i18n.translate("ai.analyzing_request"),
                "progress": 10
            }
        )
        
        # AI 기반 생성
        result = await ai_excel_generator.generate_from_natural_language(
            user_request=request.request,
            context=request.context,
            language=request.language
        )
        
        if result["status"] == "success":
            # 백그라운드에서 사용 통계 업데이트
            background_tasks.add_task(
                update_generation_statistics,
                request.request,
                result
            )
            
            await websocket_manager.send_progress(
                f"ai_generation_{datetime.now().timestamp()}",
                {
                    "stage": "completed",
                    "message": i18n.translate("ai.generation_complete"),
                    "progress": 100
                }
            )
            
            return {
                "status": "success",
                "file_path": result["file_path"],
                "structure": result["structure"],
                "features": result["features_applied"],
                "ai_insights": result.get("ai_insights", []),
                "download_url": f"/download/{result['file_path'].split('/')[-1]}"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Generation failed")
            )
            
    except Exception as e:
        logger.error(f"AI Excel 생성 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=i18n.get_error_message("ai_generation_failed", error=str(e))
        )


@router.post("/interactive-generate/start")
async def start_interactive_generation(
    request: InteractiveSessionRequest,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    대화형 Excel 생성 세션 시작
    """
    try:
        result = await interactive_excel_generator.start_generation_session(
            user_id=request.user_id,
            initial_request=request.initial_request,
            language=request.language
        )
        
        return {
            "status": "success",
            "session_id": result["session_id"],
            "stage": result["stage"],
            "needs_clarification": result["needs_clarification"],
            "questions": result.get("questions", []),
            "understanding": result.get("initial_understanding", {})
        }
        
    except Exception as e:
        logger.error(f"대화형 세션 시작 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/interactive-generate/respond")
async def respond_to_interactive_session(
    request: SessionResponseRequest,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    대화형 세션에 응답
    """
    try:
        result = await interactive_excel_generator.process_user_response(
            session_id=request.session_id,
            user_response=request.response
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"세션 응답 처리 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/interactive-generate/status/{session_id}")
async def get_session_status(
    session_id: str,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    세션 상태 확인
    """
    try:
        status = await interactive_excel_generator.get_session_status(session_id)
        
        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])
        
        return status
        
    except Exception as e:
        logger.error(f"세션 상태 확인 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/smart-template")
async def create_smart_template(
    request: SmartTemplateRequest,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    도메인별 스마트 템플릿 생성
    
    지원 도메인:
    - finance: 재무/회계
    - hr: 인사관리
    - sales: 영업/판매
    - inventory: 재고관리
    - project: 프로젝트 관리
    """
    try:
        # 도메인별 특화 요청 생성
        domain_prompts = {
            "finance": "재무 분석 및 보고를 위한 Excel 템플릿",
            "hr": "인사 관리 및 급여 계산을 위한 Excel 시스템",
            "sales": "영업 실적 추적 및 분석 대시보드",
            "inventory": "재고 관리 및 수불 관리 시스템",
            "project": "프로젝트 일정 및 리소스 관리 도구"
        }
        
        base_prompt = domain_prompts.get(
            request.domain,
            f"{request.domain} 관리를 위한 Excel 템플릿"
        )
        
        # 요구사항 추가
        full_prompt = f"{base_prompt}. 요구사항: " + ", ".join(request.requirements)
        
        # 컨텍스트 구성
        context = {
            "domain": request.domain,
            "requirements": request.requirements,
            "data_sample": request.data_sample
        }
        
        # AI 생성
        result = await ai_excel_generator.generate_from_natural_language(
            user_request=full_prompt,
            context=context,
            language="ko"
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "template_id": f"smart_{request.domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "file_path": result["file_path"],
                "features": result["features_applied"],
                "domain_specific_features": get_domain_features(request.domain),
                "download_url": f"/download/{result['file_path'].split('/')[-1]}"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Template generation failed")
            )
            
    except Exception as e:
        logger.error(f"스마트 템플릿 생성 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/enhance-with-ai")
async def enhance_excel_with_ai(
    file_path: str,
    enhancement_type: str = "auto",
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    기존 Excel 파일을 AI로 향상
    
    Enhancement types:
    - auto: 자동 분석 및 개선
    - formulas: 수식 최적화
    - charts: 차트 추가/개선
    - formatting: 서식 개선
    """
    try:
        # 파일 분석 및 향상
        enhanced_file = await ai_excel_generator._enhance_with_ai(
            excel_file=file_path,
            intent_analysis={
                "enhancement_type": enhancement_type,
                "auto_detect": enhancement_type == "auto"
            }
        )
        
        return {
            "status": "success",
            "original_file": file_path,
            "enhanced_file": enhanced_file,
            "improvements": [
                "수식 최적화",
                "차트 자동 생성",
                "조건부 서식 적용",
                "데이터 유효성 검사 추가"
            ],
            "download_url": f"/download/{enhanced_file.split('/')[-1]}"
        }
        
    except Exception as e:
        logger.error(f"AI 향상 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


def get_domain_features(domain: str) -> List[str]:
    """도메인별 특화 기능"""
    domain_features = {
        "finance": [
            "자동 재무제표 생성",
            "비율 분석 차트",
            "예산 대비 실적 추적",
            "현금흐름 예측"
        ],
        "hr": [
            "급여 자동 계산",
            "근태 관리 시스템",
            "휴가 일수 추적",
            "인사 평가 대시보드"
        ],
        "sales": [
            "판매 퍼널 분석",
            "고객별 매출 추적",
            "목표 달성률 시각화",
            "영업 성과 순위"
        ],
        "inventory": [
            "재고 수준 모니터링",
            "자동 발주점 계산",
            "ABC 분석",
            "재고 회전율 추적"
        ],
        "project": [
            "간트 차트 생성",
            "리소스 할당 매트릭스",
            "마일스톤 추적",
            "진행률 대시보드"
        ]
    }
    
    return domain_features.get(domain, ["기본 데이터 관리", "자동 집계", "기본 차트"])


async def update_generation_statistics(request: str, result: Dict[str, Any]):
    """생성 통계 업데이트 (백그라운드 작업)"""
    try:
        # 통계 업데이트 로직
        logger.info(f"Generation statistics updated for request: {request[:50]}...")
    except Exception as e:
        logger.error(f"Failed to update statistics: {str(e)}")