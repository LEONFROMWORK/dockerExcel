"""
실시간 Excel 수식 검증 API
FastAPI 엔드포인트를 통한 formulas 라이브러리 기반 실시간 검증
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import tempfile
import os
from datetime import datetime

from app.services.realtime_formula_validator import (
    RealtimeFormulaValidator, 
    ValidationResult,
    get_validator
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/formula", tags=["Formula Validation"])

# Request/Response 모델들
class FormulaValidationRequest(BaseModel):
    formula: str = Field(..., description="검증할 Excel 수식")
    cell_address: str = Field(..., description="셀 주소 (예: A1, B2)")
    sheet_name: str = Field(default="Sheet1", description="시트 이름")
    context: Optional[Dict[str, Any]] = Field(default=None, description="셀 컨텍스트 데이터")

class BatchValidationRequest(BaseModel):
    changes: List[Dict[str, Any]] = Field(..., description="변경사항 목록")
    include_errors_simulation: bool = Field(default=True, description="오류 시뮬레이션 포함 여부")

class FormulaValidationResponse(BaseModel):
    valid: bool
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    calculated_value: Any = None
    formula_type: str
    dependencies: List[str] = []
    execution_time: float
    warnings: List[str] = []

class BatchValidationResponse(BaseModel):
    results: Dict[str, FormulaValidationResponse]
    summary: Dict[str, Any]
    execution_time: float

class ErrorSimulationResponse(BaseModel):
    formula: str
    potential_errors: List[Dict[str, Any]]
    risk_level: str

# API 엔드포인트들

@router.post("/validate", 
             response_model=FormulaValidationResponse,
             summary="단일 수식 실시간 검증")
async def validate_formula(request: FormulaValidationRequest):
    """
    단일 Excel 수식을 실시간으로 검증하고 계산합니다.
    
    - **formula**: 검증할 Excel 수식 (=으로 시작 안 해도 됨)
    - **cell_address**: 셀 주소 (A1, B2 등)
    - **sheet_name**: 시트 이름 (기본값: Sheet1)  
    - **context**: 참조되는 셀들의 값 (선택적)
    """
    try:
        validator = get_validator()
        
        # 컨텍스트가 제공된 경우 설정
        if request.context:
            validator.set_context(request.sheet_name, request.context)
        
        # 수식 검증 실행
        result = validator.validate_formula_realtime(
            request.formula,
            request.cell_address, 
            request.sheet_name
        )
        
        return FormulaValidationResponse(
            valid=result.valid,
            result=result.result,
            error=result.error,
            error_type=result.error_type,
            calculated_value=result.calculated_value,
            formula_type=result.formula_type,
            dependencies=result.dependencies or [],
            execution_time=result.execution_time,
            warnings=result.warnings or []
        )
        
    except Exception as e:
        logger.error(f"Formula validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"수식 검증 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/validate-batch",
             response_model=BatchValidationResponse, 
             summary="다중 변경사항 일괄 검증")
async def validate_batch_changes(request: BatchValidationRequest):
    """
    여러 변경사항을 일괄적으로 검증합니다.
    
    사용자가 여러 셀을 동시에 수정했을 때 모든 변경사항의 영향을 한 번에 분석합니다.
    """
    start_time = datetime.now()
    
    try:
        validator = get_validator()
        
        # 일괄 검증 실행
        results = validator.batch_validate_changes(request.changes)
        
        # 응답 모델로 변환
        response_results = {}
        for change_id, result in results.items():
            response_results[change_id] = FormulaValidationResponse(
                valid=result.valid,
                result=result.result,
                error=result.error,
                error_type=result.error_type,
                calculated_value=result.calculated_value,
                formula_type=result.formula_type,
                dependencies=result.dependencies or [],
                execution_time=result.execution_time,
                warnings=result.warnings or []
            )
        
        # 요약 정보 생성
        summary = generate_batch_summary(results, request.changes)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return BatchValidationResponse(
            results=response_results,
            summary=summary,
            execution_time=execution_time
        )
        
    except Exception as e:
        logger.error(f"Batch validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"일괄 검증 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/simulate-errors",
             response_model=ErrorSimulationResponse,
             summary="수식 오류 조건 시뮬레이션")
async def simulate_formula_errors(
    formula: str,
    sheet_name: str = "Sheet1",
    context: Optional[Dict[str, Any]] = None
):
    """
    주어진 수식에서 발생할 수 있는 오류 조건들을 시뮬레이션합니다.
    
    - Division by zero
    - Circular references  
    - Invalid references
    - Type mismatches
    """
    try:
        validator = get_validator()
        
        if context:
            validator.set_context(sheet_name, context)
        
        # 오류 시뮬레이션 실행
        potential_errors = validator.simulate_error_conditions(formula, sheet_name)
        
        # 위험도 계산
        risk_level = calculate_risk_level(potential_errors)
        
        return ErrorSimulationResponse(
            formula=formula,
            potential_errors=potential_errors,
            risk_level=risk_level
        )
        
    except Exception as e:
        logger.error(f"Error simulation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"오류 시뮬레이션 중 문제가 발생했습니다: {str(e)}"
        )

@router.post("/initialize-workbook",
             summary="워크북으로부터 검증기 초기화")
async def initialize_validator_from_workbook(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    업로드된 Excel 파일로부터 검증기를 초기화합니다.
    
    전체 워크북의 구조와 데이터를 분석하여 실시간 검증을 위한 컨텍스트를 구성합니다.
    """
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        validator = get_validator()
        
        # 워크북으로부터 초기화
        success = validator.initialize_from_openpyxl_workbook(tmp_file_path)
        
        # 백그라운드에서 임시 파일 삭제
        background_tasks.add_task(cleanup_temp_file, tmp_file_path)
        
        if success:
            return JSONResponse(
                content={
                    "success": True,
                    "message": "워크북이 성공적으로 초기화되었습니다",
                    "sheets": list(validator.context.keys()),
                    "total_cells": sum(len(sheet_data) for sheet_data in validator.context.values())
                }
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="워크북 초기화에 실패했습니다"
            )
            
    except Exception as e:
        logger.error(f"Workbook initialization failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"워크북 초기화 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/validator-status",
           summary="검증기 상태 확인")
