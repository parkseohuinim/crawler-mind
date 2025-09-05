"""RAG API router"""
import json
import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.domains.rag.schemas.rag_schemas import (
    RagUploadResponse, RagQueryRequest, RagQueryResponse
)
from app.application.rag.rag_service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/upload", response_model=RagUploadResponse)
async def upload_rag_data(file: UploadFile = File(...)):
    """
    Upload JSON file containing documents for RAG system
    
    Expected JSON format:
    [
        {
            "docId": "unique_id",
            "title": "Document Title",
            "text": "Document content...",
            "url": "https://example.com",
            "murl": "https://m.example.com",
            "hierarchy": ["Category", "Subcategory"],
            "metadata": {...}
        },
        ...
    ]
    """
    logger.info(f"🚀 RAG upload request received: {file.filename} ({file.size} bytes)")
    logger.info(f"📋 Request details: filename={file.filename}, content_type={file.content_type}")
    try:
        # Validate file type
        if not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=400, 
                detail="Only JSON files are allowed"
            )
        
        # Read and parse JSON file
        logger.info(f"📖 Reading file contents...")
        contents = await file.read()
        logger.info(f"📄 File read successfully: {len(contents)} bytes")
        
        try:
            # Handle UTF-8 BOM by trying utf-8-sig first, then fallback to utf-8
            try:
                text_content = contents.decode('utf-8-sig')
            except UnicodeDecodeError:
                text_content = contents.decode('utf-8')
            
            logger.info(f"🔍 Parsing JSON data...")
            json_data = json.loads(text_content)
            logger.info(f"✅ JSON parsed successfully: {len(json_data)} documents")
            
            # 문서 수 검증을 위한 상세 정보
            if len(json_data) > 0:
                sample_doc = json_data[0]
                logger.info(f"📋 Sample document structure: {list(sample_doc.keys())}")
                logger.info(f"📊 Total documents in JSON file: {len(json_data)}")
                
                # 문서 크기 분포 확인
                doc_sizes = [len(str(doc.get('text', ''))) for doc in json_data]
                if doc_sizes:
                    avg_size = sum(doc_sizes) / len(doc_sizes)
                    max_size = max(doc_sizes)
                    min_size = min(doc_sizes)
                    logger.info(f"📏 Document size stats: avg={avg_size:.0f}, max={max_size}, min={min_size}")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"❌ JSON parsing failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid JSON format: {str(e)}"
            )
        
        # Validate that it's a list
        if not isinstance(json_data, list):
            raise HTTPException(
                status_code=400, 
                detail="JSON file must contain an array of documents"
            )
        
        logger.info(f"🔄 Processing upload of {len(json_data)} documents from {file.filename}")
        
        # Process documents
        logger.info(f"🚀 Starting RAG service processing...")
        result = await rag_service.upload_documents_from_json(json_data)
        logger.info(f"✅ RAG service processing completed: {result}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file upload: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to process file: {str(e)}"
        )


@router.post("/query", response_model=RagQueryResponse)
async def query_rag_documents(request: RagQueryRequest):
    """
    Query documents using RAG (Retrieval-Augmented Generation)
    
    This endpoint:
    1. Searches for relevant documents using vector similarity (Qdrant)
    2. Performs text search using OpenSearch
    3. Combines results and generates an answer using LLM
    """
    try:
        if not request.query.strip():
            raise HTTPException(
                status_code=400,
                detail="Query cannot be empty"
            )
        
        logger.info(f"Processing RAG query: {request.query[:100]}...")
        
        result = await rag_service.query_documents(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing RAG query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


@router.delete("/data")
async def delete_all_rag_data():
    """
    Delete all RAG data from both Qdrant and OpenSearch
    
    This will:
    1. Delete all documents from Qdrant collection
    2. Delete all documents from OpenSearch index
    3. Recreate empty collection/index structures
    """
    try:
        logger.info("Starting deletion of all RAG data")
        
        result = await rag_service.delete_all_data()
        
        if result.get("success", False):
            return JSONResponse(
                status_code=200,
                content={
                    "message": result["message"],
                    "processing_time": result["processing_time"],
                    "details": result["details"]
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": result["message"],
                    "details": result.get("details", {})
                }
            )
            
    except Exception as e:
        logger.error(f"Error deleting RAG data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete RAG data: {str(e)}"
        )


@router.get("/data/info")
async def get_rag_data_info():
    """
    Get information about stored RAG data
    
    Returns:
    - Number of documents in Qdrant
    - Number of documents in OpenSearch
    - Collection/index status
    """
    try:
        result = await rag_service.get_data_info()
        
        if result.get("success", False):
            return result
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to get data info")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RAG data info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get data info: {str(e)}"
        )


