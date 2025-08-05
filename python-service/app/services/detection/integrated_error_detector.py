"""
Integrated Error Detector
통합 오류 감지 서비스 - SOLID 원칙 적용
"""

from typing import List, Dict, Any, Optional
from app.core.interfaces import (
    IErrorDetector,
    IProgressReporter,
    ExcelError,
    ProcessingTier,
)
from app.core.types import (
    FileAnalysisResult,
    ErrorInfo,
    CellInfo,
    AnalysisSummary,
    MultiCellAnalysis,
    SheetSummary,
)
from app.services.detection.strategies.enhanced_formula_detector import (
    EnhancedFormulaDetector,
)
from app.services.detection.strategies.data_quality_detector import DataQualityDetector
from app.services.detection.strategies.structure_detector import StructureDetector
from app.services.detection.strategies.vba_error_detector import VBAErrorDetector
from app.services.workbook_loader import OpenpyxlWorkbookLoader
from app.services.detection.multi_cell_analyzer import MultiCellAnalyzer
from app.core.excel_utils import ExcelUtils
from app.core.integrated_cache import integrated_cache, cache_result
import asyncio
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class IntegratedErrorDetector:
    """통합 오류 감지 서비스"""

    # 셀 주소 패턴 컴파일 (성능 최적화)
    CELL_PATTERN = re.compile(r"([A-Z]+)(\d+)")

    # 성능 최적화 설정
    BATCH_SIZE = 100  # 셀 배치 처리 크기
    MAX_CONCURRENT_DETECTORS = 4  # 동시 실행 감지기 수
    CACHE_TTL = 3600  # 캐시 TTL (1시간)

    def __init__(self, progress_reporter: Optional[IProgressReporter] = None):
        self.progress_reporter = progress_reporter

        # 감지 전략들 (Open/Closed Principle)
        self.detectors: List[IErrorDetector] = [
            EnhancedFormulaDetector(),  # Use enhanced detector instead
            DataQualityDetector(),
            StructureDetector(),
            VBAErrorDetector(),
        ]

        # 워크북 로더 사용 (순환 참조 방지)
        self.workbook_loader = OpenpyxlWorkbookLoader()

        # 멀티 셀 분석기
        self.multi_cell_analyzer = MultiCellAnalyzer()

    # @PerformanceMonitor.monitor_request  # TODO: Fix decorator
    @cache_result(prefix="error_detection", ttl=3600)  # 1 hour cache
    async def detect_all_errors(self, file_path: str) -> FileAnalysisResult:
        """파일의 모든 오류 감지"""

        # 통합 캐시에서 결과 확인
        file_id = self._extract_file_id(file_path)
        if file_id:
            cached_result = await integrated_cache.get_analysis(file_id)
            if cached_result:
                logger.info(f"캐시에서 오류 감지 결과 반환: {file_path}")
                # PerformanceMonitor.record_cache_access("error_detection", hit=True)  # TODO: Fix method
                return cached_result

        # PerformanceMonitor.record_cache_access("error_detection", hit=False)  # TODO: Fix method

        # TODO: Fix PerformanceMonitor.monitor_operation
        # with PerformanceMonitor.monitor_operation("error_detection", file_path=file_path):
        try:
            # 워크북 로드
            workbook = await self._load_workbook(file_path)

            # 진행 상황 보고
            if self.progress_reporter:
                await self.progress_reporter.start_task("오류 감지", 100)
                await self.progress_reporter.report_progress(0, 100, "오류 감지 시작")

            start_time = datetime.now()

            # 병렬로 모든 감지기 실행 (최적화)
            all_errors = await self._run_detectors_parallel_optimized(workbook)

            # 중복 제거 및 정렬
            unique_errors = self._deduplicate_errors(all_errors)
            sorted_errors = self._sort_errors_by_priority(unique_errors)

            # 타입화된 결과 생성
            result: FileAnalysisResult = {
                "status": "success",
                "file_id": file_id or self._generate_file_id(file_path),
                "file_path": file_path,
                "filename": file_path.split("/")[-1],
                "timestamp": datetime.now().isoformat(),
                "analysis_time": (datetime.now() - start_time).total_seconds(),
                "errors": [
                    self._convert_to_error_info(error) for error in sorted_errors
                ],
                "summary": self._create_summary(sorted_errors),
                "sheets": await self._get_sheet_summaries(workbook),
                "tier_used": ProcessingTier.CACHE.value,
            }

            # 통합 캐시에 저장 (계층적 캐싱)
            if file_id:
                # 전체 분석 결과 캐싱
                await integrated_cache.set_analysis(file_id, result, ttl=self.CACHE_TTL)

                # 오류 목록 캐싱
                await integrated_cache.set_errors(
                    file_id, sorted_errors, ttl=self.CACHE_TTL
                )

                # 요약 정보는 더 오래 캐싱 (분석 결과보다 작고 자주 조회됨)
                await integrated_cache.set(
                    f"summary:{file_id}", result["summary"], ttl=self.CACHE_TTL * 2
                )

            # 진행 상황 완료
            if self.progress_reporter:
                await self.progress_reporter.report_progress(100, 100, "오류 감지 완료")
                await self.progress_reporter.complete_task("오류 감지", result)

            return result

        except FileNotFoundError:
            logger.error(f"파일을 찾을 수 없음: {file_path}")
            return {
                "status": "error",
                "message": f"파일을 찾을 수 없습니다: {file_path}",
                "file_path": file_path,
                "timestamp": datetime.now().isoformat(),
            }
        except PermissionError:
            logger.error(f"파일 접근 권한 없음: {file_path}")
            return {
                "status": "error",
                "message": f"파일 접근 권한이 없습니다: {file_path}",
                "file_path": file_path,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"오류 감지 실패: {str(e)}", exc_info=True)
            if self.progress_reporter:
                await self.progress_reporter.report_error(e)

            return {
                "status": "error",
                "message": str(e),
                "file_path": file_path,
                "timestamp": datetime.now().isoformat(),
            }

    async def detect_cell_error(
        self, file_path: str, sheet: str, cell: str
    ) -> Optional[ExcelError]:
        """특정 셀의 오류 감지"""
        try:
            workbook = await self._load_workbook(file_path)
            worksheet = workbook[sheet]
            cell_obj = worksheet[cell]

            # 각 감지기로 셀 검사
            for detector in self.detectors:
                if hasattr(detector, "detect_cell"):
                    errors = await detector.detect_cell(cell_obj, sheet)
                    if errors:
                        return errors[0]  # 첫 번째 오류 반환

            return None

        except Exception as e:
            logger.error(f"셀 오류 감지 실패: {str(e)}")
            return None

    async def detect_multi_cell_errors(
        self, file_path: str, cells: List[CellInfo]
    ) -> MultiCellAnalysis:
        """여러 셀의 오류 감지 및 패턴 분석 - 배치 처리 최적화

        Args:
            file_path: Excel 파일 경로
            cells: 분석할 셀 정보 리스트
                [{"sheet": "Sheet1", "address": "A1", "value": ..., "formula": ...}, ...]

        Returns:
            Dict containing individual cell errors and pattern analysis
        """
        try:
            workbook = await self._load_workbook(file_path)

            # 배치 처리를 위한 셀 그룹화
            if len(cells) > self.BATCH_SIZE:
                # 대량의 셀은 배치로 처리
                cell_analysis_results, individual_errors = (
                    await self._process_cells_in_batches(workbook, cells)
                )
            else:
                # 소량의 셀은 기존 방식으로 처리
                cell_analysis_results, individual_errors = (
                    await self._process_cells_sequential(workbook, cells)
                )

            # 패턴 분석
            pattern_analysis = await self.multi_cell_analyzer.analyze_cell_patterns(
                cells, individual_errors
            )

            # 교차 셀 문제 감지
            cross_cell_issues = await self.multi_cell_analyzer.detect_cross_cell_issues(
                cells, workbook
            )

            # 결과 반환
            result: MultiCellAnalysis = {
                "individual_cells": cell_analysis_results,
                "total_errors": len(individual_errors),
                "pattern_analysis": pattern_analysis,
                "cross_cell_issues": cross_cell_issues,
                "summary": self.multi_cell_analyzer.create_multi_cell_summary(
                    cell_analysis_results, pattern_analysis
                ),
            }
            return result

        except Exception as e:
            logger.error(f"멀티 셀 오류 감지 실패: {str(e)}")
            result: MultiCellAnalysis = {
                "individual_cells": [],
                "total_errors": 0,
                "pattern_analysis": {
                    "patterns": [],
                    "summary": "",
                    "has_insights": False,
                    "total_patterns": 0,
                },
                "cross_cell_issues": [],
                "summary": {"error": str(e)},
            }
            return result

    async def _load_workbook(self, file_path: str) -> Any:
        """워크북 로드"""
        return await self.workbook_loader.load_workbook(file_path)

    async def _run_detectors_parallel(self, workbook: Any) -> List[ExcelError]:
        """병렬로 감지기 실행 - 기본 방법"""
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

    async def _run_detectors_parallel_optimized(
        self, workbook: Any
    ) -> List[ExcelError]:
        """병렬로 감지기 실행 - 최적화 버전"""
        # Semaphore로 동시 실행 제한
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DETECTORS)
        all_errors = []
        error_lock = asyncio.Lock()

        async def run_detector_with_limit(
            detector: IErrorDetector, index: int, total: int
        ):
            async with semaphore:
                try:
                    if self.progress_reporter:
                        progress = int((index / total) * 100)
                        await self.progress_reporter.report_progress(
                            progress, 100, f"{detector.__class__.__name__} 실행 중"
                        )

                    # 감지기 실행
                    errors = await detector.detect(workbook)

                    # 결과를 안전하게 추가
                    async with error_lock:
                        all_errors.extend(errors)

                except Exception as e:
                    logger.error(
                        f"{detector.__class__.__name__} 오류: {str(e)}", exc_info=True
                    )
                    if self.progress_reporter:
                        await self.progress_reporter.report_error(e)

        # 모든 감지기 비동기 실행
        tasks = [
            run_detector_with_limit(detector, i, len(self.detectors))
            for i, detector in enumerate(self.detectors)
        ]

        await asyncio.gather(*tasks)

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
        priority_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        return sorted(
            errors,
            key=lambda e: (
                priority_map.get(e.severity, 4),
                e.sheet,
                self._cell_to_row_col(e.cell),
            ),
        )

    def _cell_to_row_col(self, cell: str) -> tuple:
        """셀 주소를 행, 열로 변환 (정렬용)"""
        return ExcelUtils.cell_to_row_col(cell)

    def _generate_file_id(self, file_path: str) -> str:
        """파일 ID 생성"""
        import hashlib

        return hashlib.md5(file_path.encode()).hexdigest()[:16]

    def _create_error_result(self, file_path: str, message: str) -> FileAnalysisResult:
        """에러 결과 생성"""
        return {
            "status": "error",
            "file_id": self._generate_file_id(file_path),
            "file_path": file_path,
            "filename": file_path.split("/")[-1],
            "timestamp": datetime.now().isoformat(),
            "analysis_time": 0,
            "errors": [],
            "summary": self._create_empty_summary(),
            "sheets": {},
            "tier_used": ProcessingTier.ERROR.value,
        }

    def _convert_to_error_info(self, error: ExcelError) -> ErrorInfo:
        """에러 정보 변환"""
        return {
            "id": error.id,
            "type": error.type,
            "severity": error.severity,
            "cell": error.cell,
            "sheet": error.sheet,
            "message": error.message,
            "is_auto_fixable": error.is_auto_fixable,
            "suggested_fix": error.suggested_fix,
            "confidence": getattr(error, "confidence", None),
            "details": getattr(error, "details", None),
        }

    async def _get_sheet_summaries(self, workbook: Any) -> Dict[str, SheetSummary]:
        """시트 요약 생성"""
        summaries = {}

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]

            # 데이터 타입 카운트
            data_types: Dict[str, int] = {
                "numbers": 0,
                "text": 0,
                "formulas": 0,
                "dates": 0,
                "empty": 0,
            }

            non_empty_cells = 0
            formulas_count = 0

            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value is not None:
                        non_empty_cells += 1

                        if cell.data_type == "f":
                            formulas_count += 1
                            data_types["formulas"] += 1
                        elif isinstance(cell.value, (int, float)):
                            data_types["numbers"] += 1
                        elif isinstance(cell.value, str):
                            data_types["text"] += 1
                        elif cell.is_date:
                            data_types["dates"] += 1
                    else:
                        data_types["empty"] += 1

            summaries[sheet_name] = {
                "name": sheet_name,
                "rows": sheet.max_row,
                "columns": sheet.max_column,
                "non_empty_cells": non_empty_cells,
                "formulas_count": formulas_count,
                "errors_count": 0,  # Will be updated later
                "data_types": data_types,
            }

        return summaries

    def _create_empty_summary(self) -> AnalysisSummary:
        """빈 요약 생성"""
        return {
            "total_sheets": 0,
            "total_rows": 0,
            "total_cells_with_data": 0,
            "total_errors": 0,
            "has_errors": False,
            "error_types": {},
            "auto_fixable_count": 0,
            "auto_fixable_percentage": 0,
            "has_charts": False,
            "has_pivot_tables": False,
            "most_common_error_type": None,
        }

    def _create_summary(self, errors: List[ExcelError]) -> AnalysisSummary:
        """오류 요약 생성"""
        # 오류 타입별 카운트
        error_types = {}
        auto_fixable_count = 0

        for error in errors:
            error_types[error.type] = error_types.get(error.type, 0) + 1
            if error.is_auto_fixable:
                auto_fixable_count += 1

        # 가장 많은 오류 타입
        most_common_error_type = None
        if error_types:
            most_common_error_type = max(error_types.items(), key=lambda x: x[1])[0]

        # 자동 수정 가능 비율
        auto_fixable_percentage = 0
        if errors:
            auto_fixable_percentage = round((auto_fixable_count / len(errors)) * 100, 2)

        return {
            "total_sheets": 0,  # Will be updated by caller
            "total_rows": 0,  # Will be updated by caller
            "total_cells_with_data": 0,  # Will be updated by caller
            "total_errors": len(errors),
            "has_errors": len(errors) > 0,
            "error_types": error_types,
            "auto_fixable_count": auto_fixable_count,
            "auto_fixable_percentage": auto_fixable_percentage,
            "has_charts": False,  # TODO: Implement chart detection
            "has_pivot_tables": False,  # TODO: Implement pivot table detection
            "most_common_error_type": most_common_error_type,
        }

    def _extract_file_id(self, file_path: str) -> Optional[str]:
        """파일 경로에서 파일 ID 추출"""
        # 예: /tmp/excel_file_123.xlsx -> 123
        import re

        match = re.search(r"_(\d+)\.xlsx$", file_path)
        if match:
            return match.group(1)
        return None

    def add_detector(self, detector: IErrorDetector):
        """새로운 감지기 추가 (Open/Closed Principle)"""
        self.detectors.append(detector)
        logger.info(f"새로운 감지기 추가: {detector.__class__.__name__}")

    def remove_detector(self, detector_type: type):
        """감지기 제거"""
        self.detectors = [d for d in self.detectors if not isinstance(d, detector_type)]

    async def clear_cache(self):
        """캐시 초기화"""
        # 특정 패턴의 캐시만 삭제
        count = await integrated_cache.clear_pattern("error_detection:")
        logger.info(f"오류 감지 캐시 초기화: {count}개 항목 삭제")

    async def detect_errors_streaming(self, file_path: str, callback=None):
        """대용량 파일을 위한 스트리밍 오류 감지"""
        file_id = self._extract_file_id(file_path) or self._generate_file_id(file_path)

        try:
            workbook = await self._load_workbook(file_path)
            total_sheets = len(workbook.sheetnames)
            errors_found = []

            # 시트별로 스트리밍 처리
            for sheet_index, sheet_name in enumerate(workbook.sheetnames):
                sheet = workbook[sheet_name]
                sheet_errors = []

                # 진행률 계산
                progress = int((sheet_index / total_sheets) * 100)

                # 각 감지기 실행
                for detector in self.detectors:
                    try:
                        # 시트 단위로 감지
                        if hasattr(detector, "detect_sheet"):
                            errors = await detector.detect_sheet(sheet, sheet_name)
                            sheet_errors.extend(errors)
                    except Exception as e:
                        logger.warning(f"시트 {sheet_name} 감지 오류: {str(e)}")

                # 콜백 호출 (중간 결과 전달)
                if callback:
                    await callback(
                        {
                            "sheet": sheet_name,
                            "progress": progress,
                            "errors": sheet_errors,
                            "sheet_index": sheet_index,
                            "total_sheets": total_sheets,
                        }
                    )

                errors_found.extend(sheet_errors)

            # 최종 결과 반환
            return {
                "status": "success",
                "file_id": file_id,
                "errors": errors_found,
                "streaming": True,
            }

        except Exception as e:
            logger.error(f"스트리밍 오류 감지 실패: {str(e)}")
            raise

    async def _process_cells_in_batches(
        self, workbook: Any, cells: List[CellInfo]
    ) -> tuple:
        """대량 셀을 배치로 처리 - 성능 최적화"""
        all_results = []
        all_errors = []

        # 세마포어로 동시 처리 제한
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DETECTORS)

        async def process_batch(batch: List[CellInfo]):
            async with semaphore:
                results, errors = await self._process_cells_sequential(workbook, batch)
                return results, errors

        # 배치 생성
        batches = [
            cells[i : i + self.BATCH_SIZE]
            for i in range(0, len(cells), self.BATCH_SIZE)
        ]

        # 배치 병렬 처리
        batch_tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*batch_tasks)

        # 결과 통합
        for results, errors in batch_results:
            all_results.extend(results)
            all_errors.extend(errors)

        return all_results, all_errors

    async def _process_cells_sequential(
        self, workbook: Any, cells: List[CellInfo]
    ) -> tuple:
        """셀 순차 처리 - 기본 방법"""
        cell_analysis_results = []
        individual_errors = []

        for cell_info in cells:
            sheet_name = cell_info.get("sheet", "Sheet1")
            cell_address = cell_info.get("address")

            try:
                worksheet = workbook[sheet_name]
                cell_obj = worksheet[cell_address]

                # 셀별 오류 검사
                cell_errors = []
                for detector in self.detectors:
                    if hasattr(detector, "check_cell_formula"):
                        # FormulaErrorDetector의 경우
                        errors = await detector.check_cell_formula(cell_obj, sheet_name)
                        cell_errors.extend(errors)

                # 셀 분석 결과 저장
                cell_result = {
                    "address": cell_address,
                    "sheet": sheet_name,
                    "value": cell_info.get("value"),
                    "formula": cell_info.get("formula"),
                    "errors": [
                        self._convert_to_error_info(error) for error in cell_errors
                    ],
                    "has_errors": len(cell_errors) > 0,
                }

                cell_analysis_results.append(cell_result)
                individual_errors.extend(cell_errors)

            except Exception as e:
                logger.warning(f"셀 {cell_address} 분석 실패: {str(e)}")
                cell_analysis_results.append(
                    {"address": cell_address, "sheet": sheet_name, "error": str(e)}
                )

        return cell_analysis_results, individual_errors