async def get_validator_status():
    """
    현재 검증기의 상태와 로드된 데이터 정보를 반환합니다.
    """
    try:
        validator = get_validator()
        
        status = {
            "initialized": validator.xl_model is not None,
            "sheets_count": len(validator.context),
            "sheets": list(validator.context.keys()),
            "total_cells": sum(len(sheet_data) for sheet_data in validator.context.values()),
            "memory_usage": get_validator_memory_usage(validator)
        }
        
        return JSONResponse(content=status)
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"상태 확인 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/reset-validator",
             summary="검증기 초기화")
async def reset_validator():
    """
    검증기를 초기 상태로 리셋합니다.
    """
    try:
        global _validator_instance
        from app.services.realtime_formula_validator import _validator_instance
        _validator_instance = None
        
        return JSONResponse(
            content={
                "success": True,
                "message": "검증기가 성공적으로 리셋되었습니다"
            }
        )
        
    except Exception as e:
        logger.error(f"Validator reset failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"검증기 리셋 중 오류가 발생했습니다: {str(e)}"
        )

# 헬퍼 함수들

def generate_batch_summary(results: Dict[str, ValidationResult], changes: List[Dict]) -> Dict[str, Any]:
    """일괄 검증 결과 요약 생성"""
    total_changes = len(changes)
    valid_changes = sum(1 for result in results.values() if result.valid)
    invalid_changes = total_changes - valid_changes
    
    # 오류 유형별 집계
    error_types = {}
    formula_types = {}
    
    for result in results.values():
        if result.error_type:
            error_types[result.error_type] = error_types.get(result.error_type, 0) + 1
        if result.formula_type:
            formula_types[result.formula_type] = formula_types.get(result.formula_type, 0) + 1
    
    return {
        "total_changes": total_changes,
        "valid_changes": valid_changes,
        "invalid_changes": invalid_changes,
        "success_rate": (valid_changes / total_changes) * 100 if total_changes > 0 else 0,
        "error_types": error_types,
        "formula_types": formula_types,
        "requires_attention": invalid_changes > 0
    }

def calculate_risk_level(potential_errors: List[Dict]) -> str:
    """잠재적 오류 목록으로부터 위험도 계산"""
    if not potential_errors:
        return "low"
    
    high_risk_errors = [err for err in potential_errors if err.get('severity') == 'high']
    if high_risk_errors:
        return "high"
    
    medium_risk_errors = [err for err in potential_errors if err.get('severity') == 'medium']
    if len(medium_risk_errors) > 2:
        return "high"
    elif medium_risk_errors:
        return "medium"
    
    return "low"

def get_validator_memory_usage(validator: RealtimeFormulaValidator) -> Dict[str, Any]:
    """검증기 메모리 사용량 추정"""
    import sys
    
    try:
        context_size = sys.getsizeof(validator.context)
        model_size = sys.getsizeof(validator.xl_model) if validator.xl_model else 0
        
        return {
            "context_size_bytes": context_size,
            "model_size_bytes": model_size,
            "total_size_mb": (context_size + model_size) / (1024 * 1024)
        }
    except Exception:
        return {"error": "메모리 사용량 계산 실패"}

async def cleanup_temp_file(file_path: str):
    """임시 파일 정리"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

# Note: Exception handlers should be added to the main app, not router
# These will be moved to main.py if needed