#!/usr/bin/env python3
"""
자동 품질 검증 API 엔드포인트
Automatic Quality Verification API Endpoints

AI 기반 OCR 결과 자동 검증, 오류 패턴 학습, 신뢰도 점수 산출을 위한 RESTful API
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import tempfile
import os
import logging
from datetime import datetime

from app.services.quality_verification_service import quality_verification_service
from app.services.multilingual_two_tier_service import MultilingualTwoTierService

logger = logging.getLogger(__name__)

router = APIRouter()

# OCR 서비스 인스턴스
ocr_service = MultilingualTwoTierService()


@router.post("/verify-quality", response_model=Dict[str, Any])
async def verify_ocr_quality(
    file: UploadFile = File(...),
    language: str = Form("kor"),
    verification_level: str = Form("comprehensive"),
    reference_text: Optional[str] = Form(None),
    include_detailed_errors: bool = Form(True),
    include_patterns: bool = Form(True)
):
    """
    OCR 품질 자동 검증
    
    Args:
        file: 업로드된 이미지 파일
        language: 언어 코드 (kor, eng, chi_sim, jpn, etc.)
        verification_level: 검증 수준 (basic, comprehensive, detailed)
        reference_text: 참조 텍스트 (정답, 선택사항)
        include_detailed_errors: 상세 오류 정보 포함 여부
        include_patterns: 오류 패턴 정보 포함 여부
        
    Returns:
        품질 검증 보고서
    """
    temp_file_path = None
    
    try:
        # 파일 형식 검증
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 검증 수준 검증
        if verification_level not in ["basic", "comprehensive", "detailed"]:
            raise HTTPException(
                status_code=400, 
                detail="verification_level은 basic, comprehensive, detailed 중 하나여야 합니다"
            )
        
        # 임시 파일 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        logger.info(f"품질 검증 시작: {file.filename} (수준: {verification_level})")
        
        # 1. 먼저 OCR 수행
        ocr_result = ocr_service.process_image(temp_file_path, language)
        extracted_text = ocr_result.get("extracted_text", "")
        
        if not extracted_text.strip():
            raise HTTPException(
                status_code=400, 
                detail="OCR 결과가 비어있습니다. 이미지를 확인해주세요."
            )
        
        # 2. 품질 검증 수행
        quality_report = await quality_verification_service.verify_ocr_quality(
            image_path=temp_file_path,
            extracted_text=extracted_text,
            language=language,
            reference_text=reference_text,
            verification_level=verification_level
        )
        
        # 3. 응답 구성
        response = {
            "success": True,
            "file_info": {
                "filename": file.filename,
                "content_type": file.content_type,
                "language": language
            },
            "verification_config": {
                "level": verification_level,
                "has_reference": reference_text is not None,
                "timestamp": datetime.now().isoformat()
            },
            "ocr_result": {
                "extracted_text": extracted_text,
                "text_length": len(extracted_text)
            },
            "quality_assessment": {
                "overall_grade": quality_report.overall_grade,
                "overall_score": quality_report.quality_metrics.overall_score,
                "metrics": {
                    "character_accuracy": quality_report.quality_metrics.character_accuracy,
                    "word_accuracy": quality_report.quality_metrics.word_accuracy,
                    "layout_preservation": quality_report.quality_metrics.layout_preservation,
                    "consistency_score": quality_report.quality_metrics.consistency_score,
                    "confidence_reliability": quality_report.quality_metrics.confidence_reliability,
                    "error_density": quality_report.quality_metrics.error_density
                }
            },
            "recommendations": quality_report.recommendations
        }
        
        # 조건부 상세 정보 포함
        if include_detailed_errors and quality_report.detected_errors:
            response["detailed_errors"] = {
                "total_errors": len(quality_report.detected_errors),
                "errors": quality_report.detected_errors[:20],  # 최대 20개
                "error_summary": {
                    error_type: len([e for e in quality_report.detected_errors if e["type"] == error_type])
                    for error_type in set(e["type"] for e in quality_report.detected_errors)
                }
            }
        
        if include_patterns and quality_report.error_patterns:
            response["error_patterns"] = {
                "total_patterns": len(quality_report.error_patterns),
                "patterns": [
                    {
                        "pattern_type": pattern.pattern_type,
                        "frequency": pattern.frequency,
                        "confidence_impact": pattern.confidence_impact,
                        "suggested_fix": pattern.suggested_fix,
                        "examples": pattern.examples[:3]  # 최대 3개 예시
                    }
                    for pattern in quality_report.error_patterns
                ]
            }
        
        logger.info(f"품질 검증 완료: {quality_report.overall_grade} " +
                   f"({quality_report.quality_metrics.overall_score:.2f})")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"품질 검증 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검증 중 오류 발생: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")


@router.post("/validate-text", response_model=Dict[str, Any])
async def validate_text_with_ai(
    text: str = Form(...),
    language: str = Form("kor"),
    expected_content_type: str = Form("general"),
    confidence_threshold: float = Form(0.7)
):
    """
    AI를 사용한 텍스트 검증
    
    Args:
        text: 검증할 텍스트
        language: 언어 코드
        expected_content_type: 예상 콘텐츠 타입 (general, financial, legal, etc.)
        confidence_threshold: 신뢰도 임계값
        
    Returns:
        텍스트 검증 결과
    """
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="검증할 텍스트가 비어있습니다")
        
        logger.info(f"텍스트 검증 시작: {len(text)}자")
        
        # AI 기반 텍스트 검증
        validation_result = await quality_verification_service.validate_text_with_ai(
            text=text,
            language=language,
            expected_content_type=expected_content_type
        )
        
        # 응답 구성
        response = {
            "success": True,
            "text_info": {
                "length": len(text),
                "word_count": len(text.split()),
                "language": language,
                "content_type": expected_content_type
            },
            "validation_result": {
                "is_valid": validation_result.is_valid,
                "confidence_score": validation_result.confidence_score,
                "meets_threshold": validation_result.confidence_score >= confidence_threshold,
                "quality_issues": validation_result.quality_issues,
                "suggested_corrections": validation_result.suggested_corrections,
                "validation_method": validation_result.validation_details.get("method", "unknown")
            },
            "threshold_info": {
                "confidence_threshold": confidence_threshold,
                "recommendation": (
                    "텍스트 품질이 양호합니다" if validation_result.confidence_score >= confidence_threshold
                    else "텍스트 품질 개선이 필요합니다"
                )
            }
        }
        
        logger.info(f"텍스트 검증 완료: {'유효' if validation_result.is_valid else '무효'} " +
                   f"(신뢰도: {validation_result.confidence_score:.2f})")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"텍스트 검증 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검증 중 오류 발생: {str(e)}")


@router.post("/batch-verify", response_model=Dict[str, Any])
async def batch_quality_verification(
    files: List[UploadFile] = File(...),
    language: str = Form("kor"),
    verification_level: str = Form("basic"),
    max_files: int = Form(5)
):
    """
    배치 품질 검증
    
    Args:
        files: 업로드된 이미지 파일들
        language: 언어 코드
        verification_level: 검증 수준
        max_files: 최대 처리 파일 수
        
    Returns:
        배치 검증 결과
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
            "verification_level": verification_level,
            "timestamp": datetime.now().isoformat()
        },
        "results": [],
        "summary": {
            "successful": 0,
            "failed": 0,
            "grade_distribution": {},
            "average_score": 0.0,
            "total_errors": 0,
            "total_patterns": 0
        }
    }
    
    scores = []
    total_errors = 0
    total_patterns = 0
    
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
            
            # OCR 수행
            ocr_result = ocr_service.process_image(temp_file_path, language)
            extracted_text = ocr_result.get("extracted_text", "")
            
            if not extracted_text.strip():
                results["results"].append({
                    "file_index": i,
                    "filename": file.filename,
                    "success": False,
                    "error": "OCR 결과가 비어있음"
                })
                results["summary"]["failed"] += 1
                continue
            
            # 품질 검증
            quality_report = await quality_verification_service.verify_ocr_quality(
                image_path=temp_file_path,
                extracted_text=extracted_text,
                language=language,
                reference_text=None,
                verification_level=verification_level
            )
            
            # 결과 저장
            file_result = {
                "file_index": i,
                "filename": file.filename,
                "success": True,
                "quality_result": {
                    "overall_grade": quality_report.overall_grade,
                    "overall_score": quality_report.quality_metrics.overall_score,
                    "error_count": len(quality_report.detected_errors),
                    "pattern_count": len(quality_report.error_patterns),
                    "text_length": len(extracted_text)
                }
            }
            
            results["results"].append(file_result)
            results["summary"]["successful"] += 1
            
            # 통계 업데이트
            scores.append(quality_report.quality_metrics.overall_score)
            total_errors += len(quality_report.detected_errors)
            total_patterns += len(quality_report.error_patterns)
            
            # 등급 분포
            grade = quality_report.overall_grade
            if grade in results["summary"]["grade_distribution"]:
                results["summary"]["grade_distribution"][grade] += 1
            else:
                results["summary"]["grade_distribution"][grade] = 1
            
        except Exception as e:
            logger.error(f"파일 {file.filename} 검증 실패: {e}")
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
    
    # 전체 통계 계산
    if scores:
        results["summary"]["average_score"] = sum(scores) / len(scores)
    results["summary"]["total_errors"] = total_errors
    results["summary"]["total_patterns"] = total_patterns
    
    logger.info(f"배치 품질 검증 완료: {results['summary']['successful']}/{len(files)} 성공")
    
    return results


