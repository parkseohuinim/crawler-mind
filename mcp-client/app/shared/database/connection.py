"""Raw database connection for direct queries"""
import asyncpg
from typing import AsyncContextManager
from app.config import settings
import logging

logger = logging.getLogger(__name__)

def get_db_connection() -> AsyncContextManager[asyncpg.Connection]:
    """Get raw database connection for direct SQL queries"""
    # asyncpg URL 형식으로 변환 (SQLAlchemy URL에서)
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
    
    class ConnectionManager:
        def __init__(self, connection_url: str):
            self.connection_url = connection_url
            self.connection = None
        
        async def __aenter__(self) -> asyncpg.Connection:
            self.connection = await asyncpg.connect(self.connection_url)
            return self.connection
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.connection:
                await self.connection.close()
    
    return ConnectionManager(url)
