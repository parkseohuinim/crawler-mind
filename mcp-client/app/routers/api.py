"""API routes for MCP Client"""
from fastapi import APIRouter, HTTPException, Query, Depends, Path
from fastapi.responses import StreamingResponse
import logging
import math

from app.models import (
    QueryRequest, QueryResponse, ToolsResponse, HealthResponse,
    ProcessUrlRequest, TaskResponse, TaskResult, CrawlingResult
)
from app.infrastructure.mcp.mcp_service import mcp_service
from app.infrastructure.llm.llm_service import llm_service  
from app.application.crawler.crawler_service import crawler_service
from app.shared.exceptions.base import MCPConnectionError, LLMQueryError
from app.shared.database.base import get_database_session
from app.application.menu.menu_service import MenuApplicationService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

# Dependency to get menu service
async def get_menu_service(db: AsyncSession = Depends(get_database_session)) -> MenuApplicationService:
    """Dependency to get menu application service"""
    return MenuApplicationService(db)

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

@router.post("/process-url", response_model=TaskResponse, tags=["frontend"])
async def process_url(request: ProcessUrlRequest):
    """Start URL processing task"""
    try:
        if not mcp_service.is_connected:
            raise HTTPException(status_code=503, detail="MCP 서버에 연결되지 않았습니다")
        
        # URL 형식 검증
        if not request.url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="올바른 URL 형식이 아닙니다 (http:// 또는 https://로 시작해야 함)")
        
        # 작업 생성
        task_id = crawler_service.create_task(request.url, request.mode)
        
        logger.info(f"Created task {task_id} for URL: {request.url} with mode: {request.mode}")
        
        return TaskResponse(taskId=task_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"작업 생성 중 오류: {str(e)}")

