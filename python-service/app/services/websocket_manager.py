"""
WebSocket 연결 관리 및 실시간 진행률 전송
WebSocket Manager for Real-time Progress Updates
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
import uuid

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        # 활성 WebSocket 연결들
        self.active_connections: Dict[str, WebSocket] = {}
        # 사용자별 연결 매핑
        self.user_connections: Dict[str, List[str]] = {}
        # 작업별 연결 매핑  
        self.task_connections: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str = None, 
                     user_id: str = None, task_id: str = None) -> str:
        """WebSocket 연결 수락 및 등록"""
        
        await websocket.accept()
        
        # 연결 ID 생성
        if not connection_id:
            connection_id = str(uuid.uuid4())
        
        # 연결 저장
        self.active_connections[connection_id] = websocket
        
        # 사용자별 연결 매핑
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(connection_id)
        
        # 작업별 연결 매핑
        if task_id:
            if task_id not in self.task_connections:
                self.task_connections[task_id] = []
            self.task_connections[task_id].append(connection_id)
        
        logger.info(f"WebSocket 연결 수락: {connection_id} (user: {user_id}, task: {task_id})")
        
        # 연결 확인 메시지 전송
        await self.send_to_connection(connection_id, {
            "type": "connection_established",
            "connection_id": connection_id,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        return connection_id
    
    def disconnect(self, connection_id: str):
        """WebSocket 연결 해제"""
        
        if connection_id in self.active_connections:
            # 연결 제거
            del self.active_connections[connection_id]
            
            # 사용자별 매핑에서 제거
            for user_id, connections in self.user_connections.items():
                if connection_id in connections:
                    connections.remove(connection_id)
                    if not connections:  # 빈 리스트면 삭제
                        del self.user_connections[user_id]
                    break
            
            # 작업별 매핑에서 제거
            for task_id, connections in self.task_connections.items():
                if connection_id in connections:
                    connections.remove(connection_id)
                    if not connections:  # 빈 리스트면 삭제
                        del self.task_connections[task_id]
                    break
            
            logger.info(f"WebSocket 연결 해제: {connection_id}")
    
    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """특정 연결에 메시지 전송"""
        
        if connection_id not in self.active_connections:
            return False
        
        try:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"메시지 전송 실패 (연결 {connection_id}): {str(e)}")
            # 연결이 끊어진 경우 정리
            self.disconnect(connection_id)
            return False
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """특정 사용자의 모든 연결에 메시지 전송"""
        
        if user_id not in self.user_connections:
            return 0
        
        connections = self.user_connections[user_id].copy()  # 복사본 사용
        sent_count = 0
        
        for connection_id in connections:
            if await self.send_to_connection(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def send_to_task(self, task_id: str, message: Dict[str, Any]) -> int:
        """특정 작업을 추적하는 모든 연결에 메시지 전송"""
        
        if task_id not in self.task_connections:
            return 0
        
        connections = self.task_connections[task_id].copy()  # 복사본 사용
        sent_count = 0
        
        for connection_id in connections:
            if await self.send_to_connection(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def broadcast(self, message: Dict[str, Any], exclude_connections: List[str] = None) -> int:
        """모든 연결에 메시지 브로드캐스트"""
        
        exclude_connections = exclude_connections or []
        sent_count = 0
        
        for connection_id in list(self.active_connections.keys()):
            if connection_id not in exclude_connections:
                if await self.send_to_connection(connection_id, message):
                    sent_count += 1
        
        return sent_count
    
    async def send_progress_update(self, task_id: str, progress_data: Dict[str, Any]):
        """진행률 업데이트 전송"""
        
        message = {
            "type": "progress_update",
            "task_id": task_id,
            "data": progress_data,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        sent_count = await self.send_to_task(task_id, message)
        
        if sent_count > 0:
            logger.debug(f"진행률 업데이트 전송: {task_id} -> {sent_count}개 연결")
        
        return sent_count
    
    async def send_task_completion(self, task_id: str, result_data: Dict[str, Any]):
        """작업 완료 알림 전송"""
        
        message = {
            "type": "task_completed",
            "task_id": task_id,
            "data": result_data,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        sent_count = await self.send_to_task(task_id, message)
        
        if sent_count > 0:
            logger.info(f"작업 완료 알림 전송: {task_id} -> {sent_count}개 연결")
        
        return sent_count
    
    async def send_task_error(self, task_id: str, error_data: Dict[str, Any]):
        """작업 오류 알림 전송"""
        
        message = {
            "type": "task_failed",
            "task_id": task_id,
            "data": error_data,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        sent_count = await self.send_to_task(task_id, message)
        
        if sent_count > 0:
            logger.error(f"작업 오류 알림 전송: {task_id} -> {sent_count}개 연결")
        
        return sent_count
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """연결 통계 정보"""
        
        return {
            "total_connections": len(self.active_connections),
            "users_connected": len(self.user_connections),
            "tasks_being_tracked": len(self.task_connections),
            "connection_details": {
                "active_connections": list(self.active_connections.keys()),
                "user_connections": {
                    user_id: len(connections) 
                    for user_id, connections in self.user_connections.items()
                },
                "task_connections": {
                    task_id: len(connections)
                    for task_id, connections in self.task_connections.items()
                }
            }
        }
    
    async def cleanup_inactive_connections(self):
        """비활성 연결 정리"""
        
        inactive_connections = []
        
        for connection_id, websocket in list(self.active_connections.items()):
            try:
                # ping 메시지로 연결 상태 확인
                await websocket.ping()
            except Exception:
                inactive_connections.append(connection_id)
        
        # 비활성 연결 제거
        for connection_id in inactive_connections:
            self.disconnect(connection_id)
        
        if inactive_connections:
            logger.info(f"비활성 연결 {len(inactive_connections)}개 정리 완료")
        
        return len(inactive_connections)


# 전역 WebSocket 매니저 인스턴스
websocket_manager = WebSocketManager()


class ProgressWebSocketHandler:
    """진행률 추적 WebSocket 핸들러"""
    
    def __init__(self, websocket: WebSocket, connection_id: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.is_active = True
    
    async def handle_connection(self):
        """WebSocket 연결 처리"""
        
        try:
            while self.is_active:
                # 클라이언트로부터 메시지 수신
                data = await self.websocket.receive_text()
                message = json.loads(data)
                
                await self.handle_message(message)
                
        except WebSocketDisconnect:
            logger.info(f"클라이언트 연결 해제: {self.connection_id}")
        except Exception as e:
            logger.error(f"WebSocket 처리 오류 ({self.connection_id}): {str(e)}")
        finally:
            self.is_active = False
            websocket_manager.disconnect(self.connection_id)
    
    async def handle_message(self, message: Dict[str, Any]):
        """클라이언트 메시지 처리"""
        
        message_type = message.get("type")
        
        if message_type == "subscribe_task":
            # 특정 작업 구독
            task_id = message.get("task_id")
            if task_id:
                if task_id not in websocket_manager.task_connections:
                    websocket_manager.task_connections[task_id] = []
                
                if self.connection_id not in websocket_manager.task_connections[task_id]:
                    websocket_manager.task_connections[task_id].append(self.connection_id)
                
                await websocket_manager.send_to_connection(self.connection_id, {
                    "type": "subscription_confirmed",
                    "task_id": task_id
                })
        
        elif message_type == "unsubscribe_task":
            # 작업 구독 해제
            task_id = message.get("task_id")
            if task_id and task_id in websocket_manager.task_connections:
                if self.connection_id in websocket_manager.task_connections[task_id]:
                    websocket_manager.task_connections[task_id].remove(self.connection_id)
                
                await websocket_manager.send_to_connection(self.connection_id, {
                    "type": "unsubscription_confirmed",
                    "task_id": task_id
                })
        
        elif message_type == "ping":
            # Ping 응답
            await websocket_manager.send_to_connection(self.connection_id, {
                "type": "pong",
                "timestamp": asyncio.get_event_loop().time()
            })
        
        else:
            logger.warning(f"알 수 없는 메시지 타입: {message_type}")


# 진행률 추적과 WebSocket 연동을 위한 헬퍼 함수들
async def notify_progress_update(task_id: str, progress_data: Dict[str, Any]):
    """진행률 업데이트 알림"""
    await websocket_manager.send_progress_update(task_id, progress_data)


async def notify_task_completion(task_id: str, result_data: Dict[str, Any]):
    """작업 완료 알림"""
    await websocket_manager.send_task_completion(task_id, result_data)


async def notify_task_error(task_id: str, error_data: Dict[str, Any]):
    """작업 오류 알림"""
    await websocket_manager.send_task_error(task_id, error_data)