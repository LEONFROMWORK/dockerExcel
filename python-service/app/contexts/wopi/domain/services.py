"""
WOPI domain services - abstract interfaces following SOLID principles.
These define the contracts that infrastructure must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional
from .models import WOPIFile, WOPIUser, WOPIToken, CheckFileInfoResponse


class FileInfoService(ABC):
    """Service interface for file information operations."""
    
    @abstractmethod
    async def get_file_info(self, file_id: str, token: str) -> Optional[WOPIFile]:
        """Get file information by ID."""
        pass
    
    @abstractmethod
    async def build_check_file_info_response(
        self, 
        file: WOPIFile, 
        user: WOPIUser,
        post_message_origin: str
    ) -> CheckFileInfoResponse:
        """Build CheckFileInfo response from file and user data."""
        pass


class FileContentService(ABC):
    """Service interface for file content operations."""
    
    @abstractmethod
    async def get_file_content(self, file_id: str, token: str) -> Optional[bytes]:
        """Get file content as bytes."""
        pass
    
    @abstractmethod
    async def save_file_content(
        self, 
        file_id: str, 
        content: bytes, 
        token: str
    ) -> bool:
        """Save file content and return success status."""
        pass
    
    @abstractmethod
    async def get_file_path(self, file_id: str) -> Optional[str]:
        """Get physical file path for given file ID."""
        pass


class TokenService(ABC):
    """Service interface for token operations."""
    
    @abstractmethod
    async def generate_token(self, file_id: str, user_id: str) -> WOPIToken:
        """Generate new WOPI access token."""
        pass
    
    @abstractmethod
    async def validate_token(self, token: str) -> Optional[WOPIToken]:
        """Validate token and return token info if valid."""
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        pass


class UserService(ABC):
    """Service interface for user operations."""
    
    @abstractmethod
    async def get_user_by_token(self, token: str) -> Optional[WOPIUser]:
        """Get user information from token."""
        pass
    
    @abstractmethod
    async def check_user_permission(
        self, 
        user_id: str, 
        file_id: str, 
        required_permission: str
    ) -> bool:
        """Check if user has required permission for file."""
        pass