"""
Performance Tests
성능 테스트 - 대용량 파일 및 동시성 테스트
"""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
import random

from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.core.integrated_cache import IntegratedCache
from app.services.context.enhanced_context_manager import EnhancedContextManager


class TestPerformance:
    """성능 테스트 스위트"""

    @pytest.fixture
    def large_workbook(self):
        """대용량 워크북 모의"""
        workbook = MagicMock()
        # 100개 시트, 각 시트 1000개 셀
        workbook.sheetnames = [f"Sheet{i}" for i in range(100)]

        for sheet_name in workbook.sheetnames:
            sheet = MagicMock()
            sheet.max_row = 1000
            sheet.max_column = 26
            workbook[sheet_name] = sheet

        return workbook

    @pytest.fixture
    def detector_with_mock_cache(self):
        """캐시가 모의된 감지기"""
        with patch(
            "app.services.detection.integrated_error_detector.integrated_cache"
        ) as mock_cache:
            mock_cache.get_analysis = AsyncMock(return_value=None)
            mock_cache.set_analysis = AsyncMock()
            mock_cache.set_errors = AsyncMock()
            mock_cache.set = AsyncMock()

            detector = IntegratedErrorDetector()
            # 모든 감지기를 빠른 모의로 교체
            for det in detector.detectors:
                det.detect = AsyncMock(return_value=[])

            return detector

    @pytest.mark.asyncio
    async def test_large_file_processing(
        self, detector_with_mock_cache, large_workbook
    ):
        """대용량 파일 처리 성능 테스트"""
        detector = detector_with_mock_cache

        with patch.object(detector, "_load_workbook", return_value=large_workbook):
            start_time = time.time()

            # 대용량 파일 분석
            result = await detector.detect_all_errors("/tmp/large_file.xlsx")

            end_time = time.time()
            processing_time = end_time - start_time

            # 성능 검증
            assert result["status"] == "success"
            assert processing_time < 10  # 10초 이내 처리
            print(f"대용량 파일 처리 시간: {processing_time:.2f}초")

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, detector_with_mock_cache):
        """동시 요청 처리 테스트"""
        detector = detector_with_mock_cache
        concurrent_requests = 50

        async def process_file(file_id):
            with patch.object(detector, "_load_workbook", return_value=MagicMock()):
                return await detector.detect_all_errors(f"/tmp/file_{file_id}.xlsx")

        start_time = time.time()

        # 동시 요청 실행
        tasks = [process_file(i) for i in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # 모든 요청 성공 확인
        assert all(r["status"] == "success" for r in results)
        assert total_time < 30  # 30초 이내 모든 요청 처리

        avg_time = total_time / concurrent_requests
        print(f"동시 요청 {concurrent_requests}개 처리 시간: {total_time:.2f}초")
        print(f"요청당 평균 시간: {avg_time:.2f}초")

    @pytest.mark.asyncio
    async def test_batch_processing_performance(self, detector_with_mock_cache):
        """배치 처리 성능 테스트"""
        detector = detector_with_mock_cache

        # 1000개 셀 생성
        cells = [
            {
                "address": f"{chr(65 + i % 26)}{i // 26 + 1}",
                "sheet": f"Sheet{i % 10}",
                "value": random.randint(1, 100),
            }
            for i in range(1000)
        ]

        with patch.object(detector, "_load_workbook", return_value=MagicMock()):
            start_time = time.time()

            # 배치 처리
            result = await detector.detect_multi_cell_errors("/tmp/test.xlsx", cells)

            end_time = time.time()
            processing_time = end_time - start_time

            # 배치 처리가 효율적인지 확인
            assert processing_time < 5  # 5초 이내
            assert len(result["individual_cells"]) == len(cells)
            print(f"1000개 셀 배치 처리 시간: {processing_time:.2f}초")

    @pytest.mark.asyncio
    async def test_streaming_performance(
        self, detector_with_mock_cache, large_workbook
    ):
        """스트리밍 처리 성능 테스트"""
        detector = detector_with_mock_cache
        callback_count = 0

        async def callback(result):
            nonlocal callback_count
            callback_count += 1

        with patch.object(detector, "_load_workbook", return_value=large_workbook):
            start_time = time.time()

            # 스트리밍 감지
            result = await detector.detect_errors_streaming(
                "/tmp/large_file.xlsx", callback=callback
            )

            end_time = time.time()
            processing_time = end_time - start_time

            # 스트리밍이 시트별로 호출되었는지 확인
            assert callback_count == len(large_workbook.sheetnames)
            assert processing_time < 15  # 15초 이내
            print(f"스트리밍 처리 시간: {processing_time:.2f}초")

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """캐시 성능 테스트"""
        # 모의 캐시 생성
        with patch("app.core.integrated_cache.Redis") as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.get = AsyncMock(return_value=None)
            mock_redis_instance.set = AsyncMock(return_value=True)
            mock_redis.return_value = mock_redis_instance

            cache = IntegratedCache()

            # 캐시 쓰기 성능
            start_time = time.time()
            for i in range(1000):
                await cache.set(f"key_{i}", {"data": f"value_{i}"})
            write_time = time.time() - start_time

            # 캐시 읽기 성능
            mock_redis_instance.get = AsyncMock(return_value='{"data": "cached_value"}')
            start_time = time.time()
            for i in range(1000):
                await cache.get(f"key_{i}")
            read_time = time.time() - start_time

            print(f"1000개 캐시 쓰기: {write_time:.2f}초")
            print(f"1000개 캐시 읽기: {read_time:.2f}초")

            assert write_time < 2  # 2초 이내
            assert read_time < 1  # 1초 이내

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, detector_with_mock_cache):
        """메모리 효율성 테스트"""
        detector = detector_with_mock_cache

        # 메모리 사용량 측정을 위한 가상 테스트
        # 실제로는 memory_profiler나 tracemalloc 사용

        # 많은 수의 오류 생성
        large_errors = []
        for i in range(10000):
            error = MagicMock()
            error.id = f"error_{i}"
            error.type = "TEST_ERROR"
            error.severity = "medium"
            large_errors.append(error)

        # 중복 제거 테스트
        start_time = time.time()
        unique_errors = detector._deduplicate_errors(large_errors)
        dedup_time = time.time() - start_time

        print(f"10000개 오류 중복 제거 시간: {dedup_time:.2f}초")
        assert dedup_time < 1  # 1초 이내

    @pytest.mark.asyncio
    async def test_context_manager_performance(self):
        """컨텍스트 관리자 성능 테스트"""
        context_manager = EnhancedContextManager()

        # 100개 세션 동시 생성
        session_ids = [f"session_{i}" for i in range(100)]

        start_time = time.time()

        # 병렬로 세션 초기화
        tasks = []
        for session_id in session_ids:
            task = context_manager.initialize_workbook_context(
                session_id=session_id,
                file_id=f"file_{session_id}",
                file_name="test.xlsx",
                analysis_result={"status": "success", "errors": []},
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        print(f"100개 세션 초기화 시간: {total_time:.2f}초")
        assert total_time < 5  # 5초 이내

    def test_cpu_bound_operations(self):
        """CPU 집약적 작업 성능 테스트"""
        # 셀 주소 변환 성능
        from app.core.excel_utils import ExcelUtils

        start_time = time.time()

        # 100만 개 셀 주소 변환
        for i in range(1000000):
            row, col = ExcelUtils.cell_to_row_col(f"AA{i % 1000 + 1}")

        end_time = time.time()
        conversion_time = end_time - start_time

        print(f"100만 개 셀 주소 변환 시간: {conversion_time:.2f}초")
        assert conversion_time < 5  # 5초 이내


if __name__ == "__main__":
    # 성능 테스트 실행
    pytest.main([__file__, "-v", "-s"])
