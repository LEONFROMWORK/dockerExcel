"""
Insights Services
프로액티브 인사이트 서비스 모음
"""

from app.services.insights.pattern_analyzer import (
    PatternAnalyzer,
    UserAction,
    WorkPattern,
)
from app.services.insights.error_predictor import ErrorPredictor, ErrorPrediction
from app.services.insights.optimization_advisor import (
    OptimizationAdvisor,
    OptimizationSuggestion,
)
from app.services.insights.proactive_notifier import (
    ProactiveNotifier,
    ProactiveNotification,
    NotificationType,
    NotificationPriority,
)

# 싱글톤 인스턴스
_pattern_analyzer: PatternAnalyzer = None
_error_predictor: ErrorPredictor = None
_optimization_advisor: OptimizationAdvisor = None
_proactive_notifier: ProactiveNotifier = None


def get_pattern_analyzer() -> PatternAnalyzer:
    """패턴 분석기 싱글톤 인스턴스"""
    global _pattern_analyzer
    if _pattern_analyzer is None:
        _pattern_analyzer = PatternAnalyzer()
    return _pattern_analyzer


def get_error_predictor() -> ErrorPredictor:
    """오류 예측기 싱글톤 인스턴스"""
    global _error_predictor
    if _error_predictor is None:
        _error_predictor = ErrorPredictor()
    return _error_predictor


def get_optimization_advisor() -> OptimizationAdvisor:
    """최적화 자문 싱글톤 인스턴스"""
    global _optimization_advisor
    if _optimization_advisor is None:
        _optimization_advisor = OptimizationAdvisor()
    return _optimization_advisor


def get_proactive_notifier() -> ProactiveNotifier:
    """프로액티브 알림 싱글톤 인스턴스"""
    global _proactive_notifier
    if _proactive_notifier is None:
        _proactive_notifier = ProactiveNotifier()
    return _proactive_notifier


__all__ = [
    # 클래스
    "PatternAnalyzer",
    "UserAction",
    "WorkPattern",
    "ErrorPredictor",
    "ErrorPrediction",
    "OptimizationAdvisor",
    "OptimizationSuggestion",
    "ProactiveNotifier",
    "ProactiveNotification",
    "NotificationType",
    "NotificationPriority",
    # 팩토리 함수
    "get_pattern_analyzer",
    "get_error_predictor",
    "get_optimization_advisor",
    "get_proactive_notifier",
]
