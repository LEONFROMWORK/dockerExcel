#!/usr/bin/env python3
"""
차트/그래프 감지 API 엔드포인트
Chart/Graph Detection API Endpoints

재무 문서의 차트와 그래프를 감지하고 데이터를 추출하는 API
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, Response
from typing import List, Dict, Any, Optional
import cv2
import numpy as np
from PIL import Image
import io
import json
import logging

from app.services.chart_detector import chart_detector

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/detect", response_model=Dict[str, Any])
async def detect_charts(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.5
):
    """
    이미지에서 차트 감지
    
    Args:
        file: 업로드된 이미지 파일
        confidence_threshold: 차트 감지 신뢰도 임계값
        
    Returns:
        감지된 차트 정보와 데이터 포인트
    """
    try:
        # 파일 형식 검증
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 이미지 읽기
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다")
        
        logger.info(f"차트 감지 시작 - 이미지 크기: {image.shape}")
        
        # 차트 감지
        charts = chart_detector.detect_charts(image)
        
        # 신뢰도 필터링
        filtered_charts = [
            chart for chart in charts 
            if chart.confidence >= confidence_threshold
        ]
        
        logger.info(f"감지된 차트: {len(charts)}개, 필터링 후: {len(filtered_charts)}개")
        
        # 결과 구성
        result = {
            "success": True,
            "total_charts": len(filtered_charts),
            "image_info": {
                "width": image.shape[1],
                "height": image.shape[0],
                "channels": image.shape[2] if len(image.shape) > 2 else 1
            },
            "charts": []
        }
        
        # 각 차트 정보 추가
        for i, chart in enumerate(filtered_charts):
            chart_data = chart_detector.to_structured_data(chart)
            chart_data["chart_id"] = i + 1
            result["charts"].append(chart_data)
        
        return result
        
    except Exception as e:
        logger.error(f"차트 감지 실패: {e}")
        raise HTTPException(status_code=500, detail=f"차트 감지 중 오류 발생: {str(e)}")


@router.post("/detect-with-visualization")
async def detect_charts_with_visualization(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.5,
    return_format: str = "json"  # "json" or "image"
):
    """
    차트 감지 결과를 시각화와 함께 반환
    
    Args:
        file: 업로드된 이미지 파일
        confidence_threshold: 차트 감지 신뢰도 임계값
        return_format: 반환 형식 ("json" 또는 "image")
        
    Returns:
        차트 감지 결과와 시각화 이미지
    """
    try:
        # 파일 읽기
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다")
        
        # 차트 감지
        charts = chart_detector.detect_charts(image)
        
        # 신뢰도 필터링
        filtered_charts = [
            chart for chart in charts 
            if chart.confidence >= confidence_threshold
        ]
        
        # 시각화 생성
        visualized_image = chart_detector.visualize_chart_detection(image, filtered_charts)
        
        if return_format == "image":
            # PNG 이미지로 반환
            _, buffer = cv2.imencode('.png', visualized_image)
            return Response(
                content=buffer.tobytes(),
                media_type="image/png",
                headers={"Content-Disposition": "inline; filename=chart_detection_result.png"}
            )
        else:
            # JSON 형식으로 반환 (base64 인코딩된 이미지 포함)
            import base64
            _, buffer = cv2.imencode('.png', visualized_image)
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            result = {
                "success": True,
                "total_charts": len(filtered_charts),
                "charts": [
                    chart_detector.to_structured_data(chart) 
                    for chart in filtered_charts
                ],
                "visualization": {
                    "format": "base64_png",
                    "data": image_base64
                }
            }
            
            return result
            
    except Exception as e:
        logger.error(f"차트 감지 및 시각화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"처리 중 오류 발생: {str(e)}")


@router.post("/analyze-data-points", response_model=Dict[str, Any])
async def analyze_chart_data_points(
    file: UploadFile = File(...),
    chart_type: str = "auto",  # "auto", "line", "bar", "pie", "scatter"
    extract_values: bool = True
):
    """
    특정 차트 타입에 대한 상세 데이터 포인트 분석
    
    Args:
        file: 업로드된 이미지 파일
        chart_type: 분석할 차트 타입 (auto는 자동 감지)
        extract_values: 수치 값 추출 여부
        
    Returns:
        상세한 데이터 포인트 분석 결과
    """
    try:
        # 파일 읽기
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다")
        
        # 차트 감지
        charts = chart_detector.detect_charts(image)
        
        if not charts:
            return {
                "success": False,
                "message": "감지된 차트가 없습니다",
                "charts": []
            }
        
        # 첫 번째 차트 선택 (가장 신뢰도 높은 것)
        primary_chart = max(charts, key=lambda x: x.confidence)
        
        # 차트 타입이 지정된 경우 필터링
        if chart_type != "auto":
            target_charts = [c for c in charts if c.chart_type == chart_type]
            if target_charts:
                primary_chart = target_charts[0]
        
        # 상세 분석
        detailed_analysis = {
            "success": True,
            "chart_analysis": {
                "detected_type": primary_chart.chart_type,
                "requested_type": chart_type,
                "confidence": primary_chart.confidence,
                "position": {
                    "x": primary_chart.x,
                    "y": primary_chart.y,
                    "width": primary_chart.width,
                    "height": primary_chart.height
                }
            },
            "data_points": [],
            "axis_info": {},
            "legend_info": {},
            "statistics": {}
        }
        
        # 데이터 포인트 분석
        for i, point in enumerate(primary_chart.data_points):
            point_info = {
                "point_id": i + 1,
                "coordinates": {"x": point.x, "y": point.y},
                "value": point.value,
                "label": point.label,
                "confidence": point.confidence
            }
            
            if extract_values and point.value is not None:
                point_info["formatted_value"] = f"{point.value:.2f}"
            
            detailed_analysis["data_points"].append(point_info)
        
        # 축 정보
        if primary_chart.x_axis:
            detailed_analysis["axis_info"]["x_axis"] = {
                "min_value": primary_chart.x_axis.min_value,
                "max_value": primary_chart.x_axis.max_value,
                "labels": primary_chart.x_axis.labels,
                "title": primary_chart.x_axis.title,
                "scale_type": primary_chart.x_axis.scale_type
            }
        
        if primary_chart.y_axis:
            detailed_analysis["axis_info"]["y_axis"] = {
                "min_value": primary_chart.y_axis.min_value,
                "max_value": primary_chart.y_axis.max_value,
                "labels": primary_chart.y_axis.labels,
                "title": primary_chart.y_axis.title,
                "scale_type": primary_chart.y_axis.scale_type
            }
        
        # 범례 정보
        if primary_chart.legend:
            detailed_analysis["legend_info"] = {
                "position": primary_chart.legend.position,
                "items": primary_chart.legend.items
            }
        
        # 통계 정보
        if primary_chart.data_points:
            values = [p.value for p in primary_chart.data_points if p.value is not None]
            if values:
                detailed_analysis["statistics"] = {
                    "total_points": len(primary_chart.data_points),
                    "valid_values": len(values),
                    "min_value": min(values),
                    "max_value": max(values),
                    "average_value": sum(values) / len(values),
                    "value_range": max(values) - min(values)
                }
        
        return detailed_analysis
        
    except Exception as e:
        logger.error(f"차트 데이터 포인트 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")


@router.get("/chart-types", response_model=Dict[str, Any])
async def get_supported_chart_types():
    """
    지원되는 차트 타입 목록 반환
    
    Returns:
        지원되는 차트 타입과 설명
    """
    return {
        "supported_types": {
            "line": {
                "name": "선 그래프",
                "description": "시간에 따른 데이터 변화를 선으로 표현",
                "features": ["연속 데이터", "트렌드 분석", "다중 시리즈"]
            },
            "bar": {
                "name": "막대 그래프",
                "description": "카테고리별 수치를 막대로 표현",
                "features": ["범주형 데이터", "비교 분석", "수직/수평 배치"]
            },
            "pie": {
                "name": "원형 그래프",
                "description": "전체에서 각 부분의 비율을 원형으로 표현",
                "features": ["비율 데이터", "구성 분석", "섹터별 분할"]
            },
            "scatter": {
                "name": "산점도",
                "description": "두 변수 간의 관계를 점으로 표현",
                "features": ["상관관계", "분포 분석", "이상치 감지"]
            },
            "area": {
                "name": "영역 그래프",
                "description": "선 그래프 아래 영역을 채워서 표현",
                "features": ["누적 데이터", "면적 비교", "전체 대비 부분"]
            }
        },
        "detection_confidence": {
            "high": "0.8 이상 - 매우 정확한 감지",
            "medium": "0.5-0.8 - 보통 수준의 감지",
            "low": "0.3-0.5 - 낮은 신뢰도 감지"
        },
        "data_extraction_features": [
            "데이터 포인트 좌표 추출",
            "축 레이블 및 값 인식",
            "범례 항목 식별",
            "차트 제목 추출",
            "수치 값 자동 계산"
        ]
    }


@router.post("/batch-detect", response_model=Dict[str, Any])
async def batch_detect_charts(
    files: List[UploadFile] = File(...),
    confidence_threshold: float = 0.5,
    max_files: int = 10
):
    """
    여러 이미지에서 일괄 차트 감지
    
    Args:
        files: 업로드된 이미지 파일들
        confidence_threshold: 차트 감지 신뢰도 임계값
        max_files: 최대 처리 파일 수
        
    Returns:
        각 파일별 차트 감지 결과
    """
    try:
        if len(files) > max_files:
            raise HTTPException(
                status_code=400, 
                detail=f"최대 {max_files}개 파일까지 처리 가능합니다"
            )
        
        results = {
            "success": True,
            "total_files": len(files),
            "processed_files": 0,
            "total_charts_detected": 0,
            "files": []
        }
        
        for i, file in enumerate(files):
            try:
                # 파일 처리
                contents = await file.read()
                nparr = np.frombuffer(contents, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if image is None:
                    file_result = {
                        "filename": file.filename,
                        "success": False,
                        "error": "이미지를 읽을 수 없습니다",
                        "charts": []
                    }
                else:
                    # 차트 감지
                    charts = chart_detector.detect_charts(image)
                    filtered_charts = [
                        chart for chart in charts 
                        if chart.confidence >= confidence_threshold
                    ]
                    
                    file_result = {
                        "filename": file.filename,
                        "success": True,
                        "image_size": f"{image.shape[1]}x{image.shape[0]}",
                        "charts_detected": len(filtered_charts),
                        "charts": [
                            {
                                "chart_id": j + 1,
                                "type": chart.chart_type,
                                "confidence": chart.confidence,
                                "data_points": len(chart.data_points),
                                "has_title": bool(chart.title),
                                "has_legend": chart.legend is not None
                            }
                            for j, chart in enumerate(filtered_charts)
                        ]
                    }
                    
                    results["total_charts_detected"] += len(filtered_charts)
                    results["processed_files"] += 1
                
                results["files"].append(file_result)
                
            except Exception as e:
                logger.error(f"파일 {file.filename} 처리 실패: {e}")
                results["files"].append({
                    "filename": file.filename,
                    "success": False,
                    "error": str(e),
                    "charts": []
                })
        
        return results
        
    except Exception as e:
        logger.error(f"일괄 차트 감지 실패: {e}")
        raise HTTPException(status_code=500, detail=f"일괄 처리 중 오류 발생: {str(e)}")


@router.get("/health")
async def health_check():
    """차트 감지 서비스 상태 확인"""
    return {
        "status": "healthy",
        "service": "chart_detection",
        "version": "1.0.0",
        "features": [
            "chart_detection",
            "data_point_extraction", 
            "visualization",
            "batch_processing"
        ]
    }