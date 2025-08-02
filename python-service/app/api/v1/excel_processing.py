"""
Excel processing API endpoints - Univer Native Only
Excel 파일을 Univer 형식으로 변환하는 전용 API
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional, Dict, Any
import tempfile
import os
import json
import io
import logging

# Univer 관련 import 제거됨 - RevoGrid 사용

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter()

# Univer 관련 converter 제거됨 - RevoGrid 사용

# 지원되는 파일 확장자
SUPPORTED_EXTENSIONS = {'.xlsx', '.xls', '.xlsm'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_excel_file(file: UploadFile) -> None:
    """Excel 파일 유효성 검사"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다")
    
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(SUPPORTED_EXTENSIONS)}"
        )


@router.get("/deprecated")
async def deprecated_endpoint() -> JSONResponse:
    """
    이 엔드포인트는 더 이상 사용되지 않습니다.
    새로운 Excel 처리 API를 사용해주세요.
    """
    return JSONResponse(
        status_code=410,  # Gone
        content={
            "error": True,
            "message": "이 API는 더 이상 사용되지 않습니다",
            "deprecated": True,
            "replacement": "/api/v1/excel/convert",
            "reason": "새로운 Excel 처리 백엔드로 완전 전환됨"
        }
    )


@router.get("/supported-formats")
async def get_supported_formats() -> JSONResponse:
    """지원되는 Excel 파일 형식 목록 반환 (더 이상 사용되지 않음)"""
    return JSONResponse(
        status_code=410,  # Gone
        content={
            "error": True,
            "message": "이 API는 더 이상 사용되지 않습니다",
            "deprecated": True,
            "replacement": "/api/v1/excel/supported-formats",
            "reason": "새로운 Excel 처리 백엔드로 완전 전환됨"
        }
    )