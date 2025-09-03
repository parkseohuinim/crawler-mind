"""Main application entry point"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.core.logging import setup_logging
from app.services.mcp_service import mcp_service
from app.routers.api import router
from app.menu_links.router import router as menu_links_router
from app.database import init_database, close_database

# Setup logging
setup_logging()
logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("Starting MCP FastAPI Server...")
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")
        
        # Initialize MCP service
        await mcp_service.initialize()
        logger.info("MCP service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP FastAPI Server...")
    try:
        await mcp_service.shutdown()
        logger.info("MCP service shutdown completed")
        
        await close_database()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during service shutdown: {e}")

# Create FastAPI app
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)
app.include_router(menu_links_router)

# Development server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )