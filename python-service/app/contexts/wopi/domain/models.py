"""
WOPI domain models following SOLID principles.
Each model has a single responsibility.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class UserPermission(Enum):
    """User permission levels for WOPI."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass
class WOPIFile:
    """Represents a file in WOPI context."""
    id: str
    name: str
    size: int
    owner_id: str
    last_modified: datetime
    version: str = "1.0"
    
    @property
    def base_name(self) -> str:
        """Get file name without path."""
        return self.name.split('/')[-1]


@dataclass
class WOPIUser:
    """Represents a user in WOPI context."""
    id: str
    name: str
    friendly_name: str
    permission: UserPermission
    
    @property
    def can_write(self) -> bool:
        """Check if user has write permission."""
        return self.permission in [UserPermission.WRITE, UserPermission.ADMIN]
    
    @property
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.permission == UserPermission.ADMIN


@dataclass
class WOPIToken:
    """Represents an access token for WOPI."""
    token: str
    file_id: str
    user_id: str
    expires_at: datetime
    created_at: datetime
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def ttl_ms(self) -> int:
        """Get time to live in milliseconds."""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return int(delta.total_seconds() * 1000)


@dataclass
class CheckFileInfoResponse:
    """Response model for CheckFileInfo endpoint."""
    BaseFileName: str
    Size: int
    UserId: str
    OwnerId: str
    UserFriendlyName: str
    UserCanWrite: bool
    Version: str
    LastModifiedTime: Optional[str] = None
    PostMessageOrigin: Optional[str] = None
    UserExtraInfo: Optional[dict] = None
    IsUserRestricted: bool = False
    IsUserLocked: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                result[key] = value
        return result