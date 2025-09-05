"""OpenSearch text search service"""
import logging
from typing import List, Dict, Any, Optional
from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError, RequestError
import asyncio

from app.domains.rag.entities.document import Document
from app.config import settings

logger = logging.getLogger(__name__)


class OpenSearchService:
    """Service for interacting with OpenSearch for text search"""
    
    def __init__(self):
        self.client = OpenSearch(
            hosts=[settings.opensearch_host],  # "https://opensearch.alvinpark.xyz"
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        self.index_name = "documents"
        
    async def initialize_index(self):
        """Initialize OpenSearch index if it doesn't exist"""
        try:
            if not self.client.indices.exists(index=self.index_name):
                index_body = {
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "analysis": {
                            "analyzer": {
                                "korean_analyzer": {
                                    "type": "custom",
                                    "tokenizer": "nori_tokenizer",
                                    "filter": ["lowercase", "nori_part_of_speech"]
                                }
                            }
                        }
                    },
                    "mappings": {
                        "properties": {
                            "title": {
                                "type": "text",
                                "analyzer": "korean_analyzer",
                                "search_analyzer": "korean_analyzer"
                            },
                            "content": {
                                "type": "text",
                                "analyzer": "korean_analyzer",
                                "search_analyzer": "korean_analyzer"
                            },
                            "url": {"type": "keyword"},
                            "mobile_url": {"type": "keyword"},
                            "hierarchy": {"type": "keyword"},
                            "metadata": {"type": "object"},
                            "created_at": {"type": "date"},
                            "updated_at": {"type": "date"}
                        }
                    }
                }
                
                self.client.indices.create(index=self.index_name, body=index_body)
                logger.info(f"Created index: {self.index_name}")
            else:
                logger.info(f"Index {self.index_name} already exists")
                
        except Exception as e:
            logger.error(f"Failed to initialize index: {e}")
            raise
    
    async def store_document(self, document: Document) -> bool:
        """Store a single document in OpenSearch"""
        try:
            doc_body = {
                "title": document.title,
                "content": document.content,
                "url": document.url,
                "mobile_url": document.mobile_url,
                "hierarchy": document.hierarchy,
                "metadata": document.metadata,
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "updated_at": document.updated_at.isoformat() if document.updated_at else None,
            }
            
            response = self.client.index(
                index=self.index_name,
                id=document.id,
                body=doc_body
            )
            
            logger.info(f"Stored document in OpenSearch: {document.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store document {document.id} in OpenSearch: {e}")
            return False
    
    async def store_documents(self, documents: List[Document]) -> Dict[str, int]:
        """Store multiple documents in OpenSearch with bulk operations"""
        total_docs = len(documents)
        logger.info(f"Starting to store {total_docs} documents in OpenSearch with bulk operations")
        
        success_count = 0
        failed_count = 0
        failed_documents = []
        
        # OpenSearch는 동기 라이브러리이므로 bulk insert 사용
        try:
            # bulk insert를 위한 데이터 준비
            bulk_data = []
            for document in documents:
                # 인덱스 작업 정의
                bulk_data.append({
                    "index": {
                        "_index": self.index_name,
                        "_id": document.id
                    }
                })
                # 문서 데이터
                bulk_data.append({
                    "title": document.title,
                    "content": document.content,
                    "url": document.url,
                    "mobile_url": document.mobile_url,
                    "hierarchy": document.hierarchy,
                    "metadata": document.metadata,
                    "created_at": document.created_at.isoformat() if document.created_at else None,
                    "updated_at": document.updated_at.isoformat() if document.updated_at else None,
                })
            
            # bulk insert 실행 (배치 크기를 100개로 제한)
            batch_size = 100
            for i in range(0, len(bulk_data), batch_size * 2):  # *2 because each doc has 2 entries
                batch = bulk_data[i:i + batch_size * 2]
                
                # 동기 작업을 비동기로 래핑
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: self.client.bulk(body=batch, refresh=False)  # refresh 비활성화
                )
                
                # 결과 처리
                if response.get('errors'):
                    for item in response['items']:
                        if 'index' in item and item['index'].get('status', 200) >= 400:
                            failed_count += 1
                            doc_id = item['index'].get('_id', 'unknown')
                            failed_documents.append(doc_id)
                            logger.error(f"Failed to index document {doc_id}: {item['index'].get('error', 'Unknown error')}")
                        else:
                            success_count += 1
                else:
                    # 모든 문서가 성공한 경우
                    batch_doc_count = len(batch) // 2
                    success_count += batch_doc_count
                
                # 진행 상황 로깅
                processed_docs = min((i // 2) + (len(batch) // 2), total_docs)
                logger.info(f"OpenSearch progress: {processed_docs}/{total_docs} documents processed ({success_count} success, {failed_count} failed)")
                
                # 배치 간 잠시 대기
                if i + batch_size * 2 < len(bulk_data):
                    await asyncio.sleep(0.05)
            
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")
            # 실패한 경우 개별 처리로 폴백
            return await self._store_documents_individually(documents)
        
        finally:
            # 모든 배치 처리 완료 후 한 번만 refresh
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, 
                    lambda: self.client.indices.refresh(index=self.index_name)
                )
                logger.info("OpenSearch index refreshed")
            except Exception as e:
                logger.warning(f"Failed to refresh OpenSearch index: {e}")
        
        logger.info(f"OpenSearch storage completed: {success_count} success, {failed_count} failed out of {total_docs}")
        
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_documents": failed_documents
        }
    
    async def _store_documents_individually(self, documents: List[Document]) -> Dict[str, int]:
        """Fallback method to store documents individually"""
        success_count = 0
        failed_count = 0
        failed_documents = []
        total_docs = len(documents)
        
        logger.info(f"Falling back to individual document storage for {total_docs} documents")
        
        for i, document in enumerate(documents, 1):
            try:
                success = await self.store_document(document)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    failed_documents.append(document.id)
                
                # 진행 상황 로깅 (매 10개마다)
                if i % 10 == 0 or i == total_docs:
                    logger.info(f"OpenSearch individual progress: {i}/{total_docs} documents processed ({success_count} success, {failed_count} failed)")
                    
            except Exception as e:
                logger.error(f"Failed to process document {document.id}: {e}")
                failed_count += 1
                failed_documents.append(document.id)
        
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_documents": failed_documents
        }
    
    async def search_documents(
        self, 
        query: str, 
        limit: int = 10,
        min_score: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Search documents using text search"""
        try:
            search_body = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "title": {
                                        "query": query,
                                        "boost": 2.0
                                    }
                                }
                            },
                            {
                                "match": {
                                    "content": {
                                        "query": query,
                                        "boost": 1.0
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": limit,
                "min_score": min_score,
                "_source": ["title", "content", "url", "mobile_url", "hierarchy", "metadata"]
            }
            
            response = self.client.search(
                index=self.index_name,
                body=search_body
            )
            
            results = []
            for hit in response['hits']['hits']:
                result = {
                    "id": hit['_id'],
                    "score": hit['_score'],
                    "source": hit['_source']
                }
                results.append(result)
            
            logger.info(f"Found {len(results)} documents for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []
    
    async def delete_all_documents(self) -> Dict[str, Any]:
        """Delete all documents from the index"""
        try:
            # Delete all documents using delete by query
            delete_body = {
                "query": {
                    "match_all": {}
                }
            }
            
            response = self.client.delete_by_query(
                index=self.index_name,
                body=delete_body,
                wait_for_completion=True,
                refresh=True
            )
            
            deleted_count = response.get('deleted', 0)
            logger.info(f"Successfully deleted {deleted_count} documents from OpenSearch")
            
            return {
                "success": True,
                "message": f"All documents deleted from OpenSearch ({deleted_count} documents)"
            }
            
        except NotFoundError:
            logger.info("Index does not exist, nothing to delete")
            return {
                "success": True,
                "message": "Index does not exist, nothing to delete"
            }
        except Exception as e:
            logger.error(f"Failed to delete all documents from OpenSearch: {e}")
            return {
                "success": False,
                "message": f"Failed to delete documents: {str(e)}"
            }
    
    async def get_index_info(self) -> Dict[str, Any]:
        """Get information about the index"""
        try:
            if not self.client.indices.exists(index=self.index_name):
                return {
                    "success": True,
                    "index_name": self.index_name,
                    "exists": False,
                    "document_count": 0
                }
            
            # Get index stats
            stats = self.client.indices.stats(index=self.index_name)
            doc_count = stats['indices'][self.index_name]['total']['docs']['count']
            
            return {
                "success": True,
                "index_name": self.index_name,
                "exists": True,
                "document_count": doc_count
            }
            
        except Exception as e:
            logger.error(f"Failed to get index info: {e}")
            return {
                "success": False,
                "message": f"Failed to get index info: {str(e)}"
            }


# Global instance - will be initialized lazily  
opensearch_service = None

def get_opensearch_service() -> OpenSearchService:
    """Get or create OpenSearch service instance"""
    global opensearch_service
    if opensearch_service is None:
        opensearch_service = OpenSearchService()
    return opensearch_service
