"""LLM Service - Handles OpenAI API interactions"""
from typing import List, Dict, Any, AsyncGenerator, Optional
import json
import logging
import tiktoken
import numpy as np
from openai import AsyncOpenAI
from app.config import settings
from app.infrastructure.mcp.mcp_service import mcp_service
from app.shared.exceptions.base import LLMQueryError

logger = logging.getLogger(__name__)

# 임베딩 모델 (지연 로딩)
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.warning("sentence-transformers not available, falling back to keyword-based intent detection")

class LLMService:
    """Service class for managing LLM interactions"""
    
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # 임베딩 모델 초기화 (지연 로딩)
        self._embedding_model: Optional[SentenceTransformer] = None
        self._intent_examples = self._get_intent_examples()
        
    def _get_embedding_model(self) -> Optional[SentenceTransformer]:
        """임베딩 모델 지연 로딩"""
        if not EMBEDDING_AVAILABLE:
            return None
            
        if self._embedding_model is None:
            try:
                # 다국어 지원 경량 모델 사용
                self._embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                logger.info("🎯 임베딩 모델 로드 완료: paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as e:
                logger.error(f"임베딩 모델 로드 실패: {e}")
                return None
        
        return self._embedding_model
    
    def _get_intent_examples(self) -> Dict[str, List[str]]:
        """의도별 예시 문장들"""
        return {
            'web_crawling': [
                "웹사이트를 크롤링해주세요",
                "이 URL의 내용을 가져와주세요",
                "페이지를 스크래핑해서 분석해주세요",
                "사이트 데이터를 수집해주세요",
                "웹페이지 정보를 추출해주세요"
            ],
            'system_status': [
                "시스템 상태를 확인해주세요",
                "서버가 정상 작동하는지 체크해주세요",
                "헬스체크를 실행해주세요",
                "현재 시스템 통계를 보여주세요",
                "서비스 상태를 알려주세요"
            ],
            'text_analysis': [
                "이 텍스트를 요약해주세요",
                "내용을 분석해서 정리해주세요",
                "문서의 핵심 내용을 추출해주세요",
                "텍스트에서 주요 정보를 찾아주세요",
                "내용을 간단히 요약해주세요"
            ],
            'html_processing': [
                "HTML 파일을 처리해주세요",
                "컨플루언스 문서를 변환해주세요",
                "업로드한 파일을 분석해주세요",
                "HTML에서 메인 컨텐츠를 추출해주세요",
                "ARI 파일을 파싱해주세요"
            ],
            'db_query': [
                "메뉴 정보를 조회해주세요",
                "링크 데이터를 찾아주세요",
                "담당자 정보를 검색해주세요",
                "데이터베이스에서 정보를 가져와주세요",
                "매니저 목록을 보여주세요"
            ],
            'database_schema': [
                "메뉴 테이블 구조를 보여주세요",
                "데이터베이스 스키마를 알려주세요",
                "컬럼명을 보여주세요",
                "테이블 필드를 알려주세요",
                "메뉴 컬럼 정보를 확인해주세요",
                "데이터 구조를 설명해주세요"
            ],
            'rag_query': [
                "문서에서 검색해주세요",
                "지식베이스에서 찾아주세요",
                "RAG로 질문에 답변해주세요",
                "등록된 문서에서 정보를 찾아주세요",
                "벡터 검색을 실행해주세요"
            ]
        }
    
    async def _classify_intent_with_embedding(self, question: str) -> List[str]:
        """임베딩 기반 의도 분류"""
        model = self._get_embedding_model()
        if not model:
            return []
        
        try:
            # 질문 임베딩
            question_embedding = model.encode([question])
            
            detected_intents = []
            similarity_threshold = 0.6  # 유사도 임계값
            
            # 각 의도별로 유사도 계산
            for intent, examples in self._intent_examples.items():
                example_embeddings = model.encode(examples)
                
                # 질문과 각 예시 간의 코사인 유사도 계산
                similarities = np.dot(question_embedding, example_embeddings.T).flatten()
                max_similarity = float(np.max(similarities))
                
                logger.debug(f"📊 의도 '{intent}' 유사도: {max_similarity:.3f}")
                
                if max_similarity > similarity_threshold:
                    detected_intents.append((intent, max_similarity))
            
            # 유사도 순으로 정렬하여 상위 3개만 선택
            detected_intents.sort(key=lambda x: x[1], reverse=True)
            result = [intent for intent, _ in detected_intents[:3]]
            
            logger.info(f"🎯 임베딩 기반 의도 분류: {result}")
            return result
            
        except Exception as e:
            logger.error(f"임베딩 기반 의도 분류 실패: {e}")
            return []
    
    async def _classify_intent_with_llm(self, question: str) -> List[str]:
        """LLM 프롬프팅 기반 의도 분류"""
        try:
            prompt = f"""다음 사용자 질문을 분석하여 해당하는 의도 카테고리를 선택하세요.

카테고리 설명:
- web_crawling: 웹페이지 크롤링, 스크래핑, URL 데이터 수집
- system_status: 시스템 상태 확인, 헬스체크, 서버 모니터링  
- text_analysis: 텍스트 요약, 분석, 정보 추출
- html_processing: HTML 파일 처리, 컨플루언스 문서 변환, ARI 파일 파싱
- db_query: 데이터베이스 조회, 메뉴/링크/담당자 정보 검색 (실제 데이터)
- database_schema: 데이터베이스 스키마 조회, 테이블 구조, 컬럼 정보 확인
- rag_query: 문서 검색, 지식베이스 질의, RAG 기반 질문답변

사용자 질문: "{question}"

위 질문에 가장 적합한 카테고리 1-3개를 JSON 배열 형태로 응답하세요.
예시: ["web_crawling", "text_analysis"]

응답:"""

            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",  # 빠르고 저렴한 모델 사용
                messages=[
                    {"role": "system", "content": "당신은 사용자 의도를 정확히 분류하는 AI 어시스턴트입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1  # 일관성을 위해 낮은 온도
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱 시도
            try:
                if result_text.startswith('[') and result_text.endswith(']'):
                    intents = json.loads(result_text)
                else:
                    # 텍스트에서 JSON 부분 추출
                    import re
                    json_match = re.search(r'\[.*?\]', result_text)
                    if json_match:
                        intents = json.loads(json_match.group())
                    else:
                        intents = []
                
                # 유효한 의도만 필터링
                valid_intents = [intent for intent in intents if intent in self._intent_examples.keys()]
                
                logger.info(f"🤖 LLM 기반 의도 분류: {valid_intents}")
                return valid_intents
                
            except json.JSONDecodeError as e:
                logger.warning(f"LLM 응답 JSON 파싱 실패: {result_text}, 오류: {e}")
                return []
                
        except Exception as e:
            logger.error(f"LLM 기반 의도 분류 실패: {e}")
            return []
    
    async def _classify_intent_hybrid(self, question: str) -> List[str]:
        """하이브리드 의도 분류 (임베딩 + LLM)"""
        embedding_intents = await self._classify_intent_with_embedding(question)
        llm_intents = await self._classify_intent_with_llm(question)
        
        # 두 결과를 조합하여 신뢰도 높은 의도 선택
        combined_intents = []
        
        # 1. 두 방법 모두에서 감지된 의도 (높은 신뢰도)
        common_intents = list(set(embedding_intents) & set(llm_intents))
        combined_intents.extend(common_intents)
        
        # 2. 임베딩에서만 감지된 의도 (중간 신뢰도)
        embedding_only = [i for i in embedding_intents if i not in common_intents]
        combined_intents.extend(embedding_only[:2])  # 상위 2개만
        
        # 3. LLM에서만 감지된 의도 (중간 신뢰도)
        llm_only = [i for i in llm_intents if i not in common_intents]
        combined_intents.extend(llm_only[:1])  # 상위 1개만
        
        # 중복 제거 및 최대 3개로 제한
        final_intents = list(dict.fromkeys(combined_intents))[:3]
        
        logger.info(f"🔄 하이브리드 의도 분류:")
        logger.info(f"   임베딩: {embedding_intents}")
        logger.info(f"   LLM: {llm_intents}")
        logger.info(f"   최종: {final_intents}")
        
        return final_intents
    
    def _format_tools_for_openai(self, available_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert MCP tools format to OpenAI tools format
        
        MCP format might be: {"name": "tool_name", "description": "...", "parameters": {...}}
        OpenAI expects: {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        """
        formatted_tools = []
        for tool in available_tools:
            # Check if already in OpenAI format
            if "type" in tool and tool["type"] == "function" and "function" in tool:
                formatted_tools.append(tool)
            else:
                # Convert from MCP format to OpenAI format
                formatted_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {
                            "type": "object",
                            "properties": {},
                            "required": []
                        })
                    }
                }
                formatted_tools.append(formatted_tool)
        return formatted_tools
    
    # (삭제됨) 상단 중복 정의된 _filter_tools_by_intent — 클래스의 하단 정의만 사용
    
    async def query(self, question: str, available_tools: List[Dict[str, Any]]) -> str:
        """Execute a query against the LLM with available tools"""
        try:
            # 1단계: 의도 분류 및 도구 필터링 (토큰 제한 해결)
            filtered_tools = await self._filter_tools_by_intent(question, available_tools)
            
            # Format tools for OpenAI
            formatted_tools = self._format_tools_for_openai(filtered_tools)
            
            # Log for debugging
            logger.info(f"🔍 의도 분류 완료: {len(filtered_tools)}개 도구 선택 (전체 {len(available_tools)}개 중)")
            logger.debug(f"Formatted tools: {json.dumps(formatted_tools[:1], indent=2)}")  # Log first tool as example
            
            tool_catalog = self._get_tool_categories_description(formatted_tools)
            system_prompt = f"""You are an AI assistant specialized in web analysis and data processing.

CRITICAL: Always use tools when available. Execute the appropriate tools to perform real work; avoid generic explanations without using tools.

Available tools (dynamic):
{tool_catalog}

Tool usage principles:
1) If a URL is present → use crawl4ai_scrape or crawl_urls_sequential
2) For system status → use health_check
3) For structured data conversion → use convert_to_json_format
4) For menu/DB queries → use menu_search
5) For HTML/Confluence content → use ari_extract_main_blocks and/or ari_markdown_to_json and/or convert_to_json_format

