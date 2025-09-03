"""Custom exceptions for MCP Client application"""

class MCPClientException(Exception):
    """Base exception for MCP Client errors"""
    pass

class MCPConnectionError(MCPClientException):
    """Raised when MCP connection fails"""
    pass

class MCPToolExecutionError(MCPClientException):
    """Raised when MCP tool execution fails"""
    pass

class LLMQueryError(MCPClientException):
    """Raised when LLM query fails"""
    pass

class SchemaConversionError(MCPClientException):
    """Raised when schema conversion fails"""
    pass

class DatabaseError(MCPClientException):
    """Raised when database operation fails"""
    pass