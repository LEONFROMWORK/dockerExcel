"""
성능 최적화 API 엔드포인트
최적화된 OCR 서비스와 리소스 관리 기능 제공
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import tempfile
import os
import logging
import time

from app.services.optimized_multilingual_service import OptimizedMultilingualOCRService
from app.core.performance_optimization import OptimizationConfig, PerformanceOptimizerFactory
from app.core.resource_management import get_resource_manager, cleanup_global_resources

logger = logging.getLogger(__name__)
router = APIRouter()

# 서비스 인스턴스
optimized_ocr_service = OptimizedMultilingualOCRService(optimization_level="standard")
resource_manager = get_resource_manager()

@router.post("/optimized-ocr")
async def optimized_ocr_process(
    file: UploadFile = File(...),
    language: str = Query("auto", description="대상 언어 (auto, kor, eng, chi_sim, jpn 등)"),
    context_tags: Optional[str] = Query(None, description="컨텍스트 태그 (쉼표로 구분)"),
    optimization_level: str = Query("standard", description="최적화 수준 (basic, standard, aggressive)")
) -> Dict[str, Any]:
    """
    최적화된 OCR 처리
    - 캐싱, 메모리 풀링, 벡터화된 분석 적용
    - 처리 시간 세부 분석 제공
    """
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 필요합니다")
    
    # 지원되는 이미지 형식 확인
    supported_formats = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp']
    file_ext = os.path.splitext(file.filename.lower())[1]
    
    if file_ext not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"지원되지 않는 파일 형식입니다. 지원 형식: {', '.join(supported_formats)}"
        )
    
    temp_image_path = None
    
    try:
        # 임시 파일 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_image_path = temp_file.name
        
        # 컨텍스트 태그 파싱
        context_list = []
        if context_tags:
            context_list = [tag.strip() for tag in context_tags.split(',')]
        
        # 최적화 수준에 따라 서비스 조정
        if optimization_level != "standard":
            global optimized_ocr_service
            optimized_ocr_service = OptimizedMultilingualOCRService(optimization_level)
        
        # 최적화된 OCR 처리
        start_time = time.perf_counter()
        result = optimized_ocr_service.process_image(
            image_path=temp_image_path,
            language=language,
            context_tags=context_list
        )
        total_time = time.perf_counter() - start_time
        
        # 응답 구성
        response = {
            "success": result.success,
            "message": "최적화된 OCR 처리 완료" if result.success else "OCR 처리 실패",
            "data": result.data if result.success else None,
            "error": result.error_message if not result.success else None,
            "optimization_info": {
                "optimization_level": optimization_level,
                "cache_used": result.cache_used,
                "total_processing_time": total_time,
                "time_breakdown": result.processing_time_breakdown,
                "optimization_stats": result.optimization_stats
            },
            "metadata": result.processing_metadata
        }
        
        return response
    
    except Exception as e:
        logger.error(f"최적화된 OCR 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"처리 실패: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.unlink(temp_image_path)
            except Exception as e:
                logger.warning(f"임시 파일 정리 실패: {e}")

@router.post("/optimized-batch-ocr")
async def optimized_batch_ocr_process(
    files: List[UploadFile] = File(...),
    language: str = Query("auto", description="대상 언어"),
    context_tags: Optional[str] = Query(None, description="컨텍스트 태그"),
    optimization_level: str = Query("standard", description="최적화 수준")
) -> Dict[str, Any]:
    """
    최적화된 배치 OCR 처리
    - 메모리 효율적인 배치 처리
    - 병렬 처리 최적화
    """
    
    if len(files) > 20:
        raise HTTPException(
            status_code=400,
            detail="한 번에 최대 20개 파일까지 처리 가능합니다"
        )
    
    temp_files = []
    
    try:
        # 임시 파일들 저장
        image_paths = []
        for file in files:
            if not file.filename:
                continue
            
            file_ext = os.path.splitext(file.filename.lower())[1]
            if file_ext not in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp']:
                continue
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_files.append(temp_file.name)
                image_paths.append(temp_file.name)
        
        if not image_paths:
            raise HTTPException(status_code=400, detail="처리 가능한 이미지 파일이 없습니다")
        
        # 컨텍스트 태그 파싱
        context_list = []
        if context_tags:
            context_list = [tag.strip() for tag in context_tags.split(',')]
        
        # 배치 처리
        start_time = time.perf_counter()
        results = optimized_ocr_service.process_image_batch(
            image_paths=image_paths,
            language=language,
            context_tags=context_list
        )
        total_time = time.perf_counter() - start_time
        
        # 결과 집계
        successful_count = sum(1 for r in results if r.success)
        failed_count = len(results) - successful_count
        
        return {
            "success": True,
            "message": f"배치 처리 완료: {successful_count}/{len(results)} 성공",
            "data": {
                "total_files": len(results),
                "successful_count": successful_count,
                "failed_count": failed_count,
                "results": [
                    {
                        "success": r.success,
                        "data": r.data if r.success else None,
                        "error": r.error_message if not r.success else None,
                        "cache_used": r.cache_used,
                        "processing_time_breakdown": r.processing_time_breakdown
                    }
                    for r in results
                ]
            },
            "optimization_info": {
                "optimization_level": optimization_level,
                "total_processing_time": total_time,
                "avg_processing_time": total_time / len(results) if results else 0,
                "optimization_stats": optimized_ocr_service.get_optimization_stats()
            }
        }
    
    except Exception as e:
        logger.error(f"배치 OCR 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 처리 실패: {str(e)}")
    
    finally:
        # 임시 파일들 정리
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"임시 파일 정리 실패: {e}")

@router.get("/optimization-stats")
async def get_optimization_stats() -> Dict[str, Any]:
    """
    성능 최적화 통계 조회
    - 캐시 효율성, 메모리 사용량, 처리 성능 등
    """
    
    try:
        # OCR 서비스 통계
        ocr_stats = optimized_ocr_service.get_optimization_stats()
        
        # 리소스 관리 통계
        resource_stats = resource_manager.get_comprehensive_stats()
        
        return {
            "success": True,
            "data": {
                "ocr_optimization": ocr_stats,
                "resource_management": resource_stats,
                "summary": {
                    "cache_hit_rate": ocr_stats.get('metrics', {}).get('cache_hit_rate', 0),
                    "avg_processing_time": ocr_stats.get('metrics', {}).get('avg_processing_time', 0),
                    "memory_usage_mb": resource_stats['current_memory']['process_memory_mb'],
                    "memory_utilization": resource_stats['current_memory']['memory_percent']
                }
            }
        }
    
    except Exception as e:
        logger.error(f"최적화 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@router.post("/optimize-memory")
async def optimize_memory_usage() -> Dict[str, Any]:
    """
    메모리 사용량 최적화 실행
    - 가비지 컬렉션, 캐시 정리, 메모리 풀 최적화
    """
    
    try:
        # 메모리 최적화 실행
        optimization_result = resource_manager.optimize_memory_usage()
        
        # OCR 서비스 캐시 정리
        optimized_ocr_service.clear_caches()
        
        return {
            "success": True,
            "message": "메모리 최적화 완료",
            "data": {
                "optimization_result": optimization_result,
                "memory_freed_mb": optimization_result['gc_result']['memory_freed'] / 1024 / 1024,
                "optimization_time": optimization_result['optimization_time'],
                "final_memory_usage": optimization_result['final_memory_stats']['process_memory'] / 1024 / 1024
            }
        }
    
    except Exception as e:
        logger.error(f"메모리 최적화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"메모리 최적화 실패: {str(e)}")

@router.put("/optimization-config")
async def update_optimization_config(
    cache_size_limit: int = Query(1000, description="캐시 크기 제한"),
    memory_pool_size: int = Query(100, description="메모리 풀 크기"),
    batch_size: int = Query(32, description="배치 크기"),
    enable_vectorization: bool = Query(True, description="벡터화 활성화"),
    enable_memory_pooling: bool = Query(True, description="메모리 풀링 활성화"),
    enable_result_caching: bool = Query(True, description="결과 캐싱 활성화")
) -> Dict[str, Any]:
    """
    최적화 설정 업데이트
    """
    
    try:
        new_config = OptimizationConfig(
            cache_size_limit=cache_size_limit,
            memory_pool_size=memory_pool_size,
            batch_size=batch_size,
            enable_vectorization=enable_vectorization,
            enable_memory_pooling=enable_memory_pooling,
            enable_result_caching=enable_result_caching
        )
        
        # 설정 업데이트
        optimized_ocr_service.update_optimization_config(new_config)
        
        return {
            "success": True,
            "message": "최적화 설정 업데이트 완료",
            "data": {
                "new_config": {
                    "cache_size_limit": cache_size_limit,
                    "memory_pool_size": memory_pool_size,
                    "batch_size": batch_size,
                    "enable_vectorization": enable_vectorization,
                    "enable_memory_pooling": enable_memory_pooling,
                    "enable_result_caching": enable_result_caching
                }
            }
        }
    
    except Exception as e:
        logger.error(f"설정 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"설정 업데이트 실패: {str(e)}")

@router.get("/performance-benchmark")
async def run_performance_benchmark() -> Dict[str, Any]:
    """
    성능 벤치마크 실행
    - 다양한 최적화 수준별 성능 측정
    """
    
    try:
        # 더미 이미지 생성 (테스트용)
        import numpy as np
        from PIL import Image
        
        # 테스트 이미지 생성
        test_image = np.random.randint(0, 255, (800, 600, 3), dtype=np.uint8)
        pil_image = Image.fromarray(test_image)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
            pil_image.save(temp_file.name)
            test_image_path = temp_file.name
        
        benchmark_results = {}
        
        try:
            # 다양한 최적화 수준 테스트
            for level in ['basic', 'standard', 'aggressive']:
                test_service = OptimizedMultilingualOCRService(level)
                
                # 5회 반복 측정
                times = []
                for i in range(5):
                    start_time = time.perf_counter()
                    result = test_service.process_image(test_image_path, "auto", ["test"])
                    end_time = time.perf_counter()
                    
                    if result.success:
                        times.append(end_time - start_time)
                
                if times:
                    benchmark_results[level] = {
                        "avg_time": sum(times) / len(times),
                        "min_time": min(times),
                        "max_time": max(times),
                        "runs": len(times),
                        "optimization_stats": test_service.get_optimization_stats()
                    }
            
            return {
                "success": True,
                "message": "성능 벤치마크 완료",
                "data": {
                    "benchmark_results": benchmark_results,
                    "test_conditions": {
                        "image_size": "800x600",
                        "iterations_per_level": 5,
                        "test_image_type": "synthetic"
                    }
                }
            }
        
        finally:
            # 테스트 이미지 정리
            if os.path.exists(test_image_path):
                os.unlink(test_image_path)
    
    except Exception as e:
        logger.error(f"성능 벤치마크 실패: {e}")
        raise HTTPException(status_code=500, detail=f"벤치마크 실패: {str(e)}")

@router.delete("/cleanup-resources")
async def cleanup_all_resources() -> Dict[str, Any]:
    """
    모든 리소스 정리
    - 개발/테스트 환경에서 사용
    """
    
    try:
        # OCR 서비스 캐시 정리
        optimized_ocr_service.clear_caches()
        
        # 전역 리소스 정리
        cleanup_global_resources()
        
        return {
            "success": True,
            "message": "모든 리소스가 정리되었습니다"
        }
    
    except Exception as e:
        logger.error(f"리소스 정리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"리소스 정리 실패: {str(e)}")

@router.get("/health-check")
async def optimization_health_check() -> Dict[str, Any]:
    """
    최적화 시스템 상태 확인
    """
    
    try:
        # 기본 상태 확인
        ocr_stats = optimized_ocr_service.get_optimization_stats()
        resource_stats = resource_manager.get_comprehensive_stats()
        
        # 상태 판단
        memory_usage = resource_stats['current_memory']['memory_percent']
        cache_hit_rate = ocr_stats.get('metrics', {}).get('cache_hit_rate', 0)
        
        status = "healthy"
        if memory_usage > 90:
            status = "critical"
        elif memory_usage > 80 or cache_hit_rate < 0.3:
            status = "warning"
        
        return {
            "success": True,
            "status": status,
            "data": {
                "memory_usage_percent": memory_usage,
                "cache_hit_rate": cache_hit_rate,
                "optimization_active": True,
                "resource_pools_active": len(resource_stats['memory_pools']),
                "recommendations": _get_optimization_recommendations(memory_usage, cache_hit_rate)
            }
        }
    
    except Exception as e:
        logger.error(f"상태 확인 실패: {e}")
        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }

def _get_optimization_recommendations(memory_usage: float, cache_hit_rate: float) -> List[str]:
    """최적화 권장사항 생성"""
    recommendations = []
    
    if memory_usage > 80:
        recommendations.append("메모리 사용량이 높습니다. 메모리 최적화를 실행하세요.")
    
    if cache_hit_rate < 0.5:
        recommendations.append("캐시 효율성이 낮습니다. 캐시 크기를 늘리거나 캐시 전략을 검토하세요.")
    
    if memory_usage < 50 and cache_hit_rate > 0.8:
        recommendations.append("시스템이 최적 상태입니다.")
    
    if not recommendations:
        recommendations.append("시스템 상태가 양호합니다.")
    
    return recommendations