"""RAG Application Service - orchestrates RAG operations"""
import json
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.domains.rag.entities.document import Document
from app.domains.rag.schemas.rag_schemas import (
    RagUploadResponse, RagQueryRequest, RagQueryResponse, DocumentChunk
)
from app.infrastructure.vectordb.qdrant_service import get_qdrant_service
from app.infrastructure.search.opensearch_service import get_opensearch_service
from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)


class RagApplicationService:
    """Application service for managing RAG operations"""
    
    def __init__(self):
        self.qdrant_service = None
        self.opensearch_service = None
        self.llm_service = llm_service
    
    def _get_services(self):
        """Lazy initialization of services"""
        if self.qdrant_service is None:
            self.qdrant_service = get_qdrant_service()
        if self.opensearch_service is None:
            self.opensearch_service = get_opensearch_service()
        return self.qdrant_service, self.opensearch_service
    
    async def initialize_services(self):
        """Initialize all RAG services"""
        try:
            qdrant_service, opensearch_service = self._get_services()
            await qdrant_service.initialize_collection()
            await opensearch_service.initialize_index()
            logger.info("RAG services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG services: {e}")
            raise
    
    async def upload_documents_from_json(self, json_data: List[Dict[str, Any]]) -> RagUploadResponse:
        """Upload documents from JSON data"""
        start_time = time.time()
        
        try:
            # Convert JSON data to Document entities
            documents = []
            for i, item in enumerate(json_data):
                try:
                    document = Document.from_json_data(item)
                    documents.append(document)
                    
                    # 첫 번째 문서의 내용 확인 (디버깅용)
                    if i == 0:
                        logger.info(f"🔍 First document sample:")
                        logger.info(f"   ID: {document.id}")
                        logger.info(f"   Title: {document.title}")
                        logger.info(f"   Content length: {len(document.content)}")
                        logger.info(f"   Content preview: {document.content[:200]}...")
                    
                    if (i + 1) % 100 == 0:  # 100개마다 진행 상황 로그
                        logger.info(f"Parsed {i + 1}/{len(json_data)} documents...")
                except Exception as e:
                    logger.warning(f"Failed to parse document {item.get('docId', 'unknown')}: {e}")
            
            logger.info(f"Successfully parsed {len(documents)} documents from JSON")
            
            # Store in both Qdrant and OpenSearch
            qdrant_service, opensearch_service = self._get_services()
            
            logger.info("Starting Qdrant storage...")
            qdrant_result = await qdrant_service.store_documents(documents)
            logger.info(f"Qdrant storage completed: {qdrant_result}")
            
            logger.info("Starting OpenSearch storage...")
            opensearch_result = await opensearch_service.store_documents(documents)
            logger.info(f"OpenSearch storage completed: {opensearch_result}")
            
            # Combine results
            total_processed = len(documents)
            total_failed = max(qdrant_result["failed_count"], opensearch_result["failed_count"])
            total_success = total_processed - total_failed
            
            failed_docs = list(set(
                qdrant_result["failed_documents"] + opensearch_result["failed_documents"]
            ))
            
            processing_time = time.time() - start_time
            logger.info(f"📊 Document upload completed in {processing_time:.2f}s:")
            logger.info(f"   📄 Original documents: {len(documents)}")
            logger.info(f"   ✅ Successfully processed: {total_success}")
            logger.info(f"   ❌ Failed: {total_failed}")
            logger.info(f"   🔍 Qdrant chunks: {qdrant_result.get('success_count', 0)}")
            logger.info(f"   📚 OpenSearch docs: {opensearch_result.get('success_count', 0)}")
            logger.info(f"   ⏱️  Processing time: {processing_time:.2f}s")
            
            return RagUploadResponse(
                message=f"Documents uploaded successfully in {processing_time:.2f} seconds",
                processed_count=total_success,
                failed_count=total_failed,
                failed_documents=failed_docs
            )
            
        except Exception as e:
            logger.error(f"Failed to upload documents: {e}")
            raise
    
    async def query_documents(self, request: RagQueryRequest) -> RagQueryResponse:
        """Query documents using RAG approach"""
        start_time = time.time()
        
        try:
            qdrant_service, opensearch_service = self._get_services()
            
            # 키워드 추출 및 검색 쿼리 최적화
            search_queries = self._extract_search_queries(request.query)
            logger.info(f"🔍 Search queries: {search_queries}")
            
            # Step 1: Vector similarity search with Qdrant
            # 유사도 임계값을 낮춰서 더 많은 결과를 가져오기
            vector_results = await qdrant_service.search_similar_documents(
                query=search_queries[0],  # 첫 번째 키워드 사용
                limit=request.max_results * 3,  # 더 많은 결과 가져오기 (3배)
                score_threshold=0.0  # 임계값 제거
            )
            
            # Step 2: Text search with OpenSearch
            text_results = await opensearch_service.search_documents(
                query=search_queries[0],  # 첫 번째 키워드 사용
                limit=request.max_results * 2  # 더 많은 결과 가져오기
            )
            
            # Step 3: Combine and deduplicate results
            combined_results = self._combine_search_results(vector_results, text_results)
            
            logger.info(f"🔍 Search results summary:")
            logger.info(f"   📊 Vector results: {len(vector_results)}")
            logger.info(f"   📊 Text results: {len(text_results)}")
            logger.info(f"   📊 Combined results: {len(combined_results)}")
            
            # 검색 결과 상세 로그
            for i, result in enumerate(combined_results[:5]):  # 상위 5개 로그
                logger.info(f"   📄 Result {i+1}: id={result.get('id', 'unknown')}, score={result.get('combined_score', 0):.2f}")
                if 'payload' in result:
                    payload = result['payload']
                    logger.info(f"      Title: {payload.get('title', 'No title')}")
                    logger.info(f"      Content length: {len(payload.get('content', ''))}")
                    # 홈코노미 관련 문서 찾기
                    if '홈코노미' in payload.get('title', '') or '홈코노미' in payload.get('content', ''):
                        logger.info(f"      🎯 FOUND HOMECONOMY DOCUMENT!")
                elif 'source' in result:
                    source = result['source']
                    logger.info(f"      Title: {source.get('title', 'No title')}")
                    logger.info(f"      Content length: {len(source.get('content', ''))}")
                    # 홈코노미 관련 문서 찾기
                    if '홈코노미' in source.get('title', '') or '홈코노미' in source.get('content', ''):
                        logger.info(f"      🎯 FOUND HOMECONOMY DOCUMENT!")
            
            # Step 4: Prepare context for LLM with token limit
            context_chunks = []
            sources = []
            max_context_tokens = 15000  # 더 작은 값으로 설정하여 LLM이 처리할 수 있도록
            
            # 토큰 카운터 초기화
            total_tokens = 0
            
            # Qdrant 결과에서 홈코노미 관련 문서 우선 포함
            homeco_results = [r for r in combined_results if '홈코노미' in str(r.get('payload', {}).get('title', '')) or '홈코노미' in str(r.get('source', {}).get('title', ''))]
            other_results = [r for r in combined_results if r not in homeco_results]
            
            # 홈코노미 문서를 우선적으로 포함
            prioritized_results = homeco_results + other_results
            logger.info(f"🎯 Prioritized results: {len(homeco_results)} homeco + {len(other_results)} others")
            
            # 먼저 모든 점수를 수집하여 OpenSearch 정규화 범위 파악
            opensearch_scores = []
            
            for result in prioritized_results[:request.max_results * 2]:
                if 'source' in result:  # OpenSearch result
                    opensearch_scores.append(result['score'])
            
            # OpenSearch 점수 범위 계산 (Qdrant는 이미 0~1 범위이므로 정규화 불필요)
            opensearch_max = max(opensearch_scores) if opensearch_scores else 1.0
            opensearch_min = min(opensearch_scores) if opensearch_scores else 0.0
            
            logger.info(f"📊 Score ranges - OpenSearch: min={opensearch_min:.3f}, max={opensearch_max:.3f}")
            
            for result in prioritized_results[:request.max_results * 2]:  # 더 많은 결과 확인
                if 'payload' in result:  # Qdrant result
                    chunk_data = result['payload']
                    raw_score = result['score']
                    # Qdrant 코사인 거리를 유사도로 변환 (이미 0~1 범위이므로 추가 정규화 불필요)
                    normalized_score = max(0.0, 1.0 - raw_score)
                elif 'source' in result:  # OpenSearch result
                    chunk_data = result['source']
                    raw_score = result['score']
                    # OpenSearch 점수를 Min-Max 정규화로 0-1 범위로 정규화
                    if opensearch_max > opensearch_min:
                        normalized_score = (raw_score - opensearch_min) / (opensearch_max - opensearch_min + 1e-6)
                        normalized_score = max(0.0, min(1.0, normalized_score))
                    else:
                        normalized_score = 0.5  # fallback
                else:
                    continue
                
                # 청크 텍스트 생성
                title = chunk_data.get('title', '')
                content = chunk_data.get('content', '')
                chunk_text = f"Title: {title}\nContent: {content}"
                
                # 문서 내용 디버깅 로그
                logger.info(f"📄 Document chunk: title='{title}', content_length={len(content)}")
                if content:
                    logger.info(f"📝 Content preview: {content[:300]}...")
                else:
                    logger.warning(f"⚠️ Empty content for document: {chunk_data.get('id', 'unknown')}")
                
                # 토큰 수 계산 (간단한 추정)
                estimated_tokens = len(chunk_text.split()) * 1.3  # 대략적인 토큰 수 추정
                
                # 토큰 제한 확인
                if total_tokens + estimated_tokens > max_context_tokens:
                    logger.warning(f"Context token limit reached ({total_tokens:.0f} tokens), stopping at {len(context_chunks)} chunks")
                    break
                
                context_chunks.append(chunk_text)
                total_tokens += estimated_tokens
                
                # 검색 소스 정보 추가
                search_source = "vector" if 'payload' in result else "text"
                raw_score = result['score']
                
                # 원본 점수 그대로 표시 (일관성 유지)
                if search_source == "vector":
                    # Qdrant: 코사인 거리 그대로 사용
                    display_score = raw_score
                    score_label = "코사인 거리"
                else:
                    # OpenSearch: BM25 점수 그대로 사용
                    display_score = raw_score
                    score_label = "BM25 점수"
                
                sources.append({
                    "id": result.get('id', ''),
                    "title": chunk_data.get('title', ''),
                    "url": chunk_data.get('url', ''),
                    "hierarchy": chunk_data.get('hierarchy', []),
                    "similarity_score": display_score,
                    "score_label": score_label,
                    "search_source": search_source,
                    "raw_score": raw_score,
                    "search_method": "Qdrant (벡터 검색)" if search_source == "vector" else "OpenSearch (텍스트 검색)"
                })
            
            logger.info(f"Prepared context: {len(context_chunks)} chunks, ~{total_tokens:.0f} tokens")
            
            # Context에 포함된 문서들 디버깅 로그
            logger.info(f"📋 Context documents:")
            for i, (chunk, source) in enumerate(zip(context_chunks, sources)):
                logger.info(f"   {i+1}. {source['title']} (normalized_score: {source['similarity_score']:.3f})")
                if '홈코노미' in source['title'] or '홈코노미' in chunk:
                    logger.info(f"      🎯 HOMECONOMY FOUND IN CONTEXT!")
            
            # Step 5: Generate answer using LLM
            if context_chunks:
                context = "\n\n---\n\n".join(context_chunks)
                logger.info(f"🔍 Context prepared for LLM: {len(context_chunks)} chunks, {len(context)} characters")
                logger.info(f"📝 First chunk preview: {context_chunks[0][:200]}..." if context_chunks else "No chunks")
                answer = await self._generate_answer(request.query, context)
            else:
                logger.warning("❌ No context chunks found for query")
                answer = "죄송합니다. 질문과 관련된 정보를 찾을 수 없습니다."
                sources = []
            
            processing_time = time.time() - start_time
            
            logger.info(f"RAG query completed in {processing_time:.2f}s: "
                       f"found {len(sources)} relevant sources")
            
            return RagQueryResponse(
                answer=answer,
                sources=sources,
                query=request.query,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Failed to process RAG query: {e}")
            raise
    
    def _combine_search_results(
        self, 
        vector_results: List[Dict[str, Any]], 
        text_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Combine and deduplicate search results from different sources"""
        combined = {}
        
        # Add vector results
        for result in vector_results:
            doc_id = result['id']
            combined[doc_id] = {
                **result,
                'source_type': 'vector',
                'combined_score': result['score']
            }
        
        # Add text results, boost score if already exists
        for result in text_results:
            doc_id = result['id']
            if doc_id in combined:
                # Document found in both searches, boost the score
                combined[doc_id]['combined_score'] = (
                    combined[doc_id]['score'] * 0.7 + result['score'] * 0.3
                )
                combined[doc_id]['source_type'] = 'both'
            else:
                combined[doc_id] = {
                    **result,
                    'source_type': 'text',
                    'combined_score': result['score']
                }
        
        # Sort by combined score
        sorted_results = sorted(
            combined.values(), 
            key=lambda x: x['combined_score'], 
            reverse=True
        )
        
        return sorted_results
    
    def _extract_search_queries(self, query: str) -> List[str]:
        """자연어 질문에서 검색 키워드 추출"""
        # 기본 쿼리
        queries = [query]
        
        # 특정 키워드가 포함된 경우 단순화
        if "홈코노미" in query:
            queries.append("홈코노미")
            queries.append("홈코노미캠페인")
        
        if "eSIM" in query:
            queries.append("eSIM")
            queries.append("eSIM이동")
        
        if "듀얼번호" in query:
            queries.append("듀얼번호")
            queries.append("듀얼번호가입")
        
        if "데이터쉐어링" in query:
            queries.append("데이터쉐어링")
            queries.append("데이터쉐어링가입")
        
        # 중복 제거
        return list(dict.fromkeys(queries))
    
    async def _generate_answer(self, query: str, context: str) -> str:
        """Generate answer using LLM with retrieved context"""
        try:
            prompt = f"""사용자 질문에 대해 아래 정보를 바탕으로 정확한 답변을 제공해주세요.

질문: {query}

관련 정보:
{context}

위 정보를 바탕으로 질문에 대한 구체적이고 도움이 되는 답변을 제공해주세요:"""

            logger.info(f"🤖 Sending prompt to LLM: {len(prompt)} characters")
            logger.info(f"📋 Query: {query}")
            logger.info(f"📄 Context length: {len(context)} characters")
            
            # Use the existing LLM service
            response = await self.llm_service.generate_response(prompt)
            logger.info(f"✅ LLM response received: {len(response)} characters")
            logger.info(f"💬 Response preview: {response[:200]}...")
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate LLM answer: {e}")
            return "답변 생성 중 오류가 발생했습니다."
    
    async def delete_all_data(self) -> Dict[str, Any]:
        """Delete all RAG data from both Qdrant and OpenSearch"""
        start_time = time.time()
        
        try:
            qdrant_service, opensearch_service = self._get_services()
            
            # Delete from both services
            qdrant_result = await qdrant_service.delete_all_documents()
            opensearch_result = await opensearch_service.delete_all_documents()
            
            processing_time = time.time() - start_time
            
            # Check if both operations were successful
            both_success = qdrant_result.get("success", False) and opensearch_result.get("success", False)
            
            if both_success:
                message = "모든 RAG 데이터가 성공적으로 삭제되었습니다."
                logger.info(f"All RAG data deleted successfully in {processing_time:.2f}s")
            else:
                message = f"일부 데이터 삭제 실패: Qdrant({qdrant_result.get('message', '')}), OpenSearch({opensearch_result.get('message', '')})"
                logger.warning(f"Partial deletion failure in {processing_time:.2f}s")
            
            return {
                "success": both_success,
                "message": message,
                "processing_time": processing_time,
                "details": {
                    "qdrant": qdrant_result,
                    "opensearch": opensearch_result
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to delete RAG data: {e}")
            return {
                "success": False,
                "message": f"데이터 삭제 중 오류가 발생했습니다: {str(e)}",
                "processing_time": time.time() - start_time
            }
    
    async def get_data_info(self) -> Dict[str, Any]:
        """Get information about stored RAG data"""
        try:
            qdrant_service, opensearch_service = self._get_services()
            
            # Get info from both services
            qdrant_info = await qdrant_service.get_collection_info()
            opensearch_info = await opensearch_service.get_index_info()
            
            qdrant_count = qdrant_info.get("points_count", 0) if qdrant_info.get("success") else 0
            opensearch_count = opensearch_info.get("document_count", 0) if opensearch_info.get("success") else 0
            
            return {
                "success": True,
                "qdrant": qdrant_info,
                "opensearch": opensearch_info,
                "summary": {
                    "qdrant_documents": qdrant_count,
                    "opensearch_documents": opensearch_count,
                    "chunk_ratio": round(qdrant_count / opensearch_count, 2) if opensearch_count > 0 else 0,
                    "status": "✅ Both services healthy" if qdrant_info.get("success") and opensearch_info.get("success") else "⚠️ Some services have issues"
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get data info: {e}")
            return {
                "success": False,
                "message": f"데이터 정보 조회 중 오류가 발생했습니다: {str(e)}"
            }


# Global instance
rag_service = RagApplicationService()
