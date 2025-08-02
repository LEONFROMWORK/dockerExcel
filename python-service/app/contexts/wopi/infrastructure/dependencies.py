"""
Dependency injection configuration for WOPI context.
"""

import os
import logging
from typing import Generator
from fastapi import Depends
import redis.asyncio as redis

from ..domain.services import FileInfoService, FileContentService, TokenService
from .token_manager import RedisTokenManager
from .jwt_token_service import JWTTokenService
from .streaming_file_storage import StreamingFileStorage
from .rails_storage_adapter import RailsStorageAdapter
from .test_token_service import TestTokenService
from .structured_logger import wopi_logger
from ..api.middleware.csrf_protection import CSRFProtection
from .config import settings

logger = logging.getLogger(__name__)

# Singleton instances
_redis_pool = None
_csrf_protection = None
_token_service = None
_file_storage = None


async def get_redis_pool() -> redis.ConnectionPool:
    """Get Redis connection pool singleton."""
    global _redis_pool
    if not _redis_pool:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            decode_responses=True,
            socket_keepalive=settings.redis_socket_keepalive,
            socket_keepalive_options={
                1: 1,  # TCP_KEEPIDLE
                2: 3,  # TCP_KEEPINTVL
                3: 5,  # TCP_KEEPCNT
            } if settings.redis_socket_keepalive else None
        )
    return _redis_pool


async def get_redis_client() -> Generator[redis.Redis, None, None]:
    """Get Redis client from pool."""
    pool = await get_redis_pool()
    client = redis.Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.close()


def get_token_service() -> TokenService:
    """Get token service based on configuration."""
    global _token_service
    if not _token_service:
        # Use test token service in development
        if settings.environment == "development":
            _token_service = TestTokenService()
            logger.info("Using test token service for development")
        elif settings.use_jwt_tokens:
            _token_service = JWTTokenService(
                secret_key=settings.jwt_secret_key,
                algorithm=settings.jwt_algorithm,
                token_ttl_hours=settings.token_ttl_hours,
                refresh_ttl_days=settings.refresh_ttl_days
            )
            logger.info("Using JWT token service")
        else:
            _token_service = RedisTokenManager(
                redis_url=settings.redis_url,
                pool_size=settings.redis_pool_size
            )
            logger.info("Using Redis token service")
    return _token_service


def get_file_storage() -> FileContentService:
    """Get file storage service."""
    global _file_storage
    if not _file_storage:
        # Use Rails storage adapter for Active Storage integration
        _file_storage = RailsStorageAdapter()
        wopi_logger("Using Rails storage adapter for Active Storage integration")
    return _file_storage


def get_csrf_protection() -> CSRFProtection:
    """Get CSRF protection singleton."""
    global _csrf_protection
    if not _csrf_protection:
        _csrf_protection = CSRFProtection(
            redis_url=settings.redis_url,
            token_name=settings.csrf_token_name,
            header_name=settings.csrf_header_name,
            cookie_secure=settings.csrf_cookie_secure,
            cookie_samesite=settings.csrf_cookie_samesite,
            token_ttl_hours=settings.csrf_token_ttl_hours
        )
        logger.info("CSRF protection initialized")
    return _csrf_protection


# Dependency injection functions
async def get_current_token_service() -> TokenService:
    """Dependency for token service."""
    return get_token_service()


async def get_current_file_storage() -> FileContentService:
    """Dependency for file storage."""
    return get_file_storage()


# Cleanup function for graceful shutdown
async def cleanup_services():
    """Cleanup services on shutdown."""
    global _redis_pool, _token_service, _file_storage, _csrf_protection
    
    if _redis_pool:
        await _redis_pool.disconnect()
        _redis_pool = None
    
    _token_service = None
    _file_storage = None
    _csrf_protection = None
    
    logger.info("Services cleaned up")