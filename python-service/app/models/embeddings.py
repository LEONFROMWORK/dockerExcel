"""
Database models for embeddings and vector operations
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


class DocumentEmbedding(Base):
    """Model for storing document embeddings"""
    __tablename__ = "document_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String, nullable=False, index=True)
    document_type = Column(String, nullable=False)  # excel_file, qa_pair, etc.
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # OpenAI embedding dimension
    document_metadata = Column(Text)  # JSON string for additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SearchCache(Base):
    """Model for caching search results"""
    __tablename__ = "search_cache"
    
    id = Column(Integer, primary_key=True)
    query = Column(String, nullable=False, unique=True, index=True)
    query_embedding = Column(Vector(1536))
    results = Column(Text, nullable=False)  # JSON string
    ttl = Column(Integer, default=3600)  # Time to live in seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())