"""
Token management implementation using Redis.
Handles token generation, validation, and storage.
"""

import secrets
import json
from datetime import datetime, timedelta
from typing import Optional
import redis.asyncio as redis
import logging

from ..domain.services import TokenService
from ..domain.models import WOPIToken, UserPermission

logger = logging.getLogger(__name__)


class RedisTokenManager(TokenService):
    """Redis-based implementation of TokenService."""
    
    def __init__(self, redis_url: str, token_ttl_hours: int = 24, pool_size: int = 10):
        """Initialize with Redis connection pool."""
        self.redis_url = redis_url
        self.token_ttl_hours = token_ttl_hours
        # Create connection pool for better performance
        self.pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=pool_size,
            decode_responses=True,
            socket_keepalive=True,
            socket_keepalive_options={
                1: 1,  # TCP_KEEPIDLE
                2: 5,  # TCP_KEEPINTVL  
                3: 5,  # TCP_KEEPCNT
            }
        )
        self.token_prefix = "wopi:token:"
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis client from pool."""
        return redis.Redis.from_pool(self.pool)
    
    async def generate_token(self, file_id: str, user_id: str) -> WOPIToken:
        """Generate new WOPI access token."""
        try:
            # Generate secure random token
            token_str = secrets.token_urlsafe(32)
            
            # Create token object
            now = datetime.utcnow()
            expires_at = now + timedelta(hours=self.token_ttl_hours)
            
            token = WOPIToken(
                token=token_str,
                file_id=file_id,
                user_id=user_id,
                expires_at=expires_at,
                created_at=now
            )
            
            # Store in Redis
            redis_client = await self._get_redis()
            key = f"{self.token_prefix}{token_str}"
            
            token_data = {
                'file_id': file_id,
                'user_id': user_id,
                'expires_at': expires_at.isoformat(),
                'created_at': now.isoformat()
            }
            
            # Set with expiration
            ttl_seconds = self.token_ttl_hours * 3600
            await redis_client.setex(
                key, 
                ttl_seconds, 
                json.dumps(token_data)
            )
            
            logger.info(f"Generated token for file {file_id}, user {user_id}")
            return token
            
        except Exception as e:
            logger.error(f"Error generating token: {str(e)}")
            raise
    
    async def validate_token(self, token: str) -> Optional[WOPIToken]:
        """Validate token and return token info if valid."""
        try:
            redis_client = await self._get_redis()
            key = f"{self.token_prefix}{token}"
            
            # Get token data from Redis
            token_data_str = await redis_client.get(key)
            if not token_data_str:
                logger.warning(f"Token not found: {token}")
                return None
            
            # Parse token data
            token_data = json.loads(token_data_str)
            
            # Create token object
            token_obj = WOPIToken(
                token=token,
                file_id=token_data['file_id'],
                user_id=token_data['user_id'],
                expires_at=datetime.fromisoformat(token_data['expires_at']),
                created_at=datetime.fromisoformat(token_data['created_at'])
            )
            
            # Check if expired
            if token_obj.is_expired:
                logger.warning(f"Token expired: {token}")
                await self.revoke_token(token)
                return None
            
            logger.info(f"Token validated for file {token_obj.file_id}")
            return token_obj
            
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return None
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        try:
            redis_client = await self._get_redis()
            key = f"{self.token_prefix}{token}"
            
            result = await redis_client.delete(key)
            
            if result > 0:
                logger.info(f"Token revoked: {token}")
                return True
            else:
                logger.warning(f"Token not found for revocation: {token}")
                return False
                
        except Exception as e:
            logger.error(f"Error revoking token: {str(e)}")
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()