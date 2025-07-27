"""
WebSocket Progress Reporter
실시간 진행 상황 보고를 위한 WebSocket 구현
"""

from typing import Dict, Any, Optional, Set
from app.core.interfaces import IProgressReporter
import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket 연결 관리자 (Singleton)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.active_connections: Dict[str, Set[Any]] = {}
            cls._instance.lock = asyncio.Lock()
        return cls._instance
    
    async def connect(self, websocket: Any, session_id: str):
        """WebSocket 연결 추가"""
        async with self.lock:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = set()
            self.active_connections[session_id].add(websocket)
            logger.info(f"WebSocket 연결됨: {session_id}")
    
    async def disconnect(self, websocket: Any, session_id: str):
        """WebSocket 연결 제거"""
        async with self.lock:
            if session_id in self.active_connections:
                self.active_connections[session_id].discard(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
            logger.info(f"WebSocket 연결 해제: {session_id}")
    
    async def send_message(self, session_id: str, message: Dict[str, Any]):
        """특정 세션에 메시지 전송"""
        if session_id in self.active_connections:
            disconnected = set()
            
            for websocket in self.active_connections[session_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"메시지 전송 실패: {str(e)}")
                    disconnected.add(websocket)
            
            # 연결이 끊긴 WebSocket 제거
            for ws in disconnected:
                await self.disconnect(ws, session_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """모든 연결에 메시지 브로드캐스트"""
        for session_id in list(self.active_connections.keys()):
            await self.send_message(session_id, message)

class WebSocketProgressReporter(IProgressReporter):
    """WebSocket을 통한 진행 상황 보고"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.manager = WebSocketManager()
        self.current_task = None
        self.start_time = None
    
    async def report_progress(self, current: int, total: int, message: str = ""):
        """진행 상황 보고"""
        if self.start_time is None:
            self.start_time = datetime.now()
        
        progress_data = {
            "type": "progress",
            "session_id": self.session_id,
            "data": {
                "current": current,
                "total": total,
                "percentage": round((current / total * 100) if total > 0 else 0, 2),
                "message": message,
                "task": self.current_task,
                "elapsed_time": (datetime.now() - self.start_time).total_seconds()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await self.manager.send_message(self.session_id, progress_data)
        logger.debug(f"진행 상황 보고: {current}/{total} - {message}")
    
    async def report_error(self, error: Exception):
        """오류 보고"""
        error_data = {
            "type": "error",
            "session_id": self.session_id,
            "data": {
                "error_type": type(error).__name__,
                "message": str(error),
                "task": self.current_task
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await self.manager.send_message(self.session_id, error_data)
        logger.error(f"오류 보고: {str(error)}")
    
    async def start_task(self, task_name: str, total_steps: int = 0):
        """새 작업 시작"""
        self.current_task = task_name
        self.start_time = datetime.now()
        
        start_data = {
            "type": "task_start",
            "session_id": self.session_id,
            "data": {
                "task": task_name,
                "total_steps": total_steps
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await self.manager.send_message(self.session_id, start_data)
        logger.info(f"작업 시작: {task_name}")
    
    async def complete_task(self, task_name: str, result: Optional[Dict[str, Any]] = None):
        """작업 완료"""
        complete_data = {
            "type": "task_complete",
            "session_id": self.session_id,
            "data": {
                "task": task_name,
                "result": result,
                "duration": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await self.manager.send_message(self.session_id, complete_data)
        logger.info(f"작업 완료: {task_name}")
        
        self.current_task = None
        self.start_time = None

class ExcelUpdateNotifier:
    """Excel 파일 업데이트 알림"""
    
    def __init__(self):
        self.manager = WebSocketManager()
    
    async def notify_error_detected(self, session_id: str, error_data: Dict[str, Any]):
        """오류 감지 알림"""
        notification = {
            "type": "error_detected",
            "session_id": session_id,
            "data": error_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.manager.send_message(session_id, notification)
    
    async def notify_error_fixed(self, session_id: str, fix_data: Dict[str, Any]):
        """오류 수정 알림"""
        notification = {
            "type": "error_fixed",
            "session_id": session_id,
            "data": fix_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.manager.send_message(session_id, notification)
    
    async def notify_cell_update(self, session_id: str, cell_data: Dict[str, Any]):
        """셀 업데이트 알림"""
        notification = {
            "type": "cell_update",
            "session_id": session_id,
            "data": cell_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.manager.send_message(session_id, notification)
    
    async def notify_ai_suggestion(self, session_id: str, suggestion: Dict[str, Any]):
        """AI 제안 알림"""
        notification = {
            "type": "ai_suggestion",
            "session_id": session_id,
            "data": suggestion,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.manager.send_message(session_id, notification)