"""
실시간 모니터링 대시보드를 위한 SOLID 원칙 준수 서비스

관리자용 실시간 모니터링 기능:
- OCR 처리량 모니터링
- 성공률 통계
- 언어별 성능 분석
- 시스템 리소스 사용량
- 오류 패턴 분석
- 알림 시스템

Interface Segregation Principle (ISP): 각각의 모니터링 기능을 개별 프로토콜로 분리
Single Responsibility Principle (SRP): 각 클래스는 하나의 책임만
Dependency Inversion Principle (DIP): 추상화에 의존, 구현에 의존하지 않음
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Protocol
from datetime import datetime, timedelta
import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from collections import defaultdict
import psutil
import threading
import time

# ===== Protocols (ISP) =====

class MetricsCollector(Protocol):
    """메트릭 수집 인터페이스"""
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """메트릭 수집"""
        ...
    
    def get_metric_types(self) -> List[str]:
        """지원하는 메트릭 타입 반환"""
        ...

class AlertManager(Protocol):
    """알림 관리 인터페이스"""
    
    async def check_thresholds(self, metrics: Dict[str, Any]) -> List[Dict]:
        """임계값 확인 및 알림 생성"""
        ...
    
    async def send_alert(self, alert: Dict) -> bool:
        """알림 전송"""
        ...

class DataStorage(Protocol):
    """데이터 저장 인터페이스"""
    
    async def store_metrics(self, metrics: Dict[str, Any]) -> bool:
        """메트릭 저장"""
        ...
    
    async def get_historical_data(self, hours: int) -> List[Dict]:
        """과거 데이터 조회"""
        ...

class DashboardRenderer(Protocol):
    """대시보드 렌더링 인터페이스"""
    
    def render_real_time_dashboard(self, metrics: Dict[str, Any]) -> str:
        """실시간 대시보드 HTML 생성"""
        ...
    
    def render_metrics_chart(self, data: List[Dict], chart_type: str) -> str:
        """차트 HTML 생성"""
        ...

# ===== Data Models =====

@dataclass
class OCRMetrics:
    """OCR 성능 메트릭"""
    timestamp: datetime
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_processing_time: float = 0.0
    language_stats: Dict[str, Dict] = None
    
    def __post_init__(self):
        if self.language_stats is None:
            self.language_stats = {}
    
    @property
    def success_rate(self) -> float:
        """성공률 계산"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

@dataclass
class SystemMetrics:
    """시스템 리소스 메트릭"""
    timestamp: datetime
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_io: Dict[str, int] = None
    
    def __post_init__(self):
        if self.network_io is None:
            self.network_io = {"bytes_sent": 0, "bytes_recv": 0}

@dataclass
class AlertConfig:
    """알림 설정"""
    metric_name: str
    threshold: float
    comparison: str  # "gt", "lt", "eq"
    severity: str  # "low", "medium", "high", "critical"
    cooldown_minutes: int = 30

# ===== Implementations (SRP) =====

class OCRMetricsCollector:
    """OCR 메트릭 수집기 - SRP: OCR 관련 메트릭만 수집"""
    
    def __init__(self):
        self.request_counter = 0
        self.success_counter = 0
        self.failure_counter = 0
        self.processing_times = []
        self.language_data = defaultdict(lambda: {"requests": 0, "successes": 0, "avg_time": 0.0})
        self.lock = threading.Lock()
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """현재 OCR 메트릭 수집"""
        with self.lock:
            avg_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0.0
            
            metrics = OCRMetrics(
                timestamp=datetime.now(),
                total_requests=self.request_counter,
                successful_requests=self.success_counter,
                failed_requests=self.failure_counter,
                average_processing_time=avg_time,
                language_stats=dict(self.language_data)
            )
            
            return asdict(metrics)
    
    def get_metric_types(self) -> List[str]:
        return ["ocr_requests", "success_rate", "processing_time", "language_performance"]
    
    def record_request(self, language: str, success: bool, processing_time: float):
        """요청 기록"""
        with self.lock:
            self.request_counter += 1
            self.processing_times.append(processing_time)
            
            # 최근 1000개 처리시간만 유지
            if len(self.processing_times) > 1000:
                self.processing_times = self.processing_times[-1000:]
            
            if success:
                self.success_counter += 1
                self.language_data[language]["successes"] += 1
            else:
                self.failure_counter += 1
            
            self.language_data[language]["requests"] += 1
            lang_data = self.language_data[language]
            lang_data["avg_time"] = (lang_data.get("avg_time", 0) * (lang_data["requests"] - 1) + processing_time) / lang_data["requests"]

