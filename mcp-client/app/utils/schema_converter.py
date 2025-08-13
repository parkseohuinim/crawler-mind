"""Schema conversion utilities for MCP tools to OpenAI format"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

def to_openai_schema(mcp_tool) -> Dict[str, Any]:
    """
    Convert MCP tool schema to OpenAI Function Calling format
    
    Args:
        mcp_tool: MCP tool object with schema information
        
    Returns:
        Dict containing OpenAI-compatible function schema
    """
    try:
        # Extract schema from various possible attributes
        raw_schema = (
            getattr(mcp_tool, "inputSchema", None)
            or getattr(mcp_tool, "input_schema", None)
            or getattr(mcp_tool, "parameters", None)
        )

        schema = _process_raw_schema(raw_schema)
        
        # Ensure required fields exist
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        
        # Set required fields if not specified
        if "required" not in schema:
            schema["required"] = list(schema["properties"].keys())

        return {
            "type": "function",
            "name": mcp_tool.name,
            "description": getattr(mcp_tool, "description", ""),
            "parameters": schema,
        }
        
    except Exception as e:
        logger.error(f"Failed to convert schema for tool {getattr(mcp_tool, 'name', 'unknown')}: {e}")
        # Return a safe default schema
        return {
            "type": "function",
            "name": getattr(mcp_tool, "name", "unknown"),
            "description": getattr(mcp_tool, "description", ""),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": True
            },
        }

def _process_raw_schema(raw_schema) -> Dict[str, Any]:
    """
    Process raw schema from MCP tool into standardized format
    
    Args:
        raw_schema: Raw schema data from MCP tool
        
    Returns:
        Processed schema dictionary
    """
    if raw_schema is None:
        return {"type": "object", "properties": {}, "additionalProperties": True}
    
    if isinstance(raw_schema, dict):
        return raw_schema
    
    if hasattr(raw_schema, "model_json_schema"):
        return raw_schema.model_json_schema()
    
    if isinstance(raw_schema, list):
        return _process_list_schema(raw_schema)
    
    # Fallback for unknown schema types
    logger.warning(f"Unknown schema type: {type(raw_schema)}")
    return {"type": "object", "properties": {}, "additionalProperties": True}

def _process_list_schema(schema_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process list-based schema definition
    
    Args:
        schema_list: List of parameter definitions
        
    Returns:
        OpenAI-compatible schema dictionary
    """
    properties = {}
    required = []
    
    for param in schema_list:
        if not isinstance(param, dict) or "name" not in param:
            continue
            
        param_name = param["name"]
        properties[param_name] = {
            "type": param.get("type", "string"),
            "description": param.get("description", ""),
        }
        
        if param.get("required", True):
            required.append(param_name)
    
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
        
    return schema

def validate_openai_schema(schema: Dict[str, Any]) -> bool:
    """
    Validate that a schema conforms to OpenAI function calling format
    
    Args:
        schema: Schema dictionary to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ["type", "name", "parameters"]
    
    for field in required_fields:
        if field not in schema:
            logger.error(f"Missing required field in schema: {field}")
            return False
    
    if schema["type"] != "function":
        logger.error(f"Invalid schema type: {schema['type']}")
        return False
    
    parameters = schema.get("parameters", {})
    if not isinstance(parameters, dict):
        logger.error("Parameters must be a dictionary")
        return False
    
    if parameters.get("type") != "object":
        logger.error("Parameters type must be 'object'")
        return False
    
    return True