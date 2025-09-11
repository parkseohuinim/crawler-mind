"""Main application entry point - DDD Architecture"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.core.logging import setup_logging
from app.infrastructure.mcp.mcp_service import mcp_service
from app.routers.api import router as api_router
from app.shared.database.base import init_database, close_database
from app.application.rag.rag_service import rag_service

# Setup logging
setup_logging()
logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("Starting MCP FastAPI Server with DDD Architecture...")
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")
        
        # Initialize MCP service
        await mcp_service.initialize()
        logger.info("MCP service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize core services: {e}")
    
    # Initialize RAG service separately (optional)
    try:
        logger.info("Starting RAG service initialization...")
        await rag_service.initialize_services()
        logger.info("✅ RAG service initialized successfully")
        
        # RAG 서비스 상태 확인
        data_info = await rag_service.get_data_info()
        if data_info.get("success"):
            qdrant_count = data_info["summary"]["qdrant_documents"]
            opensearch_count = data_info["summary"]["opensearch_documents"]
            logger.info(f"📊 Current RAG data: Qdrant={qdrant_count}, OpenSearch={opensearch_count}")
        
    except Exception as e:
        logger.warning(f"RAG service initialization failed (will continue without RAG): {e}")
        import traceback
        logger.debug(f"RAG init traceback: {traceback.format_exc()}")
    
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
    title=f"{settings.app_title} - DDD",
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

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    return {"status": "healthy", "service": "mcp-client"}

# Include routers
app.include_router(api_router, prefix="/api")

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
