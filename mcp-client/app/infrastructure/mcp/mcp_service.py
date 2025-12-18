"""MCP Client Service - Handles all MCP server interactions"""
from typing import List, Dict, Any, Optional
import asyncio
import logging
from fastmcp import Client
from app.config import settings
from app.shared.exceptions.base import MCPConnectionError, MCPToolExecutionError

logger = logging.getLogger(__name__)

# 재연결 설정
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 2.0  # seconds


class MCPService:
    """Service class for managing MCP client operations"""
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._tools_cache: List[Dict[str, Any]] = []
        self._connection_lock = asyncio.Lock()
        self._tool_usage_stats: Dict[str, int] = {}  # 도구 사용 통계
        self._reconnecting = False
        
    async def initialize(self) -> None:
        """Initialize MCP client connection"""
        async with self._connection_lock:
            if self._client is not None:
                return
                
            try:
                self._client = Client(settings.mcp_server_url)
                await self._client.__aenter__()
                
                # Cache available tools
                await self._refresh_tools_cache()
                
                logger.info(f"MCP Client connected to {settings.mcp_server_url}")
                logger.info(f"Available tools: {[tool['name'] for tool in self._tools_cache]}")
                
            except Exception as e:
                logger.error(f"Failed to initialize MCP client: {e}")
                self._client = None
                raise MCPConnectionError(f"MCP client initialization failed: {str(e)}")
    
    async def shutdown(self) -> None:
        """Cleanup MCP client connection"""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
                logger.info("MCP Client connection closed")
            except Exception as e:
                logger.error(f"Error during MCP client shutdown: {e}")
            finally:
                self._client = None
                self._tools_cache = []
    
    async def _refresh_tools_cache(self) -> None:
        """Refresh the cached tools list"""
        if not self._client:
            raise MCPConnectionError("MCP client not initialized")
            
        try:
            from app.shared.utils.schema_converter import to_openai_schema
            
            mcp_tools = await self._client.list_tools()
            self._tools_cache = [to_openai_schema(tool) for tool in mcp_tools]
            
        except Exception as e:
            logger.error(f"Failed to refresh tools cache: {e}")
            raise MCPConnectionError(f"Failed to get tools list: {str(e)}")
    
    @property
    def is_connected(self) -> bool:
        """Check if MCP client is connected"""
        return self._client is not None and self._client.is_connected()
    
    @property
    def available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools"""
        return self._tools_cache.copy()
    
    async def _reconnect(self) -> bool:
        """연결이 끊어진 경우 재연결 시도"""
        if self._reconnecting:
            # 이미 재연결 중이면 대기
            for _ in range(30):  # 최대 30초 대기
                await asyncio.sleep(1)
                if self.is_connected:
                    return True
            return False
        
        async with self._connection_lock:
            if self.is_connected:
                return True
            
            self._reconnecting = True
            try:
                for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
                    try:
                        logger.warning(f"🔄 MCP 재연결 시도 ({attempt}/{MAX_RECONNECT_ATTEMPTS})...")
                        
                        # 기존 연결 정리
                        if self._client:
                            try:
                                await self._client.__aexit__(None, None, None)
                            except:
                                pass
                            self._client = None
                        
                        # 새 연결
                        self._client = Client(settings.mcp_server_url)
                        await self._client.__aenter__()
                        await self._refresh_tools_cache()
                        
                        logger.info(f"✅ MCP 재연결 성공!")
                        return True
                        
                    except Exception as e:
                        logger.error(f"❌ MCP 재연결 실패 ({attempt}/{MAX_RECONNECT_ATTEMPTS}): {e}")
                        if attempt < MAX_RECONNECT_ATTEMPTS:
                            await asyncio.sleep(RECONNECT_DELAY)
                
                return False
            finally:
                self._reconnecting = False
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on the MCP server (with auto-reconnect)"""
        # 연결 확인 및 재연결
        if not self.is_connected:
            logger.warning(f"⚠️ MCP 연결 끊김 감지, 재연결 시도...")
            if not await self._reconnect():
                raise MCPConnectionError("MCP client not connected and reconnection failed")
        
        try:
            logger.debug(f"🚀 Calling MCP tool: {tool_name}")
            result = await self._client.call_tool(tool_name, arguments)
            
            # 사용 통계 업데이트
            self._tool_usage_stats[tool_name] = self._tool_usage_stats.get(tool_name, 0) + 1
            
            # CallToolResult를 dict로 변환
            result_dict = self._parse_tool_result(result)
            
            # 결과 요약만 로그 (전체 내용 출력 방지)
            result_summary = f"success={result_dict.get('success', 'N/A')}"
            logger.debug(f"✅ Tool '{tool_name}' completed. {result_summary}")
            return result_dict
            
        except MCPConnectionError:
            raise
        except Exception as e:
            # 연결 오류인 경우 재연결 시도
            error_str = str(e).lower()
            if "connect" in error_str or "closed" in error_str or "disconnected" in error_str:
                logger.warning(f"⚠️ 연결 오류 감지, 재연결 후 재시도...")
                if await self._reconnect():
                    # 재연결 성공 시 한 번 더 시도
                    try:
                        result = await self._client.call_tool(tool_name, arguments)
                        return self._parse_tool_result(result)
                    except Exception as retry_e:
                        logger.error(f"❌ 재시도 실패 - {tool_name}: {retry_e}")
                        raise MCPToolExecutionError(f"Failed to execute tool '{tool_name}': {str(retry_e)}")
            
            logger.error(f"❌ Tool execution failed - {tool_name}: {e}")
            raise MCPToolExecutionError(f"Failed to execute tool '{tool_name}': {str(e)}")
    
    def _parse_tool_result(self, result: Any) -> Dict[str, Any]:
        """CallToolResult 객체를 dict로 변환"""
        import json
        
        # 이미 dict인 경우 그대로 반환
        if isinstance(result, dict):
            return result
        
        # CallToolResult 객체인 경우 content에서 텍스트 추출
        if hasattr(result, 'content') and result.content:
            for content_item in result.content:
                if hasattr(content_item, 'text'):
                    try:
                        # JSON 문자열인 경우 파싱
                        return json.loads(content_item.text)
                    except json.JSONDecodeError:
                        # JSON이 아닌 경우 텍스트 그대로 반환
                        return {
                            "success": True,
                            "text": content_item.text,
                            "markdown": content_item.text,
                        }
        
        # isError 속성 확인
        if hasattr(result, 'isError') and result.isError:
            error_msg = ""
            if hasattr(result, 'content') and result.content:
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        error_msg = content_item.text
                        break
            return {
                "success": False,
                "error": error_msg or "Unknown error"
            }
        
        # 알 수 없는 형식
        logger.warning(f"Unknown result type: {type(result)}")
        return {
            "success": False,
            "error": f"Unknown result type: {type(result).__name__}"
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on MCP connection"""
        return {
            "connected": self.is_connected,
            "server_url": settings.mcp_server_url,
            "tools_available": len(self._tools_cache),
            "tools": [tool["name"] for tool in self._tools_cache],
            "tool_usage_stats": self._tool_usage_stats.copy()
        }
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Get tool usage statistics"""
        return self._tool_usage_stats.copy()

# Global service instance
mcp_service = MCPService()
