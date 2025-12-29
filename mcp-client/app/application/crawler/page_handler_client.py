"""
PageHandlerClient - page_handlers용 스크래핑 클라이언트
MCP 서버의 crawl4ai_scrape를 호출하여 URL을 스크래핑합니다.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.infrastructure.mcp.mcp_service import mcp_service

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """스크래핑 결과를 담는 데이터 클래스"""
    success: bool
    markdown: str = ""
    html: str = ""
    title: str = ""
    url: str = ""
    error: Optional[str] = None


@dataclass
class CrawlResult:
    """crawl4ai의 CrawlResult와 호환되는 결과 클래스"""
    success: bool
    html: str = ""
    markdown: str = ""
    title: str = ""
    url: str = ""
    error_message: Optional[str] = None


class CrawlerProxy:
    """
    crawl4ai의 crawler.arun() 직접 접근을 위한 프록시
    실제로는 MCP 서버의 crawl4ai_scrape를 호출합니다.
    """

    def _normalize_result(self, result: Any) -> Dict[str, Any]:
        """
        MCP CallToolResult를 Dict로 변환
        """
        if hasattr(result, "structured_content"):
            return result.structured_content
        if hasattr(result, "data"):
            return result.data
        if isinstance(result, dict):
            return result
        logger.warning(f"Unexpected MCP tool result type: {type(result)}")
        return {"success": False, "error": "Unknown result format"}

    async def arun(self, url: str, config: Any = None) -> CrawlResult:
        """
        crawl4ai 스타일의 arun 메서드 에뮬레이션
        Args:
            url: 크롤링할 URL
            config: CrawlerRunConfig (현재는 무시, MCP 서버가 기본 설정 사용)
        Returns:
            crawl4ai 결과와 유사한 객체
        """
        logger.debug(f"CrawlerProxy.arun called for: {url}")
        raw_result = await mcp_service.call_tool("crawl4ai_scrape", {"url": url})
        result = self._normalize_result(raw_result)

        return CrawlResult(
            success=result.get("success", False),
            html=result.get("html_content", ""),
            markdown=result.get("markdown", ""),
            title=result.get("title", ""),
            url=url,
            error_message=result.get("error")
        )


class PageHandlerClient:
    """
    page_handlers.py의 fclient 인터페이스와 호환되는 클라이언트
    MCPService를 직접 호출합니다.
    """

    def __init__(self):
        self._crawler_proxy = CrawlerProxy()

    @property
    def crawler(self) -> CrawlerProxy:
        """crawl4ai crawler 직접 접근용 프록시"""
        return self._crawler_proxy

    def _normalize_result(self, result: Any) -> Dict[str, Any]:
        """
        MCP CallToolResult를 Dict로 변환
        """
        if hasattr(result, "structured_content"):
            return result.structured_content
        if hasattr(result, "data"):
            return result.data
        if isinstance(result, dict):
            return result
        logger.warning(f"Unexpected MCP tool result type: {type(result)}")
        return {"success": False, "error": "Unknown result format"}

    async def scrape(self, url: str) -> Dict[str, Any]:
        """
        단일 URL 비동기 스크래핑 (Dict 반환)
        Args:
            url: 스크래핑할 URL
        Returns:
            Dict with keys: success, markdown, html, title, url, error
        """
        logger.debug(f"PageHandlerClient.scrape called for: {url}")
        try:
            raw_result = await mcp_service.call_tool("crawl4ai_scrape", {"url": url})
            result = self._normalize_result(raw_result)
            return {
                "success": result.get("success", False),
                "markdown": result.get("markdown", ""),
                "html": result.get("html_content", ""),
                "title": result.get("title", ""),
                "url": url,
                "error": result.get("error")
            }
        except Exception as e:
            logger.error(f"scrape failed for {url}: {e}")
            return {
                "success": False,
                "markdown": "",
                "html": "",
                "title": "",
                "url": url,
                "error": str(e)
            }

    async def scrape_single_url(self, url: str) -> Dict[str, Any]:
        """
        scrape()의 별칭 (하위 호환성 유지)
        """
        return await self.scrape(url)

    async def scrape_as_result(self, url: str) -> ScrapeResult:
        """
        비동기 스크래핑 (ScrapeResult 객체 반환)
        Args:
            url: 스크래핑할 URL
        Returns:
            ScrapeResult 객체
        """
        result = await self.scrape(url)
        return ScrapeResult(
            success=result.get("success", False),
            markdown=result.get("markdown", ""),
            html=result.get("html", ""),
            title=result.get("title", ""),
            url=url,
            error=result.get("error")
        )


# 싱글톤 인스턴스
page_handler_client = PageHandlerClient()
