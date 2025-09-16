"""RAG Crawling Service - Based on rag-scraping app.py workflow"""
import asyncio
import re
import uuid
from datetime import datetime
from typing import Dict, Optional, AsyncGenerator, Any, List
import logging
import json

from app.models import TaskStatus, CrawlingResult, TaskResult, ProcessingMode
from app.infrastructure.mcp.mcp_service import mcp_service
from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)

class RAGCrawlingService:
    """RAG 스크래핑 서비스 - rag-scraping의 app.py 워크플로우 기반"""
    
    def __init__(self):
        self.tasks: Dict[str, TaskResult] = {}
        self.task_streams: Dict[str, asyncio.Queue] = {}
        
    def create_task(self, urls_input: str) -> str:
        """새 크롤링 작업 생성"""
        task_id = str(uuid.uuid4())
        
        task_result = TaskResult(
            taskId=task_id,
            status=TaskStatus.PENDING,
            createdAt=datetime.now().isoformat()
        )
        
        self.tasks[task_id] = task_result
        self.task_streams[task_id] = asyncio.Queue()
        
        logger.info(f"✅ RAG Task created: {task_id} for URLs: {urls_input[:100]}...")
        
        # 백그라운드에서 작업 시작
        asyncio.create_task(self._process_rag_task(task_id, urls_input))
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskResult]:
        """작업 조회"""
        return self.tasks.get(task_id)
    
    async def get_task_stream(self, task_id: str) -> AsyncGenerator[str, None]:
        """SSE 스트림 제공"""
        logger.info(f"🔍 RAG SSE stream requested for task: {task_id}")
        
        if task_id not in self.task_streams:
            logger.error(f"❌ RAG Task stream not found: {task_id}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Task not found'}})}\n\n"
            return
            
        # 초기 연결 확인
        yield f"data: {json.dumps({'type': 'connected', 'data': {'message': 'RAG Stream connected'}})}\n\n"
            
        queue = self.task_streams[task_id]
        
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {message}\n\n"
                    
                    # 완료 신호 확인
                    try:
                        msg_data = json.loads(message)
                        if msg_data.get('type') in ['final', 'complete', 'error']:
                            logger.warning(f"🔚 [RAG SSE] Sending final event, waiting before close...")
                            await asyncio.sleep(0.5)
                            break
                    except:
                        pass
                    
                    # 작업 완료 확인
                    task = self.tasks.get(task_id)
                    if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        break
                        
                except asyncio.TimeoutError:
                    # 하트비트
                    yield f"data: {json.dumps({'type': 'heartbeat', 'data': {}})}\n\n"
                    
                    task = self.tasks.get(task_id)
                    if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        yield f"data: {json.dumps({'type': 'complete', 'data': {'message': 'RAG 작업 완료'}})}\n\n"
                        break
                    
        except Exception as e:
            logger.error(f"RAG Task stream error {task_id}: {e}")
            try:
                yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
            except:
                pass
        finally:
            logger.info(f"Cleaning up RAG task stream: {task_id}")
            if task_id in self.task_streams:
                del self.task_streams[task_id]
    
    async def _process_rag_task(self, task_id: str, urls_input: str):
        """RAG 작업 처리 - rag-scraping app.py의 전체 워크플로우"""
        try:
            # 작업 상태 업데이트
            self.tasks[task_id].status = TaskStatus.RUNNING
            await self._send_update(task_id, 'status', {'message': 'RAG 크롤링 작업을 시작합니다...', 'status': 'active'})

            # 1단계: URL 추출 및 검증
            await self._send_update(task_id, 'status', {'message': 'URL 목록을 분석하고 있습니다...', 'status': 'active'})
            urls_list = await self._extract_urls_from_input(urls_input)
            
            if not urls_list:
                raise Exception("유효한 URL이 없습니다")
            
            logger.info(f"📋 RAG Task {task_id}: {len(urls_list)} URLs 추출됨")

            # 2단계: 데이터 스크래핑 (rag-scraping의 scrape_data 단계)
            await self._send_update(task_id, 'status', {'message': f'{len(urls_list)}개 URL 크롤링을 시작합니다...', 'status': 'active'})
            scraped_results = await self._scrape_data(task_id, urls_list)
            
            if not scraped_results:
                raise Exception("크롤링된 데이터가 없습니다")

            # 3단계: 데이터 전처리 (rag-scraping의 preprocess_data 단계)
            await self._send_update(task_id, 'status', {'message': '데이터 전처리를 수행합니다...', 'status': 'active'})
            processed_results = await self._preprocess_data(task_id, scraped_results)

            # 4단계: JSON 변환 (rag-scraping의 convert_to_json 단계)
            await self._send_update(task_id, 'status', {'message': 'JSON 형식으로 변환합니다...', 'status': 'active'})
            json_results = await self._convert_to_json(task_id, processed_results)

            # 5단계: AI 분석 (선택적, 링크 추출 제외)
            await self._send_update(task_id, 'status', {'message': 'AI 분석을 수행합니다...', 'status': 'active'})
            final_results = await self._analyze_with_ai(task_id, json_results)

            # 최종 결과 구성 (불필요한 필드 제거)
            result = CrawlingResult(
                json_data=final_results  # 핵심 JSON 결과만 포함
                # title, textLength, linkCount, links, summary, screenshot, error 제거
            )

            # 작업 완료
            self.tasks[task_id].result = result
            self.tasks[task_id].status = TaskStatus.COMPLETED
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            
            await self._send_update(task_id, 'final', result.model_dump())
            await self._send_update(task_id, 'complete', {'message': 'RAG 크롤링 작업이 완료되었습니다'})
            
        except Exception as e:
            logger.error(f"RAG Task {task_id} failed: {e}")
            
            # 에러 처리
            self.tasks[task_id].status = TaskStatus.FAILED
            self.tasks[task_id].error = str(e)
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            
            await self._send_update(task_id, 'error', {'message': str(e)})

    async def _extract_urls_from_input(self, raw_input: str) -> List[str]:
        """입력에서 URL 추출 - LLM 분석 + 정규식 백업"""
        try:
            # 1단계: 정규식으로 기본 URL 추출
            regex_urls = re.findall(r"https?://[^\s,;]+", raw_input)
            
            # 2단계: LLM을 사용한 고급 분석 (자연어 처리)
            llm_urls = await self._extract_urls_with_llm(raw_input)
            
            # 3단계: 결과 통합 및 중복 제거
            all_urls = regex_urls + llm_urls
            ordered_unique: List[str] = []
            seen = set()
            
            for url in all_urls:
                # URL 정리 (끝의 특수문자 제거)
                clean_url = url.rstrip('.,;)]}')
                if clean_url and clean_url not in seen and clean_url.startswith(('http://', 'https://')):
                    ordered_unique.append(clean_url)
                    seen.add(clean_url)
            
            logger.info(f"🔍 URL 추출 완료: {len(ordered_unique)}개 (정규식: {len(regex_urls)}, LLM: {len(llm_urls)})")
            return ordered_unique
            
        except Exception as e:
            logger.error(f"URL 추출 실패: {e}")
            return []

    async def _extract_urls_with_llm(self, raw_input: str) -> List[str]:
        """LLM을 사용한 URL 추출 및 자연어 분석"""
        try:
            # LLM 서비스 가져오기
            from app.infrastructure.llm.llm_service import llm_service
            
            # 자연어 입력에서 URL 추출을 위한 프롬프트
            extraction_prompt = f"""
다음 텍스트에서 웹페이지 URL을 모두 추출해주세요. 
사용자가 크롤링하고 싶어하는 웹페이지들을 찾아서 완전한 URL 형태로 반환해주세요.

입력 텍스트:
{raw_input}

규칙:
1. http:// 또는 https://로 시작하는 완전한 URL만 추출
2. 불완전한 URL이나 도메인만 있는 경우는 제외
3. 한 줄에 하나씩, URL만 출력
4. 중복 제거
5. URL이 없으면 "NO_URLS" 출력

예시 출력:
https://example1.com/page1
https://example2.com/page2
"""

            # LLM 호출
            response = await llm_service.query(extraction_prompt, [])
            
            if not response or "NO_URLS" in response:
                logger.info("🤖 LLM: URL을 찾지 못함")
                return []
            
            # 응답에서 URL 추출
            extracted_urls = []
            for line in response.strip().split('\n'):
                line = line.strip()
                if line and (line.startswith('http://') or line.startswith('https://')):
                    extracted_urls.append(line)
            
            logger.info(f"🤖 LLM URL 추출 성공: {len(extracted_urls)}개")
            return extracted_urls
            
        except Exception as e:
            logger.warning(f"⚠️ LLM URL 추출 실패, 정규식으로 대체: {e}")
            return []

    async def _scrape_data(self, task_id: str, urls_list: List[str]) -> List[Dict[str, Any]]:
        """데이터 스크래핑 - rag-scraping의 scrape_data 메서드 기반"""
        try:
            # MCP 도구를 사용하여 순차적으로 크롤링
            await self._send_update(task_id, 'status', {'message': '순차 크롤링을 시작합니다...', 'status': 'active'})
            
            scraped_results = []
            for i, url in enumerate(urls_list, 1):
                await self._send_update(task_id, 'status', {
                    'message': f'크롤링 진행: {i}/{len(urls_list)} - {url}',
                    'status': 'active'
                })
                
                # crawl4ai_scrape 도구 사용
                try:
                    result = await mcp_service.call_tool("crawl4ai_scrape", {"url": url})
                    
                    # 결과 처리
                    if hasattr(result, 'structured_content'):
                        data = result.structured_content
                    elif hasattr(result, 'data'):
                        data = result.data
                    else:
                        data = result
                    
                    if isinstance(data, dict) and data.get('success'):
                        scraped_results.append({
                            'url': url,
                            'title': data.get('title', '제목 없음'),
                            'html_content': data.get('html_content', ''),
                            'markdown': data.get('markdown', ''),
                            'status_code': data.get('status_code'),
                            'success': True
                        })
                        logger.info(f"✅ RAG 크롤링 성공: {url}")
                    else:
                        error_msg = data.get('error', '알 수 없는 오류') if isinstance(data, dict) else '응답 형식 오류'
                        scraped_results.append({
                            'url': url,
                            'title': '크롤링 실패',
                            'html_content': '',
                            'markdown': '',
                            'error': error_msg,
                            'success': False
                        })
                        logger.warning(f"⚠️ RAG 크롤링 실패: {url} - {error_msg}")
                        
                except Exception as e:
                    logger.error(f"❌ RAG 크롤링 도구 호출 실패: {url} - {e}")
                    scraped_results.append({
                        'url': url,
                        'title': '크롤링 실패',
                        'html_content': '',
                        'markdown': '',
                        'error': str(e),
                        'success': False
                    })

            successful_count = len([r for r in scraped_results if r.get('success', False)])
            logger.info(f"📊 RAG 크롤링 완료 - 성공: {successful_count}/{len(urls_list)}")
            
            return scraped_results
            
        except Exception as e:
            logger.error(f"RAG 스크래핑 단계 실패: {e}")
            raise

    async def _preprocess_data(self, task_id: str, scraped_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """데이터 전처리 - 텍스트 정리 및 구조화"""
        try:
            processed_results = []
            
            for i, result in enumerate(scraped_results, 1):
                await self._send_update(task_id, 'status', {
                    'message': f'전처리 진행: {i}/{len(scraped_results)} - {result["url"]}',
                    'status': 'active'
                })
                
                if not result.get('success', False):
                    # 실패한 항목도 포함 (에러 정보 유지)
                    processed_results.append(result)
                    continue
                
                # 마크다운 텍스트 정리
                markdown_content = result.get('markdown', '')
                
                # 기본적인 텍스트 정리
                if markdown_content:
                    # 연속된 공백 정리
                    markdown_content = re.sub(r'\n\s*\n', '\n\n', markdown_content)
                    markdown_content = re.sub(r' +', ' ', markdown_content)
                    markdown_content = markdown_content.strip()
                
                # 전처리된 결과 구성
                processed_result = {
                    **result,
                    'processed_markdown': markdown_content,
                    'processed_at': datetime.now().isoformat(),
                    'text_length': len(markdown_content),
                    'word_count': len(markdown_content.split()) if markdown_content else 0
                }
                
                processed_results.append(processed_result)
            
            logger.info(f"📝 RAG 전처리 완료: {len(processed_results)}개 항목")
            return processed_results
            
        except Exception as e:
            logger.error(f"RAG 전처리 단계 실패: {e}")
            raise

    async def _convert_to_json(self, task_id: str, processed_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """JSON 형식으로 변환 - rag-scraping의 to_json.py 기반"""
        try:
            json_results = []
            
            for i, result in enumerate(processed_results, 1):
                await self._send_update(task_id, 'status', {
                    'message': f'JSON 변환 진행: {i}/{len(processed_results)} - {result["url"]}',
                    'status': 'active'
                })
                
                if not result.get('success', False):
                    # 실패한 항목은 에러 정보만 포함
                    json_results.append({
                        'url': result['url'],
                        'title': result.get('title', '크롤링 실패'),
                        'text': '',
                        'error': result.get('error', '알 수 없는 오류'),
                        'status': 'failed'
                    })
                    continue
                
                # MCP 도구를 사용하여 JSON 형식으로 변환
                try:
                    url = result['url']
                    title = result.get('title') or '제목 없음'  # None 처리
                    markdown_content = result.get('processed_markdown', result.get('markdown', ''))
                    html_content = result.get('html_content', '')
                    
                    # hierarchy는 현재 메뉴 정보가 없어 주석 처리
                    # from urllib.parse import urlparse
                    # parsed_url = urlparse(url)
                    # hierarchy = [parsed_url.netloc, title]
                    
                    # convert_to_json_format 도구 호출 (hierarchy 제거)
                    json_result = await mcp_service.call_tool("convert_to_json_format", {
                        "url": url,
                        "title": title,  # 이제 항상 문자열
                        "markdown_content": markdown_content,
                        "html_content": html_content
                        # hierarchy 매개변수 제거
                    })
                    
                    # 결과 처리
                    if hasattr(json_result, 'structured_content'):
                        data = json_result.structured_content
                    elif hasattr(json_result, 'data'):
                        data = json_result.data
                    else:
                        data = json_result
                    
                    if isinstance(data, dict) and data.get('success'):
                        json_data = data.get('json_data', {})
                        json_results.append(json_data)
                        logger.info(f"✅ RAG JSON 변환 성공: {url}")
                    else:
                        # 변환 실패시 기본 형식으로 생성 (불필요한 필드 제거)
                        json_results.append({
                            'url': url,
                            'title': title,  # 이미 위에서 None 처리됨
                            'text': markdown_content.replace('\n', '\\n'),
                            # 'hierarchy': hierarchy,  # 주석 처리
                            # 'status': 'new',  # 주석 처리
                            'startdate': '0000-00-00',
                            'enddate': '9999-99-99',
                            'metadata': {}
                        })
                        logger.warning(f"⚠️ RAG JSON 변환 실패, 기본 형식 사용: {url}")
                        
                except Exception as e:
                    logger.error(f"❌ RAG JSON 변환 도구 호출 실패: {result['url']} - {e}")
                    # 기본 형식으로 생성 (불필요한 필드 제거)
                    safe_title = result.get('title') or '제목 없음'  # None 처리
                    json_results.append({
                        'url': result['url'],
                        'title': safe_title,
                        'text': result.get('processed_markdown', '').replace('\n', '\\n'),
                        # 'hierarchy': [result['url']],  # 주석 처리
                        # 'status': 'new',  # 주석 처리
                        'error': str(e)
                    })

            successful_count = len([r for r in json_results if not r.get('error')])
            logger.info(f"📄 RAG JSON 변환 완료 - 성공: {successful_count}/{len(processed_results)}")
            
            return json_results
            
        except Exception as e:
            logger.error(f"RAG JSON 변환 단계 실패: {e}")
            raise

    async def _analyze_with_ai(self, task_id: str, json_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """AI 분석 - 제약사항: 링크 추출 과정 제외"""
        try:
            analyzed_results = []
            
            for i, json_item in enumerate(json_results, 1):
                await self._send_update(task_id, 'status', {
                    'message': f'AI 분석 진행: {i}/{len(json_results)} - {json_item.get("url", "Unknown")}',
                    'status': 'active'
                })
                
                if json_item.get('error'):
                    # 에러가 있는 항목은 그대로 유지
                    analyzed_results.append(json_item)
                    continue
                
                # AI 분석 수행 (링크 추출 제외)
                try:
                    text_content = json_item.get('text', '').replace('\\n', '\n')
                    
                    if text_content and len(text_content.strip()) > 50:
                        # AI에게 컨텐츠 분석 요청 (링크 정보 제외)
                        analysis_prompt = f"""다음 웹페이지 내용을 분석하고 한국어로 요약해주세요:

URL: {json_item.get('url', '')}
제목: {json_item.get('title', '')}

내용:
{text_content[:2000]}{'...' if len(text_content) > 2000 else ''}

다음 형식으로 분석 결과를 제공해주세요:
1. [요약] 
- 페이지의 주요 목적과 내용 (100자 이내)으로 작성합니다.
2. [키워드] 
- 핵심 키워드 3-5개를 작성합니다.
3. [특징] 
- 사용자에게 유용한 정보나 특징을 작성합니다.

간결하고 실용적인 분석을 제공해주세요."""
                        
                        try:
                            ai_response = await llm_service.query(analysis_prompt, [])
                            
                            if ai_response and len(ai_response.strip()) > 10:
                                # AI 분석 결과를 메타데이터에 추가 (중복 제거)
                                if 'metadata' not in json_item:
                                    json_item['metadata'] = {}
                                json_item['metadata']['ai_analysis'] = ai_response.strip()
                                # ai_summary 필드는 중복이므로 제거
                                logger.info(f"✅ RAG AI 분석 성공: {json_item.get('url', '')}")
                            else:
                                logger.warning(f"⚠️ RAG AI 분석 응답 부족: {json_item.get('url', '')}")
                                
                        except Exception as ai_e:
                            logger.warning(f"⚠️ RAG AI 분석 실패: {json_item.get('url', '')} - {ai_e}")
                    
                    analyzed_results.append(json_item)
                    
                except Exception as e:
                    logger.error(f"❌ RAG AI 분석 처리 실패: {json_item.get('url', '')} - {e}")
                    analyzed_results.append(json_item)

            logger.info(f"🤖 RAG AI 분석 완료: {len(analyzed_results)}개 항목")
            return analyzed_results
            
        except Exception as e:
            logger.error(f"RAG AI 분석 단계 실패: {e}")
            # AI 분석 실패시에도 기존 결과 반환
            return json_results

    async def _send_update(self, task_id: str, event_type: str, data: dict):
        """작업 스트림에 업데이트 전송"""
        if task_id in self.task_streams:
            message = json.dumps({
                'type': event_type,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }, ensure_ascii=False)  # 한글 유니코드 이스케이프 방지
            
            logger.warning(f"📤 [RAG SSE] Sending {event_type} event to task {task_id}: {message[:100]}...")
            
            try:
                await self.task_streams[task_id].put(message)
                logger.warning(f"✅ [RAG SSE] Successfully queued {event_type} event")
            except Exception as e:
                logger.error(f"❌ [RAG SSE] Failed to send update for task {task_id}: {e}")

# Global service instance
crawling_service = RAGCrawlingService()