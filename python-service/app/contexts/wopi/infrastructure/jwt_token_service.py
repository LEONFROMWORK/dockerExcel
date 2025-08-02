"""
JWT-based token service for enhanced security.
"""

import jwt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import logging

from ..domain.services import TokenService
from ..domain.models import WOPIToken, UserPermission

logger = logging.getLogger(__name__)


class JWTTokenService(TokenService):
    """JWT-based implementation of TokenService."""
    
    def __init__(
        self, 
        secret_key: str, 
        algorithm: str = "HS256",
        token_ttl_hours: int = 24,
        refresh_ttl_days: int = 7
    ):
        """Initialize JWT service."""
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_ttl_hours = token_ttl_hours
        self.refresh_ttl_days = refresh_ttl_days
    
    async def generate_token(
        self, 
        file_id: str, 
        user_id: str,
        user_name: str = "Anonymous",
        permission: str = "read"
    ) -> WOPIToken:
        """Generate new JWT access token."""
        try:
            # Generate unique token ID
            token_id = secrets.token_urlsafe(16)
            
            # Create expiration times
            now = datetime.now(timezone.utc)
            access_expires = now + timedelta(hours=self.token_ttl_hours)
            refresh_expires = now + timedelta(days=self.refresh_ttl_days)
            
            # Create JWT payload
            payload = {
                "jti": token_id,  # JWT ID
                "sub": user_id,   # Subject (user)
                "file_id": file_id,
                "user_name": user_name,
                "permission": permission,
                "iat": now.timestamp(),
                "exp": access_expires.timestamp(),
                "type": "access"
            }
            
            # Generate access token
            access_token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            # Generate refresh token
            refresh_payload = {
                "jti": f"{token_id}_refresh",
                "sub": user_id,
                "file_id": file_id,
                "iat": now.timestamp(),
                "exp": refresh_expires.timestamp(),
                "type": "refresh"
            }
            refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
            
            # Create token object
            token = WOPIToken(
                access_token=access_token,
                file_id=file_id,
                user_id=user_id,
                user_permission=UserPermission(
                    user_id=user_id,
                    user_name=user_name,
                    can_write=(permission == "write"),
                    can_export=True,
                    can_copy=True
                ),
                created_at=now.replace(tzinfo=None),
                expires_at=access_expires.replace(tzinfo=None),
                version="1.0"
            )
            
            # Store refresh token (you might want to store this in Redis)
            token.refresh_token = refresh_token
            
            logger.info(f"Generated JWT token for user {user_id}, file {file_id}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {str(e)}")
            raise
    
    async def validate_token(self, access_token: str) -> Optional[WOPIToken]:
        """Validate JWT access token."""
        try:
            # Decode and verify token
            payload = jwt.decode(
                access_token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            
            # Check token type
            if payload.get("type") != "access":
                logger.warning("Invalid token type")
                return None
            
            # Reconstruct token object
            token = WOPIToken(
                access_token=access_token,
                file_id=payload["file_id"],
                user_id=payload["sub"],
                user_permission=UserPermission(
                    user_id=payload["sub"],
                    user_name=payload.get("user_name", "Anonymous"),
                    can_write=(payload.get("permission") == "write"),
                    can_export=True,
                    can_copy=True
                ),
                created_at=datetime.fromtimestamp(payload["iat"]),
                expires_at=datetime.fromtimestamp(payload["exp"]),
                version="1.0"
            )
            
            return token
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[WOPIToken]:
        """Refresh access token using refresh token."""
        try:
            # Decode refresh token
            payload = jwt.decode(
                refresh_token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            
            # Check token type
            if payload.get("type") != "refresh":
                logger.warning("Invalid refresh token type")
                return None
            
            # Generate new access token
            return await self.generate_token(
                file_id=payload["file_id"],
                user_id=payload["sub"],
                user_name=payload.get("user_name", "Anonymous"),
                permission=payload.get("permission", "read")
            )
            
        except jwt.ExpiredSignatureError:
            logger.warning("Refresh token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid refresh token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Refresh token error: {str(e)}")
            return None
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke token (would need to implement blacklist in Redis)."""
        try:
            # Decode token to get JTI
            payload = jwt.decode(
                access_token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Allow expired tokens to be revoked
            )
            
            jti = payload.get("jti")
            if not jti:
                return False
            
            # TODO: Add JTI to Redis blacklist with expiration
            # await redis_client.setex(f"blacklist:{jti}", ttl, "1")
            
            logger.info(f"Revoked token with JTI: {jti}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke token: {str(e)}")
            return False
    
    def decode_token_unsafe(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode token without verification (for debugging only)."""
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None