@router.get("/quality-statistics", response_model=Dict[str, Any])
async def get_quality_statistics():
    """품질 검증 통계 조회"""
    try:
        stats = quality_verification_service.get_quality_statistics()
        
        return {
            "success": True,
            "statistics": stats,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"품질 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.get("/error-patterns", response_model=Dict[str, Any])
async def get_learned_error_patterns(
    language: Optional[str] = None,
    pattern_type: Optional[str] = None,
    min_frequency: int = 1
):
    """
    학습된 오류 패턴 조회
    
    Args:
        language: 언어 필터 (선택사항)
        pattern_type: 패턴 유형 필터 (선택사항)
        min_frequency: 최소 빈도수
        
    Returns:
        오류 패턴 목록
    """
    try:
        all_patterns = quality_verification_service.error_patterns_db
        
        # 필터링
        filtered_patterns = {}
        for pattern_key, pattern_data in all_patterns.items():
            # 빈도수 필터
            if pattern_data["count"] < min_frequency:
                continue
            
            # 언어 필터
            if language and not pattern_key.endswith(f"_{language}"):
                continue
            
            # 패턴 유형 필터
            if pattern_type and not pattern_key.startswith(f"{pattern_type}_"):
                continue
            
            filtered_patterns[pattern_key] = pattern_data
        
        # 패턴별 상세 정보 구성
        pattern_details = []
        for pattern_key, pattern_data in filtered_patterns.items():
            parts = pattern_key.split("_")
            pattern_type_name = "_".join(parts[:-1])
            pattern_language = parts[-1]
            
            pattern_details.append({
                "pattern_id": pattern_key,
                "pattern_type": pattern_type_name,
                "language": pattern_language,
                "frequency": pattern_data["count"],
                "last_seen": pattern_data["last_seen"],
                "example_count": len(pattern_data["examples"]),
                "examples": pattern_data["examples"][:3]  # 최대 3개 예시
            })
        
        # 빈도수 기준 정렬
        pattern_details.sort(key=lambda x: x["frequency"], reverse=True)
        
        return {
            "success": True,
            "filters": {
                "language": language,
                "pattern_type": pattern_type,
                "min_frequency": min_frequency
            },
            "total_patterns": len(pattern_details),
            "patterns": pattern_details,
            "summary": {
                "most_common_type": pattern_details[0]["pattern_type"] if pattern_details else None,
                "total_occurrences": sum(p["frequency"] for p in pattern_details),
                "languages_covered": list(set(p["language"] for p in pattern_details))
            }
        }
        
    except Exception as e:
        logger.error(f"오류 패턴 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"패턴 조회 실패: {str(e)}")


@router.get("/quality-thresholds", response_model=Dict[str, Any])
async def get_quality_thresholds():
    """품질 등급 임계값 조회"""
    try:
        thresholds = quality_verification_service.quality_thresholds
        
        return {
            "success": True,
            "thresholds": thresholds,
            "grade_descriptions": {
                "A": "우수 (95점 이상) - 추가 처리 불필요",
                "B": "양호 (85-94점) - 경미한 수정 권장",
                "C": "보통 (70-84점) - 부분적 수정 필요",
                "D": "미흡 (50-69점) - 상당한 수정 필요",
                "F": "불량 (50점 미만) - 재처리 권장"
            },
            "recommended_actions": {
                "A": ["현재 설정 유지"],
                "B": ["미세 조정", "후처리 규칙 적용"],
                "C": ["OCR 설정 조정", "이미지 전처리 개선"],
                "D": ["다른 OCR 엔진 시도", "이미지 품질 개선"],
                "F": ["수동 입력 고려", "원본 이미지 재검토"]
            }
        }
        
    except Exception as e:
        logger.error(f"품질 임계값 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"임계값 조회 실패: {str(e)}")


@router.get("/supported-features", response_model=Dict[str, Any])
async def get_supported_features():
    """지원되는 품질 검증 기능 조회"""
    try:
        service_info = quality_verification_service.get_service_info()
        
        return {
            "success": True,
            "service_info": service_info,
            "api_endpoints": [
                {
                    "endpoint": "/verify-quality",
                    "method": "POST",
                    "description": "OCR 품질 자동 검증",
                    "features": ["quality_metrics", "error_detection", "pattern_analysis"]
                },
                {
                    "endpoint": "/validate-text",
                    "method": "POST",
                    "description": "AI 기반 텍스트 검증",
                    "features": ["ai_validation", "confidence_scoring"]
                },
                {
                    "endpoint": "/batch-verify",
                    "method": "POST", 
                    "description": "배치 품질 검증",
                    "features": ["batch_processing", "statistics"]
                },
                {
                    "endpoint": "/quality-statistics",
                    "method": "GET",
                    "description": "품질 통계 조회",
                    "features": ["historical_data", "trend_analysis"]
                },
                {
                    "endpoint": "/error-patterns",
                    "method": "GET",
                    "description": "학습된 오류 패턴 조회",  
                    "features": ["pattern_learning", "error_analysis"]
                }
            ],
            "verification_capabilities": {
                "character_level": "문자 정확도 측정",
                "word_level": "단어 정확도 측정",  
                "layout_level": "레이아웃 보존도 측정",
                "structural_level": "구조적 일관성 측정",
                "semantic_level": "의미적 타당성 측정"
            }
        }
        
    except Exception as e:
        logger.error(f"지원 기능 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"기능 조회 실패: {str(e)}")


@router.get("/health")
async def quality_verification_health_check():
    """품질 검증 서비스 상태 확인"""
    try:
        service_info = quality_verification_service.get_service_info()
        
        return {
            "status": "healthy",
            "service": "quality_verification",
            "version": service_info["version"],
            "verification_count": service_info["verification_count"],
            "learned_patterns": service_info["learned_patterns"],
            "supported_languages": service_info["supported_languages"],
            "capabilities": service_info["capabilities"],
            "health_indicators": {
                "pattern_learning": "active" if service_info["learned_patterns"] > 0 else "inactive",
                "quality_assessment": "operational",
                "error_detection": "operational",
                "ai_validation": "operational"
            }
        }
        
    except Exception as e:
        logger.error(f"건강 상태 확인 실패: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }