"""
Template Description Management API
템플릿 설명 및 메타데이터 관리 API
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ...models.template_metadata import (
    EnhancedTemplateMetadata,
    TemplateCategory,
    TemplateComplexity,
)
from ...services.ai_template_context_service import ai_template_context_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/template-descriptions", tags=["template_descriptions"])


class TemplateDescriptionRequest(BaseModel):
    template_id: str
    name: str
    description: str
    category: str
    purpose: str
    business_use_cases: List[str]
    target_audience: List[str]
    complexity: str = "intermediate"
    estimated_completion_time: str = "30 minutes"
    prerequisites: List[str] = []
    tips_and_best_practices: List[str] = []
    context_keywords: List[str] = []


class FieldDescriptionRequest(BaseModel):
    section_name: str
    field_name: str
    description: str
    data_type: str
    is_required: bool = False
    business_logic: Optional[str] = None
    example_values: List[str] = []


class AIContextResponse(BaseModel):
    template_understanding: Dict[str, str]
    field_guidance: Dict[str, Dict[str, Any]]
    validation_prompts: Dict[str, str]
    user_assistance: Dict[str, str]
    data_insights: Dict[str, str]


@router.post("/create")
async def create_template_description(
    request: TemplateDescriptionRequest, background_tasks: BackgroundTasks
):
    """
    템플릿에 대한 상세 설명 및 메타데이터 생성
    """
    try:
        # EnhancedTemplateMetadata 객체 생성
        metadata = EnhancedTemplateMetadata(
            template_id=request.template_id,
            name=request.name,
            description=request.description,
            category=TemplateCategory(request.category),
            purpose=request.purpose,
            business_use_cases=request.business_use_cases,
            target_audience=request.target_audience,
            complexity=TemplateComplexity(request.complexity),
            estimated_completion_time=request.estimated_completion_time,
            prerequisites=request.prerequisites,
            tips_and_best_practices=request.tips_and_best_practices,
            context_keywords=request.context_keywords,
        )

        # 메타데이터 저장
        await _save_template_metadata(metadata)

        # 백그라운드에서 AI 컨텍스트 생성
        background_tasks.add_task(generate_ai_context_background, metadata)

        return {
            "status": "success",
            "message": "Template description created successfully",
            "template_id": request.template_id,
            "ai_context_generation": "started_in_background",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to create template description: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create template description"
        )


@router.get("/{template_id}")
async def get_template_description(template_id: str):
    """
    템플릿 설명 및 메타데이터 조회
    """
    try:
        metadata = await _load_template_metadata(template_id)
        if not metadata:
            raise HTTPException(
                status_code=404, detail="Template description not found"
            )

        return {
            "template_id": template_id,
            "metadata": metadata,
            "ai_context_available": await _check_ai_context_exists(template_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template description: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve template description"
        )


@router.post("/{template_id}/fields")
async def add_field_description(template_id: str, request: FieldDescriptionRequest):
    """
    특정 필드에 대한 상세 설명 추가
    """
    try:
        metadata = await _load_template_metadata(template_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Template not found")

        # 필드 설명 추가 로직
        # 실제 구현에서는 메타데이터 업데이트 필요

        return {
            "status": "success",
            "message": "Field description added successfully",
            "field": f"{request.section_name}.{request.field_name}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add field description: {e}")
        raise HTTPException(status_code=500, detail="Failed to add field description")


@router.get("/{template_id}/ai-context", response_model=AIContextResponse)
async def get_ai_context(template_id: str):
    """
    템플릿의 AI 컨텍스트 정보 조회
    """
    try:
        metadata = await _load_template_metadata(template_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Template not found")

        ai_context = await ai_template_context_service.generate_ai_context(metadata)

        return AIContextResponse(**ai_context)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI context: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve AI context")


@router.post("/{template_id}/ai-context/generate")
async def generate_ai_context(template_id: str, background_tasks: BackgroundTasks):
    """
    AI 컨텍스트 재생성
    """
    try:
        metadata = await _load_template_metadata(template_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Template not found")

        # 백그라운드에서 AI 컨텍스트 생성
        background_tasks.add_task(generate_ai_context_background, metadata)

        return {
            "status": "started",
            "message": "AI context generation started in background",
            "template_id": template_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start AI context generation: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to start AI context generation"
        )


@router.get("/{template_id}/smart-prompt")
async def get_smart_prompt(
    template_id: str, task_type: str, user_data: Optional[Dict[str, Any]] = None
):
    """
    특정 작업에 맞는 스마트 AI 프롬프트 생성
    """
    try:
        metadata = await _load_template_metadata(template_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Template not found")

        smart_prompt = await ai_template_context_service.get_contextual_ai_prompt(
            metadata, task_type, user_data
        )

        return {
            "template_id": template_id,
            "task_type": task_type,
            "smart_prompt": smart_prompt,
            "context_keywords": metadata.context_keywords,
            "domain_expertise": metadata.category.value,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate smart prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate smart prompt")


@router.post("/{template_id}/suggestions")
async def get_smart_suggestions(template_id: str, current_data: Dict[str, Any]):
    """
    현재 데이터를 기반으로 스마트 제안 생성
    """
    try:
        metadata = await _load_template_metadata(template_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Template not found")

        suggestions = await ai_template_context_service.generate_smart_suggestions(
            metadata, current_data
        )

        return {
            "template_id": template_id,
            "suggestions": suggestions,
            "total_suggestions": len(suggestions),
            "high_priority": len(
                [s for s in suggestions if s.get("priority") == "high"]
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")


@router.get("/")
async def list_template_descriptions():
    """
    모든 템플릿 설명 목록 조회
    """
    try:
        # 실제 구현에서는 파일 시스템이나 데이터베이스에서 조회
        templates = []

        return {"templates": templates, "total": len(templates)}

    except Exception as e:
        logger.error(f"Failed to list template descriptions: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to list template descriptions"
        )


# 헬퍼 함수들
async def _save_template_metadata(metadata: EnhancedTemplateMetadata):
    """템플릿 메타데이터 저장"""
    import json
    from pathlib import Path

    metadata_dir = Path("app/templates/excel/metadata")
    metadata_dir.mkdir(parents=True, exist_ok=True)

    metadata_file = metadata_dir / f"{metadata.template_id}_metadata.json"

    # dataclass를 dict로 변환 (enum은 value로)
    metadata_dict = {
        "template_id": metadata.template_id,
        "name": metadata.name,
        "description": metadata.description,
        "category": metadata.category.value,
        "subcategory": metadata.subcategory,
        "purpose": metadata.purpose,
        "business_use_cases": metadata.business_use_cases,
        "target_audience": metadata.target_audience,
        "usage_context": [uc.value for uc in metadata.usage_context],
        "complexity": metadata.complexity.value,
        "estimated_completion_time": metadata.estimated_completion_time,
        "prerequisites": metadata.prerequisites,
        "key_metrics": metadata.key_metrics,
        "calculation_methods": metadata.calculation_methods,
        "tips_and_best_practices": metadata.tips_and_best_practices,
        "common_errors": metadata.common_errors,
        "context_keywords": metadata.context_keywords,
        "semantic_tags": metadata.semantic_tags,
        "supported_languages": metadata.supported_languages,
        "version": metadata.version,
        "author": metadata.author,
        "source": metadata.source,
        "created_at": metadata.created_at.isoformat(),
        "updated_at": metadata.updated_at.isoformat(),
    }

    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata_dict, f, ensure_ascii=False, indent=2)


async def _load_template_metadata(template_id: str) -> Optional[Dict[str, Any]]:
    """템플릿 메타데이터 로드"""
    import json
    from pathlib import Path

    metadata_file = Path(f"app/templates/excel/metadata/{template_id}_metadata.json")

    if metadata_file.exists():
        with open(metadata_file, "r", encoding="utf-8") as f:
            return json.load(f)

    return None


async def _check_ai_context_exists(template_id: str) -> bool:
    """AI 컨텍스트 파일 존재 확인"""
    from pathlib import Path

    context_file = Path(f"app/templates/excel/ai_context/{template_id}_context.json")
    return context_file.exists()


async def generate_ai_context_background(metadata: EnhancedTemplateMetadata):
    """백그라운드에서 AI 컨텍스트 생성"""
    try:
        logger.info(f"Generating AI context for template {metadata.template_id}")

        ai_context = await ai_template_context_service.generate_ai_context(metadata)

        # AI 컨텍스트 저장
        await _save_ai_context(metadata.template_id, ai_context)

        logger.info(
            f"AI context generation completed for template {metadata.template_id}"
        )

    except Exception as e:
        logger.error(f"Failed to generate AI context in background: {e}")


async def _save_ai_context(template_id: str, ai_context: Dict[str, Any]):
    """AI 컨텍스트 저장"""
    import json
    from pathlib import Path

    context_dir = Path("app/templates/excel/ai_context")
    context_dir.mkdir(parents=True, exist_ok=True)

    context_file = context_dir / f"{template_id}_context.json"

    with open(context_file, "w", encoding="utf-8") as f:
        json.dump(ai_context, f, ensure_ascii=False, indent=2)
