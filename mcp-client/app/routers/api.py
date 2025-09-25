"""API routes for MCP Client"""
from fastapi import APIRouter, HTTPException, Query, Depends, Path, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response
import logging
import math
from typing import List
from datetime import datetime

from pydantic import BaseModel, Field
from app.models import (
    QueryRequest, QueryResponse, ToolsResponse, HealthResponse,
    TaskResponse, TaskResult, CrawlingResult,
    AriCrawlResponse, TaskStatus
)
from app.infrastructure.mcp.mcp_service import mcp_service
from app.infrastructure.llm.llm_service import llm_service  
from app.application.crawler.crawling_service import crawling_service
from app.shared.exceptions.base import MCPConnectionError, LLMQueryError
from app.shared.database.base import get_database_session
from app.application.menu.menu_service import MenuApplicationService
from app.presentation.api.rag.rag_router import router as rag_router
from app.presentation.api.json_compare.json_compare_router import router as json_compare_router
from app.application.ari.ari_service import ari_service
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

# === RAG Crawling Endpoints ===

class RAGCrawlRequest(BaseModel):
    """Request model for RAG crawling endpoint"""
    urls: str = Field(
        ..., 
        description="크롤링할 URL들 또는 자연어 요청 (예: 'KT 로밍 상품 페이지들을 크롤링해주세요: https://... https://...')", 
        min_length=1,
        examples=[
            "https://example1.com https://example2.com",
            "다음 페이지들을 분석해주세요:\nhttps://site1.com/page1\nhttps://site2.com/page2",
            "KT 로밍 상품 정보를 크롤링하고 싶습니다. https://globalroaming.kt.com/product/data/dru_talk.asp https://globalroaming.kt.com/product/data/dru_unlimit.asp"
        ]
    )

@router.post("/rag-crawl", response_model=TaskResponse, tags=["rag-crawling"])
async def create_rag_crawl_task(request: RAGCrawlRequest):
    """
    Create RAG crawling task for multiple URLs with intelligent parsing
    
    Supports:
    - Multiple URL formats (space-separated, newline-separated)
    - Natural language requests with URLs
    - Automatic URL extraction using LLM + regex
    - Based on rag-scraping app.py workflow
    """
    try:
        if not mcp_service.is_connected:
            raise HTTPException(status_code=503, detail="MCP 서버에 연결되지 않음")
        
        if not request.urls.strip():
            raise HTTPException(status_code=400, detail="URL이 비어있습니다")
        
        # Create RAG crawling task
        task_id = crawling_service.create_task(request.urls)
        logger.info(f"✅ RAG crawling task created: {task_id}")
        
        return TaskResponse(taskId=task_id)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG crawling task creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"RAG 크롤링 작업 생성 실패: {str(e)}")

@router.get("/rag-crawl/{task_id}", response_model=TaskResult, tags=["rag-crawling"])
async def get_rag_crawl_task(task_id: str = Path(..., description="Task ID")):
    """Get RAG crawling task status and result"""
    try:
        task = crawling_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        return task
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG task retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"RAG 작업 조회 실패: {str(e)}")

@router.get("/rag-crawl/{task_id}/stream", tags=["rag-crawling"])
async def stream_rag_crawl_task(task_id: str = Path(..., description="Task ID")):
    """Stream RAG crawling task updates via Server-Sent Events"""
    try:
        task = crawling_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        logger.info(f"🎯 RAG SSE stream requested for task: {task_id}")
        
        return StreamingResponse(
            crawling_service.get_task_stream(task_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG SSE stream creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"RAG 스트림 생성 실패: {str(e)}")

# === ARI HTML Processing Endpoints ===

@router.post("/ari/crawl", response_model=AriCrawlResponse, tags=["ari"])
async def ari_crawl_endpoint(
    files: List[UploadFile] = File(..., description="HTML 파일들 (복수 파일 지원)")
):
    """Process HTML files from ARI for RAG conversion"""
    try:
        if not files:
            raise HTTPException(status_code=400, detail="업로드할 HTML 파일이 없습니다")
        
        # HTML 파일 처리 (기존 저장/메타 유지) + 마크다운 → JSON 파싱 추가
        result = await ari_service.process_html_files(files)
        if not result['success']:
            raise HTTPException(status_code=500, detail=result['message'])

        structured_results: List[dict] = []
        for info in result['processed_files']:
            try:
                # 원본 HTML 로드
                with open(info['file_path'], 'r', encoding='utf-8', errors='ignore') as rf:
                    html = rf.read()

                # 1) HTML → Markdown (Confluence main-content 기반)
                md = ari_service.extract_markdown(html)

                # 2) Markdown → JSON(contents)
                tool_res = await mcp_service.call_tool('ari_markdown_to_json', {"markdown_content": md})
                # MCP 결과 안전 해석
                if hasattr(tool_res, 'structured_content'):
                    tool_payload = tool_res.structured_content
                elif hasattr(tool_res, 'data'):
                    tool_payload = tool_res.data
                else:
                    tool_payload = tool_res if isinstance(tool_res, dict) else {}
                contents = tool_payload.get('contents', []) if tool_payload.get('success') else []
                if not contents:
                    # 폴백: 마크다운을 텍스트 단락으로 반환
                    contents = [{"id": 1, "type": "text", "title": "", "data": md}]

                # 메타데이터: 기존 처리에서 추출된 제목/길이 활용
                meta_src = info.get('processed_data', {}).get('metadata', {})
                structured_results.append({
                    'content': {
                        'contents': contents
                    }
                })
            except Exception as pe:
                logger.error(f"ARI crawl item 구조화 실패: {pe}")
                structured_results.append({
                    'content': {
                        'contents': [{"id": 1, "type": "text", "title": "", "data": "구조화 중 오류가 발생했습니다."}]
                    }
                })

        # 응답 데이터 구성 (AriCrawlResponse 모델 유지)
        response_data = AriCrawlResponse(
            taskId=f"ari_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            status=TaskStatus.COMPLETED,
            result=structured_results,  # contents 기반 결과
            error=None,
            createdAt=result['processed_files'][0]['upload_time'] if result['processed_files'] else datetime.now().isoformat(),
            completedAt=datetime.now().isoformat(),
            message=result['message'],
            total_files=result['total_files'],
            total_size=result['total_size']
        )
        
        logger.info(f"✅ ARI HTML 처리 완료: {result['total_files']}개 파일, {result['total_size']} bytes")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ARI HTML 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"ARI HTML 처리 중 오류가 발생했습니다: {str(e)}")


