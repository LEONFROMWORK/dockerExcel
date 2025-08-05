"""
Excel cleanup API endpoints
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from pydantic import BaseModel
from typing import Dict, Any
import tempfile
import os
import logging

from app.services.excel_external_reference_cleaner import (
    excel_external_reference_cleaner,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class CleanupRequest(BaseModel):
    """Request model for cleanup operations"""

    remove_external_refs: bool = True
    preserve_values: bool = True


@router.post("/clean-external-references")
async def clean_external_references(
    file: UploadFile = File(...),
    remove_external_refs: bool = Form(default=True),
    preserve_values: bool = Form(default=True),
) -> Dict[str, Any]:
    """
    Clean external references from Excel file

    Args:
        file: Excel file to clean
        remove_external_refs: Whether to remove external references (True) or just detect them (False)
        preserve_values: Whether to preserve calculated values when removing references

    Returns:
        Cleanup results including found references and cleaned file
    """
    try:
        # Validate file type
        if not file.filename.endswith((".xlsx", ".xlsm", ".xls")):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only Excel files are supported.",
            )

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename)[1]
        ) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Clean external references
        result = excel_external_reference_cleaner.clean_external_references(
            tmp_path, remove_external=remove_external_refs
        )

        # If file was cleaned, read the cleaned file
        if result.get("success") and result.get("output_file"):
            cleaned_file_path = result["output_file"]
            with open(cleaned_file_path, "rb") as f:
                cleaned_content = f.read()

            # Clean up temporary files
            os.unlink(cleaned_file_path)

            # Return cleaned file content as base64
            import base64

            result["cleaned_file_base64"] = base64.b64encode(cleaned_content).decode(
                "utf-8"
            )
            result["cleaned_filename"] = f"cleaned_{file.filename}"

        # Clean up temporary file
        os.unlink(tmp_path)

        return result

    except Exception as e:
        logger.error(f"Error cleaning external references: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to clean external references: {str(e)}"
        )


@router.post("/detect-external-references")
async def detect_external_references(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Detect external references in Excel file without modifying it

    Args:
        file: Excel file to analyze

    Returns:
        List of detected external references
    """
    try:
        # This is essentially the same as clean_external_references with remove_external_refs=False
        return await clean_external_references(
            file=file, remove_external_refs=False, preserve_values=False
        )

    except Exception as e:
        logger.error(f"Error detecting external references: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to detect external references: {str(e)}"
        )
