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

@mcp.tool
def summarize_content(text_content: str, max_length: int = 500) -> Dict[str, Any]:
    """
    텍스트 콘텐츠를 요약합니다.
    간단한 추출 요약을 수행합니다.
    """
    try:
        if not text_content.strip():
            return {
                "success": False,
                "error": "텍스트 콘텐츠가 비어있습니다"
            }
        
        # 문장 단위로 분할
        sentences = re.split(r'[.!?]+', text_content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return {
                "success": False,
                "error": "유효한 문장을 찾을 수 없습니다"
            }
        
        # 간단한 추출 요약 (처음 몇 문장)
        summary_sentences = []
        current_length = 0
        
        for sentence in sentences:
            if current_length + len(sentence) > max_length:
                break
            summary_sentences.append(sentence)
            current_length += len(sentence)
        
        summary = '. '.join(summary_sentences)
        if not summary.endswith('.'):
            summary += '.'
        
        return {
            "success": True,
            "summary": summary,
            "original_length": len(text_content),
            "summary_length": len(summary),
            "compression_ratio": len(summary) / len(text_content) if text_content else 0
        }
        
    except Exception as e:
        logger.error(f"요약 생성 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool
async def crawl4ai_scrape(url: str, include_selector: Optional[str] = None) -> Dict[str, Any]:
    """
    Crawl4AI를 사용하여 단건 URL을 스크랩합니다.
    - 성공 시: { success, url, title, html_content, markdown, status_code }
    - 실패 시: { success: False, url, error }
    """
    logger.info(f"[MCP] crawl4ai_scrape called for URL: {url}")
    try:
        try:
            from crawl4ai import AsyncWebCrawler
            from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
        except Exception as e:
            logger.warning(f"crawl4ai 미설치 또는 임포트 실패: {e}")
            return {"success": False, "url": url, "error": f"crawl4ai import failed: {e}"}

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
                logger.error(f"[MCP] crawl4ai 실패: {getattr(result, 'error_message', 'unknown error')}")
                return {
                    "success": False,
                    "url": url,
                    "error": getattr(result, 'error_message', 'crawl4ai 실패')
                }

            html_content = result.html or ""
            status_code = getattr(result, 'status_code', None)
            title = None
            meta = getattr(result, 'metadata', None)
            if isinstance(meta, list):
                meta = meta[0] if meta else None
            if meta is not None:
                title = getattr(meta, 'title', None)

            # 마크다운 변환은 다운스트림(ARI/프론트)에서 처리
            markdown_text = ""

            payload = {
                "success": True,
                "url": url,
                "title": title,
                "html_content": html_content,
                "markdown": markdown_text,
                "status_code": status_code,
            }
            logger.info(f"[MCP] crawl4ai_scrape completed: html={len(html_content)} chars, title='{title}'")
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

## 제거됨: html 테이블 마크다운 변환 툴 (정제 로직 삭제)

## 제거됨: 단일 행 테이블 변환 헬퍼

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

## 제거됨: HTML 메타데이터 추출 툴

# ============================================================================
# MENU SERVICE TOOL (실제 DB 조회는 mcp-client API 위임)
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
# ARI CONTENT STRUCTURING TOOLS (HTML/Markdown -> Ordered JSON)
# ============================================================================

def _get_main_content_soup(html_content: str):
    """
    내부 유틸: Confluence 중심으로 main-content를 찾아 BeautifulSoup 노드를 반환
    """
    try:
        from bs4 import BeautifulSoup
    except Exception:
        raise RuntimeError("bs4(BeautifulSoup) 미설치로 HTML 파싱 불가")

    soup = BeautifulSoup(html_content or "", 'html.parser')

    # 불필요한 UI 요소 제거 (ari_service와 동일 계열의 안전한 최소 셋)
    elements_to_remove = [
        'header', 'footer', 'nav', 'aside', 'sidebar',
        '.header', '.footer', '.nav', '.aside', '.sidebar',
        '.navigation', '.menu', '.breadcrumb',
        'div.aui-page-header-actions', 'div.page-metadata', 'ul.aui-nav-breadcrumbs',
        'div.page-actions', 'div.aui-toolbar2', 'div.comment-container', 'div.like-button-container',
        'div.page-labels', 'div.comment-actions', 'span.st-table-filter', 'svg',
        'div.confluence-information-macro', 'div.aui-message', 'div.page-metadata-modification-info',
        '.aui-page-header-actions', '.page-metadata', '.like-button-container', '.page-labels',
    ]
    for selector in elements_to_remove:
        for el in soup.select(selector):
            el.decompose()

    # main-content 우선, 그 외 폴백 순서 유지 (#main-contents 지원 추가)
    main_content = soup.find('div', {'id': 'main-content'}) or soup.find('div', {'id': 'main-contents'})
    if not main_content:
        main_content = soup.find('div', {'class': 'wiki-content'})
    if not main_content:
        main_content = soup.find('main')
    if not main_content:
        main_content = soup.find('body')
    if not main_content:
        main_content = soup

    return soup, main_content

def _extract_text_from_block(block) -> str:
    """블록 요소에서 의미있는 텍스트를 정리하여 반환 (목록 지원)"""
    # 목록은 항목별로 줄바꿈 유지
    if block.name in ['ul', 'ol']:
        lines: List[str] = []
        for li in block.find_all('li', recursive=False):
            txt = li.get_text(" ", strip=True)
            if txt:
                prefix = "- " if block.name == 'ul' else "1. "
                lines.append(prefix + txt)
        return "\n".join(lines)

    # 일반 블록: 공백 정리
    text = block.get_text(" ", strip=True) if hasattr(block, 'get_text') else str(block)
    return re.sub(r"\s+", " ", text).strip()

def _parse_table_element(table_el) -> Dict[str, Any]:
    """
    AriService와 동일한 방식의 테이블 파서 (그리드 구성 + 복합 헤더 감지)
    - rowspan/colspan 보정
    - 빈 열 제거
    - thead/강조/병합 패턴 기반 다중 헤더 감지
    """
    def extract_text(el) -> str:
        text = el.get_text(separator=' ', strip=True) or ''
        return text.strip()

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

        # 빈 열 제거
        col_count = max_cols
        used: List[bool] = [False] * col_count
        for row in grid:
            for idx, val in enumerate(row):
                if idx < col_count and (val or '').strip():
                    used[idx] = True
        keep_indices = [i for i, u in enumerate(used) if u]
        if keep_indices:
            grid = [[row[i] for i in keep_indices] for row in grid]

        return {'grid': grid, 'cols': len(grid[0]) if grid else 0}

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
            name_parts = []
            for r in range(len(norm_rows)):
                if norm_rows[r][c] and norm_rows[r][c].strip():
                    name_parts.append(norm_rows[r][c].strip())
            if name_parts:
                unique_parts: List[str] = []
                for part in name_parts:
                    if part not in unique_parts:
                        unique_parts.append(part)
                name = ' > '.join(unique_parts) if len(unique_parts) > 1 else unique_parts[0]
            else:
                name = f"컬럼{c+1}"
            headers.append(name)

        return {'headers': headers, 'header_rows_count': len(norm_rows)}

    # 실행
    grid_obj = build_grid(table_el)
    header_info = detect_headers(table_el, grid_obj)
    headers = header_info['headers']
    header_rows_count = header_info['header_rows_count']

    data_rows = grid_obj['grid'][header_rows_count if header_rows_count > 0 else 1:]
    rows: List[Dict[str, Any]] = []
    row_id = 0
    for row in data_rows:
        # 완전 빈 행은 스킵
        if not any((cell or '').strip() for cell in row):
            continue
        data = {}
        for idx, h in enumerate(headers):
            data[h] = row[idx] if idx < len(row) else ''
        row_id += 1
        rows.append({'row_id': row_id, 'data': data})

    return {'headers': headers, 'rows': rows}

def _table_to_markdown(headers: List[str], rows: List[Dict[str, Any]], title: Optional[str] = None) -> str:
    lines: List[str] = []
    if title:
        lines.append(f"### {title}")
        lines.append("")
    # 헤더
    lines.append('|' + '|'.join(h.replace('|', '\\|') for h in headers) + '|')
    lines.append('|' + '|'.join(' --- ' for _ in headers) + '|')
    # 데이터
    for row in rows:
        data = row.get('data', {}) if isinstance(row, dict) else {}
        values = [str(data.get(h, '')).replace('|', '\\|') for h in headers]
        lines.append('|' + '|'.join(values) + '|')
    lines.append("")
    return '\n'.join(lines)

@mcp.tool
def ari_html_to_markdown(html_content: str) -> Dict[str, Any]:
    """
    HTML을 Confluence 메인 콘텐츠 기준으로 마크다운으로 변환합니다.
    - 테이블은 마크다운 테이블로 보존
    - 나머지 블록은 텍스트 마크다운 변환 (markdownify가 없으면 기본 텍스트로 대체)
    리턴: { success, markdown, title }
    """
    try:
        # 원본에서 제목/작성자 추출
        try:
            from bs4 import BeautifulSoup as _BS
            raw_soup = _BS(html_content or "", 'html.parser')
        except Exception:
            raw_soup = None

        main_title_text = ""
        author_text = ""
        if raw_soup is not None:
            try:
                h1 = raw_soup.find('h1', id='title-text') or raw_soup.find('h1', class_='with-breadcrumbs')
                if h1:
                    # 내부 a 텍스트 우선
                    a = h1.find('a')
                    main_title_text = (a.get_text(" ", strip=True) if a else h1.get_text(" ", strip=True)) or ""
            except Exception:
                pass
            try:
                meta = raw_soup.find('div', class_='page-metadata')
                if meta:
                    author_span = meta.find('span', class_='author')
                    if author_span:
                        a = author_span.find('a')
                        author_text = (a.get_text(" ", strip=True) if a else author_span.get_text(" ", strip=True)) or ""
            except Exception:
                pass

        soup, main = _get_main_content_soup(html_content)

        # 제목
        title_el = soup.find('title')
        doc_title = title_el.get_text(strip=True) if title_el else ""

        # DOM 순서를 보존하여 블록별로 마크다운 생성
        parts: List[str] = []
        try:
            try:
                from markdownify import markdownify as md_convert
            except Exception:
                md_convert = None

            for child in list(getattr(main, 'children', [])):
                if not getattr(child, 'name', None):
                    # 텍스트 노드
                    txt = str(child).strip()
                    if txt:
                        parts.append(txt)
                    continue

                tag = child.name.lower()
                if tag == 'table':
                    try:
                        parsed = _parse_table_element(child)
                        caption = None
                        cap_el = child.find('caption')
                        if cap_el:
                            cap_txt = cap_el.get_text(" ", strip=True)
                            caption = cap_txt if cap_txt else None
                        parts.append(_table_to_markdown(parsed['headers'], parsed['rows'], caption).strip())
                    except Exception as te:
                        logger.warning(f"테이블 마크다운 변환 실패: {te}")
                    continue

                # 일반 블록은 개별 HTML 조각을 마크다운으로 변환
                frag_html = child.decode() if hasattr(child, 'decode') else str(child)
                md_text = ""
                if md_convert:
                    try:
                        md_text = md_convert(frag_html, heading_style="ATX", strip=['style', 'script']).strip()
                    except Exception as e:
                        logger.warning(f"블록 마크다운 변환 실패, 텍스트 폴백 사용: {e}")
                if not md_text:
                    try:
                        from bs4 import BeautifulSoup
                        md_text = BeautifulSoup(frag_html, 'html.parser').get_text('\n', strip=True)
                    except Exception:
                        md_text = frag_html
                if md_text.strip():
                    parts.append(md_text.strip())
        except Exception as e:
            logger.warning(f"블록 순회 중 오류: {e}")
            # parts를 비우지 않고 가능한 부분만 사용
            pass

        final_md = '\n\n'.join([p for p in parts if p])

        return {
            "success": True,
            "markdown": final_md,
            "title": doc_title,
            "length": len(final_md),
            "main_title": main_title_text,
            "author": author_text
        }
    except Exception as e:
        logger.error(f"ari_html_to_markdown 실패: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool
def ari_extract_main_blocks(html_content: str) -> Dict[str, Any]:
    """
    Confluence HTML의 main-content 내부를 순서대로 파싱하여 JSON으로 반환합니다.
    - 단락 분할 없이, 블록 단위로 table/text만 구분하여 contents 배열에 기록
    - text 항목의 title은 가장 가까운 직전 heading(h1~h6) 텍스트를 사용
    리턴: { success, contents: [ {id, type, ...}, ... ], metadata: {title} }
    """
    try:
        soup, main = _get_main_content_soup(html_content)

        # 문서 제목
        title_el = soup.find('title')
        doc_title = title_el.get_text(strip=True) if title_el else ""

        contents: List[Dict[str, Any]] = []
        current_title: Optional[str] = None
        idx = 0

        # main의 직계 자식 순회로 순서 보존
        for child in list(getattr(main, 'children', [])):
            # 태그가 아닌 경우(문자 노드) 무시
            if not getattr(child, 'name', None):
                continue

            tag_name = child.name.lower()
            # heading이면 제목 갱신하고 출력은 하지 않음
            if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                current_title = child.get_text(" ", strip=True)
                continue

            if tag_name == 'table':
                try:
                    table_obj = _parse_table_element(child)
                    idx += 1
                    contents.append({
                        "id": idx,
                        "type": "table",
                        "headers": table_obj.get("headers", []),
                        "rows": table_obj.get("rows", []),
                    })
                except Exception as te:
                    logger.warning(f"테이블 파싱 실패: {te}")
                continue

            # 목록/문단/섹션 등 블록을 텍스트로 수집
            if tag_name in ['p', 'div', 'section', 'article', 'ul', 'ol', 'pre', 'blockquote']:
                text = _extract_text_from_block(child)
                if text:
                    idx += 1
                    contents.append({
                        "id": idx,
                        "type": "text",
                        "title": current_title or "",
                        "data": text,
                    })

        return {
            "success": True,
            "contents": contents,
            "metadata": {"title": doc_title}
        }
    except Exception as e:
        logger.error(f"ari_extract_main_blocks 실패: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool
def ari_markdown_to_json(markdown_content: str) -> Dict[str, Any]:
    """
    ARI 마크다운을 최종 JSON 포맷(contents 배열)으로 변환합니다.
    - 헤더(#..)는 이후 text 블록의 title로 사용
    - 마크다운 테이블(|...| + | --- |)을 table 항목으로 파싱
    - 그 외 연속 텍스트를 하나의 text 항목으로 누적하여 추가
    리턴: { success, contents: [...] }
    """
    try:
        if markdown_content is None:
            return {"success": False, "error": "마크다운이 비어있습니다"}

        lines = markdown_content.splitlines()
        contents: List[Dict[str, Any]] = []
        buffer: List[str] = []  # 텍스트 누적 버퍼
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

            # 제목 라인
            if re.match(r"^\s*#{1,6}\s+", line):
                # 기존 텍스트 버퍼를 먼저 비움
                flush_text_buffer()
                # 현재 제목 갱신
                current_title = re.sub(r"^\s*#{1,6}\s+", "", line).strip()
                i += 1
                continue

            # 테이블 감지: 현재 줄이 헤더 라인, 다음 줄이 구분선
            if '|' in line:
                # 테이블 헤더 후보와 구분선 검사
                header_candidate = line.strip()
                if i + 1 < len(lines):
                    separator = lines[i + 1].strip()
                    if re.match(r"^\|\s*:?\-+\s*(\|\s*:?\-+\s*)+\|$", separator):
                        # 텍스트 버퍼를 먼저 비움
                        flush_text_buffer()

                        # 헤더 파싱
                        raw_headers = [h.strip() for h in header_candidate.strip('|').split('|')]
                        headers = [h for h in raw_headers if h != ""]

                        # 데이터 행 수집
                        i += 2  # 헤더와 구분선 건너뜀
                        rows = []
                        row_id = 0
                        while i < len(lines) and '|' in lines[i] and not re.match(r"^\s*#", lines[i]):
                            row_line = lines[i].strip()
                            if not row_line:
                                break
                            raw_cells = [c.strip() for c in row_line.strip('|').split('|')]
                            # 셀 수가 헤더보다 적으면 보정
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

            # 빈 줄이면 텍스트 버퍼를 플러시
            if not line.strip():
                flush_text_buffer()
                i += 1
                continue

            # 그 외는 텍스트 버퍼에 누적
            buffer.append(line)
            i += 1

        # 루프 종료 후 남은 텍스트 반영
        flush_text_buffer()

        return {"success": True, "contents": contents}
    except Exception as e:
        logger.error(f"ari_markdown_to_json 실패: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# EXISTING TOOLS
# ============================================================================

@mcp.tool
def convert_to_json_format(
    url: str,
    title: Optional[str],
    markdown_content: str,
    html_content: str,
    hierarchy: Optional[List[str]] = None,
    startdate: str = "1900-01-01",
    enddate: str = "2999-12-31"
) -> Dict[str, Any]:
    """
    크롤링 결과를 rag-scraping의 JSON 포맷으로 변환합니다.
    to_json.py의 기능을 제공합니다.
    """
    logger.info(f"[MCP] convert_to_json_format called for URL: {url}")
    try:
        import unicodedata
        
        # 텍스트 정규화
        title = unicodedata.normalize('NFC', title or "제목 없음")
        url = unicodedata.normalize('NFC', url)
        
        # 마크다운 내용 처리 (\n -> \\n)
        final_content = markdown_content.strip().replace("\n", "\\n")
        final_content = unicodedata.normalize('NFC', final_content)
        
        # hierarchy 처리 (현재 메뉴 정보가 없어 주석 처리)
        # if not hierarchy:
        #     hierarchy = ["기본"]
        # hierarchy = [unicodedata.normalize('NFC', h) for h in hierarchy]
        
        # HTML에서 메타데이터 추출 (직접 구현)
        metadata = {}
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 이미지 정보 추출 (alt 값이 있는 경우만)
            images = []
            for img in soup.find_all('img'):
                # 헤더/푸터 영역 제외
                if img.find_parent(id=['cfmClHeader', 'cfmClFooter']):
                    continue
                    
                alt_text = img.get('alt', '').strip()
                # alt 값이 있고 의미있는 텍스트인 경우만 추가
                if alt_text and len(alt_text) > 2:
                    images.append({
                        'alt': alt_text,
                        'src': img.get('src', '')
                    })
            
            # 내부 링크 정보 추출
            urls = []
            for link in soup.find_all('a', href=True):
                # 헤더/푸터 영역 제외
                if link.find_parent(id=['cfmClHeader', 'cfmClFooter']):
                    continue
                    
                link_url = link.get('href')
                link_text = link.get_text().strip()
                
                # 의미있는 링크 텍스트가 있는지 확인 (최소 2글자 이상)
                if len(link_text) < 2:
                    continue
                    
                # mailto/tel 제외, 의미있는 텍스트만
                if (link_url.startswith('http') or link_url.startswith('/')) and link_text:
                    urls.append({
                        'desc': link_text,
                        'url': link_url
                    })
            
            # URL 기준 중복 제거
            seen_urls = set()
            unique_urls = []
            for url_info in urls:
                if url_info['url'] not in seen_urls:
                    seen_urls.add(url_info['url'])
                    unique_urls.append(url_info)
            
            # 결과 추가
            if images:
                metadata['images'] = images
            if unique_urls:
                metadata['urls'] = unique_urls
                
        except Exception as e:
            logger.warning(f"메타데이터 추출 실패: {e}")
            metadata = {}
        
        # JSON 데이터 구성 (불필요한 필드 주석 처리)
        json_data = {
            "url": url,
            "murl": "",  # 모바일 URL (기본값 빈 문자열)
            # "hierarchy": hierarchy,  # 현재 메뉴 정보가 없어 주석 처리
            "title": title,
            "text": final_content,
            "startdate": startdate,
            "enddate": enddate,
            "metadata": metadata,
            # "status": "new"  # 현재 상태 관리가 없어 주석 처리
        }
        
        return {
            "success": True,
            "json_data": json_data,
            "text_length": len(final_content),
            "metadata_count": len(metadata)
        }
        
    except Exception as e:
        logger.error(f"JSON 포맷 변환 실패: {e}")
        return {
            "success": False,
            "error": str(e)
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