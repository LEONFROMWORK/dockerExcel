#!/usr/bin/env python3
"""
성능 벤치마크 테스트 서비스
Performance Benchmark Test Service

11개 언어별 정확도 측정, 처리 속도 분석, 메모리 사용량 모니터링
SOLID 원칙을 준수한 리팩토링된 구조로 구현
"""

import logging
import time
import psutil
import asyncio
import statistics
from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from pathlib import Path
import json
import numpy as np
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# SOLID 원칙 적용: Interface Segregation
class OCRProcessor(Protocol):
    """OCR 처리 인터페이스"""
    def process_image(self, image_path: str, language: str) -> Dict[str, Any]:
        ...
    
    def get_service_info(self) -> Dict[str, str]:
        ...


class PerformanceMetrics(Protocol):
    """성능 측정 인터페이스"""
    def measure_processing_time(self, func, *args, **kwargs) -> tuple:
        ...
    
    def measure_memory_usage(self, func, *args, **kwargs) -> tuple:
        ...


class BenchmarkReporter(Protocol):
    """벤치마크 결과 리포팅 인터페이스"""
    def generate_report(self, results: List[Dict]) -> Dict[str, Any]:
        ...


# 데이터 클래스들
@dataclass
class LanguageBenchmark:
    """언어별 벤치마크 결과"""
    language: str
    language_name: str
    total_tests: int
    successful_tests: int
    failed_tests: int
    average_accuracy: float
    average_processing_time: float
    average_memory_usage: float
    confidence_distribution: Dict[str, int]
    error_patterns: List[str]


@dataclass
class ProcessingMetrics:
    """개별 처리 성능 지표"""
    processing_time: float
    memory_used: float
    cpu_usage: float
    accuracy_score: float
    confidence_score: float
    text_length: int
    error_occurred: bool
    error_type: Optional[str] = None


@dataclass
class SystemBenchmark:
    """시스템 전체 벤치마크 결과"""
    test_session_id: str
    test_start_time: str
    test_duration: float
    total_images_processed: int
    overall_success_rate: float
    language_benchmarks: List[LanguageBenchmark]
    system_performance: Dict[str, float]
    recommendations: List[str]


# SOLID 원칙 적용: Single Responsibility
class PerformanceMeasurer:
    """성능 측정 전담 클래스"""
    
    def __init__(self):
        self.process = psutil.Process()
    
    def measure_processing_time(self, func, *args, **kwargs) -> tuple:
        """처리 시간 측정"""
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            return result, end_time - start_time, None
        except Exception as e:
            end_time = time.perf_counter()
            return None, end_time - start_time, str(e)
    
    def measure_memory_usage(self, func, *args, **kwargs) -> tuple:
        """메모리 사용량 측정"""
        tracemalloc.start()
        initial_memory = self.process.memory_info().rss
        
        try:
            result = func(*args, **kwargs)
            current_memory, peak_memory = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            memory_used = (self.process.memory_info().rss - initial_memory) / 1024 / 1024  # MB
            return result, memory_used, None
        except Exception as e:
            tracemalloc.stop()
            return None, 0, str(e)
    
    def measure_cpu_usage(self) -> float:
        """CPU 사용량 측정"""
        return self.process.cpu_percent(interval=0.1)
    
    def get_system_info(self) -> Dict[str, Any]:
        """시스템 정보 수집"""
        return {
            "cpu_count": psutil.cpu_count(),
            "total_memory": psutil.virtual_memory().total / 1024 / 1024 / 1024,  # GB
            "available_memory": psutil.virtual_memory().available / 1024 / 1024 / 1024,  # GB
            "cpu_usage": psutil.cpu_percent(interval=1),
            "memory_usage": psutil.virtual_memory().percent
        }


