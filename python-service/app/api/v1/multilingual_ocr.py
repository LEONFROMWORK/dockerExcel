"""
다국어 OCR API 엔드포인트
10개 언어 지원 + 자동 언어 감지 + 재무 특화 모델 + Redis 캐싱
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from app.services.multilingual_two_tier_service import MultilingualTwoTierService
from app.services.ocr_cache_service import ocr_cache
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()

# 다국어 OCR 서비스 초기화
multilingual_service = MultilingualTwoTierService()

@router.post("/multilingual/extract")
async def extract_multilingual_text(file: UploadFile = File(...)):
    """
    다국어 자동 감지 OCR
    
    지원 언어: 한국어, 중국어(간체/번체), 일본어, 스페인어, 포르투갈어, 프랑스어, 독일어, 베트남어, 이탈리아어
    """
    try:
        # 파일 타입 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 이미지 데이터 읽기
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="빈 파일입니다")
        
        # 처리 시간 측정
        start_time = time.time()
        
        # 다국어 OCR 실행
        result = multilingual_service.extract_text(image_data)
        
        processing_time = time.time() - start_time
        
        # 메타데이터 추가
        result["processing_time"] = round(processing_time, 3)
        result["file_size"] = len(image_data)
        result["filename"] = file.filename
        
        # 재무 콘텐츠 분석
        if result["success"] and result["text"]:
            language = result.get("language", "ko")
            financial_analysis = multilingual_service.analyze_multilingual_financial_content(
                result["text"], language
            )
            result["financial_analysis"] = financial_analysis
        
        logger.info(f"다국어 OCR 완료: {file.filename} ({processing_time:.3f}s)")
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다국어 OCR 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OCR 처리 실패: {str(e)}"
        )

@router.post("/multilingual/extract-language")
async def extract_text_specific_language(
    file: UploadFile = File(...),
    language: str = Query(..., description="언어 코드 (ko, zh-cn, zh-tw, ja, es, pt, fr, de, vi, it)")
):
    """
    특정 언어로 OCR 처리
    """
    try:
        # 파일 타입 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 언어 코드 검증
        supported_languages = ['ko', 'zh-cn', 'zh-tw', 'ja', 'es', 'pt', 'fr', 'de', 'vi', 'it']
        if language not in supported_languages:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 언어입니다. 지원 언어: {', '.join(supported_languages)}"
            )
        
        # 이미지 데이터 읽기
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="빈 파일입니다")
        
        # 이미지 변환
        import cv2
        import numpy as np
        
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지 디코딩 실패")
        
        start_time = time.time()
        
        # 특정 언어로 OCR 실행
        result = multilingual_service.extract_text_with_language(image, language, tier=1)
        
        processing_time = time.time() - start_time
        
        # 메타데이터 추가
        result["processing_time"] = round(processing_time, 3)
        result["file_size"] = len(image_data)
        result["filename"] = file.filename
        result["requested_language"] = language
        
        # 재무 콘텐츠 분석
        if result["success"] and result["text"]:
            financial_analysis = multilingual_service.analyze_multilingual_financial_content(
                result["text"], language
            )
            result["financial_analysis"] = financial_analysis
        
        logger.info(f"언어별 OCR 완료: {language} - {file.filename} ({processing_time:.3f}s)")
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"언어별 OCR 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OCR 처리 실패: {str(e)}"
        )

@router.post("/multilingual/compare-languages")
async def compare_multiple_languages(
    file: UploadFile = File(...),
    languages: str = Query(..., description="비교할 언어들 (쉼표로 구분, 예: ko,zh-cn,ja,it)")
):
    """
    여러 언어로 동시에 OCR 처리하여 결과 비교
    """
    try:
        # 파일 타입 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 언어 목록 파싱
        language_list = [lang.strip() for lang in languages.split(',')]
        supported_languages = ['ko', 'zh-cn', 'zh-tw', 'ja', 'es', 'pt', 'fr', 'de', 'vi', 'it']
        
        invalid_languages = [lang for lang in language_list if lang not in supported_languages]
        if invalid_languages:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 언어: {', '.join(invalid_languages)}"
            )
        
        # 이미지 데이터 읽기
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="빈 파일입니다")
        
        # 이미지 변환
        import cv2
        import numpy as np
        
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지 디코딩 실패")
        
        start_time = time.time()
        
        # 각 언어별로 OCR 실행
        results = {}
        for lang in language_list:
            lang_result = multilingual_service.extract_text_with_language(image, lang, tier=1)
            
            # 재무 분석 추가
            if lang_result["success"] and lang_result["text"]:
                financial_analysis = multilingual_service.analyze_multilingual_financial_content(
                    lang_result["text"], lang
                )
                lang_result["financial_analysis"] = financial_analysis
            
            results[lang] = lang_result
        
        processing_time = time.time() - start_time
        
        # 최고 성능 언어 찾기
        best_language = None
        best_confidence = 0
        
        for lang, result in results.items():
            if result["success"] and result["confidence"] > best_confidence:
                best_language = lang
                best_confidence = result["confidence"]
        
        # 통합 결과
        comparison_result = {
            "success": True,
            "results": results,
            "best_language": best_language,
            "best_confidence": best_confidence,
            "processing_time": round(processing_time, 3),
            "filename": file.filename,
            "compared_languages": language_list,
            "summary": {
                lang: {
                    "confidence": results[lang].get("confidence", 0),
                    "text_length": len(results[lang].get("text", "")),
                    "financial_score": results[lang].get("financial_analysis", {}).get("financial_score", 0)
                }
                for lang in language_list
            }
        }
        
        logger.info(f"다국어 비교 완료: {', '.join(language_list)} - {file.filename}")
        
        return JSONResponse(content=comparison_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다국어 비교 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"다국어 비교 처리 실패: {str(e)}"
        )

@router.get("/multilingual/info")
async def get_multilingual_service_info():
    """
    다국어 OCR 서비스 정보 조회
    """
    try:
        info = multilingual_service.get_service_info()
        return JSONResponse(content=info)
        
    except Exception as e:
        logger.error(f"서비스 정보 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"서비스 정보 조회 실패: {str(e)}"
        )

@router.post("/multilingual/financial-analysis")
async def analyze_multilingual_financial_document(file: UploadFile = File(...)):
    """
    다국어 재무제표 전용 분석
    """
    try:
        # 파일 타입 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 이미지 데이터 읽기
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="빈 파일입니다")
        
        start_time = time.time()
        
        # 다국어 OCR 실행
        result = multilingual_service.extract_text(image_data)
        
        processing_time = time.time() - start_time
        
        if not result["success"]:
            raise HTTPException(
                status_code=422,
                detail=f"OCR 처리 실패: {result.get('error', '알 수 없는 오류')}"
            )
        
        # 재무 분석 강화
        language = result.get("language", "ko")
        financial_analysis = multilingual_service.analyze_multilingual_financial_content(
            result["text"], language
        )
        
        # 재무제표 점수 계산
        financial_score = financial_analysis["financial_score"]
        is_financial_document = financial_score > 30
        
        # 언어별 재무용어 매칭률 계산
        total_keywords = len(multilingual_service.financial_keywords.get(language, []))
        found_keywords = len(financial_analysis["financial_keywords"])
        keyword_match_rate = (found_keywords / total_keywords * 100) if total_keywords > 0 else 0
        
        enhanced_result = {
            "success": True,
            "text": result["text"],
            "confidence": result["confidence"],
            "language": language,
            "method": result.get("method", ""),
            "processing_time": round(processing_time, 3),
            "financial_analysis": financial_analysis,
            "financial_score": financial_score,
            "is_financial_document": is_financial_document,
            "keyword_match_rate": round(keyword_match_rate, 1),
            "regions": result.get("regions", []),
            "filename": file.filename,
            "language_detection": result.get("language_detection", {}),
            "document_classification": {
                "type": "financial" if is_financial_document else "general",
                "confidence": financial_score / 100,
                "language": multilingual_service.language_mapping[language]["name"]
            }
        }
        
        logger.info(f"다국어 재무 분석 완료: {language} - {file.filename} (점수: {financial_score})")
        
        return JSONResponse(content=enhanced_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다국어 재무 분석 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"재무 분석 실패: {str(e)}"
        )

@router.get("/multilingual/cache/stats")
async def get_cache_stats():
    """
    OCR 캐시 통계 조회
    """
    try:
        stats = ocr_cache.get_cache_stats()
        return JSONResponse(content=stats)
        
    except Exception as e:
        logger.error(f"캐시 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"캐시 통계 조회 실패: {str(e)}"
        )

@router.delete("/multilingual/cache/clear")
async def clear_cache():
    """
    OCR 캐시 클리어
    """
    try:
        cleared_count = ocr_cache.clear_cache()
        return JSONResponse(content={
            "success": True,
            "message": f"{cleared_count}개의 캐시 항목이 삭제되었습니다",
            "cleared_count": cleared_count
        })
        
    except Exception as e:
        logger.error(f"캐시 클리어 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"캐시 클리어 실패: {str(e)}"
        )

@router.get("/multilingual/cache/info/{image_hash}")
async def get_cache_info(image_hash: str):
    """
    특정 이미지 해시의 캐시 정보 조회
    """
    try:
        info = ocr_cache.get_cache_key_info(image_hash)
        return JSONResponse(content=info)
        
    except Exception as e:
        logger.error(f"캐시 정보 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"캐시 정보 조회 실패: {str(e)}"
        )