Response policy:
- After using tools, produce a concise, high-signal answer based on the results.
- IMPORTANT: Write all final answers to the user in Korean.
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
            
            # First API call with tools
            response = await self._client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=formatted_tools if formatted_tools else None,  # Only pass tools if available
                tool_choice="auto" if formatted_tools else None
            )
            
            # Check if tools were called
            message = response.choices[0].message
            
            if not message.tool_calls:
                return message.content or ""
            
            # Process tool calls
            messages.append(message.model_dump())  # Add assistant's message with tool calls
            
            # Execute each tool call
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Executing tool: {function_name} with args: {function_args}")
                
                try:
                    # Call your MCP service
                    tool_result = await mcp_service.call_tool(function_name, function_args)
                    
                    # Format the result
                    if hasattr(tool_result, 'structured_content'):
                        result_content = json.dumps(tool_result.structured_content, ensure_ascii=False)
                    elif hasattr(tool_result, 'data'):
                        result_content = json.dumps(tool_result.data, ensure_ascii=False)
                    elif isinstance(tool_result, dict):
                        result_content = json.dumps(tool_result, ensure_ascii=False)
                    else:
                        result_content = str(tool_result)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content
                    })
                except Exception as e:
                    logger.error(f"Tool execution failed for {function_name}: {e}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": str(e)}, ensure_ascii=False)
                    })
            
            # Second API call for final response
            final_response = await self._client.chat.completions.create(
                model=settings.openai_model,
                messages=messages
            )
            
            return final_response.choices[0].message.content or ""
            
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise LLMQueryError(f"LLM 쿼리 실행 중 오류: {str(e)}")
    
    async def _filter_tools_by_intent(self, question: str, available_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        임베딩 + LLM 프롬프팅 기반 의도 분석으로 관련 도구 필터링
        """
        try:
            # 하이브리드 의도 분류 실행
            detected_intents = await self._classify_intent_hybrid(question)
            
            # 폴백: 의도가 감지되지 않으면 키워드 기반 분석 사용
            if not detected_intents:
                logger.warning("🔄 하이브리드 분류 실패, 키워드 기반 폴백 사용")
                detected_intents = self._fallback_keyword_intent(question)
            
            # 의도별 도구 매핑 (확장된 버전)
            tool_mapping = {
                'web_crawling': [
                    'crawl4ai_scrape', 'crawl_urls_sequential', 'playwright_scrape',
                    'scrape_webpage', 'take_screenshot'
                ],
                'system_status': [
                    'health_check', 'get_system_stats', 'monitor_services'
                ],
                'text_analysis': [
                    'extract_keywords', 'analyze_sentiment',
                    'text_classification', 'content_analysis'
                ],
                'html_processing': [
                    'ari_extract_main_blocks', 'ari_markdown_to_json', 'convert_to_json_format',
                    'parse_html', 'extract_tables', 'convert_markdown'
                ],
                'db_query': [
                    'menu_search', 'search_database', 'query_menu_links',
                    'get_manager_info', 'search_records'
                ],
                'database_schema': [
                    'get_database_schema'
                ],
                'rag_query': [
                    'rag_search', 'vector_search', 'document_query',
                    'knowledge_base_search', 'semantic_search'
                ]
            }
            
            # 관련 도구들 수집
            relevant_tools = []
            for intent in detected_intents:
                relevant_tools.extend(tool_mapping.get(intent, []))
            
            # 스마트 기본 도구 선택 (의도에 따라 다르게)
            smart_essential_tools = []
            if 'web_crawling' in detected_intents or any('http' in question.lower() for protocol in ['http', 'www', '.com', '.kr']):
                smart_essential_tools.extend(['crawl4ai_scrape'])
            if 'system_status' in detected_intents or not detected_intents:
                smart_essential_tools.extend(['health_check'])
            if 'text_analysis' in detected_intents:
                smart_essential_tools.extend(['convert_to_json_format'])
                
            relevant_tools.extend(smart_essential_tools)
            
            # 중복 제거
            relevant_tools = list(set(relevant_tools))
            
            # 도구 필터링
            filtered_tools = []
            for tool in available_tools:
                tool_name = tool.get('function', {}).get('name', '')
                if tool_name in relevant_tools:
                    filtered_tools.append(tool)
            
            logger.info(f"🎯 최종 필터링 결과: {len(filtered_tools)}개 도구 선택 (전체 {len(available_tools)}개 중)")
            logger.info(f"   선택된 도구: {[t.get('function', {}).get('name', '') for t in filtered_tools]}")
            
            return filtered_tools if filtered_tools else available_tools[:10]  # 최대 10개로 제한
            
        except Exception as e:
            logger.error(f"의도 기반 필터링 실패, 전체 도구 사용: {e}")
            return available_tools[:15]  # 오류 시 상위 15개 도구 사용
    
    def _fallback_keyword_intent(self, question: str) -> List[str]:
        """키워드 기반 폴백 의도 분석 (기존 방식)"""
        question_lower = question.lower()
        
        intent_keywords = {
            'web_crawling': ['크롤링', 'crawl', 'url', '웹사이트', '웹페이지', '스크래핑', 'scrape', 'http'],
            'system_status': ['상태', 'status', 'health', '서버', '통계', 'statistics'],
            'text_analysis': ['요약', 'summarize', '분석', 'analyze', '추출', 'extract', '텍스트'],
            'html_processing': ['html', '파일', 'file', 'confluence', '업로드', 'upload', 'ari'],
            'db_query': ['메뉴', 'menu', '링크', 'link', '매니저', 'manager', '담당자', '조회', 'query'],
            'database_schema': ['스키마', 'schema', '구조', '컬럼', 'column', '테이블', 'table', '필드', 'field', '데이터구조'],
            'rag_query': ['rag', '검색', 'search', '문서', 'document', '지식', 'knowledge']
        }
        
        detected_intents = []
        for intent, keywords in intent_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                detected_intents.append(intent)
        
        logger.info(f"🔄 키워드 기반 의도 분류: {detected_intents}")
        return detected_intents
    
    def _get_tool_categories_description(self, tools: List[Dict[str, Any]]) -> str:
        """
        도구 카테고리별 설명 생성
        """
        categories = {
            'web': [],
            'system': [],
            'text': [],
            'html': [],
            'other': []
        }
        
        for tool in tools:
            tool_name = tool.get('function', {}).get('name', '')
            tool_desc = tool.get('function', {}).get('description', '')
            
            if 'crawl' in tool_name or 'scrape' in tool_name:
                categories['web'].append(f"- {tool_name}: {tool_desc}")
            elif 'health' in tool_name or 'status' in tool_name:
                categories['system'].append(f"- {tool_name}: {tool_desc}")
            elif 'summarize' in tool_name or 'extract' in tool_name:
                categories['text'].append(f"- {tool_name}: {tool_desc}")
            elif 'html' in tool_name or 'table' in tool_name:
                categories['html'].append(f"- {tool_name}: {tool_desc}")
            else:
                categories['other'].append(f"- {tool_name}: {tool_desc}")
        
        description = ""
        if categories['web']:
            description += "**웹 크롤링 도구:**\n" + "\n".join(categories['web']) + "\n\n"
        if categories['system']:
            description += "**시스템 상태 도구:**\n" + "\n".join(categories['system']) + "\n\n"
        if categories['text']:
            description += "**텍스트 분석 도구:**\n" + "\n".join(categories['text']) + "\n\n"
        if categories['html']:
            description += "**HTML 처리 도구:**\n" + "\n".join(categories['html']) + "\n\n"
        if categories['other']:
            description += "**기타 도구:**\n" + "\n".join(categories['other']) + "\n\n"
        
        return description
    
    async def generate_response(self, prompt: str) -> str:
        """
        Generate a simple response using OpenAI Chat Completions API
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            Generated response as string
        """
        try:
            # 토큰 수 계산 및 제한 확인
            tokens = self.tokenizer.encode(prompt)
            token_count = len(tokens)
            
            # RAG용으로는 gpt-4o-mini 사용 (더 저렴하고 토큰 제한이 큼)
            model = "gpt-4o-mini"  # RAG 응답 생성용
            
            # 토큰 제한 확인 (gpt-4o-mini는 128k context)
            max_tokens = 20000  # 더 안전한 제한
            if token_count > max_tokens:
                logger.warning(f"Prompt too long ({token_count} tokens), truncating to {max_tokens}")
                tokens = tokens[:max_tokens]
                prompt = self.tokenizer.decode(tokens)
                token_count = max_tokens
            
            logger.info(f"LLM request: {token_count} tokens, model: {model}")
            
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "당신은 도움이 되는 AI 어시스턴트입니다. 주어진 정보를 바탕으로 정확하고 유용한 답변을 제공합니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,  # 응답 토큰 수 증가
                temperature=0.7
            )
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise LLMQueryError(f"Failed to generate response: {str(e)}")
    
    async def query_stream(self, question: str, available_tools: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a streaming query against the LLM with available tools
        
        Args:
            question: User's question
            available_tools: List of available MCP tools in OpenAI format
            
        Yields:
            Dict with event type and data (not SSE formatted strings)
        """
        try:
            # 1단계: 의도 분류 및 도구 필터링
            filtered_tools = await self._filter_tools_by_intent(question, available_tools)
            
            # 2차 요청 - 스트리밍 모드
            logger.warning(f"🔧 LLM tools available: {len(filtered_tools)} tools (filtered from {len(available_tools)})")
            logger.warning(f"🔧 LLM question: {question[:100]}...")
            
            attempt = 0
            stream = None
            last_error: Exception | None = None
            while attempt < 2 and stream is None:
                try:
                    logger.warning(f"🔧 Creating OpenAI stream with {len(filtered_tools)} filtered tools")
                    stream = await self._client.responses.create(
                        model=settings.openai_model,
                        input=[
                            {"role": "system", "content": f"""You are an AI assistant specialized in web analysis and data processing.

CRITICAL: Always use tools when available. Execute the appropriate tools to perform real work; avoid generic explanations without using tools.

Available tools: {len(filtered_tools)} (filtered from {len(available_tools)} total)

Tool usage principles:
1) If a URL is present → use crawl4ai_scrape or crawl_urls_sequential
2) For system status → use health_check
3) For structured data conversion → use convert_to_json_format
4) For menu/DB queries → use menu_search
5) For HTML/Confluence content → use ari_extract_main_blocks and/or ari_markdown_to_json and/or convert_to_json_format

Response policy:
- After using tools, produce a concise, high-signal answer based on the results.
- IMPORTANT: Write all final answers to the user in Korean.
"""},
                            {"role": "user", "content": question}
                        ],
                        tools=filtered_tools,
                        stream=True
                    )
                    logger.warning(f"🔧 OpenAI stream created successfully")
                except Exception as e:
                    last_error = e
                    attempt += 1
                    logger.warning(f"Streaming create failed (attempt {attempt}): {e}")
            if stream is None and last_error is not None:
                raise last_error

            tool_calls = []
            current_call = None
            
            async for chunk in stream:
                # OpenAI Responses API 이벤트 처리
                event_type = type(chunk).__name__
                logger.warning(f"🔧 Event: {event_type}")
                
                # Function call 시작
                if event_type == 'ResponseOutputItemAddedEvent':
                    if hasattr(chunk, 'item') and hasattr(chunk.item, 'type') and chunk.item.type == 'function_call':
                        # chunk.item이 직접 도구 호출 정보를 가지고 있음
                        tool_call = {
                            'id': chunk.item.id,
                            'name': chunk.item.name,
                            'arguments': chunk.item.arguments or ''
                        }
                        tool_calls.append(tool_call)
                        current_call = tool_call
                        logger.warning(f"🔧 Function call started: {chunk.item.name}")
                
                # Function call arguments 수집
                elif event_type == 'ResponseFunctionCallArgumentsDeltaEvent':
                    if current_call and hasattr(chunk, 'delta'):
                        current_call['arguments'] += chunk.delta
                        logger.warning(f"🔧 Arguments delta: {chunk.delta[:20]}...")
                
                # Function call 완료
                elif event_type == 'ResponseFunctionCallArgumentsDoneEvent':
                    if current_call:
                        logger.warning(f"🔧 Function call completed: {current_call['name']}")
                        yield f"data: {json.dumps({'type': 'tool_call_delta', 'data': {'tool_calls': tool_calls}})}\n\n"
                
                # 전체 응답 완료
                elif event_type == 'ResponseCompletedEvent':
                    logger.warning(f"🔧 Response completed with {len(tool_calls)} tool calls")
                    break

            # Tool 호출이 있는 경우 완성된 tool_calls 반환
            if tool_calls:
                yield f"data: {json.dumps({'type': 'tool_calls_ready', 'data': {'tool_calls': tool_calls}})}\n\n"
                async for event in self._process_tool_calls_stream(question, tool_calls):
                    if isinstance(event, dict):
                        yield f"data: {json.dumps(event)}\n\n"
                    else:
                        yield event
            
            yield f"data: {json.dumps({'type': 'done', 'data': {}})}\n\n"
            
        except Exception as e:
            # 스트리밍 실패는 치명적이지 않음: 상태로 알리고 상위에서 폴백 진행
            logger.warning(f"Streaming LLM query failed, will fallback: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': f'LLM 연결 실패: {str(e)}'}})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'data': {}})}\n\n"
    
    async def _process_tool_calls(self, question: str, tool_calls: List[Any]) -> List[Any]:
        """Process tool calls and return next input for LLM"""
        next_input: List[Any] = [{"role": "user", "content": question}]
        
        for call in tool_calls:
            args = call.arguments
            if isinstance(args, str):
                args = json.loads(args)
            
            result = await mcp_service.call_tool(call.name, args)

            # 호출 자체를 메시지 배열에 추가
            next_input.append(call)
            # 대용량 데이터 도구들은 LLM에 요약된 정보만 전달
            if call.name == 'take_screenshot':
                result_str = str({
                    "success": True,
                    "message": "스크린샷이 성공적으로 촬영되었습니다",
                    "screenshot_captured": True
                })
                logger.info(f"Screenshot tool result simplified for LLM: original {len(str(result)):,} chars -> {len(result_str)} chars")
            elif call.name == 'crawl_webpage':
                # HTML 전체 대신 메타 정보만 전달
                try:
                    original_result = result.structured_content if hasattr(result, 'structured_content') else result.data
                    result_str = str({
                        "success": original_result.get("success", True),
                        "url": original_result.get("url", ""),
                        "title": original_result.get("title", ""),
                        "meta_description": original_result.get("meta_description", ""),
                        "content_length": original_result.get("content_length", 0),
                        "message": "웹페이지 크롤링이 완료되었습니다 (HTML 데이터는 LLM 분석에 불필요하므로 생략)"
                    })
                    logger.info(f"Crawl webpage result simplified for LLM: original {len(str(result)):,} chars -> {len(result_str)} chars")
                except Exception as e:
                    logger.warning(f"Failed to simplify crawl result: {e}")
                    result_str = str(result)  # 실패시 원본 사용
            else:
                # 다른 도구들의 결과 데이터 크기 제한 (OpenAI API 제한: 10MB)
                result_str = str(result)
                max_output_size = 8 * 1024 * 1024  # 8MB로 안전하게 제한
                
                if len(result_str) > max_output_size:
                    # 대용량 데이터는 요약해서 전달
                    truncated_result = {
                        "success": True,
                        "message": f"결과가 너무 커서 요약됨 (원본 크기: {len(result_str):,} 문자)",
                        "truncated": True,
                        "sample": result_str[:1000] + "..." if len(result_str) > 1000 else result_str
                    }
                    result_str = str(truncated_result)
                    logger.warning(f"Tool result truncated for {call.name}: {len(str(result)):,} -> {len(result_str):,} chars")
            
            # 실행 결과를 function_call_output 형식으로 추가
            next_input.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": result_str,
            })
        
        return next_input
    
    async def _handle_streaming_tool_calls(self, delta_tool_calls, tool_calls, current_call):
        """Handle streaming tool calls from delta"""
        for tool_call in delta_tool_calls:
            if tool_call.index == len(tool_calls):
                tool_calls.append({
                    'id': tool_call.id,
                    'name': tool_call.function.name if tool_call.function else '',
                    'arguments': tool_call.function.arguments if tool_call.function else ''
                })
                current_call = tool_calls[-1]
            elif current_call:
                if tool_call.function and tool_call.function.arguments:
                    current_call['arguments'] += tool_call.function.arguments
        return current_call
    
    async def _process_tool_calls_stream(self, question: str, tool_calls: List[Dict]) -> AsyncGenerator[str, None]:
        """Process tool calls in streaming mode"""
        yield f"data: {json.dumps({'type': 'tool_start', 'data': {'message': 'Tool 실행 중...'}})}\n\n"
        
        next_input: List[Any] = [{"role": "user", "content": question}]
        
        # 각 툴 호출 처리
        for call in tool_calls:
            try:
                args = json.loads(call['arguments']) if call['arguments'] else {}
                result = await mcp_service.call_tool(call['name'], args)
                
                # Tool 실행 결과를 스트림으로 전송 (원본 결과 전달)
                tool_message = f"Tool '{call['name']}' 실행 완료"
                yield f"data: {json.dumps({'type': 'tool_result', 'data': {'tool_name': call['name'], 'message': tool_message, 'result': result}})}\n\n"
                
                # 다음 요청을 위한 메시지 구성
                next_input.append({
                    "type": "function_call",
                    "call_id": call['id'],
                    "name": call['name'],
                    "arguments": call['arguments']
                })
                                # 대용량 데이터 도구들은 LLM에 요약된 정보만 전달
                if call['name'] == 'take_screenshot':
                    result_str = str({
                        "success": True,
                        "message": "스크린샷이 성공적으로 촬영되었습니다",
                        "screenshot_captured": True
                    })
                    logger.info(f"Screenshot tool result simplified for LLM: original {len(str(result)):,} chars -> {len(result_str)} chars")
                elif call['name'] == 'crawl_webpage':
                    # HTML 전체 대신 메타 정보만 전달
                    try:
                        original_result = result.structured_content if hasattr(result, 'structured_content') else result.data
                        result_str = str({
                            "success": original_result.get("success", True),
                            "url": original_result.get("url", ""),
                            "title": original_result.get("title", ""),
                            "meta_description": original_result.get("meta_description", ""),
                            "content_length": original_result.get("content_length", 0),
                            "message": "웹페이지 크롤링이 완료되었습니다 (HTML 데이터는 LLM 분석에 불필요하므로 생략)"
                        })
                        logger.info(f"Crawl webpage result simplified for LLM: original {len(str(result)):,} chars -> {len(result_str)} chars")
                    except Exception as e:
                        logger.warning(f"Failed to simplify crawl result: {e}")
                        result_str = str(result)  # 실패시 원본 사용
                else:
                    # 다른 도구들의 결과 데이터 크기 제한 (OpenAI API 제한: 10MB)
                    result_str = str(result)
                    max_output_size = 8 * 1024 * 1024  # 8MB로 안전하게 제한
                    
                    if len(result_str) > max_output_size:
                        # 대용량 데이터는 요약해서 전달
                        truncated_result = {
                            "success": True,
                            "message": f"결과가 너무 커서 요약됨 (원본 크기: {len(result_str):,} 문자)",
                            "truncated": True,
                            "sample": result_str[:1000] + "..." if len(result_str) > 1000 else result_str
                        }
                        result_str = str(truncated_result)
                        logger.warning(f"Tool result truncated for {call['name']}: {len(str(result)):,} -> {len(result_str):,} chars")
                
                next_input.append({
                    "type": "function_call_output", 
                    "call_id": call['id'],
                    "output": result_str
                })
                
            except Exception as tool_error:
                error_message = f'Tool 실행 오류: {str(tool_error)}'
                yield f"data: {json.dumps({'type': 'tool_error', 'data': {'tool_name': call['name'], 'error': error_message}})}\n\n"

        # 2차 호출 - 최종 답변 스트리밍
        final_stream = await self._client.responses.create(
            model=settings.openai_model,
            input=next_input,
            stream=True
        )
        
        async for chunk in final_stream:
            if hasattr(chunk, 'choices') and chunk.choices:
                choice = chunk.choices[0]
                if hasattr(choice, 'delta') and choice.delta and hasattr(choice.delta, 'content') and choice.delta.content:
                    yield f"data: {json.dumps({'type': 'final_content', 'data': {'content': choice.delta.content}})}\n\n"

# Global service instance
llm_service = LLMService()
