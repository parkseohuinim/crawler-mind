"""Database configuration and connection management"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from app.config import settings

# Global variables for lazy initialization
engine = None
AsyncSessionLocal = None

def _initialize_database_engine():
    """Initialize database engine and session factory"""
    global engine, AsyncSessionLocal
    if engine is None:
        engine = create_async_engine(
            settings.database_url,
            echo=False,  # Set to True for SQL debugging
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

class Base(DeclarativeBase):
    """Base class for all database models"""
    pass

async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    _initialize_database_engine()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_database():
    """Initialize database tables"""
    _initialize_database_engine()
    
    # Import all models to ensure they're registered with Base
    from app.domains.menu.entities.menu_link import MenuLink
    from app.domains.menu.entities.menu_manager import MenuManagerInfo
    
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)

async def close_database():
    """Close database connections"""
    if engine is not None:
        await engine.dispose()
