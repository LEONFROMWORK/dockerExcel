"""
AI consultation and chat API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import json

from app.core.database import get_db
from app.services.openai_service import openai_service
from app.services.vector_search import vector_search_service
logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class CellContext(BaseModel):
    address: str
    row: int
    col: int
    value: Any
    formula: Optional[str] = None
    format: Optional[Dict[str, Any]] = None
    style: Optional[Dict[str, Any]] = None
    sheetName: Optional[str] = None


class AIConsultationRequest(BaseModel):
    prompt: str
    cell_context: Optional[CellContext] = None
    file_info: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, Any]]] = []


class ExcelProblemRequest(BaseModel):
    problem: str
    context: Optional[Dict[str, Any]] = None
    search_knowledge: bool = True


@router.post("/chat") 
async def ai_consultation(
    request: AIConsultationRequest
) -> Dict[str, Any]:
    """
    AI 상담 엔드포인트 - Excel 셀 컨텍스트와 함께 작동
    """
    try:
        # Build enhanced prompt with cell context
        enhanced_prompt = _build_enhanced_prompt(request.prompt, request.cell_context)
        
        # Build conversation messages
        messages = [
            {
                "role": "system",
                "content": """당신은 Excel/스프레드시트 전문가입니다. 사용자의 Excel 관련 질문에 명확하고 실용적인 답변을 제공해주세요.
                
