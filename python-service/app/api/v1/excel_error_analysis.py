"""
Excel Error Analysis API Endpoints
Excel 오류 분석 API 엔드포인트 - SOLID 원칙 적용
"""

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    BackgroundTasks,
    Form,
)
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import json
import asyncio

from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.services.ai_chat.chat_handler import AIChatHandler  # 추후 구현
from app.websocket.progress_reporter import WebSocketProgressReporter
from app.core.responses import ResponseBuilder
from app.core.types import ErrorInfo
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/excel-error-analysis", tags=["Excel Error Analysis"])


# Request/Response Models
class AnalyzeRequest(BaseModel):
    file_path: Optional[str] = None
    session_id: str
    options: Dict[str, Any] = {}


class CellErrorRequest(BaseModel):
    file_path: str
    sheet: str
    cell: str
    session_id: str


class FixErrorRequest(BaseModel):
    error_id: str
    session_id: str
    auto_apply: bool = False


class BatchFixRequest(BaseModel):
    error_ids: List[str]
    session_id: str
    strategy: str = "safe"  # safe, aggressive


# Dependencies
async def get_error_detector(
    session_id: Optional[str] = None,
) -> IntegratedErrorDetector:
    """오류 감지기 의존성 주입"""
    if session_id:
        progress_reporter = WebSocketProgressReporter(session_id)
    else:
        # 세션 ID가 없으면 기본 progress reporter 사용
        from app.core.interfaces import DummyProgressReporter

        progress_reporter = DummyProgressReporter()
    return IntegratedErrorDetector(progress_reporter)


async def get_error_fixer(session_id: str):
    """오류 수정기 의존성 주입"""
    # 추후 구현


# Endpoints
@router.post("/analyze")
async def analyze_excel_file(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    detector: IntegratedErrorDetector = Depends(get_error_detector),
):
    """
    Excel 파일 전체 오류 분석

    - 모든 시트의 오류 감지
    - 우선순위별 정렬
    - 자동 수정 가능 여부 판단
    """
    try:
        # 파일 경로 확인
        if not request.file_path:
            raise HTTPException(status_code=400, detail="파일 경로가 필요합니다")

        # 오류 감지 실행
        result = await detector.detect_all_errors(request.file_path)

        # 백그라운드에서 추가 분석 (필요시)
        if request.options.get("deep_analysis", False):
            background_tasks.add_task(
                perform_deep_analysis, request.file_path, request.session_id
            )

        return result

    except Exception as e:
        logger.error(f"파일 분석 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-upload")
async def analyze_uploaded_file(
    file: UploadFile = File(...), session_id: Optional[str] = Form(None)
):
    """
    업로드된 Excel 파일 분석
    """
    try:
        # 파일 저장
        file_path = await save_uploaded_file(file)

        # 오류 감지기 생성
        detector = await get_error_detector(session_id)

        # 분석 실행
        result = await detector.detect_all_errors(file_path)

        return ResponseBuilder.success(
            data=result, message="파일 분석이 완료되었습니다."
        )

    except Exception as e:
        logger.error(f"업로드 파일 분석 오류: {str(e)}")
        error_response = ResponseBuilder.from_exception(e)
        raise HTTPException(status_code=500, detail=error_response)


@router.post("/check-cell")
async def check_cell_error(
    request: CellErrorRequest,
    detector: IntegratedErrorDetector = Depends(get_error_detector),
):
    """
    특정 셀의 오류 확인

    실시간 편집 시 사용
    """
    try:
        error = await detector.detect_cell_error(
            request.file_path, request.sheet, request.cell
        )

        if error:
            error_info: ErrorInfo = {
                "id": error.id,
                "type": error.type,
                "severity": error.severity,
                "cell": error.cell,
                "sheet": error.sheet,
                "message": error.message,
                "is_auto_fixable": error.is_auto_fixable,
                "suggested_fix": error.suggested_fix,
                "confidence": getattr(error, "confidence", None),
                "details": getattr(error, "details", None),
            }
            return ResponseBuilder.success(
                data={"error": error_info}, message="오류가 발견되었습니다."
            )
        else:
            return ResponseBuilder.success(
                data={"cell": request.cell}, message="오류가 없습니다."
            )

    except Exception as e:
        logger.error(f"셀 확인 오류: {str(e)}")
        error_response = ResponseBuilder.from_exception(
            e, context={"cell": request.cell}
        )
        raise HTTPException(status_code=500, detail=error_response)


