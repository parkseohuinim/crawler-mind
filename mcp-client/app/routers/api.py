"""API routes for MCP Client"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import logging

from app.models import (
    QueryRequest, QueryResponse, ToolsResponse, HealthResponse,
    ProcessUrlRequest, TaskResponse, TaskResult, CrawlingResult
)
from app.services.mcp_service import mcp_service
from app.services.llm_service import llm_service
from app.services.task_service import task_service
from app.utils.exceptions import MCPConnectionError, LLMQueryError

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

@router.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {"message": "MCP FastAPI Server is running"}

@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint"""
    try:
        health_data = await mcp_service.health_check()
        
        return HealthResponse(
            status="healthy" if health_data["connected"] else "unhealthy",
            mcp_connected=health_data["connected"],
            tools_available=health_data["tools_available"],
            details=health_data
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            mcp_connected=False,
            tools_available=0,
            details={"error": str(e)}
        )

@router.get("/tools", response_model=ToolsResponse, tags=["tools"])
async def get_tools():
    """Get available MCP tools"""
    try:
        if not mcp_service.is_connected:
            raise HTTPException(status_code=503, detail="MCP 클라이언트가 연결되지 않음")
        
        tools = mcp_service.available_tools
        
        return ToolsResponse(
            tools=tools,
            success=True
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tools: {e}")
        return ToolsResponse(
            tools=[],
            success=False,
            error=str(e)
        )

@router.post("/query", response_model=QueryResponse, tags=["query"])
async def query_endpoint(request: QueryRequest):
    """Execute a query using LLM and available tools"""
    try:
        if not mcp_service.is_connected:
            raise HTTPException(status_code=503, detail="MCP 클라이언트가 연결되지 않음")
        
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="질문이 비어있습니다")
        
        tools = mcp_service.available_tools
        answer = await llm_service.query(request.question, tools)
        
        return QueryResponse(
            answer=answer,
            success=True
        )
    
    except HTTPException:
        raise
    except (MCPConnectionError, LLMQueryError) as e:
        logger.error(f"Query failed: {e}")
        return QueryResponse(
            answer="",
            success=False,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in query: {e}")
        return QueryResponse(
            answer="",
            success=False,
            error=f"예상치 못한 오류가 발생했습니다: {str(e)}"
        )

@router.post("/query/stream", tags=["query"])
async def query_stream_endpoint(request: QueryRequest):
    """Execute a streaming query using LLM and available tools"""
    try:
        if not mcp_service.is_connected:
            raise HTTPException(status_code=503, detail="MCP 클라이언트가 연결되지 않음")
        
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="질문이 비어있습니다")
        
        tools = mcp_service.available_tools
        
        return StreamingResponse(
            llm_service.query_stream(request.question, tools),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Streaming query failed: {e}")
        raise HTTPException(status_code=500, detail=f"스트리밍 쿼리 실행 중 오류: {str(e)}")

@router.get("/stats", tags=["monitoring"])
async def get_tool_usage_stats():
    """Get tool usage statistics"""
    try:
        stats = mcp_service.get_usage_stats()
        return {
            "tool_usage_stats": stats,
            "total_calls": sum(stats.values()),
            "most_used_tool": max(stats.items(), key=lambda x: x[1]) if stats else None
        }
    except Exception as e:
        logger.error(f"Failed to get usage stats: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 중 오류: {str(e)}")

# Frontend Integration Endpoints

@router.post("/api/process-url", response_model=TaskResponse, tags=["frontend"])
async def process_url(request: ProcessUrlRequest):
    """Start URL processing task"""
    try:
        if not mcp_service.is_connected:
            raise HTTPException(status_code=503, detail="MCP 서버에 연결되지 않았습니다")
        
        # URL 형식 검증
        if not request.url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="올바른 URL 형식이 아닙니다 (http:// 또는 https://로 시작해야 함)")
        
        # 작업 생성
        task_id = task_service.create_task(request.url, request.mode)
        
        logger.info(f"Created task {task_id} for URL: {request.url} with mode: {request.mode}")
        
        return TaskResponse(taskId=task_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"작업 생성 중 오류: {str(e)}")

@router.get("/api/stream/{task_id}", tags=["frontend"])
async def stream_task_updates(task_id: str):
    """Stream task updates via SSE"""
    try:
        task = task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        return StreamingResponse(
            task_service.get_task_stream(task_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "Cache-Control",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"스트림 생성 중 오류: {str(e)}")

@router.get("/api/result/{task_id}", response_model=TaskResult, tags=["frontend"])
async def get_task_result(task_id: str):
    """Get task result"""
    try:
        task = task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task result {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"결과 조회 중 오류: {str(e)}")