특히 다음 사항에 중점을 둬주세요:
- 구체적이고 실행 가능한 해결책 제시
- 단계별 설명 제공
- 관련 Excel 함수나 기능 추천
- 셀 컨텍스트가 제공되면 해당 셀의 상황을 고려한 맞춤형 조언
- 한국어로 친근하고 이해하기 쉽게 설명"""
            }
        ]
        
        # Add conversation history
        if request.conversation_history:
            for msg in request.conversation_history[-5:]:  # Last 5 messages
                if msg.get('role') and msg.get('content'):
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
        
        # Add current user message
        messages.append({
            "role": "user", 
            "content": enhanced_prompt
        })
        
        # Search for relevant knowledge - temporarily disabled due to DB issues
        similar_docs = []
        # Vector search is disabled for now due to database connection issues
        
        # Add relevant knowledge to context
        if similar_docs:
            knowledge_context = "\n\n관련 지식:\n"
            for i, doc in enumerate(similar_docs, 1):
                knowledge_context += f"{i}. {doc['content'][:200]}...\n"
            
            messages.insert(1, {
                "role": "system",
                "content": knowledge_context
            })
        
        # Generate AI response
        ai_response = await openai_service.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        # Generate contextual suggestions and follow-up questions
        suggestions = _generate_contextual_suggestions(request.cell_context, request.prompt)
        follow_up_questions = _generate_follow_up_questions(request.cell_context, request.prompt)
        related_cells = _analyze_related_cells(request.cell_context)
        action_items = _generate_action_items(request.cell_context, ai_response)
        
        return {
            "response": ai_response,
            "suggestions": suggestions,
            "follow_up_questions": follow_up_questions,
            "related_cells": related_cells,
            "action_items": action_items,
            "model_used": openai_service.model,
            "cell_context_provided": bool(request.cell_context)
        }
        
    except Exception as e:
        logger.error(f"AI consultation error: {str(e)}")
        # Return fallback response instead of error
        return {
            "response": "죄송합니다. 현재 AI 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도해주세요.",
            "suggestions": [
                "잠시 후 다시 시도해보세요",
                "질문을 더 구체적으로 다시 작성해보세요", 
                "Excel 도움말을 참조해보세요"
            ],
            "follow_up_questions": [
                "다른 방법으로 도움을 드릴까요?",
                "특정 Excel 기능에 대해 궁금한 것이 있나요?"
            ],
            "error": str(e)
        }


@router.post("/chat-legacy")
async def chat_completion_legacy(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate AI chat completion for Excel-related queries
    """
    try:
        # Convert messages to dict format
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Add system message for Excel expertise
        system_message = {
            "role": "system",
            "content": """You are an Excel expert assistant. Help users with Excel-related questions, 
            formulas, data analysis, and troubleshooting. Provide clear, step-by-step solutions 
            and explain complex concepts in simple terms. Always suggest best practices and 
            efficient approaches. Respond in Korean when the user writes in Korean."""
        }
        
        messages.insert(0, system_message)
        
        # Get the latest user message for context
        user_message = next((msg for msg in reversed(messages) if msg["role"] == "user"), None)
        
        if user_message:
            # Search for relevant knowledge
            similar_docs = await vector_search_service.search_similar_documents(
                query=user_message["content"],
                document_type="qa_pair",
                limit=3,
                threshold=0.7,
                db=db
            )
            
            # Add relevant knowledge to context
            if similar_docs:
                knowledge_context = "\n\nRelevant knowledge from database:\n"
                for doc in similar_docs:
                    knowledge_context += f"- {doc['content']}\n"
                
                messages.insert(1, {
                    "role": "system",
                    "content": knowledge_context
                })
        
        # Generate response
        if request.stream:
            # Return streaming response
            return StreamingResponse(
                _stream_chat_response(messages, request.temperature, request.max_tokens),
                media_type="text/event-stream"
            )
        else:
            response = await openai_service.chat_completion(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            return {
                "response": response,
                "session_id": request.session_id,
                "model": openai_service.model
            }
    
    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/solve-problem")
async def solve_excel_problem(
    request: ExcelProblemRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate solution for a specific Excel problem
    """
    try:
        # Search for similar problems/solutions if requested
        related_knowledge = []
        if request.search_knowledge:
            similar_docs = await vector_search_service.search_similar_documents(
                query=request.problem,
                document_type="qa_pair",
                limit=5,
                threshold=0.6,
                db=db
            )
            
            related_knowledge = [
                {
                    "content": doc["content"],
                    "similarity": doc["similarity"]
                }
                for doc in similar_docs
            ]
        
        # Enhance context with related knowledge
        enhanced_context = request.context or {}
        if related_knowledge:
            enhanced_context["related_solutions"] = related_knowledge
        
        # Generate solution
        solution = await openai_service.generate_excel_solution(
            problem_description=request.problem,
            context=enhanced_context
        )
        
        # Index the problem-solution pair for future use
        await vector_search_service.index_document(
            document_id=f"solution_{request.session_id or 'anonymous'}_{hash(request.problem)}",
            document_type="qa_pair",
            content=f"Q: {request.problem}\nA: {solution['solution']}",
            metadata={
                "source": "ai_generated",
                "problem": request.problem,
                "has_context": bool(request.context)
            },
            db=db
        )
        
        return {
            "problem": request.problem,
            "solution": solution["solution"],
            "related_knowledge": related_knowledge,
            "model": solution["model_used"]
        }
    
    except Exception as e:
        logger.error(f"Problem solving error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_chat_response(messages, temperature, max_tokens):
    """
    Stream chat responses for real-time display
    """
    try:
        stream = await openai_service.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


# Helper functions for AI consultation

def _build_enhanced_prompt(prompt: str, cell_context: Optional[CellContext]) -> str:
    """셀 컨텍스트를 포함한 향상된 프롬프트 생성"""
    if not cell_context:
        return prompt
    
    enhanced_prompt = f"{prompt}\n\n"
    enhanced_prompt += f"[셀 정보]\n"
    enhanced_prompt += f"- 위치: {cell_context.address}"
    
    if cell_context.sheetName:
        enhanced_prompt += f" ({cell_context.sheetName} 시트)"
    
    enhanced_prompt += f"\n"
    
    if cell_context.value is not None:
        enhanced_prompt += f"- 현재 값: {cell_context.value}\n"
    
    if cell_context.formula:
        enhanced_prompt += f"- 수식: {cell_context.formula}\n"
    
    return enhanced_prompt


def _generate_contextual_suggestions(cell_context: Optional[CellContext], prompt: str) -> List[str]:
    """셀 컨텍스트 기반 제안 생성"""
    suggestions = []
    
    if not cell_context:
        suggestions = [
            "Excel 함수 참조 가이드 확인하기",
            "데이터 유효성 검사 설정하기",
            "조건부 서식 적용하기"
        ]
    else:
        # Formula-based suggestions
        if cell_context.formula:
            suggestions.extend([
                "수식 오류 검사하기",
                "수식 최적화 방법 알아보기",
                "함수 중첩 단순화하기"
            ])
        
        # Value-based suggestions
        if isinstance(cell_context.value, (int, float)):
            suggestions.extend([
                "숫자 서식 설정하기",
                "차트 만들기",
                "조건부 서식으로 강조하기"
            ])
        elif isinstance(cell_context.value, str):
            if '#' in str(cell_context.value):
                suggestions.extend([
                    "에러 원인 분석하기",
                    "참조 오류 수정하기"
                ])
            else:
                suggestions.extend([
                    "텍스트 함수 활용하기",
                    "데이터 정리하기"
                ])
        
        # General suggestions
        suggestions.extend([
            "셀 보호 설정하기",
            "데이터 검증 규칙 추가하기"
        ])
    
    return suggestions[:5]  # Return top 5 suggestions


def _generate_follow_up_questions(cell_context: Optional[CellContext], prompt: str) -> List[str]:
    """컨텍스트 기반 후속 질문 생성"""
    questions = []
    
    if not cell_context:
        questions = [
            "다른 Excel 기능에 대해 궁금한 것이 있나요?",
            "특정 작업을 자동화하고 싶으신가요?",
            "데이터 분석에 도움이 필요하신가요?"
        ]
    else:
        if cell_context.formula:
            questions.extend([
                "이 수식의 다른 활용 방법을 알고 싶으신가요?",
                "수식 성능을 개선하는 방법이 궁금하신가요?"
            ])
        
        if cell_context.value:
            questions.extend([
                "이 데이터로 다른 분석을 하고 싶으신가요?",
                "관련된 다른 셀들과의 연관성을 확인하고 싶으신가요?"
            ])
        
        questions.extend([
            "이 셀과 관련된 다른 문제가 있나요?",
            "비슷한 작업을 다른 셀에도 적용하고 싶으신가요?"
        ])
    
    return questions[:4]  # Return top 4 questions


def _analyze_related_cells(cell_context: Optional[CellContext]) -> List[str]:
    """관련 셀 분석"""
    if not cell_context or not cell_context.formula:
        return []
    
    # Basic formula parsing to find referenced cells
    related_cells = []
    formula = cell_context.formula
    
    # Simple regex to find cell references (A1, B2, etc.)
    import re
    cell_refs = re.findall(r'[A-Z]+\d+', formula.upper())
    
    # Remove duplicates and current cell
    related_cells = list(set(cell_refs))
    if cell_context.address in related_cells:
        related_cells.remove(cell_context.address)
    
    return related_cells[:5]  # Return top 5 related cells


def _generate_action_items(cell_context: Optional[CellContext], ai_response: str) -> List[Dict[str, str]]:
    """실행 가능한 액션 아이템 생성"""
    action_items = []
    
    if not cell_context:
        return action_items
    
    # Formula-related actions
    if cell_context.formula:
        action_items.append({
            "type": "formula",
            "description": "수식 유효성 검사 실행",
            "code": f"=FORMULATEXT({cell_context.address})"
        })
    
    # Value-related actions
    if isinstance(cell_context.value, (int, float)):
        action_items.append({
            "type": "format",
            "description": "숫자 서식 적용",
            "code": "셀 서식 > 숫자 탭에서 원하는 형식 선택"
        })
        
        action_items.append({
            "type": "chart",
            "description": "차트 생성",
            "code": "삽입 > 차트 > 적절한 차트 유형 선택"
        })
    
    # Error-related actions
    if cell_context.value and '#' in str(cell_context.value):
        action_items.append({
            "type": "data",
            "description": "에러 추적 및 수정",
            "code": "수식 > 수식 계산 > 오류 검사"
        })
    
    return action_items[:3]  # Return top 3 action items