"""
WOPI API endpoints following SOLID principles.
Each endpoint has a single responsibility.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import StreamingResponse
import logging
from typing import Optional
import io
import os

from ..domain.models import WOPIFile, WOPIUser, UserPermission, CheckFileInfoResponse
from ..domain.services import TokenService, FileContentService
from datetime import datetime
from ..infrastructure.dependencies import get_current_token_service, get_current_file_storage
from ..infrastructure.structured_logger import wopi_logger
from .error_handlers import WOPIError, TokenError, FileNotFoundError as WOPIFileNotFoundError, PermissionError as WOPIPermissionError
from .middleware.csrf_protection import CSRFTokenEndpoint
from ..infrastructure.dependencies import get_csrf_protection
from .dto import GenerateTokenRequest, GenerateTokenResponse, WOPIErrorResponse

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/wopi", tags=["wopi"])

# Add CSRF token endpoint
csrf_endpoint = CSRFTokenEndpoint(get_csrf_protection())

@router.get("/csrf/token")
async def get_csrf_token(request: Request):
    """Get CSRF token for session."""
    return await csrf_endpoint.get_token(request)


@router.get("/files/{file_id}")
async def check_file_info(
    file_id: str,
    access_token: str,
    request: Request,
    file_storage: FileContentService = Depends(get_current_file_storage),
    token_service: TokenService = Depends(get_current_token_service)
) -> dict:
    """
    CheckFileInfo endpoint - returns file metadata.
    This is the first call Collabora makes.
    """
    try:
        # Validate token
        token = await token_service.validate_token(access_token)
        if not token:
            raise TokenError("Invalid or expired token")
        
        if token.file_id != "*" and token.file_id != file_id:
            raise WOPIPermissionError("access", file_id)
        
        # Get file info
        file_info = await file_storage.get_file_info(file_id)
        if not file_info:
            raise WOPIFileNotFoundError(file_id)
        
        # Build response
        response = CheckFileInfoResponse(
            BaseFileName=file_info.name,
            Size=file_info.size,
            UserId=token.user_id,
            OwnerId=file_info.owner_id,
            UserFriendlyName=token.user_permission.user_name,
            UserCanWrite=token.user_permission.can_write,
            Version=file_info.version,
            PostMessageOrigin=f"{request.url.scheme}://{request.url.netloc}"
        )
        
        wopi_logger.log_file_accessed(
            file_id=file_id,
            user_id=token.user_id,
            operation="check_file_info",
            success=True
        )
        return response.to_dict()
        
    except WOPIError:
        raise
    except Exception as e:
        wopi_logger.log_error(
            error_type="check_file_info_error",
            error_message=str(e),
            context={"file_id": file_id}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/files/{file_id}/contents")
async def get_file(
    file_id: str,
    access_token: str,
    file_storage: FileContentService = Depends(get_current_file_storage),
    token_service: TokenService = Depends(get_current_token_service)
) -> StreamingResponse:
    """
    GetFile endpoint - returns file content.
    Collabora calls this to download the file.
    """
    try:
        # Validate token
        token = await token_service.validate_token(access_token)
        if not token:
            raise TokenError("Invalid or expired token")
        
        if token.file_id != "*" and token.file_id != file_id:
            raise WOPIPermissionError("access", file_id)
        
        # Get file content
        content = await file_storage.get_file_content(file_id, access_token)
        if not content:
            raise WOPIFileNotFoundError(file_id)
        
        # Log success
        wopi_logger.log_file_accessed(
            file_id=file_id,
            user_id=token.user_id,
            operation="get_file",
            success=True,
            size_bytes=len(content)
        )
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{file_id}.xlsx"',
                'Content-Length': str(len(content))
            }
        )
        
    except WOPIError:
        raise
    except Exception as e:
        wopi_logger.log_error(
            error_type="get_file_error",
            error_message=str(e),
            context={"file_id": file_id}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/files/{file_id}/contents")
async def put_file(
    file_id: str,
    access_token: str,
    request: Request,
    file_storage: FileContentService = Depends(get_current_file_storage),
    token_service: TokenService = Depends(get_current_token_service)
) -> dict:
    """
    PutFile endpoint - saves file content.
    Collabora calls this when user saves the document.
    """
    try:
        # Validate token
        token = await token_service.validate_token(access_token)
        if not token:
            raise TokenError("Invalid or expired token")
        
        if token.file_id != "*" and token.file_id != file_id:
            raise WOPIPermissionError("access", file_id)
        
        # Read request body
        content = await request.body()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file content")
        
        # Save file
        success = await file_storage.save_file_content(file_id, content, access_token)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save file")
        
        wopi_logger.log_file_accessed(
            file_id=file_id,
            user_id=token.user_id,
            operation="put_file",
            success=True,
            size_bytes=len(content)
        )
        
        # Return success response
        return {
            "status": "success",
            "LastModifiedTime": datetime.utcnow().isoformat() + "Z"
        }
        
    except WOPIError:
        raise
    except Exception as e:
        wopi_logger.log_error(
            error_type="put_file_error",
            error_message=str(e),
            context={"file_id": file_id}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/token/generate")
async def generate_token(
    request: GenerateTokenRequest,
    token_service: TokenService = Depends(get_current_token_service)
) -> GenerateTokenResponse:
    """
    Generate WOPI access token for a file.
    This is called by our own frontend, not by Collabora.
    """
    try:
        # Generate token
        token = await token_service.generate_token(
            file_id=request.file_id,
            user_id=request.user_id,
            user_name=getattr(request, 'user_name', 'Anonymous'),
            permission=getattr(request, 'permission', 'read')
        )
        
        # Build WOPI source URL
        base_url = os.getenv('WOPI_BASE_URL', 'http://localhost:8000')
        wopi_src = f"{base_url}/wopi/files/{request.file_id}"
        
        wopi_logger.log_token_generated(
            user_id=request.user_id,
            file_id=request.file_id,
            permission=getattr(request, 'permission', 'read'),
            token_id=token.access_token[:8] + "..."
        )
        
        return GenerateTokenResponse(
            access_token=token.access_token,
            access_token_ttl=int((token.expires_at - token.created_at).total_seconds() * 1000),
            wopi_src=wopi_src
        )
        
    except Exception as e:
        wopi_logger.log_error(
            error_type="token_generation_error",
            error_message=str(e),
            context={"file_id": request.file_id, "user_id": request.user_id}
        )
        raise HTTPException(status_code=500, detail="Failed to generate token")


@router.get("/files/{file_id}/stream")
async def stream_file(
    file_id: str,
    access_token: str,
    range: Optional[str] = None,
    file_storage: FileContentService = Depends(get_current_file_storage),
    token_service: TokenService = Depends(get_current_token_service)
) -> StreamingResponse:
    """
    Stream file content for large files.
    Supports HTTP range requests.
    """
    try:
        # Validate token
        token = await token_service.validate_token(access_token)
        if not token:
            raise TokenError("Invalid or expired token")
        
        if token.file_id != "*" and token.file_id != file_id:
            raise WOPIPermissionError("access", file_id)
        
        # Get file info
        file_info = await file_storage.get_file_info(file_id)
        if not file_info:
            raise WOPIFileNotFoundError(file_id)
        
        # Parse range header
        start_byte = 0
        end_byte = file_info.size - 1
        
        if range:
            # Parse "bytes=start-end" format
            range_match = range.replace("bytes=", "").split("-")
            if len(range_match) == 2:
                if range_match[0]:
                    start_byte = int(range_match[0])
                if range_match[1]:
                    end_byte = int(range_match[1])
        
        # Create streaming response
        async def stream_generator():
            async for chunk in file_storage.get_file_stream(
                file_id, access_token, start_byte, end_byte
            ):
                yield chunk
        
        content_length = end_byte - start_byte + 1
        
        headers = {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Length': str(content_length),
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {start_byte}-{end_byte}/{file_info.size}'
        }
        
        wopi_logger.log_file_accessed(
            file_id=file_id,
            user_id=token.user_id,
            operation="stream_file",
            success=True,
            size_bytes=content_length
        )
        
        return StreamingResponse(
            stream_generator(),
            status_code=206 if range else 200,
            headers=headers
        )
        
    except WOPIError:
        raise
    except Exception as e:
        wopi_logger.log_error(
            error_type="stream_file_error",
            error_message=str(e),
            context={"file_id": file_id}
        )
        raise HTTPException(status_code=500, detail="Internal server error")