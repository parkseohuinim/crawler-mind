"""RAG schemas for API requests and responses"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class RagUploadResponse(BaseModel):
    """Response for RAG file upload"""
    message: str
    processed_count: int
    failed_count: int
    failed_documents: List[str] = []


class RagQueryRequest(BaseModel):
    """Request for RAG query"""
    query: str
    max_results: int = 5
    similarity_threshold: float = 0.7


class RagQueryResponse(BaseModel):
    """Response for RAG query"""
    answer: str
    sources: List[Dict[str, Any]]
    query: str
    processing_time: float


class DocumentChunk(BaseModel):
    """Document chunk for similarity search"""
    id: str
    title: str
    content: str
    url: Optional[str] = None
    hierarchy: Optional[List[str]] = None
    similarity_score: float
    metadata: Optional[Dict[str, Any]] = None
