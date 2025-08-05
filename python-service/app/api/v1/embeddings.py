"""
Embeddings and vector search API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.services.openai_service import openai_service
from app.services.vector_search import vector_search_service

logger = logging.getLogger(__name__)

router = APIRouter()


class EmbeddingRequest(BaseModel):
    text: str


class DocumentIndexRequest(BaseModel):
    document_id: str
    document_type: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class BatchDocumentIndexRequest(BaseModel):
    documents: List[DocumentIndexRequest]


class SearchRequest(BaseModel):
    query: str
    document_type: Optional[str] = None
    limit: int = 10
    threshold: float = 0.7


@router.post("/generate")
async def generate_embedding(request: EmbeddingRequest) -> Dict[str, Any]:
    """
    Generate embedding for a given text
    """
    try:
        embedding = await openai_service.generate_embedding(request.text)

        return {
            "text": request.text,
            "embedding": embedding,
            "dimension": len(embedding),
            "model": "vertex-ai-text-embedding-004",  # Using Vertex AI
        }
    except Exception as e:
        logger.error(f"Embedding generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index-document")
async def index_document(
    request: DocumentIndexRequest, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Index a document with its embedding
    """
    try:
        doc_id = await vector_search_service.index_document(
            document_id=request.document_id,
            document_type=request.document_type,
            content=request.content,
            metadata=request.metadata,
            db=db,
        )

        return {
            "success": True,
            "document_id": request.document_id,
            "embedding_id": doc_id,
        }
    except Exception as e:
        logger.error(f"Document indexing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index-batch")
async def index_documents_batch(
    request: BatchDocumentIndexRequest, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Index multiple documents in batch
    """
    try:
        documents = [
            {
                "document_id": doc.document_id,
                "document_type": doc.document_type,
                "content": doc.content,
                "metadata": doc.metadata,
            }
            for doc in request.documents
        ]

        doc_ids = await vector_search_service.index_documents_batch(
            documents=documents, db=db
        )

        return {
            "success": True,
            "indexed_count": len(doc_ids),
            "embedding_ids": doc_ids,
        }
    except Exception as e:
        logger.error(f"Batch indexing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_similar_documents(
    request: SearchRequest, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Search for similar documents using vector similarity
    """
    try:
        results = await vector_search_service.search_similar_documents(
            query=request.query,
            document_type=request.document_type,
            limit=request.limit,
            threshold=request.threshold,
            db=db,
        )

        return {"query": request.query, "results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update-document/{document_id}")
async def update_document_embedding(
    document_id: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Update an existing document's embedding
    """
    try:
        success = await vector_search_service.update_document_embedding(
            document_id=document_id, content=content, metadata=metadata, db=db
        )

        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        return {"success": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document update error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/document/{document_id}")
async def delete_document_embedding(
    document_id: str, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete a document's embedding
    """
    try:
        success = await vector_search_service.delete_document_embedding(
            document_id=document_id, db=db
        )

        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        return {"success": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document deletion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
