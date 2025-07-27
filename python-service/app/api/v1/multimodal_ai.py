#!/usr/bin/env python3
"""
멀티모달 AI API 엔드포인트
Multimodal AI API Endpoints

이미지+텍스트 동시 분석을 위한 RESTful API
비전-언어 모델 통합 및 지능형 문서 분류
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import tempfile
import os
import logging
from datetime import datetime

from app.services.multimodal_ai_service import multimodal_ai_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_document_multimodal(
    file: UploadFile = File(...),
    language: str = Form("kor"),
    analysis_depth: str = Form("comprehensive"),
    include_visual_features: bool = Form(True),
    include_classification: bool = Form(True)
):
    """
    멀티모달 문서 분석
    
    Args:
        file: 업로드된 이미지 파일
        language: 언어 코드 (kor, eng, chi_sim, jpn, etc.)
        analysis_depth: 분석 깊이 (basic, comprehensive, detailed)
        include_visual_features: 시각적 특징 포함 여부
        include_classification: 문서 분류 포함 여부
        
    Returns:
        멀티모달 분석 결과
    """
    temp_file_path = None
    
    try:
        # 파일 형식 검증
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 분석 깊이 검증
        if analysis_depth not in ["basic", "comprehensive", "detailed"]:
            raise HTTPException(status_code=400, detail="analysis_depth는 basic, comprehensive, detailed 중 하나여야 합니다")
        
        # 임시 파일 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        logger.info(f"멀티모달 분석 시작: {file.filename} (깊이: {analysis_depth})")
        
        # 멀티모달 분석 수행
        result = await multimodal_ai_service.analyze_document_multimodal(
            image_path=temp_file_path,
            language=language,
            analysis_depth=analysis_depth
        )
        
        # 응답 구성
        response = {
            "success": True,
            "file_info": {
                "filename": file.filename,
                "content_type": file.content_type,
                "language": language
            },
            "analysis_config": {
                "depth": analysis_depth,
                "include_visual_features": include_visual_features,
                "include_classification": include_classification,
                "timestamp": datetime.now().isoformat()
            },
            "results": {
                "document_type": result.document_type,
                "confidence": result.confidence,
                "recommendations": result.recommendations
            }
        }
        
        # 조건부 세부 정보 포함
        if include_visual_features:
            response["results"]["visual_features"] = result.visual_features
        
        if include_classification:
            response["results"]["classification"] = result.classification_results
        
        # 분석 깊이에 따른 추가 정보
        if analysis_depth in ["comprehensive", "detailed"]:
            response["results"]["combined_analysis"] = result.combined_analysis
        
        if include_visual_features and result.visual_features:
            response["results"]["textual_features"] = result.textual_features
        
        logger.info(f"멀티모달 분석 완료: {result.document_type} (신뢰도: {result.confidence:.2f})")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"멀티모달 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")


@router.post("/classify", response_model=Dict[str, Any])
async def classify_document_type(
    file: UploadFile = File(...),
    language: str = Form("kor"),
    confidence_threshold: float = Form(0.5)
):
    """
    문서 유형 분류
    
    Args:
        file: 업로드된 이미지 파일
        language: 언어 코드
        confidence_threshold: 신뢰도 임계값
        
    Returns:
        문서 분류 결과
    """
    temp_file_path = None
    
    try:
        # 파일 형식 검증
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 임시 파일 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        logger.info(f"문서 분류 시작: {file.filename}")
        
        # 기본 분석으로 분류 정보 획득
        result = await multimodal_ai_service.analyze_document_multimodal(
            image_path=temp_file_path,
            language=language,
            analysis_depth="basic"
        )
        
        classification = result.classification_results
        
        # 신뢰도 필터링
        high_confidence_types = {
            doc_type: score for doc_type, score in classification.get("confidence_scores", {}).items()
            if score >= confidence_threshold
        }
        
        response = {
            "success": True,
            "file_info": {
                "filename": file.filename,
                "language": language
            },
            "classification": {
                "primary_type": classification.get("primary_type", "unknown"),
                "secondary_types": classification.get("secondary_types", []),
                "confidence_scores": classification.get("confidence_scores", {}),
                "high_confidence_types": high_confidence_types,
                "key_indicators": classification.get("key_indicators", []),
                "processing_suggestions": classification.get("processing_suggestions", [])
            },
            "thresholds": {
                "confidence_threshold": confidence_threshold,
                "meets_threshold": len(high_confidence_types) > 0
            }
        }
        
        logger.info(f"문서 분류 완료: {classification.get('primary_type', 'unknown')}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 분류 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분류 중 오류 발생: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")


@router.post("/batch-analyze", response_model=Dict[str, Any])
async def batch_multimodal_analysis(
    files: List[UploadFile] = File(...),
    language: str = Form("kor"),
    analysis_depth: str = Form("basic"),
    max_files: int = Form(5)
):
    """
    멀티모달 배치 분석
    
    Args:
        files: 업로드된 이미지 파일들
        language: 언어 코드
        analysis_depth: 분석 깊이
        max_files: 최대 처리 파일 수
        
    Returns:
        배치 분석 결과
    """
    if len(files) > max_files:
        raise HTTPException(
            status_code=400, 
            detail=f"최대 {max_files}개 파일까지 처리 가능합니다"
        )
    
    results = {
        "success": True,
        "processing_info": {
            "total_files": len(files),
            "language": language,
            "analysis_depth": analysis_depth,
            "timestamp": datetime.now().isoformat()
        },
        "results": [],
        "summary": {
            "successful": 0,
            "failed": 0,
            "document_types": {},
            "average_confidence": 0.0
        }
    }
    
    confidences = []
    
    for i, file in enumerate(files):
        temp_file_path = None
        
        try:
            # 파일 형식 검증
            if not file.content_type or not file.content_type.startswith("image/"):
                results["results"].append({
                    "file_index": i,
                    "filename": file.filename,
                    "success": False,
                    "error": "지원하지 않는 파일 형식"
                })
                results["summary"]["failed"] += 1
                continue
            
            # 임시 파일 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            # 멀티모달 분석
            result = await multimodal_ai_service.analyze_document_multimodal(
                image_path=temp_file_path,
                language=language,
                analysis_depth=analysis_depth
            )
            
            # 결과 저장
            file_result = {
                "file_index": i,
                "filename": file.filename,
                "success": True,
                "analysis_result": {
                    "document_type": result.document_type,
                    "confidence": result.confidence,
                    "recommendations": result.recommendations[:3]  # 상위 3개만
                }
            }
            
            # 상세 정보 포함 (comprehensive 이상)
            if analysis_depth in ["comprehensive", "detailed"]:
                file_result["analysis_result"]["classification"] = result.classification_results
            
            results["results"].append(file_result)
            results["summary"]["successful"] += 1
            confidences.append(result.confidence)
            
            # 문서 타입 통계
            doc_type = result.document_type
            if doc_type in results["summary"]["document_types"]:
                results["summary"]["document_types"][doc_type] += 1
            else:
                results["summary"]["document_types"][doc_type] = 1
            
        except Exception as e:
            logger.error(f"파일 {file.filename} 분석 실패: {e}")
            results["results"].append({
                "file_index": i,
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
            results["summary"]["failed"] += 1
        
        finally:
            # 임시 파일 정리
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"임시 파일 삭제 실패: {e}")
    
    # 평균 신뢰도 계산
    if confidences:
        results["summary"]["average_confidence"] = sum(confidences) / len(confidences)
    
    logger.info(f"배치 멀티모달 분석 완료: {results['summary']['successful']}/{len(files)} 성공")
    
    return results


@router.post("/visual-features", response_model=Dict[str, Any])
async def extract_visual_features(
    file: UploadFile = File(...),
    feature_types: List[str] = Form(["layout", "structural", "text_regions"])
):
    """
    시각적 특징 추출
    
    Args:
        file: 업로드된 이미지 파일
        feature_types: 추출할 특징 유형 목록
        
    Returns:
        시각적 특징 추출 결과
    """
    temp_file_path = None
    
    try:
        # 파일 형식 검증
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 임시 파일 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        logger.info(f"시각적 특징 추출 시작: {file.filename}")
        
        # 시각적 특징 추출
        visual_features = await multimodal_ai_service._extract_visual_features(temp_file_path)
        
        # 요청된 특징 유형만 필터링
        filtered_features = {}
        for feature_type in feature_types:
            if feature_type in visual_features:
                filtered_features[feature_type] = visual_features[feature_type]
        
        response = {
            "success": True,
            "file_info": {
                "filename": file.filename,
                "content_type": file.content_type
            },
            "extraction_config": {
                "requested_features": feature_types,
                "timestamp": datetime.now().isoformat()
            },
            "visual_features": filtered_features,
            "feature_summary": {
                "total_features_extracted": len(filtered_features),
                "available_feature_types": list(visual_features.keys())
            }
        }
        
        logger.info(f"시각적 특징 추출 완료: {len(filtered_features)}개 특징")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시각적 특징 추출 실패: {e}")
        raise HTTPException(status_code=500, detail=f"특징 추출 중 오류 발생: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")


@router.get("/document-types", response_model=Dict[str, Any])
async def get_supported_document_types():
    """지원되는 문서 유형 조회"""
    try:
        service_info = multimodal_ai_service.get_service_info()
        
        # 문서 타입별 상세 정보
        document_types_info = {}
        for doc_type in service_info["supported_document_types"]:
            type_config = multimodal_ai_service.document_types.get(doc_type, {})
            document_types_info[doc_type] = {
                "name": doc_type.replace("_", " ").title(),
                "keywords": type_config.get("keywords", [])[:5],  # 상위 5개만
                "visual_patterns": type_config.get("visual_patterns", []),
                "confidence_threshold": type_config.get("confidence_threshold", 0.7)
            }
        
        return {
            "success": True,
            "supported_document_types": document_types_info,
            "total_types": len(document_types_info),
            "classification_info": {
                "method": "multimodal",
                "features_used": ["text_keywords", "visual_patterns", "layout_analysis"],
                "confidence_based": True
            }
        }
        
    except Exception as e:
        logger.error(f"문서 유형 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 유형 조회 실패: {str(e)}")


@router.get("/capabilities", response_model=Dict[str, Any])
async def get_service_capabilities():
    """서비스 기능 조회"""
    try:
        service_info = multimodal_ai_service.get_service_info()
        
        return {
            "success": True,
            "service_info": service_info,
            "api_endpoints": [
                {
                    "endpoint": "/analyze",
                    "method": "POST",
                    "description": "멀티모달 문서 분석",
                    "features": ["document_classification", "visual_analysis", "text_analysis"]
                },
                {
                    "endpoint": "/classify",
                    "method": "POST", 
                    "description": "문서 유형 분류",
                    "features": ["classification_only", "confidence_filtering"]
                },
                {
                    "endpoint": "/batch-analyze",
                    "method": "POST",
                    "description": "배치 멀티모달 분석",
                    "features": ["batch_processing", "summary_statistics"]
                },
                {
                    "endpoint": "/visual-features",
                    "method": "POST",
                    "description": "시각적 특징 추출",
                    "features": ["layout_analysis", "structural_detection", "text_regions"]
                }
            ],
            "performance_info": {
                "recommended_image_size": "최대 2MB",
                "supported_formats": ["PNG", "JPEG", "JPG"],
                "batch_processing_limit": 5,
                "processing_time": "이미지당 5-15초 (분석 깊이에 따라)"
            }
        }
        
    except Exception as e:
        logger.error(f"서비스 기능 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"기능 조회 실패: {str(e)}")


@router.get("/health")
async def multimodal_ai_health_check():
    """멀티모달 AI 서비스 상태 확인"""
    try:
        service_info = multimodal_ai_service.get_service_info()
        
        return {
            "status": "healthy",
            "service": "multimodal_ai",
            "version": service_info["version"],
            "capabilities": service_info["capabilities"],
            "models_status": service_info["models_available"],
            "supported_features": [
                "document_analysis",
                "visual_feature_extraction", 
                "text_analysis",
                "document_classification",
                "batch_processing",
                "multimodal_integration"
            ],
            "health_indicators": {
                "core_service": "operational",
                "visual_analysis": "operational",
                "text_processing": "operational",
                "classification": "operational"
            }
        }
        
    except Exception as e:
        logger.error(f"건강 상태 확인 실패: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }