"""
AI Chat Context Manager
AI 채팅 컨텍스트 관리자 구현
"""

from typing import Dict, Any, List, Optional
from app.core.interfaces import IContextBuilder, Context, ExcelError
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class ContextManager(IContextBuilder):
    """AI 채팅 컨텍스트 관리자"""
    
    def __init__(self):
        self.active_contexts: Dict[str, Context] = {}
        self.max_history_size = 50  # 최대 히스토리 크기
    
    def build_context(self, session_id: str) -> Context:
        """새로운 컨텍스트 생성"""
        context = Context(
            session_id=session_id,
            file_info={},
            selected_cell=None,
            detected_errors=[],
            user_history=[],
            current_operation=None
        )
        
        # 컨텍스트 저장
        self.active_contexts[session_id] = context
        logger.info(f"새 컨텍스트 생성: {session_id}")
        
        return context
    
    def update_context(self, context: Context, update_data: Dict[str, Any]) -> Context:
        """컨텍스트 업데이트"""
        try:
            # 파일 정보 업데이트
            if 'file_info' in update_data:
                context.file_info.update(update_data['file_info'])
            
            # 선택된 셀 업데이트
            if 'selected_cell' in update_data:
                context.selected_cell = update_data['selected_cell']
            
            # 감지된 오류 업데이트
            if 'detected_errors' in update_data:
                if isinstance(update_data['detected_errors'], list):
                    context.detected_errors = update_data['detected_errors']
                else:
                    # 단일 오류 추가
                    context.detected_errors.append(update_data['detected_errors'])
            
            # 현재 작업 업데이트
            if 'current_operation' in update_data:
                context.current_operation = update_data['current_operation']
            
            # 사용자 히스토리 추가
            if 'user_action' in update_data:
                self._add_to_history(context, update_data['user_action'])
            
            # 컨텍스트 저장
            self.active_contexts[context.session_id] = context
            
            return context
            
        except Exception as e:
            logger.error(f"컨텍스트 업데이트 오류: {str(e)}")
            return context
    
    def get_context(self, session_id: str) -> Optional[Context]:
        """저장된 컨텍스트 가져오기"""
        return self.active_contexts.get(session_id)
    
    def remove_context(self, session_id: str):
        """컨텍스트 제거"""
        if session_id in self.active_contexts:
            del self.active_contexts[session_id]
            logger.info(f"컨텍스트 제거: {session_id}")
    
    def get_relevant_context(self, context: Context) -> Dict[str, Any]:
        """AI 처리를 위한 관련 컨텍스트 추출"""
        relevant = {
            'session_id': context.session_id,
            'current_cell': context.selected_cell,
            'recent_errors': self._get_recent_errors(context),
            'recent_actions': self._get_recent_actions(context),
            'file_summary': self._get_file_summary(context),
            'current_operation': context.current_operation
        }
        
        return relevant
    
    def serialize_context(self, context: Context) -> str:
        """컨텍스트를 JSON으로 직렬화"""
        try:
            data = {
                'session_id': context.session_id,
                'file_info': context.file_info,
                'selected_cell': context.selected_cell,
                'detected_errors': [self._serialize_error(e) for e in context.detected_errors],
                'user_history': context.user_history[-10:],  # 최근 10개만
                'current_operation': context.current_operation,
                'timestamp': datetime.now().isoformat()
            }
            
            return json.dumps(data, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"컨텍스트 직렬화 오류: {str(e)}")
            return "{}"
    
    def deserialize_context(self, data: str) -> Optional[Context]:
        """JSON에서 컨텍스트 역직렬화"""
        try:
            parsed = json.loads(data)
            
            context = Context(
                session_id=parsed['session_id'],
                file_info=parsed['file_info'],
                selected_cell=parsed.get('selected_cell'),
                detected_errors=[],  # 오류 객체는 별도 처리 필요
                user_history=parsed.get('user_history', []),
                current_operation=parsed.get('current_operation')
            )
            
            return context
            
        except Exception as e:
            logger.error(f"컨텍스트 역직렬화 오류: {str(e)}")
            return None
    
    # Private methods
    def _add_to_history(self, context: Context, action: Dict[str, Any]):
        """사용자 히스토리에 액션 추가"""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action
        }
        
        context.user_history.append(history_entry)
        
        # 최대 크기 유지
        if len(context.user_history) > self.max_history_size:
            context.user_history = context.user_history[-self.max_history_size:]
    
    def _get_recent_errors(self, context: Context, limit: int = 5) -> List[Dict[str, Any]]:
        """최근 오류 가져오기"""
        recent_errors = context.detected_errors[-limit:] if context.detected_errors else []
        return [self._serialize_error(e) for e in recent_errors]
    
    def _get_recent_actions(self, context: Context, limit: int = 5) -> List[Dict[str, Any]]:
        """최근 액션 가져오기"""
        return context.user_history[-limit:] if context.user_history else []
    
    def _get_file_summary(self, context: Context) -> Dict[str, Any]:
        """파일 요약 정보"""
        if not context.file_info:
            return {}
        
        return {
            'name': context.file_info.get('name', 'Unknown'),
            'sheets': context.file_info.get('sheets', []),
            'total_errors': len(context.detected_errors),
            'error_types': self._count_error_types(context.detected_errors)
        }
    
    def _count_error_types(self, errors: List[ExcelError]) -> Dict[str, int]:
        """오류 타입별 개수 집계"""
        counts = {}
        for error in errors:
            counts[error.type] = counts.get(error.type, 0) + 1
        return counts
    
    def _serialize_error(self, error: ExcelError) -> Dict[str, Any]:
        """오류 객체 직렬화"""
        if hasattr(error, '__dict__'):
            return error.__dict__
        
        # ExcelError 데이터클래스인 경우
        return {
            'id': error.id,
            'type': error.type,
            'sheet': error.sheet,
            'cell': error.cell,
            'formula': error.formula,
            'value': str(error.value) if error.value else None,
            'message': error.message,
            'severity': error.severity,
            'is_auto_fixable': error.is_auto_fixable,
            'suggested_fix': error.suggested_fix,
            'confidence': error.confidence
        }