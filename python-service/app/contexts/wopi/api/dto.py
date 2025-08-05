"""
Data Transfer Objects for WOPI API.
These are separate from domain models to maintain clean architecture.
"""

from pydantic import BaseModel
from typing import Optional


class GenerateTokenRequest(BaseModel):
    """Request model for token generation."""

    file_id: str
    user_id: str
    user_name: str
    permission: str = "write"


class GenerateTokenResponse(BaseModel):
    """Response model for token generation."""

    access_token: str
    access_token_ttl: int  # milliseconds until expiration
    wopi_src: str  # WOPI source URL for the file


class WOPIErrorResponse(BaseModel):
    """Standard error response for WOPI endpoints."""

    error: str
    error_code: str
    correlation_id: Optional[str] = None


class FileUploadRequest(BaseModel):
    """Request model for file upload."""

    file_name: str
    user_id: str
    user_name: str
