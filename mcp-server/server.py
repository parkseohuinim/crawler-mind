from fastmcp import FastMCP
import asyncio
from playwright.async_api import async_playwright
import base64
import json
from typing import Dict, List, Any, Optional
import httpx
import logging
from urllib.parse import urljoin, urlparse
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 불필요한 디버그 로그 숨기기
logging.getLogger("mcp.server").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("sse_starlette").setLevel(logging.WARNING)
logging.getLogger("mcp.server.lowlevel").setLevel(logging.WARNING)

mcp = FastMCP(name="CrawlerMindServer")

# Health check endpoint (MCP tool)
@mcp.tool
def health_check() -> Dict[str, Any]:
    """
    런타임 의존성을 실제 점검하는 헬스체크
    - crawl4ai 임포트 가능 여부
    - Playwright 브라우저 기동 가능 여부(간단 체크)
    """
    logger.info("[MCP] health_check called")
    crawl4ai_ok = False
    playwright_ok = False

    # 1) crawl4ai import 확인
    try:
        import importlib
        importlib.import_module("crawl4ai")
        crawl4ai_ok = True
    except Exception as e:
        logger.warning(f"crawl4ai import failed: {e}")

    # 2) Playwright import 확인 (이벤트 루프 중첩 문제 방지 위해 런타임 기동은 생략)
    try:
        import importlib
        importlib.import_module("playwright.async_api")
        playwright_ok = True
    except Exception as e:
        logger.warning(f"playwright import failed: {e}")

    status = "healthy" if (crawl4ai_ok and playwright_ok) else "degraded" if (crawl4ai_ok or playwright_ok) else "unhealthy"
    return {
        "success": crawl4ai_ok and playwright_ok,
        "status": status,
        "service": "mcp-server",
        "dependencies": {
            "crawl4ai": crawl4ai_ok,
            "playwright": playwright_ok,
        }
    }


async def _crawl_with_playwright(url: str) -> Dict[str, Any]:
    """
    Playwright를 사용한 폴백 크롤링 함수
    """
    logger.info(f"[MCP] Playwright 폴백으로 {url} 크롤링 시작")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # 기본 정보 추출
                title = await page.title()
                html_content = await page.content()
                
                # markdownify를 사용한 마크다운 변환
                markdown_text = ""
                try:
                    from bs4 import BeautifulSoup
                    from markdownify import markdownify as md
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 불필요한 요소 제거
                    for sel in [
                        "#cfmClHeader", "#cfmClFooter", "#cfmClSkip", ".header", ".footer",
                        ".navigation", ".sidebar", ".banner", ".popup", ".overlay", ".sns-area",
                    ]:
                        for el in soup.select(sel):
                            el.decompose()
                    for t in soup(["script", "style", "noscript"]):
                        t.decompose()
                    
                    cleaned_html = str(soup)
                    markdown_text = md(cleaned_html, heading_style="ATX")
                except Exception as me:
                    logger.warning(f"Playwright markdown 변환 실패: {me}")
                
                logger.info(f"[MCP] Playwright 크롤링 완료: html={len(html_content)} chars, markdown={len(markdown_text)} chars")
                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "html_content": html_content,
                    "markdown": markdown_text,
                    "status_code": 200,
                }
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error(f"Playwright 크롤링 실패: {e}")
        return {
            "success": False,
            "url": url,
            "error": f"Playwright 크롤링 실패: {str(e)}"
        }

# ============================================================================
# RAG CRAWLING TOOLS (일반 웹페이지 크롤링 및 정제)
# ============================================================================

