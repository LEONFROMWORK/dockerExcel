"""
성능 프로파일링 도구
cProfile, line_profiler, memory_profiler 통합
"""

import cProfile
import pstats
import io
import time
import psutil
import logging
import functools
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Optional imports for advanced profiling
try:
    import line_profiler

    LINE_PROFILER_AVAILABLE = True
except ImportError:
    LINE_PROFILER_AVAILABLE = False
    logger.warning(
        "line_profiler not available. Install with: pip install line_profiler"
    )

try:
    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False
    logger.warning(
        "memory_profiler not available. Install with: pip install memory-profiler"
    )


@dataclass
class PerformanceMetrics:
    """성능 측정 결과"""

    function_name: str
    execution_time: float
    cpu_usage_before: float
    cpu_usage_after: float
    memory_usage_before: float
    memory_usage_after: float
    memory_peak: float
    call_count: int
    timestamp: datetime
    additional_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfilingResult:
    """프로파일링 결과"""

    session_id: str
    total_execution_time: float
    metrics: List[PerformanceMetrics]
    cprofile_stats: Optional[str] = None
    line_profile_results: Optional[Dict[str, Any]] = None
    memory_profile_results: Optional[List[Dict[str, Any]]] = None
    bottlenecks: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class PerformanceProfiler:
    """성능 프로파일러 - 통합 성능 분석 도구"""

    def __init__(
        self, enable_line_profiling: bool = True, enable_memory_profiling: bool = True
    ):
        """
        초기화

        Args:
            enable_line_profiling: 라인별 프로파일링 활성화
            enable_memory_profiling: 메모리 프로파일링 활성화
        """
        self.enable_line_profiling = enable_line_profiling and LINE_PROFILER_AVAILABLE
        self.enable_memory_profiling = (
            enable_memory_profiling and MEMORY_PROFILER_AVAILABLE
        )

        self.metrics: List[PerformanceMetrics] = []
        self.session_start_time: Optional[float] = None
        self.session_id: Optional[str] = None

        # 프로파일러 인스턴스들
        self.cprofile = cProfile.Profile()
        self.line_profiler = (
            line_profiler.LineProfiler() if self.enable_line_profiling else None
        )

        # 시스템 리소스 모니터링
        self.process = psutil.Process()

        # 스레드 로컬 저장소
        self.local = threading.local()

    def start_session(self, session_id: Optional[str] = None) -> str:
        """프로파일링 세션 시작"""
        self.session_id = session_id or f"session_{int(time.time())}"
        self.session_start_time = time.time()
        self.metrics.clear()

        # cProfile 시작
        self.cprofile.enable()

        logger.info(f"Started profiling session: {self.session_id}")
        return self.session_id

    def end_session(self) -> ProfilingResult:
        """프로파일링 세션 종료 및 결과 반환"""
        if not self.session_start_time:
            raise ValueError("No active profiling session")

        # cProfile 중지
        self.cprofile.disable()

        total_time = time.time() - self.session_start_time

        # cProfile 결과 수집
        cprofile_stats = self._collect_cprofile_stats()

        # 라인 프로파일링 결과 수집
        line_profile_results = self._collect_line_profile_results()

        # 메모리 프로파일링 결과 수집
        memory_profile_results = self._collect_memory_profile_results()

        # 병목 지점 분석
        bottlenecks = self._analyze_bottlenecks()

        # 최적화 권장사항 생성
        recommendations = self._generate_recommendations()

        result = ProfilingResult(
            session_id=self.session_id,
            total_execution_time=total_time,
            metrics=self.metrics.copy(),
            cprofile_stats=cprofile_stats,
            line_profile_results=line_profile_results,
            memory_profile_results=memory_profile_results,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
        )

        logger.info(f"Ended profiling session: {self.session_id}")
        return result

    def profile_function(
        self,
        func: Callable = None,
        *,
        include_line_profiling: bool = True,
        include_memory_profiling: bool = True,
    ):
        """함수 프로파일링 데코레이터"""

        def decorator(f):
            # 라인 프로파일링 추가
            if (
                include_line_profiling
                and self.enable_line_profiling
                and self.line_profiler is not None
            ):
                self.line_profiler.add_function(f)

            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                return self._profile_execution(
                    f, args, kwargs, include_memory_profiling=include_memory_profiling
                )

            return wrapper

        if func is None:
            return decorator
        else:
            return decorator(func)

    def profile_method(
        self, include_line_profiling: bool = True, include_memory_profiling: bool = True
    ):
        """메서드 프로파일링 데코레이터"""

        def decorator(method):
            # 라인 프로파일링 추가
            if (
                include_line_profiling
                and self.enable_line_profiling
                and self.line_profiler is not None
            ):
                self.line_profiler.add_function(method)

            @functools.wraps(method)
            def wrapper(self_obj, *args, **kwargs):
                return self._profile_execution(
                    method,
                    (self_obj,) + args,
                    kwargs,
                    include_memory_profiling=include_memory_profiling,
                )

            return wrapper

        return decorator

    def _profile_execution(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        include_memory_profiling: bool = True,
    ) -> Any:
        """함수 실행 프로파일링"""
        func_name = f"{func.__module__}.{func.__qualname__}"

        # 실행 전 시스템 상태
        start_time = time.time()
        cpu_before = self.process.cpu_percent()
        memory_before = self.process.memory_info().rss / 1024 / 1024  # MB

        # 메모리 프로파일링 시작
        memory_peak = memory_before
        if include_memory_profiling and self.enable_memory_profiling:
            # 메모리 사용량 모니터링을 위한 스레드 시작
            stop_monitoring = threading.Event()
            memory_monitor = threading.Thread(
                target=self._monitor_memory, args=(stop_monitoring, lambda: memory_peak)
            )
            memory_monitor.start()

        try:
            # 함수 실행
            result = func(*args, **kwargs)

        finally:
            # 실행 후 시스템 상태
            end_time = time.time()
            execution_time = end_time - start_time
            cpu_after = self.process.cpu_percent()
            memory_after = self.process.memory_info().rss / 1024 / 1024  # MB

            # 메모리 모니터링 중지
            if include_memory_profiling and self.enable_memory_profiling:
                stop_monitoring.set()
                memory_monitor.join(timeout=1.0)
                memory_peak = max(memory_peak, memory_after)

            # 메트릭 기록
            metrics = PerformanceMetrics(
                function_name=func_name,
                execution_time=execution_time,
                cpu_usage_before=cpu_before,
                cpu_usage_after=cpu_after,
                memory_usage_before=memory_before,
                memory_usage_after=memory_after,
                memory_peak=memory_peak,
                call_count=1,
                timestamp=datetime.now(),
            )

            self.metrics.append(metrics)

            logger.debug(
                f"Profiled {func_name}: {execution_time:.4f}s, "
                f"Memory: {memory_before:.1f}→{memory_after:.1f}MB"
            )

        return result

    def _monitor_memory(self, stop_event: threading.Event, peak_callback: Callable):
        """메모리 사용량 모니터링"""
        peak_memory = 0

        while not stop_event.is_set():
            try:
                current_memory = self.process.memory_info().rss / 1024 / 1024
                peak_memory = max(peak_memory, current_memory)
                time.sleep(0.01)  # 10ms 간격으로 체크
            except Exception:
                break

        # 피크 메모리 업데이트 (콜백 방식으로는 한계가 있어 별도 처리 필요)

    def _collect_cprofile_stats(self) -> str:
        """cProfile 통계 수집"""
        try:
            s = io.StringIO()
            stats = pstats.Stats(self.cprofile, stream=s)
            stats.sort_stats("cumulative")
            stats.print_stats(20)  # 상위 20개 함수
            return s.getvalue()
        except Exception as e:
            logger.error(f"Failed to collect cProfile stats: {e}")
            return ""

    def _collect_line_profile_results(self) -> Optional[Dict[str, Any]]:
        """라인 프로파일링 결과 수집"""
        if not self.enable_line_profiling or not self.line_profiler:
            return None

        try:
            s = io.StringIO()
            self.line_profiler.print_stats(stream=s)
            line_stats = s.getvalue()

            return {
                "line_by_line_stats": line_stats,
                "functions_profiled": len(self.line_profiler.functions),
            }
        except Exception as e:
            logger.error(f"Failed to collect line profiling results: {e}")
            return None

    def _collect_memory_profile_results(self) -> Optional[List[Dict[str, Any]]]:
        """메모리 프로파일링 결과 수집"""
        if not self.enable_memory_profiling:
            return None

        # 메모리 프로파일링 결과는 실시간으로 수집된 메트릭에서 추출
        memory_results = []

        for metric in self.metrics:
            memory_results.append(
                {
                    "function": metric.function_name,
                    "memory_before": metric.memory_usage_before,
                    "memory_after": metric.memory_usage_after,
                    "memory_peak": metric.memory_peak,
                    "memory_delta": metric.memory_usage_after
                    - metric.memory_usage_before,
                }
            )

        return memory_results

    def _analyze_bottlenecks(self) -> List[Dict[str, Any]]:
        """병목 지점 분석"""
        bottlenecks = []

        if not self.metrics:
            return bottlenecks

        # 실행 시간 기준 병목 지점
        sorted_by_time = sorted(
            self.metrics, key=lambda m: m.execution_time, reverse=True
        )
        for metric in sorted_by_time[:5]:  # 상위 5개
            if metric.execution_time > 0.1:  # 100ms 이상
                bottlenecks.append(
                    {
                        "type": "execution_time",
                        "function": metric.function_name,
                        "value": metric.execution_time,
                        "severity": "high" if metric.execution_time > 1.0 else "medium",
                        "description": f"Function takes {metric.execution_time:.3f}s to execute",
                    }
                )

        # 메모리 사용량 기준 병목 지점
        sorted_by_memory = sorted(
            self.metrics,
            key=lambda m: m.memory_usage_after - m.memory_usage_before,
            reverse=True,
        )
        for metric in sorted_by_memory[:3]:  # 상위 3개
            memory_delta = metric.memory_usage_after - metric.memory_usage_before
            if memory_delta > 50:  # 50MB 이상
                bottlenecks.append(
                    {
                        "type": "memory_usage",
                        "function": metric.function_name,
                        "value": memory_delta,
                        "severity": "high" if memory_delta > 200 else "medium",
                        "description": f"Function allocates {memory_delta:.1f}MB of memory",
                    }
                )

        return bottlenecks

    def _generate_recommendations(self) -> List[str]:
        """최적화 권장사항 생성"""
        recommendations = []

        if not self.metrics:
            return recommendations

        # 전체 실행 시간 분석
        total_exec_time = sum(m.execution_time for m in self.metrics)
        if total_exec_time > 5.0:
            recommendations.append(
                "전체 처리 시간이 5초를 초과합니다. 비동기 처리나 병렬화를 고려하세요."
            )

        # 메모리 사용량 분석
        max_memory_delta = max(
            (m.memory_usage_after - m.memory_usage_before for m in self.metrics),
            default=0,
        )
        if max_memory_delta > 500:
            recommendations.append(
                "메모리 사용량이 500MB를 초과합니다. 메모리 풀링이나 스트리밍 처리를 고려하세요."
            )

        # 반복 호출 분석
        function_calls = {}
        for metric in self.metrics:
            function_calls[metric.function_name] = (
                function_calls.get(metric.function_name, 0) + 1
            )

        repeated_functions = [
            (func, count) for func, count in function_calls.items() if count > 10
        ]
        if repeated_functions:
            recommendations.append(
                f"반복 호출되는 함수들을 캐싱하세요: {', '.join(func for func, _ in repeated_functions[:3])}"
            )

        # CPU 사용률 분석
        high_cpu_functions = [
            m for m in self.metrics if m.cpu_usage_after - m.cpu_usage_before > 50
        ]
        if high_cpu_functions:
            recommendations.append(
                "CPU 집약적인 작업이 감지되었습니다. 알고리즘 최적화나 멀티프로세싱을 고려하세요."
            )

        return recommendations

    def save_results(self, result: ProfilingResult, output_path: Path) -> None:
        """프로파일링 결과 저장"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # JSON 직렬화 가능한 형태로 변환
            serializable_result = {
                "session_id": result.session_id,
                "total_execution_time": result.total_execution_time,
                "metrics": [
                    {
                        "function_name": m.function_name,
                        "execution_time": m.execution_time,
                        "cpu_usage_before": m.cpu_usage_before,
                        "cpu_usage_after": m.cpu_usage_after,
                        "memory_usage_before": m.memory_usage_before,
                        "memory_usage_after": m.memory_usage_after,
                        "memory_peak": m.memory_peak,
                        "call_count": m.call_count,
                        "timestamp": m.timestamp.isoformat(),
                        "additional_metrics": m.additional_metrics,
                    }
                    for m in result.metrics
                ],
                "bottlenecks": result.bottlenecks,
                "recommendations": result.recommendations,
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(serializable_result, f, indent=2, ensure_ascii=False)

            # cProfile 결과를 별도 파일로 저장
            if result.cprofile_stats:
                cprofile_path = output_path.with_suffix(".cprofile.txt")
                with open(cprofile_path, "w", encoding="utf-8") as f:
                    f.write(result.cprofile_stats)

            # 라인 프로파일링 결과를 별도 파일로 저장
            if result.line_profile_results:
                line_profile_path = output_path.with_suffix(".lineprofile.txt")
                with open(line_profile_path, "w", encoding="utf-8") as f:
                    f.write(result.line_profile_results.get("line_by_line_stats", ""))

            logger.info(f"Profiling results saved to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save profiling results: {e}")
            raise

    def get_function_metrics(self, function_name: str) -> List[PerformanceMetrics]:
        """특정 함수의 메트릭 조회"""
        return [m for m in self.metrics if m.function_name == function_name]

    def get_summary_stats(self) -> Dict[str, Any]:
        """요약 통계"""
        if not self.metrics:
            return {}

        execution_times = [m.execution_time for m in self.metrics]
        memory_deltas = [
            m.memory_usage_after - m.memory_usage_before for m in self.metrics
        ]

        return {
            "total_functions": len(set(m.function_name for m in self.metrics)),
            "total_calls": len(self.metrics),
            "total_execution_time": sum(execution_times),
            "avg_execution_time": sum(execution_times) / len(execution_times),
            "max_execution_time": max(execution_times),
            "total_memory_allocated": sum(max(0, delta) for delta in memory_deltas),
            "max_memory_delta": max(memory_deltas) if memory_deltas else 0,
            "session_duration": (
                time.time() - self.session_start_time if self.session_start_time else 0
            ),
        }


# 컨텍스트 매니저
class ProfilingContext:
    """프로파일링 컨텍스트 매니저"""

    def __init__(self, profiler: PerformanceProfiler, session_id: Optional[str] = None):
        self.profiler = profiler
        self.session_id = session_id
        self.result: Optional[ProfilingResult] = None

    def __enter__(self) -> PerformanceProfiler:
        self.profiler.start_session(self.session_id)
        return self.profiler

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.result = self.profiler.end_session()


# 글로벌 프로파일러 인스턴스
_global_profiler: Optional[PerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """글로벌 프로파일러 가져오기"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler


def profile(
    func: Callable = None,
    *,
    include_line_profiling: bool = True,
    include_memory_profiling: bool = True,
):
    """프로파일링 데코레이터 (글로벌 프로파일러 사용)"""
    return get_profiler().profile_function(
        func,
        include_line_profiling=include_line_profiling,
        include_memory_profiling=include_memory_profiling,
    )


def profile_session(session_id: Optional[str] = None) -> ProfilingContext:
    """프로파일링 세션 컨텍스트 매니저"""
    return ProfilingContext(get_profiler(), session_id)
