"""
CSRF protection middleware for WOPI API.
"""

import secrets
import hashlib
from typing import Optional, Dict, Set
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
import redis.asyncio as redis
from datetime import datetime, timedelta

from ..error_handlers import WOPIError
from ...infrastructure.structured_logger import wopi_logger


class CSRFProtection:
    """CSRF protection using double-submit cookie pattern."""
    
    def __init__(
        self,
        redis_url: str,
        token_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        cookie_secure: bool = True,
        cookie_samesite: str = "strict",
        token_ttl_hours: int = 24
    ):
        self.redis_url = redis_url
        self.token_name = token_name
        self.header_name = header_name
        self.cookie_secure = cookie_secure
        self.cookie_samesite = cookie_samesite
        self.token_ttl_hours = token_ttl_hours
        self.redis_client = None
        
        # Methods that require CSRF protection
        self.protected_methods: Set[str] = {"POST", "PUT", "DELETE", "PATCH"}
        
        # Paths to exclude from CSRF protection
        self.excluded_paths: Set[str] = {
            "/wopi/token/generate",  # Initial token generation might not have CSRF
            "/health",
            "/docs",
            "/openapi.json"
        }
        
        # Path prefixes to exclude from CSRF protection
        self.excluded_prefixes: Set[str] = {
            "/api/v1/",  # All API v1 endpoints
        }
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis client."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(self.redis_url)
        return self.redis_client
    
    def generate_token(self) -> str:
        """Generate CSRF token."""
        return secrets.token_urlsafe(32)
    
    def hash_token(self, token: str) -> str:
        """Hash token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    async def create_token(self, session_id: str) -> str:
        """Create and store CSRF token."""
        token = self.generate_token()
        token_hash = self.hash_token(token)
        
        # Store in Redis with TTL
        redis_client = await self._get_redis()
        key = f"csrf:{session_id}:{token_hash}"
        ttl = timedelta(hours=self.token_ttl_hours)
        
        await redis_client.setex(key, ttl, "1")
        
        wopi_logger.logger.info(
            "csrf.token.created",
            session_id=session_id,
            token_hash=token_hash[:8] + "..."
        )
        
        return token
    
    async def validate_token(
        self, 
        session_id: str, 
        token: str
    ) -> bool:
        """Validate CSRF token."""
        if not token:
            return False
        
        token_hash = self.hash_token(token)
        redis_client = await self._get_redis()
        key = f"csrf:{session_id}:{token_hash}"
        
        exists = await redis_client.exists(key)
        
        if exists:
            # Refresh TTL on successful validation
            ttl = timedelta(hours=self.token_ttl_hours)
            await redis_client.expire(key, ttl)
        
        return bool(exists)
    
    async def revoke_token(self, session_id: str, token: str):
        """Revoke CSRF token."""
        token_hash = self.hash_token(token)
        redis_client = await self._get_redis()
        key = f"csrf:{session_id}:{token_hash}"
        
        await redis_client.delete(key)
        
        wopi_logger.logger.info(
            "csrf.token.revoked",
            session_id=session_id,
            token_hash=token_hash[:8] + "..."
        )
    
    def should_check_csrf(self, request: Request) -> bool:
        """Check if request should be CSRF protected."""
        # Skip if method not protected
        if request.method not in self.protected_methods:
            return False
        
        # Skip if path excluded
        if request.url.path in self.excluded_paths:
            return False
        
        # Skip for excluded path prefixes
        for prefix in self.excluded_prefixes:
            if request.url.path.startswith(prefix):
                return False
        
        # Skip if it's an API call with valid Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return False
        
        return True
    
    async def __call__(self, request: Request, call_next):
        """Middleware to check CSRF token."""
        # Check if CSRF protection needed
        if not self.should_check_csrf(request):
            response = await call_next(request)
            return response
        
        # Get session ID (from cookie or header)
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise WOPIError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="CSRF_SESSION_MISSING",
                message="Session ID required for CSRF protection"
            )
        
        # Get CSRF token from header
        csrf_token = request.headers.get(self.header_name)
        if not csrf_token:
            # Also check form data for token
            if request.method == "POST":
                form = await request.form()
                csrf_token = form.get(self.token_name)
        
        if not csrf_token:
            raise WOPIError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="CSRF_TOKEN_MISSING",
                message="CSRF token required"
            )
        
        # Validate token
        is_valid = await self.validate_token(session_id, csrf_token)
        if not is_valid:
            wopi_logger.logger.warning(
                "csrf.validation.failed",
                session_id=session_id,
                path=request.url.path,
                method=request.method
            )
            
            raise WOPIError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="CSRF_TOKEN_INVALID",
                message="Invalid CSRF token"
            )
        
        # Token valid, proceed
        response = await call_next(request)
        
        # Optionally rotate token on state-changing operations
        if request.method in {"POST", "PUT", "DELETE"}:
            new_token = await self.create_token(session_id)
            response.set_cookie(
                key=self.token_name,
                value=new_token,
                secure=self.cookie_secure,
                httponly=True,
                samesite=self.cookie_samesite
            )
        
        return response


class CSRFTokenEndpoint:
    """Endpoint to get CSRF token."""
    
    def __init__(self, csrf_protection: CSRFProtection):
        self.csrf = csrf_protection
    
    async def get_token(self, request: Request) -> Dict[str, str]:
        """Get CSRF token for current session."""
        # Get or create session ID
        session_id = request.cookies.get("session_id")
        if not session_id:
            session_id = secrets.token_urlsafe(16)
        
        # Create CSRF token
        csrf_token = await self.csrf.create_token(session_id)
        
        # Return token and session info
        response = {
            "csrf_token": csrf_token,
            "header_name": self.csrf.header_name,
            "session_id": session_id
        }
        
        return response