@router.post("/fix-error")
async def fix_single_error(request: FixErrorRequest, fixer=Depends(get_error_fixer)):
    """
    단일 오류 수정
    """
    try:
        # 오류 정보 조회
        error = await get_error_by_id(request.error_id)
        if not error:
            raise HTTPException(status_code=404, detail="오류를 찾을 수 없습니다")

        # 수정 실행
        result = await fixer.fix_error(error)

        # 자동 적용 옵션
        if request.auto_apply and result.success:
            await apply_fix_to_file(result)

        return ResponseBuilder.success(
            data=result.__dict__, message="오류가 수정되었습니다."
        )

    except Exception as e:
        logger.error(f"오류 수정 실패: {str(e)}")
        error_response = ResponseBuilder.from_exception(e)
        raise HTTPException(status_code=500, detail=error_response)


@router.post("/fix-batch")
async def fix_batch_errors(
    request: BatchFixRequest,
    background_tasks: BackgroundTasks,
    fixer=Depends(get_error_fixer),
):
    """
    여러 오류 일괄 수정
    """
    try:
        # 백그라운드에서 일괄 수정 실행
        task_id = generate_task_id()

        background_tasks.add_task(
            batch_fix_errors,
            request.error_ids,
            request.session_id,
            request.strategy,
            task_id,
        )

        return {
            "status": "processing",
            "task_id": task_id,
            "total_errors": len(request.error_ids),
            "message": "일괄 수정이 시작되었습니다",
        }

    except Exception as e:
        logger.error(f"일괄 수정 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress/{task_id}")
async def get_progress(task_id: str):
    """
    작업 진행 상황 조회
    """
    try:
        progress = await get_task_progress(task_id)
        if not progress:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

        return progress

    except Exception as e:
        logger.error(f"진행 상황 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-fix-suggestion")
async def get_ai_fix_suggestion(
    error_id: str,
    session_id: str,
    ai_handler: AIChatHandler = Depends(lambda: AIChatHandler()),
):
    """
    AI 기반 수정 제안
    """
    try:
        # 오류 정보 조회
        error = await get_error_by_id(error_id)
        if not error:
            raise HTTPException(status_code=404, detail="오류를 찾을 수 없습니다")

        # AI 제안 생성
        context = build_error_context(error, session_id)
        suggestion = await ai_handler.get_fix_suggestion(error, context)

        return {"status": "success", "error_id": error_id, "suggestion": suggestion}

    except Exception as e:
        logger.error(f"AI 제안 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# SSE (Server-Sent Events) for real-time updates
@router.get("/stream/{session_id}")
async def stream_updates(session_id: str):
    """
    실시간 업데이트 스트림
    """

    async def event_generator():
        """SSE 이벤트 생성기"""
        try:
            # Redis 구독 또는 다른 메시지 큐 사용
            async for update in subscribe_to_updates(session_id):
                yield f"data: {json.dumps(update)}\n\n"

        except asyncio.CancelledError:
            logger.info(f"스트림 취소됨: {session_id}")
            raise
        except Exception as e:
            logger.error(f"스트림 오류: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
        },
    )


# Helper Functions
async def save_uploaded_file(file: UploadFile) -> str:
    """업로드된 파일 저장"""
    import os
    import aiofiles
    from datetime import datetime

    # 저장 경로 생성
    upload_dir = "uploads/excel"
    os.makedirs(upload_dir, exist_ok=True)

    # 파일명 생성 (타임스탬프 추가)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)

    # 파일 저장
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    return file_path


async def get_error_by_id(error_id: str):
    """오류 ID로 오류 정보 조회"""
    # 실제 구현에서는 데이터베이스나 캐시에서 조회


async def apply_fix_to_file(fix_result):
    """수정 사항을 파일에 적용"""
    # 실제 구현에서는 ExcelJS나 openpyxl로 파일 수정


def generate_task_id() -> str:
    """작업 ID 생성"""
    import uuid

    return str(uuid.uuid4())


async def batch_fix_errors(error_ids, session_id, strategy, task_id):
    """백그라운드에서 일괄 오류 수정"""
    # 실제 구현


async def get_task_progress(task_id: str):
    """작업 진행 상황 조회"""
    # Redis나 다른 저장소에서 조회


def build_error_context(error, session_id):
    """오류 컨텍스트 생성"""
    # 실제 구현


async def subscribe_to_updates(session_id: str):
    """업데이트 구독"""
    # Redis Pub/Sub 또는 다른 메시지 큐 사용


async def perform_deep_analysis(file_path: str, session_id: str):
    """심층 분석 수행 (백그라운드)"""
    # VBA 분석, 성능 분석 등 추가 분석
