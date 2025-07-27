"""
고급 작업 상태 모니터링 서비스
실시간 진행률, 실패 감지, 알림 시스템
비즈니스 KPI 중심 모니터링
"""

import time
import logging
import asyncio
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import psutil
import websockets
import asyncio

from app.services.strategic_batch_manager import (
    get_batch_manager,
    JobStatus,
    JobType,
    JobPriority
)

logger = logging.getLogger(__name__)

# ===== 모니터링 데이터 모델 =====

class AlertSeverity(Enum):
    """알림 심각도"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class MetricType(Enum):
    """메트릭 유형"""
    COUNTER = "counter"        # 누적 카운터
    GAUGE = "gauge"           # 현재 값
    HISTOGRAM = "histogram"    # 분포
    RATE = "rate"             # 비율

@dataclass
class MonitoringAlert:
    """모니터링 알림"""
    alert_id: str
    severity: AlertSeverity
    title: str
    message: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "metadata": self.metadata
        }

@dataclass
class PerformanceMetric:
    """성능 메트릭"""
    name: str
    value: float
    metric_type: MetricType
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "unit": self.unit,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class JobProgressInfo:
    """작업 진행 정보"""
    job_id: str
    job_type: str
    priority: str
    progress_percent: float
    estimated_remaining_seconds: int
    current_stage: str
    stages_completed: int
    total_stages: int
    throughput_per_second: float = 0.0
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "priority": self.priority,
            "progress_percent": self.progress_percent,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "current_stage": self.current_stage,
            "stages_completed": self.stages_completed,
            "total_stages": self.total_stages,
            "throughput_per_second": self.throughput_per_second,
            "error_messages": self.error_messages,
            "warnings": self.warnings
        }

# ===== 인터페이스 정의 =====

class AlertHandler(ABC):
    """알림 처리기 인터페이스"""
    
    @abstractmethod
    async def send_alert(self, alert: MonitoringAlert) -> bool:
        """알림 전송"""
        pass

class MetricCollector(ABC):
    """메트릭 수집기 인터페이스"""
    
    @abstractmethod
    def collect_metrics(self) -> List[PerformanceMetric]:
        """메트릭 수집"""
        pass

# ===== 알림 처리기 구현 =====

class ConsoleAlertHandler(AlertHandler):
    """콘솔 알림 처리기"""
    
    async def send_alert(self, alert: MonitoringAlert) -> bool:
        severity_icons = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.EMERGENCY: "🔥"
        }
        
        icon = severity_icons.get(alert.severity, "📢")
        logger.warning(f"{icon} [{alert.severity.value.upper()}] {alert.title}: {alert.message}")
        return True

class WebSocketAlertHandler(AlertHandler):
    """WebSocket 알림 처리기"""
    
    def __init__(self):
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
    
    def add_client(self, websocket):
        """클라이언트 추가"""
        self.connected_clients.add(websocket)
    
    def remove_client(self, websocket):
        """클라이언트 제거"""
        self.connected_clients.discard(websocket)
    
    async def send_alert(self, alert: MonitoringAlert) -> bool:
        """모든 연결된 클라이언트에 알림 전송"""
        if not self.connected_clients:
            return True
        
        message = json.dumps({
            "type": "alert",
            "data": alert.to_dict()
        })
        
        # 연결 끊어진 클라이언트 제거
        disconnected = set()
        
        for client in self.connected_clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.error(f"WebSocket 알림 전송 실패: {e}")
                disconnected.add(client)
        
        # 끊어진 연결 정리
        self.connected_clients -= disconnected
        
        return len(disconnected) == 0

# ===== 메트릭 수집기 구현 =====

class SystemMetricCollector(MetricCollector):
    """시스템 메트릭 수집기"""
    
    def collect_metrics(self) -> List[PerformanceMetric]:
        metrics = []
        
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(PerformanceMetric(
                name="system.cpu.usage",
                value=cpu_percent,
                metric_type=MetricType.GAUGE,
                unit="percent"
            ))
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            metrics.append(PerformanceMetric(
                name="system.memory.usage",
                value=memory.percent,
                metric_type=MetricType.GAUGE,
                unit="percent"
            ))
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            metrics.append(PerformanceMetric(
                name="system.disk.usage",
                value=(disk.used / disk.total) * 100,
                metric_type=MetricType.GAUGE,
                unit="percent"
            ))
            
            # 네트워크 I/O
            net_io = psutil.net_io_counters()
            metrics.append(PerformanceMetric(
                name="system.network.bytes_sent",
                value=float(net_io.bytes_sent),
                metric_type=MetricType.COUNTER,
                unit="bytes"
            ))
            
        except Exception as e:
            logger.error(f"시스템 메트릭 수집 실패: {e}")
        
        return metrics

class BatchJobMetricCollector(MetricCollector):
    """배치 작업 메트릭 수집기"""
    
    def __init__(self):
        self.batch_manager = get_batch_manager()
    
    def collect_metrics(self) -> List[PerformanceMetric]:
        metrics = []
        
        try:
            # 스케줄러 통계
            scheduler_stats = self.batch_manager.scheduler.get_scheduler_stats()
            
            # 대기 중인 작업 수
            metrics.append(PerformanceMetric(
                name="batch.queue.size",
                value=float(scheduler_stats['queue_size']),
                metric_type=MetricType.GAUGE,
                unit="jobs"
            ))
            
            # 실행 중인 작업 수
            metrics.append(PerformanceMetric(
                name="batch.active.jobs",
                value=float(scheduler_stats['active_jobs']),
                metric_type=MetricType.GAUGE,
                unit="jobs"
            ))
            
            # 완료된 작업 수 (누적)
            metrics.append(PerformanceMetric(
                name="batch.completed.total",
                value=float(scheduler_stats['total_completed']),
                metric_type=MetricType.COUNTER,
                unit="jobs"
            ))
            
            # 실패한 작업 수 (누적)
            metrics.append(PerformanceMetric(
                name="batch.failed.total",
                value=float(scheduler_stats['total_failed']),
                metric_type=MetricType.COUNTER,
                unit="jobs"
            ))
            
            # 성공률
            total_processed = scheduler_stats['total_completed'] + scheduler_stats['total_failed']
            if total_processed > 0:
                success_rate = (scheduler_stats['total_completed'] / total_processed) * 100
                metrics.append(PerformanceMetric(
                    name="batch.success.rate",
                    value=success_rate,
                    metric_type=MetricType.GAUGE,
                    unit="percent"
                ))
            
            # 작업 유형별 메트릭
            with self.batch_manager.scheduler.active_lock:
                job_type_counts = defaultdict(int)
                for job in self.batch_manager.scheduler.active_jobs.values():
                    job_type_counts[job.job_type.value] += 1
                
                for job_type, count in job_type_counts.items():
                    metrics.append(PerformanceMetric(
                        name="batch.active.by_type",
                        value=float(count),
                        metric_type=MetricType.GAUGE,
                        unit="jobs",
                        tags={"job_type": job_type}
                    ))
        
        except Exception as e:
            logger.error(f"배치 작업 메트릭 수집 실패: {e}")
        
        return metrics

# ===== 실시간 진행률 추적기 =====

class JobProgressTracker:
    """작업 진행률 추적기"""
    
    def __init__(self):
        self.batch_manager = get_batch_manager()
        self.progress_info: Dict[str, JobProgressInfo] = {}
        self.lock = threading.Lock()
        
        # 진행률 추정을 위한 히스토리
        self.progress_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
    
    def update_job_progress(
        self, 
        job_id: str, 
        progress_percent: float,
        current_stage: str = "",
        stages_completed: int = 0,
        total_stages: int = 1,
        error_message: str = "",
        warning_message: str = ""
    ) -> None:
        """작업 진행률 업데이트"""
        
        with self.lock:
            current_time = datetime.now()
            
            # 기존 정보 가져오기 또는 새로 생성
            if job_id in self.progress_info:
                progress_info = self.progress_info[job_id]
            else:
                # 배치 매니저에서 작업 정보 가져오기
                job = self.batch_manager.scheduler.job_history.get(job_id)
                
                # 작업 정보가 없어도 기본 진행률 정보 생성 (테스트 목적)
                if not job:
                    logger.warning(f"알 수 없는 작업 ID, 기본 정보로 생성: {job_id}")
                    progress_info = JobProgressInfo(
                        job_id=job_id,
                        job_type="unknown",
                        priority="NORMAL",
                        progress_percent=0.0,
                        estimated_remaining_seconds=300,
                        current_stage="시작",
                        stages_completed=0,
                        total_stages=total_stages
                    )
                else:
                    progress_info = JobProgressInfo(
                        job_id=job_id,
                        job_type=job.job_type.value,
                        priority=job.priority.name,
                        progress_percent=0.0,
                        estimated_remaining_seconds=job.estimated_duration,
                        current_stage="시작",
                        stages_completed=0,
                        total_stages=total_stages
                    )
                
                self.progress_info[job_id] = progress_info
            
            # 진행률 업데이트
            progress_info.progress_percent = min(progress_percent, 100.0)
            progress_info.current_stage = current_stage or progress_info.current_stage
            progress_info.stages_completed = stages_completed
            progress_info.total_stages = max(total_stages, progress_info.total_stages)
            
            # 에러/경고 메시지 추가
            if error_message:
                progress_info.error_messages.append(f"{current_time.strftime('%H:%M:%S')}: {error_message}")
                # 최근 5개만 유지
                progress_info.error_messages = progress_info.error_messages[-5:]
            
            if warning_message:
                progress_info.warnings.append(f"{current_time.strftime('%H:%M:%S')}: {warning_message}")
                # 최근 5개만 유지
                progress_info.warnings = progress_info.warnings[-5:]
            
            # 진행률 히스토리 업데이트 (처리량 계산용)
            self.progress_history[job_id].append((current_time.timestamp(), progress_percent))
            
            # 예상 완료 시간 계산
            self._calculate_estimated_time(job_id, progress_info)
    
    def _calculate_estimated_time(self, job_id: str, progress_info: JobProgressInfo) -> None:
        """예상 완료 시간 계산"""
        history = self.progress_history[job_id]
        
        if len(history) < 2 or progress_info.progress_percent <= 0:
            return
        
        # 최근 진행률 변화 계산
        recent_entries = list(history)[-5:]  # 최근 5개 데이터포인트
        
        if len(recent_entries) >= 2:
            time_diff = recent_entries[-1][0] - recent_entries[0][0]
            progress_diff = recent_entries[-1][1] - recent_entries[0][1]
            
            if time_diff > 0 and progress_diff > 0:
                # 초당 진행률
                progress_rate = progress_diff / time_diff
                progress_info.throughput_per_second = progress_rate
                
                # 남은 진행률
                remaining_progress = 100.0 - progress_info.progress_percent
                
                # 예상 완료 시간 (초)
                if progress_rate > 0:
                    progress_info.estimated_remaining_seconds = int(remaining_progress / progress_rate)
                else:
                    progress_info.estimated_remaining_seconds = 0
    
    def get_job_progress(self, job_id: str) -> Optional[JobProgressInfo]:
        """작업 진행률 조회"""
        with self.lock:
            return self.progress_info.get(job_id)
    
    def get_all_active_progress(self) -> List[JobProgressInfo]:
        """모든 활성 작업의 진행률 조회"""
        with self.lock:
            # 배치 매니저의 활성 작업과 매칭
            active_job_ids = set(self.batch_manager.scheduler.active_jobs.keys())
            
            active_progress = []
            for job_id, progress_info in self.progress_info.items():
                if job_id in active_job_ids:
                    active_progress.append(progress_info)
            
            return active_progress
    
    def cleanup_completed_jobs(self) -> None:
        """완료된 작업 정리"""
        with self.lock:
            active_job_ids = set(self.batch_manager.scheduler.active_jobs.keys())
            
            # 더 이상 활성 상태가 아닌 작업 제거
            completed_jobs = [
                job_id for job_id in self.progress_info.keys() 
                if job_id not in active_job_ids
            ]
            
            for job_id in completed_jobs:
                del self.progress_info[job_id]
                if job_id in self.progress_history:
                    del self.progress_history[job_id]
            
            if completed_jobs:
                logger.info(f"완료된 작업 {len(completed_jobs)}개 정리됨")

# ===== 통합 모니터링 서비스 =====

class AdvancedMonitoringService:
    """고급 모니터링 서비스"""
    
    def __init__(self):
        # 컴포넌트 초기화
        self.batch_manager = get_batch_manager()
        self.progress_tracker = JobProgressTracker()
        
        # 알림 처리기
        self.alert_handlers: List[AlertHandler] = [
            ConsoleAlertHandler(),
            WebSocketAlertHandler()
        ]
        
        # 메트릭 수집기
        self.metric_collectors: List[MetricCollector] = [
            SystemMetricCollector(),
            BatchJobMetricCollector()
        ]
        
        # 알림 관리
        self.active_alerts: Dict[str, MonitoringAlert] = {}
        self.alert_history: deque = deque(maxlen=100)  # 최근 100개 알림
        
        # 메트릭 저장소 (인메모리)
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 모니터링 설정
        self.monitoring_enabled = True
        self.monitoring_interval = 10  # 10초마다 수집
        self.alert_cooldown = 300      # 5분간 동일 알림 방지
        
        # 알림 임계값
        self.alert_thresholds = {
            'system.cpu.usage': 85.0,
            'system.memory.usage': 90.0,
            'batch.queue.size': 50,
            'batch.success.rate': 80.0  # 80% 미만 시 알림
        }
        
        # 모니터링 스레드
        self.monitoring_thread: Optional[threading.Thread] = None
        
        logger.info("고급 모니터링 서비스 초기화 완료")
    
    def start_monitoring(self) -> None:
        """모니터링 시작"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            logger.warning("모니터링이 이미 실행 중입니다")
            return
        
        self.monitoring_enabled = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="AdvancedMonitoring",
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info("고급 모니터링 시작됨")
    
    def stop_monitoring(self) -> None:
        """모니터링 정지"""
        self.monitoring_enabled = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        
        logger.info("고급 모니터링 정지됨")
    
    def _monitoring_loop(self) -> None:
        """모니터링 루프"""
        while self.monitoring_enabled:
            try:
                # 메트릭 수집
                self._collect_all_metrics()
                
                # 알림 확인
                self._check_alerts()
                
                # 진행률 추적기 정리
                self.progress_tracker.cleanup_completed_jobs()
                
                # 대기
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                time.sleep(5)
    
    def _collect_all_metrics(self) -> None:
        """모든 메트릭 수집"""
        all_metrics = []
        
        for collector in self.metric_collectors:
            try:
                metrics = collector.collect_metrics()
                all_metrics.extend(metrics)
            except Exception as e:
                logger.error(f"메트릭 수집 실패 ({collector.__class__.__name__}): {e}")
        
        # 메트릭 저장
        for metric in all_metrics:
            self.metrics_history[metric.name].append(metric)
    
    def _check_alerts(self) -> None:
        """알림 확인 및 전송"""
        current_time = datetime.now()
        
        # 최근 메트릭 기준 알림 확인
        for metric_name, threshold in self.alert_thresholds.items():
            if metric_name in self.metrics_history:
                metrics = self.metrics_history[metric_name]
                if metrics:
                    latest_metric = metrics[-1]
                    self._check_metric_alert(latest_metric, threshold, current_time)
        
        # 배치 작업 관련 알림 확인
        self._check_batch_job_alerts(current_time)
    
    def _check_metric_alert(
        self, 
        metric: PerformanceMetric, 
        threshold: float, 
        current_time: datetime
    ) -> None:
        """메트릭 기반 알림 확인"""
        alert_id = f"metric_{metric.name}"
        
        # 쿨다운 확인
        if alert_id in self.active_alerts:
            last_alert_time = self.active_alerts[alert_id].timestamp
            if (current_time - last_alert_time).total_seconds() < self.alert_cooldown:
                return
        
        # 임계값 확인
        should_alert = False
        severity = AlertSeverity.INFO
        
        if metric.name.endswith('.usage') or metric.name.endswith('.rate'):
            if metric.value > threshold:
                should_alert = True
                if metric.value > threshold * 1.1:  # 110% 이상
                    severity = AlertSeverity.CRITICAL
                else:
                    severity = AlertSeverity.WARNING
        elif metric.name == 'batch.queue.size':
            if metric.value > threshold:
                should_alert = True
                if metric.value > threshold * 2:  # 2배 이상
                    severity = AlertSeverity.CRITICAL
                else:
                    severity = AlertSeverity.WARNING
        elif metric.name == 'batch.success.rate':
            if metric.value < threshold:
                should_alert = True
                if metric.value < threshold * 0.7:  # 70% 미만
                    severity = AlertSeverity.CRITICAL
                else:
                    severity = AlertSeverity.WARNING
        
        if should_alert:
            alert = MonitoringAlert(
                alert_id=alert_id,
                severity=severity,
                title=f"{metric.name} 임계값 초과",
                message=f"{metric.name}: {metric.value:.2f}{metric.unit} (임계값: {threshold})",
                source="metric_monitor",
                metadata={
                    "metric_name": metric.name,
                    "current_value": metric.value,
                    "threshold": threshold,
                    "unit": metric.unit
                }
            )
            
            asyncio.create_task(self._send_alert(alert))
    
    def _check_batch_job_alerts(self, current_time: datetime) -> None:
        """배치 작업 관련 알림 확인"""
        # 오래 실행되는 작업 확인
        with self.batch_manager.scheduler.active_lock:
            for job in self.batch_manager.scheduler.active_jobs.values():
                if job.started_at:
                    runtime = (current_time - job.started_at).total_seconds()
                    expected_duration = job.estimated_duration
                    
                    # 예상 시간의 2배 이상 실행 중인 경우
                    if runtime > expected_duration * 2:
                        alert_id = f"long_running_job_{job.job_id}"
                        
                        if alert_id not in self.active_alerts:
                            alert = MonitoringAlert(
                                alert_id=alert_id,
                                severity=AlertSeverity.WARNING,
                                title="장시간 실행 작업 감지",
                                message=f"작업 {job.job_id}가 예상 시간보다 오래 실행 중입니다 (실행시간: {runtime/60:.1f}분, 예상: {expected_duration/60:.1f}분)",
                                source="job_monitor",
                                metadata={
                                    "job_id": job.job_id,
                                    "job_type": job.job_type.value,
                                    "runtime_seconds": runtime,
                                    "expected_duration": expected_duration
                                }
                            )
                            
                            asyncio.create_task(self._send_alert(alert))
    
    async def _send_alert(self, alert: MonitoringAlert) -> None:
        """알림 전송"""
        # 활성 알림에 추가
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        
        # 모든 알림 처리기에 전송
        for handler in self.alert_handlers:
            try:
                await handler.send_alert(alert)
            except Exception as e:
                logger.error(f"알림 전송 실패 ({handler.__class__.__name__}): {e}")
    
    def get_websocket_handler(self) -> WebSocketAlertHandler:
        """WebSocket 알림 처리기 반환"""
        for handler in self.alert_handlers:
            if isinstance(handler, WebSocketAlertHandler):
                return handler
        return None
    
    def get_monitoring_dashboard(self) -> Dict[str, Any]:
        """모니터링 대시보드 데이터"""
        current_time = datetime.now()
        
        # 최신 메트릭
        latest_metrics = {}
        for metric_name, metrics in self.metrics_history.items():
            if metrics:
                latest_metrics[metric_name] = metrics[-1].to_dict()
        
        # 활성 알림
        active_alerts = [alert.to_dict() for alert in self.active_alerts.values()]
        
        # 최근 알림 (최근 10개)
        recent_alerts = [alert.to_dict() for alert in list(self.alert_history)[-10:]]
        
        # 작업 진행률
        active_progress = [
            progress.to_dict() 
            for progress in self.progress_tracker.get_all_active_progress()
        ]
        
        # 시스템 요약
        system_summary = self._get_system_summary(latest_metrics)
        
        return {
            "timestamp": current_time.isoformat(),
            "system_summary": system_summary,
            "latest_metrics": latest_metrics,
            "active_alerts": active_alerts,
            "recent_alerts": recent_alerts,
            "job_progress": active_progress,
            "monitoring_status": {
                "enabled": self.monitoring_enabled,
                "interval_seconds": self.monitoring_interval,
                "total_metrics_collected": sum(len(metrics) for metrics in self.metrics_history.values()),
                "total_alerts_sent": len(self.alert_history)
            }
        }
    
    def _get_system_summary(self, latest_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """시스템 요약 정보"""
        summary = {
            "overall_health": "healthy",
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "active_jobs": 0,
            "queue_size": 0,
            "success_rate": 100.0
        }
        
        try:
            # 시스템 메트릭
            if "system.cpu.usage" in latest_metrics:
                summary["cpu_usage"] = latest_metrics["system.cpu.usage"]["value"]
            
            if "system.memory.usage" in latest_metrics:
                summary["memory_usage"] = latest_metrics["system.memory.usage"]["value"]
            
            # 배치 작업 메트릭
            if "batch.active.jobs" in latest_metrics:
                summary["active_jobs"] = int(latest_metrics["batch.active.jobs"]["value"])
            
            if "batch.queue.size" in latest_metrics:
                summary["queue_size"] = int(latest_metrics["batch.queue.size"]["value"])
            
            if "batch.success.rate" in latest_metrics:
                summary["success_rate"] = latest_metrics["batch.success.rate"]["value"]
            
            # 전체 건강 상태 판단
            if (summary["cpu_usage"] > 90 or 
                summary["memory_usage"] > 95 or 
                len(self.active_alerts) > 5):
                summary["overall_health"] = "critical"
            elif (summary["cpu_usage"] > 80 or 
                  summary["memory_usage"] > 85 or 
                  len(self.active_alerts) > 2):
                summary["overall_health"] = "warning"
        
        except Exception as e:
            logger.error(f"시스템 요약 생성 실패: {e}")
        
        return summary
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """알림 확인 처리"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            logger.info(f"알림 확인됨: {alert_id}")
            return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """알림 해결 처리"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.acknowledged = True
            
            # 활성 알림에서 제거
            del self.active_alerts[alert_id]
            
            logger.info(f"알림 해결됨: {alert_id}")
            return True
        return False
    
    def get_metric_history(
        self, 
        metric_name: str, 
        minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """메트릭 히스토리 조회"""
        if metric_name not in self.metrics_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        filtered_metrics = [
            metric.to_dict()
            for metric in self.metrics_history[metric_name]
            if metric.timestamp >= cutoff_time
        ]
        
        return filtered_metrics

# ===== 전역 인스턴스 =====

_global_monitoring_service: Optional[AdvancedMonitoringService] = None

def get_monitoring_service() -> AdvancedMonitoringService:
    """전역 모니터링 서비스 인스턴스 반환"""
    global _global_monitoring_service
    
    if _global_monitoring_service is None:
        _global_monitoring_service = AdvancedMonitoringService()
    
    return _global_monitoring_service

def shutdown_monitoring_service() -> None:
    """전역 모니터링 서비스 종료"""
    global _global_monitoring_service
    
    if _global_monitoring_service is not None:
        _global_monitoring_service.stop_monitoring()
        _global_monitoring_service = None