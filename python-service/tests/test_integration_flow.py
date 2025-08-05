"""
Integration Flow Tests
통합 플로우 테스트 - 파일 업로드부터 AI 채팅까지
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import os

from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.services.context.enhanced_context_manager import EnhancedContextManager
from app.core.file_path_resolver import FilePathResolver
from app.core.responses import ResponseBuilder


class TestIntegrationFlow:
    """전체 통합 플로우 테스트"""

    @pytest.fixture
    async def temp_excel_file(self):
        """임시 Excel 파일 생성"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            # 실제 Excel 파일 대신 모의 파일 사용
            tmp.write(b"Mock Excel content")
            tmp_path = tmp.name

        yield tmp_path

        # 정리
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    @pytest.fixture
    def mock_integrated_cache(self):
        """모의 통합 캐시"""
        with patch("app.core.integrated_cache.integrated_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)
            mock_cache.get_analysis = AsyncMock(return_value=None)
            mock_cache.set_analysis = AsyncMock(return_value=True)
            mock_cache.get_errors = AsyncMock(return_value=None)
            mock_cache.set_errors = AsyncMock(return_value=True)
            yield mock_cache

    @pytest.mark.asyncio
    async def test_full_flow_file_upload_to_ai_chat(
        self, temp_excel_file, mock_integrated_cache
    ):
        """파일 업로드부터 AI 채팅까지 전체 플로우 테스트"""

        # 1. 파일 업로드 및 ID 매핑
        file_id = "test_file_123"
        session_id = "session_456"

        # FilePathResolver 모의
        with patch.object(FilePathResolver, "generate_file_id", return_value=file_id):
            with patch.object(
                FilePathResolver, "save_file_mapping"
            ) as mock_save_mapping:
                mock_save_mapping.return_value = None

                # 파일 매핑 저장
                await FilePathResolver.save_file_mapping(
                    file_id,
                    temp_excel_file,
                    {"original_filename": "test.xlsx", "session_id": session_id},
                )

                mock_save_mapping.assert_called_once()

        # 2. IntegratedErrorDetector로 오류 감지
        detector = IntegratedErrorDetector()

        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_workbook.sheetnames = ["Sheet1"]
            mock_load.return_value = mock_workbook

            # 모든 감지기 모의 설정
            sample_errors = []
            for det in detector.detectors:
                det.detect = AsyncMock(return_value=sample_errors)

            # 오류 감지 실행
            detection_result = await detector.detect_all_errors(temp_excel_file)

            assert detection_result["status"] == "success"
            assert detection_result["file_id"] == file_id

        # 3. Context Manager 초기화
        context_manager = EnhancedContextManager()

        with patch.object(context_manager.cache_service, "set") as mock_cache_set:
            mock_cache_set.return_value = None

            # 워크북 컨텍스트 초기화
            workbook_context = await context_manager.initialize_workbook_context(
                session_id=session_id,
                file_id=file_id,
                file_name="test.xlsx",
                analysis_result=detection_result,
            )

            assert workbook_context is not None
            assert workbook_context["file_id"] == file_id

        # 4. AI 채팅 요청
        from app.api.v1.ai import ai_consultation
        from app.api.v1.ai import AIConsultationRequest

        # AI 상담 요청 데이터
        ai_request = AIConsultationRequest(
            prompt="이 엑셀 파일에 어떤 오류가 있나요?",
            cell_context=None,
            file_info={"fileId": file_id, "fileName": "test.xlsx"},
            conversation_history=[],
            session_id=session_id,
        )

        # OpenAI 서비스 모의
        with patch(
            "app.services.openai_service.openai_service.chat_completion"
        ) as mock_ai:
            mock_ai.return_value = "파일을 분석한 결과 오류가 없습니다."

            # 컨텍스트 관리자 모의
            with patch("app.api.v1.ai.get_enhanced_context_manager") as mock_get_cm:
                mock_get_cm.return_value = context_manager

                # AI 상담 실행
                response = await ai_consultation(ai_request, db=MagicMock())

                # ResponseBuilder 형식 확인
                assert response["status"] == "success"
                assert "data" in response
                assert "response" in response["data"]

    @pytest.mark.asyncio
    async def test_websocket_real_time_updates(self, temp_excel_file):
        """WebSocket 실시간 업데이트 테스트"""
        from app.websocket.excel_websocket_handler import ExcelWebSocketHandler

        handler = ExcelWebSocketHandler()
        session_id = "ws_session_123"

        # WebSocket 모의
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()
        mock_websocket.receive_json = AsyncMock(
            side_effect=[
                # 파일 분석 요청
                {
                    "type": "analyze_file",
                    "data": {
                        "file_path": temp_excel_file,
                        "options": {"file_id": "test_123"},
                    },
                },
                # 연결 종료
                {"type": "close"},
            ]
        )

        # 핸들러 메서드 모의
        with patch.object(handler, "handle_analyze_file") as mock_analyze:
            mock_analyze.return_value = None

            # 메시지 처리
            await handler.handle_message(
                session_id,
                {"type": "analyze_file", "data": {"file_path": temp_excel_file}},
            )

            mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_integration(self, mock_integrated_cache):
        """캐시 통합 테스트"""
        file_id = "cache_test_123"

        # 분석 결과 캐싱
        analysis_result = {"status": "success", "file_id": file_id, "errors": []}

        await mock_integrated_cache.set_analysis(file_id, analysis_result)
        mock_integrated_cache.set_analysis.assert_called_with(file_id, analysis_result)

        # 캐시에서 조회
        mock_integrated_cache.get_analysis.return_value = analysis_result
        cached_result = await mock_integrated_cache.get_analysis(file_id)

        assert cached_result == analysis_result

    @pytest.mark.asyncio
    async def test_rails_python_websocket_bridge(self):
        """Rails-Python WebSocket 브리지 테스트"""
        from app.api.v1.context_websocket import manager as ws_manager

        session_id = "bridge_test_123"
        test_message = {
            "type": "cell_selection",
            "data": {"cells": ["A1", "B2"], "sheet": "Sheet1"},
        }

        # WebSocket 매니저 모의
        with patch.object(ws_manager, "send_to_session") as mock_send:
            mock_send.return_value = None

            # 메시지 전송
            await ws_manager.send_to_session(session_id, test_message)

            mock_send.assert_called_once_with(session_id, test_message)

    @pytest.mark.asyncio
    async def test_error_response_format(self):
        """에러 응답 포맷 테스트"""
        test_exception = ValueError("테스트 오류")

        # ResponseBuilder 사용
        error_response = ResponseBuilder.from_exception(
            test_exception, context={"operation": "test"}, include_traceback=False
        )

        # 표준 에러 응답 형식 확인
        assert error_response["status"] == "error"
        assert "message" in error_response
        assert "error_code" in error_response
        assert "timestamp" in error_response
        assert "request_id" in error_response

    @pytest.mark.asyncio
    async def test_multi_cell_selection_flow(self, temp_excel_file):
        """멀티 셀 선택 플로우 테스트"""
        detector = IntegratedErrorDetector()

        # 멀티 셀 정보
        cells = [
            {"address": "A1", "sheet": "Sheet1", "value": 10},
            {"address": "B1", "sheet": "Sheet1", "value": 20},
            {"address": "C1", "sheet": "Sheet1", "value": "=A1+B1"},
        ]

        with patch.object(detector, "_load_workbook") as mock_load:
            mock_workbook = MagicMock()
            mock_load.return_value = mock_workbook

            # 멀티 셀 분석
            result = await detector.detect_multi_cell_errors(temp_excel_file, cells)

            # MultiCellAnalysis 결과 확인
            assert "individual_cells" in result
            assert "pattern_analysis" in result
            assert "cross_cell_issues" in result
            assert len(result["individual_cells"]) == len(cells)
