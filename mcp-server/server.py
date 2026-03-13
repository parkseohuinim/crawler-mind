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
    RAG(Retrieval-Augmented Generation)용 웹 크롤링 도구.
    
    웹 페이지에서 본문 콘텐츠만 추출하고 마크다운으로 변환합니다.
    crawl4ai 라이브러리를 기본으로 사용하며, 실패 시 Playwright로 폴백합니다.
    
    주요 기능:
        - 헤더, 푸터, 네비게이션, 광고 등 불필요한 요소 자동 제거
        - HTML을 깔끔한 마크다운 텍스트로 변환
        - 타임아웃 발생 시 완화된 설정으로 자동 재시도
        - JavaScript 의존 사이트에 대한 특별 처리
    
    Args:
        url: 크롤링할 웹 페이지 URL
        include_selector: 특정 영역만 추출할 CSS 셀렉터 (선택사항)
                         예: "#content", ".main-article"
    
    Returns:
        dict: 크롤링 결과
            - success (bool): 성공 여부
            - url (str): 요청한 URL
            - title (str|None): 페이지 제목
            - html_content (str): 원본 HTML
            - markdown (str): 변환된 마크다운 텍스트
            - status_code (int|None): HTTP 상태 코드
            - error (str): 실패 시 에러 메시지
    """
    logger.info(f"[crawl4ai_scrape] Start: {url}")
    
    try:
        # ============================================================
        # 1. crawl4ai 라이브러리 임포트
        #    - 설치되지 않았거나 임포트 실패 시 Playwright로 폴백
        # ============================================================
        try:
            from crawl4ai import AsyncWebCrawler
            from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
        except Exception as e:
            logger.warning(f"[crawl4ai_scrape] Import failed, fallback to Playwright: {e}")
            return await _crawl_with_playwright(url)

        # ============================================================
        # 2. 브라우저 설정
        #    - headless: UI 없이 백그라운드 실행
        #    - chromium: 크로미움 엔진 사용
        #    - ignore_https_errors: SSL 인증서 오류 무시
        #    - java_script_enabled: JS 실행 활성화
        # ============================================================
        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            browser_type="chromium",
            ignore_https_errors=True,
            java_script_enabled=True,
        )

        # ============================================================
        # 3. 크롤러 인스턴스 생성 및 시작
        # ============================================================
        crawler = AsyncWebCrawler(config=browser_config)
        await crawler.start()
        
        try:
            # ========================================================
            # 4. JavaScript 의존 사이트 감지
            #    - SPA(Single Page Application) 등 JS 렌더링이 필수인 사이트
            #    - 이런 사이트는 더 긴 대기 시간과 추가 설정 필요
            # ========================================================
            js_heavy_domains = [
                "google.com", "gmail.com", "youtube.com",
                "facebook.com", "twitter.com", "instagram.com",
                "linkedin.com", "reddit.com",
                # KT 도메인 (SPA/JS 렌더링 의존)
                "product.kt.com", "shop.kt.com", "inside.kt.com",
            ]
            is_js_heavy = any(domain in url.lower() for domain in js_heavy_domains)
            
            # ========================================================
            # 5. 제외할 CSS 셀렉터 정의
            #    - 본문과 무관한 UI 요소들을 크롤링에서 제외
            #    - 헤더/푸터, 네비게이션, SNS 공유 버튼, 팝업 등
            # ========================================================
            excluded_selector = (
                # KT 공통 프레임워크 요소
                "#cfmClHeader, #cfmClFooter, #cfmClSkip, "
                "#kt_mb, .kt_mb, #kt-head, .kt-head, "
                # 레이아웃 요소
                ".header-area, .footer-area, .nav, .navigation, .sidebar, "
                # 광고 및 프로모션
                ".advertisement, .banner, .bnr_info, "
                # 팝업 및 모달
                ".popup, .modal, .overlay, "
                "#popupVideo, #popupVideoNo, #popupShortsNo, #popupDownload, #popupConsulting, "
                # SNS 관련
                ".sns-area, .sns-share, .sns-list, .share_wrap, "
                # 슬라이더 컨트롤
                ".swiper-controls-wrapper, .swiper-button-next, .swiper-button-prev, "
                # 기타 UI 요소
                ".location, .find-center, .opage-hashtag-arrow, "
                ".N-compare-suggest-list, .top-three-box, "
                ".sticky, .quickMenu"
            )
            
            # ========================================================
            # 6. 크롤러 실행 설정
            #    - word_count_threshold: 최소 단어 수 (10단어 미만 블록 제외)
            #    - exclude_external_links: 외부 링크 제외
            #    - process_iframes: iframe 내용 처리 여부
            #    - cache_mode: 캐시 우회하여 항상 최신 데이터 가져오기
            #    - wait_until: 페이지 로드 완료 기준
            #      - domcontentloaded: DOM 파싱 완료 시
            #      - networkidle: 네트워크 요청이 없을 때 (JS 사이트용)
            #    - delay_before_return_html: HTML 반환 전 대기 시간(초)
            #    - page_timeout: 페이지 로드 타임아웃 (밀리초)
            # ========================================================
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
                excluded_selector=excluded_selector,
                # JS 의존 사이트: networkidle + 긴 대기 / 일반: domcontentloaded + 짧은 대기
                wait_until="networkidle" if is_js_heavy else "domcontentloaded",
                delay_before_return_html=15 if is_js_heavy else 6,
                # JS 의존 사이트에서만 사용자 시뮬레이션 활성화
                simulate_user=is_js_heavy,
                override_navigator=is_js_heavy,
                page_timeout=120000,  # 2분
            )

            # ========================================================
            # 7. 크롤링 실행
            # ========================================================
            result = await crawler.arun(url=url, config=run_config)
            
            # ========================================================
            # 8. 타임아웃 에러 시 재시도
            #    - 첫 시도 실패가 타임아웃인 경우
            #    - 더 관대한(lenient) 설정으로 재시도
            #    - iframe 처리 비활성화, 대기 시간 단축, 타임아웃 증가
            # ========================================================
            if not result.success:
                error_msg = result.error_message or ""
                is_timeout = "timeout" in error_msg.lower()
                
                if is_timeout:
                    logger.warning(f"[crawl4ai_scrape] Timeout, retrying: {url}")
                    
                    # 재시도용 완화된 설정
                    retry_config = CrawlerRunConfig(
                        verbose=False,
                        word_count_threshold=10,
                        exclude_external_links=True,
                        remove_overlay_elements=False,
                        process_iframes=False,  # iframe 처리 비활성화로 속도 향상
                        ignore_body_visibility=True,
                        js_only=False,
                        cache_mode=CacheMode.BYPASS,
                        excluded_tags=['form', 'header', 'footer', 'nav'],
                        excluded_selector=excluded_selector,
                        wait_until="domcontentloaded",  # 더 빠른 완료 기준
                        delay_before_return_html=3,     # 대기 시간 단축
                        simulate_user=False,
                        override_navigator=False,
                        page_timeout=180000,  # 3분으로 타임아웃 증가
                    )
                    
                    result = await crawler.arun(url=url, config=retry_config)
                    
                    if result.success:
                        logger.info(f"[crawl4ai_scrape] Retry succeeded: {url}")
            
            # ========================================================
            # 9. 크롤링 최종 실패 시 Playwright로 폴백
            # ========================================================
            if not result.success:
                logger.error(f"[crawl4ai_scrape] Failed: {result.error_message}")
                try:
                    return await _crawl_with_playwright(url)
                except Exception:
                    return {
                        "success": False,
                        "url": url,
                        "error": result.error_message or "crawl4ai failed",
                    }

            # ========================================================
            # 10. HTML 콘텐츠 추출
            #     - 결과가 리스트인 경우 문자열로 조인
            # ========================================================
            html_content = result.html or ""
            if isinstance(html_content, list):
                html_content = "\n".join([str(x) for x in html_content])
            
            # ========================================================
            # 11. 메타데이터 추출 (상태 코드, 제목)
            # ========================================================
            status_code = getattr(result, 'status_code', None)
            title = None
            meta = getattr(result, 'metadata', None)
            if isinstance(meta, list):
                meta = meta[0] if meta else None
            if meta is not None:
                title = getattr(meta, 'title', None)

            # ========================================================
            # 12. HTML을 마크다운으로 변환
            #     - BeautifulSoup으로 HTML 파싱 및 정제
            #     - markdownify로 마크다운 변환
            # ========================================================
            markdown_text = ""
            try:
                from bs4 import BeautifulSoup
                from markdownify import markdownify as md
                
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # ----------------------------------------------------
                # 12-1. include_selector가 지정된 경우 해당 영역만 추출
                #       셀렉터가 #, ., [, :로 시작하지 않으면 ID로 간주
                # ----------------------------------------------------
                if include_selector:
                    sel = include_selector if include_selector.startswith(('#', '.', '[', ':')) else f"#{include_selector}"
                    selected = soup.select_one(sel)
                    if selected:
                        soup = BeautifulSoup(str(selected), 'html.parser')
                
                # ----------------------------------------------------
                # 12-2. 불필요한 요소 제거 (마크다운 변환용 확장 목록)
                #       크롤링 단계에서 제거되지 않은 요소들 추가 정리
                # ----------------------------------------------------
                excluded_selectors = [
                    # 레이아웃 요소
                    "#cfmClHeader", "#cfmClFooter", "#cfmClSkip",
                    ".header", ".footer", ".header-area", ".footer-area",
                    ".nav", ".navigation", ".sidebar",
                    # 광고/프로모션
                    ".advertisement", ".banner", ".bnr_info",
                    # 팝업/모달
                    ".popup", ".modal", ".overlay", ".layerPop",
                    "#popupVideo", "#popupVideoNo", "#popupShortsNo", 
                    "#popupDownload", "#popupConsulting",
                    # SNS 관련
                    ".sns-share", ".sns-list", ".sns-area", ".share_wrap",
                    ".sns.twitter", ".sns.facebook", ".sns.kakao", ".sns.youtube",
                    ".icon.kakao", ".icon.facebook", ".icon.twitter", ".icon.youtube",
                    ".btn-twitter", ".btn-facebook", ".btn-kakao", ".btn-youtube",
                    # 슬라이더/캐러셀 컨트롤
                    ".swiper-controls-wrapper", ".swiper-button-next", ".swiper-button-prev",
                    ".opage-hashtag-arrow",
                    # 기타 UI 요소
                    ".location", ".find-center", ".opener",
                    ".N-compare-suggest-list", ".top-three-box",
                    "#kt_mb", ".kt_mb", "#kt-head", ".kt-head",
                    ".sticky", ".quickMenu",
                    # 추적 스크립트 관련
                    "a[onclick*='KT_trackClicks']",
                ]
                
                for sel in excluded_selectors:
                    for el in soup.select(sel):
                        el.decompose()
                
                # ----------------------------------------------------
                # 12-3. 숨겨진 요소 제거
                #       display:none 스타일 또는 invisible 클래스
                # ----------------------------------------------------
                for tag in soup.select('[style*="display:none"]'):
                    tag.decompose()
                for tag in soup.select('.invisible'):
                    tag.decompose()
                
                # ----------------------------------------------------
                # 12-4. 스크립트/스타일 태그 제거
                #       마크다운 변환에 불필요한 코드 블록
                # ----------------------------------------------------
                for t in soup(["script", "style", "noscript"]):
                    t.decompose()
                
                # ----------------------------------------------------
                # 12-5. 마크다운 변환
                #       heading_style="ATX": # 스타일 헤딩 사용
                # ----------------------------------------------------
                cleaned_html = str(soup)
                markdown_text = md(cleaned_html, heading_style="ATX")
                
            except Exception as e:
                logger.warning(f"[crawl4ai_scrape] Markdown conversion failed: {e}")

            # ========================================================
            # 13. 결과 반환
            # ========================================================
            logger.info(f"[crawl4ai_scrape] Done: html={len(html_content)}, md={len(markdown_text)}, title='{title}'")
            
            return {
                "success": True,
                "url": url,
                "title": title,
                "html_content": html_content,
                "markdown": markdown_text,
                "status_code": status_code,
            }
            
        finally:
            # ========================================================
            # 14. 크롤러 리소스 정리
            #     - 브라우저 인스턴스 종료
            #     - 예외 발생해도 무시 (이미 종료되었을 수 있음)
            # ========================================================
            try:
                await crawler.close()
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"[crawl4ai_scrape] Error: {url} - {e}")
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
    """
    HTML 콘텐츠에서 이미지 메타데이터(src, alt)를 추출합니다.
    
    웹 페이지의 HTML에서 모든 <img> 태그를 찾아 이미지 URL과 대체 텍스트를 수집합니다.
    헤더/푸터 영역의 이미지와 의미 없는 alt 텍스트는 필터링됩니다.
    
    Args:
        html_content: 파싱할 HTML 문자열
        base_url: 상대 경로를 절대 경로로 변환할 기준 URL (선택사항)
                  예: "https://example.com"
        min_alt_length: 유효한 alt 텍스트의 최소 길이 (기본값: 2)
                        이보다 짧은 alt는 의미 없는 것으로 간주하여 제외
    
    Returns:
        dict: 추출 결과
            - success (bool): 성공 여부
            - images (list): 이미지 정보 목록 [{"alt": str, "src": str}, ...]
            - count (int): 추출된 이미지 수
            - error (str): 실패 시 에러 메시지
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content or "", "html.parser")
        images: List[Dict[str, str]] = []
        
        # ============================================================
        # 모든 <img> 태그 순회
        # ============================================================
        for element in soup.find_all("img"):
            # --------------------------------------------------------
            # 헤더/푸터 영역 내 이미지 제외
            # - cfmClHeader, cfmClFooter: KT 공통 프레임워크 요소
            # --------------------------------------------------------
            parent = element.find_parent(id=["cfmClHeader", "cfmClFooter"])
            if parent:
                continue

            # --------------------------------------------------------
            # alt 텍스트 유효성 검사
            # - 빈 문자열이거나 너무 짧은 alt는 의미 없는 것으로 제외
            # --------------------------------------------------------
            alt_text = (element.get("alt") or "").strip()
            if len(alt_text) < min_alt_length:
                continue

            # --------------------------------------------------------
            # 이미지 src 처리
            # - 상대 경로인 경우 base_url을 사용해 절대 경로로 변환
            # --------------------------------------------------------
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
        logger.error(f"[extract_image_metadata] Error: {exc}")
        return {"success": False, "error": str(exc)}


