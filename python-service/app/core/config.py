"""
Application configuration using Pydantic settings
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""
    
    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_PREFIX: str = Field(default="/api/v1")
    
    # Rails API Configuration
    RAILS_API_URL: str = Field(default="http://localhost:3000")
    RAILS_API_KEY: Optional[str] = Field(default=None)
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/excel_unified_development"
    )
    
    # OpenAI Configuration (Fallback when OpenRouter is not available)
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_MODEL: str = Field(default="gpt-4-turbo")  # Updated to valid model name
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    
    # OpenRouter Configuration
    OPENROUTER_API_KEY: Optional[str] = Field(default=None)
    
    # Anthropic Configuration
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    
    # Groq Configuration
    GROQ_API_KEY: Optional[str] = Field(default=None)
    
    # Security
    SECRET_KEY: str = Field(default="your-secret-key-here")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3036", "http://localhost:8081", "file://", "*"]
    )
    
    # Redis Configuration
    REDIS_URL: Optional[str] = Field(default="redis://localhost:6379/0")
    
    # Logging
    LOG_LEVEL: str = Field(default="DEBUG")
    LOG_FORMAT: str = Field(default="json")
    
    # File Upload
    MAX_UPLOAD_SIZE: int = Field(default=10485760)  # 10MB
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[".xlsx", ".xls", ".csv"]
    )
    
    # AI Processing
    MAX_TOKENS: int = Field(default=4000)
    TEMPERATURE: float = Field(default=0.7)
    VISION_TEMPERATURE: float = Field(default=0.1)  # Lower temperature for more accurate vision analysis
    CHUNK_SIZE: int = Field(default=1000)
    OVERLAP_SIZE: int = Field(default=200)
    
    # Excel Service Settings
    EXCEL_CACHE_TTL: int = Field(default=300)  # 5 minutes
    EXCEL_MAX_ERRORS_PER_SHEET: int = Field(default=1000)
    EXCEL_ANALYSIS_TIMEOUT: int = Field(default=300)  # 5 minutes
    
    # WebSocket Settings
    WS_RECONNECT_ATTEMPTS: int = Field(default=5)
    WS_RECONNECT_DELAY: int = Field(default=3000)  # milliseconds
    WS_PING_INTERVAL: int = Field(default=30)  # seconds
    WS_MESSAGE_SIZE_LIMIT: int = Field(default=1048576)  # 1MB
    
    # Performance Settings
    BATCH_PROCESSING_SIZE: int = Field(default=100)
    PARALLEL_WORKERS: int = Field(default=4)
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 추가 환경 변수 무시


# Create settings instance
settings = Settings()