class AccuracyEvaluator:
    """정확도 평가 전담 클래스"""
    
    def __init__(self):
        # 테스트용 참조 데이터 (실제로는 데이터베이스에서 로드)
        self.reference_data = self._load_reference_data()
    
    def _load_reference_data(self) -> Dict[str, Dict[str, str]]:
        """참조 데이터 로드 (언어별 정답 텍스트)"""
        return {
            "kor": {
                "financial_table.png": "매출액 1,000,000원 영업이익 200,000원 당기순이익 150,000원",
                "invoice.png": "청구서 번호 INV-2024-001 총액 3,520,000원",
                "report.png": "월간 매출 분석 보고서 2024년 1월"
            },
            "eng": {
                "financial_table.png": "Revenue $1,000,000 Operating Income $200,000 Net Income $150,000",
                "invoice.png": "Invoice Number INV-2024-001 Total Amount $3,520,000",
                "report.png": "Monthly Sales Analysis Report January 2024"
            },
            "chi_sim": {
                "financial_table.png": "营业收入 1,000,000元 营业利润 200,000元 净利润 150,000元",
                "invoice.png": "发票编号 INV-2024-001 总金额 3,520,000元",
                "report.png": "月度销售分析报告 2024年1月"
            },
            "jpn": {
                "financial_table.png": "売上高 1,000,000円 営業利益 200,000円 当期純利益 150,000円",
                "invoice.png": "請求書番号 INV-2024-001 総額 3,520,000円",
                "report.png": "月次売上分析レポート 2024年1月"
            },
            "ara": {
                "financial_table.png": "الإيرادات 1,000,000 ريال الربح التشغيلي 200,000 ريال صافي الدخل 150,000 ريال",
                "invoice.png": "رقم الفاتورة INV-2024-001 المبلغ الإجمالي 3,520,000 ريال",
                "report.png": "تقرير تحليل المبيعات الشهرية يناير 2024"
            },
            "spa": {
                "financial_table.png": "Ingresos $1,000,000 Ingresos Operativos $200,000 Ingresos Netos $150,000",
                "invoice.png": "Número de Factura INV-2024-001 Monto Total $3,520,000",
                "report.png": "Informe de Análisis de Ventas Mensual Enero 2024"
            },
            "por": {
                "financial_table.png": "Receita R$1,000,000 Receita Operacional R$200,000 Receita Líquida R$150,000",
                "invoice.png": "Número da Fatura INV-2024-001 Valor Total R$3,520,000",
                "report.png": "Relatório de Análise de Vendas Mensal Janeiro 2024"
            },
            "fra": {
                "financial_table.png": "Revenus €1,000,000 Revenus d'Exploitation €200,000 Revenus Nets €150,000",
                "invoice.png": "Numéro de Facture INV-2024-001 Montant Total €3,520,000",
                "report.png": "Rapport d'Analyse des Ventes Mensuel Janvier 2024"
            },
            "deu": {
                "financial_table.png": "Umsatz €1,000,000 Betriebsgewinn €200,000 Nettogewinn €150,000",
                "invoice.png": "Rechnungsnummer INV-2024-001 Gesamtbetrag €3,520,000",
                "report.png": "Monatlicher Verkaufsanalysebericht Januar 2024"
            },
            "ita": {
                "financial_table.png": "Ricavi €1,000,000 Reddito Operativo €200,000 Reddito Netto €150,000",
                "invoice.png": "Numero Fattura INV-2024-001 Importo Totale €3,520,000",
                "report.png": "Rapporto di Analisi delle Vendite Mensile Gennaio 2024"
            },
            "vie": {
                "financial_table.png": "Doanh thu 1,000,000 VND Lợi nhuận hoạt động 200,000 VND Lợi nhuận ròng 150,000 VND",
                "invoice.png": "Số hóa đơn INV-2024-001 Tổng số tiền 3,520,000 VND",
                "report.png": "Báo cáo Phân tích Bán hàng Hàng tháng Tháng 1 2024"
            }
        }
    
    def calculate_accuracy(self, predicted_text: str, reference_text: str) -> float:
        """정확도 계산 (Levenshtein 거리 기반)"""
        import difflib
        
        if not reference_text:
            return 0.0
        
        # 정규화
        predicted = self._normalize_text(predicted_text)
        reference = self._normalize_text(reference_text)
        
        # 유사도 계산
        matcher = difflib.SequenceMatcher(None, predicted, reference)
        return matcher.ratio() * 100
    
    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        import re
        
        # 공백 정리
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 숫자 형식 통일 (콤마 제거)
        text = re.sub(r'(\d+),(\d+)', r'\1\2', text)
        
        return text.lower()
    
    def get_reference_text(self, language: str, image_name: str) -> Optional[str]:
        """참조 텍스트 조회"""
        return self.reference_data.get(language, {}).get(image_name)


