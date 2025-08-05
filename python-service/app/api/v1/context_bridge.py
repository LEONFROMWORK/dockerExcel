"""
Context Bridge API
Rails Action Cable과 Python WebSocket 간 브릿지
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Dict, Any
import logging
from datetime import datetime

from app.services.context import get_enhanced_context_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ContextUpdateRequest(BaseModel):
    """컨텍스트 업데이트 요청"""

    session_id: str
    data: Dict[str, Any]


class CellAnalysisRequest(BaseModel):
    """셀 분석 요청"""

    session_id: str
    cell_address: str


def verify_internal_api_key(x_internal_api_key: str = Header(...)):
    """내부 API 키 검증"""
    if x_internal_api_key != settings.RAILS_INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@router.post("/update")
async def update_context(
    request: ContextUpdateRequest, authorized: bool = Depends(verify_internal_api_key)
) -> Dict[str, Any]:
    """
    Rails에서 컨텍스트 업데이트 수신
    """
    try:
        context_manager = get_enhanced_context_manager()

        # 메시지 타입에 따라 처리
        message_type = request.data.get("type")

        if message_type == "cell_selection":
            cells = request.data.get("data", {}).get("cells", [])
            result = await context_manager.update_multi_cell_selection(
                request.session_id, cells
            )

            return {
                "status": "success",
                "action": "cell_selection_updated",
                "cell_count": len(cells),
                "result": result,
            }

        else:
            # 일반 컨텍스트 업데이트
            context = context_manager.get_context(request.session_id)
            if context:
                context_manager.update_context(context, request.data)
                return {"status": "success", "action": "context_updated"}
            else:
                return {"status": "error", "message": "Context not found"}

    except Exception as e:
        logger.error(f"컨텍스트 업데이트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/enhanced/{session_id}")
async def get_enhanced_context(
    session_id: str, authorized: bool = Depends(verify_internal_api_key)
) -> Dict[str, Any]:
    """
    향상된 컨텍스트 조회
    """
    try:
        context_manager = get_enhanced_context_manager()
        context = await context_manager.get_enhanced_context(session_id)

        return context

    except Exception as e:
        logger.error(f"컨텍스트 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-cell")
async def analyze_cell(
    request: CellAnalysisRequest, authorized: bool = Depends(verify_internal_api_key)
) -> Dict[str, Any]:
    """
    특정 셀 분석 요청
    """
    try:
        context_manager = get_enhanced_context_manager()
        workbook_context = context_manager.workbook_contexts.get(request.session_id)

        if not workbook_context:
            return {"status": "error", "message": "Workbook context not found"}

        # 셀 주소 파싱 (예: "Sheet1!A1")
        parts = request.cell_address.split("!")
        sheet_name = parts[0] if len(parts) > 1 else "Sheet1"
        cell_address = parts[1] if len(parts) > 1 else request.cell_address

        # IntegratedErrorDetector를 사용한 셀 분석
        from app.services.detection.integrated_error_detector import (
            IntegratedErrorDetector,
        )
        from app.core.file_path_resolver import FilePathResolver

        detector = IntegratedErrorDetector()
        file_path = await FilePathResolver.get_file_path(workbook_context.file_id)

        if file_path:
            cell_error = await detector.detect_cell_error(
                file_path, sheet_name, cell_address
            )

            return {
                "status": "success",
                "cell": request.cell_address,
                "has_error": cell_error is not None,
                "error": cell_error.__dict__ if cell_error else None,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {"status": "error", "message": "File not found"}

    except Exception as e:
        logger.error(f"셀 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
