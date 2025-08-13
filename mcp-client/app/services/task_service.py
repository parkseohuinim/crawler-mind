"""Task management service for handling async crawling operations"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional, AsyncGenerator, Any, List
import logging
import json

from app.models import TaskStatus, CrawlingResult, TaskResult, ProcessingMode
from app.services.mcp_service import mcp_service
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class TaskService:
    """Service for managing crawling tasks"""
    
    def __init__(self):
        self.tasks: Dict[str, TaskResult] = {}
        self.task_streams: Dict[str, asyncio.Queue] = {}
        
    def create_task(self, url: str, mode: ProcessingMode) -> str:
        """Create a new crawling task"""
        task_id = str(uuid.uuid4())
        
        task_result = TaskResult(
            taskId=task_id,
            status=TaskStatus.PENDING,
            createdAt=datetime.now().isoformat()
        )
        
        self.tasks[task_id] = task_result
        self.task_streams[task_id] = asyncio.Queue()
        
        logger.info(f"✅ Task created: {task_id} for URL: {url} with mode: {mode}")
        logger.info(f"📊 Total tasks in memory: {len(self.tasks)}")
        logger.info(f"📊 Task streams in memory: {len(self.task_streams)}")
        
        # Start task processing in background
        asyncio.create_task(self._process_task(task_id, url, mode))
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskResult]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    async def get_task_stream(self, task_id: str) -> AsyncGenerator[str, None]:
        """Get SSE stream for task updates"""
        logger.info(f"🔍 SSE stream requested for task: {task_id}")
        logger.info(f"📊 Available tasks: {list(self.tasks.keys())}")
        logger.info(f"📊 Available streams: {list(self.task_streams.keys())}")
        
        if task_id not in self.task_streams:
            logger.error(f"❌ Task stream not found: {task_id}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Task not found'}})}\n\n"
            return
            
        # 초기 연결 확인 메시지 전송
        yield f"data: {json.dumps({'type': 'connected', 'data': {'message': 'Stream connected'}})}\n\n"
            
        queue = self.task_streams[task_id]
        
        try:
            while True:
                try:
                    # Wait for next update with timeout
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {message}\n\n"
                    
                    # Parse message to check if it's a completion signal
                    try:
                        msg_data = json.loads(message)
                        if msg_data.get('type') in ['final', 'complete', 'error']:
                            # Send final message and break
                            break
                    except:
                        pass
                    
                    # Check if task is completed
                    task = self.tasks.get(task_id)
                    if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        break
                        
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat', 'data': {}})}\n\n"
                    
                    # Check if task is completed during timeout
                    task = self.tasks.get(task_id)
                    if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        yield f"data: {json.dumps({'type': 'complete', 'data': {'message': '작업 완료'}})}\n\n"
                        break
                    
        except Exception as e:
            logger.error(f"Error in task stream {task_id}: {e}")
            try:
                yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
            except:
                pass
        finally:
            # Clean up stream
            logger.info(f"Cleaning up task stream: {task_id}")
            if task_id in self.task_streams:
                del self.task_streams[task_id]
    
    async def _process_task(self, task_id: str, url: str, mode: ProcessingMode):
        """Process crawling task"""
        try:
            # Update task status
            self.tasks[task_id].status = TaskStatus.RUNNING
            await self._send_update(task_id, 'status', {'message': '작업을 시작합니다...', 'status': 'active'})
            
            if mode == ProcessingMode.AUTO:
                # AI 자동 분석 모드 (스트리밍 실패 시 기본 플로우 폴백)
                result = await self._process_auto_mode(task_id, url)
            else:
                # 기본 크롤링 모드
                result = await self._process_basic_mode(task_id, url)
            
            # Update task with result
            self.tasks[task_id].result = result
            self.tasks[task_id].status = TaskStatus.COMPLETED
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            
            await self._send_update(task_id, 'final', result.model_dump() if result else {})
            
            # 스트림 완료 신호 전송
            await self._send_update(task_id, 'complete', {'message': '작업이 완료되었습니다'})
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            
            # Update task with error
            self.tasks[task_id].status = TaskStatus.FAILED
            self.tasks[task_id].error = str(e)
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            
            await self._send_update(task_id, 'error', {'message': str(e)})
    
    async def _process_auto_mode(self, task_id: str, url: str) -> CrawlingResult:
        """Process task using AI automatic mode"""
        try:
            # LLM에게 URL 분석 요청 (엄격 모드: 각 도구를 LLM이 직접 호출하도록 순차 강제)
            await self._send_update(task_id, 'status', {'message': 'AI가 도구 호출을 순차적으로 수행합니다...', 'status': 'active'})

            all_tools: List[Dict[str, Any]] = mcp_service.available_tools

            def filter_tools(name: str) -> List[Dict[str, Any]]:
                # available_tools 항목은 {'type':'function', 'name':..., 'parameters':...}
                return [t for t in all_tools if t.get('name') == name]

            tool_results: Dict[str, Any] = {}
            html_content: Optional[str] = None
            text_content: Optional[str] = None

            # 1) crawl_webpage (URL만 필요)
            await self._send_update(task_id, 'status', {'message': '웹페이지를 크롤링합니다 (LLM 호출)...', 'status': 'active'})
            cw_prompt = f"Call crawl_webpage for URL: {url}. Return a function call only."
            planned_calls: List[Dict[str, Any]] = []
            async for ev in llm_service.query_stream(cw_prompt, filter_tools('crawl_webpage')):
                if ev.get('type') == 'tool_calls_ready':
                    planned_calls = ev['data'].get('tool_calls', [])
                    break
            # 실행 (필요 인자 보강)
            crawl_args = {'url': url}
            crawl_res = await mcp_service.call_tool('crawl_webpage', crawl_args)
            tool_results['crawl_webpage'] = crawl_res
            # HTML 보관
            crawl_data = getattr(crawl_res, 'structured_content', None) or getattr(crawl_res, 'data', None) or crawl_res
            if isinstance(crawl_data, dict) and crawl_data.get('success'):
                html_content = crawl_data.get('html_content')

            # 2) extract_text_content (HTML은 내부에서 보강)
            await self._send_update(task_id, 'status', {'message': '텍스트를 추출합니다 (LLM 호출)...', 'status': 'active'})
            etc_prompt = "Call extract_text_content. Do not include the full HTML in arguments; use an empty placeholder."
            planned_calls = []
            async for ev in llm_service.query_stream(etc_prompt, filter_tools('extract_text_content')):
                if ev.get('type') == 'tool_calls_ready':
                    planned_calls = ev['data'].get('tool_calls', [])
                    break
            text_args = {'html_content': html_content or ''}
            text_res = await mcp_service.call_tool('extract_text_content', text_args)
            tool_results['extract_text_content'] = text_res
            text_data = getattr(text_res, 'structured_content', None) or getattr(text_res, 'data', None) or text_res
            if isinstance(text_data, dict) and text_data.get('success'):
                text_content = text_data.get('text_content')

            # 3) extract_links (HTML은 내부에서 보강)
            await self._send_update(task_id, 'status', {'message': '링크를 분석합니다 (LLM 호출)...', 'status': 'active'})
            el_prompt = "Call extract_links. Do not include the full HTML in arguments; use an empty placeholder."
            planned_calls = []
            async for ev in llm_service.query_stream(el_prompt, filter_tools('extract_links')):
                if ev.get('type') == 'tool_calls_ready':
                    planned_calls = ev['data'].get('tool_calls', [])
                    break
            links_args = {'html_content': html_content or '', 'base_url': url}
            links_res = await mcp_service.call_tool('extract_links', links_args)
            tool_results['extract_links'] = links_res

            # 4) take_screenshot (URL만 필요)
            await self._send_update(task_id, 'status', {'message': '스크린샷을 촬영합니다 (LLM 호출)...', 'status': 'active'})
            ss_prompt = f"Call take_screenshot for URL: {url}. Return a function call only."
            planned_calls = []
            async for ev in llm_service.query_stream(ss_prompt, filter_tools('take_screenshot')):
                if ev.get('type') == 'tool_calls_ready':
                    planned_calls = ev['data'].get('tool_calls', [])
                    break
            ss_args = {'url': url}
            ss_res = await mcp_service.call_tool('take_screenshot', ss_args)
            tool_results['take_screenshot'] = ss_res

            # 5) summarize_content (텍스트는 내부에서 보강)
            await self._send_update(task_id, 'status', {'message': '내용을 요약합니다 (LLM 호출)...', 'status': 'active'})
            sum_prompt = "Call summarize_content. Do not include the full text in arguments; use an empty placeholder."
            planned_calls = []
            async for ev in llm_service.query_stream(sum_prompt, filter_tools('summarize_content')):
                if ev.get('type') == 'tool_calls_ready':
                    planned_calls = ev['data'].get('tool_calls', [])
                    break
            sum_args = {'text_content': text_content or ''}
            sum_res = await mcp_service.call_tool('summarize_content', sum_args)
            tool_results['summarize_content'] = sum_res

            await self._send_update(task_id, 'status', {'message': 'AI 도구 호출 결과를 정리합니다...', 'status': 'active'})
            return self._build_result_from_llm_tools(tool_results, url)
            
        except Exception as e:
            logger.error(f"Auto mode processing failed: {e}")
            return CrawlingResult(error=str(e))
    
    async def _enhance_llm_results(self, task_id: str, url: str, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """LLM이 선택한 도구 결과에 누락된 필수 도구들을 보완"""
        enhanced_results = tool_results.copy()
        
        # crawl_webpage가 있어야 다른 도구들을 실행할 수 있음
        if 'crawl_webpage' not in enhanced_results:
            logger.warning(f"🔧 Missing crawl_webpage, executing...")
            await self._send_update(task_id, 'status', {'message': '웹페이지를 크롤링하고 있습니다...', 'status': 'active'})
            crawl_result = await mcp_service.call_tool('crawl_webpage', {'url': url})
            enhanced_results['crawl_webpage'] = crawl_result
        
        # HTML 데이터 추출
        html_content = None
        crawl_result = enhanced_results.get('crawl_webpage')
        if crawl_result:
            if hasattr(crawl_result, 'structured_content'):
                crawl_data = crawl_result.structured_content
            elif hasattr(crawl_result, 'data'):
                crawl_data = crawl_result.data
            else:
                crawl_data = crawl_result
            
            if isinstance(crawl_data, dict) and crawl_data.get('success'):
                html_content = crawl_data.get('html')
        
        # 텍스트 추출이 누락되었다면 실행
        if 'extract_text_content' not in enhanced_results and html_content:
            logger.warning(f"🔧 Missing extract_text_content, executing...")
            await self._send_update(task_id, 'status', {'message': '텍스트를 추출하고 있습니다...', 'status': 'active'})
            text_result = await mcp_service.call_tool('extract_text_content', {'html': html_content})
            enhanced_results['extract_text_content'] = text_result
        
        # 링크 추출이 누락되었다면 실행
        if 'extract_links' not in enhanced_results and html_content:
            logger.warning(f"🔧 Missing extract_links, executing...")
            await self._send_update(task_id, 'status', {'message': '링크를 분석하고 있습니다...', 'status': 'active'})
            links_result = await mcp_service.call_tool('extract_links', {'html': html_content})
            enhanced_results['extract_links'] = links_result
        
        # 요약이 누락되었다면 실행
        text_content = None
        if 'extract_text_content' in enhanced_results:
            text_result = enhanced_results['extract_text_content']
            if hasattr(text_result, 'structured_content'):
                text_data = text_result.structured_content
            elif hasattr(text_result, 'data'):
                text_data = text_result.data
            else:
                text_data = text_result
            
            if isinstance(text_data, dict) and text_data.get('success'):
                text_content = text_data.get('text')
        
        if 'summarize_content' not in enhanced_results and text_content:
            logger.warning(f"🔧 Missing summarize_content, executing...")
            await self._send_update(task_id, 'status', {'message': '내용을 요약하고 있습니다...', 'status': 'active'})
            summary_result = await mcp_service.call_tool('summarize_content', {'text': text_content})
            enhanced_results['summarize_content'] = summary_result
        
        # 스크린샷이 누락되었다면 실행
        if 'take_screenshot' not in enhanced_results:
            logger.warning(f"🔧 Missing take_screenshot, executing...")
            await self._send_update(task_id, 'status', {'message': '스크린샷을 촬영하고 있습니다...', 'status': 'active'})
            screenshot_result = await mcp_service.call_tool('take_screenshot', {'url': url})
            enhanced_results['take_screenshot'] = screenshot_result
        
        logger.warning(f"🔧 Enhanced results: {list(enhanced_results.keys())}")
        return enhanced_results
    
    def _build_result_from_llm_tools(self, tool_results: Dict[str, Any], url: str) -> CrawlingResult:
        """LLM이 실행한 도구 결과들을 조합하여 CrawlingResult 생성"""
        result_data = {}
        
        # crawl_webpage 결과 처리
        if 'crawl_webpage' in tool_results:
            crawl_result = tool_results['crawl_webpage']
            if hasattr(crawl_result, 'structured_content'):
                crawl_data = crawl_result.structured_content
            elif hasattr(crawl_result, 'data'):
                crawl_data = crawl_result.data
            else:
                crawl_data = crawl_result
            
            if isinstance(crawl_data, dict) and crawl_data.get('success'):
                result_data['title'] = crawl_data.get('title')
        
        # extract_text_content 결과 처리
        if 'extract_text_content' in tool_results:
            text_result = tool_results['extract_text_content']
            if hasattr(text_result, 'structured_content'):
                text_data = text_result.structured_content
            elif hasattr(text_result, 'data'):
                text_data = text_result.data
            else:
                text_data = text_result
                
            if isinstance(text_data, dict) and text_data.get('success'):
                result_data['textLength'] = text_data.get('text_length', 0)
        
        # extract_links 결과 처리
        if 'extract_links' in tool_results:
            links_result = tool_results['extract_links']
            if hasattr(links_result, 'structured_content'):
                links_data = links_result.structured_content
            elif hasattr(links_result, 'data'):
                links_data = links_result.data
            else:
                links_data = links_result
                
            if isinstance(links_data, dict) and links_data.get('success'):
                links_list = links_data.get('links', [])
                result_data['linkCount'] = len(links_list)
                result_data['links'] = [link['url'] for link in links_list[:20] if isinstance(link, dict) and 'url' in link]
        
        # summarize_content 결과 처리
        if 'summarize_content' in tool_results:
            summary_result = tool_results['summarize_content']
            if hasattr(summary_result, 'structured_content'):
                summary_data = summary_result.structured_content
            elif hasattr(summary_result, 'data'):
                summary_data = summary_result.data
            else:
                summary_data = summary_result
                
            if isinstance(summary_data, dict) and summary_data.get('success'):
                result_data['summary'] = summary_data.get('summary')
        
        # take_screenshot 결과 처리
        if 'take_screenshot' in tool_results:
            screenshot_result = tool_results['take_screenshot']
            if hasattr(screenshot_result, 'structured_content'):
                screenshot_data = screenshot_result.structured_content
            elif hasattr(screenshot_result, 'data'):
                screenshot_data = screenshot_result.data
            else:
                screenshot_data = screenshot_result
                
            if isinstance(screenshot_data, dict) and screenshot_data.get('success'):
                result_data['screenshot'] = screenshot_data.get('screenshot')
        
        # 누락된 필드에 기본값 설정 (LLM이 일부 도구만 선택한 경우)
        if 'textLength' not in result_data:
            result_data['textLength'] = 0
        if 'linkCount' not in result_data:
            result_data['linkCount'] = 0
        if 'links' not in result_data:
            result_data['links'] = []
        
        return CrawlingResult(**result_data)
    
    async def _process_basic_mode(self, task_id: str, url: str) -> CrawlingResult:
        """Process task using basic crawling mode"""
        try:
            result_data = {}
            
            # 1. 웹페이지 크롤링
            await self._send_update(task_id, 'status', {'message': '웹페이지를 크롤링하고 있습니다...', 'status': 'active'})
            
            if not mcp_service.is_connected:
                raise Exception("MCP 서버에 연결되지 않았습니다")
            
            # crawl_webpage 도구 호출
            crawl_result = await mcp_service.call_tool("crawl_webpage", {"url": url})
            
            # MCP 도구 결과는 CallToolResult 객체이므로 .data 또는 .structured_content 사용
            crawl_data = crawl_result.structured_content if hasattr(crawl_result, 'structured_content') else crawl_result.data
            
            if not crawl_data.get("success"):
                raise Exception(f"크롤링 실패: {crawl_data.get('error', '알 수 없는 오류')}")
            
            result_data["title"] = crawl_data.get("title")
            html_content = crawl_data.get("html_content", "")
            
            # 2. 텍스트 추출
            await self._send_update(task_id, 'status', {'message': '텍스트를 추출하고 있습니다...', 'status': 'active'})
            
            text_result = await mcp_service.call_tool("extract_text_content", {"html_content": html_content})
            text_data = text_result.structured_content if hasattr(text_result, 'structured_content') else text_result.data
            
            if text_data.get("success"):
                result_data["textLength"] = text_data.get("text_length", 0)
                text_content = text_data.get("text_content", "")
            else:
                text_content = ""
            
            # 3. 링크 추출
            await self._send_update(task_id, 'status', {'message': '링크를 분석하고 있습니다...', 'status': 'active'})
            
            links_result = await mcp_service.call_tool("extract_links", {"html_content": html_content, "base_url": url})
            links_data_result = links_result.structured_content if hasattr(links_result, 'structured_content') else links_result.data
            
            if links_data_result.get("success"):
                links_data = links_data_result.get("links", [])
                result_data["linkCount"] = len(links_data)
                result_data["links"] = [link["url"] for link in links_data[:20]]  # 최대 20개만
            
            # 4. 요약 생성
            if text_content:
                await self._send_update(task_id, 'status', {'message': '내용을 요약하고 있습니다...', 'status': 'active'})
                
                summary_result = await mcp_service.call_tool("summarize_content", {"text_content": text_content})
                summary_data = summary_result.structured_content if hasattr(summary_result, 'structured_content') else summary_result.data
                
                if summary_data.get("success"):
                    result_data["summary"] = summary_data.get("summary")
            
            # 5. 스크린샷 (선택적)
            try:
                await self._send_update(task_id, 'status', {'message': '스크린샷을 촬영하고 있습니다...', 'status': 'active'})
                
                screenshot_result = await mcp_service.call_tool("take_screenshot", {"url": url})
                screenshot_data = screenshot_result.structured_content if hasattr(screenshot_result, 'structured_content') else screenshot_result.data
                
                if screenshot_data.get("success"):
                    result_data["screenshot"] = screenshot_data.get("screenshot")
                    
            except Exception as e:
                logger.warning(f"Screenshot failed: {e}")
                # 스크린샷 실패는 전체 작업 실패로 간주하지 않음
            
            await self._send_update(task_id, 'status', {'message': '분석이 완료되었습니다!', 'status': 'completed'})
            
            return CrawlingResult(**result_data)
            
        except Exception as e:
            logger.error(f"Basic mode processing failed: {e}")
            return CrawlingResult(error=str(e))
    
    async def _send_update(self, task_id: str, event_type: str, data: dict):
        """Send update to task stream"""
        if task_id in self.task_streams:
            message = json.dumps({
                'type': event_type,
                'data': data,
                'timestamp': datetime.now().isoformat()
            })
            
            try:
                await self.task_streams[task_id].put(message)
            except Exception as e:
                logger.error(f"Failed to send update for task {task_id}: {e}")

# Global task service instance
task_service = TaskService()
