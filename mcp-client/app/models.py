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
    title: Optional[str] = Field(None, description="Page title")
    textLength: Optional[int] = Field(None, description="Length of extracted text")
    linkCount: Optional[int] = Field(None, description="Number of links found")
    links: Optional[List[str]] = Field(None, description="List of found links")
    summary: Optional[str] = Field(None, description="Content summary")
    screenshot: Optional[str] = Field(None, description="Base64 encoded screenshot")
    error: Optional[str] = Field(None, description="Error message if failed")

class TaskResult(BaseModel):
    """Task result model"""
    taskId: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="Task status")
    result: Optional[CrawlingResult] = Field(None, description="Crawling result")
    error: Optional[str] = Field(None, description="Error message if failed")
    createdAt: str = Field(..., description="Task creation timestamp")
    completedAt: Optional[str] = Field(None, description="Task completion timestamp")