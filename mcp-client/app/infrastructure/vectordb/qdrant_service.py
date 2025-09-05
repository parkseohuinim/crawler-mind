"""Qdrant vector database service"""
import logging
from typing import List, Dict, Any, Optional
import httpx
import openai
from openai import OpenAI
import tiktoken
import uuid
import asyncio
import time
import gc
from concurrent.futures import ThreadPoolExecutor
from aiolimiter import AsyncLimiter

from app.domains.rag.entities.document import Document
from app.config import settings

logger = logging.getLogger(__name__)


class ProgressTracker:
    """진행 상황 추적 및 ETA 계산"""
    
    def __init__(self, total_items: int, name: str = "Processing"):
        self.total = total_items
        self.processed = 0
        self.start_time = time.time()
        self.name = name
        self.last_log_time = self.start_time
        
    def update(self, count: int = 1):
        self.processed += count
        current_time = time.time()
        
        # 2초마다 또는 완료시에만 로그 (더 자주 표시)
        if current_time - self.last_log_time >= 2.0 or self.processed >= self.total:
            elapsed = current_time - self.start_time
            rate = self.processed / elapsed if elapsed > 0 else 0
            eta = (self.total - self.processed) / rate if rate > 0 else 0
            progress_percent = (self.processed / self.total * 100) if self.total > 0 else 0
            
            logger.info(f"{self.name}: {self.processed}/{self.total} ({progress_percent:.1f}%) "
                       f"Rate: {rate:.1f}/sec ETA: {eta:.0f}s")
            self.last_log_time = current_time
    
    def force_log(self):
        """강제로 현재 진행 상황 로그 출력"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        rate = self.processed / elapsed if elapsed > 0 else 0
        eta = (self.total - self.processed) / rate if rate > 0 else 0
        progress_percent = (self.processed / self.total * 100) if self.total > 0 else 0
        
        logger.info(f"{self.name} (FORCE): {self.processed}/{self.total} ({progress_percent:.1f}%) "
                   f"Rate: {rate:.1f}/sec ETA: {eta:.0f}s")
        self.last_log_time = current_time


class QdrantService:
    """Service for interacting with Qdrant vector database"""
    
    def __init__(self):
        self.base_url = settings.qdrant_host.rstrip('/')  # "https://qdrant.alvinpark.xyz"
        self.client = httpx.AsyncClient(verify=False, timeout=60.0)  # 타임아웃 증가
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.collection_name = "documents"
        self.vector_size = 1536  # OpenAI text-embedding-ada-002 dimension
        
        # Initialize tokenizer for text-embedding-ada-002
        try:
            self.tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")
        except Exception:
            # Fallback to cl100k_base encoding
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # 청킹을 위한 설정 - 더 작은 청크로 설정하여 토큰 제한 문제 해결
        self.chunk_size = 2000  # 토큰 단위 (8192의 1/4 정도로 안전하게 설정)
        self.chunk_overlap = 100  # 청크 간 겹치는 토큰 수
        
        # Rate limiter for OpenAI API (초당 10개 요청으로 제한)
        self.embedding_limiter = AsyncLimiter(max_rate=10, time_period=1)
        
    async def initialize_collection(self):
        """Initialize Qdrant collection if it doesn't exist"""
        try:
            # Get collections
            response = await self.client.get(f"{self.base_url}/collections")
            response.raise_for_status()
            collections_data = response.json()
            
            collection_names = [col["name"] for col in collections_data.get("result", {}).get("collections", [])]
            
            if self.collection_name not in collection_names:
                # Create collection with proper Qdrant API format
                create_payload = {
                    "vectors": {
                        "size": self.vector_size,
                        "distance": "Cosine"
                    }
                }
                response = await self.client.put(
                    f"{self.base_url}/collections/{self.collection_name}",
                    json=create_payload
                )
                response.raise_for_status()
                logger.info(f"Created collection: {self.collection_name}")
                
                # Verify collection was created
                response = await self.client.get(f"{self.base_url}/collections")
                response.raise_for_status()
                collections_data = response.json()
                logger.info(f"Collections after creation: {collections_data}")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                
        except Exception as e:
            logger.error(f"Failed to initialize collection: {e}")
            raise
    
    def _count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 계산"""
        return len(self.tokenizer.encode(text))
    
    def _smart_chunk_text(self, text: str) -> List[str]:
        """의미 단위 기반 스마트 청킹 - 토큰 제한 안전장치 포함"""
        # 문단 단위로 먼저 분리
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if not paragraphs:
            return [text] if text.strip() else []
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            # 현재 청크에 문단을 추가했을 때의 토큰 수
            test_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
            test_tokens = self._count_tokens(test_chunk)
            
            # 토큰 제한 안전장치: 8192 토큰을 초과하면 강제로 분할
            if test_tokens > 8000:  # 8192보다 작은 안전 마진
                # 현재 청크가 있으면 저장
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 문단이 너무 크면 문장 단위로 분할
                if self._count_tokens(para) > 8000:
                    sentence_chunks = self._split_by_sentences(para)
                    chunks.extend(sentence_chunks)
                    current_chunk = ""
                else:
                    current_chunk = para
            elif test_tokens > self.chunk_size:
                # 현재 청크가 있으면 저장
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 문단이 너무 크면 문장 단위로 분할
                if self._count_tokens(para) > self.chunk_size:
                    sentence_chunks = self._split_by_sentences(para)
                    chunks.extend(sentence_chunks)
                    current_chunk = ""
                else:
                    current_chunk = para
            else:
                current_chunk = test_chunk
        
        # 마지막 청크 추가
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # 빈 청크 제거 및 최종 토큰 수 검증
        final_chunks = []
        for chunk in chunks:
            if chunk.strip():
                # 각 청크의 토큰 수를 다시 확인하고 필요시 추가 분할
                chunk_tokens = self._count_tokens(chunk)
                if chunk_tokens > 8000:
                    # 강제로 더 작은 청크로 분할
                    sub_chunks = self._force_split_large_chunk(chunk)
                    final_chunks.extend(sub_chunks)
                else:
                    final_chunks.append(chunk)
        
        original_tokens = self._count_tokens(text)
        logger.info(f"Smart chunking: {len(final_chunks)} chunks from {original_tokens} tokens")
        return final_chunks
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """문장 단위로 텍스트 분할 (긴 문단용)"""
        # 간단한 문장 분리 (더 정교한 방법으로 교체 가능)
        sentences = []
        for sent in text.split('.'):
            sent = sent.strip()
            if sent:
                sentences.append(sent + '.')
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            test_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence
            
            if self._count_tokens(test_chunk) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk = test_chunk
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    def _force_split_large_chunk(self, text: str) -> List[str]:
        """큰 청크를 강제로 작은 청크로 분할"""
        chunks = []
        words = text.split()
        
        current_chunk = ""
        for word in words:
            test_chunk = f"{current_chunk} {word}" if current_chunk else word
            test_tokens = self._count_tokens(test_chunk)
            
            if test_tokens > 1000:  # 1000 토큰마다 분할
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                current_chunk = test_chunk
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    def _chunk_text(self, text: str) -> List[str]:
        """청크 단위로 텍스트 분할 (스마트 청킹 사용)"""
        return self._smart_chunk_text(text)
    
    async def _get_embedding_with_retry(self, text: str, max_retries: int = 3) -> List[float]:
        """재시도 로직이 포함된 임베딩 생성 - 토큰 수 검증 포함"""
        # 토큰 수 사전 검증
        token_count = self._count_tokens(text)
        if token_count > 8000:
            logger.warning(f"Text too long for embedding ({token_count} tokens), truncating to 8000 tokens")
            # 텍스트를 8000 토큰으로 자르기
            tokens = self.tokenizer.encode(text)
            truncated_tokens = tokens[:8000]
            text = self.tokenizer.decode(truncated_tokens)
            token_count = 8000
        
        for attempt in range(max_retries):
            try:
                async with self.embedding_limiter:
                    # blocking OpenAI 호출을 비동기로 변환
                    response = await asyncio.to_thread(
                        self.openai_client.embeddings.create,
                        input=text,
                        model="text-embedding-ada-002"
                    )
                    return response.data[0].embedding
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to embed after {max_retries} attempts: {e}")
                    raise
                
                # 지수 백오프로 대기
                wait_time = 2 ** attempt
                logger.warning(f"Embedding attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
        
        raise Exception("Max retries exceeded")
    
    async def _get_embedding_async(self, text: str) -> List[float]:
        """비동기로 임베딩 생성 (재시도 포함)"""
        return await self._get_embedding_with_retry(text)
    
    async def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트의 임베딩을 병렬로 생성"""
        logger.info(f"Getting embeddings for {len(texts)} texts in parallel")
        
        # 병렬로 임베딩 생성
        tasks = [self._get_embedding_async(text) for text in texts]
        embeddings = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리 - 실패한 임베딩은 None으로 표시
        valid_embeddings = []
        for i, result in enumerate(embeddings):
            if isinstance(result, Exception):
                logger.error(f"Failed to get embedding for text {i}: {result}")
                # 실패한 경우 None으로 표시 (나중에 필터링됨)
                valid_embeddings.append(None)
            else:
                valid_embeddings.append(result)
        
        return valid_embeddings
    
    async def store_document(self, document: Document) -> bool:
        """Store a single document in Qdrant"""
        try:
            # Combine title and content for embedding
            text_for_embedding = f"{document.title}\n{document.content}"
            embedding = await self._get_embedding_async(text_for_embedding)
            
            # Create point for Qdrant (use UUID for ID)
            point_uuid = str(uuid.uuid4())
            point_data = {
                "points": [{
                    "id": point_uuid,
                    "vector": embedding,
                    "payload": {
                        "original_id": document.id,  # 원래 문서 ID 저장
                        "title": document.title,
                        "content": document.content,
                        "url": document.url,
                        "mobile_url": document.mobile_url,
                        "hierarchy": document.hierarchy,
                        "metadata": document.metadata,
                        "created_at": document.created_at.isoformat() if document.created_at else None,
                        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
                    }
                }]
            }
            
            # Upsert point to collection (use PUT for upsert)
            response = await self.client.put(
                f"{self.base_url}/collections/{self.collection_name}/points",
                json=point_data
            )
            response.raise_for_status()
            
            logger.info(f"Stored document: {document.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store document {document.id}: {e}")
            return False
    
    async def _process_document_batch(self, documents: List[Document], progress_tracker: ProgressTracker) -> Dict[str, int]:
        """문서 배치를 처리하고 메모리 효율적으로 관리"""
        batch_success = 0
        batch_failed = 0
        batch_failed_docs = []
        
        try:
            # 1단계: 배치 내 문서들을 청킹
            all_chunks = []
            chunk_metadata = []
            
            for doc in documents:
                full_text = f"{doc.title}\n{doc.content}"
                chunks = self._chunk_text(full_text)
                
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    chunk_metadata.append({
                        "document": doc,
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    })
            
            # 2단계: 임베딩 생성
            logger.info(f"Starting embedding generation for {len(all_chunks)} chunks")
            embeddings = await self._get_embeddings_batch(all_chunks)
            logger.info(f"Completed embedding generation, got {len(embeddings)} embeddings")
            
            # 3단계: Qdrant 포인트 생성 및 업서트
            points_batch = []
            for chunk, embedding, metadata in zip(all_chunks, embeddings, chunk_metadata):
                doc = metadata["document"]
                
                # UUID 형식의 고유 ID 생성
                point_uuid = str(uuid.uuid4())
                
                # 실패한 임베딩 건너뛰기
                if embedding is None:
                    logger.warning(f"Skipping chunk due to failed embedding")
                    continue
                
                # 임베딩 벡터 유효성 검증
                if not embedding or len(embedding) != self.vector_size:
                    logger.warning(f"Invalid embedding for chunk, skipping. Expected size: {self.vector_size}, got: {len(embedding) if embedding else 0}")
                    continue
                
                # Qdrant API 형식에 맞게 포인트 생성
                point = {
                    "id": point_uuid,  # UUID 문자열
                    "vector": embedding,
                    "payload": {
                        "original_id": str(doc.id),  # 문자열로 변환
                        "title": str(doc.title) if doc.title else "",
                        "content": str(chunk),
                        "url": str(doc.url) if doc.url else "",
                        "mobile_url": str(doc.mobile_url) if doc.mobile_url else "",
                        "hierarchy": doc.hierarchy if doc.hierarchy else [],
                        "metadata": doc.metadata if doc.metadata else {},
                        "chunk_index": int(metadata["chunk_index"]),
                        "total_chunks": int(metadata["total_chunks"]),
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                    }
                }
                points_batch.append(point)
            
            # 디버깅: 첫 번째 포인트 구조 로깅
            if points_batch:
                sample_point = points_batch[0]
                logger.info(f"Sample point structure: id={sample_point['id']}, vector_len={len(sample_point['vector'])}, payload_keys={list(sample_point['payload'].keys())}")
            
            # 4단계: Qdrant 배치 업서트
            qdrant_batch_size = 50  # 더 작은 배치로 메모리 절약
            logger.info(f"Starting Qdrant batch upsert: {len(points_batch)} points in batches of {qdrant_batch_size}")
            
            for i in range(0, len(points_batch), qdrant_batch_size):
                batch = points_batch[i:i + qdrant_batch_size]
                batch_num = (i // qdrant_batch_size) + 1
                total_batches = (len(points_batch) + qdrant_batch_size - 1) // qdrant_batch_size
                
                logger.info(f"Processing Qdrant batch {batch_num}/{total_batches} ({len(batch)} points)")
                
                try:
                    response = await self.client.put(
                        f"{self.base_url}/collections/{self.collection_name}/points",
                        json={"points": batch}
                    )
                    response.raise_for_status()
                    logger.info(f"✅ Successfully uploaded batch {batch_num}/{total_batches} to Qdrant")
                    
                except Exception as e:
                    # 상세한 오류 정보 로깅
                    error_details = ""
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            error_body = await e.response.text()
                            error_details = f" - Response: {error_body}"
                        except:
                            pass
                    
                    logger.error(f"Failed to upsert Qdrant batch: {e}{error_details}")
                    logger.error(f"Batch size: {len(batch)}, First point keys: {list(batch[0].keys()) if batch else 'empty'}")
                    
                    batch_docs = set(point["payload"]["original_id"] for point in batch)
                    batch_failed += len(batch_docs)
                    batch_failed_docs.extend(batch_docs)
            
            # 성공한 문서 계산
            processed_docs = set(doc.id for doc in documents)
            failed_docs = set(batch_failed_docs)
            successful_docs = processed_docs - failed_docs
            batch_success = len(successful_docs)
            
            # 진행률 업데이트
            progress_tracker.update(len(documents))
            
            return {
                "success_count": batch_success,
                "failed_count": len(failed_docs),
                "failed_documents": list(failed_docs)
            }
            
        except Exception as e:
            logger.error(f"Error processing document batch: {e}")
            return {
                "success_count": 0,
                "failed_count": len(documents),
                "failed_documents": [doc.id for doc in documents]
            }
        finally:
            # 메모리 정리
            gc.collect()
    
    async def store_documents(self, documents: List[Document]) -> Dict[str, int]:
        """문서 크기에 따른 차등 처리로 메모리 효율적 저장"""
        total_docs = len(documents)
        logger.info(f"Starting to store {total_docs} documents with memory-efficient processing")
        
        # 문서 크기별 분류
        small_docs = []
        large_docs = []
        
        for doc in documents:
            content_size = len(doc.content)
            if content_size < 50000:  # 50KB 미만은 작은 문서
                small_docs.append(doc)
            else:
                large_docs.append(doc)
        
        logger.info(f"Classified: {len(small_docs)} small docs, {len(large_docs)} large docs")
        
        total_success = 0
        total_failed = 0
        all_failed_docs = []
        
        # 진행률 추적기
        progress_tracker = ProgressTracker(total_docs, "Qdrant Storage")
        
        try:
            # 1. 작은 문서들을 배치로 처리 (메모리 효율성)
            if small_docs:
                batch_size = 20  # 작은 배치로 메모리 관리
                for i in range(0, len(small_docs), batch_size):
                    batch = small_docs[i:i + batch_size]
                    result = await self._process_document_batch(batch, progress_tracker)
                    
                    total_success += result["success_count"]
                    total_failed += result["failed_count"]
                    all_failed_docs.extend(result["failed_documents"])
                    
                    # 배치 간 잠시 대기
                    await asyncio.sleep(0.1)
            
            # 2. 큰 문서들을 개별 처리
            for large_doc in large_docs:
                try:
                    result = await self._process_document_batch([large_doc], progress_tracker)
                    total_success += result["success_count"]
                    total_failed += result["failed_count"]
                    all_failed_docs.extend(result["failed_documents"])
                    
                except Exception as e:
                    logger.error(f"Failed to process large document {large_doc.id}: {e}")
                    total_failed += 1
                    all_failed_docs.append(large_doc.id)
                    progress_tracker.update(1)
            
            # 중복 제거
            unique_failed_docs = list(set(all_failed_docs))
            
            logger.info(f"Qdrant storage completed: {total_success} success, {len(unique_failed_docs)} failed")
            
            return {
                "success_count": total_success,
                "failed_count": len(unique_failed_docs),
                "failed_documents": unique_failed_docs
            }
            
        except Exception as e:
            logger.error(f"Critical error in store_documents: {e}")
            return {
                "success_count": 0,
                "failed_count": total_docs,
                "failed_documents": [doc.id for doc in documents]
            }
    
    async def search_similar_documents(
        self, 
        query: str, 
        limit: int = 5, 
        score_threshold: float = 0.3  # 0.7 → 0.3으로 낮춰서 recall 향상
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity"""
        try:
            query_embedding = await self._get_embedding_async(query)
            
            # Search request payload
            search_payload = {
                "vector": query_embedding,
                "limit": limit,
                "score_threshold": score_threshold,
                "with_payload": True,
                "with_vector": False
            }
            
            # Perform search
            response = await self.client.post(
                f"{self.base_url}/collections/{self.collection_name}/points/search",
                json=search_payload
            )
            response.raise_for_status()
            search_data = response.json()
            
            results = []
            for point in search_data.get("result", []):
                result = {
                    "id": point["id"],
                    "score": point["score"],
                    "payload": point.get("payload", {})
                }
                results.append(result)
            
            logger.info(f"Found {len(results)} similar documents for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []
    
    async def delete_all_documents(self) -> Dict[str, Any]:
        """Delete all documents from the collection"""
        try:
            # Delete the entire collection
            response = await self.client.delete(
                f"{self.base_url}/collections/{self.collection_name}"
            )
            response.raise_for_status()
            
            # Recreate the collection
            await self.initialize_collection()
            
            logger.info("Successfully deleted all documents from Qdrant and recreated collection")
            return {
                "success": True,
                "message": "All documents deleted from Qdrant"
            }
            
        except Exception as e:
            logger.error(f"Failed to delete all documents from Qdrant: {e}")
            return {
                "success": False,
                "message": f"Failed to delete documents: {str(e)}"
            }
    
    async def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection"""
        try:
            response = await self.client.get(
                f"{self.base_url}/collections/{self.collection_name}"
            )
            response.raise_for_status()
            collection_data = response.json()
            
            return {
                "success": True,
                "collection_name": self.collection_name,
                "points_count": collection_data.get("result", {}).get("points_count", 0),
                "vector_size": collection_data.get("result", {}).get("config", {}).get("params", {}).get("vectors", {}).get("size", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {
                "success": False,
                "message": f"Failed to get collection info: {str(e)}"
            }


# Global instance - will be initialized lazily
qdrant_service = None

def get_qdrant_service() -> QdrantService:
    """Get or create Qdrant service instance"""
    global qdrant_service
    if qdrant_service is None:
        qdrant_service = QdrantService()
    return qdrant_service
