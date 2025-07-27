"""
이미지를 Excel로 변환하고 오류 감지를 통합하는 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Dict, Any, List, Optional
import tempfile
import os
import logging
from datetime import datetime

from app.services.image_excel_integration import ImageExcelIntegrationService

logger = logging.getLogger(__name__)
router = APIRouter()

# 서비스 인스턴스 생성
image_integration_service = ImageExcelIntegrationService()


@router.post("/convert-and-analyze")
async def convert_image_and_analyze(
    file: UploadFile = File(...),
    output_format: str = Query("xlsx", regex="^(xlsx|xls)$"),
    detect_errors: bool = Query(True),
    session_id: Optional[str] = Query(None),
    auto_fix: bool = Query(False),
    ai_consultation: bool = Query(False),
    question: Optional[str] = Query(None),
    temperature: Optional[float] = Query(None, ge=0.0, le=2.0, description="Temperature for AI model (0.0-2.0)")
) -> Dict[str, Any]:
    """
    이미지를 Excel로 변환하고 오류를 감지하는 통합 API
    
    Parameters:
    - file: 업로드된 이미지 파일
    - output_format: 출력 Excel 형식 (xlsx 또는 xls)
    - detect_errors: 오류 감지 수행 여부
    - session_id: WebSocket 세션 ID (실시간 업데이트용)
    - auto_fix: 자동 수정 가능한 오류 자동 수정 여부
    - ai_consultation: AI 상담 응답 생성 여부
    - question: AI 상담을 위한 사용자 질문
    """
    
    # 파일 유효성 검사
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
        )
    
    # 파일 크기 검사 (10MB 제한)
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    if file_size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="파일 크기가 10MB를 초과합니다."
        )
    
    # 임시 파일로 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        logger.info(f"이미지 변환 시작: {file.filename}")
        
        # 이미지를 Excel로 변환하고 오류 감지
        result = await image_integration_service.process_image_with_error_detection(
            image_path=tmp_path,
            output_format=output_format,
            detect_errors=detect_errors
        )
        
        # 자동 수정 옵션이 활성화된 경우
        if auto_fix and result["status"] == "success" and result.get("error_detection"):
            error_detection = result["error_detection"]
            if error_detection.get("summary", {}).get("auto_fixable", 0) > 0:
                # 자동 수정 가능한 오류들 수정
                auto_fixable_errors = [
                    error for error in error_detection.get("errors", [])
                    if error.get("is_auto_fixable", False)
                ]
                
                if auto_fixable_errors:
                    from app.services.fixing.integrated_error_fixer import IntegratedErrorFixer
                    fixer = IntegratedErrorFixer()
                    
                    fix_result = await fixer.fix_batch(
                        errors=auto_fixable_errors,
                        strategy="safe"
                    )
                    
                    result["auto_fix_result"] = fix_result
        
        # AI 상담 응답 생성
        ai_response = None
        if ai_consultation and result["status"] == "success":
            try:
                from app.services.openai_service import OpenAIService
                openai_service = OpenAIService()
                
                # OCR 결과에서 컨텍스트 추출
                image_analysis = result.get("image_analysis", {})
                excel_conversion = result.get("excel_conversion", {})
                error_detection = result.get("error_detection", {})
                
                # AI 상담용 컨텍스트 구성
                context_data = {
                    "ocr_confidence": image_analysis.get('confidence', 0),
                    "ocr_method": image_analysis.get('ocr_method', 'unknown'),
                    "detected_language": image_analysis.get('detected_language', 'unknown'),
                    "total_cells": excel_conversion.get('total_cells', 0),
                    "total_errors": error_detection.get("summary", {}).get("total_errors", 0),
                    "error_types": error_detection.get("summary", {}).get("error_types", []),
                    "has_structured_data": excel_conversion.get('total_cells', 0) > 0
                }
                
                # 사용자 질문이 없는 경우 기본 분석 질문
                user_question = question or "이 이미지의 내용을 분석하고 Excel 데이터에 대한 인사이트를 제공해주세요."
                
                # AI 프롬프트 구성
                system_prompt = """당신은 Excel 전문가 AI 어시스턴트입니다. 이미지에서 추출된 OCR 분석 결과를 바탕으로 전문적인 조언을 제공합니다.
                
