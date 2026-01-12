"""Configuration management for MCP Client"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "info"
    
    # MCP Server Configuration
    mcp_server_url: str = "http://127.0.0.1:4200/my-custom-path/"
    mcp_connection_timeout: int = 30
    mcp_retry_attempts: int = 3
    
    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_allow_credentials: bool = True
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    openai_timeout: int = 60
    
    # Database Configuration
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/crawler_mind"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # If database_url is empty string from env, use default
        if self.database_url == "":
            self.database_url = "postgresql+asyncpg://user:password@localhost:5432/crawler_mind"
        
        # Validate database_url is not empty after processing
        if not self.database_url or not self.database_url.strip():
            raise ValueError(
                "DATABASE_URL이 유효하지 않습니다. "
                ".env 파일에 올바른 DATABASE_URL을 설정해주세요. "
                "예: postgresql+asyncpg://user:password@localhost:5432/crawler_mind"
            )
    
    # Vector Database Configuration (Qdrant)
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333
    
    # Search Engine Configuration (OpenSearch)
    opensearch_host: str = "127.0.0.1"
    opensearch_port: int = 9200
    
    # Feature Flags
    allow_daily_crawling: bool = True
    
    # Application Configuration
    app_title: str = "MCP FastAPI Server"
    app_version: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()