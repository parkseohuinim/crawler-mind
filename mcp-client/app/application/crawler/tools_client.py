import logging
from typing import Any, Dict, List, Optional

from app.infrastructure.mcp.mcp_service import mcp_service

logger = logging.getLogger(__name__)


class CrawlerToolsClient:
    """RAG 크롤링 플로우에서 사용할 MCP 툴 래퍼"""

    async def scrape(self, url: str) -> Dict[str, Any]:
        """crawl4ai_scrape"""
        logger.debug("Calling crawl4ai_scrape for %s", url)
        result = await mcp_service.call_tool("crawl4ai_scrape", {"url": url})
        return self._normalize_result(result)

    async def convert_to_json(
        self,
        *,
        url: str,
        title: Optional[str],
        markdown_content: str,
        html_content: str,
        hierarchy: Optional[List[str]] = None,
        mobile_url: Optional[str] = None,
        startdate: str,
        enddate: str,
    ) -> Dict[str, Any]:
        payload = {
            "url": url,
            "title": title,
            "markdown_content": markdown_content,
            "html_content": html_content,
            "hierarchy": hierarchy,
            "startdate": startdate,
            "enddate": enddate,
        }
        if mobile_url is not None:
            payload["murl"] = mobile_url
        logger.debug("Calling convert_to_json_format for %s", url)
        result = await mcp_service.call_tool("convert_to_json_format", payload)
        return self._normalize_result(result)

    async def extract_meta_title(self, html_content: str) -> Dict[str, Any]:
        result = await mcp_service.call_tool(
            "extract_meta_title",
            {"html_content": html_content},
        )
        return self._normalize_result(result)

    async def extract_images(self, html_content: str, base_url: str) -> Dict[str, Any]:
        result = await mcp_service.call_tool(
            "extract_image_metadata",
            {"html_content": html_content, "base_url": base_url},
        )
        return self._normalize_result(result)

    async def extract_links(self, html_content: str, base_url: str) -> Dict[str, Any]:
        result = await mcp_service.call_tool(
            "extract_links",
            {"html_content": html_content, "base_url": base_url},
        )
        return self._normalize_result(result)

    def _normalize_result(self, result: Any) -> Dict[str, Any]:
        if hasattr(result, "structured_content"):
            return result.structured_content
        if hasattr(result, "data"):
            return result.data
        if isinstance(result, dict):
            return result
        logger.warning("Unexpected MCP tool result type: %s", type(result))
        return {"success": False, "error": "Unknown result format"}


crawler_tools = CrawlerToolsClient()
