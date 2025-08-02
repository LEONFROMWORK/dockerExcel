"""
WOPI context configuration.
"""

import os
from typing import Optional, Set
from pydantic_settings import BaseSettings


class WOPISettings(BaseSettings):
    """WOPI service configuration."""
    
    # Environment
    environment: str = "development"
    
    # Redis settings
    redis_url: str = "redis://localhost:6379"
    redis_pool_size: int = 20
    redis_socket_keepalive: bool = True
    
    # Token settings
    use_jwt_tokens: bool = True
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    token_ttl_hours: int = 24
    refresh_ttl_days: int = 7
    
    # File storage settings
    storage_path: str = "/tmp/excel_files"
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    chunk_size: int = 1024 * 1024  # 1MB
    allowed_extensions: Set[str] = {'.xlsx', '.xls', '.xlsm', '.ods', '.csv'}
    
    # CSRF settings
    csrf_token_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    csrf_cookie_secure: bool = False
    csrf_cookie_samesite: str = "lax"
    csrf_token_ttl_hours: int = 24
    
    # WOPI settings
    wopi_base_url: str = "http://localhost:8000"
    collabora_url: str = "http://localhost:9980"
    
    # Logging settings
    log_level: str = "INFO"
    json_logs: bool = True
    service_name: str = "wopi-service"
    
    # Performance settings
    enable_metrics: bool = True
    metrics_port: int = 9090
    
    class Config:
        env_prefix = "WOPI_"
        env_file = ".env"
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Use SECRET_KEY_BASE if JWT secret not provided
        if not self.jwt_secret_key:
            self.jwt_secret_key = os.getenv("SECRET_KEY_BASE", "development-secret-key")
        
        # Adjust for environment
        if os.getenv("RAILS_ENV") == "production":
            self.csrf_cookie_secure = True
            self.csrf_cookie_samesite = "strict"
        
        # Use FORCE_SSL setting
        if os.getenv("FORCE_SSL", "false").lower() == "true":
            self.csrf_cookie_secure = True


# Global settings instance
settings = WOPISettings()