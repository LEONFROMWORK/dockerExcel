"""
Integrated Error Detector
통합 오류 감지 서비스 - SOLID 원칙 적용
"""

from typing import List, Dict, Any, Optional
from app.core.interfaces import (
    IErrorDetector, IProgressReporter, ExcelError, 
    ExcelErrorType, ProcessingTier
)
from app.services.detection.strategies.formula_error_detector import FormulaErrorDetector
from app.services.detection.strategies.data_quality_detector import DataQualityDetector
from app.services.detection.strategies.structure_detector import StructureDetector
from app.services.detection.strategies.vba_error_detector import VBAErrorDetector
from app.services.workbook_loader import OpenpyxlWorkbookLoader
from app.core.cache import cached, ExcelAnalysisCache, CACHE_TTL
from app.core.monitoring import PerformanceMonitor, AnalysisMetrics
import asyncio
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class IntegratedErrorDetector:
    """통합 오류 감지 서비스"""
    
    # 셀 주소 패턴 컴파일 (성능 최적화)
    CELL_PATTERN = re.compile(r'([A-Z]+)(\d+)')
    
    def __init__(self, progress_reporter: Optional[IProgressReporter] = None):
        self.progress_reporter = progress_reporter
        
        # 감지 전략들 (Open/Closed Principle)
        self.detectors: List[IErrorDetector] = [
            FormulaErrorDetector(),
            DataQualityDetector(),
            StructureDetector(),
            VBAErrorDetector()
        ]
        
        # 워크북 로더 사용 (순환 참조 방지)
        self.workbook_loader = OpenpyxlWorkbookLoader()
        
        # 캐시 (성능 최적화)
        self._cache = {}
        # 설정에서 값 가져오기
        from app.core.config import settings
        self._cache_ttl = settings.EXCEL_CACHE_TTL
    
    @PerformanceMonitor.monitor_request
    @cached(prefix="error_detection", ttl=CACHE_TTL['MEDIUM'])
    async def detect_all_errors(self, file_path: str) -> Dict[str, Any]:
        """파일의 모든 오류 감지"""
        
        # 캐시된 결과 확인
        cached_result = ExcelAnalysisCache.get_cached_analysis(file_path, "error_detection")
        if cached_result:
            logger.info(f"캐시에서 오류 감지 결과 반환: {file_path}")
            PerformanceMonitor.record_cache_access("error_detection", hit=True)
            return cached_result
        
        PerformanceMonitor.record_cache_access("error_detection", hit=False)
        
        with PerformanceMonitor.monitor_operation("error_detection", file_path=file_path):
            try:
                # 워크북 로드
                workbook = await self._load_workbook(file_path)
            
                # 진행 상황 보고
                if self.progress_reporter:
                    await self.progress_reporter.report_progress(0, 100, "오류 감지 시작")
                
                start_time = datetime.now()
                
                # 병렬로 모든 감지기 실행
                all_errors = await self._run_detectors_parallel(workbook)
                
                # 중복 제거 및 정렬
                unique_errors = self._deduplicate_errors(all_errors)
                sorted_errors = self._sort_errors_by_priority(unique_errors)
                
                # 결과 생성
                result = {
                    'status': 'success',
                    'file_path': file_path,
                    'timestamp': datetime.now().isoformat(),
                    'analysis_time': (datetime.now() - start_time).total_seconds(),
                    'errors': [error.__dict__ for error in sorted_errors],
                    'summary': self._create_summary(sorted_errors),
                    'tier_used': ProcessingTier.CACHE.value
                }
                
                # 캐시 저장
                cache_key = self._get_cache_key(file_path)
                self._cache[cache_key] = {
                    'data': result,
                    'timestamp': datetime.now()
                }
                
                # 진행 상황 완료
                if self.progress_reporter:
                    await self.progress_reporter.report_progress(100, 100, "오류 감지 완료")
                
                return result
                
            except FileNotFoundError as e:
                logger.error(f"파일을 찾을 수 없음: {file_path}")
                return {
                    'status': 'error',
                    'message': f"파일을 찾을 수 없습니다: {file_path}",
                    'file_path': file_path,
                    'timestamp': datetime.now().isoformat()
                }
            except PermissionError as e:
                logger.error(f"파일 접근 권한 없음: {file_path}")
                return {
                    'status': 'error',
                    'message': f"파일 접근 권한이 없습니다: {file_path}",
                    'file_path': file_path,
                    'timestamp': datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"오류 감지 실패: {str(e)}", exc_info=True)
                if self.progress_reporter:
                    await self.progress_reporter.report_error(e)
                
                return {
                    'status': 'error',
                    'message': str(e),
                    'file_path': file_path,
                    'timestamp': datetime.now().isoformat()
                }
    
    async def detect_cell_error(self, file_path: str, sheet: str, cell: str) -> Optional[ExcelError]:
        """특정 셀의 오류 감지"""
        try:
            workbook = await self._load_workbook(file_path)
            worksheet = workbook[sheet]
            cell_obj = worksheet[cell]
            
            # 각 감지기로 셀 검사
            for detector in self.detectors:
                if hasattr(detector, 'detect_cell'):
                    errors = await detector.detect_cell(cell_obj, sheet)
                    if errors:
                        return errors[0]  # 첫 번째 오류 반환
            
            return None
            
        except Exception as e:
            logger.error(f"셀 오류 감지 실패: {str(e)}")
            return None
    
    async def _load_workbook(self, file_path: str) -> Any:
        """워크북 로드"""
        return await self.workbook_loader.load_workbook(file_path)
    
    async def _run_detectors_parallel(self, workbook: Any) -> List[ExcelError]:
        """병렬로 감지기 실행"""
        tasks = []
        total_detectors = len(self.detectors)
        
        for i, detector in enumerate(self.detectors):
            # 각 감지기에 대한 진행 상황 보고
            async def run_detector(det: IErrorDetector, index: int) -> List[ExcelError]:
                if self.progress_reporter:
                    progress = int((index / total_detectors) * 100)
                    await self.progress_reporter.report_progress(
                        progress, 100, f"{det.__class__.__name__} 실행 중"
                    )
                
                return await det.detect(workbook)
            
            tasks.append(run_detector(detector, i))
        
        # 모든 감지기 결과 수집
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 오류 결합
        all_errors = []
        for result in results:
            if isinstance(result, list):
                all_errors.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"감지기 오류: {str(result)}", exc_info=True)
        
        return all_errors
    
    def _deduplicate_errors(self, errors: List[ExcelError]) -> List[ExcelError]:
        """중복 오류 제거"""
        seen = set()
        unique_errors = []
        
        for error in errors:
            key = f"{error.sheet}_{error.cell}_{error.type}"
            if key not in seen:
                seen.add(key)
                unique_errors.append(error)
        
        return unique_errors
    
    def _sort_errors_by_priority(self, errors: List[ExcelError]) -> List[ExcelError]:
        """우선순위별 정렬"""
        priority_map = {
            'critical': 0,
            'high': 1,
            'medium': 2,
            'low': 3
        }
        
        return sorted(errors, key=lambda e: (
            priority_map.get(e.severity, 4),
            e.sheet,
            self._cell_to_row_col(e.cell)
        ))
    
    def _cell_to_row_col(self, cell: str) -> tuple:
        """셀 주소를 행, 열로 변환 (정렬용)"""
        match = self.CELL_PATTERN.match(cell)
        if match:
            col = sum((ord(c) - ord('A') + 1) * (26 ** i) 
                     for i, c in enumerate(reversed(match.group(1))))
            row = int(match.group(2))
            return (row, col)
        return (0, 0)
    
    def _create_summary(self, errors: List[ExcelError]) -> Dict[str, Any]:
        """오류 요약 생성"""
        summary = {
            'total_errors': len(errors),
            'by_type': {},
            'by_severity': {},
            'by_sheet': {},
            'auto_fixable': 0
        }
        
        for error in errors:
            # 타입별 집계
            summary['by_type'][error.type] = summary['by_type'].get(error.type, 0) + 1
            
            # 심각도별 집계
            summary['by_severity'][error.severity] = summary['by_severity'].get(error.severity, 0) + 1
            
            # 시트별 집계
            summary['by_sheet'][error.sheet] = summary['by_sheet'].get(error.sheet, 0) + 1
            
            # 자동 수정 가능 개수
            if error.is_auto_fixable:
                summary['auto_fixable'] += 1
        
        # 가장 많은 오류 타입
        if summary['by_type']:
            summary['most_common_type'] = max(summary['by_type'].items(), key=lambda x: x[1])[0]
        
        # 자동 수정 가능 비율
        if errors:
            summary['auto_fixable_percentage'] = round(
                (summary['auto_fixable'] / len(errors)) * 100, 2
            )
        
        return summary
    
    def _get_cache_key(self, file_path: str) -> str:
        """캐시 키 생성"""
        import hashlib
        return hashlib.md5(file_path.encode()).hexdigest()
    
    def _is_cache_valid(self, cached_data: Dict) -> bool:
        """캐시 유효성 확인"""
        if 'timestamp' not in cached_data:
            return False
        
        age = (datetime.now() - cached_data['timestamp']).total_seconds()
        return age < self._cache_ttl
    
    def add_detector(self, detector: IErrorDetector):
        """새로운 감지기 추가 (Open/Closed Principle)"""
        self.detectors.append(detector)
        logger.info(f"새로운 감지기 추가: {detector.__class__.__name__}")
    
    def remove_detector(self, detector_type: type):
        """감지기 제거"""
        self.detectors = [d for d in self.detectors if not isinstance(d, detector_type)]
    
    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()
        logger.info("오류 감지 캐시 초기화됨")