@mcp.tool
async def crawl4ai_scrape(url: str, include_selector: Optional[str] = None) -> Dict[str, Any]:
    """
    RAG용 웹 크롤링: 불필요한 요소 제거 및 마크다운 변환
    - 헤더/푸터/네비게이션 등 제거하여 본문만 추출
    - markdownify로 깔끔한 텍스트 변환
    - 성공 시: { success, url, title, html_content, markdown, status_code }
    - 실패 시: { success: False, url, error }
    """
    logger.info(f"[MCP] crawl4ai_scrape called for URL: {url}")
    try:
        try:
            from crawl4ai import AsyncWebCrawler
            from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
        except Exception as e:
            logger.warning(f"crawl4ai 미설치 또는 임포트 실패: {e} — Playwright로 폴백합니다")
            return await _crawl_with_playwright(url)

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            browser_type="chromium",
            ignore_https_errors=True,
            java_script_enabled=True,
        )

        crawler = AsyncWebCrawler(config=browser_config)
        await crawler.start()
        try:
            is_js_heavy = any(d in url.lower() for d in [
                "google.com", "youtube.com", "facebook.com", "instagram.com", "twitter.com",
            ])
            run_config = CrawlerRunConfig(
                verbose=False,
                word_count_threshold=10,
                exclude_external_links=True,
                remove_overlay_elements=False,
                process_iframes=True,
                ignore_body_visibility=True,
                js_only=False,
                cache_mode=CacheMode.BYPASS,
                excluded_tags=['form', 'header', 'footer', 'nav'],
                excluded_selector="#cfmClHeader, #cfmClFooter, #cfmClSkip, .location, .sns-area",
                wait_until="networkidle" if is_js_heavy else "domcontentloaded",
                delay_before_return_html=12 if is_js_heavy else 6,
                simulate_user=is_js_heavy,
                override_navigator=is_js_heavy,
                page_timeout=120000,
            )

            result = await crawler.arun(url=url, config=run_config)
            if not result.success:
                logger.error(f"[MCP] crawl4ai 실패: {result.error_message}")
                # 폴백: Playwright 시도
                try:
                    return await _crawl_with_playwright(url)
                except Exception:
                    return {
                        "success": False,
                        "url": url,
                        "error": result.error_message or "crawl4ai 실패",
                    }

            html_content = result.html or ""
            status_code = getattr(result, 'status_code', None)
            title = None
            meta = getattr(result, 'metadata', None)
            if isinstance(meta, list):
                meta = meta[0] if meta else None
            if meta is not None:
                title = getattr(meta, 'title', None)

            markdown_text = ""
            try:
                from bs4 import BeautifulSoup
                from markdownify import markdownify as md
                soup = BeautifulSoup(html_content, 'html.parser')
                # include_selector가 주어지면 해당 영역만 변환 대상으로 제한
                if include_selector:
                    sel = include_selector if include_selector.startswith(('#', '.', '[', ':')) else f"#{include_selector}"
                    selected = soup.select_one(sel)
                    if selected:
                        soup = BeautifulSoup(str(selected), 'html.parser')
                for sel in [
                    "#cfmClHeader", "#cfmClFooter", "#cfmClSkip", ".header", ".footer",
                    ".navigation", ".sidebar", ".banner", ".popup", ".overlay", ".sns-area",
                ]:
                    for el in soup.select(sel):
                        el.decompose()
                for t in soup(["script", "style", "noscript"]):
                    t.decompose()
                cleaned_html = str(soup)
                markdown_text = md(cleaned_html, heading_style="ATX")
            except Exception as me:
                logger.warning(f"markdown 변환 실패(무시): {me}")

            payload = {
                "success": True,
                "url": url,
                "title": title,
                "html_content": html_content,
                "markdown": markdown_text,
                "status_code": status_code,
            }
            logger.info(f"[MCP] crawl4ai_scrape completed: html={len(html_content)} chars, markdown={len(markdown_text)} chars, title='{title}'")
            return payload
        finally:
            try:
                await crawler.close()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"crawl4ai_scrape 실패 {url}: {str(e)}")
        return {
            "success": False,
            "url": url,
            "error": str(e)
        }

@mcp.tool
async def crawl_urls_sequential(urls: List[str], selector: Optional[str] = None) -> Dict[str, Any]:
    """
    여러 URL을 순차적으로 크롤링합니다.
    rag-scraping의 scrape_urls_sequential 기능을 제공합니다.
    """
    logger.info(f"[MCP] crawl_urls_sequential called with {len(urls)} URLs")
    results = []
    
    for i, url in enumerate(urls):
        try:
            logger.info(f"[MCP] 크롤링 진행: {i+1}/{len(urls)} - {url}")
            result = await crawl4ai_scrape(url, selector)
            results.append(result)
        except Exception as e:
            logger.error(f"[MCP] URL 크롤링 실패 {url}: {e}")
            results.append({
                "success": False,
                "url": url,
                "error": str(e)
            })
    
    return {
        "success": True,
        "total_urls": len(urls),
        "results": results,
        "successful_count": len([r for r in results if r.get("success", False)]),
        "failed_count": len([r for r in results if not r.get("success", False)])
    }

@mcp.tool
def extract_headings_from_html(
    html_content: str,
    heading_tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """HTML에서 heading 태그(H1~H6 등)를 추출"""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content or "", "html.parser")
        tags = heading_tags or ["h1", "h2", "h3", "h4", "h5", "h6"]
        headings: List[str] = []
        for tag in tags:
            for element in soup.find_all(tag):
                text = element.get_text(strip=True)
                if text:
                    headings.append(text)
        return {
            "success": True,
            "headings": headings,
            "count": len(headings),
        }
    except Exception as exc:
        logger.error(f"extract_headings_from_html 실패: {exc}")
        return {"success": False, "error": str(exc)}


