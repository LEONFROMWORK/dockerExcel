"""
Excel WebSocket Handler
Excel 파일 실시간 업데이트를 위한 WebSocket 핸들러
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional
import json
import asyncio
import logging
from datetime import datetime

from app.core.interfaces import IWebSocketHandler, Context
from app.websocket.progress_reporter import WebSocketManager, ExcelUpdateNotifier
from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.services.ai_chat.context_manager import ContextManager

logger = logging.getLogger(__name__)

class ExcelWebSocketHandler(IWebSocketHandler):
    """Excel WebSocket 핸들러 구현"""
    
    def __init__(self):
        self.manager = WebSocketManager()
        self.notifier = ExcelUpdateNotifier()
        self.context_manager = ContextManager()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def handle_connection(self, websocket: WebSocket, session_id: str):
        """WebSocket 연결 처리"""
        await websocket.accept()
        await self.manager.connect(websocket, session_id)
        
        # 세션 초기화
        self.active_sessions[session_id] = {
            'websocket': websocket,
            'context': self.context_manager.build_context(session_id),
            'connected_at': datetime.now(),
            'last_activity': datetime.now()
        }
        
        # 환영 메시지
        await self.send_welcome_message(websocket, session_id)
        
        try:
            while True:
                # 클라이언트로부터 메시지 수신
                data = await websocket.receive_json()
                await self.handle_message(session_id, data)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket 연결 종료: {session_id}")
        except Exception as e:
            logger.error(f"WebSocket 오류: {str(e)}")
        finally:
            await self.close_connection(session_id)
    
    async def handle_message(self, session_id: str, message: Dict[str, Any]):
        """수신된 메시지 처리"""
        message_type = message.get('type')
        data = message.get('data', {})
        
        # 세션 활동 시간 업데이트
        if session_id in self.active_sessions:
            self.active_sessions[session_id]['last_activity'] = datetime.now()
        
        # 메시지 타입별 처리
        handlers = {
            'check_cell': self.handle_check_cell,
            'fix_error': self.handle_fix_error,
            'analyze_file': self.handle_analyze_file,
            'update_context': self.handle_update_context,
            'ai_query': self.handle_ai_query,
            'ping': self.handle_ping
        }
        
        handler = handlers.get(message_type)
        if handler:
            await handler(session_id, data)
        else:
            await self.send_error(session_id, f"알 수 없는 메시지 타입: {message_type}")
    
    async def handle_check_cell(self, session_id: str, data: Dict[str, Any]):
        """셀 오류 검사 처리"""
        try:
            file_path = data.get('file_path')
            sheet = data.get('sheet')
            cell = data.get('cell')
            
            if not all([file_path, sheet, cell]):
                await self.send_error(session_id, "필수 매개변수가 누락되었습니다")
                return
            
            # 오류 감지
            detector = IntegratedErrorDetector()
            error = await detector.detect_cell_error(file_path, sheet, cell)
            
            if error:
                # 오류 발견 알림
                await self.notifier.notify_error_detected(session_id, {
                    'cell': cell,
                    'sheet': sheet,
                    'error': error.__dict__
                })
            else:
                # 오류 없음 알림
                await self.broadcast(session_id, {
                    'type': 'cell_check_result',
                    'data': {
                        'cell': cell,
                        'sheet': sheet,
                        'has_error': False
                    }
                })
        
        except Exception as e:
            logger.error(f"셀 검사 오류: {str(e)}")
            await self.send_error(session_id, str(e))
    
    async def handle_fix_error(self, session_id: str, data: Dict[str, Any]):
        """오류 수정 요청 처리"""
        try:
            error_id = data.get('error_id')
            auto_apply = data.get('auto_apply', False)
            
            # 수정 처리 (실제 구현 필요)
            # fixer = IntegratedErrorFixer()
            # result = await fixer.fix_error(error_id)
            
            # 임시 응답
            await self.notifier.notify_error_fixed(session_id, {
                'error_id': error_id,
                'status': 'fixed',
                'message': '오류가 수정되었습니다'
            })
            
        except Exception as e:
            logger.error(f"오류 수정 실패: {str(e)}")
            await self.send_error(session_id, str(e))
    
    async def handle_analyze_file(self, session_id: str, data: Dict[str, Any]):
        """파일 분석 요청 처리"""
        try:
            file_path = data.get('file_path')
            options = data.get('options', {})
            
            # 진행 상황 보고기 생성
            from app.websocket.progress_reporter import WebSocketProgressReporter
            progress_reporter = WebSocketProgressReporter(session_id)
            
            # 분석 시작
            await progress_reporter.start_task("파일 분석", 100)
            
            detector = IntegratedErrorDetector(progress_reporter)
            result = await detector.detect_all_errors(file_path)
            
            # 분석 완료
            await progress_reporter.complete_task("파일 분석", result)
            
        except Exception as e:
            logger.error(f"파일 분석 오류: {str(e)}")
            await self.send_error(session_id, str(e))
    
    async def handle_update_context(self, session_id: str, data: Dict[str, Any]):
        """컨텍스트 업데이트 처리"""
        try:
            if session_id in self.active_sessions:
                current_context = self.active_sessions[session_id]['context']
                updated_context = self.context_manager.update_context(current_context, data)
                self.active_sessions[session_id]['context'] = updated_context
                
                await self.broadcast(session_id, {
                    'type': 'context_updated',
                    'data': {
                        'context': updated_context.__dict__
                    }
                })
        
        except Exception as e:
            logger.error(f"컨텍스트 업데이트 오류: {str(e)}")
            await self.send_error(session_id, str(e))
    
    async def handle_ai_query(self, session_id: str, data: Dict[str, Any]):
        """AI 쿼리 처리"""
        try:
            query = data.get('query')
            context = self.active_sessions[session_id]['context']
            
            # AI 처리 (실제 구현 필요)
            # ai_handler = AIChatHandler()
            # response = await ai_handler.process(query, context)
            
            # 임시 응답
            await self.notifier.notify_ai_suggestion(session_id, {
                'query': query,
                'response': 'AI 응답이 여기에 표시됩니다',
                'suggestions': []
            })
            
        except Exception as e:
            logger.error(f"AI 쿼리 처리 오류: {str(e)}")
            await self.send_error(session_id, str(e))
    
    async def handle_ping(self, session_id: str, data: Dict[str, Any]):
        """Ping 메시지 처리 (연결 유지)"""
        await self.broadcast(session_id, {
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        })
    
    async def broadcast(self, session_id: str, message: Dict[str, Any]):
        """메시지 브로드캐스트"""
        await self.manager.send_message(session_id, message)
    
    async def close_connection(self, session_id: str):
        """연결 종료"""
        if session_id in self.active_sessions:
            websocket = self.active_sessions[session_id]['websocket']
            await self.manager.disconnect(websocket, session_id)
            del self.active_sessions[session_id]
    
    async def send_welcome_message(self, websocket: WebSocket, session_id: str):
        """환영 메시지 전송"""
        welcome_message = {
            'type': 'welcome',
            'session_id': session_id,
            'data': {
                'message': 'Excel 실시간 분석 서비스에 연결되었습니다',
                'capabilities': [
                    'real_time_error_detection',
                    'auto_fix_suggestions',
                    'ai_assistance',
                    'progress_tracking'
                ],
                'version': '1.0.0'
            },
            'timestamp': datetime.now().isoformat()
        }
        
        await websocket.send_json(welcome_message)
    
    async def send_error(self, session_id: str, error_message: str):
        """오류 메시지 전송"""
        error_data = {
            'type': 'error',
            'data': {
                'message': error_message
            },
            'timestamp': datetime.now().isoformat()
        }
        
        await self.broadcast(session_id, error_data)
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """활성 세션 목록 반환"""
        return {
            session_id: {
                'connected_at': info['connected_at'].isoformat(),
                'last_activity': info['last_activity'].isoformat(),
                'context': info['context'].__dict__ if hasattr(info['context'], '__dict__') else {}
            }
            for session_id, info in self.active_sessions.items()
        }
    
    async def cleanup_inactive_sessions(self, timeout_minutes: int = 30):
        """비활성 세션 정리"""
        current_time = datetime.now()
        inactive_sessions = []
        
        for session_id, info in self.active_sessions.items():
            if (current_time - info['last_activity']).total_seconds() > timeout_minutes * 60:
                inactive_sessions.append(session_id)
        
        for session_id in inactive_sessions:
            logger.info(f"비활성 세션 정리: {session_id}")
            await self.close_connection(session_id)