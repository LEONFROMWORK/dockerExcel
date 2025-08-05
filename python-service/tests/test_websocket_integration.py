"""
WebSocket 통합 테스트
실시간 진행 상황 보고 및 오류 감지/수정 알림 테스트
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.websocket.excel_websocket_handler import ExcelWebSocketHandler
from app.websocket.progress_reporter import (
    WebSocketManager,
    WebSocketProgressReporter,
    ExcelUpdateNotifier,
)


class TestWebSocketIntegration:
    """WebSocket 통합 테스트"""

    @pytest.fixture
    def websocket_manager(self):
        """WebSocket Manager 인스턴스"""
        # Singleton 패턴이므로 기존 인스턴스 초기화
        manager = WebSocketManager()
        manager.active_connections.clear()
        return manager

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket 연결"""
        ws = Mock()
        ws.send_json = AsyncMock()
        ws.accept = AsyncMock()
        ws.receive_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.fixture
    def excel_handler(self):
        """Excel WebSocket Handler"""
        return ExcelWebSocketHandler()

    @pytest.fixture
    def progress_reporter(self):
        """Progress Reporter"""
        return WebSocketProgressReporter("test_session_123")

    @pytest.fixture
    def update_notifier(self):
        """Update Notifier"""
        return ExcelUpdateNotifier()

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(
        self, websocket_manager, mock_websocket
    ):
        """WebSocket 연결 생명주기 테스트"""
        session_id = "test_session_123"

        # 연결
        await websocket_manager.connect(mock_websocket, session_id)
        assert session_id in websocket_manager.active_connections
        assert mock_websocket in websocket_manager.active_connections[session_id]

        # 메시지 전송
        test_message = {"type": "test", "data": {"message": "Hello"}}
        await websocket_manager.send_message(session_id, test_message)
        mock_websocket.send_json.assert_called_with(test_message)

        # 연결 해제
        await websocket_manager.disconnect(mock_websocket, session_id)
        assert session_id not in websocket_manager.active_connections

    @pytest.mark.asyncio
    async def test_progress_reporting(
        self, progress_reporter, websocket_manager, mock_websocket
    ):
        """진행 상황 보고 테스트"""
        session_id = progress_reporter.session_id
        await websocket_manager.connect(mock_websocket, session_id)

        # 작업 시작
        await progress_reporter.start_task("파일 분석", 100)

        # 진행 상황 보고
        for i in range(0, 101, 25):
            await progress_reporter.report_progress(i, 100, f"{i}% 완료")

        # 작업 완료
        await progress_reporter.complete_task("파일 분석", {"errors_found": 5})

        # 메시지 검증
        calls = mock_websocket.send_json.call_args_list
        message_types = [call[0][0]["type"] for call in calls]

        assert "task_start" in message_types
        assert "progress" in message_types
        assert "task_complete" in message_types

        # 진행률 검증
        progress_messages = [
            call[0][0] for call in calls if call[0][0]["type"] == "progress"
        ]
        percentages = [msg["data"]["percentage"] for msg in progress_messages]
        assert percentages == [0.0, 25.0, 50.0, 75.0, 100.0]

    @pytest.mark.asyncio
    async def test_error_detection_notification(
        self, update_notifier, websocket_manager, mock_websocket
    ):
        """오류 감지 알림 테스트"""
        session_id = "test_session_123"
        await websocket_manager.connect(mock_websocket, session_id)

        # 오류 감지 알림
        error_data = {
            "cell": "A1",
            "sheet": "Sheet1",
            "error": {
                "type": "DIV_ZERO",
                "message": "Division by zero",
                "formula": "=B1/C1",
            },
        }

        await update_notifier.notify_error_detected(session_id, error_data)

        # 알림 검증
        mock_websocket.send_json.assert_called()
        sent_message = mock_websocket.send_json.call_args[0][0]
        assert sent_message["type"] == "error_detected"
        assert sent_message["data"] == error_data

    @pytest.mark.asyncio
    async def test_error_fix_notification(
        self, update_notifier, websocket_manager, mock_websocket
    ):
        """오류 수정 알림 테스트"""
        session_id = "test_session_123"
        await websocket_manager.connect(mock_websocket, session_id)

        # 오류 수정 알림
        fix_data = {
            "error_id": "error_001",
            "original_formula": "=B1/C1",
            "fixed_formula": "=IFERROR(B1/C1, 0)",
            "status": "success",
        }

        await update_notifier.notify_error_fixed(session_id, fix_data)

        # 알림 검증
        mock_websocket.send_json.assert_called()
        sent_message = mock_websocket.send_json.call_args[0][0]
        assert sent_message["type"] == "error_fixed"
        assert sent_message["data"] == fix_data

    @pytest.mark.asyncio
    async def test_excel_handler_message_processing(
        self, excel_handler, mock_websocket
    ):
        """Excel WebSocket Handler 메시지 처리 테스트"""
        session_id = "test_session_123"

        # Mock 설정
        with patch.object(
            excel_handler, "handle_check_cell", new_callable=AsyncMock
        ) as mock_check_cell, patch.object(
            excel_handler, "handle_fix_error", new_callable=AsyncMock
        ) as mock_fix_error:

            # 셀 검사 메시지
            await excel_handler.handle_message(
                session_id,
                {
                    "type": "check_cell",
                    "data": {
                        "file_path": "/tmp/test.xlsx",
                        "sheet": "Sheet1",
                        "cell": "A1",
                    },
                },
            )
            mock_check_cell.assert_called_once()

            # 오류 수정 메시지
            await excel_handler.handle_message(
                session_id,
                {
                    "type": "fix_error",
                    "data": {"error_id": "error_001", "auto_apply": True},
                },
            )
            mock_fix_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, websocket_manager):
        """동시 다중 연결 테스트"""
        # 여러 세션 생성
        sessions = []
        for i in range(5):
            ws = Mock()
            ws.send_json = AsyncMock()
            session_id = f"session_{i}"
            await websocket_manager.connect(ws, session_id)
            sessions.append((session_id, ws))

        # 브로드캐스트 메시지
        broadcast_message = {
            "type": "announcement",
            "data": {"message": "Server update"},
        }
        await websocket_manager.broadcast(broadcast_message)

        # 모든 연결이 메시지를 받았는지 확인
        for _, ws in sessions:
            ws.send_json.assert_called_with(broadcast_message)

        # 정리
        for session_id, ws in sessions:
            await websocket_manager.disconnect(ws, session_id)

    @pytest.mark.asyncio
    async def test_error_recovery(self, websocket_manager, mock_websocket):
        """오류 복구 테스트"""
        session_id = "test_session_123"
        await websocket_manager.connect(mock_websocket, session_id)

        # 전송 오류 시뮬레이션
        mock_websocket.send_json.side_effect = Exception("Connection lost")

        # 메시지 전송 시도
        await websocket_manager.send_message(session_id, {"type": "test"})

        # 연결이 자동으로 제거되었는지 확인
        assert session_id not in websocket_manager.active_connections

    @pytest.mark.asyncio
    async def test_progress_reporter_with_errors(
        self, progress_reporter, websocket_manager, mock_websocket
    ):
        """오류 상황에서의 진행 상황 보고 테스트"""
        session_id = progress_reporter.session_id
        await websocket_manager.connect(mock_websocket, session_id)

        # 작업 시작
        await progress_reporter.start_task("오류 분석", 50)

        # 일부 진행
        await progress_reporter.report_progress(25, 50, "분석 중...")

        # 오류 보고
        test_error = Exception("분석 실패")
        await progress_reporter.report_error(test_error)

        # 메시지 검증
        calls = mock_websocket.send_json.call_args_list
        error_messages = [call[0][0] for call in calls if call[0][0]["type"] == "error"]

        assert len(error_messages) == 1
        assert error_messages[0]["data"]["error_type"] == "Exception"
        assert error_messages[0]["data"]["message"] == "분석 실패"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