@router.get("/search-test/{query}")
async def search_test(query: str):
    """특정 쿼리로 검색 테스트"""
    try:
        qdrant_service, opensearch_service = rag_service._get_services()
        
        # Qdrant 검색
        vector_results = await qdrant_service.search_similar_documents(
            query=query,
            limit=10,
            score_threshold=0.0
        )
        
        # OpenSearch 검색
        text_results = await opensearch_service.search_documents(
            query=query,
            limit=10
        )
        
        # 홈코노미 관련 문서 찾기
        homeco_results = []
        for result in vector_results + text_results:
            if 'payload' in result:
                content = result['payload'].get('content', '')
                title = result['payload'].get('title', '')
            elif 'source' in result:
                content = result['source'].get('content', '')
                title = result['source'].get('title', '')
            else:
                continue
                
            if '홈코노미' in title or '홈코노미' in content:
                homeco_results.append({
                    'id': result.get('id'),
                    'title': title,
                    'content_preview': content[:200] + '...' if len(content) > 200 else content
                })
        
        return {
            "query": query,
            "vector_results_count": len(vector_results),
            "text_results_count": len(text_results),
            "homeco_results": homeco_results,
            "all_results": [
                {
                    'id': r.get('id'),
                    'title': r.get('payload', {}).get('title') or r.get('source', {}).get('title'),
                    'score': r.get('score', 0)
                } for r in (vector_results + text_results)[:5]
            ]
        }
        
    except Exception as e:
        logger.error(f"Search test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_documents(
    query: str,
    limit: int = 20,
    include_content: bool = True
):
    """문서 검색 API - 프론트엔드용"""
    try:
        qdrant_service, opensearch_service = rag_service._get_services()
        
        # Qdrant 검색 (벡터 유사도)
        vector_results = await qdrant_service.search_similar_documents(
            query=query,
            limit=limit,
            score_threshold=0.0
        )
        
        # OpenSearch 검색 (텍스트 검색)
        text_results = await opensearch_service.search_documents(
            query=query,
            limit=limit
        )
        
        # 결과 통합 및 정규화
        all_results = []
        seen_ids = set()
        
        # 점수 정규화를 위한 최대값 계산
        vector_scores = [r['score'] for r in vector_results]
        text_scores = [r['score'] for r in text_results]
        vector_max = max(vector_scores) if vector_scores else 1.0
        text_max = max(text_scores) if text_scores else 1.0
        
        # Qdrant 결과 처리
        for result in vector_results:
            if result['id'] in seen_ids:
                continue
            seen_ids.add(result['id'])
            
            payload = result['payload']
            raw_score = result['score']
            # 코사인 거리를 유사도로 변환 후 정규화
            similarity = max(0.0, 1.0 - raw_score)
            normalized_score = max(0.0, min(1.0, similarity / vector_max if vector_max > 0 else similarity))
            
            all_results.append({
                'id': result['id'],
                'title': payload.get('title', ''),
                'url': payload.get('url', ''),
                'hierarchy': payload.get('hierarchy', []),
                'content': payload.get('content', '') if include_content else '',
                'content_preview': payload.get('content', '')[:200] + '...' if len(payload.get('content', '')) > 200 else payload.get('content', ''),
                'similarity_score': normalized_score,
                'search_type': 'vector',
                'metadata': payload.get('metadata', {})
            })
        
        # OpenSearch 결과 처리
        for result in text_results:
            if result['id'] in seen_ids:
                continue
            seen_ids.add(result['id'])
            
            source = result['source']
            raw_score = result['score']
            # 텍스트 검색 점수 정규화
            normalized_score = max(0.0, min(1.0, raw_score / text_max if text_max > 0 else raw_score))
            
            all_results.append({
                'id': result['id'],
                'title': source.get('title', ''),
                'url': source.get('url', ''),
                'hierarchy': source.get('hierarchy', []),
                'content': source.get('content', '') if include_content else '',
                'content_preview': source.get('content', '')[:200] + '...' if len(source.get('content', '')) > 200 else source.get('content', ''),
                'similarity_score': normalized_score,
                'search_type': 'text',
                'metadata': source.get('metadata', {})
            })
        
        # 유사도 점수 기준으로 정렬
        all_results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return {
            "query": query,
            "total_results": len(all_results),
            "vector_results_count": len(vector_results),
            "text_results_count": len(text_results),
            "results": all_results[:limit]
        }
        
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint for RAG services"""
    try:
        # Test actual connections
        qdrant_status = "disconnected"
        opensearch_status = "disconnected"
        
        try:
            # Test Qdrant connection (using HTTP client)
            qdrant_service, opensearch_service = rag_service._get_services()
            response = await qdrant_service.client.get(f"{qdrant_service.base_url}/collections")
            response.raise_for_status()
            qdrant_status = "connected"
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
        
        try:
            # Test OpenSearch connection
            health = opensearch_service.client.cluster.health()
            opensearch_status = "connected"
        except Exception as e:
            logger.warning(f"OpenSearch health check failed: {e}")
        
        overall_status = "healthy" if qdrant_status == "connected" and opensearch_status == "connected" else "degraded"
        
        return {
            "status": overall_status,
            "services": {
                "qdrant": qdrant_status,
                "opensearch": opensearch_status,
                "llm": "available"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="RAG services are not healthy"
        )
