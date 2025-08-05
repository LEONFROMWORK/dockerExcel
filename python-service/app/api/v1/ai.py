"""
AI consultation and chat API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import json

from app.core.database import get_db
from app.services.openai_service import openai_service
from app.services.rate_limiter import rate_limit, RateLimitTier
from app.services.vector_search import vector_search_service
from app.core.validators import InputSanitizer, validate_session_id
from app.services.ai_chat_helpers import (
    build_enhanced_prompt,
    generate_contextual_suggestions,
    generate_follow_up_questions,
    analyze_related_cells,
    generate_action_items,
)
from app.services.context import get_enhanced_context_manager
from app.core.responses import ResponseBuilder
from app.core.types import AIConsultationResponse

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
    prompt: str = Field(..., min_length=1, max_length=5000)
    cell_context: Optional[CellContext] = None
    file_info: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=[], max_items=50
    )
    session_id: Optional[str] = Field(None, regex=r"^[a-zA-Z0-9\-_]+$", max_length=128)


class ExcelProblemRequest(BaseModel):
    problem: str
    context: Optional[Dict[str, Any]] = None
    search_knowledge: bool = True


class MultiCellAnalysisRequest(BaseModel):
    """Request model for multi-cell analysis with context"""

    cells: List[CellContext]
    selection_type: str  # "range", "multiple", "column", "row"
    cell_range: Optional[str] = None  # e.g., "A1:C10"
    question: str
    file_id: str
    session_id: Optional[str] = None
    file_info: Optional[Dict[str, Any]] = None


class CellSelectionAnalysis(BaseModel):
    """Analysis result for cell selection"""

    individual_errors: List[Dict[str, Any]]
    cross_cell_issues: List[Dict[str, Any]]
    pattern_insights: Dict[str, Any]
    statistics: Optional[Dict[str, Any]] = None
    data_types: Dict[str, int]
    detected_patterns: List[str]


@router.post("/chat")
@rate_limit(tier=RateLimitTier.FREE, endpoint="/api/v1/ai/chat")
async def ai_consultation(
    request: AIConsultationRequest, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    AI 상담 엔드포인트 - Excel 셀 컨텍스트와 함께 작동
    """
    try:
        # 입력 검증 및 정제
        sanitized_prompt = InputSanitizer.sanitize_string(
            request.prompt, max_length=5000
        )

        # 세션 ID 검증
        if request.session_id and not validate_session_id(request.session_id):
            raise HTTPException(status_code=400, detail="Invalid session ID format")
        # Get enhanced context if session_id is provided
        enhanced_context = None
        if request.session_id:
            from app.services.context import get_enhanced_context_manager

            context_manager = get_enhanced_context_manager()
            enhanced_context = await context_manager.get_enhanced_context(
                request.session_id
            )

            # Update file_info from context if not provided
            if not request.file_info and enhanced_context.get("workbook_context"):
                wb_context = enhanced_context["workbook_context"]
                request.file_info = {
                    "fileId": wb_context.get("file_id"),
                    "fileName": wb_context.get("file_name"),
                }

            # Log context availability
            if enhanced_context.get("workbook_context"):
                logger.info(f"Using workbook context for session: {request.session_id}")

        # Build enhanced prompt with cell context
        enhanced_prompt = build_enhanced_prompt(request.prompt, request.cell_context)

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
- 한국어로 친근하고 이해하기 쉽게 설명""",
            }
        ]

        # Add conversation history
        if request.conversation_history:
            for msg in request.conversation_history[-5:]:  # Last 5 messages
                if msg.get("role") and msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current user message
        messages.append({"role": "user", "content": enhanced_prompt})

        # Search for file context and relevant knowledge
        file_context = None
        detector_errors = []
        qa_knowledge = []

        try:
            # 1. Search for file analysis context if file_info is provided
            if request.file_info and request.file_info.get("fileId"):
                file_id = request.file_info.get("fileId")

                # Try to get IntegratedErrorDetector results from cache first
                from app.core.integrated_cache import integrated_cache

                cached_errors = await integrated_cache.get_errors(file_id)
                if cached_errors:
                    detector_errors = cached_errors
                    logger.info(
                        f"Found cached IntegratedErrorDetector results for: {file_id}"
                    )

                # Search vector store for file analysis
                search_query = request.file_info.get("fileName", file_id)
                file_docs = await vector_search_service.search_similar_documents(
                    query=search_query,
                    document_type="excel_analysis",
                    limit=1,
                    threshold=0.3,  # Lower threshold for file matching
                    db=db,
                )
                if file_docs:
                    file_context = file_docs[0]["content"]
                    logger.info(f"Found file context for: {search_query}")

            # 2. Search for Q&A knowledge relevant to the prompt
            qa_knowledge = await vector_search_service.search_similar_documents(
                query=request.prompt,
                document_type="qa_pair",
                limit=3,
                threshold=0.7,
                db=db,
            )
        except Exception as e:
            logger.warning(f"Vector search error (non-critical): {str(e)}")

        # Add file context and errors as primary context
        if file_context or detector_errors:
            context_parts = ["[현재 Excel 파일 컨텍스트]"]

            # Add file analysis context
            if file_context:
                context_parts.append(file_context)

            # Add IntegratedErrorDetector errors if relevant to current cell
            if detector_errors and request.cell_context:
                current_sheet = request.cell_context.get("sheet", "Sheet1")
                current_cell = request.cell_context.get("address")

                # Find errors related to current cell or sheet
                relevant_errors = []
                for error in detector_errors:
                    if isinstance(error, dict):
                        if error.get("sheet") == current_sheet:
                            if error.get("cell") == current_cell:
                                relevant_errors.insert(
                                    0, error
                                )  # Current cell errors first
                            else:
                                relevant_errors.append(error)

                if relevant_errors:
                    context_parts.append("\n[감지된 오류 정보]")
                    for i, error in enumerate(relevant_errors[:5], 1):  # Top 5 errors
                        context_parts.append(
                            f"{i}. {error.get('type')}: {error.get('cell')} - {error.get('message')}"
                        )
                        if error.get("suggested_fix"):
                            context_parts.append(
                                f"   수정 제안: {error.get('suggested_fix')}"
                            )

            context_parts.append(
                "\n위 파일의 전체 구조와 오류 정보를 참고하여 답변해주세요."
            )

            messages.insert(1, {"role": "system", "content": "\n".join(context_parts)})

        # Add Q&A knowledge as secondary context
        if qa_knowledge:
            knowledge_content = "\n[참고 지식]\n"
            for i, doc in enumerate(qa_knowledge, 1):
                knowledge_content += f"{i}. {doc['content'][:200]}...\n"

            messages.insert(
                2 if file_context else 1,
                {"role": "system", "content": knowledge_content},
            )

        # Generate AI response
        ai_response = await openai_service.chat_completion(
            messages=messages, temperature=0.7, max_tokens=1000
        )

        # Generate contextual suggestions and follow-up questions
        suggestions = generate_contextual_suggestions(
            request.cell_context, request.prompt
        )
        follow_up_questions = generate_follow_up_questions(
            request.cell_context, request.prompt
        )
        related_cells = analyze_related_cells(request.cell_context)
        action_items = generate_action_items(request.cell_context, ai_response)

        # 표준 AI 상담 응답
        consultation_response: AIConsultationResponse = {
            "response": ai_response,
            "suggestions": suggestions,
            "follow_up_questions": follow_up_questions,
            "related_cells": related_cells,
            "action_items": action_items,
            "model_used": openai_service.model,
            "cell_context_provided": bool(request.cell_context),
        }

        return ResponseBuilder.success(
            data=consultation_response, message="AI 상담이 성공적으로 완료되었습니다."
        )

    except Exception as e:
        logger.error(f"AI consultation error: {str(e)}")
        # 폴백 응답 반환
        fallback_response: AIConsultationResponse = {
            "response": "죄송합니다. 현재 AI 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도해주세요.",
            "suggestions": [
                {"type": "retry", "text": "잠시 후 다시 시도해보세요"},
                {"type": "clarify", "text": "질문을 더 구체적으로 다시 작성해보세요"},
                {"type": "help", "text": "Excel 도움말을 참조해보세요"},
            ],
            "follow_up_questions": [
                "다른 방법으로 도움을 드릴까요?",
                "특정 Excel 기능에 대해 궁금한 것이 있나요?",
            ],
            "related_cells": [],
            "action_items": [],
            "model_used": "fallback",
            "cell_context_provided": bool(request.cell_context),
        }

        return ResponseBuilder.error(
            message="AI 상담 처리 중 오류가 발생했습니다.",
            error_code="AI_CONSULTATION_ERROR",
            details={"fallback_response": fallback_response},
        )


@router.post("/chat-legacy")
@rate_limit(tier=RateLimitTier.FREE, endpoint="/api/v1/ai/chat-legacy")
async def chat_completion_legacy(
    request: ChatRequest, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate AI chat completion for Excel-related queries
    """
    try:
        # Convert messages to dict format
        messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Add system message for Excel expertise
        system_message = {
            "role": "system",
            "content": """You are an Excel expert assistant. Help users with Excel-related questions,
            formulas, data analysis, and troubleshooting. Provide clear, step-by-step solutions
            and explain complex concepts in simple terms. Always suggest best practices and
            efficient approaches. Respond in Korean when the user writes in Korean.""",
        }

        messages.insert(0, system_message)

        # Get the latest user message for context
        user_message = next(
            (msg for msg in reversed(messages) if msg["role"] == "user"), None
        )

        if user_message:
            # Search for relevant knowledge
            similar_docs = await vector_search_service.search_similar_documents(
                query=user_message["content"],
                document_type="qa_pair",
                limit=3,
                threshold=0.7,
                db=db,
            )

            # Add relevant knowledge to context
            if similar_docs:
                knowledge_context = "\n\nRelevant knowledge from database:\n"
                for doc in similar_docs:
                    knowledge_context += f"- {doc['content']}\n"

                messages.insert(1, {"role": "system", "content": knowledge_context})

        # Generate response
        if request.stream:
            # Return streaming response
            return StreamingResponse(
                _stream_chat_response(
                    messages, request.temperature, request.max_tokens
                ),
                media_type="text/event-stream",
            )
        else:
            response = await openai_service.chat_completion(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            return ResponseBuilder.success(
                data={
                    "response": response,
                    "session_id": request.session_id,
                    "model": openai_service.model,
                },
                message="Chat completion successful",
            )

    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        error_response = ResponseBuilder.from_exception(
            exception=e, context={"session_id": request.session_id}
        )
        raise HTTPException(status_code=500, detail=error_response)


@router.post("/solve-problem")
async def solve_excel_problem(
    request: ExcelProblemRequest, db: AsyncSession = Depends(get_db)
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
                db=db,
            )

            related_knowledge = [
                {"content": doc["content"], "similarity": doc["similarity"]}
                for doc in similar_docs
            ]

        # Enhance context with related knowledge
        enhanced_context = request.context or {}
        if related_knowledge:
            enhanced_context["related_solutions"] = related_knowledge

        # Generate solution
        solution = await openai_service.generate_excel_solution(
            problem_description=request.problem, context=enhanced_context
        )

        # Index the problem-solution pair for future use
        await vector_search_service.index_document(
            document_id=f"solution_{request.session_id or 'anonymous'}_{hash(request.problem)}",
            document_type="qa_pair",
            content=f"Q: {request.problem}\nA: {solution['solution']}",
            metadata={
                "source": "ai_generated",
                "problem": request.problem,
                "has_context": bool(request.context),
            },
            db=db,
        )

        return {
            "problem": request.problem,
            "solution": solution["solution"],
            "related_knowledge": related_knowledge,
            "model": solution["model_used"],
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
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


# Helper functions for AI consultation are now in ai_chat_helpers.py


@router.post("/analyze-cells-with-context")
async def analyze_cells_with_context(
    request: MultiCellAnalysisRequest, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyze multiple cells with full file context
    멀티 셀 선택 시 파일 전체 컨텍스트를 포함한 분석
    """
    try:
        # 확장된 컨텍스트 매니저 사용
        context_manager = get_enhanced_context_manager()

        # 멀티 셀 선택 업데이트
        cells_data = [
            {
                "address": cell.address,
                "sheetName": cell.sheetName,
                "value": cell.value,
                "formula": cell.formula,
            }
            for cell in request.cells
        ]

        if request.session_id:
            context_info = await context_manager.update_multi_cell_selection(
                request.session_id, cells_data
            )
            logger.info(
                f"멀티 셀 컨텍스트 업데이트: {context_info.get('cell_count')} cells"
            )
        # 1. Load file context from vector store
        file_context = None
        if request.file_id:
            file_docs = await vector_search_service.search_similar_documents(
                query=(
                    request.file_info.get("fileName", request.file_id)
                    if request.file_info
                    else request.file_id
                ),
                document_type="excel_analysis",
                limit=1,
                threshold=0.3,
                db=db,
            )
            if file_docs:
                file_context = file_docs[0]["content"]
                logger.info(
                    f"Found file context for multi-cell analysis: {request.file_id}"
                )

        # 2. Analyze selected cells using IntegratedErrorDetector
        from app.services.detection.integrated_error_detector import (
            IntegratedErrorDetector,
        )

        detector = IntegratedErrorDetector()

        # Prepare cell data for detector
        cells_for_detector = [
            {
                "sheet": cell.sheetName or "Sheet1",
                "address": cell.address,
                "value": cell.value,
                "formula": cell.formula,
            }
            for cell in request.cells
        ]

        # Get detector analysis
        detector_result = await detector.detect_multi_cell_errors(
            file_path=request.file_id,  # This should be the actual file path
            cells=cells_for_detector,
        )

        individual_analyses = detector_result.get("individual_cells", [])
        pattern_insights = detector_result.get("pattern_analysis", {})
        cross_cell_issues = detector_result.get("cross_cell_issues", [])

        # 4. Calculate statistics for numeric data
        statistics = None
        numeric_values = [
            cell.value
            for cell in request.cells
            if isinstance(cell.value, (int, float)) and cell.value is not None
        ]
        if numeric_values:
            import numpy as np

            statistics = {
                "count": len(numeric_values),
                "sum": sum(numeric_values),
                "mean": np.mean(numeric_values),
                "median": np.median(numeric_values),
                "std_dev": np.std(numeric_values) if len(numeric_values) > 1 else 0,
                "min": min(numeric_values),
                "max": max(numeric_values),
            }

        # 5. Identify data types
        data_types = {}
        for cell in request.cells:
            dtype = type(cell.value).__name__
            data_types[dtype] = data_types.get(dtype, 0) + 1

        # 6. Generate contextual AI response
        context_prompt = _build_multi_cell_prompt(
            request.question, request.cells, file_context, pattern_insights, statistics
        )

        messages = [
            {
                "role": "system",
                "content": """당신은 Excel 전문가입니다. 사용자가 선택한 여러 셀의 데이터를 분석하고,
                파일 전체 맥락에서 이 데이터가 가지는 의미를 설명해주세요.
                패턴, 이상치, 관계성 등을 찾아 인사이트를 제공하세요.""",
            },
            {"role": "user", "content": context_prompt},
        ]

        ai_response = await openai_service.chat_completion(
            messages=messages, temperature=0.7, max_tokens=1500
        )

        # 7. Return comprehensive analysis
        return {
            "analysis": {
                "individual_cells": individual_analyses,
                "pattern_insights": pattern_insights,
                "cross_cell_issues": cross_cell_issues,
                "statistics": statistics,
                "data_types": data_types,
                "cell_count": len(request.cells),
                "selection_type": request.selection_type,
                "detector_summary": detector_result.get("summary", {}),
            },
            "ai_response": ai_response,
            "file_context_found": file_context is not None,
            "suggestions": _generate_multi_cell_suggestions(
                pattern_insights, statistics
            ),
            "visualizations": _suggest_visualizations(data_types, pattern_insights),
        }

    except Exception as e:
        logger.error(f"Multi-cell analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_multi_cell_prompt(
    question: str,
    cells: List[CellContext],
    file_context: Optional[str],
    patterns: Dict[str, Any],
    statistics: Optional[Dict[str, Any]],
) -> str:
    """Build comprehensive prompt for multi-cell analysis"""
    prompt = f"사용자 질문: {question}\n\n"

    if file_context:
        prompt += f"[파일 전체 컨텍스트]\n{file_context}\n\n"

    prompt += "[선택된 셀 정보]\n"
    prompt += f"- 선택 유형: {patterns['type']}\n"
    prompt += f"- 셀 개수: {len(cells)}\n"

    # Add first few cells as examples
    prompt += "\n[샘플 데이터]\n"
    for cell in cells[:5]:
        prompt += f"- {cell.address}: {cell.value}"
        if cell.formula:
            prompt += f" (수식: {cell.formula})"
        prompt += "\n"

    if len(cells) > 5:
        prompt += f"... 외 {len(cells) - 5}개 셀\n"

    # Add patterns
    if patterns.get("common_patterns"):
        prompt += "\n[발견된 패턴]\n"
        for pattern in patterns["common_patterns"]:
            prompt += f"- {pattern}\n"

    # Add statistics
    if statistics:
        prompt += "\n[통계 정보]\n"
        prompt += f"- 평균: {statistics['mean']:.2f}\n"
        prompt += f"- 중앙값: {statistics['median']:.2f}\n"
        prompt += f"- 표준편차: {statistics['std_dev']:.2f}\n"
        prompt += f"- 범위: {statistics['min']} ~ {statistics['max']}\n"

    return prompt


def _generate_multi_cell_suggestions(
    patterns: Dict[str, Any], statistics: Optional[Dict[str, Any]]
) -> List[str]:
    """Generate suggestions based on multi-cell analysis"""
    suggestions = []

    if patterns.get("is_formula_range"):
        suggestions.append(
            "수식 일괄 수정 기능을 사용하여 효율적으로 업데이트할 수 있습니다"
        )

    if patterns.get("data_trend") == "increasing":
        suggestions.append(
            "증가 추세를 보이는 데이터입니다. 추세선 차트를 추가해보세요"
        )
    elif patterns.get("data_trend") == "decreasing":
        suggestions.append(
            "감소 추세를 보이는 데이터입니다. 원인 분석이 필요할 수 있습니다"
        )

    if statistics and statistics.get("std_dev", 0) > statistics.get("mean", 1) * 0.5:
        suggestions.append("데이터의 변동성이 큽니다. 이상치를 확인해보세요")

    return suggestions


def _suggest_visualizations(
    data_types: Dict[str, int], patterns: Dict[str, Any]
) -> List[Dict[str, str]]:
    """Suggest appropriate visualizations for the data"""
    visualizations = []

    # Check if mostly numeric
    numeric_count = sum(
        data_types.get(t, 0) for t in ["int", "float", "numpy.float64", "numpy.int64"]
    )
    total_count = sum(data_types.values())

    if numeric_count > total_count * 0.7:
        if patterns.get("data_trend"):
            visualizations.append(
                {
                    "type": "line_chart",
                    "reason": "시계열 또는 연속 데이터의 추세를 보여주기에 적합합니다",
                }
            )

        visualizations.append(
            {"type": "column_chart", "reason": "값의 비교를 쉽게 할 수 있습니다"}
        )

        if total_count > 20:
            visualizations.append(
                {"type": "histogram", "reason": "데이터 분포를 파악하기에 좋습니다"}
            )

    return visualizations
