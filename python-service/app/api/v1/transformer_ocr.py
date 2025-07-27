#!/usr/bin/env python3
"""
트랜스포머 기반 OCR API 엔드포인트 
Transformer-based OCR API Endpoints

BERT/GPT 기반 문맥 이해 OCR을 위한 RESTful API
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import tempfile
import os
import logging
from datetime import datetime

from app.services.transformer_ocr_service import transformer_ocr_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/process", response_model=Dict[str, Any])
async def process_with_transformer_ocr(
    file: UploadFile = File(...),
    language: str = Form("kor"),
    use_context: bool = Form(True),
    model_preference: str = Form("auto")
):
    """
    트랜스포머 기반 OCR 처리
    
    Args:
        file: 업로드된 이미지 파일
        language: 언어 코드 (kor, eng, chi_sim, jpn, etc.)
        use_context: 문맥 기반 교정 사용 여부
        model_preference: 모델 선택 (auto, bert, openai, rule_based)
        
    Returns:
        문맥 기반 OCR 결과
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
        
        logger.info(f"트랜스포머 OCR 처리 시작: {file.filename} ({language})")
        
        # 트랜스포머 OCR 처리
        result = await transformer_ocr_service.process_with_context(
            image_path=temp_file_path,
            language=language,
            use_context=use_context,
            model_preference=model_preference
        )
        
        # 결과 구성
        response = {
            "success": True,
            "file_info": {
                "filename": file.filename,
                "content_type": file.content_type,
                "language": language
            },
            "processing_info": {
                "use_context": use_context,
                "model_preference": model_preference,
                "model_used": result.model_used,
                "context_used": result.context_used,
                "timestamp": datetime.now().isoformat()
            },
            "ocr_results": {
                "original_text": result.original_text,
                "corrected_text": result.corrected_text,
                "confidence": result.confidence,
                "text_length": {
                    "original": len(result.original_text),
                    "corrected": len(result.corrected_text)
                }
            },
            "corrections": {
                "total_corrections": len(result.corrections),
                "corrections_applied": result.corrections
            }
        }
        
        logger.info(f"트랜스포머 OCR 완료: {len(result.corrected_text)}자, "
                   f"신뢰도: {result.confidence:.2f}, 교정: {len(result.corrections)}개")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"트랜스포머 OCR 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"처리 중 오류 발생: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")


