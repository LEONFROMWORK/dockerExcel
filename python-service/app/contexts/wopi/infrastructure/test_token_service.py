"""
Test token service for development.
In production, use proper JWT or Redis-based tokens.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from ..domain.models import WOPIToken, UserPermission
from ..domain.services import TokenService

logger = logging.getLogger(__name__)


class TestTokenService(TokenService):
    """Simple token service for testing."""
    
    def __init__(self):
        """Initialize test token service."""
        # In-memory storage for test tokens
        self.tokens = {}
        
        # Create a default test token
        self._create_test_token()
    
    def _create_test_token(self):
        """Create a default test token."""
        token = WOPIToken(
            access_token="test-token",
            file_id="25",  # Default test file ID
            user_id="test-user",
            user_permission=UserPermission(
                user_id="test-user",
                user_name="Test User",
                can_write=False,  # Read-only for testing
                can_export=True,
                can_print=True
            ),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        self.tokens["test-token"] = token
        logger.info("Created default test token")
    
    async def generate_token(
        self,
        file_id: str,
        user_id: str,
        user_name: str = "User",
        permission: str = "read"
    ) -> WOPIToken:
        """Generate a new test token."""
        # For testing, use simple token format
        token_value = f"test-{file_id}-{user_id}-{datetime.utcnow().timestamp()}"
        
        can_write = permission in ["write", "edit"]
        
        token = WOPIToken(
            access_token=token_value,
            file_id=file_id,
            user_id=user_id,
            user_permission=UserPermission(
                user_id=user_id,
                user_name=user_name,
                can_write=can_write,
                can_export=True,
                can_print=True
            ),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        self.tokens[token_value] = token
        logger.info(f"Generated test token for file {file_id}, user {user_id}")
        
        return token
    
    async def validate_token(self, access_token: str) -> Optional[WOPIToken]:
        """Validate test token."""
        # Special handling for "test-token"
        if access_token == "test-token":
            # Allow any file ID with test-token by updating the stored token
            return WOPIToken(
                access_token="test-token",
                file_id="*",  # Wildcard for any file
                user_id="test-user",
                user_permission=UserPermission(
                    user_id="test-user",
                    user_name="Test User",
                    can_write=False,
                    can_export=True,
                    can_print=True
                ),
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
        
        # Check if token exists
        token = self.tokens.get(access_token)
        if not token:
            logger.warning(f"Token not found: {access_token}")
            return None
        
        # Check if token is expired
        if token.expires_at < datetime.utcnow():
            logger.warning(f"Token expired: {access_token}")
            del self.tokens[access_token]
            return None
        
        return token
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke test token."""
        if access_token in self.tokens:
            del self.tokens[access_token]
            logger.info(f"Revoked token: {access_token}")
            return True
        return False
    
    async def refresh_token(self, access_token: str) -> Optional[WOPIToken]:
        """Refresh test token."""
        token = self.tokens.get(access_token)
        if not token:
            return None
        
        # Extend expiration
        token.expires_at = datetime.utcnow() + timedelta(hours=24)
        logger.info(f"Refreshed token: {access_token}")
        
        return token