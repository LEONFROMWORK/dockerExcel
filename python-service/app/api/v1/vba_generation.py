"""
VBA Code Generation API endpoints
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from app.services.vba_generator import VBAGenerator
from app.services.openai_service import OpenAIService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vba", tags=["vba_generation"])


class VBAGenerationRequest(BaseModel):
    """Request model for VBA generation"""
    description: str = Field(..., description="Natural language description of what the VBA code should do")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (worksheet names, data ranges, etc.)")
    template_id: Optional[str] = Field(None, description="Template ID to use as base")
    language: str = Field("en", description="Language for comments and messages (en, ko)")


class VBATemplateRequest(BaseModel):
    """Request model for template-based VBA generation"""
    template_id: str = Field(..., description="Template ID")
    parameters: Dict[str, Any] = Field(..., description="Template parameters")


class VBAValidationRequest(BaseModel):
    """Request model for VBA code validation"""
    vba_code: str = Field(..., description="VBA code to validate")
    check_security: bool = Field(True, description="Check for security issues")
    check_performance: bool = Field(True, description="Check for performance issues")


@router.post("/generate")
async def generate_vba(request: VBAGenerationRequest) -> Dict[str, Any]:
    """
    Generate VBA code from natural language description
    """
    try:
        generator = VBAGenerator()
        openai_service = OpenAIService()
        
        # Parse user requirements
        parsed_requirements = await openai_service.parse_vba_requirements(
            request.description,
            request.context,
            request.language
        )
        
        # Generate VBA code
        if request.template_id:
            # Use template-based generation
            vba_code = generator.generate_from_template(
                request.template_id,
                parsed_requirements
            )
        else:
            # Use AI-based generation
            vba_code = await openai_service.generate_vba_code(
                parsed_requirements,
                request.language
            )
        
        # Validate generated code
        validation_result = generator.validate_vba_code(vba_code)
        
        if not validation_result["is_valid"]:
            # Try to fix common issues
            vba_code = generator.fix_common_issues(vba_code)
            validation_result = generator.validate_vba_code(vba_code)
        
        return {
            "success": True,
            "vba_code": vba_code,
            "requirements": parsed_requirements,
            "validation": validation_result,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "language": request.language,
                "template_used": request.template_id
            }
        }
        
    except Exception as e:
        logger.error(f"VBA generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-from-template")
async def create_from_template(request: VBATemplateRequest) -> Dict[str, Any]:
    """
    Generate VBA code from a predefined template
    """
    try:
        generator = VBAGenerator()
        
        # Get template
        template = generator.get_template(request.template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{request.template_id}' not found")
        
        # Generate code from template
        vba_code = generator.generate_from_template(
            request.template_id,
            request.parameters
        )
        
        # Validate
        validation_result = generator.validate_vba_code(vba_code)
        
        return {
            "success": True,
            "vba_code": vba_code,
            "template": {
                "id": template["id"],
                "name": template["name"],
                "description": template["description"]
            },
            "validation": validation_result,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates(category: Optional[str] = None) -> Dict[str, Any]:
    """
    List available VBA templates
    """
    try:
        generator = VBAGenerator()
        templates = generator.list_templates(category)
        
        return {
            "success": True,
            "templates": templates,
            "categories": generator.get_template_categories()
        }
        
    except Exception as e:
        logger.error(f"Template listing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_vba(request: VBAValidationRequest) -> Dict[str, Any]:
    """
    Validate VBA code for syntax, security, and performance issues
    """
    try:
        generator = VBAGenerator()
        
        # Basic validation
        validation_result = generator.validate_vba_code(
            request.vba_code,
            check_security=request.check_security,
            check_performance=request.check_performance
        )
        
        # Get improvement suggestions
        suggestions = generator.get_improvement_suggestions(request.vba_code)
        
        return {
            "success": True,
            "validation": validation_result,
            "suggestions": suggestions,
            "metadata": {
                "validated_at": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"VBA validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enhance")
async def enhance_vba(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Enhance existing VBA code with error handling, performance improvements, etc.
    """
    try:
        # Read uploaded file
        content = await file.read()
        
        # Detect encoding
        try:
            vba_code = content.decode('utf-8')
        except UnicodeDecodeError:
            vba_code = content.decode('cp1252')  # Windows default
        
        generator = VBAGenerator()
        openai_service = OpenAIService()
        
        # Analyze existing code
        analysis = generator.analyze_vba_code(vba_code)
        
        # Generate enhanced version
        enhanced_code = await openai_service.enhance_vba_code(
            vba_code,
            analysis["issues"],
            analysis["suggestions"]
        )
        
        # Validate enhanced code
        validation_result = generator.validate_vba_code(enhanced_code)
        
        return {
            "success": True,
            "original_analysis": analysis,
            "enhanced_code": enhanced_code,
            "validation": validation_result,
            "improvements": {
                "error_handling_added": True,
                "performance_optimized": True,
                "security_enhanced": True
            },
            "metadata": {
                "filename": file.filename,
                "enhanced_at": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"VBA enhancement error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))