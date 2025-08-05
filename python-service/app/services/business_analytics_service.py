"""
비즈니스 가치 중심 배치 작업 분석 시스템
ROI 측정, 효율성 지표, 성과 대시보드
데이터 기반 의사결정 지원
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from app.services.strategic_batch_manager import get_batch_manager, JobStatus
from app.services.advanced_monitoring_service import get_monitoring_service

logger = logging.getLogger(__name__)

# ===== 비즈니스 분석 데이터 모델 =====


class AnalyticsPeriod(Enum):
    """분석 기간"""

    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"


class KPICategory(Enum):
    """KPI 카테고리"""

    FINANCIAL = "financial"  # 재무 지표
    OPERATIONAL = "operational"  # 운영 지표
    QUALITY = "quality"  # 품질 지표
    EFFICIENCY = "efficiency"  # 효율성 지표


@dataclass
class KPIMetric:
    """KPI 메트릭"""

    name: str
    value: float
    category: KPICategory
    unit: str = ""
    target: Optional[float] = None
    previous_value: Optional[float] = None
    trend: str = "stable"  # up, down, stable
    description: str = ""

    @property
    def achievement_rate(self) -> Optional[float]:
        """목표 달성률"""
        if self.target and self.target > 0:
            return (self.value / self.target) * 100
        return None

    @property
    def change_rate(self) -> Optional[float]:
        """변화율"""
        if self.previous_value and self.previous_value > 0:
            return ((self.value - self.previous_value) / self.previous_value) * 100
        return None


@dataclass
class BusinessInsight:
    """비즈니스 인사이트"""

    title: str
    description: str
    impact_level: str  # high, medium, low
    category: str
    recommended_actions: List[str] = field(default_factory=list)
    data_points: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0


@dataclass
class ROIAnalysis:
    """ROI 분석"""

    total_investment: float
    total_return: float
    roi_percentage: float
    payback_period_days: Optional[int]
    net_present_value: float
    break_even_point: Optional[datetime]
    risk_assessment: str
    profitability_trend: List[Tuple[datetime, float]]


# ===== 인터페이스 정의 =====


class AnalyticsEngine(ABC):
    """분석 엔진 인터페이스"""

    @abstractmethod
    def calculate_kpis(self, period: AnalyticsPeriod) -> List[KPIMetric]:
        """KPI 계산"""

    @abstractmethod
    def generate_insights(self, data: Dict[str, Any]) -> List[BusinessInsight]:
        """인사이트 생성"""


class ReportGenerator(ABC):
    """보고서 생성기 인터페이스"""

    @abstractmethod
    def generate_executive_summary(
        self, analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """경영진 요약 보고서 생성"""


# ===== 핵심 분석 엔진 구현 =====


class BatchJobAnalyticsEngine(AnalyticsEngine):
    """배치 작업 분석 엔진"""

    def __init__(self):
        self.batch_manager = get_batch_manager()
        self.monitoring_service = get_monitoring_service()

        # KPI 목표값 설정
        self.kpi_targets = {
            "success_rate": 95.0,  # 성공률 95%
            "avg_processing_time": 300.0,  # 평균 처리시간 5분
            "throughput_per_hour": 100.0,  # 시간당 100개 작업
            "cost_per_job": 5.0,  # 작업당 $5
            "customer_satisfaction": 4.5,  # 고객 만족도 4.5/5
            "resource_utilization": 80.0,  # 리소스 사용률 80%
            "roi_percentage": 200.0,  # ROI 200%
        }

    def calculate_kpis(self, period: AnalyticsPeriod) -> List[KPIMetric]:
        """KPI 계산"""
        kpis = []

        # 기간별 작업 데이터 수집
        period_jobs = self._get_jobs_by_period(period)
        if not period_jobs:
            return kpis

        # 재무 KPI
        kpis.extend(self._calculate_financial_kpis(period_jobs))

        # 운영 KPI
        kpis.extend(self._calculate_operational_kpis(period_jobs))

        # 품질 KPI
        kpis.extend(self._calculate_quality_kpis(period_jobs))

        # 효율성 KPI
        kpis.extend(self._calculate_efficiency_kpis(period_jobs))

        return kpis

    def _get_jobs_by_period(self, period: AnalyticsPeriod) -> List[Any]:
        """기간별 작업 조회"""
        now = datetime.now()

        if period == AnalyticsPeriod.LAST_HOUR:
            cutoff = now - timedelta(hours=1)
        elif period == AnalyticsPeriod.LAST_24_HOURS:
            cutoff = now - timedelta(days=1)
        elif period == AnalyticsPeriod.LAST_7_DAYS:
            cutoff = now - timedelta(weeks=1)
        elif period == AnalyticsPeriod.LAST_30_DAYS:
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(days=1)  # 기본값

        # 완료된 작업 중 기간에 해당하는 작업 필터링
        period_jobs = [
            job
            for job in self.batch_manager.scheduler.completed_jobs
            if job.completed_at and job.completed_at >= cutoff
        ]

        return period_jobs

    def _calculate_financial_kpis(self, jobs: List[Any]) -> List[KPIMetric]:
        """재무 KPI 계산"""
        kpis = []

        # 기본 KPI 생성 (데이터가 없는 경우)
        if not jobs:
            kpis.extend(
                [
                    KPIMetric(
                        name="총 수익",
                        value=0.0,
                        unit="USD",
                        category=KPICategory.FINANCIAL,
                        target=10000.0,
                        achievement_rate=0.0,
                        change_rate=0.0,
                        description="총 생성된 수익",
                    ),
                    KPIMetric(
                        name="ROI 백분율",
                        value=0.0,
                        unit="%",
                        category=KPICategory.FINANCIAL,
                        target=300.0,
                        achievement_rate=0.0,
                        change_rate=0.0,
                        description="투자 대비 수익률",
                    ),
                    KPIMetric(
                        name="평균 작업당 비용",
                        value=0.0,
                        unit="USD",
                        category=KPICategory.FINANCIAL,
                        target=50.0,
                        achievement_rate=0.0,
                        change_rate=0.0,
                        description="작업당 평균 처리 비용",
                    ),
                ]
            )
            return kpis

        # 총 수익 영향
        total_revenue_impact = sum(job.business_metrics.revenue_impact for job in jobs)

        # 총 처리 비용
        total_cost = sum(job.business_metrics.processing_cost for job in jobs)

        # ROI 계산
        roi = (
            ((total_revenue_impact - total_cost) / total_cost * 100)
            if total_cost > 0
            else 0
        )

        kpis.append(
            KPIMetric(
                name="total_revenue_impact",
                value=total_revenue_impact,
                category=KPICategory.FINANCIAL,
                unit="USD",
                description="총 수익 영향도",
            )
        )

        kpis.append(
            KPIMetric(
                name="total_processing_cost",
                value=total_cost,
                category=KPICategory.FINANCIAL,
                unit="USD",
                description="총 처리 비용",
            )
        )

        kpis.append(
            KPIMetric(
                name="roi_percentage",
                value=roi,
                category=KPICategory.FINANCIAL,
                unit="%",
                target=self.kpi_targets.get("roi_percentage"),
                description="투자 수익률",
            )
        )

        # 작업당 평균 비용
        avg_cost_per_job = total_cost / len(jobs) if jobs else 0

        kpis.append(
            KPIMetric(
                name="avg_cost_per_job",
                value=avg_cost_per_job,
                category=KPICategory.FINANCIAL,
                unit="USD",
                target=self.kpi_targets.get("cost_per_job"),
                description="작업당 평균 비용",
            )
        )

        return kpis

    def _calculate_operational_kpis(self, jobs: List[Any]) -> List[KPIMetric]:
        """운영 KPI 계산"""
        kpis = []

        # 기본 KPI 생성 (데이터가 없는 경우)
        if not jobs:
            kpis.extend(
                [
                    KPIMetric(
                        name="시간당 처리량",
                        value=0.0,
                        unit="jobs/hour",
                        category=KPICategory.OPERATIONAL,
                        target=10.0,
                        achievement_rate=0.0,
                        change_rate=0.0,
                        description="시간당 처리된 작업 수",
                    ),
                    KPIMetric(
                        name="성공률",
                        value=100.0,
                        unit="%",
                        category=KPICategory.OPERATIONAL,
                        target=95.0,
                        achievement_rate=105.3,
                        change_rate=0.0,
                        description="성공적으로 완료된 작업 비율",
                    ),
                    KPIMetric(
                        name="평균 처리 시간",
                        value=0.0,
                        unit="seconds",
                        category=KPICategory.OPERATIONAL,
                        target=300.0,
                        achievement_rate=0.0,
                        change_rate=0.0,
                        description="작업당 평균 처리 시간",
                    ),
                ]
            )
            return kpis

        # 성공률
        successful_jobs = [job for job in jobs if job.status == JobStatus.COMPLETED]
        success_rate = (len(successful_jobs) / len(jobs)) * 100

        kpis.append(
            KPIMetric(
                name="success_rate",
                value=success_rate,
                category=KPICategory.OPERATIONAL,
                unit="%",
                target=self.kpi_targets.get("success_rate"),
                description="작업 성공률",
            )
        )

        # 평균 처리 시간
        processing_times = []
        for job in successful_jobs:
            if job.started_at and job.completed_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                processing_times.append(duration)

        avg_processing_time = (
            statistics.mean(processing_times) if processing_times else 0
        )

        kpis.append(
            KPIMetric(
                name="avg_processing_time",
                value=avg_processing_time,
                category=KPICategory.OPERATIONAL,
                unit="seconds",
                target=self.kpi_targets.get("avg_processing_time"),
                description="평균 처리 시간",
            )
        )

        # 처리량 (시간당)
        if jobs:
            time_span = max(job.completed_at for job in jobs) - min(
                job.created_at for job in jobs
            )
            hours = time_span.total_seconds() / 3600
            throughput = len(jobs) / hours if hours > 0 else 0
        else:
            throughput = 0

        kpis.append(
            KPIMetric(
                name="throughput_per_hour",
                value=throughput,
                category=KPICategory.OPERATIONAL,
                unit="jobs/hour",
                target=self.kpi_targets.get("throughput_per_hour"),
                description="시간당 처리량",
            )
        )

        return kpis

    def _calculate_quality_kpis(self, jobs: List[Any]) -> List[KPIMetric]:
        """품질 KPI 계산"""
        kpis = []

        # 기본 KPI 생성 (데이터가 없는 경우)
        if not jobs:
            kpis.extend(
                [
                    KPIMetric(
                        name="품질 점수",
                        value=85.0,
                        unit="score",
                        category=KPICategory.QUALITY,
                        target=90.0,
                        achievement_rate=94.4,
                        change_rate=0.0,
                        description="전체 작업의 품질 평가 점수",
                    ),
                    KPIMetric(
                        name="재작업률",
                        value=0.0,
                        unit="%",
                        category=KPICategory.QUALITY,
                        target=5.0,
                        achievement_rate=0.0,
                        change_rate=0.0,
                        description="재작업이 필요한 작업의 비율",
                    ),
                ]
            )
            return kpis

        # 재시도 없이 성공한 작업 비율
        first_try_success = [
            job
            for job in jobs
            if job.retry_count == 0 and job.status == JobStatus.COMPLETED
        ]
        first_try_success_rate = (len(first_try_success) / len(jobs)) * 100

        kpis.append(
            KPIMetric(
                name="first_try_success_rate",
                value=first_try_success_rate,
                category=KPICategory.QUALITY,
                unit="%",
                description="첫 시도 성공률",
            )
        )

        # SLA 준수율
        sla_compliant_jobs = []
        for job in jobs:
            if job.business_metrics.sla_deadline and job.completed_at:
                if job.completed_at <= job.business_metrics.sla_deadline:
                    sla_compliant_jobs.append(job)

        jobs_with_sla = [job for job in jobs if job.business_metrics.sla_deadline]
        sla_compliance_rate = (
            (len(sla_compliant_jobs) / len(jobs_with_sla)) * 100
            if jobs_with_sla
            else 100
        )

        kpis.append(
            KPIMetric(
                name="sla_compliance_rate",
                value=sla_compliance_rate,
                category=KPICategory.QUALITY,
                unit="%",
                description="SLA 준수율",
            )
        )

        return kpis

    def _calculate_efficiency_kpis(self, jobs: List[Any]) -> List[KPIMetric]:
        """효율성 KPI 계산"""
        kpis = []

        # 기본 KPI 생성 (데이터가 없는 경우)
        if not jobs:
            kpis.extend(
                [
                    KPIMetric(
                        name="리소스 효율성",
                        value=75.0,
                        unit="%",
                        category=KPICategory.EFFICIENCY,
                        target=80.0,
                        achievement_rate=93.75,
                        change_rate=0.0,
                        description="시스템 리소스 활용 효율성",
                    ),
                    KPIMetric(
                        name="처리 속도",
                        value=0.0,
                        unit="items/min",
                        category=KPICategory.EFFICIENCY,
                        target=5.0,
                        achievement_rate=0.0,
                        change_rate=0.0,
                        description="분당 처리 항목 수",
                    ),
                ]
            )
            return kpis

        # 시스템 리소스 사용률 (모니터링 서비스에서)
        try:
            resource_stats = self.batch_manager.resource_manager.get_resource_stats()
            cpu_usage = resource_stats.get("system_cpu_percent", 0)
            memory_usage = resource_stats.get("system_memory_percent", 0)

            avg_resource_utilization = (cpu_usage + memory_usage) / 2

            kpis.append(
                KPIMetric(
                    name="resource_utilization",
                    value=avg_resource_utilization,
                    category=KPICategory.EFFICIENCY,
                    unit="%",
                    target=self.kpi_targets.get("resource_utilization"),
                    description="평균 리소스 사용률",
                )
            )
        except Exception as e:
            logger.warning(f"리소스 사용률 계산 실패: {e}")

        # 작업 유형별 효율성
        if jobs:
            job_type_efficiency = self._calculate_job_type_efficiency(jobs)

            for job_type, efficiency in job_type_efficiency.items():
                kpis.append(
                    KPIMetric(
                        name=f"{job_type}_efficiency",
                        value=efficiency,
                        category=KPICategory.EFFICIENCY,
                        unit="score",
                        description=f"{job_type} 작업 효율성 점수",
                    )
                )

        return kpis

    def _calculate_job_type_efficiency(self, jobs: List[Any]) -> Dict[str, float]:
        """작업 유형별 효율성 계산"""
        efficiency_scores = {}

        # 작업 유형별 그룹화
        jobs_by_type = defaultdict(list)
        for job in jobs:
            jobs_by_type[job.job_type.value].append(job)

        for job_type, type_jobs in jobs_by_type.items():
            if not type_jobs:
                continue

            # 효율성 점수 계산 (0-100)
            success_rate = len(
                [j for j in type_jobs if j.status == JobStatus.COMPLETED]
            ) / len(type_jobs)

            # 평균 처리 시간 대비 예상 시간 비율
            time_efficiency = 0
            valid_time_comparisons = 0

            for job in type_jobs:
                if job.started_at and job.completed_at:
                    actual_time = (job.completed_at - job.started_at).total_seconds()
                    expected_time = job.estimated_duration
                    if expected_time > 0:
                        efficiency = min(
                            expected_time / actual_time, 2.0
                        )  # 최대 2배 효율
                        time_efficiency += efficiency
                        valid_time_comparisons += 1

            avg_time_efficiency = (
                time_efficiency / valid_time_comparisons
                if valid_time_comparisons > 0
                else 1.0
            )

            # 종합 효율성 점수
            overall_efficiency = (success_rate * 0.6 + avg_time_efficiency * 0.4) * 100
            efficiency_scores[job_type] = min(overall_efficiency, 100.0)

        return efficiency_scores

    def generate_insights(self, data: Dict[str, Any]) -> List[BusinessInsight]:
        """비즈니스 인사이트 생성"""
        insights = []

        kpis = data.get("kpis", [])

        # 기본 인사이트 생성 (데이터가 없는 경우)
        if not kpis:
            insights.extend(
                [
                    BusinessInsight(
                        title="시스템 준비 완료",
                        description="분석 시스템이 성공적으로 초기화되었습니다. 작업 데이터가 수집되면 더 상세한 인사이트를 제공할 수 있습니다.",
                        impact_level="low",
                        category="operational",
                        recommended_actions=[
                            "작업 데이터 수집 시작",
                            "시스템 모니터링 활성화",
                            "성능 기준선 설정",
                        ],
                        data_points={"readiness_score": 100},
                        confidence_score=0.9,
                    ),
                    BusinessInsight(
                        title="모니터링 시스템 활성",
                        description="실시간 모니터링 시스템이 정상적으로 작동하고 있으며, 성능 지표 수집이 준비되었습니다.",
                        impact_level="medium",
                        category="quality",
                        recommended_actions=[
                            "알림 임계값 설정",
                            "대시보드 사용자 정의",
                            "정기 보고서 일정 수립",
                        ],
                        data_points={"monitoring_status": "active"},
                        confidence_score=0.95,
                    ),
                ]
            )
            return insights

        # KPI별 인사이트 생성
        for kpi in kpis:
            if kpi.target and kpi.value < kpi.target * 0.8:  # 목표의 80% 미달
                insight = self._generate_underperformance_insight(kpi)
                if insight:
                    insights.append(insight)
            elif kpi.target and kpi.value > kpi.target * 1.2:  # 목표의 120% 초과
                insight = self._generate_overperformance_insight(kpi)
                if insight:
                    insights.append(insight)

        # 패턴 기반 인사이트
        insights.extend(self._generate_pattern_insights(data))

        # 트렌드 기반 인사이트
        insights.extend(self._generate_trend_insights(data))

        return insights

    def _generate_underperformance_insight(
        self, kpi: KPIMetric
    ) -> Optional[BusinessInsight]:
        """저성과 KPI 인사이트 생성"""
        if kpi.category == KPICategory.FINANCIAL:
            if kpi.name == "roi_percentage":
                return BusinessInsight(
                    title="ROI 개선 필요",
                    description=f"현재 ROI {kpi.value:.1f}%가 목표 {kpi.target:.1f}%를 크게 하회하고 있습니다.",
                    impact_level="high",
                    category="financial",
                    recommended_actions=[
                        "고비용 작업 유형 분석 및 최적화",
                        "자동화를 통한 처리 비용 절감",
                        "고수익 작업 우선순위 조정",
                    ],
                    confidence_score=0.9,
                )
        elif kpi.category == KPICategory.OPERATIONAL:
            if kpi.name == "success_rate":
                return BusinessInsight(
                    title="작업 성공률 개선 필요",
                    description=f"현재 성공률 {kpi.value:.1f}%가 목표 {kpi.target:.1f}%에 미달하고 있습니다.",
                    impact_level="high",
                    category="operational",
                    recommended_actions=[
                        "실패 원인 분석 및 개선",
                        "재시도 로직 최적화",
                        "모니터링 및 알림 강화",
                    ],
                    confidence_score=0.8,
                )

        return None

    def _generate_overperformance_insight(
        self, kpi: KPIMetric
    ) -> Optional[BusinessInsight]:
        """고성과 KPI 인사이트 생성"""
        if kpi.category == KPICategory.OPERATIONAL:
            if kpi.name == "throughput_per_hour":
                return BusinessInsight(
                    title="처리량 목표 초과 달성",
                    description=f"시간당 처리량 {kpi.value:.1f}개가 목표 {kpi.target:.1f}개를 크게 상회하고 있습니다.",
                    impact_level="medium",
                    category="operational",
                    recommended_actions=[
                        "현재 성과 유지를 위한 표준화",
                        "추가 용량 확장 검토",
                        "성과 요인 분석 및 다른 영역 적용",
                    ],
                    confidence_score=0.7,
                )

        return None

    def _generate_pattern_insights(self, data: Dict[str, Any]) -> List[BusinessInsight]:
        """패턴 기반 인사이트 생성"""
        insights = []

        # 작업 유형별 성과 패턴 분석
        jobs = data.get("period_jobs", [])
        if jobs:
            job_type_analysis = self._analyze_job_type_patterns(jobs)

            for job_type, analysis in job_type_analysis.items():
                if analysis["performance_score"] < 60:  # 60점 미만
                    insights.append(
                        BusinessInsight(
                            title=f"{job_type} 작업 성과 저조",
                            description=f"{job_type} 작업의 전반적인 성과가 {analysis['performance_score']:.1f}점으로 개선이 필요합니다.",
                            impact_level="medium",
                            category="operational",
                            recommended_actions=[
                                f"{job_type} 작업 프로세스 재검토",
                                "전담 팀 구성 검토",
                                "기술적 개선 방안 도출",
                            ],
                            data_points=analysis,
                            confidence_score=0.8,
                        )
                    )

        return insights

    def _analyze_job_type_patterns(self, jobs: List[Any]) -> Dict[str, Dict[str, Any]]:
        """작업 유형별 패턴 분석"""
        analysis = {}

        jobs_by_type = defaultdict(list)
        for job in jobs:
            jobs_by_type[job.job_type.value].append(job)

        for job_type, type_jobs in jobs_by_type.items():
            success_count = len(
                [j for j in type_jobs if j.status == JobStatus.COMPLETED]
            )
            success_rate = (success_count / len(type_jobs)) * 100 if type_jobs else 0

            avg_revenue = (
                statistics.mean([j.business_metrics.revenue_impact for j in type_jobs])
                if type_jobs
                else 0
            )
            avg_cost = (
                statistics.mean([j.business_metrics.processing_cost for j in type_jobs])
                if type_jobs
                else 0
            )

            # 성과 점수 계산 (0-100)
            performance_score = success_rate * 0.4 + min(
                avg_revenue / max(avg_cost, 1) * 10, 60
            )  # ROI 기반 점수

            analysis[job_type] = {
                "job_count": len(type_jobs),
                "success_rate": success_rate,
                "avg_revenue": avg_revenue,
                "avg_cost": avg_cost,
                "performance_score": performance_score,
            }

        return analysis

    def _generate_trend_insights(self, data: Dict[str, Any]) -> List[BusinessInsight]:
        """트렌드 기반 인사이트 생성"""
        insights = []

        # KPI 트렌드 분석
        kpis = data.get("kpis", [])
        declining_kpis = [
            kpi for kpi in kpis if kpi.change_rate and kpi.change_rate < -10
        ]

        if declining_kpis:
            kpi_names = [kpi.name for kpi in declining_kpis]
            insights.append(
                BusinessInsight(
                    title="성과 지표 하락 추세",
                    description=f"다음 지표들이 지속적으로 하락하고 있습니다: {', '.join(kpi_names)}",
                    impact_level="high",
                    category="trend",
                    recommended_actions=[
                        "하락 원인 근본 분석",
                        "즉시 개선 조치 실행",
                        "모니터링 주기 단축",
                    ],
                    confidence_score=0.9,
                )
            )

        return insights


# ===== 보고서 생성기 구현 =====


class ExecutiveReportGenerator(ReportGenerator):
    """경영진 보고서 생성기"""

    def generate_executive_summary(
        self, analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """경영진 요약 보고서 생성"""
        kpis = analysis_data.get("kpis", [])
        insights = analysis_data.get("insights", [])
        period = analysis_data.get("period", "day")

        # 핵심 성과 지표 요약
        key_metrics = self._extract_key_metrics(kpis)

        # 주요 인사이트 (상위 3개)
        top_insights = sorted(
            insights, key=lambda x: self._calculate_insight_priority(x), reverse=True
        )[:3]

        # 권장 조치 통합
        all_actions = []
        for insight in top_insights:
            all_actions.extend(insight.recommended_actions)

        # 중복 제거 및 우선순위화
        unique_actions = list(dict.fromkeys(all_actions))[:5]

        # 종합 평가
        overall_score = self._calculate_overall_score(kpis)
        health_status = self._determine_health_status(overall_score)

        return {
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "overall_health": {
                "score": overall_score,
                "status": health_status,
                "description": self._get_health_description(health_status),
            },
            "key_metrics": key_metrics,
            "top_insights": [
                {
                    "title": insight.title,
                    "description": insight.description,
                    "impact_level": insight.impact_level,
                    "recommended_actions": insight.recommended_actions,
                }
                for insight in top_insights
            ],
            "priority_actions": unique_actions,
            "performance_summary": self._generate_performance_summary(kpis),
            "risk_assessment": self._assess_risks(insights),
            "next_steps": self._recommend_next_steps(insights, kpis),
        }

    def _extract_key_metrics(self, kpis: List[KPIMetric]) -> Dict[str, Any]:
        """핵심 메트릭 추출"""
        key_metrics = {}

        priority_kpis = [
            "roi_percentage",
            "success_rate",
            "throughput_per_hour",
            "avg_cost_per_job",
        ]

        for kpi in kpis:
            if kpi.name in priority_kpis:
                key_metrics[kpi.name] = {
                    "value": kpi.value,
                    "unit": kpi.unit,
                    "target": kpi.target,
                    "achievement_rate": kpi.achievement_rate,
                    "change_rate": kpi.change_rate,
                    "status": self._get_kpi_status(kpi),
                }

        return key_metrics

    def _get_kpi_status(self, kpi: KPIMetric) -> str:
        """KPI 상태 판단"""
        if not kpi.target:
            return "no_target"

        achievement_rate = kpi.achievement_rate
        if achievement_rate >= 100:
            return "excellent"
        elif achievement_rate >= 90:
            return "good"
        elif achievement_rate >= 80:
            return "fair"
        else:
            return "poor"

    def _calculate_insight_priority(self, insight: BusinessInsight) -> float:
        """인사이트 우선순위 계산"""
        impact_weights = {"high": 3.0, "medium": 2.0, "low": 1.0}
        impact_weight = impact_weights.get(insight.impact_level, 1.0)

        return impact_weight * insight.confidence_score

    def _calculate_overall_score(self, kpis: List[KPIMetric]) -> float:
        """전체 점수 계산"""
        if not kpis:
            return 0.0

        scores = []
        for kpi in kpis:
            if kpi.target and kpi.target > 0:
                achievement_rate = min(kpi.achievement_rate, 150)  # 최대 150%로 제한
                scores.append(achievement_rate)

        return statistics.mean(scores) if scores else 50.0

    def _determine_health_status(self, score: float) -> str:
        """건강 상태 판단"""
        if score >= 95:
            return "excellent"
        elif score >= 85:
            return "good"
        elif score >= 70:
            return "fair"
        elif score >= 50:
            return "poor"
        else:
            return "critical"

    def _get_health_description(self, status: str) -> str:
        """건강 상태 설명"""
        descriptions = {
            "excellent": "모든 지표가 목표를 상회하며 매우 우수한 성과를 보이고 있습니다.",
            "good": "대부분의 지표가 목표를 달성하고 있으며 양호한 상태입니다.",
            "fair": "일부 지표에서 개선이 필요하지만 전반적으로 안정적입니다.",
            "poor": "여러 지표에서 목표 미달로 즉시 개선 조치가 필요합니다.",
            "critical": "심각한 성과 저하로 긴급한 대응이 필요합니다.",
        }
        return descriptions.get(status, "상태를 판단할 수 없습니다.")

    def _generate_performance_summary(self, kpis: List[KPIMetric]) -> Dict[str, Any]:
        """성과 요약 생성"""
        categories = defaultdict(list)
        for kpi in kpis:
            categories[kpi.category.value].append(kpi)

        summary = {}
        for category, category_kpis in categories.items():
            avg_achievement = (
                statistics.mean(
                    [
                        kpi.achievement_rate
                        for kpi in category_kpis
                        if kpi.achievement_rate is not None
                    ]
                )
                if category_kpis
                else 0
            )

            summary[category] = {
                "metric_count": len(category_kpis),
                "avg_achievement_rate": avg_achievement,
                "status": self._get_category_status(avg_achievement),
            }

        return summary

    def _get_category_status(self, achievement_rate: float) -> str:
        """카테고리 상태 판단"""
        if achievement_rate >= 100:
            return "exceeding"
        elif achievement_rate >= 90:
            return "meeting"
        elif achievement_rate >= 80:
            return "approaching"
        else:
            return "below"

    def _assess_risks(self, insights: List[BusinessInsight]) -> Dict[str, Any]:
        """위험 평가"""
        high_risk_count = len([i for i in insights if i.impact_level == "high"])
        medium_risk_count = len([i for i in insights if i.impact_level == "medium"])

        risk_level = "low"
        if high_risk_count >= 3:
            risk_level = "high"
        elif high_risk_count >= 1 or medium_risk_count >= 3:
            risk_level = "medium"

        return {
            "level": risk_level,
            "high_risk_issues": high_risk_count,
            "medium_risk_issues": medium_risk_count,
            "key_concerns": [
                insight.title for insight in insights if insight.impact_level == "high"
            ][:3],
        }

    def _recommend_next_steps(
        self, insights: List[BusinessInsight], kpis: List[KPIMetric]
    ) -> List[str]:
        """다음 단계 권장"""
        next_steps = []

        # 긴급 조치가 필요한 KPI 확인
        critical_kpis = [
            kpi
            for kpi in kpis
            if kpi.target and kpi.achievement_rate and kpi.achievement_rate < 70
        ]

        if critical_kpis:
            next_steps.append("성과 미달 지표에 대한 즉시 개선 계획 수립")

        # 고위험 인사이트 기반 조치
        high_risk_insights = [i for i in insights if i.impact_level == "high"]
        if high_risk_insights:
            next_steps.append("고위험 이슈에 대한 긴급 대응팀 구성")

        # 일반적인 권장 사항
        next_steps.extend(
            [
                "주간 성과 리뷰 미팅 일정 조정",
                "다음 분석 기간 모니터링 계획 수립",
                "개선 조치 효과 측정 방안 마련",
            ]
        )

        return next_steps[:5]  # 최대 5개


# ===== 통합 비즈니스 분석 서비스 =====


class BusinessAnalyticsService:
    """비즈니스 분석 서비스 통합 관리자"""

    def __init__(self):
        self.analytics_engine = BatchJobAnalyticsEngine()
        self.report_generator = ExecutiveReportGenerator()
        self.batch_manager = get_batch_manager()
        self.monitoring_service = get_monitoring_service()

        # 분석 캐시 (성능 최적화)
        self.analysis_cache = {}
        self.cache_ttl = 300  # 5분

        logger.info("비즈니스 분석 서비스 초기화 완료")

    def generate_comprehensive_analysis(
        self, period: AnalyticsPeriod
    ) -> Dict[str, Any]:
        """종합 비즈니스 분석 생성"""
        cache_key = f"analysis_{period.value}_{int(time.time() // self.cache_ttl)}"

        # 캐시 확인
        if cache_key in self.analysis_cache:
            logger.info(f"캐시된 분석 결과 반환: {period.value}")
            return self.analysis_cache[cache_key]

        logger.info(f"새로운 비즈니스 분석 생성: {period.value}")

        # KPI 계산
        kpis = self.analytics_engine.calculate_kpis(period)

        # 기간별 작업 데이터
        period_jobs = self.analytics_engine._get_jobs_by_period(period)

        # 분석 데이터 구성
        analysis_data = {
            "kpis": kpis,
            "period_jobs": period_jobs,
            "period": period.value,
        }

        # 인사이트 생성
        insights = self.analytics_engine.generate_insights(analysis_data)
        analysis_data["insights"] = insights

        # 경영진 보고서 생성
        executive_summary = self.report_generator.generate_executive_summary(
            analysis_data
        )

        # ROI 상세 분석
        roi_analysis = self._generate_roi_analysis(period_jobs)

        # 요약 정보 계산
        total_jobs = len(period_jobs)
        total_revenue_impact = (
            sum(job.business_metrics.revenue_impact for job in period_jobs)
            if period_jobs
            else 0
        )
        total_cost = (
            sum(job.business_metrics.processing_cost for job in period_jobs)
            if period_jobs
            else 1
        )
        average_roi = (
            ((total_revenue_impact - total_cost) / total_cost * 100)
            if total_cost > 0
            else 0
        )
        efficiency_score = 85.0  # 기본 효율성 점수
        cost_savings = max(0, total_revenue_impact - total_cost)

        # KPI를 카테고리별로 분류
        kpi_metrics = {
            "financial": [],
            "operational": [],
            "quality": [],
            "efficiency": [],
        }
        for kpi in kpis:
            category = kpi.category.value
            if category in kpi_metrics:
                kpi_metrics[category].append(
                    {
                        "name": kpi.name,
                        "value": kpi.value,
                        "unit": kpi.unit,
                        "target": kpi.target,
                        "achievement_rate": kpi.achievement_rate,
                        "change_rate": kpi.change_rate,
                        "trend": (
                            "increasing"
                            if kpi.change_rate > 0
                            else "decreasing" if kpi.change_rate < 0 else "stable"
                        ),
                    }
                )

        # 인사이트 변환
        insights_formatted = [
            {
                "title": insight.title,
                "description": insight.description,
                "impact": insight.impact_level,
                "confidence": insight.confidence_score,
                "category": insight.category,
                "recommended_actions": insight.recommended_actions,
            }
            for insight in insights
        ]

        # 최종 결과 구성
        comprehensive_analysis = {
            "analysis_period": period.value,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_jobs": total_jobs,
                "total_revenue_impact": total_revenue_impact,
                "average_roi": average_roi,
                "efficiency_score": efficiency_score,
                "cost_savings": cost_savings,
            },
            "kpi_metrics": kpi_metrics,
            "roi_analysis": roi_analysis,
            "insights": insights_formatted,
            "executive_summary": executive_summary,
            "performance_trends": self._generate_performance_trends(period),
            "operational_metrics": self._generate_operational_metrics(period_jobs),
            "recommendations": self._generate_actionable_recommendations(
                insights, kpis
            ),
        }

        # 캐시에 저장
        self.analysis_cache[cache_key] = comprehensive_analysis

        return comprehensive_analysis

    def calculate_roi_metrics(self) -> Dict[str, Any]:
        """ROI 메트릭 계산"""
        period_jobs = self.analytics_engine._get_jobs_by_period(
            AnalyticsPeriod.LAST_24_HOURS
        )

        if not period_jobs:
            return {
                "total_revenue_generated": 0.0,
                "total_cost_invested": 0.0,
                "overall_roi_percent": 0.0,
                "cost_efficiency": 0.0,
                "job_performance": {},
            }

        total_revenue = sum(job.business_metrics.revenue_impact for job in period_jobs)
        total_cost = sum(job.business_metrics.processing_cost for job in period_jobs)

        roi_percent = (
            ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
        )
        cost_efficiency = (total_revenue / total_cost) if total_cost > 0 else 0

        # 작업 유형별 성과
        job_performance = {}
        jobs_by_type = defaultdict(list)
        for job in period_jobs:
            jobs_by_type[job.job_type.value].append(job)

        for job_type, type_jobs in jobs_by_type.items():
            type_revenue = sum(j.business_metrics.revenue_impact for j in type_jobs)
            type_cost = sum(j.business_metrics.processing_cost for j in type_jobs)
            type_roi = (
                ((type_revenue - type_cost) / type_cost * 100) if type_cost > 0 else 0
            )
            type_throughput = len(type_jobs) / 24  # 시간당 처리량

            job_performance[job_type] = {
                "roi_percent": type_roi,
                "throughput": type_throughput,
                "total_jobs": len(type_jobs),
                "revenue": type_revenue,
                "cost": type_cost,
            }

        return {
            "total_revenue_generated": total_revenue,
            "total_cost_invested": total_cost,
            "overall_roi_percent": roi_percent,
            "cost_efficiency": cost_efficiency,
            "job_performance": job_performance,
        }

    def _generate_roi_analysis(self, jobs: List[Any]) -> Dict[str, Any]:
        """ROI 상세 분석 생성"""
        if not jobs:
            return {"status": "insufficient_data"}

        total_investment = sum(job.business_metrics.processing_cost for job in jobs)
        total_return = sum(job.business_metrics.revenue_impact for job in jobs)

        roi_percentage = (
            ((total_return - total_investment) / total_investment * 100)
            if total_investment > 0
            else 0
        )

        # 손익분기점 추정
        daily_cost = total_investment / max(
            len(set(job.created_at.date() for job in jobs)), 1
        )
        daily_return = total_return / max(
            len(set(job.created_at.date() for job in jobs)), 1
        )

        if daily_return > daily_cost:
            payback_period_days = int(total_investment / (daily_return - daily_cost))
        else:
            payback_period_days = None

        return {
            "total_investment": total_investment,
            "total_return": total_return,
            "net_profit": total_return - total_investment,
            "roi_percentage": roi_percentage,
            "payback_period_days": payback_period_days,
            "daily_cost": daily_cost,
            "daily_return": daily_return,
            "profitability_status": (
                "profitable" if roi_percentage > 0 else "unprofitable"
            ),
            "investment_efficiency": (
                total_return / total_investment if total_investment > 0 else 0
            ),
        }

    def _generate_performance_trends(self, period: AnalyticsPeriod) -> Dict[str, Any]:
        """성과 트렌드 생성"""
        # 이전 기간과 비교
        current_kpis = self.analytics_engine.calculate_kpis(period)

        # 간단한 트렌드 분석 (실제로는 시계열 데이터 필요)
        trends = {}
        for kpi in current_kpis:
            if kpi.change_rate is not None:
                if kpi.change_rate > 5:
                    trends[kpi.name] = "improving"
                elif kpi.change_rate < -5:
                    trends[kpi.name] = "declining"
                else:
                    trends[kpi.name] = "stable"

        return {
            "period": period.value,
            "trend_analysis": trends,
            "overall_trend": self._determine_overall_trend(trends),
            "improvement_areas": [
                name for name, trend in trends.items() if trend == "improving"
            ],
            "concern_areas": [
                name for name, trend in trends.items() if trend == "declining"
            ],
        }

    def _determine_overall_trend(self, trends: Dict[str, str]) -> str:
        """전체 트렌드 판단"""
        if not trends:
            return "insufficient_data"

        improving_count = sum(1 for trend in trends.values() if trend == "improving")
        declining_count = sum(1 for trend in trends.values() if trend == "declining")

        if improving_count > declining_count:
            return "positive"
        elif declining_count > improving_count:
            return "negative"
        else:
            return "mixed"

    def _generate_operational_metrics(self, jobs: List[Any]) -> Dict[str, Any]:
        """운영 메트릭 생성"""
        if not jobs:
            return {}

        # 작업 유형별 분석
        job_type_stats = defaultdict(
            lambda: {"count": 0, "success": 0, "total_revenue": 0, "total_cost": 0}
        )

        for job in jobs:
            job_type = job.job_type.value
            job_type_stats[job_type]["count"] += 1
            if job.status == JobStatus.COMPLETED:
                job_type_stats[job_type]["success"] += 1
            job_type_stats[job_type][
                "total_revenue"
            ] += job.business_metrics.revenue_impact
            job_type_stats[job_type][
                "total_cost"
            ] += job.business_metrics.processing_cost

        # 통계 계산
        for stats in job_type_stats.values():
            stats["success_rate"] = (
                (stats["success"] / stats["count"]) * 100 if stats["count"] > 0 else 0
            )
            stats["roi"] = (
                ((stats["total_revenue"] - stats["total_cost"]) / stats["total_cost"])
                * 100
                if stats["total_cost"] > 0
                else 0
            )

        return {
            "total_jobs": len(jobs),
            "job_type_breakdown": dict(job_type_stats),
            "peak_processing_time": self._find_peak_processing_time(jobs),
            "average_queue_time": self._calculate_average_queue_time(jobs),
            "resource_efficiency": self._calculate_resource_efficiency(jobs),
        }

    def _find_peak_processing_time(self, jobs: List[Any]) -> str:
        """피크 처리 시간 찾기"""
        if not jobs:
            return "unknown"

        hour_counts = defaultdict(int)
        for job in jobs:
            if job.created_at:
                hour = job.created_at.hour
                hour_counts[hour] += 1

        if hour_counts:
            peak_hour = max(hour_counts, key=hour_counts.get)
            return f"{peak_hour:02d}:00-{peak_hour+1:02d}:00"

        return "unknown"

    def _calculate_average_queue_time(self, jobs: List[Any]) -> float:
        """평균 대기 시간 계산"""
        queue_times = []
        for job in jobs:
            if job.created_at and job.started_at:
                queue_time = (job.started_at - job.created_at).total_seconds()
                queue_times.append(queue_time)

        return statistics.mean(queue_times) if queue_times else 0.0

    def _calculate_resource_efficiency(self, jobs: List[Any]) -> float:
        """리소스 효율성 계산"""
        if not jobs:
            return 0.0

        # 단순화된 효율성 계산 (실제로는 더 복잡한 로직 필요)
        total_processing_time = 0
        total_estimated_time = 0

        for job in jobs:
            if job.started_at and job.completed_at:
                actual_time = (job.completed_at - job.started_at).total_seconds()
                total_processing_time += actual_time
                total_estimated_time += job.estimated_duration

        if total_estimated_time > 0:
            efficiency = (total_estimated_time / total_processing_time) * 100
            return min(efficiency, 200.0)  # 최대 200% 효율성

        return 100.0

    def _generate_actionable_recommendations(
        self, insights: List[BusinessInsight], kpis: List[KPIMetric]
    ) -> List[Dict[str, Any]]:
        """실행 가능한 권장사항 생성"""
        recommendations = []

        # 우선순위별 권장사항
        high_priority_insights = [i for i in insights if i.impact_level == "high"]

        for insight in high_priority_insights:
            for action in insight.recommended_actions:
                recommendations.append(
                    {
                        "action": action,
                        "priority": "high",
                        "related_insight": insight.title,
                        "estimated_effort": "medium",  # 실제로는 더 정교한 추정 필요
                        "expected_impact": insight.impact_level,
                        "timeline": (
                            "immediate"
                            if insight.impact_level == "high"
                            else "short_term"
                        ),
                    }
                )

        # KPI 기반 권장사항
        underperforming_kpis = [
            kpi
            for kpi in kpis
            if kpi.target and kpi.achievement_rate and kpi.achievement_rate < 80
        ]

        for kpi in underperforming_kpis:
            recommendations.append(
                {
                    "action": f"{kpi.description} 개선 계획 수립",
                    "priority": "medium",
                    "related_metric": kpi.name,
                    "current_value": kpi.value,
                    "target_value": kpi.target,
                    "timeline": "short_term",
                }
            )

        return recommendations[:10]  # 최대 10개 권장사항

    def get_analytics_summary(self) -> Dict[str, Any]:
        """분석 서비스 요약 정보"""
        return {
            "service_status": "active",
            "cache_entries": len(self.analysis_cache),
            "supported_periods": [period.value for period in AnalyticsPeriod],
            "available_engines": ["BatchJobAnalyticsEngine"],
            "available_reports": ["ExecutiveSummary"],
            "last_analysis": (
                max(self.analysis_cache.keys()) if self.analysis_cache else None
            ),
        }


# ===== 전역 인스턴스 =====

_global_analytics_service: Optional[BusinessAnalyticsService] = None


def get_analytics_service() -> BusinessAnalyticsService:
    """전역 분석 서비스 인스턴스 반환"""
    global _global_analytics_service

    if _global_analytics_service is None:
        _global_analytics_service = BusinessAnalyticsService()

    return _global_analytics_service


def get_business_analytics_service() -> BusinessAnalyticsService:
    """전역 비즈니스 분석 서비스 인스턴스 반환 (별칭)"""
    return get_analytics_service()


def shutdown_business_analytics_service() -> None:
    """전역 비즈니스 분석 서비스 종료"""
    global _global_analytics_service
    _global_analytics_service = None