class AriProcessRequest(BaseModel):
    """HTML 콘텐츠 기반 ARI 처리 요청 (내부망: URL 크롤링 비사용)"""
    htmls: List[str] = Field(..., description="직접 전달할 HTML 콘텐츠 목록")


@router.post("/ari/process", tags=["ari"])
async def ari_process_endpoint(request: AriProcessRequest):
    """
    자연어/URL/HTML 입력을 받아 Confluence HTML을 전처리/파싱하여 주요 내용만 추출합니다.
    - htmls가 제공되면 그대로 처리
    - urls가 제공되면 MCP의 crawl4ai_scrape 툴로 크롤링 후 처리
    - query만 있는 경우, query에서 URL들을 추출하여 처리
    반환: { success, processed, total_inputs, results: [processed_data...], errors: [...] }
    """
    try:
        errors: List[dict] = []
        candidate_htmls: List[str] = []
        # HTML 직접 전달만 처리
        for html in request.htmls:
            if isinstance(html, str) and html.strip():
                candidate_htmls.append(html)

        if not candidate_htmls:
            raise HTTPException(status_code=400, detail="처리할 HTML이 비어있습니다")

        # ARI 파이프라인 수행: HTML -> Markdown -> JSON(contents)
        results: List[dict] = []
        for html in candidate_htmls:
            try:
                md = ari_service.extract_markdown(html)
                tool_res = await mcp_service.call_tool('ari_markdown_to_json', {"markdown_content": md})
                if hasattr(tool_res, 'structured_content'):
                    tool_payload = tool_res.structured_content
                elif hasattr(tool_res, 'data'):
                    tool_payload = tool_res.data
                else:
                    tool_payload = tool_res if isinstance(tool_res, dict) else {}
                contents = tool_payload.get('contents', []) if tool_payload.get('success') else []
                if not contents:
                    contents = [{"id": 1, "type": "text", "title": "", "data": md}]

                results.append({
                    'content': {
                        'contents': contents
                    }
                })
            except Exception as pe:
                errors.append({"error": f"parse failed: {str(pe)}"})

        return {
            "success": True,
            "total_inputs": len(candidate_htmls),
            "processed": len(results),
            "results": results,
            "errors": errors,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ARI process failed: {e}")
        raise HTTPException(status_code=500, detail=f"ARI 처리 실패: {str(e)}")


@router.post("/ari/markdown", tags=["ari"])
async def ari_markdown_endpoint(
    files: List[UploadFile] = File(..., description="HTML 파일들 (복수 파일 지원)")
):
    """
    HTML을 받아 테이블만 마크다운으로 변환하여 반환합니다.
    - 반환 필드: tables_markdown(list[str])
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="업로드할 HTML 파일이 없습니다")
        fragments: List[str] = []
        for file in files:
            if not file.filename.endswith('.html'):
                continue
            content = await file.read()
            html = content.decode('utf-8', errors='ignore')
            md = ari_service.extract_markdown(html)
            fragments.append(md)
        final_md = "\n\n".join(fragments)
        return Response(content=final_md, media_type="text/markdown; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ARI markdown failed: {e}")
        raise HTTPException(status_code=500, detail=f"ARI 마크다운 생성 실패: {str(e)}")

# Include RAG router
router.include_router(rag_router)

# Include JSON Compare router
router.include_router(json_compare_router)
