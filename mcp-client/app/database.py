"""Database configuration and connection management"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, BigInteger, Text, String, DateTime, func
from typing import AsyncGenerator
from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL debugging
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Create async session factory
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
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_database():
    """Initialize database tables"""
    # Import all models to ensure they're registered with Base
    from app.menu_links.database import MenuLink, MenuManagerInfo
    
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)

async def close_database():
    """Close database connections"""
    await engine.dispose()