@mcp.tool
async def extract_links(
    html_content: str,
    base_url: Optional[str] = None,
    min_text_length: int = 2
) -> Dict[str, Any]:
    """
    HTML 콘텐츠에서 의미 있는 앵커 링크를 추출합니다.
    
    웹 페이지의 HTML에서 모든 <a> 태그를 찾아 링크 텍스트와 URL을 수집합니다.
    헤더/푸터 영역의 링크와 텍스트가 없는 링크는 필터링됩니다.
    
    Args:
        html_content: 파싱할 HTML 문자열
        base_url: 상대 경로를 절대 경로로 변환할 기준 URL (선택사항)
                  예: "https://example.com"
        min_text_length: 유효한 링크 텍스트의 최소 길이 (기본값: 2)
                         이보다 짧은 텍스트는 의미 없는 것으로 간주하여 제외
    
    Returns:
        dict: 추출 결과
            - success (bool): 성공 여부
            - links (list): 링크 정보 목록 [{"text": str, "url": str}, ...]
            - count (int): 추출된 링크 수
            - error (str): 실패 시 에러 메시지
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content or "", "html.parser")
        links: List[Dict[str, str]] = []
        
        # ============================================================
        # href 속성이 있는 모든 <a> 태그 순회
        # ============================================================
        for element in soup.find_all("a", href=True):
            # --------------------------------------------------------
            # 헤더/푸터 영역 내 링크 제외
            # - cfmClHeader, cfmClFooter: KT 공통 프레임워크 요소
            # --------------------------------------------------------
            parent = element.find_parent(id=["cfmClHeader", "cfmClFooter"])
            if parent:
                continue

            # --------------------------------------------------------
            # 링크 텍스트 유효성 검사
            # - 빈 문자열이거나 너무 짧은 텍스트는 의미 없는 것으로 제외
            # --------------------------------------------------------
            text = element.get_text(strip=True)
            if len(text) < min_text_length:
                continue

            # --------------------------------------------------------
            # href 속성 처리
            # - 빈 href 제외
            # - 상대 경로("/"로 시작)는 base_url로 절대 경로 변환
            # - http:// 또는 https://로 시작하는 URL만 수집
            # --------------------------------------------------------
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
        logger.error(f"[extract_links] Error: {exc}")
        return {"success": False, "error": str(exc)}


@mcp.tool
def extract_meta_title(html_content: str) -> Dict[str, Any]:
    """
    HTML에서 페이지 제목을 추출합니다.
    
    우선순위:
        1. Open Graph meta 태그 (og:title)
        2. <title> 태그
    
    Args:
        html_content: 파싱할 HTML 문자열
    
    Returns:
        dict: 추출 결과
            - success (bool): 제목 추출 성공 여부
            - title (str): 추출된 제목 (없으면 빈 문자열)
            - error (str): 실패 시 에러 메시지
    """
    try:
        title = extract_meta_title_from_html(html_content)
        return {"success": bool(title), "title": title or ""}
    except Exception as exc:
        logger.error(f"[extract_meta_title] Error: {exc}")
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


@mcp.tool
def convert_to_rag_json_v2(
    url: str,
    title: str,
    processed_text: str,
    html_content: str,
    hierarchy: Optional[List[str]] = None,
    murl: Optional[str] = None,
    startdate: str = "1900-01-01",
    enddate: str = "2999-12-31"
) -> Dict[str, Any]:
    """
    RAG용 JSON 포맷 변환 (v2): daily_crawling_service와 동일한 JSON 구조 생성
    
    이미 전처리된 텍스트를 받아서 최종 JSON 형식으로 변환합니다.
    docId, status 필드는 포함하지 않습니다.
    
    출력 JSON 구조:
        {
            "url": "https://...",
            "murl": "https://m...",
            "hierarchy": ["고객지원", "매장/고객센터 안내", "..."],
            "title": "문서 제목",
            "text": "본문 텍스트...",
            "startdate": "1900-01-01",
            "enddate": "2999-12-31",
            "metadata": { "images": [...], "urls": [...] }
        }
    
    Args:
        url: 페이지 URL
        title: 페이지 제목
        processed_text: 전처리된 마크다운 텍스트
        html_content: 원본 HTML (메타데이터 추출용)
        hierarchy: 메뉴 계층 구조 리스트
        murl: 모바일 URL
        startdate: 시작일 (기본: 1900-01-01)
        enddate: 종료일 (기본: 2999-12-31)
    
    Returns:
        dict: 변환 결과
            - success (bool): 성공 여부
            - json_data (dict): 최종 JSON 데이터
            - error (str): 실패 시 에러 메시지
    """
    logger.info(f"[MCP] convert_to_rag_json_v2 called for URL: {url}")
    try:
        import unicodedata
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        # ============================================================
        # 유니코드 정규화 (NFC)
        # 한글 자모 분리 문제 방지 (ㄱ+ㅏ → 가)
        # ============================================================
        normalized_title = unicodedata.normalize('NFC', title or "제목 없음")
        normalized_url = unicodedata.normalize('NFC', url or "")
        normalized_text = unicodedata.normalize('NFC', processed_text or "")
        
        # ============================================================
        # 개행문자 이스케이프
        # JSON 저장 시 실제 개행이 아닌 문자열 "\n"으로 저장
        # ============================================================
        final_text = normalized_text.replace("\n", "\\n")
        
        # ============================================================
        # hierarchy 정규화
        # ============================================================
        normalized_hierarchy = []
        if hierarchy:
            normalized_hierarchy = [
                unicodedata.normalize('NFC', item)
                for item in hierarchy
                if item and item.strip()
            ]
        
        # ============================================================
        # 메타데이터 추출 (이미지, 링크)
        # ============================================================
        metadata: Dict[str, Any] = {}
        
        if html_content:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 이미지 추출
                images = []
                for img in soup.find_all('img'):
                    # 헤더/푸터 영역 제외
                    if img.find_parent(id=['cfmClHeader', 'cfmClFooter']):
                        continue
                    alt_text = (img.get('alt') or '').strip()
                    if len(alt_text) >= 2:
                        src = img.get('src', '')
                        if url and src and not src.startswith('http'):
                            src = urljoin(url, src)
                        images.append({'alt': alt_text, 'src': src})
                
                if images:
                    metadata['images'] = images
                
                # 링크 추출
                urls_data = []
                for link in soup.find_all('a', href=True):
                    # 헤더/푸터 영역 제외
                    if link.find_parent(id=['cfmClHeader', 'cfmClFooter']):
                        continue
                    link_text = link.get_text(strip=True)
                    if len(link_text) < 2:
                        continue
                    href = link.get('href', '')
                    if not href:
                        continue
                    # 상대 경로를 절대 경로로 변환
                    if url and href.startswith('/'):
                        href = urljoin(url, href)
                    # http/https URL만 수집
                    if href.startswith(('http://', 'https://')):
                        urls_data.append({'desc': link_text, 'url': href})
                
                if urls_data:
                    metadata['urls'] = _deduplicate_by_key(urls_data, 'url')
                    
            except Exception as e:
                logger.warning(f"[convert_to_rag_json_v2] 메타데이터 추출 실패: {e}")
        
        # ============================================================
        # 최종 JSON 구조 생성
        # ============================================================
        json_data = {
            "url": normalized_url,
            "murl": murl or "",
            "hierarchy": normalized_hierarchy,
            "title": normalized_title,
            "text": final_text,
            "startdate": startdate,
            "enddate": enddate,
            "metadata": metadata,
        }
        
        return {
            "success": True,
            "json_data": json_data,
            "text_length": len(final_text),
            "metadata_count": len(metadata),
        }
        
    except Exception as exc:
        logger.error(f"[convert_to_rag_json_v2] Error: {exc}")
        return {
            "success": False,
            "json_data": {},
            "error": str(exc),
        }


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
# KT PAGE INFO EXTRACTION TOOLS (KT 페이지 정보 추출)
# ============================================================================

@mcp.tool
def extract_kt_page_info(html_content: str) -> Dict[str, Any]:
    """
    KT 페이지의 HTML에서 title과 hierarchy를 추출합니다.
    
    title 추출 (og:title 파싱):
        - "인터넷 요금제 | 인터넷 | KT닷컴" → "인터넷 요금제"
        - "제조사별 A/S센터 안내&nbsp;|&nbsp;KT" → "제조사별 A/S센터 안내"
        - "KT" (단독) → 빈 문자열 반환
    
    hierarchy 추출 (breadcrumb 파싱):
        - <div class="location"> 내의 span 요소들에서 추출
        - HOME 제외, 나머지 메뉴 경로 반환
        - 예: ["고객지원", "매장/고객센터 안내", "제조사별 A/S센터 안내"]
    
    Args:
        html_content: 파싱할 HTML 문자열
    
    Returns:
        dict: 추출 결과
            - success (bool): 성공 여부
            - title (str): 추출된 title
            - hierarchy (list): breadcrumb에서 추출된 hierarchy 리스트
            - error (str): 실패 시 에러 메시지
    """
    try:
        from bs4 import BeautifulSoup
        import html as html_module
        
        soup = BeautifulSoup(html_content or "", "html.parser")
        
        # ============================================================
        # 1. title 추출: og:title 메타 태그에서 추출
        # ============================================================
        title = ""
        og_title_meta = soup.find("meta", attrs={"property": "og:title"})
        
        if og_title_meta and og_title_meta.get("content"):
            raw_title = og_title_meta.get("content", "").strip()
            # HTML 엔티티 디코딩 (&nbsp; → 공백 등)
            raw_title = html_module.unescape(raw_title)
            
            # "|" 또는 "│"로 분리하여 첫 번째 부분만 사용
            # 예: "인터넷 요금제 | 인터넷 | KT닷컴" → "인터넷 요금제"
            separators = ['|', '│', '｜']
            for sep in separators:
                if sep in raw_title:
                    parts = [p.strip() for p in raw_title.split(sep)]
                    # 첫 번째 의미 있는 부분 사용 (빈 문자열이 아닌)
                    for part in parts:
                        if part and part not in ["KT", "KT닷컴", "케이티"]:
                            title = part
                            break
                    break
            else:
                # 구분자가 없으면 그대로 사용 (예: "KT"만 있는 경우도 포함)
                title = raw_title
        
        # og:title이 없거나 빈 경우 <title> 태그에서 시도
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                raw_title = title_tag.get_text(strip=True)
                raw_title = html_module.unescape(raw_title)
                if raw_title:
                    # 동일한 분리 로직 적용
                    separators = ['|', '│', '｜']
                    for sep in separators:
                        if sep in raw_title:
                            parts = [p.strip() for p in raw_title.split(sep)]
                            for part in parts:
                                if part and part not in ["KT", "KT닷컴", "케이티"]:
                                    title = part
                                    break
                            break
                    else:
                        # 구분자가 없으면 그대로 사용 (예: "KT"만 있는 경우도 포함)
                        title = raw_title
        
        # ============================================================
        # 2. hierarchy 추출: breadcrumb (location div)에서 추출
        # ============================================================
        hierarchy = []
        
        # <div class="location"> 찾기
        location_div = soup.find("div", class_=lambda c: c and "location" in c)
        
        if location_div:
            spans = location_div.find_all("span")
            for span in spans:
                # 링크가 있는 경우 링크 텍스트, 없으면 span 텍스트
                link = span.find("a")
                if link:
                    text = link.get_text(strip=True)
                else:
                    text = span.get_text(strip=True)
                
                # HTML 엔티티 디코딩
                text = html_module.unescape(text)
                
                # HOME 및 빈 문자열 제외
                if text and text.upper() != "HOME":
                    hierarchy.append(text)
        
        return {
            "success": True,
            "title": title,
            "hierarchy": hierarchy,
        }
        
    except Exception as exc:
        logger.error(f"[extract_kt_page_info] Error: {exc}")
        return {"success": False, "title": "", "hierarchy": [], "error": str(exc)}


# ============================================================================
# MARKDOWN PREPROCESSING TOOLS (마크다운 전처리)
# ============================================================================

def _is_table_row(line: str) -> bool:
    """마크다운 테이블 행인지 확인"""
    line = line.strip()
    if not line or '|' not in line:
        return False
    content_without_pipes = line.replace('|', '')
    if all(c in '- ' for c in content_without_pipes):
        return True
    if line.startswith('|') or line.endswith('|'):
        return True
    cells = line.split('|')
    has_content = any(cell.strip() for cell in cells)
    if has_content or line.count('|') >= 2:
        return True
    return False


def _is_separator_row(line: str) -> bool:
    """마크다운 테이블 구분선인지 확인"""
    stripped = line.strip()
    if not stripped or '|' not in stripped:
        return False
    if not (stripped.startswith('|') or stripped.endswith('|')):
        return False
    content = stripped.replace('|', '')
    return all(c in '- ' for c in content)


def _find_table_boundaries(lines: List[str], start_idx: int) -> tuple:
    """테이블의 시작과 끝 인덱스 찾기"""
    if not _is_table_row(lines[start_idx]):
        return -1, -1
    
    original_start_idx = start_idx
    consecutive_empty_lines = 0
    max_empty_lines = 1
    
    while start_idx > 0:
        prev_line = lines[start_idx - 1].strip()
        if _is_table_row(lines[start_idx - 1]):
            start_idx -= 1
            consecutive_empty_lines = 0
        elif prev_line == '':
            consecutive_empty_lines += 1
            if consecutive_empty_lines <= max_empty_lines:
                start_idx -= 1
            else:
                break
        else:
            break
    
    has_separator = False
    for i in range(start_idx, min(start_idx + 5, len(lines))):
        if i >= len(lines):
            break
        if _is_separator_row(lines[i]):
            has_separator = True
            break
    
    first_line = lines[start_idx].strip()
    is_single_row_table = (first_line.startswith('|') and first_line.endswith('|'))
    cell_count = first_line.count('|') - 1 if first_line.startswith('|') and first_line.endswith('|') else 0
    
    if is_single_row_table and cell_count >= 1:
        return start_idx, start_idx
    
    if not has_separator:
        valid_rows = 0
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            if i < len(lines) and _is_table_row(lines[i]):
                valid_rows += 1
        if valid_rows < 2:
            if is_single_row_table:
                return start_idx, start_idx
            return -1, -1
    
    end_idx = start_idx
    consecutive_non_table = 0
    max_table_rows = 200
    
    while end_idx < len(lines) and (end_idx - start_idx) < max_table_rows:
        is_table = _is_table_row(lines[end_idx])
        is_empty = lines[end_idx].strip() == ''
        if is_table or is_empty:
            if is_table:
                consecutive_non_table = 0
            end_idx += 1
            continue
        consecutive_non_table += 1
        if consecutive_non_table >= 1:
            break
        end_idx += 1
    
    while end_idx > start_idx and (not _is_table_row(lines[end_idx - 1]) or lines[end_idx - 1].strip() == ''):
        end_idx -= 1
    
    if end_idx <= start_idx:
        return -1, -1
    
    valid_table = False
    row_count = 0
    
    if is_single_row_table and start_idx == end_idx - 1:
        return start_idx, end_idx - 1
    
    for i in range(start_idx, end_idx):
        if _is_table_row(lines[i]):
            row_count += 1
        if _is_separator_row(lines[i]):
            valid_table = True
            break
    
    if valid_table or row_count >= 2 or (is_single_row_table and row_count >= 1):
        return start_idx, end_idx - 1
    else:
        return -1, -1


def _process_markdown_table(lines: List[str], start_idx: int, end_idx: int) -> Optional[str]:
    """마크다운 테이블 구조 보정"""
    if end_idx - start_idx < 1:
        return None
    
    table_lines = []
    has_separator = False
    max_columns = 0
    
    for i in range(start_idx, end_idx + 1):
        line = lines[i].strip()
        if '|' in line:
            if line.startswith('|') and line.endswith('|'):
                columns = line.count('|') - 1
            else:
                columns = line.count('|') + 1
            max_columns = max(max_columns, columns)
    
    header_row = lines[start_idx].strip()
    if not header_row.startswith('|'):
        header_row = '|' + header_row
    if not header_row.endswith('|'):
        header_row = header_row + '|'
    
    header_cells = header_row.strip('|').split('|')
    while len(header_cells) < max_columns:
        header_cells.append('')
    header_row = '|' + '|'.join(header_cells) + '|'
    table_lines.append(header_row)
    
    if start_idx + 1 <= end_idx:
        next_row = lines[start_idx + 1].strip()
        if _is_separator_row(next_row):
            has_separator = True
            separator = '|' + '|'.join([' --- ' for _ in range(max_columns)]) + '|'
            table_lines.append(separator)
            start_idx += 1
    
    if not has_separator:
        separator = '|' + '|'.join([' --- ' for _ in range(max_columns)]) + '|'
        table_lines.append(separator)
    
    for i in range(start_idx + 1, end_idx + 1):
        if _is_table_row(lines[i]):
            data_row = lines[i].strip()
            if not data_row.startswith('|'):
                data_row = '|' + data_row
            if not data_row.endswith('|'):
                data_row = data_row + '|'
            data_cells = data_row.strip('|').split('|')
            while len(data_cells) < max_columns:
                data_cells.append('')
            data_row = '|' + '|'.join(data_cells) + '|'
            table_lines.append(data_row)
    
    if len(table_lines) < 2:
        return None
    
    return '\n'.join(table_lines)


def _process_single_row_table(line: str) -> str:
    """단일 행 테이블을 마크다운 표 형식으로 변환"""
    if not line.strip().startswith('|') or not line.strip().endswith('|'):
        line = '|' + line.strip() + '|'
    cells = [cell.strip() for cell in line.strip('|').split('|')]
    header_row = '|' + '|'.join(cells) + '|'
    separator = '|' + '|'.join([' --- ' for _ in range(len(cells))]) + '|'
    return header_row + '\n' + separator


def _extract_table_from_html(html_content: str) -> List[str]:
    """HTML에서 테이블 추출하여 마크다운으로 변환"""
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        tables = soup.find_all('table')
        
        if not tables:
            return []
        
        markdown_tables = []
        
        for table in tables:
            rows = table.find_all('tr')
            row_count = len(rows)
            
            if row_count == 0:
                continue
            
            has_header_tags = False
            thead = table.find('thead')
            if thead and thead.find_all('th'):
                has_header_tags = True
            elif rows[0].find_all('th'):
                has_header_tags = True
            
            header_row = rows[0]
            header_cells = header_row.find_all(['th', 'td'])
            header_col_count = sum(int(cell.get('colspan', 1)) for cell in header_cells)
            
            max_data_col_count = 0
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                row_col_count = sum(int(cell.get('colspan', 1)) for cell in cells)
                max_data_col_count = max(max_data_col_count, row_col_count)
            
            col_count = max(header_col_count, max_data_col_count, 2)
            
            grid = [[None for _ in range(col_count)] for _ in range(row_count)]
            
            for row_idx, row in enumerate(rows):
                col_idx = 0
                cells = row.find_all(['td', 'th'])
                
                for cell in cells:
                    while col_idx < col_count and grid[row_idx][col_idx] is not None:
                        col_idx += 1
                    
                    if col_idx >= col_count:
                        break
                    
                    rowspan = int(cell.get('rowspan', 1))
                    colspan = int(cell.get('colspan', 1))
                    content = cell.get_text(separator=' ', strip=True)
                    content = re.sub(r'\s+', ' ', content)
                    
                    for r in range(rowspan):
                        for c in range(colspan):
                            if row_idx + r < row_count and col_idx + c < col_count:
                                grid[row_idx + r][col_idx + c] = content
                    
                    col_idx += colspan
            
            grid = [['' if cell is None else cell for cell in row] for row in grid]
            
            actual_col_count = 0
            for col_idx in range(col_count):
                has_content = False
                for row_idx in range(row_count):
                    if grid[row_idx][col_idx]:
                        has_content = True
                        break
                if has_content:
                    actual_col_count = col_idx + 1
            
            if actual_col_count > 0 and actual_col_count < col_count:
                grid = [row[:actual_col_count] for row in grid]
                col_count = actual_col_count
            
            if row_count == 1:
                header_line = '|' + '|'.join(str(cell) for cell in grid[0]) + '|'
                markdown_table = _process_single_row_table(header_line)
                markdown_tables.append('\n' + markdown_table + '\n')
            else:
                markdown_table_lines = []
                
                if has_header_tags:
                    header = '|' + '|'.join(str(cell) for cell in grid[0]) + '|'
                    markdown_table_lines.append(header)
                    separator = '|' + '|'.join(' --- ' for _ in range(col_count)) + '|'
                    markdown_table_lines.append(separator)
                    
                    for row in grid[1:]:
                        if all(cell.strip().replace('-', '') == '' for cell in row):
                            continue
                        data_row = '|' + '|'.join(str(cell) for cell in row) + '|'
                        markdown_table_lines.append(data_row)
                else:
                    empty_header = '|' + '|'.join('' for _ in range(col_count)) + '|'
                    markdown_table_lines.append(empty_header)
                    separator = '|' + '|'.join(' --- ' for _ in range(col_count)) + '|'
                    markdown_table_lines.append(separator)
                    
                    for row in grid:
                        if all(cell.strip().replace('-', '') == '' for cell in row):
                            continue
                        data_row = '|' + '|'.join(str(cell) for cell in row) + '|'
                        markdown_table_lines.append(data_row)
                
                markdown_tables.append('\n' + '\n'.join(markdown_table_lines) + '\n')
        
        return markdown_tables
            
    except Exception as e:
        logger.warning(f"[_extract_table_from_html] Error: {e}")
        return []


def _clean_js_patterns_in_table(table_content: str) -> str:
    """테이블 내 JavaScript 링크 패턴 정리"""
    if not table_content:
        return table_content
    
    import regex
    
    js_patterns = [
        (r'\[([^\]]*)\]\(javascript:void\(0\)(?:\s*;[^)]*)?(?:\s+"(?:[^"\\]|\\.)*")?\s*\)', r'\1'),
        (r'\[([^\]]*)\]\(javascript:(?:kt_common\.ktMenuLinkStat|wDicProd\.lnkBtn|detailClickStatistics\.click)\([^)]*\)(?:\s*;[^)]*)*\)', r'\1'),
        (r'\[([^\]]*)\]\(javascript:[^)]*\)', r'\1'),
        (r'\[([^\]]*)\]\([^)]*javascript[^)]*\)', r'\1'),
        (r'([^\]]+)\]\(javascript:[^)]*\)', r'\1'),
        (r'([^\]]+)\]\(javascript:void\(0[^)]*', r'\1'),
        (r'([^\]]+)\]\([^)]*javascript[^)]*', r'\1'),
        (r'([^\]]+)\]\([^)]*;[^)]*$', r'\1'),
        (r'([^)]+)"\)$', r'\1'),
        (r'([^)]+)\)$', r'\1'),
    ]
    
    for pattern, replacement in js_patterns:
        table_content = regex.sub(pattern, replacement, table_content)
    
    return table_content


def _postprocess_duplicate_table_headers(text: str) -> str:
    """중복 테이블 헤더 제거"""
    lines = text.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        if i < len(lines) and _is_separator_row(lines[i]):
            if i + 1 < len(lines) and _is_separator_row(lines[i + 1]):
                result_lines.append(lines[i])
                i += 2
                continue
        
        if i < len(lines) and _is_table_row(lines[i]):
            first_header = lines[i]
            is_first_header_empty = all(cell.strip() == '' for cell in first_header.strip('|').split('|') if cell != '')
            
            if i + 1 < len(lines) and _is_separator_row(lines[i + 1]):
                first_separator = lines[i + 1]
                
                if i + 2 < len(lines) and _is_table_row(lines[i + 2]):
                    second_header = lines[i + 2]
                    is_second_header_empty = all(cell.strip() == '' for cell in second_header.strip('|').split('|') if cell != '')
                    
                    if i + 3 < len(lines) and _is_separator_row(lines[i + 3]):
                        if is_first_header_empty and is_second_header_empty:
                            result_lines.append(first_header)
                            result_lines.append(first_separator)
                            i += 4
                            continue
                        elif is_first_header_empty and not is_second_header_empty:
                            result_lines.append(second_header)
                            result_lines.append(first_separator)
                            i += 4
                            continue
        
        if i < len(lines):
            result_lines.append(lines[i])
        i += 1
    
    return '\n'.join(result_lines)


@mcp.tool
def preprocess_markdown(
    markdown_text: str,
    html_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    마크다운 텍스트를 전처리합니다. (일반 정보 처리)
    
    처리 내용:
        - 마크다운 테이블 구조 보정
        - HTML 테이블 rowspan/colspan 처리
        - 불필요한 요소 제거 (네비게이션, JavaScript 링크 등)
        - 이미지/링크 텍스트 변환
        - 공백 정리
    
    Args:
        markdown_text: 전처리할 마크다운 텍스트
        html_content: 원본 HTML (테이블 처리용, 선택적)
    
    Returns:
        dict: 전처리 결과
            - success (bool): 성공 여부
            - processed_text (str): 전처리된 텍스트
            - original_length (int): 원본 길이
            - processed_length (int): 처리 후 길이
            - error (str): 실패 시 에러 메시지
    """
    try:
        import regex
        
        if not markdown_text:
            return {
                "success": True,
                "processed_text": "",
                "original_length": 0,
                "processed_length": 0,
            }
        
        text = markdown_text
        original_length = len(text)
        
        # ============================================================
        # 1단계: 테이블 위치 찾기 및 마커로 대체
        # ============================================================
        table_data = []
        lines = text.split('\n')
        
        i = 0
        processed_ranges = []
        max_iterations = len(lines) * 2
        iteration_count = 0
        
        while i < len(lines):
            iteration_count += 1
            if iteration_count > max_iterations:
                break
            
            is_processed = False
            for start, end in processed_ranges:
                if start <= i <= end:
                    is_processed = True
                    i = end + 1
                    break
            
            if is_processed:
                continue
            
            line = lines[i].strip()
            if '|' in line:
                start_idx, end_idx = _find_table_boundaries(lines, i)
                if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                    already_processed = False
                    for start, end in processed_ranges:
                        if not (end_idx < start or start_idx > end):
                            already_processed = True
                            break
                    
                    if already_processed:
                        i += 1
                        continue
                    
                    original_table = '\n'.join(lines[start_idx:end_idx + 1])
                    table_marker = f'<<__TABLE_MARKER_{len(table_data)}__>>'
                    
                    processed_ranges.append((start_idx, end_idx))
                    orig_pos = text.find(original_table)
                    
                    is_single_row = start_idx == end_idx and lines[start_idx].strip().startswith('|') and lines[start_idx].strip().endswith('|')
                    
                    table_data.append({
                        'marker': table_marker,
                        'original': original_table,
                        'processed': None,
                        'original_position': orig_pos,
                        'is_single_row': is_single_row
                    })
                    
                    if orig_pos >= 0:
                        text = text[:orig_pos] + table_marker + text[orig_pos + len(original_table):]
                    else:
                        text = text.replace(original_table, table_marker)
                    i = end_idx + 1
                    continue
            i += 1
        
        # ============================================================
        # HTML에서 테이블 추출
        # ============================================================
        html_tables = []
        if html_content:
            try:
                html_tables = _extract_table_from_html(html_content)
            except Exception as e:
                logger.warning(f"[preprocess_markdown] HTML table extraction error: {e}")
        
        # 마커 보호 함수
        def protect_markers(txt, tbl_data):
            markers_map = {}
            for idx, tbl in enumerate(tbl_data):
                marker = tbl['marker']
                if marker in txt:
                    temp_key = f"___PROTECTED_MARKER_{idx}___"
                    markers_map[temp_key] = marker
                    txt = txt.replace(marker, temp_key)
            return txt, markers_map

        def restore_markers(txt, markers_map):
            for temp_key, marker in markers_map.items():
                txt = txt.replace(temp_key, marker)
            return txt

        def safe_regex_sub(pattern, repl, txt, **kwargs):
            protected_text, markers_map = protect_markers(txt, table_data)
            processed_text = regex.sub(pattern, repl, protected_text, **kwargs)
            restored_text = restore_markers(processed_text, markers_map)
            return restored_text
        
        # ============================================================
        # 2단계: 텍스트 정리
        # ============================================================
        # 2.1 백슬래시 처리
        text = safe_regex_sub(r'(\\\\|\\)+', '', text)
        
        # 2.2 이미지 처리
        def image_replacer(match):
            alt = match.group(1)
            if alt.strip():
                return alt
            return ''
        
        text = safe_regex_sub(r'!\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)', image_replacer, text)
        
        prev_text = ""
        iter_count = 0
        max_iter = 3
        while prev_text != text and iter_count < max_iter:
            prev_text = text
            text = regex.sub(r'!\[(.*?)\]\((.*?)\)', image_replacer, text)
            iter_count += 1
        
        # 2.3 링크 처리
        text = safe_regex_sub(r'\[([^\]]*)\]\(javascript:void\(0\)(?:\s*;[^)]*)?(?:\s+"(?:[^"\\]|\\.)*")?\s*\)', r'\1', text)
        text = safe_regex_sub(r'\[([^\]]*)\]\(javascript:[^)]*\)', r'\1', text)
        
        special_patterns = [
            (r'\[([^\]]*)\[([^\]]*)\]\]\([^)]*\)', r'\1[\2]'),
            (r'\[\s*([^\]]*?)\s*\]\([^)]*\s+"[^"]*"\s*\)', r'\1'),
            (r'\[([^\]]*)\]\(mailto:.*?\)', r'\1'),
            (r'\[\]\(\)', ''),
            (r'\[([^\]]*)\]\(#\)', r'\1 '),
            (r'\[([^\]]*)\]\(/[^)]*?\.aspx\)', r'\1 '),
            (r'\[([^\]]*)\]\(\?[^)]*\s*"[^"]*"\)', r'\1'),
        ]
        
        for pattern, replacement in special_patterns:
            text = safe_regex_sub(pattern, replacement, text)
        
        for _ in range(3):
            prev_text = text
            text = safe_regex_sub(r'\[([^\[\]]*?)\]\((?:[^()]|\([^()]*\))*?\)', r'\1', text)
            if prev_text == text:
                break
        
        # 2.4 HTML 태그 제거
        html_tag_pattern = r'<(?:br\s*/?|p\s*/?|/p|div[^>]*|/div|span[^>]*|/span|strong|/strong|em|/em|[^>]+)>'
        text = safe_regex_sub(html_tag_pattern, '', text)
        
        # 2.5 특수 텍스트 제거
        special_text_patterns = [
            (r'자막\s*열기\s*자막\s*접기|(?:\[자막 열기\](?:\([^)]*\))?\s*\[자막 접기\](?:\([^)]*\))?)', '', regex.MULTILINE),
            (r'^\s*[=-]{3,}\s*$', '', regex.MULTILINE),
            (r'(?:\[HOME\]|HOME).*?\n|\[(?:이전글|다음글)\\\\.*?\]\(.*?\)|\[목록\]\(.*?\)|(?:이전글|다음글) \[.*?\]\(.*?\)', '', regex.DOTALL),
            (r'^(?:_?닫기_?|주문하기|이전\s*다음|확인|동의|검색|레이어\s*닫기|prevnext|Pause|상세검색|카카오톡페이스북트위터라인닫기|하루\s*동안\s*보지\s*않기닫기)$', '', regex.MULTILINE | regex.IGNORECASE),
        ]
        
        for pattern_tuple in special_text_patterns:
            if len(pattern_tuple) == 3:
                pattern, replacement, flags = pattern_tuple
            else:
                pattern, replacement = pattern_tuple
                flags = 0
            text = safe_regex_sub(pattern, replacement, text, flags=flags)
        
        # 2.6 정리 및 포맷팅
        text = safe_regex_sub(r'\n{3,}', '\n\n', text)
        text = safe_regex_sub(r' +$', '', text, flags=regex.MULTILINE)
        text = safe_regex_sub(r'^\s*-\s*', '- ', text, flags=regex.MULTILINE)
        
        # 2.7 용어 통일
        text = safe_regex_sub(r'피해\s*사례', '피해사례', text)
        text = safe_regex_sub(r'주의\s*사항', '주의사항', text)
        text = safe_regex_sub(r'대응\s*방안', '대응방안', text)
        
        # ============================================================
        # 3단계: 테이블 처리
        # ============================================================
        for idx, table in enumerate(table_data):
            marker = table['marker']
            current_pos = text.find(marker)
            if current_pos >= 0:
                table['current_position'] = current_pos
            else:
                table['current_position'] = table.get('original_position', float('inf'))
            
            if html_tables and idx < len(html_tables):
                html_table_content = html_tables[idx]
                html_table_content = _clean_js_patterns_in_table(html_table_content)
                table['processed'] = html_table_content
            else:
                if table.get('is_single_row', False):
                    original_table = table['original']
                    original_table = _clean_js_patterns_in_table(original_table)
                    processed_table = _process_single_row_table(original_table)
                    table['processed'] = processed_table if processed_table else original_table
                else:
                    original_table = table['original']
                    original_table = _clean_js_patterns_in_table(original_table)
                    table_lines = original_table.split('\n')
                    processed_table = _process_markdown_table(table_lines, start_idx=0, end_idx=len(table_lines) - 1)
                    table['processed'] = processed_table if processed_table else original_table
        
        # 마커를 처리된 테이블로 교체
        sorted_tables = sorted(table_data, key=lambda t: t.get('current_position', float('inf')))
        
        for table in sorted_tables:
            marker = table['marker']
            if marker in text:
                processed = table['processed'] or table['original']
                if processed:
                    text = text.replace(marker, processed)
                else:
                    text = text.replace(marker, '')
        
        # 남은 마커 제거
        for table in table_data:
            marker = table['marker']
            if marker in text:
                text = text.replace(marker, '')
        
        text = text.strip()
        text = _postprocess_duplicate_table_headers(text)
        
        return {
            "success": True,
            "processed_text": text,
            "original_length": original_length,
            "processed_length": len(text),
        }
        
    except Exception as exc:
        logger.error(f"[preprocess_markdown] Error: {exc}")
        return {
            "success": False,
            "processed_text": markdown_text,
            "original_length": len(markdown_text) if markdown_text else 0,
            "processed_length": len(markdown_text) if markdown_text else 0,
            "error": str(exc),
        }


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