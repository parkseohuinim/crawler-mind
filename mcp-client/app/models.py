"""Pydantic models for API requests and responses"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    question: str = Field(..., description="The question to ask the LLM", min_length=1)

class QueryResponse(BaseModel):
    """Response model for query endpoint"""
    answer: str = Field(..., description="The LLM's response")
    success: bool = Field(..., description="Whether the query was successful")
    error: Optional[str] = Field(None, description="Error message if query failed")

class ToolsResponse(BaseModel):
    """Response model for tools endpoint"""
    tools: List[Dict[str, Any]] = Field(..., description="List of available tools")
    success: bool = Field(..., description="Whether the request was successful")
    error: Optional[str] = Field(None, description="Error message if request failed")

class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str = Field(..., description="Health status")
    mcp_connected: bool = Field(..., description="Whether MCP client is connected")
    tools_available: int = Field(..., description="Number of available tools")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional health details")

class ProcessingMode(str, Enum):
    """Processing mode for URL analysis"""
    AUTO = "auto"
    BASIC = "basic"

class ProcessUrlRequest(BaseModel):
    """Request model for process URL endpoint"""
    url: str = Field(..., description="The URL to process", min_length=1)
    mode: ProcessingMode = Field(ProcessingMode.AUTO, description="Processing mode")

class TaskResponse(BaseModel):
    """Response model for task creation"""
    taskId: str = Field(..., description="Unique task identifier")

class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class CrawlingResult(BaseModel):
    """Crawling result model"""
    json_data: Optional[List[Dict[str, Any]]] = Field(None, description="RAG JSON formatted data")

class TaskResult(BaseModel):
    """Task result model"""
    taskId: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="Task status")
    result: Optional[CrawlingResult] = Field(None, description="Crawling result")
    error: Optional[str] = Field(None, description="Error message if failed")
    createdAt: str = Field(..., description="Task creation timestamp")
    completedAt: Optional[str] = Field(None, description="Task completion timestamp")

# ARI API Models
class StructuredTableRow(BaseModel):
    """구조화된 테이블 행 데이터"""
    data: Dict[str, str] = Field(..., description="컬럼명: 값 매핑")

class StructuredTable(BaseModel):
    """구조화된 테이블 모델"""
    table_name: str = Field(..., description="테이블 이름")
    columns: List[str] = Field(..., description="컬럼 목록")
    rows: List[StructuredTableRow] = Field(..., description="테이블 행 데이터")
    is_merged: bool = Field(False, description="병합된 셀이 있는지 여부")

class AriCrawlResult(BaseModel):
    """ARI crawling result model"""
    content: Dict[str, Any] = Field(
        ..., description="Extracted content data (e.g., contents array)"
    )

class AriCrawlResponse(BaseModel):
    """Response model for ARI crawling endpoint (Task-like schema)"""
    taskId: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="Task status")
    result: List[AriCrawlResult] = Field(..., description="List of extracted results per file")
    error: Optional[str] = Field(None, description="Error message if failed")
    createdAt: str = Field(..., description="Task creation timestamp")
    completedAt: Optional[str] = Field(None, description="Task completion timestamp")
    message: str = Field(..., description="Processing result message")
    total_files: int = Field(..., description="Number of processed files")
    total_size: int = Field(..., description="Total file size in bytes")