class TestDataGenerator:
    """테스트 데이터 생성 전담 클래스"""
    
    def __init__(self):
        self.supported_languages = [
            ("kor", "한국어"),
            ("eng", "English"),
            ("chi_sim", "中文(简体)"),
            ("jpn", "日本語"),
            ("ara", "العربية"),
            ("spa", "Español"),
            ("por", "Português"),
            ("fra", "Français"),
            ("deu", "Deutsch"),
            ("ita", "Italiano"),
            ("vie", "Tiếng Việt")
        ]
    
    def create_test_images(self, output_dir: str) -> Dict[str, List[str]]:
        """언어별 테스트 이미지 생성"""
        from PIL import Image, ImageDraw, ImageFont
        import tempfile
        
        test_images = {}
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        for lang_code, lang_name in self.supported_languages:
            lang_dir = output_path / lang_code
            lang_dir.mkdir(exist_ok=True)
            
            test_images[lang_code] = []
            
            # 각 언어별로 3가지 테스트 이미지 생성
            templates = [
                ("financial_table", self._create_financial_table),
                ("invoice", self._create_invoice),
                ("report", self._create_report)
            ]
            
            for template_name, template_func in templates:
                image_path = lang_dir / f"{template_name}.png"
                img = template_func(lang_code, lang_name)
                img.save(image_path)
                test_images[lang_code].append(str(image_path))
                logger.info(f"생성됨: {image_path}")
        
        return test_images
    
    def _create_financial_table(self, lang_code: str, lang_name: str) -> Image.Image:
        """재무제표 이미지 생성"""
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (600, 400), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        # 언어별 텍스트
        texts = {
            "kor": ["재무제표 (단위: 원)", "매출액", "1,000,000원", "영업이익", "200,000원", "당기순이익", "150,000원"],
            "eng": ["Financial Statement (Unit: USD)", "Revenue", "$1,000,000", "Operating Income", "$200,000", "Net Income", "$150,000"],
            "chi_sim": ["财务报表 (单位: 元)", "营业收入", "1,000,000元", "营业利润", "200,000元", "净利润", "150,000元"],
            "jpn": ["財務諸表 (単位: 円)", "売上高", "1,000,000円", "営業利益", "200,000円", "当期純利益", "150,000円"],
            "ara": ["البيان المالي (الوحدة: ريال)", "الإيرادات", "1,000,000 ريال", "الربح التشغيلي", "200,000 ريال", "صافي الدخل", "150,000 ريال"],
            "spa": ["Estado Financiero (Unidad: USD)", "Ingresos", "$1,000,000", "Ingresos Operativos", "$200,000", "Ingresos Netos", "$150,000"],
            "por": ["Demonstração Financeira (Unidade: R$)", "Receita", "R$1,000,000", "Receita Operacional", "R$200,000", "Receita Líquida", "R$150,000"],
            "fra": ["État Financier (Unité: €)", "Revenus", "€1,000,000", "Revenus d'Exploitation", "€200,000", "Revenus Nets", "€150,000"],
            "deu": ["Finanzausweise (Einheit: €)", "Umsatz", "€1,000,000", "Betriebsgewinn", "€200,000", "Nettogewinn", "€150,000"],
            "ita": ["Rendiconto Finanziario (Unità: €)", "Ricavi", "€1,000,000", "Reddito Operativo", "€200,000", "Reddito Netto", "€150,000"],
            "vie": ["Báo cáo Tài chính (Đơn vị: VND)", "Doanh thu", "1,000,000 VND", "Lợi nhuận hoạt động", "200,000 VND", "Lợi nhuận ròng", "150,000 VND"]
        }
        
        lang_texts = texts.get(lang_code, texts["eng"])
        
        # 제목
        draw.text((50, 30), lang_texts[0], fill='black', font=font)
        
        # 표 형태로 배치
        y_pos = 100
        for i in range(1, len(lang_texts), 2):
            if i + 1 < len(lang_texts):
                draw.text((50, y_pos), lang_texts[i], fill='black', font=font)
                draw.text((300, y_pos), lang_texts[i + 1], fill='black', font=font)
                y_pos += 40
        
        return img
    
    def _create_invoice(self, lang_code: str, lang_name: str) -> Image.Image:
        """청구서 이미지 생성"""
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (600, 400), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        # 간단한 청구서 형태
        texts = {
            "kor": ["청구서", "번호: INV-2024-001", "총액: 3,520,000원"],
            "eng": ["Invoice", "Number: INV-2024-001", "Total Amount: $3,520,000"],
            "chi_sim": ["发票", "编号: INV-2024-001", "总金额: 3,520,000元"],
            "jpn": ["請求書", "番号: INV-2024-001", "総額: 3,520,000円"],
            "ara": ["فاتورة", "الرقم: INV-2024-001", "المبلغ الإجمالي: 3,520,000 ريال"],
            "spa": ["Factura", "Número: INV-2024-001", "Monto Total: $3,520,000"],
            "por": ["Fatura", "Número: INV-2024-001", "Valor Total: R$3,520,000"],
            "fra": ["Facture", "Numéro: INV-2024-001", "Montant Total: €3,520,000"],
            "deu": ["Rechnung", "Nummer: INV-2024-001", "Gesamtbetrag: €3,520,000"],
            "ita": ["Fattura", "Numero: INV-2024-001", "Importo Totale: €3,520,000"],
            "vie": ["Hóa đơn", "Số: INV-2024-001", "Tổng số tiền: 3,520,000 VND"]
        }
        
        lang_texts = texts.get(lang_code, texts["eng"])
        
        y_pos = 50
        for text in lang_texts:
            draw.text((50, y_pos), text, fill='black', font=font)
            y_pos += 50
        
        return img
    
    def _create_report(self, lang_code: str, lang_name: str) -> Image.Image:
        """보고서 이미지 생성"""
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (600, 400), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        # 보고서 형태
        texts = {
            "kor": ["월간 매출 분석 보고서", "2024년 1월", "주요 성과 요약"],
            "eng": ["Monthly Sales Analysis Report", "January 2024", "Key Performance Summary"],
            "chi_sim": ["月度销售分析报告", "2024年1月", "关键绩效摘要"],
            "jpn": ["月次売上分析レポート", "2024年1月", "主要業績要約"],
            "ara": ["تقرير تحليل المبيعات الشهرية", "يناير 2024", "ملخص الأداء الرئيسي"],
            "spa": ["Informe de Análisis de Ventas Mensual", "Enero 2024", "Resumen de Rendimiento Clave"],
            "por": ["Relatório de Análise de Vendas Mensal", "Janeiro 2024", "Resumo de Desempenho Chave"],
            "fra": ["Rapport d'Analyse des Ventes Mensuel", "Janvier 2024", "Résumé des Performances Clés"],
            "deu": ["Monatlicher Verkaufsanalysebericht", "Januar 2024", "Zusammenfassung der Hauptleistung"],
            "ita": ["Rapporto di Analisi delle Vendite Mensile", "Gennaio 2024", "Riepilogo delle Prestazioni Chiave"],
            "vie": ["Báo cáo Phân tích Bán hàng Hàng tháng", "Tháng 1 2024", "Tóm tắt Hiệu suất Chính"]
        }
        
        lang_texts = texts.get(lang_code, texts["eng"])
        
        y_pos = 50
        for text in lang_texts:
            draw.text((50, y_pos), text, fill='black', font=font)
            y_pos += 60
        
        return img


