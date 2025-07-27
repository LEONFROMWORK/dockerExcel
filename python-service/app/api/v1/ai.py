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
from app.services.image_excel_integration import ImageExcelIntegrationService

logger = logging.getLogger(__name__)

router = APIRouter()

# 이미지 분석 서비스 인스턴스
image_integration_service = ImageExcelIntegrationService()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ExcelProblemRequest(BaseModel):
    problem: str
    context: Optional[Dict[str, Any]] = None
    search_knowledge: bool = True


@router.post("/chat")
async def chat_completion(
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


@router.post("/analyze-image")
async def analyze_excel_image(
    file: Optional[UploadFile] = File(None),
    image_url: Optional[str] = None,
    question: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze an Excel screenshot or image using unified convert-and-analyze service
    
    This endpoint now uses the unified image-excel-integration service for all processing.
    """
    try:
        if not file and not image_url:
            raise HTTPException(
                status_code=400, 
                detail="Either file upload or image_url must be provided"
            )
        
        # Use unified convert-and-analyze service for file uploads
        if file:
            logger.info(f"Using unified convert-and-analyze service with file: {file.filename}")
            
            # Validate file type
            if not file.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400, 
                    detail="Only image files are supported"
                )
            
            # Save image temporarily
            image_data = await file.read()
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_file.write(image_data)
                temp_path = temp_file.name
            
            try:
                # Create form data to call convert-and-analyze endpoint
                import httpx
                
                # Create multipart form data
                files = {"file": (file.filename, image_data, file.content_type)}
                data = {
                    "ai_consultation": "true",
                    "question": question or "이 이미지를 분석해주세요.",
                    "detect_errors": "false"  # Skip error detection for consultation
                }
                
                # Call the unified convert-and-analyze service internally
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8000/api/v1/image-excel-integration/convert-and-analyze",
                        files=files,
                        data=data,
                        timeout=60.0
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Extract AI consultation response
                    ai_consultation = result.get("ai_consultation", {})
                    ai_response = ai_consultation.get("response", "AI 응답을 생성할 수 없습니다.")
                    
                    return {
                        "ai_analysis": ai_response,
                        "method": "unified_convert_and_analyze",
                        "filename": file.filename,
                        "question": question,
                        "processing_details": {
                            "ocr_confidence": result.get("image_analysis", {}).get("confidence", 0),
                            "ocr_method": result.get("image_analysis", {}).get("ocr_method", "unknown"),
                            "total_cells": result.get("excel_conversion", {}).get("total_cells", 0)
                        },
                        "full_result": result  # Include full conversion result for debugging
                    }
                else:
                    # Fallback for API call failure
                    fallback_prompt = f"""이미지 처리 서비스에 문제가 발생했지만, 기본적인 분석을 제공하겠습니다.

사용자 질문: {question or "이 이미지를 분석해주세요."}

Excel 이미진나 데이터 테이블에 대한 일반적인 분석 및 조언을 드리겠습니다."""
                    
                    messages = [
                        {"role": "system", "content": "당신은 Excel 전문가입니다. OCR 처리가 실패했을 때도 일반적인 조언을 제공하세요."},
                        {"role": "user", "content": fallback_prompt}
                    ]
                    
                    ai_response = await openai_service.chat_completion(
                        messages=messages,
                        temperature=0.7,
                        max_tokens=1000
                    )
                    
                    return {
                        "ai_analysis": ai_response,
                        "method": "unified_convert_and_analyze_fallback",
                        "filename": file.filename,
                        "question": question,
                        "warning": "OCR 서비스 호출 실패, 기본 분석 제공",
                        "api_error": response.text if response else "Unknown error"
                    }
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        # Legacy URL-based analysis (kept for compatibility)
        else:
            logger.info(f"Using legacy vision API with URL: {image_url}")
            
            messages = [
                {
                    "role": "system",
                    "content": "You are an Excel expert. Analyze the image and provide insights."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question or "Please analyze this Excel image and provide insights."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ]
            
            ai_response = await openai_service.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return {
                "ai_analysis": ai_response,
                "method": "legacy_vision_api",
                "image_url": image_url,
                "question": question
            }
    
    except Exception as e:
        logger.error(f"Image analysis error: {str(e)}")
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