@router.get("/stream/{task_id}", tags=["frontend"])
async def stream_task_updates(task_id: str):
    """Stream task updates via SSE"""
    try:
        task = crawler_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        return StreamingResponse(
            crawler_service.get_task_stream(task_id),
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

@router.get("/result/{task_id}", response_model=TaskResult, tags=["frontend"])
async def get_task_result(task_id: str):
    """Get task result"""
    try:
        task = crawler_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task result {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"결과 조회 중 오류: {str(e)}")


# ===== MENU LINKS API (Legacy Compatibility) =====
# These endpoints use the new DDD services but maintain the old API contract

@router.get("/menu-links", tags=["menu-links"])
async def get_menu_links(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=1000, description="Page size"),
    search: str = Query(None, description="Search term"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get menu links with pagination and search (Legacy API)"""
    try:
        skip = (page - 1) * size
        result = await service.get_menu_links(skip, size, search)
        return {
            "items": [item.model_dump() for item in result.items],
            "total": result.total,
            "page": result.page,
            "size": result.size,
            "pages": result.pages
        }
    except Exception as e:
        logger.error(f"Menu links 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Menu links 조회 중 오류가 발생했습니다")

@router.get("/menu-links/available-for-manager", tags=["menu-links"])
async def get_available_menu_links_for_manager(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Page size"),
    search: str = Query(None, description="Search term"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get menu links available for manager assignment (Legacy API)"""
    try:
        skip = (page - 1) * size
        result = await service.get_available_menu_links_for_manager(skip, size, search)
        return {
            "items": [item.model_dump() for item in result.items],
            "total": result.total,
            "page": result.page,
            "size": result.size,
            "pages": result.pages
        }
    except Exception as e:
        logger.error(f"Available menu links 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Available menu links 조회 중 오류가 발생했습니다")

@router.get("/menu-links/manager-info-list", tags=["menu-links"])
async def get_manager_info_list(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=1000, description="Page size"),
    search: str = Query(None, description="Search term"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get manager info list with pagination (Legacy API)"""
    try:
        skip = (page - 1) * size
        result = await service.get_manager_info_list(skip, size, search)
        return {
            "items": [item.model_dump() for item in result.items],
            "total": result.total,
            "page": result.page,
            "size": result.size,
            "pages": result.pages
        }
    except Exception as e:
        logger.error(f"Manager info list 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Manager info list 조회 중 오류가 발생했습니다")

@router.post("/menu-links/manager-info-create", tags=["menu-links"])
async def create_manager_info(
    manager_info_data: dict,
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Create menu manager info (Legacy API)"""
    try:
        from app.domains.menu.schemas.menu_manager_schemas import MenuManagerInfoCreate
        
        # Convert dict to schema
        create_schema = MenuManagerInfoCreate(**manager_info_data)
        result = await service.create_manager_info(create_schema)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Manager info 생성 중 오류 발생: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/menu-links/manager-info-update/{manager_info_id}", tags=["menu-links"])
async def update_manager_info(
    manager_info_id: int = Path(..., description="Manager info ID"),
    manager_info_data: dict = ...,
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Update manager info (Legacy API)"""
    try:
        from app.domains.menu.schemas.menu_manager_schemas import MenuManagerInfoUpdate
        
        # Convert dict to schema
        update_schema = MenuManagerInfoUpdate(**manager_info_data)
        result = await service.update_manager_info(manager_info_id, update_schema)
        if not result:
            raise HTTPException(status_code=404, detail="Manager info not found")
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager info 수정 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Manager info 수정 중 오류가 발생했습니다")

@router.delete("/menu-links/manager-info-delete/{manager_info_id}", tags=["menu-links"])
async def delete_manager_info(
    manager_info_id: int = Path(..., description="Manager info ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Delete manager info (Legacy API)"""
    try:
        result = await service.delete_manager_info(manager_info_id)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Manager info 삭제 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Manager info 삭제 중 오류가 발생했습니다")

@router.get("/menu-links/with-managers", tags=["menu-links"])
async def get_menu_links_with_managers(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=1000, description="Page size"),
    search: str = Query(None, description="Search term"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get menu links with their manager info (Legacy API)"""
    try:
        skip = (page - 1) * size
        results = await service.get_menu_links_with_managers(skip, size, search)
        return [result.model_dump() for result in results]
    except Exception as e:
        logger.error(f"Menu links with managers 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Menu links with managers 조회 중 오류가 발생했습니다")

# Individual Menu Link CRUD
@router.post("/menu-links", tags=["menu-links"])
async def create_menu_link(
    menu_link_data: dict,
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Create a new menu link (Legacy API)"""
    try:
        from app.domains.menu.schemas.menu_link_schemas import MenuLinkCreate
        
        create_schema = MenuLinkCreate(**menu_link_data)
        result = await service.create_menu_link(create_schema)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Menu link 생성 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Menu link 생성 중 오류가 발생했습니다")

@router.get("/menu-links/{menu_link_id}", tags=["menu-links"])
async def get_menu_link_by_id(
    menu_link_id: int = Path(..., description="Menu link ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get a menu link by ID (Legacy API)"""
    try:
        result = await service.get_menu_link(menu_link_id)
        if not result:
            raise HTTPException(status_code=404, detail="Menu link not found")
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Menu link 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Menu link 조회 중 오류가 발생했습니다")

@router.put("/menu-links/{menu_link_id}", tags=["menu-links"])
async def update_menu_link(
    menu_link_data: dict,
    menu_link_id: int = Path(..., description="Menu link ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Update a menu link (Legacy API)"""
    try:
        from app.domains.menu.schemas.menu_link_schemas import MenuLinkUpdate
        
        update_schema = MenuLinkUpdate(**menu_link_data)
        result = await service.update_menu_link(menu_link_id, update_schema)
        if not result:
            raise HTTPException(status_code=404, detail="Menu link not found")
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Menu link 수정 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Menu link 수정 중 오류가 발생했습니다")

@router.delete("/menu-links/{menu_link_id}", tags=["menu-links"])
async def delete_menu_link(
    menu_link_id: int = Path(..., description="Menu link ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Delete a menu link (Legacy API)"""
    try:
        result = await service.delete_menu_link(menu_link_id)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Menu link 삭제 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Menu link 삭제 중 오류가 발생했습니다")

# Manager Info by Menu ID
@router.get("/menu-links/{menu_link_id}/manager-info", tags=["menu-links"])
async def get_manager_info_by_menu_id(
    menu_link_id: int = Path(..., description="Menu link ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get manager info by menu ID (Legacy API)"""
    try:
        result = await service.get_manager_info_by_menu_id(menu_link_id)
        if not result:
            raise HTTPException(status_code=404, detail="Manager info not found")
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager info 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Manager info 조회 중 오류가 발생했습니다")

# Manager Info by ID
@router.get("/menu-links/manager-info/{manager_info_id}", tags=["menu-links"])
async def get_manager_info_by_id(
    manager_info_id: int = Path(..., description="Manager info ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get manager info by ID (Legacy API)"""
    try:
        result = await service.get_manager_info(manager_info_id)
        if not result:
            raise HTTPException(status_code=404, detail="Manager info not found")
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager info 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Manager info 조회 중 오류가 발생했습니다")

