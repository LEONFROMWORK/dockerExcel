"""
Excel analysis API endpoints
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import tempfile
import os
from typing import Dict, Any
import logging

from app.core.database import get_db
from app.core.config import settings
from app.core.i18n_dependencies import get_i18n_context, I18nContext
from app.services.excel_analyzer import excel_analyzer
from app.services.openai_service import openai_service
from app.services.vector_search import vector_search_service
from app.services.excel_chart_analyzer import excel_chart_analyzer
from app.services.excel_pivot_analyzer import excel_pivot_analyzer
from app.services.template_selection_service import template_selection_service
from app.services.excel_auto_fixer import ExcelAutoFixer
from app.services.circular_reference_detector import CircularReferenceDetector
from app.services.fast_formula_fixer import FastFormulaFixer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze")
async def analyze_excel_file(
    file: UploadFile = File(...),
    user_query: str = None,
    db: AsyncSession = Depends(get_db),
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    Analyze an Excel file and optionally answer a specific query
    """
    # Validate file type
    if not any(file.filename.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        error_message = i18n.get_error_message(
            "invalid_file_type", 
            extensions=", ".join(settings.ALLOWED_EXTENSIONS)
        )
        raise HTTPException(status_code=400, detail=error_message)
    
    # Validate file size
    if file.size > settings.MAX_UPLOAD_SIZE:
        error_message = i18n.get_error_message(
            "file_too_large", 
            max_size=settings.MAX_UPLOAD_SIZE
        )
        raise HTTPException(status_code=400, detail=error_message)
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # Analyze file structure
        logger.info(f"Analyzing file: {file.filename}")
        analysis_result = await excel_analyzer.analyze_file(tmp_path)
        
        # Get AI insights
        ai_analysis = await openai_service.analyze_excel_content(
            analysis_result,
            user_query
        )
        
        # 고급 기능 분석 추가
        advanced_analysis = {}
        
        # 차트 제안
        chart_suggestions = excel_chart_analyzer.suggest_optimal_charts(tmp_path)
        advanced_analysis['chart_suggestions'] = chart_suggestions
        
        # 피벗테이블 제안
        pivot_suggestions = excel_pivot_analyzer.suggest_optimal_pivots(tmp_path)
        advanced_analysis['pivot_suggestions'] = pivot_suggestions
        
        # 템플릿 추천 (사용자 쿼리가 있는 경우)
        if user_query:
            template_recommendations = await template_selection_service.recommend_templates(
                user_intent=user_query,
                excel_file_path=tmp_path,
                max_recommendations=3
            )
            advanced_analysis['template_recommendations'] = template_recommendations
        
        # Index content for future searches
        content_summary = _create_content_summary(analysis_result)
        await vector_search_service.index_document(
            document_id=file.filename,
            document_type="excel_analysis",
            content=content_summary,
            metadata={
                "filename": file.filename,
                "sheets": list(analysis_result["sheets"].keys()),
                "has_errors": analysis_result["summary"]["has_errors"]
            },
            db=db
        )
        
        return {
            "status": "success",
            "message": i18n.get_text("file.analysis_complete"),
            "language": i18n.language,
            "filename": file.filename,
            "file_analysis": analysis_result,
            "ai_insights": ai_analysis,
            "advanced_analysis": advanced_analysis,
            "user_query": user_query,
            "localized_labels": {
                "charts": i18n.get_text("excel.charts.title"),
                "pivot_tables": i18n.get_text("excel.pivot.title"),
                "templates": i18n.get_text("templates.title")
            }
        }
        
    except Exception as e:
        logger.error(f"Error analyzing Excel file: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/extract-formulas")
async def extract_formulas(
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Extract all formulas from an Excel file
    """
    # Validate file type
    if not any(file.filename.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {settings.ALLOWED_EXTENSIONS}"
        )
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # Extract formulas
        formulas = await excel_analyzer.extract_formulas(tmp_path)
        
        # Count total formulas
        total_formulas = sum(len(sheet_formulas) for sheet_formulas in formulas.values())
        
        return {
            "filename": file.filename,
            "total_formulas": total_formulas,
            "formulas_by_sheet": formulas
        }
        
    except Exception as e:
        logger.error(f"Error extracting formulas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/validate-formula")
async def validate_formula(
    formula: str,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Validate and explain an Excel formula
    """
    if not formula.startswith("="):
        formula = "=" + formula
    
    # Get AI explanation
    prompt = f"Explain this Excel formula and check for any issues: {formula}"
    if context:
        prompt += f"\nContext: {context}"
    
    solution = await openai_service.generate_excel_solution(prompt, context)
    
    return {
        "formula": formula,
        "validation": solution,
        "context": context
    }


@router.post("/auto-fix")
async def auto_fix_excel_file(
    file: UploadFile = File(...),
    fix_formulas: bool = True,
    fix_data_quality: bool = True,
    fix_structural: bool = True,
    fix_formatting: bool = True,
    save_fixed_file: bool = True,
    db: AsyncSession = Depends(get_db),
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    자동으로 Excel 파일의 모든 오류를 감지하고 수정
    """
    # 파일 타입 검증
    if not any(file.filename.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        error_message = i18n.get_error_message(
            "invalid_file_type", 
            extensions=", ".join(settings.ALLOWED_EXTENSIONS)
        )
        raise HTTPException(status_code=400, detail=error_message)
    
    # 파일 크기 검증
    if file.size > settings.MAX_UPLOAD_SIZE:
        error_message = i18n.get_error_message(
            "file_too_large", 
            max_size=settings.MAX_UPLOAD_SIZE
        )
        raise HTTPException(status_code=400, detail=error_message)
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # 자동 수정 옵션 설정
        fix_options = {
            'fix_formulas': fix_formulas,
            'fix_data_quality': fix_data_quality,
            'fix_structural': fix_structural,
            'fix_formatting': fix_formatting,
            'save_fixed_file': save_fixed_file,
            'revalidate': True
        }
        
        # 자동 수정 실행
        logger.info(f"Starting auto-fix for file: {file.filename}")
        auto_fixer = ExcelAutoFixer()
        fix_result = await auto_fixer.auto_fix_file(tmp_path, fix_options)
        
        # 결과 요약
        response = {
            "status": "success",
            "message": i18n.get_text("file.auto_fix_complete"),
            "language": i18n.language,
            "filename": file.filename,
            "summary": fix_result['summary'],
            "performance": fix_result['performance'],
            "details": {
                "original_errors": fix_result['original_errors'].get('summary', {}),
                "fixed_errors": {
                    "formulas": fix_result['fixed_errors'].get('formulas', {}).get('fixed_formulas', []),
                    "data_quality": fix_result['fixed_errors'].get('data_quality', {}).get('fixes_applied', []),
                    "structural": fix_result['fixed_errors'].get('structural', {}).get('fixes_applied', []),
                    "formatting": fix_result['fixed_errors'].get('formatting', {}).get('fixes_applied', [])
                },
                "remaining_errors": len(fix_result.get('unfixed_errors', []))
            }
        }
        
        # 수정된 파일 경로 추가
        if 'fixed_file_path' in fix_result:
            response['fixed_file_path'] = fix_result['fixed_file_path']
        
        # 벡터 DB에 인덱싱
        await vector_search_service.index_document(
            document_id=f"{file.filename}_autofix",
            document_type="excel_autofix",
            content=f"Auto-fixed Excel file: {file.filename}. Fixed {fix_result['summary']['total_errors_fixed']} errors.",
            metadata={
                "filename": file.filename,
                "total_errors_fixed": fix_result['summary']['total_errors_fixed'],
                "fix_rate": fix_result['summary']['fix_rate']
            },
            db=db
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in auto-fix: {str(e)}")
        error_message = i18n.get_error_message("api_error")
        raise HTTPException(status_code=500, detail=error_message)
    finally:
        # 임시 파일 정리
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _create_content_summary(analysis: Dict[str, Any]) -> str:
    """Create a searchable summary of Excel file content"""
    parts = [f"Excel file with {analysis['summary']['total_sheets']} sheets"]
    
    for sheet_name, sheet_data in analysis["sheets"].items():
        parts.append(f"\nSheet '{sheet_name}':")
        
        if "columns" in sheet_data:
            parts.append(f"Columns: {', '.join(sheet_data['columns'][:10])}")
        
        if "data_quality_issues" in sheet_data:
            parts.append(f"Issues found: {len(sheet_data['data_quality_issues'])}")
        
        if sheet_data.get("formula_count", 0) > 0:
            parts.append(f"Contains {sheet_data['formula_count']} formulas")
    
    if analysis["summary"]["has_errors"]:
        parts.append(f"\nTotal errors found: {analysis['summary']['total_errors']}")
    
    return " ".join(parts)


@router.post("/detect-circular-references")
async def detect_circular_references(
    file_path: str,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    Detect circular references in Excel file using advanced graph analysis
    """
    try:
        import openpyxl
        
        # Load workbook
        workbook = openpyxl.load_workbook(file_path, data_only=False)
        
        # Initialize detector
        detector = CircularReferenceDetector()
        
        # Analyze workbook
        circular_chains = detector.analyze_workbook(workbook)
        
        # Convert to JSON-serializable format
        results = []
        for chain in circular_chains:
            results.append({
                "cells": chain.cells,
                "chain_type": chain.chain_type,
                "severity": chain.severity,
                "description": chain.description,
                "break_suggestions": chain.break_suggestions
            })
        
        return {
            "circular_references": results,
            "total_found": len(results),
            "message": i18n.get_message("circular_references_detected", count=len(results))
        }
        
    except Exception as e:
        logger.error(f"Circular reference detection failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=i18n.get_error_message("analysis_failed", error=str(e))
        )


@router.post("/fix-formula")
async def fix_formula(
    formula: str,
    error_type: str,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    Fix a formula error using FastFormulaFixer
    """
    try:
        # Initialize fixer
        fixer = FastFormulaFixer()
        
        # Map error description to error type
        error_mapping = {
            "#DIV/0!": "#DIV/0!",
            "#N/A": "#N/A",
            "#NAME?": "#NAME?",
            "#REF!": "#REF!",
            "#VALUE!": "#VALUE!",
            "#NUM!": "#NUM!",
            "#NULL!": "#NULL!",
            "#SPILL!": "#SPILL!",
            "#CALC!": "#CALC!"
        }
        
        # Find matching error type
        detected_error = None
        for error, code in error_mapping.items():
            if error in error_type:
                detected_error = code
                break
        
        if not detected_error:
            detected_error = "#VALUE!"  # Default
        
        # Fix formula
        result = fixer.fix_formula(formula, detected_error)
        
        return {
            "original_formula": formula,
            "fixed_formula": result.fixed_formula,
            "confidence": result.confidence,
            "explanation": result.explanation,
            "error_type": detected_error
        }
        
    except Exception as e:
        logger.error(f"Formula fix failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=i18n.get_error_message("formula_fix_failed", error=str(e))
        )


@router.post("/update-cell")
async def update_cell(
    file_path: str,
    location: str,
    value: str,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    Update a specific cell in Excel file
    """
    try:
        import openpyxl
        
        # Load workbook
        workbook = openpyxl.load_workbook(file_path)
        
        # Parse location (e.g., "Sheet1!A1" or "A1")
        if "!" in location:
            sheet_name, cell_ref = location.split("!", 1)
            sheet = workbook[sheet_name]
        else:
            sheet = workbook.active
            cell_ref = location
        
        # Update cell
        sheet[cell_ref] = value
        
        # Save workbook
        workbook.save(file_path)
        workbook.close()
        
        return {
            "success": True,
            "location": location,
            "new_value": value,
            "message": i18n.get_message("cell_updated", location=location)
        }
        
    except Exception as e:
        logger.error(f"Cell update failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=i18n.get_error_message("cell_update_failed", error=str(e))
        )


@router.post("/remove-duplicates")
async def remove_duplicates(
    file_path: str,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    Remove duplicate rows from Excel file
    """
    try:
        import pandas as pd
        
        # Read Excel file
        df = pd.read_excel(file_path)
        
        # Count duplicates before removal
        duplicates_before = df.duplicated().sum()
        
        # Remove duplicates
        df_cleaned = df.drop_duplicates()
        
        # Save back to Excel
        df_cleaned.to_excel(file_path, index=False)
        
        return {
            "success": True,
            "duplicates_removed": duplicates_before,
            "rows_before": len(df),
            "rows_after": len(df_cleaned),
            "message": i18n.get_message("duplicates_removed", count=duplicates_before)
        }
        
    except Exception as e:
        logger.error(f"Duplicate removal failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=i18n.get_error_message("duplicate_removal_failed", error=str(e))
        )


@router.post("/optimize-formulas")
async def optimize_formulas(
    file_path: str,
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    Optimize formulas in Excel file for better performance
    """
    try:
        import openpyxl
        
        # Load workbook
        workbook = openpyxl.load_workbook(file_path, data_only=False)
        
        # Initialize fixer for optimization
        fixer = FastFormulaFixer()
        
        optimized_count = 0
        optimization_details = []
        
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.data_type == 'f' and cell.value:
                        original_formula = cell.value
                        
                        # Check if formula can be optimized
                        if fixer._is_inefficient_formula(original_formula):
                            optimized = fixer._optimize_formula(original_formula)
                            
                            if optimized != original_formula:
                                cell.value = optimized
                                optimized_count += 1
                                
                                optimization_details.append({
                                    "location": f"{sheet_name}!{cell.coordinate}",
                                    "original": original_formula,
                                    "optimized": optimized
                                })
        
        # Save workbook
        workbook.save(file_path)
        workbook.close()
        
        return {
            "success": True,
            "formulas_optimized": optimized_count,
            "details": optimization_details[:10],  # First 10 optimizations
            "message": i18n.get_message("formulas_optimized", count=optimized_count)
        }
        
    except Exception as e:
        logger.error(f"Formula optimization failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=i18n.get_error_message("optimization_failed", error=str(e))
        )


class CellVerificationRequest(BaseModel):
    file_id: str
    cell_address: str

@router.post("/verify-cell-position")
async def verify_cell_position(
    request: CellVerificationRequest,
    db: AsyncSession = Depends(get_db),
    i18n: I18nContext = Depends(get_i18n_context)
) -> Dict[str, Any]:
    """
    Verify cell position by analyzing the same cell in Python
    Used for testing coordinate consistency between ExcelJS and Python
    """
    try:
        # TODO: 실제 파일 경로를 file_id로부터 가져오는 로직 구현
        # 현재는 테스트용으로 하드코딩
        if request.file_id == "36":
            file_path = "/Users/kevin/Desktop/사고조사.xlsx"
        else:
            # 기본 테스트 파일 사용
            file_path = "/Users/kevin/Desktop/사고조사.xlsx"
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}"
            )
        
        # openpyxl로 Excel 파일 읽기
        import openpyxl
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        worksheet = workbook.active
        
        # 셀 주소를 좌표로 변환 (예: "C3" -> row=3, col=3)
        try:
            cell = worksheet[request.cell_address]
            python_address = cell.coordinate
            python_value = cell.value
            python_row = cell.row
            python_col = cell.column
            
            # 셀 타입 판단
            if python_value is None:
                cell_type = "empty"
            elif isinstance(python_value, (int, float)):
                cell_type = "number"
            elif isinstance(python_value, str):
                cell_type = "text"
            else:
                cell_type = "other"
            
            workbook.close()
            
            return {
                "success": True,
                "address": python_address,
                "value": python_value,
                "row": python_row,
                "column": python_col,
                "type": cell_type,
                "requested_address": request.cell_address,
                "match": request.cell_address == python_address
            }
            
        except Exception as cell_error:
            workbook.close()
            return {
                "success": False,
                "error": f"Cell access error: {str(cell_error)}",
                "address": "ERROR",
                "value": None,
                "type": "error",
                "requested_address": request.cell_address,
                "match": False
            }
        
    except Exception as e:
        logger.error(f"Cell position verification failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed: {str(e)}"
        )