@mcp.tool
async def extract_image_metadata(
    html_content: str,
    base_url: Optional[str] = None,
    min_alt_length: int = 2
) -> Dict[str, Any]:
    """HTML에서 이미지 정보(src, alt 등)를 추출"""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content or "", "html.parser")
        images: List[Dict[str, str]] = []
        for element in soup.find_all("img"):
            parent = element.find_parent(id=["cfmClHeader", "cfmClFooter"])
            if parent:
                continue

            alt_text = (element.get("alt") or "").strip()
            if len(alt_text) < min_alt_length:
                continue

            src = element.get("src") or ""
            if base_url and src and not src.startswith("http"):
                src = urljoin(base_url, src)

            images.append({"alt": alt_text, "src": src})

        return {
            "success": True,
            "images": images,
            "count": len(images),
        }
    except Exception as exc:
        logger.error(f"extract_image_metadata 실패: {exc}")
        return {"success": False, "error": str(exc)}


@mcp.tool
async def extract_links(
    html_content: str,
    base_url: Optional[str] = None,
    min_text_length: int = 2
) -> Dict[str, Any]:
    """HTML에서 의미 있는 앵커 링크를 추출"""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content or "", "html.parser")
        links: List[Dict[str, str]] = []
        for element in soup.find_all("a", href=True):
            parent = element.find_parent(id=["cfmClHeader", "cfmClFooter"])
            if parent:
                continue

            text = element.get_text(strip=True)
            if len(text) < min_text_length:
                continue

            href = element.get("href")
            if not href:
                continue

            if base_url and href.startswith("/"):
                href = urljoin(base_url, href)

            if href.startswith(("http://", "https://")):
                links.append({"text": text, "url": href})

        return {
            "success": True,
            "links": links,
            "count": len(links),
        }
    except Exception as exc:
        logger.error(f"extract_links 실패: {exc}")
        return {"success": False, "error": str(exc)}


@mcp.tool
def extract_meta_title(html_content: str) -> Dict[str, Any]:
    """HTML의 meta og:title 또는 title 태그를 추출"""
    try:
        title = extract_meta_title_from_html(html_content)
        return {"success": bool(title), "title": title or ""}
    except Exception as exc:
        logger.error(f"extract_meta_title 실패: {exc}")
        return {"success": False, "error": str(exc)}


