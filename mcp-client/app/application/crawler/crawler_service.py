"""Crawler Application Service - orchestrates crawling operations"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional, AsyncGenerator, Any, List
import logging
import json

from app.models import TaskStatus, CrawlingResult, TaskResult, ProcessingMode
from app.domains.crawler.entities.task import Task
from app.domains.crawler.entities.crawling_result import CrawlingResult as DomainCrawlingResult
from app.infrastructure.mcp.mcp_service import mcp_service
from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)

class CrawlerApplicationService:
    """Application service for managing crawling operations"""
    
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
                # AI 자동 분석 모드
                result = await self._process_auto_mode(task_id, url)
            else:
                # 기본 크롤링 모드
                result = await self._process_basic_mode(task_id, url)
            
            # Update task with result
            self.tasks[task_id].result = result
            self.tasks[task_id].status = TaskStatus.COMPLETED
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            
            await self._send_update(task_id, 'final', result.model_dump() if result else {})
            await self._send_update(task_id, 'complete', {'message': '작업이 완료되었습니다'})
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            
            # Update task with error
            self.tasks[task_id].status = TaskStatus.FAILED
            self.tasks[task_id].error = str(e)
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            
            await self._send_update(task_id, 'error', {'message': str(e)})
    
    async def _process_auto_mode(self, task_id: str, url: str) -> CrawlingResult:
        """Process task using AI automatic mode - programmatic tools with AI analysis"""
        try:
            await self._send_update(task_id, 'status', {'message': 'AI가 웹 분석을 시작합니다...', 'status': 'active'})
            
            # Step 1: 프로그래밍적으로 모든 도구 실행 (확실한 데이터 수집)
            tool_results = {}
            
            # 1. Crawl webpage
            await self._send_update(task_id, 'status', {'message': '웹페이지를 크롤링하고 있습니다...', 'status': 'active'})
            logger.warning(f"[AUTO MODE] Starting crawl_webpage for {url}")
            try:
                crawl_result = await mcp_service.call_tool("crawl_webpage", {"url": url})
                tool_results['crawl_webpage'] = crawl_result
                logger.warning(f"[AUTO MODE] crawl_webpage completed - result type: {type(crawl_result)}")
                await self._send_update(task_id, 'status', {'message': 'crawl_webpage 도구 실행 완료', 'status': 'active'})
            except Exception as e:
                logger.error(f"[AUTO MODE] Crawl webpage failed: {e}")
                return await self._process_basic_mode(task_id, url)
            
            # Get HTML content for subsequent tools
            html_content = None
            if hasattr(crawl_result, 'structured_content'):
                html_content = crawl_result.structured_content.get('html_content')
            elif hasattr(crawl_result, 'data'):
                html_content = crawl_result.data.get('html_content')
            else:
                html_content = crawl_result.get('html_content') if isinstance(crawl_result, dict) else None
            
            if not html_content:
                logger.warning("[AUTO MODE] No HTML content obtained, falling back to basic mode")
                return await self._process_basic_mode(task_id, url)
            
            logger.warning(f"[AUTO MODE] HTML content obtained: {len(html_content)} characters")
            
            # 2. Extract text content
            await self._send_update(task_id, 'status', {'message': '텍스트를 추출하고 있습니다...', 'status': 'active'})
            logger.warning(f"[AUTO MODE] Starting extract_text_content")
            try:
                text_result = await mcp_service.call_tool("extract_text_content", {"html_content": html_content})
                tool_results['extract_text_content'] = text_result
                logger.warning(f"[AUTO MODE] extract_text_content completed")
                await self._send_update(task_id, 'status', {'message': 'extract_text_content 도구 실행 완료', 'status': 'active'})
            except Exception as e:
                logger.warning(f"[AUTO MODE] Extract text failed: {e}")
            
            # 3. Extract links
            await self._send_update(task_id, 'status', {'message': '링크를 추출하고 있습니다...', 'status': 'active'})
            logger.warning(f"[AUTO MODE] Starting extract_links")
            try:
                links_result = await mcp_service.call_tool("extract_links", {"html_content": html_content, "base_url": url})
                tool_results['extract_links'] = links_result
                logger.warning(f"[AUTO MODE] extract_links completed")
                await self._send_update(task_id, 'status', {'message': 'extract_links 도구 실행 완료', 'status': 'active'})
            except Exception as e:
                logger.warning(f"[AUTO MODE] Extract links failed: {e}")
            
            # 4. Take screenshot first (for AI analysis)
            await self._send_update(task_id, 'status', {'message': '스크린샷을 촬영하고 있습니다...', 'status': 'active'})
            logger.warning(f"[AUTO MODE] Starting take_screenshot for {url}")
            try:
                screenshot_result = await mcp_service.call_tool("take_screenshot", {"url": url})
                tool_results['take_screenshot'] = screenshot_result
                logger.warning(f"[AUTO MODE] take_screenshot completed")
                await self._send_update(task_id, 'status', {'message': 'take_screenshot 도구 실행 완료', 'status': 'active'})
            except Exception as e:
                logger.warning(f"[AUTO MODE] Take screenshot failed: {e}")
            
            # Step 2: AI 분석 및 요약 생성
            text_content = None
            if 'extract_text_content' in tool_results:
                text_result = tool_results['extract_text_content']
                if hasattr(text_result, 'structured_content'):
                    text_content = text_result.structured_content.get('text_content')
                elif hasattr(text_result, 'data'):
                    text_content = text_result.data.get('text_content')
                else:
                    text_content = text_result.get('text_content') if isinstance(text_result, dict) else None
            
            if text_content:
                await self._send_update(task_id, 'status', {'message': 'AI가 내용을 분석하고 있습니다...', 'status': 'active'})
                logger.warning(f"[AUTO MODE] Starting AI analysis with {len(text_content)} characters")
                
                # AI에게 웹페이지 분석 및 요약 요청
                analysis_result = await self._analyze_with_ai(url, text_content, tool_results)
                if analysis_result:
                    tool_results['ai_analysis'] = analysis_result
                    logger.warning(f"[AUTO MODE] AI analysis completed")
                    await self._send_update(task_id, 'status', {'message': 'AI 분석 완료', 'status': 'active'})
                else:
                    # AI 분석 실패시 기본 요약 사용
                    logger.warning(f"[AUTO MODE] AI analysis failed, using basic summarization")
                    try:
                        summary_result = await mcp_service.call_tool("summarize_content", {"text_content": text_content})
                        tool_results['summarize_content'] = summary_result
                    except Exception as e:
                        logger.warning(f"[AUTO MODE] Basic summarization failed: {e}")
            else:
                logger.warning(f"[AUTO MODE] No text content available for AI analysis")
            
            # Step 3: 결과 구성
            logger.warning(f"[AUTO MODE] Building result from {len(tool_results)} tools: {list(tool_results.keys())}")
            result = self._build_result_from_tools(tool_results, url)
            logger.warning(f"[AUTO MODE] Final result - textLength: {result.textLength}, linkCount: {result.linkCount}")
            await self._send_update(task_id, 'status', {'message': 'AI 분석이 완료되었습니다!', 'status': 'completed'})
            return result
            
        except Exception as e:
            logger.error(f"Auto mode processing failed: {e}")
            # Fallback to basic mode
            return await self._process_basic_mode(task_id, url)
    
    async def _process_basic_mode(self, task_id: str, url: str) -> CrawlingResult:
        """Process task using basic crawling mode"""
        try:
            result_data = {}
            
            # 1. 웹페이지 크롤링
            await self._send_update(task_id, 'status', {'message': '웹페이지를 크롤링하고 있습니다...', 'status': 'active'})
            
            if not mcp_service.is_connected:
                raise Exception("MCP 서버에 연결되지 않았습니다")
            
            crawl_result = await mcp_service.call_tool("crawl_webpage", {"url": url})
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
                result_data["links"] = [link["url"] for link in links_data[:20]]
            
            # 4. 요약 생성
            if text_content:
                await self._send_update(task_id, 'status', {'message': '내용을 요약하고 있습니다...', 'status': 'active'})
                
                summary_result = await mcp_service.call_tool("summarize_content", {"text_content": text_content})
                summary_data = summary_result.structured_content if hasattr(summary_result, 'structured_content') else summary_result.data
                
                if summary_data.get("success"):
                    result_data["summary"] = summary_data.get("summary")
            
            # 5. 스크린샷
            try:
                await self._send_update(task_id, 'status', {'message': '스크린샷을 촬영하고 있습니다...', 'status': 'active'})
                
                screenshot_result = await mcp_service.call_tool("take_screenshot", {"url": url})
                screenshot_data = screenshot_result.structured_content if hasattr(screenshot_result, 'structured_content') else screenshot_result.data
                
                if screenshot_data.get("success"):
                    result_data["screenshot"] = screenshot_data.get("screenshot")
                    
            except Exception as e:
                logger.warning(f"Screenshot failed: {e}")
            
            await self._send_update(task_id, 'status', {'message': '분석이 완료되었습니다!', 'status': 'completed'})
            
            return CrawlingResult(**result_data)
            
        except Exception as e:
            logger.error(f"Basic mode processing failed: {e}")
            return CrawlingResult(error=str(e))
    
    def _build_result_from_tools(self, tool_results: Dict[str, Any], url: str) -> CrawlingResult:
        """Build CrawlingResult from tool execution results"""
        result_data = {}
        
        logger.warning(f"[BUILD] Building result from {len(tool_results)} tool results: {list(tool_results.keys())}")
        
        # Process each tool result
        for tool_name, result in tool_results.items():
            logger.warning(f"[BUILD] Processing tool: {tool_name}")
            
            if hasattr(result, 'structured_content'):
                data = result.structured_content
                logger.warning(f"[BUILD] Using structured_content for {tool_name}")
            elif hasattr(result, 'data'):
                data = result.data
                logger.warning(f"[BUILD] Using data for {tool_name}")
            else:
                data = result
                logger.warning(f"[BUILD] Using direct result for {tool_name}")
            
            logger.warning(f"[BUILD] Data type for {tool_name}: {type(data)}, success: {data.get('success') if isinstance(data, dict) else 'not dict'}")
            
            if not isinstance(data, dict) or not data.get('success'):
                logger.warning(f"[BUILD] Skipping {tool_name} - not dict or not successful")
                continue
            
            if tool_name == 'crawl_webpage':
                title = data.get('title')
                result_data['title'] = title
                logger.warning(f"[BUILD] crawl_webpage - title: {title}")
            elif tool_name == 'extract_text_content':
                text_length = data.get('text_length', 0)
                result_data['textLength'] = text_length
                logger.warning(f"[BUILD] extract_text_content - textLength: {text_length}")
            elif tool_name == 'extract_links':
                links = data.get('links', [])
                result_data['linkCount'] = len(links)
                result_data['links'] = [link['url'] for link in links[:20] if isinstance(link, dict) and 'url' in link]
                logger.warning(f"[BUILD] extract_links - linkCount: {len(links)}")
            elif tool_name == 'summarize_content':
                summary = data.get('summary')
                result_data['summary'] = summary
                logger.warning(f"[BUILD] summarize_content - summary length: {len(summary) if summary else 0}")
            elif tool_name == 'ai_analysis':
                # AI 분석 결과 처리
                analysis = data.get('analysis', '')
                summary = data.get('summary', '')
                result_data['summary'] = summary or analysis
                result_data['ai_analysis'] = analysis
                logger.warning(f"[BUILD] ai_analysis - analysis length: {len(analysis) if analysis else 0}")
            elif tool_name == 'take_screenshot':
                screenshot = data.get('screenshot')
                result_data['screenshot'] = screenshot
                logger.warning(f"[BUILD] take_screenshot - screenshot size: {len(screenshot) if screenshot else 0} chars")
        
        # Set defaults for missing fields
        result_data.setdefault('textLength', 0)
        result_data.setdefault('linkCount', 0)
        result_data.setdefault('links', [])
        
        logger.warning(f"[BUILD] Final result_data: textLength={result_data.get('textLength')}, linkCount={result_data.get('linkCount')}, title='{result_data.get('title', 'N/A')}'")
        
        return CrawlingResult(**result_data)
    
    async def _analyze_with_ai(self, url: str, text_content: str, tool_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use AI to analyze the webpage content and generate insights"""
        try:
            # 링크 정보 준비
            links_info = ""
            if 'extract_links' in tool_results:
                links_result = tool_results['extract_links']
                if hasattr(links_result, 'structured_content'):
                    links_data = links_result.structured_content.get('links', [])
                elif hasattr(links_result, 'data'):
                    links_data = links_result.data.get('links', [])
                else:
                    links_data = links_result.get('links', []) if isinstance(links_result, dict) else []
                
                if links_data:
                    links_info = f"주요 링크들: {', '.join([link.get('text', link.get('url', ''))[:50] for link in links_data[:10]])}"
            
            # 페이지 정보 준비
            page_info = ""
            if 'crawl_webpage' in tool_results:
                crawl_result = tool_results['crawl_webpage']
                if hasattr(crawl_result, 'structured_content'):
                    title = crawl_result.structured_content.get('title', '')
                elif hasattr(crawl_result, 'data'):
                    title = crawl_result.data.get('title', '')
                else:
                    title = crawl_result.get('title', '') if isinstance(crawl_result, dict) else ''
                
                if title:
                    page_info = f"페이지 제목: {title}"
            
            # AI 분석 요청
            analysis_prompt = f"""다음 웹페이지를 분석하고 한국어로 요약해주세요:

URL: {url}
{page_info}
{links_info}

페이지 내용:
{text_content[:3000]}{'...' if len(text_content) > 3000 else ''}

다음 형식으로 분석 결과를 제공해주세요:
1. 페이지의 주요 목적과 내용 (100자 이내)
2. 핵심 키워드 3-5개
3. 사용자에게 유용한 정보나 특징

간결하고 실용적인 분석을 제공해주세요."""
            
            # LLM 호출 (도구 없이 순수 텍스트 분석)
            response = await llm_service.query(analysis_prompt, [])
            
            if response and len(response.strip()) > 10:
                return {
                    'success': True,
                    'analysis': response.strip(),
                    'analysis_type': 'ai_generated',
                    'summary': response.strip()[:500]  # 첫 500자를 요약으로 사용
                }
            else:
                return None
                
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
            return None
    
    def _create_llm_question(self, url: str, missing_tools: List[str], attempt: int) -> str:
        """Create LLM question with strong emphasis on required tools"""
        if attempt == 0:
            # 첫 번째 시도: 정중한 요청
            return f"""Please analyze the website at {url}. You MUST use ALL of these tools in order:
{', '.join(missing_tools)}

IMPORTANT: Do not skip any tools. Each tool provides essential data for complete analysis."""
        
        elif attempt == 1:
            # 두 번째 시도: 더 강한 요구
            return f"""CRITICAL: You failed to use all required tools. You MUST use these remaining tools:
{', '.join(missing_tools)}

URL: {url}

This is mandatory. Do not provide text responses - only use the specified tools."""
        
        else:
            # 세 번째 시도: 최후 경고
            return f"""FINAL ATTEMPT: Use these tools immediately or the task will fail:
{', '.join(missing_tools)}

URL: {url}

NO TEXT RESPONSES. TOOLS ONLY."""
    
    async def _fill_missing_tools(self, task_id: str, url: str, missing_tools: List[str], tool_results: Dict[str, Any]):
        """Fill missing tools programmatically"""
        # HTML content 먼저 확보
        html_content = None
        if 'crawl_webpage' in tool_results:
            crawl_result = tool_results['crawl_webpage']
            if hasattr(crawl_result, 'structured_content'):
                html_content = crawl_result.structured_content.get('html_content')
            elif hasattr(crawl_result, 'data'):
                html_content = crawl_result.data.get('html_content')
            else:
                html_content = crawl_result.get('html_content') if isinstance(crawl_result, dict) else None
        
        # 누락된 도구들 실행
        for tool_name in missing_tools:
            try:
                await self._send_update(task_id, 'status', {
                    'message': f'{tool_name} 도구 실행 중 (보완)',
                    'status': 'active'
                })
                
                if tool_name == 'crawl_webpage':
                    result = await mcp_service.call_tool("crawl_webpage", {"url": url})
                elif tool_name == 'extract_text_content' and html_content:
                    result = await mcp_service.call_tool("extract_text_content", {"html_content": html_content})
                elif tool_name == 'extract_links' and html_content:
                    result = await mcp_service.call_tool("extract_links", {"html_content": html_content, "base_url": url})
                elif tool_name == 'summarize_content':
                    # 텍스트 콘텐츠 먼저 확보
                    text_content = None
                    if 'extract_text_content' in tool_results:
                        text_result = tool_results['extract_text_content']
                        if hasattr(text_result, 'structured_content'):
                            text_content = text_result.structured_content.get('text_content')
                        elif hasattr(text_result, 'data'):
                            text_content = text_result.data.get('text_content')
                    if text_content:
                        result = await mcp_service.call_tool("summarize_content", {"text_content": text_content})
                    else:
                        continue
                elif tool_name == 'take_screenshot':
                    result = await mcp_service.call_tool("take_screenshot", {"url": url})
                else:
                    continue
                
                tool_results[tool_name] = result
                logger.warning(f"🔧 [AUTO MODE] Filled missing tool: {tool_name}")
                
            except Exception as e:
                logger.warning(f"❌ [AUTO MODE] Failed to fill {tool_name}: {e}")
    
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

# Global service instance
crawler_service = CrawlerApplicationService()
