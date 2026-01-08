"""
Daily Crawling Service

input_urls 테이블에서 URL을 조회하여 크롤링하고,
전처리 후 menu_links 테이블에 업데이트합니다.
최종 결과는 data_*.json 형식으로 출력됩니다.
"""
import asyncio
import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import select, or_

from app.application.crawler.tools_client import crawler_tools
from app.application.crawler.page_handlers import (
    route_url,
    get_handler_for_url,
    page_handler_client,
)
from app.application.crawler.preprocess import preprocess_content
from app.domains.crawler.entities.input_url import InputUrl
from app.domains.crawler.repositories.input_url_repository import input_url_repository
from app.domains.menu.entities.menu_link import MenuLink
from app.models import TaskResult, TaskStatus, CrawlingResult, FailedItem
from app.shared.database.base import get_database_session

logger = logging.getLogger(__name__)

# 결과 저장 경로
RESULT_DIR = Path(__file__).parent / "result"
JSON_START_DATE = "1900-01-01"
JSON_END_DATE = "2999-12-31"


def _setup_asyncio_exception_handler():
    """
    asyncio 이벤트 루프의 exception handler 설정
    Playwright TargetClosedError 등 타임아웃 시 발생하는 예외를 무시
    """
    def handle_exception(loop, context):
        exception = context.get("exception")
        message = context.get("message", "")
        
        # TargetClosedError는 타임아웃 시 정상적으로 발생하므로 무시
        if exception:
            exc_name = type(exception).__name__
            if exc_name in ("TargetClosedError", "CancelledError"):
                logger.debug(f"Ignored async exception: {exc_name}")
                return
        
        # 그 외 예외는 기본 핸들러로 처리
        logger.warning(f"⚠️ Async exception: {message} - {exception}")
    
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(handle_exception)
    except RuntimeError:
        # 이벤트 루프가 없는 경우 무시
        pass