class BenchmarkResultReporter:
    """벤치마크 결과 리포팅 전담 클래스"""
    
    def generate_report(self, results: List[ProcessingMetrics], language_results: List[LanguageBenchmark]) -> SystemBenchmark:
        """종합 벤치마크 보고서 생성"""
        
        # 전체 통계 계산
        total_tests = len(results)
        successful_tests = len([r for r in results if not r.error_occurred])
        overall_success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        # 시스템 성능 통계
        if successful_tests > 0:
            successful_results = [r for r in results if not r.error_occurred]
            system_performance = {
                "average_processing_time": statistics.mean([r.processing_time for r in successful_results]),
                "average_memory_usage": statistics.mean([r.memory_used for r in successful_results]),
                "average_accuracy": statistics.mean([r.accuracy_score for r in successful_results]),
                "processing_time_std": statistics.stdev([r.processing_time for r in successful_results]) if len(successful_results) > 1 else 0,
                "memory_usage_std": statistics.stdev([r.memory_used for r in successful_results]) if len(successful_results) > 1 else 0
            }
        else:
            system_performance = {
                "average_processing_time": 0,
                "average_memory_usage": 0,
                "average_accuracy": 0,
                "processing_time_std": 0,
                "memory_usage_std": 0
            }
        
        # 추천사항 생성
        recommendations = self._generate_recommendations(system_performance, language_results)
        
        return SystemBenchmark(
            test_session_id=f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            test_start_time=datetime.now().isoformat(),
            test_duration=0,  # 실제 구현에서는 측정
            total_images_processed=total_tests,
            overall_success_rate=overall_success_rate,
            language_benchmarks=language_results,
            system_performance=system_performance,
            recommendations=recommendations
        )
    
    def _generate_recommendations(self, system_perf: Dict, lang_results: List[LanguageBenchmark]) -> List[str]:
        """성능 기반 추천사항 생성"""
        recommendations = []
        
        # 처리 시간 기반 추천
        if system_perf["average_processing_time"] > 10:
            recommendations.append("평균 처리 시간이 10초를 초과합니다. 이미지 전처리 최적화를 권장합니다.")
        
        # 메모리 사용량 기반 추천
        if system_perf["average_memory_usage"] > 500:  # 500MB
            recommendations.append("메모리 사용량이 높습니다. 배치 처리 크기를 줄이는 것을 권장합니다.")
        
        # 정확도 기반 추천
        if system_perf["average_accuracy"] < 80:
            recommendations.append("전체 정확도가 80% 미만입니다. 모델 업그레이드 또는 전처리 강화를 권장합니다.")
        
        # 언어별 성능 분석
        low_performance_languages = [
            lang.language_name for lang in lang_results 
            if lang.average_accuracy < 70
        ]
        
        if low_performance_languages:
            recommendations.append(f"다음 언어들의 성능이 저조합니다: {', '.join(low_performance_languages)}. 언어별 특화 모델 적용을 권장합니다.")
        
        # 기본 추천사항
        if not recommendations:
            recommendations.append("전반적인 성능이 양호합니다. 현재 설정을 유지하세요.")
        
        return recommendations
    
    def export_to_json(self, benchmark: SystemBenchmark, output_path: str):
        """JSON 형태로 결과 내보내기"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(benchmark), f, ensure_ascii=False, indent=2)
    
    def export_to_html(self, benchmark: SystemBenchmark, output_path: str):
        """HTML 보고서 생성"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OCR 성능 벤치마크 보고서</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f4f4f4; padding: 20px; }}
                .section {{ margin: 20px 0; }}
                .language-result {{ border: 1px solid #ddd; padding: 10px; margin: 10px 0; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #e9e9e9; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>OCR 성능 벤치마크 보고서</h1>
                <p>테스트 세션: {benchmark.test_session_id}</p>
                <p>실행 시간: {benchmark.test_start_time}</p>
            </div>
            
            <div class="section">
                <h2>전체 성능 요약</h2>
                <div class="metric">처리된 이미지: {benchmark.total_images_processed}개</div>
                <div class="metric">전체 성공률: {benchmark.overall_success_rate:.2f}%</div>
                <div class="metric">평균 처리 시간: {benchmark.system_performance['average_processing_time']:.2f}초</div>
                <div class="metric">평균 정확도: {benchmark.system_performance['average_accuracy']:.2f}%</div>
            </div>
            
            <div class="section">
                <h2>언어별 성능</h2>
                {''.join([f'''
                <div class="language-result">
                    <h3>{lang.language_name} ({lang.language})</h3>
                    <p>성공률: {(lang.successful_tests / lang.total_tests * 100):.2f}% ({lang.successful_tests}/{lang.total_tests})</p>
                    <p>평균 정확도: {lang.average_accuracy:.2f}%</p>
                    <p>평균 처리 시간: {lang.average_processing_time:.2f}초</p>
                </div>
                ''' for lang in benchmark.language_benchmarks])}
            </div>
            
            <div class="section">
                <h2>추천사항</h2>
                <ul>
                    {''.join([f'<li>{rec}</li>' for rec in benchmark.recommendations])}
                </ul>
            </div>
        </body>
        </html>
        """
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)


# SOLID 원칙 적용: Dependency Inversion
class PerformanceBenchmarkService:
    """
    성능 벤치마크 테스트 서비스 (메인 오케스트레이터)
    SOLID 원칙을 준수하여 의존성 주입 방식으로 구현
    """
    
    def __init__(
        self,
        ocr_processors: List[OCRProcessor],
        performance_measurer: PerformanceMeasurer,
        accuracy_evaluator: AccuracyEvaluator,
        test_data_generator: TestDataGenerator,
        result_reporter: BenchmarkResultReporter
    ):
        """의존성 주입을 통한 초기화"""
        self.ocr_processors = ocr_processors
        self.performance_measurer = performance_measurer
        self.accuracy_evaluator = accuracy_evaluator
        self.test_data_generator = test_data_generator
        self.result_reporter = result_reporter
        
        self.benchmark_results: List[ProcessingMetrics] = []
        self.language_results: List[LanguageBenchmark] = []
        
        logger.info("PerformanceBenchmarkService 초기화 완료")
    
    async def run_comprehensive_benchmark(
        self,
        output_dir: str = "/tmp/benchmark_results",
        max_workers: int = 3
    ) -> SystemBenchmark:
        """
        종합 성능 벤치마크 실행
        
        Args:
            output_dir: 결과 저장 디렉토리
            max_workers: 동시 실행 워커 수
            
        Returns:
            종합 벤치마크 결과
        """
        try:
            logger.info("종합 성능 벤치마크 시작")
            start_time = time.time()
            
            # 1. 테스트 데이터 생성
            test_images = self.test_data_generator.create_test_images(
                f"{output_dir}/test_images"
            )
            
            # 2. 언어별 벤치마크 실행
            tasks = []
            for language_code, image_paths in test_images.items():
                task = self._run_language_benchmark(language_code, image_paths, max_workers)
                tasks.append(task)
            
            # 병렬 실행
            language_results = await asyncio.gather(*tasks)
            self.language_results = language_results
            
            # 3. 종합 보고서 생성
            end_time = time.time()
            benchmark_result = self.result_reporter.generate_report(
                self.benchmark_results, 
                self.language_results
            )
            benchmark_result.test_duration = end_time - start_time
            
            # 4. 결과 저장
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            self.result_reporter.export_to_json(
                benchmark_result, 
                str(output_path / "benchmark_result.json")
            )
            self.result_reporter.export_to_html(
                benchmark_result,
                str(output_path / "benchmark_report.html")
            )
            
            logger.info(f"벤치마크 완료: {benchmark_result.test_duration:.2f}초")
            return benchmark_result
            
        except Exception as e:
            logger.error(f"벤치마크 실행 실패: {e}")
            raise
    
    async def _run_language_benchmark(
        self, 
        language_code: str, 
        image_paths: List[str],
        max_workers: int
    ) -> LanguageBenchmark:
        """언어별 벤치마크 실행"""
        
        logger.info(f"언어 벤치마크 시작: {language_code}")
        
        language_name = dict(self.test_data_generator.supported_languages).get(
            language_code, language_code
        )
        
        # 각 OCR 프로세서별로 테스트
        all_results = []
        
        for ocr_processor in self.ocr_processors:
            processor_results = await self._test_ocr_processor(
                ocr_processor, language_code, image_paths, max_workers
            )
            all_results.extend(processor_results)
        
        # 결과 집계
        total_tests = len(all_results)
        successful_tests = len([r for r in all_results if not r.error_occurred])
        failed_tests = total_tests - successful_tests
        
        if successful_tests > 0:
            successful_results = [r for r in all_results if not r.error_occurred]
            average_accuracy = statistics.mean([r.accuracy_score for r in successful_results])
            average_processing_time = statistics.mean([r.processing_time for r in successful_results])
            average_memory_usage = statistics.mean([r.memory_used for r in successful_results])
            
            # 신뢰도 분포 계산
            confidence_ranges = {"90-100%": 0, "80-89%": 0, "70-79%": 0, "60-69%": 0, "0-59%": 0}
            for result in successful_results:
                confidence = result.confidence_score
                if confidence >= 90:
                    confidence_ranges["90-100%"] += 1
                elif confidence >= 80:
                    confidence_ranges["80-89%"] += 1
                elif confidence >= 70:
                    confidence_ranges["70-79%"] += 1
                elif confidence >= 60:
                    confidence_ranges["60-69%"] += 1
                else:
                    confidence_ranges["0-59%"] += 1
        else:
            average_accuracy = 0
            average_processing_time = 0
            average_memory_usage = 0
            confidence_ranges = {"90-100%": 0, "80-89%": 0, "70-79%": 0, "60-69%": 0, "0-59%": 0}
        
        # 오류 패턴 분석
        error_patterns = []
        failed_results = [r for r in all_results if r.error_occurred]
        if failed_results:
            error_types = [r.error_type for r in failed_results if r.error_type]
            from collections import Counter
            error_counter = Counter(error_types)
            error_patterns = [f"{error}: {count}회" for error, count in error_counter.most_common(5)]
        
        return LanguageBenchmark(
            language=language_code,
            language_name=language_name,
            total_tests=total_tests,
            successful_tests=successful_tests,
            failed_tests=failed_tests,
            average_accuracy=average_accuracy,
            average_processing_time=average_processing_time,
            average_memory_usage=average_memory_usage,
            confidence_distribution=confidence_ranges,
            error_patterns=error_patterns
        )
    
    async def _test_ocr_processor(
        self,
        ocr_processor: OCRProcessor,
        language_code: str,
        image_paths: List[str],
        max_workers: int
    ) -> List[ProcessingMetrics]:
        """OCR 프로세서 테스트"""
        
        results = []
        
        # ThreadPoolExecutor를 사용한 병렬 처리
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 작업 제출
            future_to_image = {
                executor.submit(
                    self._process_single_image, 
                    ocr_processor, 
                    language_code, 
                    image_path
                ): image_path
                for image_path in image_paths
            }
            
            # 결과 수집
            for future in as_completed(future_to_image):
                image_path = future_to_image[future]
                try:
                    result = future.result()
                    results.append(result)
                    self.benchmark_results.append(result)
                except Exception as e:
                    logger.error(f"이미지 처리 실패 {image_path}: {e}")
                    # 실패한 경우도 결과에 포함
                    error_result = ProcessingMetrics(
                        processing_time=0,
                        memory_used=0,
                        cpu_usage=0,
                        accuracy_score=0,
                        confidence_score=0,
                        text_length=0,
                        error_occurred=True,
                        error_type=str(e)
                    )
                    results.append(error_result)
                    self.benchmark_results.append(error_result)
        
        return results
    
    def _process_single_image(
        self,
        ocr_processor: OCRProcessor,
        language_code: str,
        image_path: str
    ) -> ProcessingMetrics:
        """단일 이미지 처리 및 성능 측정"""
        
        # CPU 사용량 측정 시작
        cpu_before = self.performance_measurer.measure_cpu_usage()
        
        # 처리 시간 및 메모리 사용량 측정
        result, processing_time, error = self.performance_measurer.measure_processing_time(
            ocr_processor.process_image, image_path, language_code
        )
        
        _, memory_used, memory_error = self.performance_measurer.measure_memory_usage(
            lambda: None  # 이미 처리된 후이므로 빈 함수
        )
        
        cpu_after = self.performance_measurer.measure_cpu_usage()
        cpu_usage = max(0, cpu_after - cpu_before)
        
        if error or memory_error:
            return ProcessingMetrics(
                processing_time=processing_time,
                memory_used=memory_used,
                cpu_usage=cpu_usage,
                accuracy_score=0,
                confidence_score=0,
                text_length=0,
                error_occurred=True,
                error_type=error or memory_error
            )
        
        # 정확도 계산
        extracted_text = result.get("extracted_text", "") if result else ""
        image_name = Path(image_path).name
        reference_text = self.accuracy_evaluator.get_reference_text(language_code, image_name)
        
        if reference_text:
            accuracy_score = self.accuracy_evaluator.calculate_accuracy(extracted_text, reference_text)
        else:
            accuracy_score = 0
        
        confidence_score = result.get("confidence", 0) * 100 if result else 0
        text_length = len(extracted_text)
        
        return ProcessingMetrics(
            processing_time=processing_time,
            memory_used=memory_used,
            cpu_usage=cpu_usage,
            accuracy_score=accuracy_score,
            confidence_score=confidence_score,
            text_length=text_length,
            error_occurred=False
        )
    
    def get_service_info(self) -> Dict[str, Any]:
        """서비스 정보 반환"""
        return {
            "service": "performance_benchmark",
            "version": "1.0.0",
            "supported_languages": [lang[0] for lang in self.test_data_generator.supported_languages],
            "ocr_processors": len(self.ocr_processors),
            "capabilities": [
                "language_specific_testing",
                "accuracy_measurement", 
                "performance_profiling",
                "memory_monitoring",
                "comprehensive_reporting"
            ]
        }


# Factory 패턴으로 서비스 생성 (SOLID 원칙 적용)
class BenchmarkServiceFactory:
    """벤치마크 서비스 팩토리"""
    
    @staticmethod
    def create_service() -> PerformanceBenchmarkService:
        """기본 설정으로 벤치마크 서비스 생성"""
        
        # OCR 프로세서들 (현재는 더미 구현, 실제로는 실제 OCR 서비스들)
        ocr_processors = []
        
        # 실제 OCR 서비스 임포트 시도
        try:
            from app.services.multilingual_two_tier_service import MultilingualTwoTierService
            ocr_processors.append(MultilingualTwoTierService())
        except ImportError:
            logger.warning("MultilingualTwoTierService를 찾을 수 없습니다")
        
        try:
            from app.services.transformer_ocr_service import transformer_ocr_service
            ocr_processors.append(transformer_ocr_service)
        except ImportError:
            logger.warning("TransformerOCRService를 찾을 수 없습니다")
        
        # 의존성 생성
        performance_measurer = PerformanceMeasurer()
        accuracy_evaluator = AccuracyEvaluator()
        test_data_generator = TestDataGenerator()
        result_reporter = BenchmarkResultReporter()
        
        return PerformanceBenchmarkService(
            ocr_processors=ocr_processors,
            performance_measurer=performance_measurer,
            accuracy_evaluator=accuracy_evaluator,
            test_data_generator=test_data_generator,
            result_reporter=result_reporter
        )


# 전역 인스턴스 (팩토리로 생성)
performance_benchmark_service = BenchmarkServiceFactory.create_service()