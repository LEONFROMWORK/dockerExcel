"""
Enhanced Integrated Error Detector Tests
통합 오류 감지기 향상된 테스트
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.core.interfaces import ExcelError
from app.core.types import CellInfo
import asyncio


class TestIntegratedErrorDetectorEnhanced:
    """향상된 IntegratedErrorDetector 테스트"""

    @pytest.fixture
    def mock_progress_reporter(self):
        """모의 진행 상황 보고기"""
        reporter = MagicMock()
        reporter.report_progress = AsyncMock()
        reporter.report_error = AsyncMock()
        reporter.start_task = AsyncMock()
        reporter.complete_task = AsyncMock()
        return reporter

    @pytest.fixture
    def detector(self, mock_progress_reporter):
        """감지기 인스턴스"""
        with patch(
            "app.services.detection.integrated_error_detector.integrated_cache"
        ) as mock_cache:
            mock_cache.get_analysis = AsyncMock(return_value=None)
            mock_cache.set_analysis = AsyncMock()
            mock_cache.set_errors = AsyncMock()
            mock_cache.set = AsyncMock()
            return IntegratedErrorDetector(mock_progress_reporter)

    @pytest.fixture
    def sample_errors(self):
        """샘플 오류 목록"""
        return [
            ExcelError(
                id="sheet1_A1_div_zero",
                type="#DIV/0!",
                sheet="Sheet1",
                cell="A1",
                formula="=B1/C1",
                value="#DIV/0!",
                message="0으로 나누기 오류",
                severity="high",
                is_auto_fixable=True,
                suggested_fix="IFERROR 함수 사용",
                confidence=0.95,
            ),
            ExcelError(
                id="sheet1_B2_ref_error",
                type="#REF!",
                sheet="Sheet1",
                cell="B2",
                formula="=DeletedSheet!A1",
                value="#REF!",
                message="참조 오류",
                severity="critical",
                is_auto_fixable=False,
                suggested_fix=None,
                confidence=1.0,
            ),
        ]

    @pytest.fixture
    def sample_cells(self) -> list[CellInfo]:
        """샘플 셀 정보"""
        return [
            {
                "address": "A1",
                "sheet": "Sheet1",
                "value": "#DIV/0!",
                "formula": "=B1/C1",
                "row": 1,
                "col": 1,
                "has_error": True,
                "error_type": "#DIV/0!",
            },
            {
                "address": "B1",
                "sheet": "Sheet1",
                "value": 0,
                "formula": None,
                "row": 1,
                "col": 2,
                "has_error": False,
                "error_type": None,
            },
        ]

    @pytest.mark.asyncio
    async def test_batch_processing(self, detector, sample_cells):
        """배치 처리 테스트"""
        # 대량 셀 생성 (BATCH_SIZE 초과)
        large_cell_list = sample_cells * 60  # 120개 셀

        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_load.return_value = mock_workbook

            # 배치 처리 실행
            result = await detector.detect_multi_cell_errors(
                "/tmp/test.xlsx", large_cell_list
            )

            # 결과 검증
            assert isinstance(result, dict)
            assert "individual_cells" in result
            assert "total_errors" in result
            assert "pattern_analysis" in result
            assert len(large_cell_list) > detector.BATCH_SIZE

    @pytest.mark.asyncio
    async def test_parallel_detector_optimization(self, detector, sample_errors):
        """병렬 감지기 최적화 테스트"""
        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_load.return_value = mock_workbook

            # 각 감지기가 다른 오류를 반환하도록 설정
            for i, det in enumerate(detector.detectors):
                det.detect = AsyncMock(
                    return_value=[sample_errors[i % len(sample_errors)]]
                )

            # 병렬 실행
            errors = await detector._run_detectors_parallel_optimized(mock_workbook)

            # 세마포어 제한 확인
            assert len(errors) >= len(sample_errors)

    @pytest.mark.asyncio
    async def test_streaming_error_detection(self, detector):
        """스트리밍 오류 감지 테스트"""
        callback_results = []

        async def test_callback(result):
            callback_results.append(result)

        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_workbook.sheetnames = ["Sheet1", "Sheet2", "Sheet3"]
            mock_load.return_value = mock_workbook

            # 스트리밍 감지 실행
            result = await detector.detect_errors_streaming(
                "/tmp/test.xlsx", callback=test_callback
            )

            # 콜백이 시트별로 호출되었는지 확인
            assert len(callback_results) == 3
            assert all("progress" in r for r in callback_results)
            assert result["streaming"] is True

    @pytest.mark.asyncio
    async def test_hierarchical_caching(self, detector, sample_errors):
        """계층적 캐싱 테스트"""
        with patch(
            "app.services.detection.integrated_error_detector.integrated_cache"
        ) as mock_cache:
            mock_cache.get_analysis = AsyncMock(return_value=None)
            mock_cache.set_analysis = AsyncMock()
            mock_cache.set_errors = AsyncMock()
            mock_cache.set = AsyncMock()

            with patch.object(detector, "_load_workbook") as mock_load:
                mock_workbook = MagicMock()
                mock_load.return_value = mock_workbook

                # 모든 감지기가 오류를 반환하도록 설정
                for det in detector.detectors:
                    det.detect = AsyncMock(return_value=sample_errors)

                # 오류 감지 실행
                await detector.detect_all_errors("/tmp/test_123.xlsx")

                # 캐시 호출 검증
                # 1. 전체 분석 결과 캐싱
                mock_cache.set_analysis.assert_called_once()

                # 2. 오류 목록 캐싱
                mock_cache.set_errors.assert_called_once()

                # 3. 요약 정보 캐싱 (더 긴 TTL)
                summary_call = [
                    call
                    for call in mock_cache.set.call_args_list
                    if "summary:" in call[0][0]
                ]
                assert len(summary_call) > 0

    @pytest.mark.asyncio
    async def test_type_safety(self, detector):
        """타입 안정성 테스트"""
        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_load.return_value = mock_workbook

            # 빈 오류 목록으로 테스트
            for det in detector.detectors:
                det.detect = AsyncMock(return_value=[])

            result = await detector.detect_all_errors("/tmp/test.xlsx")

            # FileAnalysisResult 타입 검증
            assert result["status"] in ["success", "error"]
            assert "file_id" in result
            assert "file_path" in result
            assert "filename" in result
            assert "timestamp" in result
            assert "analysis_time" in result
            assert "errors" in result
            assert "summary" in result
            assert "sheets" in result
            assert "tier_used" in result

    @pytest.mark.asyncio
    async def test_error_info_conversion(self, detector, sample_errors):
        """ErrorInfo 변환 테스트"""
        for error in sample_errors:
            error_info = detector._convert_to_error_info(error)

            # ErrorInfo 타입 검증
            assert "id" in error_info
            assert "type" in error_info
            assert "severity" in error_info
            assert "cell" in error_info
            assert "sheet" in error_info
            assert "message" in error_info
            assert "is_auto_fixable" in error_info
            assert "suggested_fix" in error_info
            assert "confidence" in error_info
            assert "details" in error_info

    @pytest.mark.asyncio
    async def test_concurrent_detector_limit(self, detector):
        """동시 실행 감지기 제한 테스트"""
        # 많은 수의 감지기 추가
        for i in range(10):
            mock_detector = MagicMock()
            mock_detector.detect = AsyncMock(return_value=[])
            detector.detectors.append(mock_detector)

        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_load.return_value = mock_workbook

            # 실행 시간 측정
            asyncio.get_event_loop().time()
            await detector._run_detectors_parallel_optimized(mock_workbook)
            asyncio.get_event_loop().time()

            # MAX_CONCURRENT_DETECTORS 제한이 적용되었는지 확인
            # (실제로는 동시에 4개만 실행되어야 함)
            assert len(detector.detectors) > detector.MAX_CONCURRENT_DETECTORS

    @pytest.mark.asyncio
    async def test_multi_cell_analysis_type(self, detector, sample_cells):
        """MultiCellAnalysis 타입 테스트"""
        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_load.return_value = mock_workbook

            result = await detector.detect_multi_cell_errors(
                "/tmp/test.xlsx", sample_cells
            )

            # MultiCellAnalysis 타입 검증
            assert "individual_cells" in result
            assert "total_errors" in result
            assert "pattern_analysis" in result
            assert "cross_cell_issues" in result
            assert "summary" in result

            # pattern_analysis 구조 검증
            pattern_analysis = result["pattern_analysis"]
            if pattern_analysis:
                assert "patterns" in pattern_analysis
                assert "summary" in pattern_analysis
                assert "has_insights" in pattern_analysis
                assert "total_patterns" in pattern_analysis
