"""
Excel 고급 기능 API (차트, 피벗테이블)
Excel Advanced Features API (Charts, Pivot Tables)
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form, Body
from fastapi.responses import FileResponse
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import tempfile
import os
import uuid
from datetime import datetime
import logging
import json

from ...services.excel_chart_analyzer import excel_chart_analyzer
from ...services.excel_pivot_analyzer import excel_pivot_analyzer

router = APIRouter()
logger = logging.getLogger(__name__)

class ChartConfig(BaseModel):
    sheet_name: str
    chart_type: str
    data_range: str
    chart_title: Optional[str] = None
    x_axis_title: Optional[str] = None
    y_axis_title: Optional[str] = None


# ==================== 차트 관련 엔드포인트 ====================

@router.post("/charts/analyze")
async def analyze_existing_charts(
    file: UploadFile = File(...)
):
    """기존 차트 분석"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        analysis_result = excel_chart_analyzer.analyze_existing_charts(tmp_file_path)
        
        return {
            "status": "success",
            "filename": file.filename,
            "analysis_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "chart_analysis": analysis_result
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@router.post("/charts/suggest")
async def suggest_optimal_charts(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Query(None, description="분석할 시트명 (전체 시트 분석시 생략)")
):
    """데이터 기반 최적 차트 제안"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        suggestions = excel_chart_analyzer.suggest_optimal_charts(tmp_file_path, sheet_name)
        
        return {
            "status": "success",
            "filename": file.filename,
            "sheet_name": sheet_name,
            "suggestion_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "suggestions": suggestions
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@router.post("/charts/create")
async def create_chart(
    file: UploadFile = File(...),
    chart_config: str = Form(...)
):
    """지정된 설정으로 차트 생성"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # JSON 문자열을 파싱
    try:
        config_dict = json.loads(chart_config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in chart_config")
    
    # 필수 파라미터 검증
    required_fields = ['sheet_name', 'chart_type', 'data_range']
    missing_fields = [field for field in required_fields if field not in config_dict]
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"필수 필드가 누락되었습니다: {', '.join(missing_fields)}"
        )
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        result = excel_chart_analyzer.create_chart(tmp_file_path, config_dict)
        
        if result['status'] == 'success':
            # 수정된 파일을 다운로드 가능하게 준비
            output_filename = f"chart_{file.filename}"
            result['download_info'] = {
                'filename': output_filename,
                'download_url': f"/api/v1/excel-advanced/download/{os.path.basename(result['output_file'])}"
            }
        
        return {
            "status": result['status'],
            "filename": file.filename,
            "chart_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@router.post("/charts/auto-generate")
async def auto_generate_charts(
    file: UploadFile = File(...),
    max_charts_per_sheet: int = Query(3, description="시트당 최대 차트 개수")
):
    """데이터 기반 자동 차트 생성"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        result = excel_chart_analyzer.auto_generate_charts(tmp_file_path, max_charts_per_sheet)
        
        if result['status'] == 'success':
            # 수정된 파일을 다운로드 가능하게 준비
            output_filename = f"auto_charts_{file.filename}"
            result['download_info'] = {
                'filename': output_filename,
                'download_url': f"/api/v1/excel-advanced/download/{os.path.basename(result['output_file'])}"
            }
        
        return {
            "status": result['status'],
            "filename": file.filename,
            "generation_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


# ==================== 피벗테이블 관련 엔드포인트 ====================

@router.post("/pivots/analyze")
async def analyze_existing_pivots(
    file: UploadFile = File(...)
):
    """기존 피벗테이블 분석"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        analysis_result = excel_pivot_analyzer.analyze_existing_pivots(tmp_file_path)
        
        return {
            "status": "success",
            "filename": file.filename,
            "analysis_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "pivot_analysis": analysis_result
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@router.post("/pivots/suggest")
async def suggest_optimal_pivots(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Query(None, description="분석할 시트명 (전체 시트 분석시 생략)")
):
    """데이터 기반 최적 피벗테이블 제안"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        suggestions = excel_pivot_analyzer.suggest_optimal_pivots(tmp_file_path, sheet_name)
        
        return {
            "status": "success",
            "filename": file.filename,
            "sheet_name": sheet_name,
            "suggestion_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "suggestions": suggestions
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@router.post("/pivots/create")
async def create_pivot_table(
    file: UploadFile = File(...),
    pivot_config: str = Form(...)
):
    """지정된 설정으로 피벗테이블 생성"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # JSON 문자열을 파싱
    try:
        config_dict = json.loads(pivot_config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in pivot_config")
    
    # 필수 파라미터 검증
    required_fields = ['source_sheet', 'row_fields', 'value_fields']
    missing_fields = [field for field in required_fields if field not in config_dict]
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"필수 필드가 누락되었습니다: {', '.join(missing_fields)}"
        )
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        result = excel_pivot_analyzer.create_pivot_table(tmp_file_path, config_dict)
        
        if result['status'] == 'success':
            # 수정된 파일을 다운로드 가능하게 준비
            output_filename = f"pivot_{file.filename}"
            result['download_info'] = {
                'filename': output_filename,
                'download_url': f"/api/v1/excel-advanced/download/{os.path.basename(result['output_file'])}"
            }
        
        return {
            "status": result['status'],
            "filename": file.filename,
            "pivot_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@router.post("/pivots/auto-generate")
async def auto_generate_pivots(
    file: UploadFile = File(...),
    max_pivots_per_sheet: int = Query(2, description="시트당 최대 피벗테이블 개수")
):
    """데이터 기반 자동 피벗테이블 생성"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        result = excel_pivot_analyzer.auto_generate_pivots(tmp_file_path, max_pivots_per_sheet)
        
        if result['status'] == 'success':
            # 수정된 파일을 다운로드 가능하게 준비
            output_filename = f"auto_pivots_{file.filename}"
            result['download_info'] = {
                'filename': output_filename,
                'download_url': f"/api/v1/excel-advanced/download/{os.path.basename(result['final_output_file'])}"
            }
        
        return {
            "status": result['status'],
            "filename": file.filename,
            "generation_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@router.post("/crosstabs/create")
async def create_cross_tabulation(
    file: UploadFile = File(...),
    crosstab_config: str = Form(...)
):
    """교차표 생성"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # JSON 문자열을 파싱
    try:
        config_dict = json.loads(crosstab_config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in crosstab_config")
    
    # 필수 파라미터 검증
    required_fields = ['source_sheet', 'row_field', 'col_field']
    missing_fields = [field for field in required_fields if field not in config_dict]
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"필수 필드가 누락되었습니다: {', '.join(missing_fields)}"
        )
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        result = excel_pivot_analyzer.create_cross_tabulation(tmp_file_path, config_dict)
        
        if result['status'] == 'success':
            # 수정된 파일을 다운로드 가능하게 준비
            output_filename = f"crosstab_{file.filename}"
            result['download_info'] = {
                'filename': output_filename,
                'download_url': f"/api/v1/excel-advanced/download/{os.path.basename(result['output_file'])}"
            }
        
        return {
            "status": result['status'],
            "filename": file.filename,
            "crosstab_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


# ==================== 통합 분석 엔드포인트 ====================

@router.post("/comprehensive-analysis")
async def comprehensive_analysis(
    file: UploadFile = File(...),
    include_charts: bool = Query(True, description="차트 분석 포함"),
    include_pivots: bool = Query(True, description="피벗테이블 분석 포함"),
    auto_generate_suggestions: bool = Query(True, description="자동 생성 제안 포함")
):
    """차트와 피벗테이블을 포함한 종합 분석"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        comprehensive_result = {
            "filename": file.filename,
            "analysis_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "analysis_summary": {}
        }
        
        # 차트 분석
        if include_charts:
            chart_analysis = excel_chart_analyzer.analyze_existing_charts(tmp_file_path)
            comprehensive_result["chart_analysis"] = chart_analysis
            comprehensive_result["analysis_summary"]["existing_charts"] = chart_analysis.get("total_charts", 0)
            
            if auto_generate_suggestions:
                chart_suggestions = excel_chart_analyzer.suggest_optimal_charts(tmp_file_path)
                comprehensive_result["chart_suggestions"] = chart_suggestions
                comprehensive_result["analysis_summary"]["chart_suggestions"] = chart_suggestions.get("total_suggestions", 0)
        
        # 피벗테이블 분석
        if include_pivots:
            pivot_analysis = excel_pivot_analyzer.analyze_existing_pivots(tmp_file_path)
            comprehensive_result["pivot_analysis"] = pivot_analysis
            comprehensive_result["analysis_summary"]["existing_pivots"] = pivot_analysis.get("total_pivots", 0)
            
            if auto_generate_suggestions:
                pivot_suggestions = excel_pivot_analyzer.suggest_optimal_pivots(tmp_file_path)
                comprehensive_result["pivot_suggestions"] = pivot_suggestions
                comprehensive_result["analysis_summary"]["pivot_suggestions"] = pivot_suggestions.get("total_suggestions", 0)
        
        # 전체 권장사항 생성
        overall_recommendations = []
        
        if include_charts and comprehensive_result.get("chart_analysis", {}).get("total_charts", 0) == 0:
            overall_recommendations.append("데이터 시각화 개선을 위해 차트 추가를 고려해보세요")
        
        if include_pivots and comprehensive_result.get("pivot_analysis", {}).get("total_pivots", 0) == 0:
            overall_recommendations.append("데이터 요약 분석을 위해 피벗테이블 생성을 고려해보세요")
        
        if auto_generate_suggestions:
            total_suggestions = (
                comprehensive_result.get("chart_suggestions", {}).get("total_suggestions", 0) +
                comprehensive_result.get("pivot_suggestions", {}).get("total_suggestions", 0)
            )
            if total_suggestions > 0:
                overall_recommendations.append(f"총 {total_suggestions}개의 자동 생성 제안이 있습니다")
        
        comprehensive_result["overall_recommendations"] = overall_recommendations
        
        return {
            "status": "success",
            "comprehensive_analysis": comprehensive_result
        }
        
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@router.get("/download/{file_id}")
async def download_processed_file(file_id: str):
    """처리된 Excel 파일 다운로드"""
    
    file_path = f"/tmp/{file_id}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
    
    return FileResponse(
        path=file_path,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        filename=f"processed_{file_id}"
    )