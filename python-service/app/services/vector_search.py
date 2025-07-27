"""
Vector search service for semantic similarity
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
import logging
from datetime import datetime, timedelta

from app.services.openai_service import openai_service
from app.models.embeddings import DocumentEmbedding, SearchCache
from app.core.database import get_db

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service for vector-based semantic search"""
    
    async def search_similar_documents(
        self,
        query: str,
        document_type: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.7,
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity"""
        
        # Check cache first
        cached_results = await self._get_cached_results(query, db)
        if cached_results:
            return cached_results
        
        # Generate query embedding
        query_embedding = await openai_service.generate_embedding(query)
        
        # Build the similarity search query
        sql_query = """
        SELECT 
            id,
            document_id,
            document_type,
            content,
            document_metadata,
            1 - (embedding <=> :embedding::vector) as similarity
        FROM document_embeddings
        WHERE 1 - (embedding <=> :embedding::vector) > :threshold
        """
        
        params = {
            "embedding": query_embedding,
            "threshold": threshold
        }
        
        if document_type:
            sql_query += " AND document_type = :document_type"
            params["document_type"] = document_type
        
        sql_query += " ORDER BY similarity DESC LIMIT :limit"
        params["limit"] = limit
        
        # Execute search
        result = await db.execute(text(sql_query), params)
        rows = result.fetchall()
        
        # Format results
        results = []
        for row in rows:
            results.append({
                "id": str(row.id),
                "document_id": row.document_id,
                "document_type": row.document_type,
                "content": row.content,
                "metadata": json.loads(row.document_metadata) if row.document_metadata else {},
                "similarity": float(row.similarity)
            })
        
        # Cache results
        await self._cache_results(query, query_embedding, results, db)
        
        return results
    
    async def index_document(
        self,
        document_id: str,
        document_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None
    ) -> str:
        """Index a document with its embedding"""
        
        # Generate embedding
        embedding = await openai_service.generate_embedding(content)
        
        # Create embedding record
        doc_embedding = DocumentEmbedding(
            document_id=document_id,
            document_type=document_type,
            content=content,
            embedding=embedding,
            document_metadata=json.dumps(metadata) if metadata else None
        )
        
        db.add(doc_embedding)
        await db.commit()
        
        logger.info(f"Indexed document {document_id} of type {document_type}")
        return str(doc_embedding.id)
    
    async def index_documents_batch(
        self,
        documents: List[Dict[str, Any]],
        db: AsyncSession = None
    ) -> List[str]:
        """Index multiple documents in batch"""
        
        # Extract content for embedding
        contents = [doc["content"] for doc in documents]
        
        # Generate embeddings in batch
        embeddings = await openai_service.generate_embeddings_batch(contents)
        
        # Create embedding records
        doc_ids = []
        for doc, embedding in zip(documents, embeddings):
            doc_embedding = DocumentEmbedding(
                document_id=doc["document_id"],
                document_type=doc["document_type"],
                content=doc["content"],
                embedding=embedding,
                document_metadata=json.dumps(doc.get("metadata")) if doc.get("metadata") else None
            )
            db.add(doc_embedding)
            doc_ids.append(str(doc_embedding.id))
        
        await db.commit()
        
        logger.info(f"Indexed {len(documents)} documents in batch")
        return doc_ids
    
    async def update_document_embedding(
        self,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None
    ) -> bool:
        """Update an existing document's embedding"""
        
        # Find existing document
        result = await db.execute(
            text("SELECT id FROM document_embeddings WHERE document_id = :doc_id"),
            {"doc_id": document_id}
        )
        row = result.first()
        
        if not row:
            logger.warning(f"Document {document_id} not found for update")
            return False
        
        # Generate new embedding
        embedding = await openai_service.generate_embedding(content)
        
        # Update document
        await db.execute(
            text("""
                UPDATE document_embeddings 
                SET content = :content,
                    embedding = :embedding::vector,
                    metadata = :metadata,
                    updated_at = CURRENT_TIMESTAMP
                WHERE document_id = :doc_id
            """),
            {
                "content": content,
                "embedding": embedding,
                "metadata": json.dumps(metadata) if metadata else None,
                "doc_id": document_id
            }
        )
        
        await db.commit()
        logger.info(f"Updated embedding for document {document_id}")
        return True
    
    async def delete_document_embedding(
        self,
        document_id: str,
        db: AsyncSession = None
    ) -> bool:
        """Delete a document's embedding"""
        
        result = await db.execute(
            text("DELETE FROM document_embeddings WHERE document_id = :doc_id"),
            {"doc_id": document_id}
        )
        
        await db.commit()
        deleted = result.rowcount > 0
        
        if deleted:
            logger.info(f"Deleted embedding for document {document_id}")
        
        return deleted
    
    async def _get_cached_results(
        self,
        query: str,
        db: AsyncSession
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results"""
        
        # Check if caching is enabled
        if not hasattr(self, '_cache_enabled'):
            self._cache_enabled = True
        
        if not self._cache_enabled:
            return None
        
        # Look for cached results
        result = await db.execute(
            text("""
                SELECT results, created_at, ttl
                FROM search_cache
                WHERE query = :query
            """),
            {"query": query}
        )
        
        row = result.first()
        if row:
            # Check if cache is still valid
            cache_age = datetime.utcnow() - row.created_at
            if cache_age.total_seconds() < row.ttl:
                logger.info(f"Using cached results for query: {query}")
                return json.loads(row.results)
            else:
                # Delete expired cache
                await db.execute(
                    text("DELETE FROM search_cache WHERE query = :query"),
                    {"query": query}
                )
                await db.commit()
        
        return None
    
    async def _cache_results(
        self,
        query: str,
        query_embedding: List[float],
        results: List[Dict[str, Any]],
        db: AsyncSession,
        ttl: int = 3600
    ):
        """Cache search results"""
        
        if not hasattr(self, '_cache_enabled'):
            self._cache_enabled = True
        
        if not self._cache_enabled:
            return
        
        try:
            await db.execute(
                text("""
                    INSERT INTO search_cache (query, query_embedding, results, ttl)
                    VALUES (:query, :embedding::vector, :results, :ttl)
                    ON CONFLICT (query) DO UPDATE
                    SET query_embedding = :embedding::vector,
                        results = :results,
                        ttl = :ttl,
                        created_at = CURRENT_TIMESTAMP
                """),
                {
                    "query": query,
                    "embedding": query_embedding,
                    "results": json.dumps(results),
                    "ttl": ttl
                }
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to cache search results: {str(e)}")


# Create singleton instance
vector_search_service = VectorSearchService()