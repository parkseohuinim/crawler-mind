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
        
        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            # Fallback to cl100k_base encoding
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    async def query(self, question: str, available_tools: List[Dict[str, Any]]) -> str:
        """
        Execute a query against the LLM with available tools
        
        Args:
            question: User's question
            available_tools: List of available MCP tools in OpenAI format
            
        Returns:
            LLM response as string
        """
        try:
            # 1차 요청
            resp = await self._client.responses.create(
                model=settings.openai_model,
                input=[{"role": "user", "content": question}],
                tools=available_tools,
            )

            # Tool 호출이 없을 때
            tool_calls = [o for o in resp.output if getattr(o, "type", "") == "function_call"]
            if not tool_calls:
                return resp.output_text

            # Tool 호출 처리
            next_input = await self._process_tool_calls(question, tool_calls)

            # 2차 호출 -> 최종 답변
            final = await self._client.responses.create(
                model=settings.openai_model,
                input=next_input,
            )
            return final.output_text
        
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise LLMQueryError(f"LLM 쿼리 실행 중 오류: {str(e)}")
    
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
            # 1차 요청 - 스트리밍 모드 (간단 재시도)
            logger.warning(f"🔧 LLM tools available: {len(available_tools)} tools")
            logger.warning(f"🔧 LLM question: {question[:100]}...")
            
            attempt = 0
            stream = None
            last_error: Exception | None = None
            while attempt < 2 and stream is None:
                try:
                    logger.warning(f"🔧 Creating OpenAI stream with {len(available_tools)} tools")
                    stream = await self._client.responses.create(
                        model=settings.openai_model,
                        input=[
                            {"role": "system", "content": "You are a web analysis assistant. You MUST use ALL tools that are explicitly mentioned in the user's request. Complete each step in the exact order specified. Do not stop until you have used every requested tool. If a tool fails, still continue with the remaining tools."},
                            {"role": "user", "content": question}
                        ],
                        tools=available_tools,
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
                        yield {'type': 'tool_call_delta', 'data': {'tool_calls': tool_calls}}
                
                # 전체 응답 완료
                elif event_type == 'ResponseCompletedEvent':
                    logger.warning(f"🔧 Response completed with {len(tool_calls)} tool calls")
                    break

            # Tool 호출이 있는 경우 완성된 tool_calls 반환
            if tool_calls:
                yield {'type': 'tool_calls_ready', 'data': {'tool_calls': tool_calls}}
                async for event in self._process_tool_calls_stream(question, tool_calls):
                    yield event
            
            yield {'type': 'done', 'data': {}}
            
        except Exception as e:
            # 스트리밍 실패는 치명적이지 않음: 상태로 알리고 상위에서 폴백 진행
            logger.warning(f"Streaming LLM query failed, will fallback: {e}")
            yield {'type': 'error', 'data': {'message': f'LLM 연결 실패: {str(e)}'}}
            yield {'type': 'done', 'data': {}}
    
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
    
    async def _process_tool_calls_stream(self, question: str, tool_calls: List[Dict]) -> AsyncGenerator[Dict[str, Any], None]:
        """Process tool calls in streaming mode"""
        yield {'type': 'tool_start', 'data': {'message': 'Tool 실행 중...'}}
        
        next_input: List[Any] = [{"role": "user", "content": question}]
        
        # 각 툴 호출 처리
        for call in tool_calls:
            try:
                args = json.loads(call['arguments']) if call['arguments'] else {}
                result = await mcp_service.call_tool(call['name'], args)
                
                # Tool 실행 결과를 스트림으로 전송 (원본 결과 전달)
                tool_message = f"Tool '{call['name']}' 실행 완료"
                yield {'type': 'tool_result', 'data': {'tool_name': call['name'], 'message': tool_message, 'result': result}}
                
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
                yield {'type': 'tool_error', 'data': {'tool_name': call['name'], 'error': error_message}}

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
                    yield {'type': 'final_content', 'data': {'content': choice.delta.content}}

# Global service instance
llm_service = LLMService()