class DailyCrawlingService:
    """
    Daily Crawling 서비스
    
    input_urls 테이블에서 활성화된 URL을 조회하여 크롤링하고,
    전처리 후 menu_links 테이블에 업데이트합니다.
    최종 결과는 data_*.json 형식으로 출력됩니다.
    """
    
    def __init__(self) -> None:
        self.tasks: Dict[str, TaskResult] = {}
        self.task_streams: Dict[str, asyncio.Queue] = {}
        self._collected_results: Dict[str, List[Dict[str, Any]]] = {}  # task별 결과 수집
        self._failed_items: Dict[str, List[FailedItem]] = {}  # task별 실패 내역 수집
    
    # ----------------------------------------------------------------------------------
    # Public APIs
    # ----------------------------------------------------------------------------------
    def create_task(
        self, 
        force_recrawl: bool = False, 
        limit: Optional[int] = None,
        url_ids: Optional[List[int]] = None,
        mode: str = "sequential",
        concurrency: int = 3,
        update_menu_links: bool = True
    ) -> str:
        """
        Daily Crawling 태스크 생성
        
        Args:
            force_recrawl: 이미 성공한 URL도 재크롤링
            limit: 최대 URL 수 (url_ids가 있으면 무시)
            url_ids: 특정 input_urls ID 목록 (테스트용)
            mode: 실행 모드 ("sequential" 또는 "parallel")
            concurrency: 병렬 실행 시 동시 처리 수 (1~50, 기본값: 3)
            update_menu_links: menu_links DB 업데이트 여부 (기본값 True)
            
        Returns:
            task_id
        """
        task_id = str(uuid.uuid4())
        task_result = TaskResult(
            taskId=task_id,
            status=TaskStatus.PENDING,
            createdAt=datetime.now().isoformat(),
        )
        self.tasks[task_id] = task_result
        self.task_streams[task_id] = asyncio.Queue()
        self._collected_results[task_id] = []
        self._failed_items[task_id] = []
        
        # concurrency 범위 제한
        concurrency = max(1, min(10, concurrency))
        
        if url_ids:
            logger.info(f"✅ Task created: {task_id} (url_ids={url_ids}, mode={mode})")
        else:
            logger.info(f"✅ Task created: {task_id} (mode={mode}, concurrency={concurrency}, update_menu_links={update_menu_links})")
        asyncio.create_task(self._process_daily_task(task_id, force_recrawl, limit, url_ids, mode, concurrency, update_menu_links))
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskResult]:
        """태스크 조회"""
        return self.tasks.get(task_id)
    
    def get_tasks(self, limit: int = 10) -> List[TaskResult]:
        """최근 태스크 목록 조회"""
        # 생성 시간 역순으로 정렬하여 반환
        sorted_tasks = sorted(
            self.tasks.values(), 
            key=lambda x: x.createdAt, 
            reverse=True
        )
        return sorted_tasks[:limit]
    
    async def get_task_stream(self, task_id: str) -> AsyncGenerator[str, None]:
        """SSE 스트림 생성"""
        logger.info(f"🔍 SSE stream requested: {task_id}")
        
        if task_id not in self.task_streams:
            # 태스크가 아직 실행 중이라면 큐를 다시 생성 (복구/재연결 대응)
            task = self.tasks.get(task_id)
            if task and task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                logger.info(f"🔄 Re-creating stream queue for active task: {task_id}")
                self.task_streams[task_id] = asyncio.Queue()
            else:
                logger.error(f"❌ Stream not found: {task_id}")
                yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Task not found or already finished'}})}\n\n"
                return
        
        yield f"data: {json.dumps({'type': 'connected', 'data': {'message': 'Daily Crawling Stream connected'}})}\n\n"
        
        queue = self.task_streams[task_id]
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {message}\n\n"
                    
                    try:
                        payload = json.loads(message)
                        if payload.get("type") in {"final", "complete", "error"}:
                            # 클라이언트가 메시지를 받을 수 있도록 충분히 대기
                            await asyncio.sleep(2.0)
                            break
                    except json.JSONDecodeError:
                        pass
                    
                    task = self.tasks.get(task_id)
                    if task and task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                        break
                        
                except asyncio.TimeoutError:
                    await self._send_update(task_id, "heartbeat", {})
                    task = self.tasks.get(task_id)
                    if task and task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                        break
                        
        except Exception as exc:
            logger.error(f"❌ Stream error {task_id}: {exc}")
            # 이미 닫힌 스트림에 에러를 보낼 수 없으므로 로그만 남김
        finally:
            logger.info(f"SSE connection closed: {task_id}")
            # 이 연결이 종료되었다고 해서 다른 클라이언트를 위한 큐를 삭제하지 않음
            # 큐 삭제는 태스크가 완료된 후 _process_daily_task의 마지막이나 별도 관리 루틴에서 수행하는 것이 안전함
            
            task = self.tasks.get(task_id)
            if task and task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                # 태스크가 이미 종료된 상태에서 연결이 끊긴 경우에만 정리 고려
                # 단, 여러 클라이언트가 있을 수 있으므로 신중해야 함
                pass
    
    # ----------------------------------------------------------------------------------
    # Core Workflow
    # ----------------------------------------------------------------------------------
    async def _process_daily_task(
        self, 
        task_id: str, 
        force_recrawl: bool,
        limit: Optional[int],
        url_ids: Optional[List[int]] = None,
        mode: str = "sequential",
        concurrency: int = 5,
        update_menu_links: bool = True
    ) -> None:
        """Daily Crawling 태스크 처리"""
        # 타임아웃 시 TargetClosedError 등 무시하도록 설정
        _setup_asyncio_exception_handler()
        
        try:
            self.tasks[task_id].status = TaskStatus.RUNNING
            mode_text = "병렬" if mode == "parallel" else "순차"
            await self._send_update(task_id, "status", {
                "message": f"Daily Crawling 작업을 시작합니다... ({mode_text} 모드)",
                "status": "active",
                "mode": mode
            })
            
            # 1. input_urls에서 URL 조회
            if url_ids:
                # 특정 ID 목록으로 조회 (테스트용)
                urls = await input_url_repository.get_by_ids(url_ids)
                logger.info(f"🔍 Test mode: {len(urls)} URLs (IDs: {url_ids})")
            else:
                # 기존 방식: 활성 URL 조회
                urls = await input_url_repository.get_active_urls(
                    force_recrawl=force_recrawl,
                    limit=limit
                )
            
            if not urls:
                await self._send_update(task_id, "status", {
                    "message": "크롤링할 URL이 없습니다.",
                    "status": "completed"
                })
                self.tasks[task_id].status = TaskStatus.COMPLETED
                self.tasks[task_id].completedAt = datetime.now().isoformat()
                await self._send_update(task_id, "complete", {"message": "작업 완료 (크롤링 대상 없음)"})
                return
            
            test_mode_text = " [테스트]" if url_ids else ""
            await self._send_update(task_id, "status", {
                "message": f"{len(urls)}개 URL 크롤링을 시작합니다...{test_mode_text} ({mode_text} 모드, 동시성: {concurrency})",
                "status": "active",
                "total_urls": len(urls),
                "mode": mode,
                "concurrency": concurrency
            })
            
            # 2. 모드에 따라 크롤링 실행 (DB 업데이트 없이 결과만 수집)
            if mode == "parallel":
                crawl_results = await self._process_parallel(
                    task_id, urls, concurrency
                )
            else:
                crawl_results = await self._process_sequential(
                    task_id, urls
                )
            
            # 3. 일괄 DB 업데이트
            db_update_msg = "DB 업데이트 중..." if update_menu_links else "결과 처리 중... (menu_links 업데이트 스킵)"
            await self._send_update(task_id, "status", {
                "message": db_update_msg,
                "status": "active"
            })
            success_count, failed_count = await self._batch_update_db(task_id, crawl_results, update_menu_links)
            
            # 4. JSON 파일 저장
            json_file_path = await self._save_json_output(task_id)
            
            # 4. 완료 처리
            self.tasks[task_id].status = TaskStatus.COMPLETED
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            
            # 결과 저장 (API 조회용)
            self.tasks[task_id].result = CrawlingResult(
                json_file=str(json_file_path) if json_file_path else None,
                success=success_count,
                failed=failed_count,
                total=len(urls),
                failed_items=self._failed_items.get(task_id, [])
            )
            
            summary = {
                "total": len(urls),
                "success": success_count,
                "failed": failed_count,
                "json_file": str(json_file_path) if json_file_path else None,
                "message": f"Daily Crawling 완료: {success_count}/{len(crawl_results)} 성공",
                "failed_items": [item.model_dump() for item in self._failed_items.get(task_id, [])]
            }
            
            await self._send_update(task_id, "final", summary)
            await self._send_update(task_id, "complete", summary)
            
            # 클라이언트가 완료 메시지를 받을 수 있도록 잠시 대기
            await asyncio.sleep(1.0)
            
            logger.info(f"✅ Crawling done: {success_count}/{len(urls)} success, {failed_count} failed")
            
            # 정리 (충분한 대기 후 스트림 큐 삭제)
            self._collected_results.pop(task_id, None)
            self._failed_items.pop(task_id, None)
            asyncio.create_task(self._delayed_cleanup(task_id))
            
        except Exception as exc:
            logger.error(f"❌ Task {task_id} failed: {exc}")
            self.tasks[task_id].status = TaskStatus.FAILED
            self.tasks[task_id].error = str(exc)
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            await self._send_update(task_id, "error", {"message": str(exc)})
            # 클라이언트가 에러 메시지를 받을 수 있도록 잠시 대기
            await asyncio.sleep(1.0)
            self._collected_results.pop(task_id, None)
            self._failed_items.pop(task_id, None)
            asyncio.create_task(self._delayed_cleanup(task_id))

    async def _delayed_cleanup(self, task_id: str, delay: float = 300.0) -> None:
        """태스크 완료 후 지연된 정리 (스트림 큐 삭제 등)"""
        await asyncio.sleep(delay)
        logger.info(f"🧹 Delayed cleanup for task: {task_id}")
        self.task_streams.pop(task_id, None)
    
    async def _process_sequential(
        self,
        task_id: str,
        urls: List[InputUrl]
    ) -> List[Dict[str, Any]]:
        """순차 크롤링 처리 (결과만 수집, DB 업데이트 없음)"""
        results = []
        success_count = 0
        failed_count = 0
        
        for idx, input_url in enumerate(urls, start=1):
            try:
                await self._send_update(task_id, "progress", {
                    "current": idx,
                    "total": len(urls),
                    "success": success_count,
                    "failed": failed_count,
                    "url": input_url.pc_url,
                    "message": f"크롤링 중: {idx}/{len(urls)}"
                })
                
                # 크롤링 실행
                crawl_result = await self._crawl_single_url(input_url)
                
                if crawl_result.get("success"):
                    success_count += 1
                    # 전처리 실행
                    processed_result = self._preprocess_result(crawl_result, input_url)
                    results.append({
                        "success": True,
                        "input_url": input_url,
                        "processed_result": processed_result,
                    })
                    logger.info(f"✅ [{idx}/{len(urls)}] Success: {input_url.pc_url}")
                else:
                    failed_count += 1
                    results.append({
                        "success": False,
                        "input_url": input_url,
                        "error": crawl_result.get("error"),
                    })
                    logger.warning(f"❌ [{idx}/{len(urls)}] Failed: {input_url.pc_url}")
                
                # 개별 작업 후 진행 상황 업데이트 (count 반영)
                await self._send_update(task_id, "progress", {
                    "current": idx,
                    "total": len(urls),
                    "success": success_count,
                    "failed": failed_count,
                    "url": input_url.pc_url,
                    "message": f"크롤링 완료: {idx}/{len(urls)}"
                })
                    
            except Exception as exc:
                failed_count += 1
                logger.error(f"❌ [{idx}/{len(urls)}] Error: {input_url.pc_url} - {exc}")
                results.append({
                    "success": False,
                    "input_url": input_url,
                    "error": str(exc),
                })
        
        return results
    
    async def _process_parallel(
        self,
        task_id: str,
        urls: List[InputUrl],
        concurrency: int
    ) -> List[Dict[str, Any]]:
        """병렬 크롤링 처리 (결과만 수집, DB 업데이트 없음)"""
        semaphore = asyncio.Semaphore(concurrency)
        results: List[Dict[str, Any]] = []
        processed_count = 0
        success_count = 0
        failed_count = 0
        total = len(urls)
        lock = asyncio.Lock()
        
        async def crawl_with_semaphore(idx: int, input_url: InputUrl) -> Dict[str, Any]:
            nonlocal processed_count, success_count, failed_count
            
            async with semaphore:
                try:
                    # 크롤링 실행
                    crawl_result = await self._crawl_single_url(input_url)
                    
                    async with lock:
                        processed_count += 1
                        current = processed_count
                        
                        if crawl_result.get("success"):
                            success_count += 1
                            is_success = True
                        else:
                            failed_count += 1
                            is_success = False
                        
                        curr_success = success_count
                        curr_failed = failed_count
                    
                    if is_success:
                        # 전처리 실행
                        processed_result = self._preprocess_result(crawl_result, input_url)
                        result = {
                            "success": True,
                            "input_url": input_url,
                            "processed_result": processed_result,
                        }
                        logger.info(f"✅ [{current}/{total}] Success: {input_url.pc_url}")
                    else:
                        result = {
                            "success": False,
                            "input_url": input_url,
                            "error": crawl_result.get("error"),
                        }
                        logger.warning(f"❌ [{current}/{total}] Failed: {input_url.pc_url}")
                    
                    # 진행 상황 업데이트
                    await self._send_update(task_id, "progress", {
                        "current": current,
                        "total": total,
                        "success": curr_success,
                        "failed": curr_failed,
                        "url": input_url.pc_url,
                        "message": f"크롤링 완료: {current}/{total} (병렬 처리 중)"
                    })
                    
                    return result
                    
                except Exception as exc:
                    async with lock:
                        processed_count += 1
                        current = processed_count
                        failed_count += 1
                        curr_success = success_count
                        curr_failed = failed_count
                    
                    logger.error(f"❌ [{current}/{total}] Error: {input_url.pc_url} - {exc}")
                    
                    await self._send_update(task_id, "progress", {
                        "current": current,
                        "total": total,
                        "success": curr_success,
                        "failed": curr_failed,
                        "url": input_url.pc_url,
                        "message": f"크롤링 완료: {current}/{total} (병렬 처리 중)"
                    })
                    
                    return {
                        "success": False,
                        "input_url": input_url,
                        "error": str(exc),
                    }
        
        # 모든 URL에 대해 병렬 실행
        tasks = [crawl_with_semaphore(idx, url) for idx, url in enumerate(urls, start=1)]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리 및 결과 수집
        for i, result in enumerate(task_results):
            if isinstance(result, Exception):
                results.append({
                    "success": False,
                    "input_url": urls[i],
                    "error": str(result),
                })
            else:
                results.append(result)
        
        return results
    
    async def _crawl_single_url(self, input_url: InputUrl, timeout: int = 300) -> Dict[str, Any]:
        """
        단일 URL 크롤링
        
        Args:
            input_url: InputUrl 엔티티
            timeout: 타임아웃 (초, 기본값 5분)
        """
        url = input_url.pc_url
        menu = input_url.menu_path
        
        # 핸들러 타입에 따라 타임아웃 조정
        handler_info = get_handler_for_url(url)
        skip_timeout = False
        if handler_info:
            _, handler_func = handler_info
            handler_name = handler_func.__name__
            
            # 다중 페이지 순회 핸들러 패턴들
            multi_page_patterns = [
                "_main",  # 기존: 다중 결과 메인 핸들러
                "_list",  # 목록 핸들러 (내부에서 상세 페이지 순회)
                "gigagenie_faq",  # FAQ 전체 페이지 순회
                "gigagenie_news",  # 뉴스 전체 페이지 순회
                "winner_announcements",  # 당첨자발표 페이지네이션 + 상세 순회
            ]
            
            # 패턴 매칭 확인
            is_multi_page = any(pattern in handler_name for pattern in multi_page_patterns)
            
            if is_multi_page:
                # 다중 페이지 순회 핸들러: 전체 타임아웃 미적용 (개별 페이지에 자체 타임아웃)
                skip_timeout = True
                logger.info(f"🔗 Multi-page handler detected, skipping global timeout: {handler_name}")
            else:
                # 일반 핸들러: 3분(180초) 타임아웃
                timeout = 180
        
        try:
            if skip_timeout:
                # 다중 결과 핸들러는 타임아웃 없이 실행 (개별 페이지에 자체 타임아웃 있음)
                return await self._do_crawl_single_url(input_url)
            else:
                # 일반 URL/핸들러는 타임아웃 적용
                return await asyncio.wait_for(
                    self._do_crawl_single_url(input_url),
                    timeout=timeout
                )
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout ({timeout}s): {url}")
            # 타임아웃 후 잠시 대기하여 비동기 작업 정리 시간 확보
            await asyncio.sleep(0.5)
            return {
                "success": False,
                "url": url,
                "error": f"크롤링 타임아웃 ({timeout}초)"
            }
        except asyncio.CancelledError:
            logger.warning(f"⚠️ Cancelled: {url}")
            return {
                "success": False,
                "url": url,
                "error": "크롤링 취소됨"
            }
        except Exception as exc:
            logger.error(f"❌ Crawl failed {url}: {exc}")
            return {
                "success": False,
                "url": url,
                "error": str(exc)
            }
    
    async def _do_crawl_single_url(self, input_url: InputUrl) -> Dict[str, Any]:
        """실제 크롤링 로직 (타임아웃 래퍼에서 호출)"""
        url = input_url.pc_url
        menu = input_url.menu_path
        
        try:
            # 1. 전용 핸들러 확인
            handler_info = get_handler_for_url(url)
            
            if handler_info:
                pattern, handler_func = handler_info
                logger.info(f"🔗 Handler matched: {url} -> {handler_func.__name__}")
                
                handler_result = await route_url(url, page_handler_client, menu)
                
                if handler_result:
                    # datas 배열이 있는 경우 모든 항목을 처리
                    if "datas" in handler_result and handler_result.get("datas"):
                        datas = handler_result["datas"]
                        menus = handler_result.get("menus", [])  # menus 배열도 가져오기
                        logger.info(f"✅ Handler result: {len(datas)} items, {len(menus)} menus ({url})")
                        
                        # 여러 데이터를 포함한 결과 반환
                        return {
                            "success": True,
                            "url": url,
                            "mobile_url": input_url.mobile_url,
                            "title": handler_result.get("title"),
                            "markdown": handler_result.get("markdown", ""),
                            "html_content": handler_result.get("html", ""),
                            "hierarchy": input_url.get_hierarchy_list(),
                            "handler_name": handler_func.__name__,
                            "datas": datas,  # 모든 datas 포함
                            "menus": menus,  # menus 배열 포함
                            "is_multi_result": True,
                        }
                    else:
                        return {
                            "success": True,
                            "url": url,
                            "mobile_url": input_url.mobile_url,
                            "title": handler_result.get("title"),
                            "markdown": handler_result.get("markdown", ""),
                            "html_content": handler_result.get("html", ""),
                            "hierarchy": input_url.get_hierarchy_list(),
                            "handler_name": handler_func.__name__,
                        }
            
            # 2. 기본 MCP 스크래핑
            logger.info(f"🔍 Default scraping: {url}")
            tool_result = await crawler_tools.scrape(url)
            
            if tool_result.get("success"):
                return {
                    "success": True,
                    "url": url,
                    "mobile_url": input_url.mobile_url,
                    "title": tool_result.get("title"),
                    "markdown": tool_result.get("markdown", ""),
                    "html_content": tool_result.get("html_content", ""),
                    "hierarchy": input_url.get_hierarchy_list(),
                }
            else:
                return {
                    "success": False,
                    "url": url,
                    "error": tool_result.get("error", "스크래핑 실패")
                }
                
        except Exception as exc:
            logger.error(f"❌ Crawl failed {url}: {exc}")
            return {
                "success": False,
                "url": url,
                "error": str(exc)
            }
    
    # ----------------------------------------------------------------------------------
    # 전처리 및 JSON 변환
    # ----------------------------------------------------------------------------------
    def _preprocess_result(
        self, 
        crawl_result: Dict[str, Any], 
        input_url: InputUrl
    ) -> Dict[str, Any]:
        """
        크롤링 결과 전처리
        
        Args:
            crawl_result: 크롤링 결과
            input_url: InputUrl 엔티티
            
        Returns:
            전처리된 결과
        """
        menu_path = input_url.menu_path or ""
        
        # is_multi_result인 경우 datas 배열의 각 항목을 전처리
        if crawl_result.get("is_multi_result") and crawl_result.get("datas"):
            processed_datas = []
            for data in crawl_result["datas"]:
                markdown = data.get("markdown", "")
                html_content = data.get("html", "")
                
                processed_text, process_type = preprocess_content(
                    markdown_text=markdown,
                    menu_path=menu_path,
                    html_content=html_content
                )
                
                processed_datas.append({
                    **data,
                    "processed_text": processed_text,
                    "process_type": process_type,
                })
            
            return {
                **crawl_result,
                "processed_datas": processed_datas,
            }
        
        # 단일 결과인 경우
        markdown = crawl_result.get("markdown", "")
        html_content = crawl_result.get("html_content", "")
        
        # 전처리 실행
        processed_text, process_type = preprocess_content(
            markdown_text=markdown,
            menu_path=menu_path,
            html_content=html_content
        )
        
        return {
            **crawl_result,
            "processed_text": processed_text,
            "process_type": process_type,
        }
    
    def _convert_to_json_format(
        self, 
        processed_result: Dict[str, Any], 
        input_url: InputUrl,
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        전처리된 결과를 최종 JSON 포맷으로 변환
        data_*.json 형식에 맞춤
        
        Args:
            processed_result: 전처리된 결과
            input_url: InputUrl 엔티티
            document_id: menu_links에서 획득한 document_id
            
        Returns:
            JSON 포맷 딕셔너리
        """
        url = processed_result.get("url", "")
        mobile_url = processed_result.get("mobile_url") or input_url.mobile_url or ""
        processed_text = processed_result.get("processed_text", "")
        html_content = processed_result.get("html_content", "")
        hierarchy = processed_result.get("hierarchy", []) or input_url.get_hierarchy_list()
        
        # title 결정
        # 1. 핸들러 데이터인 경우: 핸들러에서 추출한 title 우선 사용
        # 2. 일반 데이터: menu_path의 ^ 기준 마지막 값 사용
        title = ""
        
        if processed_result.get("is_handler_data"):
            # 핸들러에서 추출한 개별 title 사용
            title = processed_result.get("title") or ""
        
        if not title and input_url.menu_path:
            # menu_path의 마지막 값 사용
            menu_parts = input_url.menu_path.split("^")
            title = menu_parts[-1].strip() if menu_parts else ""
        
        # 그래도 없으면 fallback
        if not title:
            title = processed_result.get("title") or "제목 없음"
        
        # 유니코드 정규화
        title = unicodedata.normalize('NFC', title)
        url = unicodedata.normalize('NFC', url)
        processed_text = unicodedata.normalize('NFC', processed_text)
        
        # 개행문자를 \\n으로 변환
        final_text = processed_text.replace("\n", "\\n")
        
        # hierarchy 정규화
        normalized_hierarchy = None
        if hierarchy:
            normalized_hierarchy = [
                unicodedata.normalize('NFC', item) 
                for item in hierarchy 
                if item
            ]
        
        # 메타데이터 추출
        metadata = self._extract_metadata(html_content, url)
        
        # recommendations 필드 추가 (상품 페이지에서 사용)
        if "recommendations" in processed_result:
            recommendations = processed_result.get("recommendations")
            if recommendations:  # 빈 리스트가 아닌 경우에만 추가
                metadata["recommendations"] = recommendations
        
        # 최종 JSON 구조
        json_data = {
            "docId": document_id or "",
            "url": url,
            "murl": mobile_url,
            "hierarchy": normalized_hierarchy or [],
            "title": title,
            "text": final_text,
            "startdate": JSON_START_DATE,
            "enddate": JSON_END_DATE,
            "metadata": metadata,
            "status": "new",
        }
        
        return json_data
    
    def _extract_metadata(
        self, 
        html_content: str, 
        base_url: str
    ) -> Dict[str, Any]:
        """HTML에서 메타데이터 추출 (이미지, 링크 등)"""
        metadata: Dict[str, Any] = {}
        
        if not html_content:
            return metadata
        
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 이미지 추출
            images = []
            for img in soup.find_all('img'):
                if img.find_parent(id=['cfmClHeader', 'cfmClFooter']):
                    continue
                alt_text = (img.get('alt') or '').strip()
                if len(alt_text) > 2:
                    src = img.get('src', '')
                    if src and not src.startswith('http'):
                        src = urljoin(base_url, src)
                    images.append({'alt': alt_text, 'src': src})
            if images:
                metadata['images'] = images
            
            # 링크 추출
            urls_data = []
            for link in soup.find_all('a', href=True):
                if link.find_parent(id=['cfmClHeader', 'cfmClFooter']):
                    continue
                link_text = link.get_text().strip()
                if len(link_text) < 2:
                    continue
                href = link.get('href')
                if href.startswith('http') or href.startswith('/'):
                    if href.startswith('/'):
                        href = urljoin(base_url, href)
                    urls_data.append({'desc': link_text, 'url': href})
            
            if urls_data:
                # 중복 제거
                seen = set()
                unique_urls = []
                for item in urls_data:
                    if item['url'] not in seen:
                        seen.add(item['url'])
                        unique_urls.append(item)
                metadata['urls'] = unique_urls
                
        except Exception as e:
            logger.warning(f"⚠️ Metadata extraction failed: {e}")
        
        return metadata
    
    def _pc_to_mobile_url(self, pc_url: str) -> str:
        """PC URL을 모바일 URL로 변환"""
        if not pc_url:
            return ""
        
        # KT 이벤트 URL 변환
        if "event.kt.com" in pc_url:
            return pc_url.replace("https://event.kt.com", "https://m.kt.com")
        
        # KT Shop URL 변환
        if "shop.kt.com" in pc_url:
            return pc_url.replace("https://shop.kt.com", "https://m.shop.kt.com")
        
        # product.kt.com 변환
        if "product.kt.com" in pc_url:
            return pc_url.replace("https://product.kt.com", "https://m.product.kt.com")
        
        # 기타 kt.com 도메인
        if "kt.com" in pc_url and "://m." not in pc_url:
            # https://xxx.kt.com -> https://m.xxx.kt.com 형태로 변환 시도
            import re
            match = re.match(r'https://([^.]+)\.kt\.com(.*)', pc_url)
            if match:
                subdomain = match.group(1)
                path = match.group(2)
                return f"https://m.{subdomain}.kt.com{path}"
        
        return pc_url
    
    # ----------------------------------------------------------------------------------
    # 일괄 DB 업데이트
    # ----------------------------------------------------------------------------------
    async def _batch_update_db(
        self,
        task_id: str,
        crawl_results: List[Dict[str, Any]],
        update_menu_links: bool = True
    ) -> tuple[int, int]:
        """
        크롤링 결과를 일괄로 DB에 업데이트
        
        Args:
            task_id: 태스크 ID
            crawl_results: 크롤링 결과 목록
            update_menu_links: menu_links DB 업데이트 여부
            
        Returns:
            (success_count, failed_count)
        """
        success_count = 0
        failed_count = 0
        total = len(crawl_results)
        
        logger.info(f"🔍 DB batch update start: {total} items")
        
        for idx, result in enumerate(crawl_results, start=1):
            input_url: InputUrl = result.get("input_url")
            
            try:
                if result.get("success"):
                    processed_result = result.get("processed_result", {})
                    
                    # is_multi_result인 경우 각 data 항목을 개별 처리
                    if processed_result.get("is_multi_result") and processed_result.get("processed_datas"):
                        processed_datas = processed_result["processed_datas"]
                        menus = processed_result.get("menus", [])  # menus 배열 가져오기
                        logger.info(f"✅ Handler result: {len(processed_datas)} items, {len(menus)} menus ({input_url.pc_url})")
                        
                        for data_idx, data in enumerate(processed_datas):
                            # menus 배열에서 해당 인덱스의 메뉴 정보 가져오기
                            menu_info = menus[data_idx] if data_idx < len(menus) else {}
                            
                            # menu 문자열을 ^ 기준으로 분리하여 hierarchy와 title 추출
                            menu_str = menu_info.get("menu", "")
                            if menu_str:
                                menu_parts = [p.strip() for p in menu_str.split("^") if p.strip()]
                                data_hierarchy = menu_parts  # 전체를 hierarchy로
                                data_title = menu_parts[-1] if menu_parts else ""  # 마지막을 title로
                            else:
                                data_hierarchy = processed_result.get("hierarchy", []) or input_url.get_hierarchy_list()
                                data_title = data.get("title") or ""
                            
                            # URL 정보: menus에서 우선, 없으면 data에서
                            data_url = menu_info.get("url") or data.get("url") or input_url.pc_url
                            data_murl = menu_info.get("mobile_url") or self._pc_to_mobile_url(data_url)
                            
                            single_result = {
                                "url": data_url,
                                "mobile_url": data_murl,
                                "title": data_title,
                                "processed_text": data.get("processed_text", ""),
                                "html_content": data.get("html", ""),
                                "hierarchy": data_hierarchy,
                                "is_handler_data": True,  # 핸들러 데이터 표시
                            }
                            
                            # recommendations 필드 포함 (있는 경우)
                            if "recommendations" in data:
                                single_result["recommendations"] = data["recommendations"]
                            
                            # menu_links 업데이트 (docId 획득)
                            document_id = None
                            if update_menu_links:
                                document_id = await self._update_menu_links(single_result, input_url)
                            
                            # JSON 형식으로 변환 (docId 포함)
                            json_data = self._convert_to_json_format(single_result, input_url, document_id)
                            
                            # 결과 수집
                            self._collected_results[task_id].append(json_data)
                        
                        # input_urls 상태 업데이트 (한 번만)
                        handler_name = processed_result.get("handler_name")
                        await input_url_repository.update_crawl_status(
                            input_url.id, "success", handler_name=handler_name
                        )
                        success_count += 1
                    else:
                        # 단일 결과 처리
                        # menu_links 업데이트 (docId 획득)
                        document_id = None
                        if update_menu_links:
                            document_id = await self._update_menu_links(processed_result, input_url)
                        
                        # JSON 형식으로 변환 (docId 포함)
                        json_data = self._convert_to_json_format(processed_result, input_url, document_id)
                        
                        # 결과 수집
                        self._collected_results[task_id].append(json_data)
                        
                        # input_urls 상태 업데이트
                        handler_name = processed_result.get("handler_name")
                        await input_url_repository.update_crawl_status(
                            input_url.id, "success", handler_name=handler_name
                        )
                        success_count += 1
                else:
                    # 실패한 경우
                    error_msg = result.get("error") or "알 수 없는 오류"
                    await input_url_repository.update_crawl_status(
                        input_url.id, "failed", error_msg
                    )
                    failed_count += 1
                    
                    # 실패 내역 저장
                    self._failed_items[task_id].append(FailedItem(
                        id=input_url.id,
                        url=input_url.pc_url,
                        error=error_msg
                    ))
                    
            except Exception as exc:
                error_msg = str(exc)
                logger.error(f"❌ DB update error [{idx}/{total}]: {input_url.pc_url} - {error_msg}")
                await input_url_repository.update_crawl_status(
                    input_url.id, "failed", error_msg
                )
                failed_count += 1
                
                # 실패 내역 저장
                self._failed_items[task_id].append(FailedItem(
                    id=input_url.id,
                    url=input_url.pc_url,
                    error=error_msg
                ))
            
            # 진행 상황 (10개마다 또는 마지막)
            if idx % 10 == 0 or idx == total:
                await self._send_update(task_id, "progress", {
                    "current": idx,
                    "total": total,
                    "success": success_count,
                    "failed": failed_count,
                    "message": f"DB 업데이트 중: {idx}/{total}"
                })
        
        logger.info(f"✅ DB batch update done: {success_count} success, {failed_count} failed")
        return success_count, failed_count
    
    # ----------------------------------------------------------------------------------
    # menu_links 업데이트 (menu_path 우선 조회)
    # ----------------------------------------------------------------------------------
    async def _update_menu_links(
        self, 
        processed_result: Dict[str, Any], 
        input_url: InputUrl
    ) -> Optional[str]:
        """
        크롤링 결과를 menu_links 테이블에 반영
        
        조회 순서: menu_path → pc_url → mobile_url
        
        Returns:
            document_id
        """
        pc_url = processed_result.get("url")
        mobile_url = processed_result.get("mobile_url") or input_url.mobile_url
        hierarchy = processed_result.get("hierarchy", [])
        
        # hierarchy → menu_path 변환
        if hierarchy:
            menu_path = "^".join([seg.strip() for seg in hierarchy if seg and seg.strip()])
        else:
            menu_path = input_url.menu_path or ""
        
        document_id = None
        
        async for session in get_database_session():
            try:
                existing = None
                
                # menu_path + pc_url 조합으로 정확히 일치하는 경우에만 업데이트
                if menu_path and pc_url:
                    stmt = select(MenuLink).where(
                        MenuLink.menu_path == menu_path,
                        MenuLink.pc_url == pc_url
                    )
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                
                if existing:
                    # 업데이트
                    existing.menu_path = menu_path
                    existing.pc_url = pc_url
                    if mobile_url:
                        existing.mobile_url = mobile_url
                    existing.updated_by = "daily_crawling"
                    existing.updated_at = datetime.now()
                    
                    await session.commit()
                    document_id = existing.document_id
                    logger.debug(f"✅ menu_links updated: {document_id}")
                else:
                    # 새 레코드 생성
                    max_num = await self._get_max_document_num(session)
                    document_id = f"ktcom_{max_num + 1}"
                    
                    new_record = MenuLink(
                        document_id=document_id,
                        menu_path=menu_path,
                        pc_url=pc_url,
                        mobile_url=mobile_url,
                        created_by="daily_crawling",
                    )
                    session.add(new_record)
                    await session.commit()
                    logger.debug(f"✅ menu_links created: {document_id}")
                    
            except Exception as exc:
                logger.error(f"❌ menu_links update failed {pc_url}: {exc}")
                await session.rollback()
                raise
            
            break
        
        return document_id
    
    async def _get_max_document_num(self, session) -> int:
        """현재 최대 document_id 번호 조회"""
        stmt = select(MenuLink.document_id).where(
            MenuLink.document_id.like("ktcom_%")
        )
        result = await session.execute(stmt)
        doc_ids = result.scalars().all()
        
        max_num = 0
        for doc_id in doc_ids:
            match = re.match(r"^ktcom_(\d+)$", doc_id)
            if match:
                try:
                    num = int(match.group(1))
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        
        return max_num
    
    # ----------------------------------------------------------------------------------
    # JSON 파일 출력
    # ----------------------------------------------------------------------------------
    async def _save_json_output(self, task_id: str) -> Optional[Path]:
        """
        수집된 결과를 JSON 파일로 저장
        
        형식: data_YYYY-MM-DD_HHMMSS.json
        """
        results = self._collected_results.get(task_id, [])
        
        if not results:
            logger.warning(f"⚠️ No results to save: {task_id}")
            return None
        
        # 결과 디렉토리 생성
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        file_path = RESULT_DIR / f"data_{timestamp}.json"
        
        try:
            # JSON 저장 (한글 유지)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ JSON saved: {file_path} ({len(results)} items)")
            return file_path
            
        except Exception as e:
            logger.error(f"❌ JSON save failed: {e}")
            return None
    
    async def _send_update(self, task_id: str, update_type: str, data: Dict[str, Any]) -> None:
        """SSE 업데이트 전송"""
        if task_id in self.task_streams:
            message = json.dumps({"type": update_type, "data": data})
            await self.task_streams[task_id].put(message)


# 싱글톤 인스턴스
daily_crawling_service = DailyCrawlingService()
