"""
Admin Template Management API
Provides endpoints for template upload, management, and internationalization
"""
import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from ...services.template_analyzer import template_analyzer
from ...services.i18n_template_service import i18n_template_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/templates", tags=["admin_templates"])


class TemplateUploadResponse(BaseModel):
    template_id: str
    status: str
    message: str
    analysis_result: Optional[Dict[str, Any]] = None
    i18n_requirements: Optional[Dict[str, Any]] = None


class TemplateListItem(BaseModel):
    template_id: str
    template_name: str
    original_filename: str
    analyzed_at: str
    complexity_score: int
    sheet_count: int
    file_size: int
    i18n_status: Dict[str, Any]


class TranslationRequest(BaseModel):
    template_id: str
    target_languages: List[str]
    use_ai_enhancement: bool = True


class TranslationUpdateRequest(BaseModel):
    language: str
    key: str
    new_translation: str


@router.post("/upload", response_model=TemplateUploadResponse)
async def upload_template(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    template_name: str = Form(None),
    auto_analyze: bool = Form(True),
    auto_i18n: bool = Form(True),
    target_languages: str = Form("ko,en,ja,zh")
):
    """
    Upload and analyze a new Excel template
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are supported")
    
    try:
        # Save uploaded file temporarily
        temp_file_path = f"/tmp/{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Use provided name or extract from filename
        if not template_name:
            template_name = Path(file.filename).stem
        
        if auto_analyze:
            # Analyze template immediately
            analysis_result = await template_analyzer.analyze_template_file(
                temp_file_path, template_name
            )
            
            # Copy to storage
            storage_path = await template_analyzer.copy_template_to_storage(
                temp_file_path, analysis_result['template_id']
            )
            
            # Generate i18n requirements if requested
            i18n_requirements = None
            if auto_i18n:
                try:
                    i18n_requirements = await i18n_template_service.analyze_template_i18n_requirements(
                        analysis_result
                    )
                    
                    # Start background translation task
                    if target_languages:
                        langs = [lang.strip() for lang in target_languages.split(',')]
                        background_tasks.add_task(
                            generate_template_translations_background,
                            analysis_result['template_id'],
                            langs
                        )
                except Exception as e:
                    logger.warning(f"I18n analysis failed: {e}")
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return TemplateUploadResponse(
                template_id=analysis_result['template_id'],
                status="success",
                message="Template uploaded and analyzed successfully",
                analysis_result=analysis_result,
                i18n_requirements=i18n_requirements
            )
        
        else:
            # Just upload without analysis
            template_id = template_analyzer._generate_template_id(template_name)
            storage_path = await template_analyzer.copy_template_to_storage(
                temp_file_path, template_id
            )
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return TemplateUploadResponse(
                template_id=template_id,
                status="success",
                message="Template uploaded successfully. Analysis can be performed later."
            )
    
    except Exception as e:
        logger.error(f"Template upload failed: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/list", response_model=List[TemplateListItem])
async def list_templates():
    """
    List all available templates with their metadata
    """
    try:
        templates = await template_analyzer.list_available_templates()
        template_list = []
        
        for template in templates:
            # Get i18n status
            i18n_status = await get_template_i18n_status(template['template_id'])
            
            template_list.append(TemplateListItem(
                template_id=template['template_id'],
                template_name=template['template_name'],
                original_filename=template.get('original_filename', ''),
                analyzed_at=template['analyzed_at'],
                complexity_score=template['complexity_score'],
                sheet_count=template['sheet_count'],
                file_size=template['file_size'],
                i18n_status=i18n_status
            ))
        
        return template_list
    
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve template list")


@router.get("/{template_id}")
async def get_template_details(template_id: str):
    """
    Get detailed information about a specific template
    """
    try:
        metadata = await template_analyzer.get_template_metadata(template_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Add i18n information
        i18n_status = await get_template_i18n_status(template_id)
        metadata['i18n_status'] = i18n_status
        
        return metadata
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve template details")


@router.post("/{template_id}/analyze")
async def analyze_template(template_id: str):
    """
    Analyze an uploaded template (if not already analyzed)
    """
    try:
        # Check if template exists in storage
        storage_path = Path(template_analyzer.template_storage_path)
        template_files = list(storage_path.glob(f"{template_id}.*"))
        
        if not template_files:
            raise HTTPException(status_code=404, detail="Template file not found")
        
        template_file = template_files[0]
        
        # Extract original name from metadata or use template_id
        metadata = await template_analyzer.get_template_metadata(template_id)
        template_name = metadata.get('template_name', template_id) if metadata else template_id
        
        # Perform analysis
        analysis_result = await template_analyzer.analyze_template_file(
            str(template_file), template_name
        )
        
        return analysis_result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/{template_id}/i18n/analyze")
async def analyze_template_i18n(template_id: str):
    """
    Analyze template internationalization requirements
    """
    try:
        # Get template metadata
        metadata = await template_analyzer.get_template_metadata(template_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Analyze i18n requirements
        i18n_requirements = await i18n_template_service.analyze_template_i18n_requirements(metadata)
        
        return i18n_requirements
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"I18n analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"I18n analysis failed: {str(e)}")


@router.post("/{template_id}/i18n/generate", response_model=TranslationRequest)
async def generate_translations(
    template_id: str,
    request: TranslationRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate translations for a template
    """
    try:
        # Validate template exists
        metadata = await template_analyzer.get_template_metadata(template_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Start translation generation in background
        background_tasks.add_task(
            generate_template_translations_background,
            template_id,
            request.target_languages,
            request.use_ai_enhancement
        )
        
        return JSONResponse(
            content={
                "status": "started",
                "message": "Translation generation started in background",
                "template_id": template_id,
                "target_languages": request.target_languages
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translation generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Translation generation failed: {str(e)}")


@router.get("/{template_id}/i18n/status")
async def get_i18n_status(template_id: str):
    """
    Get internationalization status for a template
    """
    try:
        i18n_status = await get_template_i18n_status(template_id)
        return i18n_status
    
    except Exception as e:
        logger.error(f"Failed to get i18n status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve i18n status")


@router.get("/{template_id}/i18n/{language}")
async def get_template_translations(template_id: str, language: str):
    """
    Get translations for a specific language
    """
    try:
        translations = await i18n_template_service.get_template_translations(template_id, language)
        
        if not translations:
            raise HTTPException(status_code=404, detail="Translations not found")
        
        return translations
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get translations: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve translations")


@router.put("/{template_id}/i18n/{language}")
async def update_translation(
    template_id: str,
    language: str,
    request: TranslationUpdateRequest
):
    """
    Update a specific translation
    """
    try:
        success = await i18n_template_service.update_template_translation(
            template_id, request.language, request.key, request.new_translation
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update translation")
        
        return {"status": "success", "message": "Translation updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update translation: {e}")
        raise HTTPException(status_code=500, detail="Failed to update translation")


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """
    Delete a template and all associated files
    """
    try:
        # Delete template file
        storage_path = Path(template_analyzer.template_storage_path)
        template_files = list(storage_path.glob(f"{template_id}.*"))
        
        for template_file in template_files:
            template_file.unlink()
        
        # Delete metadata
        metadata_path = Path(template_analyzer.metadata_storage_path)
        metadata_file = metadata_path / f"{template_id}.json"
        if metadata_file.exists():
            metadata_file.unlink()
        
        # Delete i18n files
        i18n_path = Path(i18n_template_service.template_translations_path)
        i18n_files = list(i18n_path.glob(f"{template_id}_*"))
        for i18n_file in i18n_files:
            i18n_file.unlink()
        
        return {"status": "success", "message": "Template deleted successfully"}
    
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete template")


@router.get("/{template_id}/download")
async def download_template(template_id: str):
    """
    Download the original template file
    """
    try:
        storage_path = Path(template_analyzer.template_storage_path)
        template_files = list(storage_path.glob(f"{template_id}.*"))
        
        if not template_files:
            raise HTTPException(status_code=404, detail="Template file not found")
        
        template_file = template_files[0]
        
        # Get original filename from metadata
        metadata = await template_analyzer.get_template_metadata(template_id)
        original_filename = metadata.get('original_filename', template_file.name) if metadata else template_file.name
        
        return FileResponse(
            path=str(template_file),
            filename=original_filename,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download template: {e}")
        raise HTTPException(status_code=500, detail="Failed to download template")


@router.get("/{template_id}/export/{language}")
async def export_localized_template(template_id: str, language: str):
    """
    Export template with specific language translations applied
    """
    try:
        # This would require implementing a template generation service
        # that applies translations to create localized versions
        # For now, return a placeholder response
        
        return JSONResponse(
            content={
                "status": "not_implemented",
                "message": "Localized template export will be implemented in future version",
                "template_id": template_id,
                "language": language
            }
        )
    
    except Exception as e:
        logger.error(f"Failed to export localized template: {e}")
        raise HTTPException(status_code=500, detail="Failed to export localized template")


# Background task functions
async def generate_template_translations_background(
    template_id: str, 
    target_languages: List[str],
    use_ai_enhancement: bool = True
):
    """Background task for generating template translations"""
    try:
        logger.info(f"Starting background translation for template {template_id}")
        
        result = await i18n_template_service.generate_template_translations(
            template_id, target_languages, use_ai_enhancement
        )
        
        logger.info(f"Completed background translation for template {template_id}")
        return result
    
    except Exception as e:
        logger.error(f"Background translation failed for template {template_id}: {e}")


async def get_template_i18n_status(template_id: str) -> Dict[str, Any]:
    """Get comprehensive i18n status for a template"""
    try:
        # Check if i18n requirements exist
        requirements_file = i18n_template_service.template_translations_path / f"{template_id}_i18n_requirements.json"
        has_requirements = requirements_file.exists()
        
        # Check if translations exist
        translations_file = i18n_template_service.template_translations_path / f"{template_id}_translations.json"
        has_translations = translations_file.exists()
        
        available_languages = []
        translation_quality = {}
        
        if has_translations:
            translations = await i18n_template_service.get_template_translations(template_id)
            available_languages = list(translations.get('translations', {}).keys())
            translation_quality = translations.get('translation_quality', {})
        
        return {
            'has_requirements': has_requirements,
            'has_translations': has_translations,
            'available_languages': available_languages,
            'translation_quality': translation_quality,
            'status': 'complete' if has_translations else 'pending' if has_requirements else 'not_analyzed'
        }
    
    except Exception as e:
        logger.error(f"Failed to get i18n status: {e}")
        return {
            'has_requirements': False,
            'has_translations': False,
            'available_languages': [],
            'translation_quality': {},
            'status': 'error'
        }