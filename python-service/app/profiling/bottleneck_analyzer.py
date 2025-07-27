"""
병목 지점 분석기
OCR 컴포넌트별 성능 분석 및 최적화 권장사항 제공
"""

import logging
import time
import psutil
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class BottleneckType(Enum):
    """병목 지점 유형"""
    CPU_INTENSIVE = "cpu_intensive"
    MEMORY_HEAVY = "memory_heavy"
    IO_BOUND = "io_bound"
    NETWORK_LATENCY = "network_latency"
    ALGORITHM_INEFFICIENCY = "algorithm_inefficiency"
    RESOURCE_CONTENTION = "resource_contention"


class SeverityLevel(Enum):
    """심각도 수준"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ComponentMetrics:
    """컴포넌트별 성능 메트릭"""
    component_name: str
    method_name: str
    execution_time: float
    cpu_usage: float
    memory_usage: float
    io_operations: int
    network_calls: int
    cache_hits: int
    cache_misses: int
    error_count: int
    throughput: float  # operations per second
    timestamp: datetime
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BottleneckIssue:
    """병목 지점 이슈"""
    issue_id: str
    component: str
    method: str
    bottleneck_type: BottleneckType
    severity: SeverityLevel
    impact_score: float
    description: str
    current_performance: Dict[str, float]
    expected_performance: Dict[str, float]
    root_cause: str
    recommendations: List[str]
    estimated_improvement: float
    fix_complexity: str  # "low", "medium", "high"


class BottleneckAnalyzer:
    """병목 지점 분석기 - OCR 컴포넌트 성능 분석"""
    
    def __init__(self):
        self.metrics_history: List[ComponentMetrics] = []
        self.baseline_metrics: Dict[str, ComponentMetrics] = {}
        self.performance_thresholds = self._load_performance_thresholds()
        self.analysis_rules = self._load_analysis_rules()
        
        # 시스템 리소스 모니터링
        self.process = psutil.Process()
        
    def _load_performance_thresholds(self) -> Dict[str, Dict[str, float]]:
        """성능 임계값 로드"""
        return {
            "tier2_processor": {
                "max_execution_time": 2.0,  # seconds
                "max_memory_usage": 200,    # MB
                "max_cpu_usage": 80,        # percentage
                "min_throughput": 0.5       # ops/sec
            },
            "tier3_processor": {
                "max_execution_time": 10.0,
                "max_memory_usage": 100,
                "max_cpu_usage": 50,
                "min_throughput": 0.1
            },
            "image_complexity_analyzer": {
                "max_execution_time": 1.0,
                "max_memory_usage": 50,
                "max_cpu_usage": 60,
                "min_throughput": 2.0
            },
            "ocr_decision_engine": {
                "max_execution_time": 0.5,
                "max_memory_usage": 20,
                "max_cpu_usage": 30,
                "min_throughput": 10.0
            },
            "text_correctors": {
                "max_execution_time": 1.5,
                "max_memory_usage": 100,
                "max_cpu_usage": 70,
                "min_throughput": 1.0
            },
            "result_aggregator": {
                "max_execution_time": 0.3,
                "max_memory_usage": 30,
                "max_cpu_usage": 20,
                "min_throughput": 5.0
            }
        }
    
    def _load_analysis_rules(self) -> List[Dict[str, Any]]:
        """분석 규칙 로드"""
        return [
            {
                "name": "high_execution_time",
                "condition": lambda m, t: m.execution_time > t.get("max_execution_time", 5.0),
                "bottleneck_type": BottleneckType.ALGORITHM_INEFFICIENCY,
                "severity_func": lambda m, t: SeverityLevel.CRITICAL if m.execution_time > t.get("max_execution_time", 5.0) * 2 else SeverityLevel.HIGH,
                "recommendations": [
                    "알고리즘 복잡도 분석 및 최적화",
                    "비효율적인 루프나 재귀 호출 개선",
                    "데이터 구조 최적화 고려"
                ]
            },
            {
                "name": "high_memory_usage",
                "condition": lambda m, t: m.memory_usage > t.get("max_memory_usage", 100),
                "bottleneck_type": BottleneckType.MEMORY_HEAVY,
                "severity_func": lambda m, t: SeverityLevel.CRITICAL if m.memory_usage > t.get("max_memory_usage", 100) * 3 else SeverityLevel.HIGH,
                "recommendations": [
                    "메모리 풀링 도입",
                    "객체 재사용 패턴 적용",
                    "가비지 컬렉션 최적화",
                    "스트리밍 처리 방식 검토"
                ]
            },
            {
                "name": "high_cpu_usage",
                "condition": lambda m, t: m.cpu_usage > t.get("max_cpu_usage", 80),
                "bottleneck_type": BottleneckType.CPU_INTENSIVE,
                "severity_func": lambda m, t: SeverityLevel.HIGH if m.cpu_usage > 90 else SeverityLevel.MEDIUM,
                "recommendations": [
                    "CPU 집약적 작업을 별도 스레드로 분리",
                    "멀티프로세싱 도입 검토",
                    "연산 로직 최적화",
                    "캐싱을 통한 중복 연산 제거"
                ]
            },
            {
                "name": "low_throughput",
                "condition": lambda m, t: m.throughput < t.get("min_throughput", 1.0),
                "bottleneck_type": BottleneckType.RESOURCE_CONTENTION,
                "severity_func": lambda m, t: SeverityLevel.HIGH,
                "recommendations": [
                    "병렬 처리 도입",
                    "배치 처리 최적화",
                    "리소스 경합 해결",
                    "비동기 처리 패턴 적용"
                ]
            },
            {
                "name": "poor_cache_performance",
                "condition": lambda m, t: m.cache_hits + m.cache_misses > 0 and m.cache_hits / (m.cache_hits + m.cache_misses) < 0.7,
                "bottleneck_type": BottleneckType.ALGORITHM_INEFFICIENCY,
                "severity_func": lambda m, t: SeverityLevel.MEDIUM,
                "recommendations": [
                    "캐시 전략 재검토",
                    "캐시 크기 조정",
                    "캐시 만료 정책 최적화",
                    "지역성(locality) 향상"
                ]
            },
            {
                "name": "high_io_operations",
                "condition": lambda m, t: m.io_operations > 100,
                "bottleneck_type": BottleneckType.IO_BOUND,
                "severity_func": lambda m, t: SeverityLevel.HIGH if m.io_operations > 500 else SeverityLevel.MEDIUM,
                "recommendations": [
                    "I/O 작업 배치 처리",
                    "비동기 I/O 도입",
                    "파일 시스템 캐싱 활용",
                    "불필요한 파일 읽기/쓰기 제거"
                ]
            },
            {
                "name": "high_network_latency",
                "condition": lambda m, t: m.network_calls > 10,
                "bottleneck_type": BottleneckType.NETWORK_LATENCY,
                "severity_func": lambda m, t: SeverityLevel.HIGH if m.network_calls > 50 else SeverityLevel.MEDIUM,
                "recommendations": [
                    "네트워크 호출 배치 처리",
                    "연결 풀링 도입",
                    "응답 캐싱",
                    "타임아웃 최적화"
                ]
            }
        ]
    
    def collect_metrics(self, component_name: str, method_name: str,
                       execution_time: float, **kwargs) -> ComponentMetrics:
        """메트릭 수집"""
        try:
            # 시스템 리소스 정보 수집
            cpu_usage = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_usage = memory_info.rss / 1024 / 1024  # MB
            
            # 메트릭 생성
            metrics = ComponentMetrics(
                component_name=component_name,
                method_name=method_name,
                execution_time=execution_time,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                io_operations=kwargs.get('io_operations', 0),
                network_calls=kwargs.get('network_calls', 0),
                cache_hits=kwargs.get('cache_hits', 0),
                cache_misses=kwargs.get('cache_misses', 0),
                error_count=kwargs.get('error_count', 0),
                throughput=1.0 / execution_time if execution_time > 0 else 0,
                timestamp=datetime.now(),
                additional_data=kwargs.get('additional_data', {})
            )
            
            # 메트릭 히스토리에 추가
            self.metrics_history.append(metrics)
            
            # 베이스라인 메트릭 업데이트
            component_key = f"{component_name}.{method_name}"
            if component_key not in self.baseline_metrics:
                self.baseline_metrics[component_key] = metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect metrics for {component_name}.{method_name}: {e}")
            raise
    
    def analyze_bottlenecks(self, time_window_minutes: int = 10) -> List[BottleneckIssue]:
        """병목 지점 분석"""
        issues = []
        
        # 시간 윈도우 내의 메트릭만 분석
        cutoff_time = datetime.now().timestamp() - (time_window_minutes * 60)
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp.timestamp() > cutoff_time
        ]
        
        # 컴포넌트별로 그룹화
        component_groups = {}
        for metric in recent_metrics:
            key = f"{metric.component_name}.{metric.method_name}"
            if key not in component_groups:
                component_groups[key] = []
            component_groups[key].append(metric)
        
        # 각 컴포넌트별 분석
        for component_key, metrics_list in component_groups.items():
            component_name = metrics_list[0].component_name
            method_name = metrics_list[0].method_name
            
            # 평균 메트릭 계산
            avg_metrics = self._calculate_average_metrics(metrics_list)
            
            # 성능 임계값 가져오기
            thresholds = self.performance_thresholds.get(component_name, {})
            
            # 각 분석 규칙 적용
            for rule in self.analysis_rules:
                if rule["condition"](avg_metrics, thresholds):
                    issue = self._create_bottleneck_issue(
                        component_name, method_name, avg_metrics, rule, thresholds
                    )
                    issues.append(issue)
        
        # 영향도 순으로 정렬
        issues.sort(key=lambda x: x.impact_score, reverse=True)
        
        return issues
    
    def _calculate_average_metrics(self, metrics_list: List[ComponentMetrics]) -> ComponentMetrics:
        """평균 메트릭 계산"""
        if not metrics_list:
            return ComponentMetrics("", "", 0, 0, 0, 0, 0, 0, 0, 0, 0, datetime.now())
        
        count = len(metrics_list)
        first_metric = metrics_list[0]
        
        return ComponentMetrics(
            component_name=first_metric.component_name,
            method_name=first_metric.method_name,
            execution_time=sum(m.execution_time for m in metrics_list) / count,
            cpu_usage=sum(m.cpu_usage for m in metrics_list) / count,
            memory_usage=sum(m.memory_usage for m in metrics_list) / count,
            io_operations=sum(m.io_operations for m in metrics_list),
            network_calls=sum(m.network_calls for m in metrics_list),
            cache_hits=sum(m.cache_hits for m in metrics_list),
            cache_misses=sum(m.cache_misses for m in metrics_list),
            error_count=sum(m.error_count for m in metrics_list),
            throughput=sum(m.throughput for m in metrics_list) / count,
            timestamp=datetime.now()
        )
    
    def _create_bottleneck_issue(self, component_name: str, method_name: str,
                                metrics: ComponentMetrics, rule: Dict[str, Any],
                                thresholds: Dict[str, float]) -> BottleneckIssue:
        """병목 지점 이슈 생성"""
        severity = rule["severity_func"](metrics, thresholds)
        
        # 영향도 점수 계산 (0-100)
        impact_score = self._calculate_impact_score(metrics, thresholds, severity)
        
        # 현재 성능과 기대 성능
        current_performance = {
            "execution_time": metrics.execution_time,
            "cpu_usage": metrics.cpu_usage,
            "memory_usage": metrics.memory_usage,
            "throughput": metrics.throughput
        }
        
        expected_performance = {
            "execution_time": thresholds.get("max_execution_time", metrics.execution_time * 0.7),
            "cpu_usage": thresholds.get("max_cpu_usage", 50),
            "memory_usage": thresholds.get("max_memory_usage", metrics.memory_usage * 0.8),
            "throughput": thresholds.get("min_throughput", metrics.throughput * 1.5)
        }
        
        # 근본 원인 분석
        root_cause = self._analyze_root_cause(metrics, rule["bottleneck_type"])
        
        # 개선 효과 추정
        estimated_improvement = self._estimate_improvement(metrics, rule["bottleneck_type"])
        
        # 수정 복잡도
        fix_complexity = self._estimate_fix_complexity(rule["bottleneck_type"], severity)
        
        issue_id = f"{component_name}_{method_name}_{rule['name']}_{int(time.time())}"
        
        return BottleneckIssue(
            issue_id=issue_id,
            component=component_name,
            method=method_name,
            bottleneck_type=rule["bottleneck_type"],
            severity=severity,
            impact_score=impact_score,
            description=f"{component_name}.{method_name}에서 {rule['name']} 문제 감지",
            current_performance=current_performance,
            expected_performance=expected_performance,
            root_cause=root_cause,
            recommendations=rule["recommendations"].copy(),
            estimated_improvement=estimated_improvement,
            fix_complexity=fix_complexity
        )
    
    def _calculate_impact_score(self, metrics: ComponentMetrics, 
                              thresholds: Dict[str, float], 
                              severity: SeverityLevel) -> float:
        """영향도 점수 계산"""
        base_score = {
            SeverityLevel.LOW: 20,
            SeverityLevel.MEDIUM: 40,
            SeverityLevel.HIGH: 70,
            SeverityLevel.CRITICAL: 90
        }[severity]
        
        # 성능 지표별 가중치
        time_weight = 0.4
        memory_weight = 0.3
        cpu_weight = 0.2
        throughput_weight = 0.1
        
        # 임계값 대비 비율
        time_ratio = metrics.execution_time / thresholds.get("max_execution_time", 1.0)
        memory_ratio = metrics.memory_usage / thresholds.get("max_memory_usage", 100)
        cpu_ratio = metrics.cpu_usage / thresholds.get("max_cpu_usage", 80)
        throughput_ratio = thresholds.get("min_throughput", 1.0) / max(metrics.throughput, 0.1)
        
        weighted_ratio = (
            time_ratio * time_weight +
            memory_ratio * memory_weight +
            cpu_ratio * cpu_weight +
            throughput_ratio * throughput_weight
        )
        
        # 최종 점수 (0-100)
        final_score = min(base_score * weighted_ratio, 100)
        return round(final_score, 1)
    
    def _analyze_root_cause(self, metrics: ComponentMetrics, 
                          bottleneck_type: BottleneckType) -> str:
        """근본 원인 분석"""
        causes = {
            BottleneckType.CPU_INTENSIVE: "CPU 집약적 연산으로 인한 처리 지연",
            BottleneckType.MEMORY_HEAVY: "과도한 메모리 사용으로 인한 성능 저하",
            BottleneckType.IO_BOUND: "디스크 I/O 대기시간으로 인한 병목",
            BottleneckType.NETWORK_LATENCY: "네트워크 지연으로 인한 응답 시간 증가",
            BottleneckType.ALGORITHM_INEFFICIENCY: "비효율적인 알고리즘으로 인한 성능 문제",
            BottleneckType.RESOURCE_CONTENTION: "리소스 경합으로 인한 처리량 저하"
        }
        
        base_cause = causes.get(bottleneck_type, "성능 문제 감지")
        
        # 구체적인 원인 추가
        if bottleneck_type == BottleneckType.MEMORY_HEAVY and metrics.memory_usage > 500:
            base_cause += " (500MB 이상의 대용량 메모리 사용)"
        elif bottleneck_type == BottleneckType.CPU_INTENSIVE and metrics.cpu_usage > 95:
            base_cause += " (CPU 사용률 95% 이상)"
        elif bottleneck_type == BottleneckType.IO_BOUND and metrics.io_operations > 1000:
            base_cause += " (1000회 이상의 I/O 작업)"
        
        return base_cause
    
    def _estimate_improvement(self, metrics: ComponentMetrics, 
                            bottleneck_type: BottleneckType) -> float:
        """개선 효과 추정 (백분율)"""
        improvement_estimates = {
            BottleneckType.CPU_INTENSIVE: 30.0,  # 30% 성능 향상 예상
            BottleneckType.MEMORY_HEAVY: 40.0,   # 40% 메모리 사용량 감소
            BottleneckType.IO_BOUND: 50.0,       # 50% I/O 시간 단축
            BottleneckType.NETWORK_LATENCY: 60.0, # 60% 네트워크 대기시간 감소
            BottleneckType.ALGORITHM_INEFFICIENCY: 70.0, # 70% 알고리즘 성능 향상
            BottleneckType.RESOURCE_CONTENTION: 35.0     # 35% 처리량 증가
        }
        
        return improvement_estimates.get(bottleneck_type, 25.0)
    
    def _estimate_fix_complexity(self, bottleneck_type: BottleneckType, 
                               severity: SeverityLevel) -> str:
        """수정 복잡도 추정"""
        complexity_map = {
            BottleneckType.CPU_INTENSIVE: "medium",
            BottleneckType.MEMORY_HEAVY: "high",
            BottleneckType.IO_BOUND: "medium",
            BottleneckType.NETWORK_LATENCY: "low",
            BottleneckType.ALGORITHM_INEFFICIENCY: "high",
            BottleneckType.RESOURCE_CONTENTION: "medium"
        }
        
        base_complexity = complexity_map.get(bottleneck_type, "medium")
        
        # 심각도에 따른 복잡도 조정
        if severity == SeverityLevel.CRITICAL:
            if base_complexity == "low":
                return "medium"
            elif base_complexity == "medium":
                return "high"
        
        return base_complexity
    
    def generate_optimization_plan(self, issues: List[BottleneckIssue]) -> Dict[str, Any]:
        """최적화 계획 생성"""
        if not issues:
            return {"message": "성능 이슈가 발견되지 않았습니다.", "plan": []}
        
        # 우선순위별 그룹화
        critical_issues = [i for i in issues if i.severity == SeverityLevel.CRITICAL]
        high_issues = [i for i in issues if i.severity == SeverityLevel.HIGH]
        medium_issues = [i for i in issues if i.severity == SeverityLevel.MEDIUM]
        low_issues = [i for i in issues if i.severity == SeverityLevel.LOW]
        
        plan = {
            "summary": {
                "total_issues": len(issues),
                "critical_issues": len(critical_issues),
                "high_issues": len(high_issues),
                "medium_issues": len(medium_issues),
                "low_issues": len(low_issues),
                "estimated_total_improvement": sum(i.estimated_improvement for i in issues[:5])
            },
            "immediate_actions": [],
            "short_term_improvements": [],
            "long_term_optimizations": [],
            "resource_requirements": {
                "development_time": "TBD",
                "testing_effort": "TBD",
                "risk_level": "TBD"
            }
        }
        
        # 즉시 조치 필요 (Critical)
        for issue in critical_issues:
            plan["immediate_actions"].append({
                "component": issue.component,
                "issue": issue.description,
                "recommendations": issue.recommendations[:2],  # 상위 2개만
                "expected_improvement": f"{issue.estimated_improvement}%",
                "complexity": issue.fix_complexity
            })
        
        # 단기 개선 (High)
        for issue in high_issues:
            plan["short_term_improvements"].append({
                "component": issue.component,
                "issue": issue.description,
                "recommendations": issue.recommendations,
                "expected_improvement": f"{issue.estimated_improvement}%",
                "complexity": issue.fix_complexity
            })
        
        # 장기 최적화 (Medium, Low)
        for issue in medium_issues + low_issues:
            plan["long_term_optimizations"].append({
                "component": issue.component,
                "issue": issue.description,
                "recommendations": issue.recommendations,
                "expected_improvement": f"{issue.estimated_improvement}%",
                "complexity": issue.fix_complexity
            })
        
        return plan
    
    def save_analysis_report(self, issues: List[BottleneckIssue], 
                           output_path: Path) -> None:
        """분석 보고서 저장"""
        try:
            optimization_plan = self.generate_optimization_plan(issues)
            
            report = {
                "analysis_timestamp": datetime.now().isoformat(),
                "total_issues": len(issues),
                "issues": [
                    {
                        "issue_id": issue.issue_id,
                        "component": issue.component,
                        "method": issue.method,
                        "bottleneck_type": issue.bottleneck_type.value,
                        "severity": issue.severity.value,
                        "impact_score": issue.impact_score,
                        "description": issue.description,
                        "current_performance": issue.current_performance,
                        "expected_performance": issue.expected_performance,
                        "root_cause": issue.root_cause,
                        "recommendations": issue.recommendations,
                        "estimated_improvement": issue.estimated_improvement,
                        "fix_complexity": issue.fix_complexity
                    }
                    for issue in issues
                ],
                "optimization_plan": optimization_plan,
                "metrics_summary": self._generate_metrics_summary()
            }
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Bottleneck analysis report saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save analysis report: {e}")
            raise
    
    def _generate_metrics_summary(self) -> Dict[str, Any]:
        """메트릭 요약 생성"""
        if not self.metrics_history:
            return {}
        
        recent_metrics = self.metrics_history[-100:]  # 최근 100개
        
        return {
            "total_metrics_collected": len(self.metrics_history),
            "avg_execution_time": sum(m.execution_time for m in recent_metrics) / len(recent_metrics),
            "avg_memory_usage": sum(m.memory_usage for m in recent_metrics) / len(recent_metrics),
            "avg_cpu_usage": sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics),
            "avg_throughput": sum(m.throughput for m in recent_metrics) / len(recent_metrics),
            "components_analyzed": len(set(f"{m.component_name}.{m.method_name}" for m in recent_metrics))
        }


# 메트릭 수집 데코레이터
def collect_performance_metrics(component_name: str, method_name: str = None):
    """성능 메트릭 수집 데코레이터"""
    def decorator(func):
        nonlocal method_name
        if method_name is None:
            method_name = func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # 글로벌 분석기가 있으면 메트릭 수집
                if hasattr(wrapper, '_analyzer'):
                    wrapper._analyzer.collect_metrics(
                        component_name, method_name, execution_time
                    )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                # 에러 메트릭도 수집
                if hasattr(wrapper, '_analyzer'):
                    wrapper._analyzer.collect_metrics(
                        component_name, method_name, execution_time,
                        error_count=1
                    )
                
                raise
        
        return wrapper
    return decorator


# 글로벌 분석기 인스턴스
_global_analyzer: Optional[BottleneckAnalyzer] = None


def get_bottleneck_analyzer() -> BottleneckAnalyzer:
    """글로벌 병목 분석기 가져오기"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = BottleneckAnalyzer()
    return _global_analyzer