class SystemMetricsCollector:
    """시스템 메트릭 수집기 - SRP: 시스템 리소스만 모니터링"""
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """시스템 리소스 메트릭 수집"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_usage=cpu_percent,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                network_io={
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv
                }
            )
            
            return asdict(metrics)
        except Exception as e:
            logging.error(f"시스템 메트릭 수집 실패: {e}")
            return {}
    
    def get_metric_types(self) -> List[str]:
        return ["cpu_usage", "memory_usage", "disk_usage", "network_io"]

class InMemoryDataStorage:
    """인메모리 데이터 저장소 - SRP: 데이터 저장/조회만"""
    
    def __init__(self, max_hours: int = 24):
        self.max_hours = max_hours
        self.metrics_data = []
        self.lock = threading.Lock()
    
    async def store_metrics(self, metrics: Dict[str, Any]) -> bool:
        """메트릭 저장"""
        try:
            with self.lock:
                self.metrics_data.append(metrics)
                
                # 오래된 데이터 정리
                cutoff_time = datetime.now() - timedelta(hours=self.max_hours)
                self.metrics_data = [
                    m for m in self.metrics_data 
                    if datetime.fromisoformat(m.get('timestamp', '1970-01-01')) > cutoff_time
                ]
            
            return True
        except Exception as e:
            logging.error(f"메트릭 저장 실패: {e}")
            return False
    
    async def get_historical_data(self, hours: int) -> List[Dict]:
        """과거 데이터 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with self.lock:
                return [
                    m for m in self.metrics_data
                    if datetime.fromisoformat(m.get('timestamp', '1970-01-01')) > cutoff_time
                ]
        except Exception as e:
            logging.error(f"과거 데이터 조회 실패: {e}")
            return []

class ThresholdAlertManager:
    """임계값 기반 알림 관리자 - SRP: 알림 생성/전송만"""
    
    def __init__(self, alert_configs: List[AlertConfig]):
        self.alert_configs = alert_configs
        self.last_alerts = {}  # 알림 쿨다운 관리
    
    async def check_thresholds(self, metrics: Dict[str, Any]) -> List[Dict]:
        """임계값 확인"""
        alerts = []
        current_time = datetime.now()
        
        for config in self.alert_configs:
            metric_value = self._extract_metric_value(metrics, config.metric_name)
            if metric_value is None:
                continue
            
            # 임계값 검사
            triggered = self._check_threshold(metric_value, config)
            if not triggered:
                continue
            
            # 쿨다운 검사
            last_alert_time = self.last_alerts.get(config.metric_name)
            if last_alert_time:
                time_diff = (current_time - last_alert_time).total_seconds() / 60
                if time_diff < config.cooldown_minutes:
                    continue
            
            # 알림 생성
            alert = {
                "metric_name": config.metric_name,
                "value": metric_value,
                "threshold": config.threshold,
                "severity": config.severity,
                "message": f"{config.metric_name} 임계값 초과: {metric_value} ({config.comparison} {config.threshold})",
                "timestamp": current_time.isoformat()
            }
            
            alerts.append(alert)
            self.last_alerts[config.metric_name] = current_time
        
        return alerts
    
    async def send_alert(self, alert: Dict) -> bool:
        """알림 전송 (로깅으로 구현)"""
        try:
            logging.warning(f"🚨 [알림] {alert['message']}")
            return True
        except Exception as e:
            logging.error(f"알림 전송 실패: {e}")
            return False
    
    def _extract_metric_value(self, metrics: Dict[str, Any], metric_name: str) -> Optional[float]:
        """메트릭에서 값 추출"""
        if metric_name == "success_rate":
            total = metrics.get("total_requests", 0)
            success = metrics.get("successful_requests", 0)
            return (success / total * 100) if total > 0 else 0.0
        elif metric_name == "cpu_usage":
            return metrics.get("cpu_usage", 0.0)
        elif metric_name == "memory_usage":
            return metrics.get("memory_usage", 0.0)
        elif metric_name == "average_processing_time":
            return metrics.get("average_processing_time", 0.0)
        
        return metrics.get(metric_name)
    
    def _check_threshold(self, value: float, config: AlertConfig) -> bool:
        """임계값 검사"""
        if config.comparison == "gt":
            return value > config.threshold
        elif config.comparison == "lt":
            return value < config.threshold
        elif config.comparison == "eq":
            return abs(value - config.threshold) < 0.01
        return False

