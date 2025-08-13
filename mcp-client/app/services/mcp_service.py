"""MCP Client Service - Handles all MCP server interactions"""
from typing import List, Dict, Any, Optional
import asyncio
import logging
from fastmcp import Client
from app.config import settings
from app.utils.exceptions import MCPConnectionError, MCPToolExecutionError

logger = logging.getLogger(__name__)

class MCPService:
    """Service class for managing MCP client operations"""
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._tools_cache: List[Dict[str, Any]] = []
        self._connection_lock = asyncio.Lock()
        self._tool_usage_stats: Dict[str, int] = {}  # 도구 사용 통계
        
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
            from app.utils.schema_converter import to_openai_schema
            
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
        """Execute a tool on the MCP server"""
        if not self.is_connected:
            raise MCPConnectionError("MCP client not connected")
        
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