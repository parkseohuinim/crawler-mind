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

# Domain-specific exceptions
class DomainException(MCPClientException):
    """Base exception for domain errors"""
    pass

class EntityNotFoundError(DomainException):
    """Raised when entity is not found"""
    pass

class BusinessRuleViolationError(DomainException):
    """Raised when business rule is violated"""
    pass

class MenuLinkNotFoundError(EntityNotFoundError):
    """Raised when menu link is not found"""
    pass

class MenuManagerInfoNotFoundError(EntityNotFoundError):
    """Raised when menu manager info is not found"""
    pass

class DuplicateMenuManagerError(BusinessRuleViolationError):
    """Raised when trying to create duplicate menu manager info"""
    pass