class HTMLDashboardRenderer:
    """HTML 대시보드 렌더러 - SRP: 화면 렌더링만"""
    
    def render_real_time_dashboard(self, metrics: Dict[str, Any]) -> str:
        """실시간 대시보드 HTML 생성"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OCR 실시간 모니터링 대시보드</title>
            <meta charset="utf-8">
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .dashboard {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric {{ margin: 10px 0; }}
                .metric-label {{ font-weight: bold; color: #333; }}
                .metric-value {{ font-size: 1.2em; color: #007bff; }}
                .success {{ color: #28a745; }}
                .warning {{ color: #ffc107; }}
                .danger {{ color: #dc3545; }}
                .language-stats {{ margin-top: 15px; }}
                .language-item {{ margin: 5px 0; padding: 5px; background: #f8f9fa; border-radius: 4px; }}
                h1 {{ text-align: center; color: #333; }}
                h2 {{ color: #555; border-bottom: 2px solid #007bff; padding-bottom: 5px; }}
                .timestamp {{ text-align: center; color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <h1>🖥️ OCR 실시간 모니터링 대시보드</h1>
            <div class="timestamp">최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            
            <div class="dashboard">
                <div class="card">
                    <h2>📊 OCR 성능 메트릭</h2>
                    <div class="metric">
                        <span class="metric-label">총 요청 수:</span>
                        <span class="metric-value">{metrics.get('total_requests', 0)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">성공률:</span>
                        <span class="metric-value {self._get_success_rate_class(metrics)}">{self._calculate_success_rate(metrics):.1f}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">평균 처리시간:</span>
                        <span class="metric-value">{metrics.get('average_processing_time', 0):.2f}초</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">실패 요청:</span>
                        <span class="metric-value danger">{metrics.get('failed_requests', 0)}</span>
                    </div>
                </div>
                
                <div class="card">
                    <h2>💻 시스템 리소스</h2>
                    <div class="metric">
                        <span class="metric-label">CPU 사용률:</span>
                        <span class="metric-value {self._get_usage_class(metrics.get('cpu_usage', 0))}">{metrics.get('cpu_usage', 0):.1f}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">메모리 사용률:</span>
                        <span class="metric-value {self._get_usage_class(metrics.get('memory_usage', 0))}">{metrics.get('memory_usage', 0):.1f}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">디스크 사용률:</span>
                        <span class="metric-value {self._get_usage_class(metrics.get('disk_usage', 0))}">{metrics.get('disk_usage', 0):.1f}%</span>
                    </div>
                </div>
                
                <div class="card">
                    <h2>🌐 언어별 성능</h2>
                    <div class="language-stats">
                        {self._render_language_stats(metrics.get('language_stats', {}))}
                    </div>
                </div>
                
                <div class="card">
                    <h2>📈 실시간 통계</h2>
                    <div class="metric">
                        <span class="metric-label">현재 시간:</span>
                        <span class="metric-value">{datetime.now().strftime('%H:%M:%S')}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">모니터링 상태:</span>
                        <span class="metric-value success">✅ 활성</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def render_metrics_chart(self, data: List[Dict], chart_type: str) -> str:
        """차트 HTML 생성 (간단한 구현)"""
        return f"<div>차트 데이터: {len(data)}개 포인트 ({chart_type})</div>"
    
    def _calculate_success_rate(self, metrics: Dict[str, Any]) -> float:
        """성공률 계산"""
        total = metrics.get('total_requests', 0)
        success = metrics.get('successful_requests', 0)
        return (success / total * 100) if total > 0 else 0.0
    
    def _get_success_rate_class(self, metrics: Dict[str, Any]) -> str:
        """성공률에 따른 CSS 클래스"""
        rate = self._calculate_success_rate(metrics)
        if rate >= 95:
            return "success"
        elif rate >= 80:
            return "warning"
        else:
            return "danger"
    
    def _get_usage_class(self, usage: float) -> str:
        """사용률에 따른 CSS 클래스"""
        if usage < 70:
            return "success"
        elif usage < 90:
            return "warning"
        else:
            return "danger"
    
    def _render_language_stats(self, language_stats: Dict[str, Dict]) -> str:
        """언어별 통계 렌더링"""
        if not language_stats:
            return "<div>언어별 데이터가 없습니다.</div>"
        
        html = ""
        for lang, stats in language_stats.items():
            success_rate = (stats.get('successes', 0) / stats.get('requests', 1)) * 100
            html += f"""
            <div class="language-item">
                <strong>{lang.upper()}:</strong> 
                {stats.get('requests', 0)}건 
                (성공률: {success_rate:.1f}%, 
                평균시간: {stats.get('avg_time', 0):.2f}초)
            </div>
            """
        
        return html

# ===== Main Service (DIP) =====

class RealTimeMonitoringService:
    """실시간 모니터링 서비스 - DIP: 추상화에 의존"""
    
    def __init__(
        self,
        ocr_collector: MetricsCollector,
        system_collector: MetricsCollector,
        storage: DataStorage,
        alert_manager: AlertManager,
        dashboard_renderer: DashboardRenderer
    ):
        """의존성 주입을 통한 초기화"""
        self.ocr_collector = ocr_collector
        self.system_collector = system_collector
        self.storage = storage
        self.alert_manager = alert_manager
        self.dashboard_renderer = dashboard_renderer
        
        self.monitoring_active = False
        self.monitoring_task = None
    
    async def start_monitoring(self, interval_seconds: int = 30):
        """모니터링 시작"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop(interval_seconds))
        logging.info("실시간 모니터링 시작됨")
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logging.info("실시간 모니터링 중지됨")
    
    async def get_current_dashboard(self) -> str:
        """현재 대시보드 HTML 생성"""
        # 현재 메트릭 수집
        ocr_metrics = await self.ocr_collector.collect_metrics()
        system_metrics = await self.system_collector.collect_metrics()
        
        # 메트릭 통합
        combined_metrics = {**ocr_metrics, **system_metrics}
        
        # 대시보드 렌더링
        return self.dashboard_renderer.render_real_time_dashboard(combined_metrics)
    
    async def get_metrics_api(self) -> Dict[str, Any]:
        """API용 메트릭 데이터"""
        ocr_metrics = await self.ocr_collector.collect_metrics()
        system_metrics = await self.system_collector.collect_metrics()
        
        return {
            "ocr_metrics": ocr_metrics,
            "system_metrics": system_metrics,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_historical_data(self, hours: int = 1) -> List[Dict]:
        """과거 데이터 조회"""
        return await self.storage.get_historical_data(hours)
    
    async def _monitoring_loop(self, interval_seconds: int):
        """모니터링 루프"""
        while self.monitoring_active:
            try:
                # 메트릭 수집
                ocr_metrics = await self.ocr_collector.collect_metrics()
                system_metrics = await self.system_collector.collect_metrics()
                combined_metrics = {**ocr_metrics, **system_metrics}
                
                # 데이터 저장
                await self.storage.store_metrics(combined_metrics)
                
                # 알림 확인
                alerts = await self.alert_manager.check_thresholds(combined_metrics)
                for alert in alerts:
                    await self.alert_manager.send_alert(alert)
                
                # 다음 수집까지 대기
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logging.error(f"모니터링 루프 오류: {e}")
                await asyncio.sleep(interval_seconds)

# ===== Factory Function =====

def create_monitoring_service() -> RealTimeMonitoringService:
    """모니터링 서비스 팩토리 - 의존성 주입 설정"""
    
    # 컬렉터 생성
    ocr_collector = OCRMetricsCollector()
    system_collector = SystemMetricsCollector()
    
    # 저장소 생성
    storage = InMemoryDataStorage(max_hours=24)
    
    # 알림 설정
    alert_configs = [
        AlertConfig("success_rate", 80.0, "lt", "high", 30),
        AlertConfig("cpu_usage", 90.0, "gt", "medium", 15),
        AlertConfig("memory_usage", 85.0, "gt", "medium", 15),
        AlertConfig("average_processing_time", 10.0, "gt", "low", 20),
    ]
    alert_manager = ThresholdAlertManager(alert_configs)
    
    # 렌더러 생성
    dashboard_renderer = HTMLDashboardRenderer()
    
    return RealTimeMonitoringService(
        ocr_collector=ocr_collector,
        system_collector=system_collector,
        storage=storage,
        alert_manager=alert_manager,
        dashboard_renderer=dashboard_renderer
    )

# 전역 모니터링 서비스 인스턴스
_monitoring_service_instance = None

def get_monitoring_service() -> RealTimeMonitoringService:
    """싱글톤 모니터링 서비스 반환"""
    global _monitoring_service_instance
    if _monitoring_service_instance is None:
        _monitoring_service_instance = create_monitoring_service()
    return _monitoring_service_instance