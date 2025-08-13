"""Main application entry point"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.core.logging import setup_logging
from app.services.mcp_service import mcp_service
from app.routers.api import router

# Setup logging
setup_logging()
logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("Starting MCP FastAPI Server...")
    try:
        await mcp_service.initialize()
        logger.info("MCP service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MCP service: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP FastAPI Server...")
    try:
        await mcp_service.shutdown()
        logger.info("MCP service shutdown completed")
    except Exception as e:
        logger.error(f"Error during MCP service shutdown: {e}")

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