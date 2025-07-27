"""
AI Chat Handler
AI 채팅 핸들러 구현 - Excel 오류 분석 및 수정 제안
"""

from typing import Dict, Any, List, Optional
from app.core.interfaces import IAIProcessor, Context, ExcelError, ProcessingTier
from app.services.openai_service import OpenAIService
from app.services.ai_chat.context_manager import ContextManager
from app.core.config import settings
from app.core.exceptions import AIServiceError
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AIChatHandler(IAIProcessor):
    """AI 채팅 핸들러"""
    
    def __init__(self):
        self.openai_service = OpenAIService()
        self.context_manager = ContextManager()
        self.tier = ProcessingTier.FAST_AI
        
        # 프롬프트 템플릿
        self.system_prompt = """당신은 Excel 파일 분석 및 오류 수정 전문가입니다.
사용자의 Excel 파일에서 발견된 오류를 분석하고, 적절한 수정 방법을 제안해주세요.

다음 지침을 따라주세요:
1. 오류의 원인을 명확하게 설명
2. 구체적인 수정 방법 제시
3. 수정 후 예상 결과 설명
4. 추가 주의사항이나 팁 제공
5. 한국어로 친절하게 응답"""
    
    async def process(self, query: str, context: Context) -> Dict[str, Any]:
        """AI 쿼리 처리"""
        try:
            # 관련 컨텍스트 추출
            relevant_context = self.context_manager.get_relevant_context(context)
            
            # 쿼리 타입 분석
            query_type = self._analyze_query_type(query)
            
            # 타입에 따른 처리
            if query_type == "error_fix":
                return await self._handle_error_fix_query(query, relevant_context)
            elif query_type == "error_analysis":
                return await self._handle_error_analysis_query(query, relevant_context)
            elif query_type == "general_help":
                return await self._handle_general_help_query(query, relevant_context)
            else:
                return await self._handle_general_query(query, relevant_context)
                
        except Exception as e:
            logger.error(f"AI 쿼리 처리 오류: {str(e)}")
            raise AIServiceError(
                f"AI 처리 중 오류 발생: {str(e)}",
                code="AI_PROCESSING_ERROR"
            )
    
    def get_tier(self) -> int:
        """처리 티어 반환"""
        return self.tier.value
    
    def get_cost_estimate(self, query: str) -> float:
        """예상 비용 계산 (토큰 기반)"""
        # 대략적인 토큰 수 추정
        estimated_tokens = len(query) / 4 + 500  # 응답 포함
        
        # GPT-3.5 기준 비용 (실제 비용은 다를 수 있음)
        cost_per_1k_tokens = 0.002
        
        return (estimated_tokens / 1000) * cost_per_1k_tokens
    
    async def get_fix_suggestion(self, error: ExcelError, context: Dict[str, Any]) -> Dict[str, Any]:
        """특정 오류에 대한 수정 제안"""
        try:
            prompt = self._build_fix_suggestion_prompt(error, context)
            
            response = await self.openai_service.get_completion(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.3,  # 더 일관된 응답을 위해 낮은 temperature
                max_tokens=1000
            )
            
            # 응답 파싱
            suggestion = self._parse_fix_suggestion(response, error)
            
            return suggestion
            
        except Exception as e:
            logger.error(f"수정 제안 생성 오류: {str(e)}")
            return {
                'error': str(e),
                'suggestion': None
            }
    
    # Private methods
    def _analyze_query_type(self, query: str) -> str:
        """쿼리 타입 분석"""
        query_lower = query.lower()
        
        # 키워드 기반 분류
        if any(keyword in query_lower for keyword in ['수정', '고치', 'fix', '해결']):
            return "error_fix"
        elif any(keyword in query_lower for keyword in ['분석', '원인', '왜', 'why']):
            return "error_analysis"
        elif any(keyword in query_lower for keyword in ['도움', '설명', 'help', '방법']):
            return "general_help"
        else:
            return "general"
    
    async def _handle_error_fix_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """오류 수정 관련 쿼리 처리"""
        # 현재 셀의 오류 찾기
        current_errors = self._get_current_cell_errors(context)
        
        if not current_errors:
            return {
                'response': "현재 선택된 셀에서 오류를 찾을 수 없습니다. 오류가 있는 셀을 선택해주세요.",
                'suggestions': [],
                'error_references': []
            }
        
        # 각 오류에 대한 수정 제안 생성
        suggestions = []
        for error in current_errors:
            suggestion = await self.get_fix_suggestion(error, context)
            if suggestion and 'suggestion' in suggestion:
                suggestions.append(suggestion['suggestion'])
        
        # 종합 응답 생성
        prompt = f"""
사용자 질문: {query}

현재 셀의 오류:
{json.dumps([e.__dict__ for e in current_errors], ensure_ascii=False, indent=2)}

위 오류들에 대한 수정 방법을 설명해주세요.
"""
        
        response = await self.openai_service.get_completion(
            prompt=prompt,
            system_prompt=self.system_prompt,
            temperature=0.5
        )
        
        return {
            'response': response,
            'suggestions': suggestions,
            'error_references': current_errors
        }
    
    async def _handle_error_analysis_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """오류 분석 관련 쿼리 처리"""
        recent_errors = context.get('recent_errors', [])
        
        if not recent_errors:
            return {
                'response': "분석할 오류가 없습니다. Excel 파일을 업로드하고 분석을 실행해주세요.",
                'suggestions': [],
                'error_references': []
            }
        
        prompt = f"""
사용자 질문: {query}

최근 발견된 오류들:
{json.dumps(recent_errors, ensure_ascii=False, indent=2)}

파일 요약:
{json.dumps(context.get('file_summary', {}), ensure_ascii=False, indent=2)}

위 정보를 바탕으로 오류를 분석하고 설명해주세요.
"""
        
        response = await self.openai_service.get_completion(
            prompt=prompt,
            system_prompt=self.system_prompt
        )
        
        return {
            'response': response,
            'suggestions': [],
            'error_references': recent_errors
        }
    
    async def _handle_general_help_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """일반 도움말 쿼리 처리"""
        prompt = f"""
사용자 질문: {query}

현재 상황:
- 선택된 셀: {context.get('current_cell', '없음')}
- 총 오류 수: {len(context.get('recent_errors', []))}
- 현재 작업: {context.get('current_operation', '없음')}

Excel 오류 수정과 관련된 도움말을 제공해주세요.
"""
        
        response = await self.openai_service.get_completion(
            prompt=prompt,
            system_prompt=self.system_prompt
        )
        
        return {
            'response': response,
            'suggestions': [],
            'error_references': []
        }
    
    async def _handle_general_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """일반 쿼리 처리"""
        prompt = f"""
사용자 질문: {query}

컨텍스트:
{json.dumps(context, ensure_ascii=False, indent=2)}

위 정보를 참고하여 사용자의 질문에 답변해주세요.
"""
        
        response = await self.openai_service.get_completion(
            prompt=prompt,
            system_prompt=self.system_prompt
        )
        
        return {
            'response': response,
            'suggestions': [],
            'error_references': []
        }
    
    def _get_current_cell_errors(self, context: Dict[str, Any]) -> List[ExcelError]:
        """현재 셀의 오류 가져오기"""
        current_cell = context.get('current_cell')
        if not current_cell:
            return []
        
        # recent_errors에서 현재 셀의 오류 찾기
        recent_errors = context.get('recent_errors', [])
        cell_errors = []
        
        for error_data in recent_errors:
            if isinstance(error_data, dict) and error_data.get('cell') == current_cell:
                # 딕셔너리를 ExcelError 객체로 변환
                cell_errors.append(self._dict_to_error(error_data))
        
        return cell_errors
    
    def _dict_to_error(self, error_dict: Dict[str, Any]) -> ExcelError:
        """딕셔너리를 ExcelError 객체로 변환"""
        from app.core.interfaces import ExcelError
        
        return ExcelError(
            id=error_dict.get('id', ''),
            type=error_dict.get('type', ''),
            sheet=error_dict.get('sheet', ''),
            cell=error_dict.get('cell', ''),
            formula=error_dict.get('formula'),
            value=error_dict.get('value'),
            message=error_dict.get('message', ''),
            severity=error_dict.get('severity', 'medium'),
            is_auto_fixable=error_dict.get('is_auto_fixable', False),
            suggested_fix=error_dict.get('suggested_fix'),
            confidence=error_dict.get('confidence', 0.0)
        )
    
    def _build_fix_suggestion_prompt(self, error: ExcelError, context: Dict[str, Any]) -> str:
        """수정 제안 프롬프트 생성"""
        return f"""
Excel 오류 정보:
- 타입: {error.type}
- 위치: {error.sheet}!{error.cell}
- 수식: {error.formula}
- 현재 값: {error.value}
- 오류 메시지: {error.message}

이 오류를 수정하는 구체적인 방법을 제안해주세요.
수정된 수식과 설명을 포함해주세요.
"""
    
    def _parse_fix_suggestion(self, response: str, error: ExcelError) -> Dict[str, Any]:
        """AI 응답에서 수정 제안 파싱"""
        # 간단한 파싱 로직 (실제로는 더 정교한 파싱 필요)
        suggestion = {
            'id': f"suggestion_{error.id}",
            'error_id': error.id,
            'original': error.formula,
            'fixed': None,  # AI 응답에서 추출 필요
            'explanation': response,
            'confidence': 0.8  # AI 제안의 기본 신뢰도
        }
        
        # 수식 추출 시도 (=로 시작하는 부분 찾기)
        import re
        formula_match = re.search(r'=\s*[^\n]+', response)
        if formula_match:
            suggestion['fixed'] = formula_match.group(0).strip()
        
        return suggestion