#!/usr/bin/env python3
"""
표 구조 인식 API 엔드포인트
Table Structure Detection API Endpoints
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import cv2
import numpy as np
from typing import List, Dict, Any
import logging
import base64
import io
from PIL import Image

from app.services.table_structure_detector import table_detector

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/detect")
async def detect_table_structure(file: UploadFile = File(...)):
    """
    이미지에서 표 구조 감지
    
    Args:
        file: 업로드된 이미지 파일
    
    Returns:
        Dict: 감지된 표 구조 정보
    """
    try:
        # 파일 형식 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
        
        # 이미지 읽기
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")
        
        logger.info(f"표 구조 감지 시작: {file.filename}")
        
        # 표 구조 감지
        tables = table_detector.detect_tables(image)
        
        # 결과 구조화
        result = {
            "success": True,
            "image_info": {
                "filename": file.filename,
                "width": image.shape[1],
                "height": image.shape[0],
                "channels": image.shape[2] if len(image.shape) == 3 else 1
            },
            "tables_count": len(tables),
            "tables": []
        }
        
        # 각 표에 대한 구조화된 데이터 생성
        for i, table in enumerate(tables):
            structured_data = table_detector.to_structured_data(table)
            structured_data["table_id"] = i + 1
            result["tables"].append(structured_data)
        
        logger.info(f"표 구조 감지 완료: {len(tables)}개 표 발견")
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"표 구조 감지 실패: {e}")
        raise HTTPException(status_code=500, detail=f"표 구조 감지 중 오류 발생: {str(e)}")


@router.post("/detect-with-visualization")
async def detect_table_structure_with_visualization(file: UploadFile = File(...)):
    """
    이미지에서 표 구조 감지 + 시각화 결과 반환
    
    Args:
        file: 업로드된 이미지 파일
    
    Returns:
        Dict: 감지된 표 구조 정보 + 시각화된 이미지
    """
    try:
        # 파일 형식 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
        
        # 이미지 읽기
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")
        
        logger.info(f"표 구조 감지 + 시각화 시작: {file.filename}")
        
        # 표 구조 감지
        tables = table_detector.detect_tables(image)
        
        # 시각화
        visualized_image = table_detector.visualize_table_detection(image, tables)
        
        # 시각화된 이미지를 base64로 인코딩
        _, buffer = cv2.imencode('.png', visualized_image)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # 결과 구조화
        result = {
            "success": True,
            "image_info": {
                "filename": file.filename,
                "width": image.shape[1],
                "height": image.shape[0],
                "channels": image.shape[2] if len(image.shape) == 3 else 1
            },
            "tables_count": len(tables),
            "tables": [],
            "visualization": {
                "image_base64": img_base64,
                "format": "png"
            }
        }
        
        # 각 표에 대한 구조화된 데이터 생성
        for i, table in enumerate(tables):
            structured_data = table_detector.to_structured_data(table)
            structured_data["table_id"] = i + 1
            result["tables"].append(structured_data)
        
        logger.info(f"표 구조 감지 + 시각화 완료: {len(tables)}개 표 발견")
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"표 구조 감지 + 시각화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"표 구조 감지 중 오류 발생: {str(e)}")


@router.post("/analyze-cell")
async def analyze_table_cell(
    file: UploadFile = File(...),
    table_id: int = 1,
    row: int = 0,
    col: int = 0
):
    """
    특정 표의 특정 셀 상세 분석
    
    Args:
        file: 업로드된 이미지 파일
        table_id: 표 ID (1부터 시작)
        row: 행 번호 (0부터 시작)
        col: 열 번호 (0부터 시작)
    
    Returns:
        Dict: 셀 상세 정보
    """
    try:
        # 파일 형식 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
        
        # 이미지 읽기
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")
        
        # 표 구조 감지
        tables = table_detector.detect_tables(image)
        
        if table_id > len(tables) or table_id < 1:
            raise HTTPException(status_code=400, detail=f"표 ID {table_id}를 찾을 수 없습니다.")
        
        table = tables[table_id - 1]
        
        # 해당 셀 찾기
        target_cell = None
        for cell in table.cells:
            if cell.row == row and cell.col == col:
                target_cell = cell
                break
        
        if not target_cell:
            raise HTTPException(status_code=400, detail=f"셀 ({row}, {col})을 찾을 수 없습니다.")
        
        # 셀 이미지 추출
        cell_image = image[target_cell.y:target_cell.y + target_cell.height,
                          target_cell.x:target_cell.x + target_cell.width]
        
        # 셀 이미지를 base64로 인코딩
        _, buffer = cv2.imencode('.png', cell_image)
        cell_img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        result = {
            "success": True,
            "table_id": table_id,
            "cell_info": {
                "row": target_cell.row,
                "col": target_cell.col,
                "text": target_cell.text,
                "confidence": target_cell.confidence,
                "is_header": target_cell.is_header,
                "is_merged": target_cell.is_merged,
                "position": {
                    "x": target_cell.x,
                    "y": target_cell.y,
                    "width": target_cell.width,
                    "height": target_cell.height
                },
                "is_numeric": table_detector._is_numeric(target_cell.text),
                "cell_image_base64": cell_img_base64
            }
        }
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"셀 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"셀 분석 중 오류 발생: {str(e)}")


@router.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "service": "table_detection"}


@router.get("/info")
async def get_service_info():
    """서비스 정보 조회"""
    return {
        "service_name": "Table Structure Detection Service",
        "version": "1.0",
        "capabilities": [
            "표 경계 자동 감지",
            "셀 구조 분석",
            "헤더/데이터 구분",
            "다국어 표 내용 OCR",
            "병합 셀 감지",
            "구조화된 데이터 출력",
            "시각화 지원"
        ],
        "supported_formats": ["PNG", "JPG", "JPEG", "BMP", "TIFF"],
        "detection_features": {
            "line_detection": "HoughLinesP 알고리즘",
            "cell_extraction": "경계 기반 분할",
            "header_detection": "위치 및 내용 기반",
            "ocr_engine": "Tesseract 4.x",
            "visualization": "OpenCV 기반"
        }
    }