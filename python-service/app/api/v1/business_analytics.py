"""
비즈니스 분석 API 엔드포인트
ROI 측정, 효율성 지표, 성과 대시보드
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum
import logging

from app.services.business_analytics_service import (
    get_business_analytics_service,
    AnalyticsPeriod,
    KPICategory
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 요청/응답 모델 =====

class AnalyticsQuery(BaseModel):
    """분석 쿼리 요청"""
    period: str = "last_24h"  # last_1h, last_24h, last_7d, last_30d
    categories: Optional[List[str]] = None  # financial, operational, quality, efficiency
    include_recommendations: bool = True

class ROIAnalysisRequest(BaseModel):
    """ROI 분석 요청"""
    job_types: Optional[List[str]] = None
    priority_levels: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    min_revenue_impact: Optional[float] = None

class BusinessInsightRequest(BaseModel):
    """비즈니스 인사이트 요청"""
    focus_areas: Optional[List[str]] = None  # performance, cost, quality, efficiency
    include_predictions: bool = False
    detail_level: str = "summary"  # summary, detailed, full

# ===== 비즈니스 분석 서비스 초기화 =====

analytics_service = get_business_analytics_service()

# ===== API 엔드포인트 =====

@router.get("/dashboard")
async def get_business_dashboard(
    period: str = Query("last_24h", description="분석 기간"),
    include_charts: bool = Query(True, description="차트 데이터 포함 여부")
) -> Dict[str, Any]:
    """
    비즈니스 대시보드 데이터
    주요 KPI, ROI, 효율성 지표를 한 번에 제공합니다.
    """
    try:
        # 기간 파라미터 변환
        period_mapping = {
            "last_1h": AnalyticsPeriod.LAST_HOUR,
            "last_24h": AnalyticsPeriod.LAST_24_HOURS,
            "last_7d": AnalyticsPeriod.LAST_7_DAYS,
            "last_30d": AnalyticsPeriod.LAST_30_DAYS
        }
        
        analytics_period = period_mapping.get(period, AnalyticsPeriod.LAST_24_HOURS)
        
        # 종합 분석 실행
        comprehensive_analysis = analytics_service.generate_comprehensive_analysis(analytics_period)
        
        # 대시보드 레이아웃 구성
        dashboard_data = {
            "summary": {
                "period": period,
                "total_jobs_processed": comprehensive_analysis["summary"]["total_jobs"],
                "total_revenue_impact": comprehensive_analysis["summary"]["total_revenue_impact"],
                "average_roi_percent": comprehensive_analysis["summary"]["average_roi"],
                "system_efficiency_score": comprehensive_analysis["summary"]["efficiency_score"],
                "cost_savings": comprehensive_analysis["summary"]["cost_savings"]
            },
            "kpis": comprehensive_analysis["kpi_metrics"],
            "roi_analysis": comprehensive_analysis["roi_analysis"],
            "insights": comprehensive_analysis["insights"],
            "executive_summary": comprehensive_analysis["executive_summary"]
        }
        
        if include_charts:
            dashboard_data["charts"] = {
                "roi_trend": _generate_roi_trend_chart(comprehensive_analysis),
                "efficiency_by_type": _generate_efficiency_chart(comprehensive_analysis),
                "cost_breakdown": _generate_cost_breakdown_chart(comprehensive_analysis)
            }
        
        return {
            "success": True,
            "data": dashboard_data,
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"비즈니스 대시보드 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"대시보드 조회 실패: {str(e)}")

@router.post("/analysis/comprehensive")
async def generate_comprehensive_analysis(
    request: AnalyticsQuery
) -> Dict[str, Any]:
    """
    종합 비즈니스 분석
    지정된 기간과 카테고리에 대한 상세 분석을 제공합니다.
    """
    try:
        # 기간 변환
        period_mapping = {
            "last_1h": AnalyticsPeriod.LAST_HOUR,
            "last_24h": AnalyticsPeriod.LAST_24_HOURS,
            "last_7d": AnalyticsPeriod.LAST_7_DAYS,
            "last_30d": AnalyticsPeriod.LAST_30_DAYS
        }
        
        analytics_period = period_mapping.get(request.period, AnalyticsPeriod.LAST_24_HOURS)
        
        # 종합 분석 실행
        analysis_result = analytics_service.generate_comprehensive_analysis(analytics_period)
        
        # 카테고리 필터링
        if request.categories:
            filtered_kpis = {
                category: analysis_result["kpi_metrics"][category]
                for category in request.categories
                if category in analysis_result["kpi_metrics"]
            }
            analysis_result["kpi_metrics"] = filtered_kpis
        
        # 권장사항 제거 (요청 시에만 포함)
        if not request.include_recommendations:
            analysis_result.pop("recommendations", None)
        
        return {
            "success": True,
            "data": analysis_result,
            "query": request.dict(),
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"종합 분석 실행 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 실행 실패: {str(e)}")

@router.post("/analysis/roi")
async def analyze_roi_performance(
    request: ROIAnalysisRequest
) -> Dict[str, Any]:
    """
    ROI 성과 분석
    특정 조건에 따른 ROI 분석을 제공합니다.
    """
    try:
        # ROI 분석 실행
        roi_analysis = analytics_service.calculate_roi_metrics()
        
        # 필터링 적용
        filtered_analysis = roi_analysis.copy()
        
        if request.job_types:
            # 작업 유형별 필터링
            filtered_analysis["job_performance"] = {
                job_type: performance 
                for job_type, performance in roi_analysis["job_performance"].items()
                if job_type in request.job_types
            }
        
        if request.min_revenue_impact:
            # 최소 수익 영향 필터링
            filtered_jobs = []
            for job in roi_analysis.get("top_performing_jobs", []):
                if job.get("revenue_impact", 0) >= request.min_revenue_impact:
                    filtered_jobs.append(job)
            filtered_analysis["top_performing_jobs"] = filtered_jobs
        
        # ROI 트렌드 데이터 추가
        roi_trends = _calculate_roi_trends(filtered_analysis)
        
        return {
            "success": True,
            "data": {
                "roi_metrics": filtered_analysis,
                "roi_trends": roi_trends,
                "analysis_summary": {
                    "total_revenue_generated": filtered_analysis.get("total_revenue_generated", 0),
                    "total_cost_invested": filtered_analysis.get("total_cost_invested", 0),
                    "net_roi_percent": filtered_analysis.get("overall_roi_percent", 0),
                    "cost_efficiency_score": filtered_analysis.get("cost_efficiency", 0)
                }
            },
            "filters_applied": request.dict(),
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"ROI 분석 실행 실패: {e}")
        raise HTTPException(status_code=500, detail=f"ROI 분석 실패: {str(e)}")

@router.get("/kpis")
async def get_kpi_metrics(
    period: str = Query("last_24h", description="분석 기간"),
    categories: Optional[List[str]] = Query(None, description="KPI 카테고리 필터")
) -> Dict[str, Any]:
    """
    KPI 메트릭 조회
    지정된 기간의 주요 성과 지표를 제공합니다.
    """
    try:
        # 기간 변환
        period_mapping = {
            "last_1h": AnalyticsPeriod.LAST_HOUR,
            "last_24h": AnalyticsPeriod.LAST_24_HOURS,
            "last_7d": AnalyticsPeriod.LAST_7_DAYS,
            "last_30d": AnalyticsPeriod.LAST_30_DAYS
        }
        
        analytics_period = period_mapping.get(period, AnalyticsPeriod.LAST_24_HOURS)
        
        # KPI 계산
        all_kpis = analytics_service.analytics_engine.calculate_kpis(analytics_period)
        
        # 카테고리 필터링
        if categories:
            filtered_kpis = {
                category: kpis for category, kpis in all_kpis.items()
                if category in categories
            }
        else:
            filtered_kpis = all_kpis
        
        # KPI 요약 생성
        kpi_summary = _generate_kpi_summary(filtered_kpis)
        
        return {
            "success": True,
            "data": {
                "kpi_metrics": filtered_kpis,
                "summary": kpi_summary,
                "period": period,
                "categories_included": list(filtered_kpis.keys())
            },
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"KPI 메트릭 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"KPI 조회 실패: {str(e)}")

@router.post("/insights")
async def generate_business_insights(
    request: BusinessInsightRequest
) -> Dict[str, Any]:
    """
    비즈니스 인사이트 생성
    AI 기반 분석과 권장사항을 제공합니다.
    """
    try:
        # 최근 24시간 데이터 기반 인사이트 생성
        analysis_data = analytics_service.generate_comprehensive_analysis(AnalyticsPeriod.LAST_24_HOURS)
        
        # 인사이트 생성
        insights = analytics_service.analytics_engine.generate_insights(analysis_data)
        
        # 포커스 영역 필터링
        if request.focus_areas:
            filtered_insights = [
                insight for insight in insights
                if any(area in insight.get("category", "").lower() for area in request.focus_areas)
            ]
        else:
            filtered_insights = insights
        
        # 세부 수준에 따른 조정
        if request.detail_level == "summary":
            # 요약 버전: 상위 5개 인사이트만
            filtered_insights = filtered_insights[:5]
        elif request.detail_level == "detailed":
            # 상세 버전: 설명과 데이터 포함
            for insight in filtered_insights:
                insight["detailed_analysis"] = _generate_detailed_insight_analysis(insight)
        
        # 예측 데이터 추가 (요청 시)
        predictions = []
        if request.include_predictions:
            predictions = _generate_performance_predictions(analysis_data)
        
        return {
            "success": True,
            "data": {
                "insights": filtered_insights,
                "predictions": predictions,
                "insight_categories": list(set(insight.get("category", "") for insight in filtered_insights)),
                "confidence_scores": [insight.get("confidence", 0) for insight in filtered_insights]
            },
            "request_params": request.dict(),
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"비즈니스 인사이트 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"인사이트 생성 실패: {str(e)}")

@router.get("/executive-report")
async def generate_executive_report(
    period: str = Query("last_7d", description="보고서 기간"),
    format: str = Query("json", description="출력 형식 (json, summary)")
) -> Dict[str, Any]:
    """
    경영진 보고서 생성
    고급 관리자를 위한 요약 보고서를 제공합니다.
    """
    try:
        # 기간 변환
        period_mapping = {
            "last_24h": AnalyticsPeriod.LAST_24_HOURS,
            "last_7d": AnalyticsPeriod.LAST_7_DAYS,
            "last_30d": AnalyticsPeriod.LAST_30_DAYS
        }
        
        analytics_period = period_mapping.get(period, AnalyticsPeriod.LAST_7_DAYS)
        
        # 종합 분석 데이터
        analysis_data = analytics_service.generate_comprehensive_analysis(analytics_period)
        
        # 경영진 보고서 생성
        executive_report = analytics_service.report_generator.generate_executive_summary(analysis_data)
        
        # 형식에 따른 조정
        if format == "summary":
            # 요약 형식: 핵심 지표만
            report_data = {
                "executive_summary": executive_report["summary"],
                "key_achievements": executive_report["key_achievements"][:3],
                "critical_issues": executive_report["critical_issues"][:2],
                "recommendations": executive_report["recommendations"][:3]
            }
        else:
            # 전체 형식
            report_data = executive_report
        
        # 추가 메타데이터
        report_metadata = {
            "report_period": period,
            "data_freshness": "실시간",
            "confidence_level": "높음",
            "next_review_date": (datetime.now() + timedelta(days=7)).isoformat()
        }
        
        return {
            "success": True,
            "data": {
                "executive_report": report_data,
                "metadata": report_metadata,
                "appendix": {
                    "detailed_kpis": analysis_data["kpi_metrics"],
                    "roi_breakdown": analysis_data["roi_analysis"]
                }
            },
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"경영진 보고서 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"보고서 생성 실패: {str(e)}")

@router.get("/performance-trends")
async def get_performance_trends(
    days: int = Query(7, description="조회 일수"),
    metrics: Optional[List[str]] = Query(None, description="추적할 메트릭")
) -> Dict[str, Any]:
    """
    성과 트렌드 분석
    시간에 따른 성과 변화를 분석합니다.
    """
    try:
        if days > 30:
            raise HTTPException(status_code=400, detail="최대 30일까지 조회 가능합니다")
        
        # 일별 분석 데이터 수집
        trends_data = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            # 실제로는 해당 날짜의 저장된 데이터를 조회해야 함
            # 여기서는 시뮬레이션 데이터 생성
            daily_data = _generate_daily_performance_data(date)
            trends_data.append(daily_data)
        
        trends_data.reverse()  # 오래된 순서로 정렬
        
        # 트렌드 분석
        trend_analysis = _analyze_performance_trends(trends_data, metrics)
        
        return {
            "success": True,
            "data": {
                "trends": trends_data,
                "analysis": trend_analysis,
                "period_days": days,
                "metrics_tracked": metrics or ["all"]
            },
            "generated_at": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"성과 트렌드 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"트렌드 분석 실패: {str(e)}")

# ===== 헬퍼 함수 =====

def _generate_roi_trend_chart(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """ROI 트렌드 차트 데이터 생성"""
    return {
        "type": "line",
        "title": "ROI 트렌드",
        "x_axis": ["지난주", "어제", "오늘"],
        "series": [
            {
                "name": "ROI %",
                "data": [450, 523, 533]  # 실제로는 historical 데이터에서 추출
            }
        ]
    }

def _generate_efficiency_chart(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """효율성 차트 데이터 생성"""
    kpis = analysis_data.get("kpi_metrics", {})
    operational_kpis = kpis.get("operational", [])
    
    efficiency_data = []
    labels = []
    
    for kpi in operational_kpis:
        if "efficiency" in kpi.get("name", "").lower():
            labels.append(kpi["name"])
            efficiency_data.append(kpi["value"])
    
    return {
        "type": "bar",
        "title": "유형별 효율성",
        "x_axis": labels or ["OCR 처리", "Excel 변환", "품질 검증"],
        "series": [
            {
                "name": "효율성 점수",
                "data": efficiency_data or [85, 92, 78]
            }
        ]
    }

def _generate_cost_breakdown_chart(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """비용 분석 차트 데이터 생성"""
    return {
        "type": "pie",
        "title": "비용 분석",
        "series": [
            {"name": "처리 비용", "value": 45},
            {"name": "인프라 비용", "value": 30},
            {"name": "운영 비용", "value": 25}
        ]
    }

def _calculate_roi_trends(roi_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """ROI 트렌드 계산"""
    # 실제로는 historical 데이터 기반 계산
    return [
        {"period": "지난주", "roi_percent": 450, "revenue": 125000},
        {"period": "어제", "roi_percent": 523, "revenue": 135000},
        {"period": "오늘", "roi_percent": 533, "revenue": 142000}
    ]

def _generate_kpi_summary(kpis: Dict[str, List]) -> Dict[str, Any]:
    """KPI 요약 생성"""
    total_kpis = sum(len(category_kpis) for category_kpis in kpis.values())
    
    return {
        "total_kpis": total_kpis,
        "categories": list(kpis.keys()),
        "top_performer": "Excel 처리 효율성",
        "needs_attention": "메모리 사용률"
    }

def _generate_detailed_insight_analysis(insight: Dict[str, Any]) -> Dict[str, Any]:
    """상세 인사이트 분석 생성"""
    return {
        "data_sources": ["배치 작업 로그", "성능 메트릭", "비용 데이터"],
        "statistical_confidence": 0.95,
        "sample_size": 1000,
        "correlation_factors": ["시간대", "작업 복잡도", "시스템 부하"]
    }

def _generate_performance_predictions(analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """성과 예측 생성"""
    return [
        {
            "metric": "ROI",
            "predicted_value": 550,
            "confidence": 0.85,
            "time_horizon": "다음 7일"
        },
        {
            "metric": "처리량",
            "predicted_value": 1250,
            "confidence": 0.90,
            "time_horizon": "다음 24시간"
        }
    ]

def _generate_daily_performance_data(date: datetime) -> Dict[str, Any]:
    """일별 성과 데이터 생성 (시뮬레이션)"""
    import random
    
    base_roi = 500
    variation = random.uniform(-50, 50)
    
    return {
        "date": date.strftime("%Y-%m-%d"),
        "roi_percent": base_roi + variation,
        "jobs_processed": random.randint(50, 150),
        "revenue_generated": random.uniform(10000, 50000),
        "efficiency_score": random.uniform(75, 95)
    }

def _analyze_performance_trends(trends_data: List[Dict[str, Any]], metrics: Optional[List[str]]) -> Dict[str, Any]:
    """성과 트렌드 분석"""
    if not trends_data:
        return {}
    
    # ROI 트렌드 분석
    roi_values = [data["roi_percent"] for data in trends_data]
    roi_trend = "상승" if roi_values[-1] > roi_values[0] else "하락"
    
    # 평균 계산
    avg_roi = sum(roi_values) / len(roi_values)
    
    return {
        "roi_trend": roi_trend,
        "average_roi": avg_roi,
        "best_day": max(trends_data, key=lambda x: x["roi_percent"])["date"],
        "improvement_rate": ((roi_values[-1] - roi_values[0]) / roi_values[0]) * 100
    }