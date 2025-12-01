"""MCP Client Service - Handles all MCP server interactions"""
from typing import List, Dict, Any, Optional
import asyncio
import logging
from fastmcp import Client
from app.config import settings
from app.shared.exceptions.base import MCPConnectionError, MCPToolExecutionError

logger = logging.getLogger(__name__)

class MCPService:
    """Service class for managing MCP client operations"""
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._tools_cache: List[Dict[str, Any]] = []
        self._connection_lock = asyncio.Lock()
        self._tool_usage_stats: Dict[str, int] = {}  # 도구 사용 통계
        self._max_retries: int = 3  # 최대 재시도 횟수
        self._retry_delay: float = 2.0  # 재시도 대기 시간 (초)
        
    async def initialize(self) -> None:
        """Initialize MCP client connection with retry logic"""
        async with self._connection_lock:
            if self._client is not None:
                return
            
            last_error = None
            for attempt in range(self._max_retries):
                try:
                    logger.info(f"🔄 Attempting to connect to MCP Server (attempt {attempt + 1}/{self._max_retries})...")
                    
                    self._client = Client(settings.mcp_server_url)
                    await self._client.__aenter__()
                    
                    # Cache available tools
                    await self._refresh_tools_cache()
                    
                    logger.info(f"✅ MCP Client connected to {settings.mcp_server_url}")
                    logger.info(f"📋 Available tools: {[tool['name'] for tool in self._tools_cache]}")
                    return
                    
                except Exception as e:
                    last_error = e
                    logger.warning(f"⚠️ Connection attempt {attempt + 1} failed: {e}")
                    self._client = None
                    
                    if attempt < self._max_retries - 1:
                        wait_time = self._retry_delay * (attempt + 1)  # Exponential backoff
                        logger.info(f"⏳ Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
            
            # All retries failed
            logger.error(f"❌ Failed to initialize MCP client after {self._max_retries} attempts")
            raise MCPConnectionError(f"MCP client initialization failed after {self._max_retries} attempts: {str(last_error)}")
    
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
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on the MCP server with automatic reconnection"""
        if not self.is_connected:
            logger.warning("⚠️ MCP client not connected, attempting to reconnect...")
            try:
                await self.initialize()
            except MCPConnectionError:
                raise MCPConnectionError("MCP client not connected and reconnection failed")
        
        try:
            logger.info(f"🚀 Calling MCP tool: {tool_name} with args: {arguments}")
            result = await self._client.call_tool(tool_name, arguments)
            
            # 사용 통계 업데이트
            self._tool_usage_stats[tool_name] = self._tool_usage_stats.get(tool_name, 0) + 1
            
            logger.info(f"✅ Tool '{tool_name}' executed successfully. Result: {result}")
            logger.info(f"📊 Tool usage count for '{tool_name}': {self._tool_usage_stats[tool_name]}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Tool execution failed - {tool_name}: {e}")
            
            # 연결이 끊어진 경우 재연결 시도
            if "connection" in str(e).lower() or "disconnect" in str(e).lower():
                logger.warning("🔄 Connection lost, attempting to reconnect and retry...")
                self._client = None
                
                try:
                    await self.initialize()
                    # 재연결 후 한 번 더 시도
                    result = await self._client.call_tool(tool_name, arguments)
                    self._tool_usage_stats[tool_name] = self._tool_usage_stats.get(tool_name, 0) + 1
                    logger.info(f"✅ Tool '{tool_name}' executed successfully after reconnection")
                    return result
                except Exception as retry_error:
                    logger.error(f"❌ Retry after reconnection failed: {retry_error}")
                    raise MCPToolExecutionError(f"Failed to execute tool '{tool_name}' even after reconnection: {str(retry_error)}")
            
            raise MCPToolExecutionError(f"Failed to execute tool '{tool_name}': {str(e)}")
    
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
