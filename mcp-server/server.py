from fastmcp import FastMCP
import asyncio
from playwright.async_api import async_playwright
import base64
import json
from typing import Dict, List, Any, Optional
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
    Health check endpoint for container orchestration
    """
    return {
        "success": True,
        "status": "healthy",
        "service": "mcp-server"
    }

async def _crawl_with_playwright(url: str) -> Dict[str, Any]:
    """
    내부 Playwright 크롤러 헬퍼 (툴 내부에서 재사용)
    """
    logger.info(f"[MCP] _crawl_with_playwright called for URL: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
            except Exception:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            title = await page.title()
            html_content = await page.content()
            try:
                meta_description = await page.get_attribute('meta[name="description"]', 'content', timeout=5000) or ""
            except Exception:
                meta_description = ""
            result = {
                "success": True,
                "url": url,
                "title": title,
                "html_content": html_content,
                "meta_description": meta_description,
                "content_length": len(html_content)
            }
            logger.info(f"[MCP] _crawl_with_playwright completed: {len(html_content)} chars, title: '{title}'")
            return result
        finally:
            await browser.close()

@mcp.tool
async def crawl_webpage(url: str) -> Dict[str, Any]:
    """
    Playwright를 사용하여 웹페이지를 크롤링합니다.
    페이지 로드, HTML 추출, 기본 메타데이터를 수집합니다.
    """
    logger.info(f"[MCP] crawl_webpage called for URL: {url}")
    try:
        return await _crawl_with_playwright(url)
    except Exception as e:
        logger.error(f"크롤링 실패 {url}: {str(e)}")
        return {"success": False, "url": url, "error": str(e)}

@mcp.tool
def extract_text_content(html_content: str) -> Dict[str, Any]:
    """
    HTML 콘텐츠에서 텍스트만 추출합니다.
    태그를 제거하고 읽기 가능한 텍스트만 반환합니다.
    """
    logger.info(f"[MCP] extract_text_content called with {len(html_content)} chars")
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 스크립트와 스타일 태그 제거
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 텍스트 추출
        text = soup.get_text()
        
        # 공백 정리
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        result = {
            "success": True,
            "text_content": text,
            "text_length": len(text),
            "word_count": len(text.split())
        }
        logger.info(f"[MCP] extract_text_content completed: {len(text)} chars, {len(text.split())} words")
        return result
        
    except Exception as e:
        logger.error(f"텍스트 추출 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool
def extract_links(html_content: str, base_url: str) -> Dict[str, Any]:
    """
    HTML 콘텐츠에서 모든 링크를 추출합니다.
    상대 링크는 절대 링크로 변환합니다.
    """
    logger.info(f"[MCP] extract_links called with {len(html_content)} chars, base_url: {base_url}")
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if href:
                # 절대 URL로 변환
                absolute_url = urljoin(base_url, href)
                link_text = link.get_text(strip=True)
                
                links.append({
                    "url": absolute_url,
                    "text": link_text,
                    "is_external": urlparse(absolute_url).netloc != urlparse(base_url).netloc
                })
        
        # 중복 제거 (URL 기준)
        unique_links = []
        seen_urls = set()
        for link in links:
            if link["url"] not in seen_urls:
                unique_links.append(link)
                seen_urls.add(link["url"])
        
        result = {
            "success": True,
            "links": unique_links,
            "total_links": len(unique_links),
            "internal_links": len([l for l in unique_links if not l["is_external"]]),
            "external_links": len([l for l in unique_links if l["is_external"]])
        }
        logger.info(f"[MCP] extract_links completed: {len(unique_links)} links found")
        return result
        
    except Exception as e:
        logger.error(f"링크 추출 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool
async def take_screenshot(url: str) -> Dict[str, Any]:
    """
    웹페이지의 스크린샷을 촬영합니다.
    Base64 인코딩된 이미지를 반환합니다.
    """
    logger.info(f"[MCP] take_screenshot called for URL: {url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # 페이지 로드 (더 관대한 전략)
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
            except Exception:
                # networkidle 실패 시 domcontentloaded로 재시도
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            
            # 스크린샷 촬영
            screenshot_bytes = await page.screenshot(full_page=True, type='png')
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            await browser.close()
            
            result = {
                "success": True,
                "url": url,
                "screenshot": screenshot_base64,
                "format": "png",
                "size_bytes": len(screenshot_bytes)
            }
            logger.info(f"[MCP] take_screenshot completed: {len(screenshot_bytes)} bytes, {len(screenshot_base64)} chars")
            return result
            
    except Exception as e:
        logger.error(f"스크린샷 촬영 실패 {url}: {str(e)}")
        return {
            "success": False,
            "url": url,
            "error": str(e)
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
def extract_html_metadata(html_content: str) -> Dict[str, Any]:
    """
    HTML에서 이미지와 링크 메타데이터를 추출합니다.
    rag-scraping의 extract_html_metadata 기능을 제공합니다.
    """
    logger.info(f"[MCP] extract_html_metadata called with {len(html_content)} chars")
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        metadata = {}
        
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
        
        return {
            "success": True,
            "metadata": metadata,
            "images_count": len(images),
            "urls_count": len(unique_urls)
        }
        
    except Exception as e:
        logger.error(f"HTML 메타데이터 추출 실패: {e}")
        return {
            "success": False,
            "error": str(e)
        }

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