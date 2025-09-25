"""RAG Crawling Service - Based on rag-scraping app.py workflow"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from sqlalchemy import select

from app.application.crawler.tools_client import crawler_tools
from app.domains.menu.entities.menu_link import MenuLink
from app.models import CrawlingResult, TaskResult, TaskStatus
from app.shared.database.base import get_database_session

logger = logging.getLogger(__name__)

# 정규식 상수
URL_PATTERN = re.compile(r"https?://[^\s,;]+")
# 메뉴 경로 구분자 (프론트/데이터와 동일하게 '^' 사용)
MENU_PATH_DELIMITER = "^"
# convert_to_json_format 기본 날짜 값
JSON_START_DATE = "1900-01-01"
JSON_END_DATE = "2999-12-31"


class RAGCrawlingService:
    """RAG 스크래핑 서비스 - rag-scraping의 app.py 워크플로우 기반"""
    
    def __init__(self) -> None:
        self.tasks: Dict[str, TaskResult] = {}
        self.task_streams: Dict[str, asyncio.Queue] = {}
        
    # ----------------------------------------------------------------------------------
    # Public APIs
    # ----------------------------------------------------------------------------------
    def create_task(self, urls_input: str) -> str:
        task_id = str(uuid.uuid4())
        task_result = TaskResult(
            taskId=task_id,
            status=TaskStatus.PENDING,
            createdAt=datetime.now().isoformat(),
        )
        self.tasks[task_id] = task_result
        self.task_streams[task_id] = asyncio.Queue()
        logger.info("✅ RAG Task created: %s", task_id)
        asyncio.create_task(self._process_rag_task(task_id, urls_input))
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskResult]:
        return self.tasks.get(task_id)
    
    async def get_task_stream(self, task_id: str) -> AsyncGenerator[str, None]:
        logger.info("🔍 RAG SSE stream requested for task: %s", task_id)
        if task_id not in self.task_streams:
            logger.error("❌ RAG Task stream not found: %s", task_id)
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Task not found'}})}\n\n"
            return
            
        # 초기 연결 알림
        yield f"data: {json.dumps({'type': 'connected', 'data': {'message': 'RAG Stream connected'}})}\n\n"
        queue = self.task_streams[task_id]
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {message}\n\n"
                    try:
                        payload = json.loads(message)
                        if payload.get("type") in {"final", "complete", "error"}:
                            await asyncio.sleep(0.5)
                            break
                    except json.JSONDecodeError:
                        logger.debug("SSE message is not JSON: %s", message)
                    
                    task = self.tasks.get(task_id)
                    if task and task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                        break
                except asyncio.TimeoutError:
                    await self._send_update(task_id, "heartbeat", {})
                    task = self.tasks.get(task_id)
                    if task and task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                        await self._send_update(task_id, "complete", {"message": "RAG 작업 완료"})
                        break
        except Exception as exc:  # pragma: no cover - SSE 에러 처리
            logger.error("RAG Task stream error %s: %s", task_id, exc)
            await self._send_update(task_id, "error", {"message": str(exc)})
        finally:
            logger.info("Cleaning up RAG task stream: %s", task_id)
            self.task_streams.pop(task_id, None)

    # ----------------------------------------------------------------------------------
    # Core workflow
    # ----------------------------------------------------------------------------------
    async def _process_rag_task(self, task_id: str, urls_input: str) -> None:
        try:
            self.tasks[task_id].status = TaskStatus.RUNNING
            await self._send_update(task_id, "status", {"message": "RAG 크롤링 작업을 시작합니다...", "status": "active"})

            urls = await self._extract_urls_from_input(urls_input)
            if not urls:
                raise ValueError("유효한 URL이 없습니다")
            await self._send_update(task_id, "status", {"message": f"{len(urls)}개 URL 크롤링을 시작합니다...", "status": "active"})

            # 메뉴 매핑 (PC URL 기준)
            url_menu_map = await self._build_url_menu_map(urls)

            scraped_results = await self._scrape_data(task_id, urls)
            if not scraped_results:
                raise ValueError("크롤링된 데이터가 없습니다")

            processed_results = await self._preprocess_data(task_id, scraped_results)
            json_results = await self._convert_to_json(task_id, processed_results, url_menu_map)

            result = CrawlingResult(json_data=json_results)
            self.tasks[task_id].result = result
            self.tasks[task_id].status = TaskStatus.COMPLETED
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            await self._send_update(task_id, "final", result.model_dump())
            await self._send_update(task_id, "complete", {"message": "RAG 크롤링 작업이 완료되었습니다"})
        except Exception as exc:  # pragma: no cover
            logger.error("RAG Task %s failed: %s", task_id, exc)
            self.tasks[task_id].status = TaskStatus.FAILED
            self.tasks[task_id].error = str(exc)
            self.tasks[task_id].completedAt = datetime.now().isoformat()
            await self._send_update(task_id, "error", {"message": str(exc)})
            
    # ----------------------------------------------------------------------------------
    # URL 처리
    # ----------------------------------------------------------------------------------
    async def _extract_urls_from_input(self, raw_input: str) -> List[str]:
        regex_urls = URL_PATTERN.findall(raw_input)
        cleaned_regex = [url.rstrip(".,;)]}") for url in regex_urls]
        ordered_unique: List[str] = []
        seen: set[str] = set()

        for url in cleaned_regex:
            if url and url not in seen and url.startswith(("http://", "https://")):
                ordered_unique.append(url)
                seen.add(url)

        return ordered_unique
            
    async def _build_url_menu_map(self, urls: List[str]) -> Dict[str, MenuLink]:
        if not urls:
            return {}
        unique_urls = list(dict.fromkeys(urls))
        url_map: Dict[str, MenuLink] = {}
        async for session in get_database_session():
            stmt = select(MenuLink).where(MenuLink.pc_url.in_(unique_urls))
            result = await session.execute(stmt)
            for row in result.scalars().all():
                if row.pc_url:
                    url_map[row.pc_url] = row
            break
        logger.info("메뉴 매핑 완료: %s/%s", len(url_map), len(unique_urls))
        return url_map

    # ----------------------------------------------------------------------------------
    # Scraping + preprocessing
    # ----------------------------------------------------------------------------------
    async def _scrape_data(self, task_id: str, urls: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for idx, url in enumerate(urls, start=1):
            await self._send_update(task_id, "status", {"message": f"크롤링 진행: {idx}/{len(urls)} - {url}", "status": "active"})
            try:
                tool_result = await crawler_tools.scrape(url)
                if tool_result.get("success"):
                    results.append(
                        {
                            "url": url,
                            "title": tool_result.get("title"),
                            "html_content": tool_result.get("html_content", ""),
                            "markdown": tool_result.get("markdown", ""),
                        }
                    )
                else:
                    results.append({"url": url, "error": tool_result.get("error", "알 수 없는 오류"), "success": False})
            except Exception as exc:  # pragma: no cover
                logger.error("❌ MCP scrape failed: %s - %s", url, exc)
                results.append({"url": url, "error": str(exc), "success": False})
        return results

    async def _preprocess_data(self, task_id: str, scraped_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed: List[Dict[str, Any]] = []
        for idx, result in enumerate(scraped_results, start=1):
            await self._send_update(task_id, "status", {"message": f"전처리 진행: {idx}/{len(scraped_results)} - {result['url']}", "status": "active"})
            if result.get("error"):
                processed.append(result)
                continue
            markdown = (result.get("markdown") or "").strip()
            processed.append({
                **result,
                "processed_markdown": markdown,
                "processed_at": datetime.now().isoformat(),
                "text_length": len(markdown),
            })
        return processed

    # ----------------------------------------------------------------------------------
    # JSON conversion
    # ----------------------------------------------------------------------------------
    async def _convert_to_json(
        self,
        task_id: str,
        processed_results: List[Dict[str, Any]],
        url_menu_map: Dict[str, MenuLink],
    ) -> List[Dict[str, Any]]:
        json_results: List[Dict[str, Any]] = []

        for idx, result in enumerate(processed_results, start=1):
            await self._send_update(
                task_id,
                "status",
                {
                    "message": f"JSON 변환 진행: {idx}/{len(processed_results)} - {result['url']}",
                    "status": "active",
                },
            )

            if result.get("error"):
                json_results.append(
                    {
                        "url": result["url"],
                        "error": result["error"],
                        "status": "failed",
                    }
                )
                continue
                
            menu = url_menu_map.get(result["url"])
            hierarchy, title = await self._resolve_hierarchy_and_title(result, menu)
            markdown_content = result.get("processed_markdown", "")
            html_content = result.get("html_content", "")
            mobile_url = menu.mobile_url if menu and menu.mobile_url else None

            try:
                json_payload = await crawler_tools.convert_to_json(
                    url=result["url"],
                    title=title,
                    markdown_content=markdown_content,
                    html_content=html_content,
                    hierarchy=hierarchy,
                    mobile_url=mobile_url,
                    startdate=JSON_START_DATE,
                    enddate=JSON_END_DATE,
                )
                if json_payload.get("success"):
                    json_data = json_payload.get("json_data", {})
                else:
                    json_data = self._build_fallback_json(
                        result["url"],
                        mobile_url,
                        title,
                        hierarchy,
                        markdown_content,
                    )
            except Exception as exc:  # pragma: no cover
                logger.error("JSON 변환 실패 %s: %s", result["url"], exc)
                json_data = self._build_fallback_json(
                    result["url"],
                    mobile_url,
                    title,
                    hierarchy,
                    markdown_content,
                    error=str(exc),
                )

            metadata = json_data.setdefault("metadata", {})
            metadata.update(await self._build_media_metadata(html_content, result["url"]))
            # source 필드는 원본 HTML/메뉴 정보 추적용 메타데이터 (전환 후 검토 가능)
            json_data["source"] = {
                "title": result.get("title"),
                "menu_path": menu.menu_path if menu else None,
            }
            json_results.append(json_data)
            
        return json_results
            
    async def _resolve_hierarchy_and_title(self, result: Dict[str, Any], menu: Optional[MenuLink]) -> Tuple[List[str], str]:
        if menu:
            hierarchy = [segment.strip() for segment in menu.menu_path.split(MENU_PATH_DELIMITER) if segment.strip()]
            title = hierarchy[-1] if hierarchy else (result.get("title") or "제목 없음")
            return hierarchy, title

        meta_title = await self._extract_meta_title(result.get("html_content", ""))
        if meta_title:
            return [], meta_title

        fallback_title = result.get("title") or "제목 없음"
        return [], fallback_title

    async def _extract_meta_title(self, html_content: str) -> Optional[str]:
        if not html_content:
            return None
        try:
            meta_result = await crawler_tools.extract_meta_title(html_content)
            if meta_result.get("success") and meta_result.get("title"):
                return meta_result.get("title")
        except Exception as exc:  # pragma: no cover
            logger.warning("Meta title 추출 실패: %s", exc)
        return None

    async def _build_media_metadata(self, html_content: str, base_url: str) -> Dict[str, Any]:
        if not html_content:
            return {}
        metadata: Dict[str, Any] = {}
        try:
            images = await crawler_tools.extract_images(html_content, base_url)
            if images.get("success") and images.get("images"):
                metadata["images"] = images.get("images", [])
        except Exception as exc:  # pragma: no cover
            logger.warning("이미지 메타데이터 추출 실패: %s", exc)
        try:
            links = await crawler_tools.extract_links(html_content, base_url)
            if links.get("success") and links.get("links"):
                metadata["links"] = [link for link in links.get("links", []) if link.get("url")]
        except Exception as exc:  # pragma: no cover
            logger.warning("링크 메타데이터 추출 실패: %s", exc)
        return metadata

    def _build_fallback_json(
        self,
        url: str,
        mobile_url: Optional[str],
        title: str,
        hierarchy: List[str],
        markdown_content: str,
        *,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "url": url,
            "murl": mobile_url or "",
            "hierarchy": hierarchy or [],
            "title": title,
            "text": markdown_content.replace("\n", "\\n"),
            "startdate": JSON_START_DATE,
            "enddate": JSON_END_DATE,
            "metadata": {},
        }
        if error:
            payload["error"] = error
        return payload

    # ----------------------------------------------------------------------------------
    # SSE helper
    # ----------------------------------------------------------------------------------
    async def _send_update(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
        queue = self.task_streams.get(task_id)
        if not queue:
            return
        message = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()}, ensure_ascii=False)
        try:
            await queue.put(message)
        except Exception as exc:  # pragma: no cover
            logger.error("[RAG SSE] Failed to send update for task %s: %s", task_id, exc)


crawling_service = RAGCrawlingService()