항상 사용자의 언어로 응답하세요 (한국어 질문에는 한국어로, 영어 질문에는 영어로).
Excel 데이터의 구조, 품질, 개선사항에 대해 구체적이고 실용적인 조언을 제공하세요."""
                
                user_prompt = f"""{user_question}

[OCR 분석 결과]
- 신뢰도: {context_data['ocr_confidence']:.1%}
- 처리 방법: {context_data['ocr_method']}
- 감지된 언어: {context_data['detected_language']}
- 추출된 데이터 셀 수: {context_data['total_cells']}개
- 감지된 오류 수: {context_data['total_errors']}개
- 오류 유형: {', '.join(context_data['error_types']) if context_data['error_types'] else '없음'}
- 구조화된 데이터: {'예' if context_data['has_structured_data'] else '아니오'}

위 분석 결과를 바탕으로 이미지의 내용과 Excel 데이터에 대한 전문적인 인사이트를 제공해주세요."""
                
                # AI 응답 생성
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                ai_response = await openai_service.chat_completion(
                    messages=messages,
                    temperature=temperature or 0.1,  # Use provided temperature or default to 0.1
                    max_tokens=1500
                )
                
                logger.info("AI 상담 응답 생성 완료")
                
            except Exception as e:
                logger.error(f"AI 상담 응답 생성 오류: {str(e)}")
                ai_response = "AI 상담 응답 생성 중 오류가 발생했습니다. 기본 분석 결과를 참고해주세요."
        
        # 응답 데이터 구성
        response_data = {
            "status": result["status"],
            "filename": file.filename,
            "file_size": file_size,
            "processing_time": result.get("processing_time", 0),
            "excel_file": result.get("excel_conversion", {}).get("file_path"),
            "image_analysis": result.get("image_analysis", {}),
            "excel_conversion": result.get("excel_conversion", {}),
            "error_detection": result.get("error_detection", {}),
            "auto_fix_result": result.get("auto_fix_result", {}),
            "ai_consultation": {
                "enabled": ai_consultation,
                "question": question,
                "response": ai_response
            } if ai_consultation else None,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"이미지 처리 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"이미지 처리 중 오류가 발생했습니다: {str(e)}"
        )
    finally:
        # 임시 파일 정리
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.post("/batch-convert")
async def batch_convert_images(
    files: List[UploadFile] = File(...),
    merge_strategy: str = Query("separate_sheets", regex="^(separate_sheets|single_sheet|separate_files)$"),
    output_format: str = Query("xlsx", regex="^(xlsx|xls)$"),
    detect_errors: bool = Query(True),
    session_id: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    여러 이미지를 일괄 변환하고 오류를 감지하는 API
    
    Parameters:
    - files: 업로드된 이미지 파일들
    - merge_strategy: 병합 전략 (separate_sheets, single_sheet, separate_files)
    - output_format: 출력 Excel 형식
    - detect_errors: 오류 감지 수행 여부
    - session_id: WebSocket 세션 ID
    """
    
    if not files:
        raise HTTPException(
            status_code=400,
            detail="최소 하나 이상의 파일을 업로드해주세요."
        )
    
    if len(files) > 20:
        raise HTTPException(
            status_code=400,
            detail="한 번에 최대 20개의 파일만 처리할 수 있습니다."
        )
    
    # 임시 파일들 저장
    temp_paths = []
    valid_files = []
    
    try:
        for file in files:
            # 파일 확장자 검사
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}:
                logger.warning(f"지원하지 않는 파일 형식 건너뜀: {file.filename}")
                continue
            
            # 파일 읽기 및 크기 검사
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:
                logger.warning(f"파일 크기 초과 건너뜀: {file.filename}")
                continue
            
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                tmp_file.write(content)
                temp_paths.append(tmp_file.name)
                valid_files.append(file.filename)
        
        if not temp_paths:
            raise HTTPException(
                status_code=400,
                detail="처리 가능한 유효한 이미지 파일이 없습니다."
            )
        
        logger.info(f"일괄 변환 시작: {len(temp_paths)}개 파일")
        
        # 일괄 처리
        result = await image_integration_service.batch_process_images(
            image_paths=temp_paths,
            merge_strategy=merge_strategy,
            detect_errors=detect_errors
        )
        
        # 응답 데이터 구성
        response_data = {
            "status": result["status"],
            "total_files": len(files),
            "valid_files": len(valid_files),
            "processed_files": result["successful"],
            "failed_files": result["failed"],
            "merge_strategy": merge_strategy,
            "merged_file": result.get("merged_file"),
            "error_detection": result.get("error_detection"),
            "individual_results": [
                {
                    "filename": valid_files[i] if i < len(valid_files) else f"file_{i}",
                    "status": res.get("status") if isinstance(res, dict) else "error",
                    "errors": res.get("error_detection", {}).get("summary", {}).get("total_errors", 0) if isinstance(res, dict) else 0
                }
                for i, res in enumerate(result.get("individual_results", []))
            ],
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"일괄 처리 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"일괄 처리 중 오류가 발생했습니다: {str(e)}"
        )
    finally:
        # 임시 파일들 정리
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

