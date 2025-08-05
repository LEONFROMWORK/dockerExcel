"""
Integrated Error Detector Tests
통합 오류 감지기 테스트
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.core.interfaces import ExcelError
from datetime import datetime


class TestIntegratedErrorDetector:
    """IntegratedErrorDetector 테스트"""

    @pytest.fixture
    def mock_progress_reporter(self):
        """모의 진행 상황 보고기"""
        reporter = MagicMock()
        reporter.report_progress = AsyncMock()
        reporter.report_error = AsyncMock()
        return reporter

    @pytest.fixture
    def detector(self, mock_progress_reporter):
        """감지기 인스턴스"""
        with patch(
            "app.services.detection.integrated_error_detector.settings"
        ) as mock_settings:
            mock_settings.EXCEL_CACHE_TTL = 300
            return IntegratedErrorDetector(mock_progress_reporter)

    @pytest.fixture
    def sample_error(self):
        """샘플 오류"""
        return ExcelError(
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
        )

    @pytest.mark.asyncio
    async def test_detect_all_errors_with_cache(self, detector):
        """캐시를 사용한 오류 감지 테스트"""
        file_path = "/test/file.xlsx"

        # 첫 번째 호출 - 캐시 미스
        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_load.return_value = mock_workbook

            with patch.object(detector, "_run_detectors_parallel") as mock_run:
                mock_run.return_value = []

                result1 = await detector.detect_all_errors(file_path)

                # 워크북 로드 확인
                mock_load.assert_called_once_with(file_path)
                mock_run.assert_called_once()

        # 두 번째 호출 - 캐시 히트
        with patch.object(detector, "_load_workbook") as mock_load2:
            result2 = await detector.detect_all_errors(file_path)

            # 워크북을 다시 로드하지 않음
            mock_load2.assert_not_called()

            # 같은 결과 반환
            assert result1["file_path"] == result2["file_path"]
            assert result1["status"] == result2["status"]

    @pytest.mark.asyncio
    async def test_detect_cell_error(self, detector, sample_error):
        """특정 셀 오류 감지 테스트"""
        file_path = "/test/file.xlsx"
        sheet = "Sheet1"
        cell = "A1"

        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_worksheet = MagicMock()
            mock_cell = MagicMock()

            mock_workbook.__getitem__.return_value = mock_worksheet
            mock_worksheet.__getitem__.return_value = mock_cell
            mock_load.return_value = mock_workbook

            # 감지기 모의 설정
            mock_detector = MagicMock()
            mock_detector.detect_cell = AsyncMock(return_value=[sample_error])
            detector.detectors = [mock_detector]

            # 오류 감지
            error = await detector.detect_cell_error(file_path, sheet, cell)

            # 검증
            assert error is not None
            assert error.type == "#DIV/0!"
            assert error.cell == "A1"

    @pytest.mark.asyncio
    async def test_run_detectors_parallel(self, detector):
        """병렬 감지기 실행 테스트"""
        mock_workbook = MagicMock()

        # 여러 감지기 설정
        errors1 = [
            ExcelError(
                id="1",
                type="#DIV/0!",
                sheet="Sheet1",
                cell="A1",
                formula=None,
                value=None,
                message="",
                severity="high",
                is_auto_fixable=True,
                suggested_fix="",
                confidence=0.9,
            )
        ]

        errors2 = [
            ExcelError(
                id="2",
                type="Duplicate",
                sheet="Sheet1",
                cell="B2",
                formula=None,
                value="dup",
                message="",
                severity="medium",
                is_auto_fixable=False,
                suggested_fix="",
                confidence=0.8,
            )
        ]

        detector1 = MagicMock()
        detector1.detect = AsyncMock(return_value=errors1)
        detector1.__class__.__name__ = "FormulaErrorDetector"

        detector2 = MagicMock()
        detector2.detect = AsyncMock(return_value=errors2)
        detector2.__class__.__name__ = "DataQualityDetector"

        detector.detectors = [detector1, detector2]

        # 실행
        all_errors = await detector._run_detectors_parallel(mock_workbook)

        # 검증
        assert len(all_errors) == 2
        assert all_errors[0].id == "1"
        assert all_errors[1].id == "2"

        # 진행 상황 보고 확인
        detector.progress_reporter.report_progress.assert_called()

    def test_deduplicate_errors(self, detector):
        """중복 오류 제거 테스트"""
        errors = [
            ExcelError(
                id="1",
                type="#DIV/0!",
                sheet="Sheet1",
                cell="A1",
                formula=None,
                value=None,
                message="",
                severity="high",
                is_auto_fixable=True,
                suggested_fix="",
                confidence=0.9,
            ),
            ExcelError(
                id="2",
                type="#DIV/0!",
                sheet="Sheet1",
                cell="A1",  # 같은 위치, 같은 타입
                formula=None,
                value=None,
                message="",
                severity="high",
                is_auto_fixable=True,
                suggested_fix="",
                confidence=0.9,
            ),
            ExcelError(
                id="3",
                type="#N/A",
                sheet="Sheet1",
                cell="A1",  # 같은 위치, 다른 타입
                formula=None,
                value=None,
                message="",
                severity="low",
                is_auto_fixable=True,
                suggested_fix="",
                confidence=0.8,
            ),
        ]

        unique_errors = detector._deduplicate_errors(errors)

        # 검증
        assert len(unique_errors) == 2
        assert unique_errors[0].type == "#DIV/0!"
        assert unique_errors[1].type == "#N/A"

    def test_sort_errors_by_priority(self, detector):
        """우선순위별 오류 정렬 테스트"""
        errors = [
            ExcelError(
                id="1",
                type="#DIV/0!",
                sheet="Sheet2",
                cell="B2",
                formula=None,
                value=None,
                message="",
                severity="medium",
                is_auto_fixable=True,
                suggested_fix="",
                confidence=0.9,
            ),
            ExcelError(
                id="2",
                type="#REF!",
                sheet="Sheet1",
                cell="A1",
                formula=None,
                value=None,
                message="",
                severity="critical",
                is_auto_fixable=False,
                suggested_fix="",
                confidence=0.7,
            ),
            ExcelError(
                id="3",
                type="#N/A",
                sheet="Sheet1",
                cell="C3",
                formula=None,
                value=None,
                message="",
                severity="low",
                is_auto_fixable=True,
                suggested_fix="",
                confidence=0.8,
            ),
        ]

        sorted_errors = detector._sort_errors_by_priority(errors)

        # 검증 - critical > medium > low
        assert sorted_errors[0].severity == "critical"
        assert sorted_errors[1].severity == "medium"
        assert sorted_errors[2].severity == "low"

    def test_create_summary(self, detector):
        """오류 요약 생성 테스트"""
        errors = [
            ExcelError(
                id="1",
                type="#DIV/0!",
                sheet="Sheet1",
                cell="A1",
                formula=None,
                value=None,
                message="",
                severity="high",
                is_auto_fixable=True,
                suggested_fix="",
                confidence=0.9,
            ),
            ExcelError(
                id="2",
                type="#DIV/0!",
                sheet="Sheet1",
                cell="B1",
                formula=None,
                value=None,
                message="",
                severity="high",
                is_auto_fixable=True,
                suggested_fix="",
                confidence=0.9,
            ),
            ExcelError(
                id="3",
                type="#N/A",
                sheet="Sheet2",
                cell="C1",
                formula=None,
                value=None,
                message="",
                severity="low",
                is_auto_fixable=False,
                suggested_fix="",
                confidence=0.8,
            ),
        ]

        summary = detector._create_summary(errors)

        # 검증
        assert summary["total_errors"] == 3
        assert summary["by_type"]["#DIV/0!"] == 2
        assert summary["by_type"]["#N/A"] == 1
        assert summary["by_severity"]["high"] == 2
        assert summary["by_severity"]["low"] == 1
        assert summary["by_sheet"]["Sheet1"] == 2
        assert summary["by_sheet"]["Sheet2"] == 1
        assert summary["auto_fixable"] == 2
        assert summary["auto_fixable_percentage"] == 66.67
        assert summary["most_common_type"] == "#DIV/0!"

    def test_add_remove_detector(self, detector):
        """감지기 추가/제거 테스트"""
        initial_count = len(detector.detectors)

        # 새 감지기 추가
        new_detector = MagicMock()
        new_detector.__class__.__name__ = "TestDetector"
        detector.add_detector(new_detector)

        assert len(detector.detectors) == initial_count + 1
        assert new_detector in detector.detectors

        # 감지기 제거
        from app.services.detection.strategies.formula_error_detector import (
            FormulaErrorDetector,
        )

        detector.remove_detector(FormulaErrorDetector)

        # FormulaErrorDetector가 제거되었는지 확인
        assert not any(isinstance(d, FormulaErrorDetector) for d in detector.detectors)

    def test_cache_operations(self, detector):
        """캐시 작업 테스트"""
        file_path = "/test/file.xlsx"
        cache_key = detector._get_cache_key(file_path)

        # 캐시 데이터 추가
        test_data = {"test": "data"}
        detector._cache[cache_key] = {"data": test_data, "timestamp": datetime.now()}

        # 캐시 유효성 확인
        assert detector._is_cache_valid(detector._cache[cache_key]) == True

        # 캐시 초기화
        detector.clear_cache()
        assert len(detector._cache) == 0