@router.post("/compare", response_model=Dict[str, Any])
async def compare_ocr_methods(
    file: UploadFile = File(...),
    language: str = Form("kor")
):
    """
    기본 OCR vs 트랜스포머 OCR 비교
    
    Args:
        file: 업로드된 이미지 파일
        language: 언어 코드
        
    Returns:
        두 방법의 비교 결과
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
        
        logger.info(f"OCR 방법 비교 시작: {file.filename}")
        
        # 기본 OCR (문맥 사용 안함)
        base_result = await transformer_ocr_service.process_with_context(
            image_path=temp_file_path,
            language=language,
            use_context=False,
            model_preference="base_ocr"
        )
        
        # 트랜스포머 OCR (문맥 사용)
        transformer_result = await transformer_ocr_service.process_with_context(
            image_path=temp_file_path,
            language=language,
            use_context=True,
            model_preference="auto"
        )
        
        # 비교 분석
        comparison = {
            "text_length_change": len(transformer_result.corrected_text) - len(base_result.original_text),
            "corrections_made": len(transformer_result.corrections),
            "confidence_improvement": transformer_result.confidence - base_result.confidence,
            "model_used": transformer_result.model_used
        }
        
        # 결과 구성
        response = {
            "success": True,
            "file_info": {
                "filename": file.filename,
                "language": language
            },
            "base_ocr": {
                "text": base_result.original_text,
                "confidence": base_result.confidence,
                "length": len(base_result.original_text)
            },
            "transformer_ocr": {
                "text": transformer_result.corrected_text,
                "confidence": transformer_result.confidence,
                "length": len(transformer_result.corrected_text),
                "model_used": transformer_result.model_used,
                "corrections": transformer_result.corrections
            },
            "comparison": comparison,
            "improvement_metrics": {
                "has_corrections": len(transformer_result.corrections) > 0,
                "confidence_improved": comparison["confidence_improvement"] > 0,
                "text_length_changed": comparison["text_length_change"] != 0
            }
        }
        
        logger.info(f"OCR 비교 완료: {comparison['corrections_made']}개 교정, "
                   f"신뢰도 변화: {comparison['confidence_improvement']:.3f}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR 비교 실패: {e}")
        raise HTTPException(status_code=500, detail=f"비교 중 오류 발생: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")


@router.post("/batch-process", response_model=Dict[str, Any])
async def batch_transformer_ocr(
    files: list[UploadFile] = File(...),
    language: str = Form("kor"),
    model_preference: str = Form("auto"),
    max_files: int = Form(10)
):
    """
    여러 이미지에 대한 일괄 트랜스포머 OCR 처리
    
    Args:
        files: 업로드된 이미지 파일들
        language: 언어 코드
        model_preference: 모델 선택
        max_files: 최대 처리 파일 수
        
    Returns:
        일괄 처리 결과
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
            "model_preference": model_preference,
            "timestamp": datetime.now().isoformat()
        },
        "results": [],
        "summary": {
            "successful": 0,
            "failed": 0,
            "total_corrections": 0,
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
            
            # 트랜스포머 OCR 처리
            result = await transformer_ocr_service.process_with_context(
                image_path=temp_file_path,
                language=language,
                use_context=True,
                model_preference=model_preference
            )
            
            # 결과 저장
            file_result = {
                "file_index": i,
                "filename": file.filename,
                "success": True,
                "ocr_result": {
                    "original_text": result.original_text,
                    "corrected_text": result.corrected_text,
                    "confidence": result.confidence,
                    "corrections_count": len(result.corrections),
                    "model_used": result.model_used
                }
            }
            
            results["results"].append(file_result)
            results["summary"]["successful"] += 1
            results["summary"]["total_corrections"] += len(result.corrections)
            confidences.append(result.confidence)
            
        except Exception as e:
            logger.error(f"파일 {file.filename} 처리 실패: {e}")
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
    
    logger.info(f"일괄 트랜스포머 OCR 완료: {results['summary']['successful']}/{len(files)} 성공")
    
    return results


@router.get("/models", response_model=Dict[str, Any])
async def get_available_models():
    """사용 가능한 트랜스포머 모델 정보 조회"""
    try:
        model_info = transformer_ocr_service.get_model_info()
        
        return {
            "success": True,
            "model_info": model_info,
            "recommendations": {
                "for_accuracy": "openai" if model_info["openai_available"] else "bert",
                "for_speed": "rule_based",
                "for_financial_documents": "bert" if model_info["transformers_available"] else "rule_based",
                "for_multilingual": "openai" if model_info["openai_available"] else "bert"
            },
            "supported_languages": ["kor", "eng", "chi_sim", "chi_tra", "jpn", "ara", "spa", "por", "fra", "deu", "ita", "vie"]
        }
        
    except Exception as e:
        logger.error(f"모델 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"모델 정보 조회 실패: {str(e)}")


@router.post("/analyze-quality", response_model=Dict[str, Any])
async def analyze_ocr_quality(
    file: UploadFile = File(...),
    language: str = Form("kor"),
    reference_text: Optional[str] = Form(None)
):
    """
    OCR 품질 분석
    
    Args:
        file: 업로드된 이미지 파일
        language: 언어 코드
        reference_text: 참조 텍스트 (정답, 선택사항)
        
    Returns:
        OCR 품질 분석 결과
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
        
        # 트랜스포머 OCR 처리
        result = await transformer_ocr_service.process_with_context(
            image_path=temp_file_path,
            language=language,
            use_context=True,
            model_preference="auto"
        )
        
        # 품질 분석
        quality_metrics = {
            "text_length": len(result.corrected_text),
            "word_count": len(result.corrected_text.split()),
            "confidence_score": result.confidence,
            "corrections_made": len(result.corrections),
            "model_used": result.model_used,
            "context_type": result.context_used
        }
        
        # 참조 텍스트가 있는 경우 정확도 계산
        if reference_text:
            accuracy_metrics = calculate_text_accuracy(result.corrected_text, reference_text)
            quality_metrics.update(accuracy_metrics)
        
        # 품질 등급 산정
        quality_grade = determine_quality_grade(quality_metrics)
        
        response = {
            "success": True,
            "file_info": {
                "filename": file.filename,
                "language": language
            },
            "ocr_result": {
                "text": result.corrected_text,
                "confidence": result.confidence
            },
            "quality_metrics": quality_metrics,
            "quality_grade": quality_grade,
            "recommendations": generate_quality_recommendations(quality_metrics)
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR 품질 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"품질 분석 중 오류 발생: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")


def calculate_text_accuracy(predicted: str, reference: str) -> Dict[str, float]:
    """텍스트 정확도 계산"""
    from difflib import SequenceMatcher
    
    # 전체 문자 정확도
    matcher = SequenceMatcher(None, predicted, reference)
    char_accuracy = matcher.ratio()
    
    # 단어 단위 정확도
    pred_words = predicted.split()
    ref_words = reference.split()
    
    word_matcher = SequenceMatcher(None, pred_words, ref_words)
    word_accuracy = word_matcher.ratio()
    
    return {
        "character_accuracy": char_accuracy,
        "word_accuracy": word_accuracy,
        "length_ratio": len(predicted) / max(len(reference), 1)
    }


def determine_quality_grade(metrics: Dict[str, Any]) -> str:
    """품질 등급 결정"""
    confidence = metrics.get("confidence_score", 0)
    corrections = metrics.get("corrections_made", 0)
    text_length = metrics.get("text_length", 0)
    
    if confidence > 0.9 and corrections <= 2:
        return "A"  # 매우 좋음
    elif confidence > 0.8 and corrections <= 5:
        return "B"  # 좋음
    elif confidence > 0.6 and corrections <= 10:
        return "C"  # 보통
    elif confidence > 0.4:
        return "D"  # 나쁨
    else:
        return "F"  # 매우 나쁨


def generate_quality_recommendations(metrics: Dict[str, Any]) -> List[str]:
    """품질 개선 권장사항 생성"""
    recommendations = []
    
    confidence = metrics.get("confidence_score", 0)
    corrections = metrics.get("corrections_made", 0)
    
    if confidence < 0.5:
        recommendations.append("이미지 품질을 개선해보세요 (해상도, 조명, 선명도)")
    
    if corrections > 10:
        recommendations.append("더 정확한 OCR 모델을 사용하거나 이미지 전처리를 시도해보세요")
    
    if metrics.get("text_length", 0) < 10:
        recommendations.append("텍스트가 너무 짧아 정확도 평가가 제한적입니다")
    
    if metrics.get("model_used") == "rule_based":
        recommendations.append("더 나은 결과를 위해 BERT 또는 OpenAI 모델 사용을 고려해보세요")
    
    if not recommendations:
        recommendations.append("OCR 품질이 양호합니다")
    
    return recommendations


@router.get("/health")
async def transformer_ocr_health_check():
    """트랜스포머 OCR 서비스 상태 확인"""
    try:
        model_info = transformer_ocr_service.get_model_info()
        
        return {
            "status": "healthy",
            "service": "transformer_ocr",
            "version": "1.0.0",
            "capabilities": {
                "transformers_models": model_info["transformers_available"],
                "openai_integration": model_info["openai_available"],
                "rule_based_correction": True,
                "contextual_analysis": True,
                "multilingual_support": True
            },
            "features": [
                "contextual_correction",
                "bert_integration", 
                "openai_integration",
                "financial_vocabulary",
                "batch_processing",
                "quality_analysis"
            ]
        }
        
    except Exception as e:
        logger.error(f"건강 상태 확인 실패: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }