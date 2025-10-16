from fastmcp import FastMCP
import asyncio
from playwright.async_api import async_playwright
import base64
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
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


# ============================================================================
# ARI TOOLS MIGRATION (from ari_service.py) - HTML 본문 추출/마크다운/JSON 변환
# ============================================================================

def _ari_extract_urls(content_element) -> List[Dict[str, str]]:
    try:
        urls: List[Dict[str, str]] = []
        for link in content_element.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if href and text:
                urls.append({'text': text, 'href': href})
        return urls
    except Exception:
        return []


def _ari_extract_pagetree(pagetree_element) -> List[Dict[str, Any]]:
    def extract_page_info(li_element) -> Optional[Dict[str, Any]]:
        span = li_element.find('span', class_='plugin_pagetree_children_span')
        if not span:
            return None
        link = span.find('a', href=lambda x: x and ('viewpage.action' in x or '/display/' in x))
        if not link:
            return None
        page_info: Dict[str, Any] = {
            'text': link.text.strip(),
            'href': link.get('href', '')
        }
        if 'pageId=' in page_info['href']:
            import re as _re
            match = _re.search(r'pageId=(\d+)', page_info['href'])
            if match:
                page_info['page_id'] = match.group(1)
        children_container = li_element.find('div', class_='plugin_pagetree_children_container')
        if children_container:
            children_ul = children_container.find('ul', class_='plugin_pagetree_children_list')
            if children_ul:
                children: List[Dict[str, Any]] = []
                for child_li in children_ul.find_all('li', recursive=False):
                    child_info = extract_page_info(child_li)
                    if child_info:
                        children.append(child_info)
                if children:
                    page_info['children'] = children
        return page_info

    main_ul = pagetree_element.find('ul', class_='plugin_pagetree_children_list')
    if not main_ul:
        return []
    result: List[Dict[str, Any]] = []
    for li in main_ul.find_all('li', recursive=False):
        info = extract_page_info(li)
        if info:
            result.append(info)
    return result


def _ari_extract_clean_html(html_content: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    elements_to_remove = [
        'header', 'footer', 'nav', 'aside', 'sidebar',
        '.header', '.footer', '.nav', '.aside', '.sidebar',
        '.navigation', '.menu',
        'div.aui-page-header-actions', 'div.page-actions', 'div.aui-toolbar2',
        'div.comment-container', 'div.like-button-container', 'div.page-labels',
        'div.comment-actions', 'span.st-table-filter', 'svg',
        'div.confluence-information-macro', 'div.aui-message', 'div.page-metadata-modification-info',
        '.aui-page-header-actions', '.like-button-container', '.page-labels',
        'div#page-metadata-banner', 'ul.banner',
    ]
    for selector in elements_to_remove:
        for el in soup.select(selector):
            el.decompose()

    result_parts: List[str] = []
    title_element = soup.find('h1', {'id': 'title-text'})
    if title_element:
        result_parts.append(f"<h1>{title_element.decode_contents()}</h1>")
    breadcrumb_element = soup.find('ol', {'id': 'breadcrumbs'})
    if breadcrumb_element:
        result_parts.append(f"<nav aria-label='이동 경로'>{breadcrumb_element.decode_contents()}</nav>")
    else:
        breadcrumb_alt = soup.find('div', class_='breadcrumbs')
        if breadcrumb_alt:
            result_parts.append(f"<nav aria-label='이동 경로'>{breadcrumb_alt.decode_contents()}</nav>")

    main_content = soup.find('div', {'id': 'main-content'})
    if not main_content:
        main_content = soup.find('div', {'class': 'wiki-content'})
    if not main_content:
        main_content = soup.find('main') or soup.find('body') or soup
    if main_content:
        try:
            main_html = main_content.decode_contents() if hasattr(main_content, 'decode_contents') else str(main_content)
            result_parts.append(main_html)
        except Exception:
            result_parts.append(str(main_content))
    return '\n'.join(result_parts)


def _ari_parse_tables(root) -> Dict[str, Any]:
    from bs4 import BeautifulSoup
    structured: List[Dict[str, Any]] = []
    markdowns: List[str] = []

    def extract_text(el) -> str:
        text = el.get_text(separator=' ', strip=True) or ''
        return text.strip()

    def limit_text(text: str, limit: int = None) -> str:
        return text if text else ""

    def get_table_rows(table_el) -> List[Any]:
        rows: List[Any] = []
        for sec_name in ['thead', 'tbody', 'tfoot']:
            for sec in table_el.find_all(sec_name, recursive=False):
                rows.extend(sec.find_all('tr', recursive=False))
        rows.extend(table_el.find_all('tr', recursive=False))
        return rows

    def build_grid(table_el) -> Dict[str, Any]:
        rows = get_table_rows(table_el)
        grid: List[List[str]] = []
        span_map: Dict[tuple, Dict[str, int]] = {}
        max_cols = 0
        for r_idx, tr in enumerate(rows):
            if len(grid) <= r_idx:
                grid.append([])
            c_idx = 0
            while (r_idx, c_idx) in span_map:
                grid[r_idx].append('')
                span_map[(r_idx, c_idx)]['remaining_rowspan'] -= 1
                if span_map[(r_idx, c_idx)]['remaining_rowspan'] > 0:
                    span_map[(r_idx + 1, c_idx)] = span_map[(r_idx, c_idx)].copy()
                del span_map[(r_idx, c_idx)]
                c_idx += 1
            for cell in tr.find_all(['td', 'th'], recursive=False):
                cell_text = extract_text(cell)
                rowspan = int(cell.get('rowspan', 1) or 1)
                colspan = int(cell.get('colspan', 1) or 1)
                grid[r_idx].append(cell_text)
                c_idx += 1
                for _ in range(colspan - 1):
                    grid[r_idx].append('')
                    c_idx += 1
                if rowspan > 1:
                    for rs in range(1, rowspan):
                        for cs in range(colspan):
                            span_map[(r_idx + rs, (c_idx - colspan) + cs)] = {
                                'text': cell_text,
                                'remaining_rowspan': rowspan - rs
                            }
            max_cols = max(max_cols, len(grid[r_idx]))
        for r in grid:
            if len(r) < max_cols:
                r.extend([''] * (max_cols - len(r)))
        col_count = max_cols
        used: List[bool] = [False] * col_count
        for row in grid:
            for idx, val in enumerate(row):
                if idx < col_count and (val or '').strip():
                    used[idx] = True
        keep_indices = [i for i, u in enumerate(used) if u]
        if keep_indices:
            grid = [[row[i] for i in keep_indices] for row in grid]
            max_cols = len(keep_indices)
        return {'grid': grid, 'cols': max_cols}

    def is_header_cell(cell) -> bool:
        if cell.name == 'th':
            return True
        if cell.name == 'td':
            strong_tags = cell.find_all(['strong', 'b'])
            if strong_tags:
                cell_text = extract_text(cell).strip()
                strong_text = ' '.join(extract_text(tag).strip() for tag in strong_tags)
                if strong_text and len(strong_text) >= len(cell_text) * 0.7:
                    return True
            cell_classes = cell.get('class', [])
            if any('highlight' in str(cls) for cls in cell_classes):
                return True
        return False

    def detect_headers(table_el, grid_obj) -> Dict[str, Any]:
        header_rows: List[List[str]] = []
        thead = table_el.find('thead')
        if thead and thead.find_all('tr'):
            for tr in thead.find_all('tr', recursive=False):
                if tr.find_all(['th', 'td']):
                    expanded: List[str] = []
                    for cell in tr.find_all(['th', 'td'], recursive=False):
                        txt = extract_text(cell)
                        span = int(cell.get('colspan', 1) or 1)
                        expanded.extend([txt] * max(1, span))
                    header_rows.append(expanded)
        else:
            body_rows: List[Any] = []
            for tbody in table_el.find_all('tbody', recursive=False):
                body_rows.extend(tbody.find_all('tr', recursive=False))
            if not body_rows:
                body_rows = table_el.find_all('tr', recursive=False)
            max_scan = min(3, len(body_rows))
            collected = 0
            for i, tr in enumerate(body_rows[:max_scan]):
                cells = tr.find_all(['th', 'td'], recursive=False)
                if not cells:
                    continue
                is_likely_header = False
                if any(is_header_cell(c) for c in cells):
                    is_likely_header = True
                elif i == 0 and any(int(c.get('rowspan', 1) or 1) > 1 or int(c.get('colspan', 1) or 1) > 1 for c in cells):
                    is_likely_header = True
                if is_likely_header and collected < 3:
                    expanded: List[str] = []
                    for cell in cells:
                        txt = extract_text(cell).strip()
                        if txt == '　' or not txt:
                            txt = ''
                        span = int(cell.get('colspan', 1) or 1)
                        expanded.extend([txt] * max(1, span))
                    header_rows.append(expanded)
                    collected += 1
                elif collected > 0:
                    break
        cols = grid_obj['cols']
        if not header_rows:
            headers = [f"컬럼{i+1}" for i in range(cols)]
            return {'headers': headers, 'header_rows_count': 0}
        norm_rows: List[List[str]] = []
        for row in header_rows:
            row = row[:cols] + [''] * max(0, cols - len(row))
            norm_rows.append(row)
        headers: List[str] = []
        for c in range(cols):
            name_parts: List[str] = []
            for r in range(len(norm_rows)):
                if norm_rows[r][c] and norm_rows[r][c].strip():
                    name_parts.append(norm_rows[r][c].strip())
            if name_parts:
                unique_parts: List[str] = []
                for part in name_parts:
                    if part not in unique_parts:
                        unique_parts.append(part)
                if len(unique_parts) == 1:
                    name = unique_parts[0]
                else:
                    name = ' > '.join(unique_parts)
            else:
                name = f"컬럼{c+1}"
            headers.append(name)
        return {'headers': headers, 'header_rows_count': len(norm_rows)}

    def preprocess_markdown_text(text: str) -> str:
        if not text:
            return text
        text = text.replace('|', '\\|')
        text = text.replace('*', '\\*')
        text = text.replace('_', '\\_')
        text = text.replace('#', '\\#')
        text = text.replace('[', '\\[')
        text = text.replace(']', '\\]')
        text = text.replace('`', '\\`')
        return text

    def grid_to_markdown(grid_obj, headers: List[str], header_rows_count: int, title: Optional[str]) -> str:
        lines: List[str] = []
        if title:
            lines.append(f"### {title}")
            lines.append("")
        processed_headers = [preprocess_markdown_text(h) for h in headers]
        lines.append('|' + '|'.join(processed_headers) + '|')
        lines.append('|' + '|'.join(' --- ' for _ in headers) + '|')
        data_rows = grid_obj['grid'][header_rows_count if header_rows_count > 0 else 1:]
        for row in data_rows:
            preview_vals = [preprocess_markdown_text(limit_text(str(v))) for v in row[:len(headers)]]
            if all(v.strip() == '' for v in preview_vals):
                continue
            lines.append('|' + '|'.join(preview_vals) + '|')
        lines.append("")
        return '\n'.join(lines)

    table_index = 0
    for tbl in root.find_all('table'):
        try:
            table_index += 1
            grid_obj = build_grid(tbl)
            header_info = detect_headers(tbl, grid_obj)
            headers = header_info['headers']
            header_rows_count = header_info['header_rows_count']
            table_name = f"테이블 {table_index}"
            caption = tbl.find('caption')
            if caption:
                cap = extract_text(caption)
                if cap:
                    table_name = cap
            markdowns.append(grid_to_markdown(grid_obj, headers, header_rows_count, table_name))
        except Exception as e:
            logger.warning(f"Table parse failed at index {table_index}: {e}")
            continue
    return {'structured': structured, 'markdown': markdowns}


def _ari_extract_markdown(html_content: str) -> str:
    import tempfile
    from bs4 import BeautifulSoup
    cleaned_html = _ari_extract_clean_html(html_content)
    soup = BeautifulSoup(cleaned_html, 'html.parser')
    table_markdowns: List[str] = []
    try:
        parsed_tables = _ari_parse_tables(soup)
        table_markdowns = parsed_tables.get('markdown', [])
    except Exception as e:
        logger.warning(f"Table parsing failed: {e}")
    for table in soup.find_all('table'):
        table.decompose()
    remaining_html = str(soup)
    remaining_markdown = ""
    try:
        import pymupdf4llm  # type: ignore
        if remaining_html.strip():
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_html:
                    full_html = f"""<!DOCTYPE html>\n<html>\n<head>\n    <meta charset=\"UTF-8\">\n</head>\n<body>\n    {remaining_html}\n</body>\n</html>"""
                    temp_html.write(full_html)
                    temp_html_path = temp_html.name
                markdown_result = pymupdf4llm.to_markdown(temp_html_path)
                try:
                    import os as _os
                    _os.unlink(temp_html_path)
                except Exception:
                    pass
                if markdown_result and str(markdown_result).strip():
                    remaining_markdown = str(markdown_result)
            except Exception as e:
                logger.warning(f"pymupdf4llm conversion failed: {e}")
                try:
                    if 'temp_html_path' in locals():
                        import os as _os
                        _os.unlink(temp_html_path)
                except Exception:
                    pass
    except Exception:
        pass
    if not remaining_markdown:
        try:
            from markdownify import markdownify as md_convert
            remaining_markdown = md_convert(remaining_html, heading_style="ATX", strip=['style', 'script'])
        except Exception as e:
            logger.warning(f"markdownify failed: {e}")
    if not remaining_markdown:
        try:
            soup_remaining = BeautifulSoup(remaining_html, 'html.parser')
            remaining_markdown = soup_remaining.get_text('\n', strip=True)
        except Exception:
            remaining_markdown = remaining_html
    result_parts: List[str] = []
    if remaining_markdown.strip():
        result_parts.append(remaining_markdown.strip())
    if table_markdowns:
        for i, table_md in enumerate(table_markdowns):
            if i > 0:
                result_parts.append("")
            result_parts.append(table_md.strip())
    return '\n\n'.join(result_parts) if result_parts else ""


def _ari_extract_main_content(html_content: str) -> Dict[str, Any]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    page_title = ""
    breadcrumbs: List[Dict[str, str]] = []
    urls: List[Dict[str, str]] = []
    pagetree: List[Dict[str, Any]] = []
    title_element = soup.find('h1', {'id': 'title-text'})
    if title_element:
        page_title = title_element.get_text(strip=True)
    breadcrumb_element = soup.find('ol', {'id': 'breadcrumbs'})
    if breadcrumb_element:
        for li in breadcrumb_element.find_all('li'):
            if li.get('id') == 'ellipsis':
                continue
            link = li.find('a')
            if link:
                breadcrumbs.append({'text': link.get_text(strip=True), 'href': link.get('href', '')})
            else:
                span = li.find('span')
                if span:
                    breadcrumbs.append({'text': span.get_text(strip=True), 'href': ''})
    pagetree_element = soup.find('div', {'class': 'ia-secondary-content'})
    if pagetree_element:
        pagetree = _ari_extract_pagetree(pagetree_element)
    main_content = soup.find('div', {'id': 'main-content'})
    if not main_content:
        main_content = soup.find('div', {'class': 'wiki-content'})
    if not main_content:
        main_content = soup.find('main') or soup.find('body') or soup
    if main_content:
        urls = _ari_extract_urls(main_content)
    elements_to_remove = [
        'header', 'footer', 'nav', 'aside', 'sidebar',
        '.header', '.footer', '.nav', '.aside', '.sidebar',
        '.navigation', '.menu',
        'div.aui-page-header-actions', 'div.page-actions', 'div.aui-toolbar2',
        'div.comment-container', 'div.like-button-container', 'div.page-labels',
        'div.comment-actions', 'span.st-table-filter', 'svg',
        'div.confluence-information-macro', 'div.aui-message', 'div.page-metadata-modification-info',
        '.aui-page-header-actions', '.like-button-container', '.page-labels',
        'div#page-metadata-banner', 'ul.banner',
    ]
    for selector in elements_to_remove:
        for element in soup.select(selector):
            element.decompose()
    main_content = soup.find('div', {'id': 'main-content'})
    if not main_content:
        main_content = soup.find('div', {'class': 'wiki-content'})
    if not main_content:
        main_content = soup.find('main')
    if not main_content:
        main_content = soup.find('body')
    if not main_content:
        main_content = soup
    text_content = main_content.get_text(separator=' ', strip=True)
    title = soup.find('title')
    title_text = title.get_text(strip=True) if title else ""
    if not page_title:
        page_title = title_text
    images: List[Dict[str, Any]] = []
    structured_tables: List[Dict[str, Any]] = []
    tables_markdown: List[str] = []
    attachments: List[Dict[str, Any]] = []
    comments: List[Dict[str, Any]] = []
    result = {
        'title': page_title or title_text,
        'breadcrumbs': breadcrumbs,
        'content': {
            'text': text_content
        },
        'metadata': {
            'img': images,
            'urls': urls,
            'pagetree': pagetree,
            'extracted_at': datetime.now().isoformat(),
            'content_length': len(text_content),
            'tables_markdown': tables_markdown,
            'structured_tables': structured_tables,
            'attachments': attachments,
            'comments': comments
        }
    }
    return result


def _ari_markdown_to_json(markdown_content: str) -> Dict[str, Any]:
    import re as _re
    try:
        if markdown_content is None:
            return {"success": False, "error": "마크다운이 비어있습니다"}
        lines = markdown_content.splitlines()
        contents: List[Dict[str, Any]] = []
        buffer: List[str] = []
        current_title: str = ""
        idx = 0
        i = 0
        def flush_text_buffer():
            nonlocal idx, buffer
            if buffer and any(s.strip() for s in buffer):
                text = "\n".join([s.rstrip() for s in buffer]).strip()
                if text:
                    idx += 1
                    contents.append({
                        "id": idx,
                        "type": "text",
                        "title": current_title,
                        "data": text
                    })
            buffer = []
        while i < len(lines):
            line = lines[i]
            if _re.match(r"^\s*#{1,6}\s+", line):
                flush_text_buffer()
                current_title = _re.sub(r"^\s*#{1,6}\s+", "", line).strip()
                i += 1
                continue
            if '|' in line:
                header_candidate = line.strip()
                if i + 1 < len(lines):
                    separator = lines[i + 1].strip()
                    if _re.match(r"^\|\s*:?\-+\s*(\|\s*:?\-+\s*)+\|$", separator):
                        flush_text_buffer()
                        raw_headers = [h.strip() for h in header_candidate.strip('|').split('|')]
                        headers = [h for h in raw_headers if h != ""]
                        i += 2
                        rows: List[Dict[str, Any]] = []
                        row_id = 0
                        while i < len(lines) and '|' in lines[i] and not _re.match(r"^\s*#", lines[i]):
                            row_line = lines[i].strip()
                            if not row_line:
                                break
                            raw_cells = [c.strip() for c in row_line.strip('|').split('|')]
                            while len(raw_cells) < len(headers):
                                raw_cells.append("")
                            data = {headers[j]: raw_cells[j] if j < len(raw_cells) else "" for j in range(len(headers))}
                            row_id += 1
                            rows.append({"row_id": row_id, "data": data})
                            i += 1
                        idx += 1
                        contents.append({
                            "id": idx,
                            "type": "table",
                            "headers": headers,
                            "rows": rows
                        })
                        continue
            if not line.strip():
                flush_text_buffer()
                i += 1
                continue
            buffer.append(line)
            i += 1
        flush_text_buffer()
        return {"success": True, "contents": contents}
    except Exception as e:
        logger.error(f"ari_markdown_to_json 실패: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def ari_extract_main_content(html_content: str) -> Dict[str, Any]:
    try:
        result = _ari_extract_main_content(html_content or "")
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"ari_extract_main_content 실패: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def ari_extract_markdown(html_content: str) -> Dict[str, Any]:
    try:
        md_text = _ari_extract_markdown(html_content or "")
        return {"success": True, "markdown": md_text, "length": len(md_text)}
    except Exception as e:
        logger.error(f"ari_extract_markdown 실패: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def ari_markdown_to_json(markdown_content: str) -> Dict[str, Any]:
    try:
        return _ari_markdown_to_json(markdown_content)
    except Exception as e:
        logger.error(f"ari_markdown_to_json 실패: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
async def ari_process_html_files_complete(files: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    여러 HTML 파일(Base64) 입력을 받아 완전 처리(본문 추출 + 마크다운 + JSON 구조화) 결과 반환
    files: [{"filename": str, "content_base64": str}]
    """
    import base64 as _b64
    import uuid as _uuid
    processed_files: List[Dict[str, Any]] = []
    total_size = 0
    try:
        for file in files or []:
            try:
                filename = file.get('filename') or 'unknown.html'
                b64 = file.get('content_base64') or ''
                raw_bytes = _b64.b64decode(b64) if b64 else b''
                total_size += len(raw_bytes)
                html_content = raw_bytes.decode('utf-8', errors='ignore')
                file_id = str(_uuid.uuid4())
                basic_data = _ari_extract_main_content(html_content)
                markdown_content = _ari_extract_markdown(html_content)
                json_result = _ari_markdown_to_json(markdown_content)
                contents = json_result.get('contents', []) if json_result.get('success') else []
                if not contents:
                    contents = [{"id": 1, "type": "text", "title": "", "data": markdown_content}]
                processed_data = {
                    'title': basic_data.get('title', ''),
                    'breadcrumbs': basic_data.get('breadcrumbs', []),
                    'content': {
                        'text': basic_data['content']['text'],
                        'markdown': markdown_content,
                        'contents': contents
                    },
                    'metadata': {
                        **basic_data.get('metadata', {}),
                        'markdown_length': len(markdown_content),
                        'contents_count': len(contents)
                    }
                }
                processed_files.append({
                    'original_filename': filename,
                    'file_id': file_id,
                    'size': len(raw_bytes),
                    'processed_data': processed_data,
                    'contents': contents,
                    'markdown': markdown_content,
                    'upload_time': datetime.now().isoformat()
                })
            except Exception as fe:
                logger.error(f"파일 처리 실패 {file}: {fe}")
                processed_files.append({
                    'original_filename': file.get('filename'),
                    'error': str(fe),
                    'success': False
                })
        return {
            'success': True,
            'processed_files': processed_files,
            'total_files': len(processed_files),
            'total_size': total_size,
            'message': f"{len(processed_files)}개의 HTML 파일이 성공적으로 완전 처리되었습니다"
        }
    except Exception as e:
        logger.error(f"ari_process_html_files_complete 실패: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': f"HTML 파일 완전 처리 중 오류가 발생했습니다: {str(e)}"
        }

async def main():
    # Start MCP server
    await mcp.run_async(
        transport="http",
        host="0.0.0.0",
        port=4200,
        path="/my-custom-path",
        log_level="debug",
    )

if __name__ == "__main__":
    asyncio.run(main())