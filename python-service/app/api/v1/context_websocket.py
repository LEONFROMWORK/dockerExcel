"""
Context WebSocket API
실시간 컨텍스트 동기화를 위한 WebSocket 엔드포인트
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Set
import logging
from datetime import datetime
from app.services.context import get_enhanced_context_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 연결 관리자"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # session_id -> WebSocket
        self.session_subscriptions: Dict[str, Set[str]] = (
            {}
        )  # session_id -> {client_ids}

    async def connect(self, websocket: WebSocket, session_id: str, client_id: str):
        """새 연결 추가"""
        await websocket.accept()
        self.active_connections[client_id] = websocket

        # 세션 구독 추가
        if session_id not in self.session_subscriptions:
            self.session_subscriptions[session_id] = set()
        self.session_subscriptions[session_id].add(client_id)

        logger.info(f"WebSocket 연결: session={session_id}, client={client_id}")

    def disconnect(self, session_id: str, client_id: str):
        """연결 제거"""
        # 연결 제거
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # 구독 제거
        if session_id in self.session_subscriptions:
            self.session_subscriptions[session_id].discard(client_id)
            if not self.session_subscriptions[session_id]:
                del self.session_subscriptions[session_id]

        logger.info(f"WebSocket 연결 해제: session={session_id}, client={client_id}")

    async def send_to_session(self, session_id: str, message: Dict[str, Any]):
        """특정 세션의 모든 클라이언트에게 메시지 전송"""
        if session_id not in self.session_subscriptions:
            return

        disconnected_clients = []

        for client_id in self.session_subscriptions[session_id]:
            if client_id in self.active_connections:
                try:
                    websocket = self.active_connections[client_id]
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"메시지 전송 실패: {e}")
                    disconnected_clients.append(client_id)

        # 연결이 끊긴 클라이언트 정리
        for client_id in disconnected_clients:
            self.disconnect(session_id, client_id)

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """모든 연결된 클라이언트에게 메시지 전송"""
        disconnected_clients = []

        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"브로드캐스트 실패: {e}")
                disconnected_clients.append(client_id)

        # 연결이 끊긴 클라이언트 정리
        for client_id in disconnected_clients:
            # session_id 찾기
            for session_id, clients in self.session_subscriptions.items():
                if client_id in clients:
                    self.disconnect(session_id, client_id)
                    break


# 전역 연결 관리자
manager = ConnectionManager()


@router.websocket("/ws/context/{session_id}")
async def context_websocket(websocket: WebSocket, session_id: str):
    """
    컨텍스트 실시간 동기화 WebSocket

    메시지 타입:
    - cell_selection: 셀 선택 변경
    - context_update: 컨텍스트 업데이트
    - error_detected: 새 오류 감지
    - analysis_complete: 분석 완료
    """
    import uuid

    client_id = str(uuid.uuid4())

    await manager.connect(websocket, session_id, client_id)

    try:
        # 초기 컨텍스트 전송
        context_manager = get_enhanced_context_manager()
        initial_context = await context_manager.get_enhanced_context(session_id)

        await websocket.send_json(
            {
                "type": "initial_context",
                "data": initial_context,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # 메시지 수신 대기
        while True:
            data = await websocket.receive_json()
            await handle_websocket_message(session_id, data)

    except WebSocketDisconnect:
        manager.disconnect(session_id, client_id)
        logger.info(f"WebSocket 정상 종료: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        manager.disconnect(session_id, client_id)


async def handle_websocket_message(session_id: str, data: Dict[str, Any]):
    """WebSocket 메시지 처리"""
    message_type = data.get("type")
    payload = data.get("data", {})

    context_manager = get_enhanced_context_manager()

    try:
        if message_type == "cell_selection":
            # 셀 선택 업데이트
            cells = payload.get("cells", [])
            await context_manager.update_multi_cell_selection(session_id, cells)

            # 다른 클라이언트에게 브로드캐스트
            await manager.send_to_session(
                session_id,
                {
                    "type": "cell_selection_updated",
                    "data": {"cells": cells, "updated_by": data.get("client_id")},
                    "timestamp": datetime.now().isoformat(),
                },
            )

        elif message_type == "request_context":
            # 현재 컨텍스트 요청
            context = await context_manager.get_enhanced_context(session_id)
            await manager.send_to_session(
                session_id,
                {
                    "type": "context_update",
                    "data": context,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        elif message_type == "user_message":
            # 사용자 메시지 (채팅)
            message = payload.get("message", "")

            # 세션 스토어에 저장
            from app.services.context import get_session_store

            session_store = await get_session_store()
            await session_store.add_chat_message(
                session_id, "user", message, metadata={"source": "websocket"}
            )

            # 브로드캐스트
            await manager.send_to_session(
                session_id,
                {
                    "type": "new_message",
                    "data": {"role": "user", "content": message},
                    "timestamp": datetime.now().isoformat(),
                },
            )

        elif message_type == "ping":
            # 연결 유지 핑
            await manager.send_to_session(
                session_id, {"type": "pong", "timestamp": datetime.now().isoformat()}
            )

    except Exception as e:
        logger.error(f"메시지 처리 오류: {e}")
        await manager.send_to_session(
            session_id,
            {"type": "error", "error": str(e), "timestamp": datetime.now().isoformat()},
        )


# 외부에서 컨텍스트 업데이트를 브로드캐스트하기 위한 함수
async def broadcast_context_update(session_id: str, update_type: str, data: Any):
    """
    외부에서 컨텍스트 업데이트를 브로드캐스트

    Args:
        session_id: 세션 ID
        update_type: 업데이트 타입
        data: 업데이트 데이터
    """
    await manager.send_to_session(
        session_id,
        {"type": update_type, "data": data, "timestamp": datetime.now().isoformat()},
    )