@router.get("/supported-formats")
async def get_supported_formats() -> Dict[str, Any]:
    """지원하는 이미지 형식 및 기능 정보 조회"""
    return {
        "supported_image_formats": [
            {
                "extension": ".png",
                "mime_type": "image/png",
                "description": "Portable Network Graphics"
            },
            {
                "extension": ".jpg",
                "mime_type": "image/jpeg",
                "description": "JPEG Image"
            },
            {
                "extension": ".jpeg",
                "mime_type": "image/jpeg",
                "description": "JPEG Image"
            },
            {
                "extension": ".bmp",
                "mime_type": "image/bmp",
                "description": "Bitmap Image"
            },
            {
                "extension": ".tiff",
                "mime_type": "image/tiff",
                "description": "Tagged Image File Format"
            },
            {
                "extension": ".gif",
                "mime_type": "image/gif",
                "description": "Graphics Interchange Format"
            }
        ],
        "supported_excel_formats": ["xlsx", "xls"],
        "features": {
            "ocr": {
                "tier2": "PaddleOCR (한국어 지원)",
                "tier3": "OpenAI Vision API"
            },
            "error_detection": {
                "formula_errors": ["#DIV/0!", "#N/A", "#NAME?", "#REF!", "#VALUE!"],
                "data_quality": ["중복", "누락", "타입 불일치", "이상치"],
                "structure": ["병합 셀", "빈 행/열", "숨겨진 데이터"]
            },
            "auto_fix": {
                "supported": True,
                "strategies": ["safe", "aggressive"]
            }
        },
        "limits": {
            "max_file_size_mb": 10,
            "max_batch_files": 20,
            "max_cells_per_sheet": 1000000
        }
    }

@router.post("/analyze-image-type")
async def analyze_image_type(
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """이미지 타입을 분석하여 최적의 처리 방법 제안"""
    
    # 파일 유효성 검사
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}:
        raise HTTPException(
            status_code=400,
            detail="지원하지 않는 파일 형식입니다."
        )
    
    # 임시 파일로 저장
    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # 이미지 분석 (타입 감지만)
        from PIL import Image
        import numpy as np
        
        image = Image.open(tmp_path)
        image_array = np.array(image)
        
        # 간단한 이미지 타입 감지
        service = ImageExcelIntegrationService()
        image_type = await service._detect_image_type(image_array)
        
        # 처리 권장사항
        recommendations = {
            "table": {
                "recommended_method": "OCR",
                "confidence": "high",
                "tips": ["테이블 경계가 명확한지 확인", "텍스트가 선명한지 확인"]
            },
            "chart": {
                "recommended_method": "Vision API",
                "confidence": "medium",
                "tips": ["차트 레이블이 명확한지 확인", "데이터 포인트가 구별되는지 확인"]
            },
            "form": {
                "recommended_method": "OCR + Structure Analysis",
                "confidence": "medium",
                "tips": ["필드 레이블이 명확한지 확인", "입력값이 읽기 쉬운지 확인"]
            }
        }
        
        return {
            "filename": file.filename,
            "image_info": {
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "format": image.format
            },
            "detected_type": image_type,
            "recommendation": recommendations.get(image_type, {
                "recommended_method": "Auto",
                "confidence": "low",
                "tips": ["자동 감지 모드 사용 권장"]
            }),
            "processing_suggestion": f"이 이미지는 {image_type} 타입으로 감지되었습니다."
        }
        
    except Exception as e:
        logger.error(f"이미지 타입 분석 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"이미지 타입 분석 중 오류가 발생했습니다: {str(e)}"
        )
    finally:
        # 임시 파일 정리
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)