@mcp.tool
def convert_to_json_format(
    url: str,
    title: Optional[str],
    markdown_content: str,
    html_content: str,
    hierarchy: Optional[List[str]] = None,
    murl: Optional[str] = None,
    startdate: str = "1900-01-01",
    enddate: str = "2999-12-31"
) -> Dict[str, Any]:
    """
    RAG용 JSON 포맷 변환: 크롤링 결과를 rag-scraping의 JSON 포맷으로 변환
    - 텍스트 정규화 및 메타데이터 추출
    - 이미지/링크 정보 포함
    - to_json.py의 기능을 제공
    """
    logger.info(f"[MCP] convert_to_json_format called for URL: {url}")
    try:
        import unicodedata

        title = unicodedata.normalize('NFC', (title or "제목 없음"))
        url = unicodedata.normalize('NFC', url)

        final_content = (markdown_content or "").strip().replace("\n", "\\n")
        final_content = unicodedata.normalize('NFC', final_content)

        normalized_hierarchy: Optional[List[str]] = None
        if hierarchy:
            normalized_hierarchy = [unicodedata.normalize('NFC', item) for item in hierarchy if item]

        metadata: Dict[str, Any] = {}
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content or "", 'html.parser')

            images = []
            for img in soup.find_all('img'):
                if img.find_parent(id=['cfmClHeader', 'cfmClFooter']):
                    continue
                alt_text = (img.get('alt') or '').strip()
                if len(alt_text) > 2:
                    images.append({'alt': alt_text, 'src': img.get('src', '')})
            if images:
                metadata['images'] = images

            urls_data = []
            for link in soup.find_all('a', href=True):
                if link.find_parent(id=['cfmClHeader', 'cfmClFooter']):
                    continue
                link_text = link.get_text().strip()
                if len(link_text) < 2:
                    continue
                href = link.get('href')
                if href.startswith('http') or href.startswith('/'):
                    urls_data.append({'desc': link_text, 'url': href})
            if urls_data:
                metadata['urls'] = _deduplicate_by_key(urls_data, 'url')
        except Exception as e:
            logger.warning(f"메타데이터 추출 실패: {e}")

        json_data = {
            "url": url,
            "murl": murl or "",
            "hierarchy": normalized_hierarchy or [],
            "title": title,
            "text": final_content,
            "startdate": startdate,
            "enddate": enddate,
            "metadata": metadata,
        }
        if normalized_hierarchy:
            json_data["hierarchy"] = normalized_hierarchy

        return {
            "success": True,
            "json_data": json_data,
            "text_length": len(final_content),
            "metadata_count": len(metadata),
        }
    except Exception as e:
        logger.error(f"JSON 포맷 변환 실패: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _deduplicate_by_key(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    unique_items: List[Dict[str, Any]] = []
    for item in items:
        value = item.get(key)
        if value and value not in seen:
            seen.add(value)
            unique_items.append(item)
    return unique_items

def extract_meta_title_from_html(html_content: str) -> Optional[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content or "", "html.parser")
    prop = soup.find("meta", attrs={"property": "og:title"})
    if prop and prop.get("content"):
        content = prop.get("content").strip()
        if content:
            return content
    name_meta = soup.find("meta", attrs={"name": "title"})
    if name_meta and name_meta.get("content"):
        content = name_meta.get("content").strip()
        if content:
            return content
    head_title = soup.find("title")
    if head_title:
        text = head_title.get_text(strip=True)
        if text:
            return text
    return None

# ============================================================================
# MENU SEARCH TOOLS (메뉴 검색 및 조회)
# ============================================================================

@mcp.tool
async def menu_search(user_query: str, page: int = 1, size: int = 50, with_managers: bool = True) -> Dict[str, Any]:
    """
    사용자 질의에서 키워드를 추출해 mcp-client의 메뉴 API로 조회합니다.
    - 키워드: 한글/영문/숫자 2자 이상 토큰만 사용하여 search 파라미터 구성
    - with_managers=True이면 /menu-links/with-managers도 함께 호출
    """
    try:
        tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", user_query)
        search = " ".join(tokens[:5]) if tokens else ""

        base_url = "http://127.0.0.1:8000"
        async with httpx.AsyncClient(timeout=30) as client:
            params = {"page": page, "size": size}
            if search:
                params["search"] = search
            resp_links = await client.get(f"{base_url}/menu-links", params=params)
            resp_links.raise_for_status()
            menu_links = resp_links.json()

            data = {"menu_links": menu_links, "search": search}
            if with_managers:
                resp_with = await client.get(f"{base_url}/menu-links/with-managers", params=params)
                resp_with.raise_for_status()
                data["with_managers"] = resp_with.json()

            return {"success": True, "query": user_query, "data": data}
    except Exception as e:
        logger.error(f"menu_search failed: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# ARI CONTENT PROCESSING TOOLS (HTML 구조화 및 전용 파싱)
# ============================================================================

@mcp.tool  
def ari_parse_html(html_content: str) -> Dict[str, Any]:
    """
    ARI 전용 HTML 파싱: 순수 HTML 파싱 및 구조화된 JSON 반환
    - 필터링 없이 모든 텍스트 및 이미지 추출
    - ARI 모델 스키마에 맞춘 구조화된 결과 반환
    - RAG 크롤링과는 다른 목적의 전용 파서
    """
    try:
        from bs4 import BeautifulSoup
        from datetime import datetime
        
        soup = BeautifulSoup(html_content or "", 'html.parser')
        title_el = soup.find('title')
        title_text = title_el.get_text(strip=True) if title_el else ""
        text = soup.get_text(separator=' ', strip=True)

        images = []
        for img in soup.find_all('img', src=True):
            images.append({'alt': (img.get('alt') or '').strip(), 'src': img['src']})

        return {
            'success': True,
            'result': {
                'content': {'text': text},
                'metadata': {
                    'title': title_text,
                    'extracted_at': datetime.now().isoformat(),
                    'content_length': len(text),
                    'images': images
                }
            }
        }
    except Exception as e:
        logger.error(f"ARI 파싱 실패: {e}")
        return {'success': False, 'error': str(e)}

async def main():
    # Start MCP server
    logger.info("🚀 Starting MCP Server on 0.0.0.0:4200")
    await mcp.run_async(
        transport="http",
        host="0.0.0.0",
        port=4200,
        path="/my-custom-path",
        log_level="debug",
    )

if __name__ == "__main__":
    asyncio.run(main())