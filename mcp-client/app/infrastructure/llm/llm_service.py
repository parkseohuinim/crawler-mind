"""LLM Service - Handles OpenAI API interactions"""
from typing import List, Dict, Any, AsyncGenerator
import json
import logging
import tiktoken
from openai import AsyncOpenAI
from app.config import settings
from app.infrastructure.mcp.mcp_service import mcp_service
from app.shared.exceptions.base import LLMQueryError

logger = logging.getLogger(__name__)

class LLMService:
    """Service class for managing LLM interactions"""
    
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
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
            filtered_tools = self._filter_tools_by_intent(question, available_tools)
            
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
3) For text summarization/clean-up → use summarize_content
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
    
    def _filter_tools_by_intent(self, question: str, available_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        질문의 의도를 분석하여 관련된 도구만 필터링
        """
        question_lower = question.lower()
        
        # 의도별 키워드 매핑
        intent_keywords = {
            'web_crawling': ['크롤링', 'crawl', 'url', '웹사이트', '웹페이지', '스크래핑', 'scrape'],
            'system_status': ['상태', 'status', 'health', '서버', '통계', 'statistics'],
            'text_analysis': ['요약', 'summarize', '분석', 'analyze', '추출', 'extract', '텍스트'],
            'html_processing': ['html', '파일', 'file', 'confluence', '업로드', 'upload', 'ari'],
            'db_query': ['메뉴', 'menu', '링크', 'link', '매니저', 'manager', '담당자', '조회', 'query'],
            'rag_query': ['rag', '검색', 'search', '문서', 'document', '지식', 'knowledge']
        }
        
        # 의도 감지
        detected_intents = []
        for intent, keywords in intent_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                detected_intents.append(intent)
        
        # 의도별 도구 매핑
        tool_mapping = {
            'web_crawling': ['crawl4ai_scrape', 'crawl_urls_sequential'],
            'system_status': ['health_check'],
            'text_analysis': ['summarize_content'],
            'html_processing': ['ari_extract_main_blocks', 'ari_markdown_to_json', 'convert_to_json_format'],
            'db_query': ['menu_search'],
            'rag_query': []
        }
        
        # 관련 도구들 수집
        relevant_tools = []
        for intent in detected_intents:
            relevant_tools.extend(tool_mapping.get(intent, []))
        
        # 기본 도구들 (항상 포함)
        essential_tools = ['health_check', 'crawl4ai_scrape', 'summarize_content']
        relevant_tools.extend(essential_tools)
        
        # 중복 제거
        relevant_tools = list(set(relevant_tools))
        
        # 도구 필터링
        filtered_tools = []
        for tool in available_tools:
            tool_name = tool.get('function', {}).get('name', '')
            if tool_name in relevant_tools:
                filtered_tools.append(tool)
        
        logger.info(f"🔍 의도 분류: {detected_intents}")
        logger.info(f"🎯 필터링된 도구: {[t.get('function', {}).get('name', '') for t in filtered_tools]}")
        
        return filtered_tools if filtered_tools else available_tools[:10]  # 최대 10개로 제한
    
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
            filtered_tools = self._filter_tools_by_intent(question, available_tools)
            
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
3) For text summarization/clean-up → use summarize_content
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
