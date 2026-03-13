"""
KT 공지사항 관련 핸들러

KT 공지사항, 네트워크 공지, 안전한통신생활 공지 처리
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright, BrowserContext
from markdownify import markdownify as md

from ..handler_registry import register_page_handler
from ..utils import sanitize_filename, format_content, create_markdown, launch_chromium

logger = logging.getLogger(__name__)

# goto 타임아웃 상향 (inside.kt.com 응답 느림 대비)
_GOTO_TIMEOUTS = [(45000, 'domcontentloaded'), (60000, 'load'), (90000, 'networkidle')]


async def _fetch_notice_metadata(page, url: str, attempt: int) -> Optional[Dict[str, Any]]:
    """상세 페이지에서 메타데이터 추출 (공통 로직)."""
    timeout_ms, wait_until = _GOTO_TIMEOUTS[min(attempt, len(_GOTO_TIMEOUTS) - 1)]
    response = await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
    status_code = response.status if response else None
    if status_code and status_code >= 400:
        logger.error(f"❌ HTTP {status_code}: {url}")
    try:
        await page.wait_for_selector('h1.title, .txt-content', timeout=10000)
        logger.info("✅ Notice content loaded")
    except Exception as e:
        logger.warning(f"⚠️ Content not loaded (attempt {attempt+1}): {e}")
    await page.wait_for_timeout(2000)
    return await page.evaluate("""() => {
        const title = document.querySelector('h1.title');
        const dateElement = document.querySelector('.desc');
        const contentDiv = document.querySelector('.txt-content');
        let nextLink = '';
        const nextElement = document.querySelector('a[data-bno].next-area');
        if (nextElement) {
            const nextBno = nextElement.getAttribute('data-bno');
            if (nextBno) {
                const currentUrl = window.location.href;
                const baseUrl = currentUrl.split('?')[0];
                nextLink = `${baseUrl}?bno=${nextBno}`;
            }
        }
        if (!nextLink) {
            const allElements = document.querySelectorAll('*');
            for (let elem of allElements) {
                if (elem.textContent && elem.textContent.includes('다음글')) {
                    const parent = elem.closest('a[data-bno]');
                    if (parent) {
                        const nextBno = parent.getAttribute('data-bno');
                        if (nextBno) {
                            const currentUrl = window.location.href;
                            const baseUrl = currentUrl.split('?')[0];
                            nextLink = `${baseUrl}?bno=${nextBno}`;
                            break;
                        }
                    }
                }
            }
        }
        if (!nextLink) {
            const nextLinks = document.querySelectorAll('a[href*="bno="]');
            for (let link of nextLinks) {
                if (link.textContent.includes('다음글') || link.textContent.includes('다음')) {
                    nextLink = link.href;
                    break;
                }
            }
        }
        return {
            title: title ? title.textContent.trim() : '',
            rawDate: dateElement ? dateElement.textContent.trim() : '',
            nextLink: nextLink,
            contentHtml: contentDiv ? contentDiv.innerHTML : ''
        };
    }""")


async def handle_kt_notice_detail(
    url: str, 
    fclient: Any, 
    cutoff_date: Optional[datetime] = None,
    context: Optional[BrowserContext] = None
) -> Dict[str, Any]:
    """
    KT 공지사항 개별 게시물 처리 핸들러
    
    context가 전달되면 해당 컨텍스트의 새 페이지를 사용 (브라우저 재사용).
    없으면 매번 새 Playwright 인스턴스를 생성.
    """
    if cutoff_date is None:
        cutoff_date = datetime.now() - timedelta(days=365)
    
    logger.info(f"🔗 KT notice detail: {url}")
    
    max_retries = 3
    metadata = None
    
    for attempt in range(max_retries):
        try:
            if context:
                page = await context.new_page()
                try:
                    metadata = await _fetch_notice_metadata(page, url, attempt)
                finally:
                    await page.close()
            else:
                async with async_playwright() as p:
                    browser = await launch_chromium(p)
                    ctx = await browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                    )
                    page = await ctx.new_page()
                    try:
                        metadata = await _fetch_notice_metadata(page, url, attempt)
                    finally:
                        await page.close()
                        await browser.close()
            
            if metadata['title'] and metadata['rawDate']:
                break
            elif attempt < max_retries - 1:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(2)  # 재시도 전 대기
                continue
            else:
                return {"error": "제목 또는 날짜 정보를 찾을 수 없습니다."}
                    
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Attempt {attempt + 1} error: {str(e)}, retrying...")
                continue
            else:
                logger.error(f"❌ All retries failed: {str(e)}")
                return {"error": f"페이지 로딩 실패: {str(e)}"}
    
    # 컨텐츠 HTML을 마크다운으로 변환
    if metadata['contentHtml']:
        content = md(metadata['contentHtml'])
        logger.info(f"✅ Content extracted: {len(content)} chars")
    else:
        logger.warning("⚠️ No content area, trying fallback")
        try:
            result = await fclient.scrape_url_async(url)
            if result.success:
                content = result.markdown
            else:
                content = "컨텐츠 스크래핑 실패"
        except Exception as e:
            logger.error(f"❌ Fallback failed: {str(e)}")
            content = "컨텐츠 스크래핑 실패"
    
    # 카테고리와 날짜 분리
    category = ""
    actual_date = ""
    
    category_date_match = re.match(r'^(.+?)(\d{4}\.\d{2}\.\d{2})$', metadata['rawDate'])
    if category_date_match:
        category = category_date_match.group(1).strip()
        actual_date = category_date_match.group(2)
    else:
        date_only_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', metadata['rawDate'])
        if date_only_match:
            actual_date = date_only_match.group(1)
        else:
            return {"error": f"날짜 파싱 실패: {metadata['rawDate']}"}
    
    # 날짜 cutoff 체크
    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', actual_date)
    if date_match:
        year, month, day = map(int, date_match.groups())
        post_date = datetime(year, month, day)
        if post_date < cutoff_date:
            return {"date_cutoff_reached": True, "date": actual_date}
    
    formatted_content = format_content(content)
    date_display = f"{actual_date}" + (f" (카테고리: {category})" if category else "")
    markdown_content = create_markdown(metadata['title'], date_display, formatted_content)
    
    next_url = None
    if metadata['nextLink'] and 'bno=' in metadata['nextLink']:
        next_url = metadata['nextLink']
    
    mobile_url = url.replace('inside.kt.com', 'm.kt.com') if 'inside.kt.com' in url else None
    
    startdate_hyphen = "1900-01-01"
    enddate_hyphen = "2999-12-31"
    try:
        dm = re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", actual_date)
        if dm:
            startdate_hyphen = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    except Exception:
        pass

    logger.info(f"✅ KT notice done: '{metadata['title']}'")

    return {
        "url": url,
        "mobile_url": mobile_url,
        "murl": mobile_url or '',
        "title": metadata['title'],
        "category": category,
        "date": actual_date,
        "raw_date": metadata['rawDate'],
        "startdate": startdate_hyphen,
        "enddate": enddate_hyphen,
        "markdown": markdown_content,
        "html": metadata['contentHtml'] or content,
        "next_url": next_url,
        "special_processed": True,
        "playwright_processed": True
    }


def _extract_next_url_from_bno(bno: str) -> str:
    """bno로 다음 공지 URL 생성."""
    base = "https://inside.kt.com/html/notice/notice_detail.html"
    return f"{base}?bno={bno}" if bno else ""


async def _get_next_url_from_list_page(context, list_url: str, current_bno: str) -> Optional[str]:
    """목록 페이지에서 current_bno 다음 공지의 URL 추출 (타임아웃 fallback)."""
    try:
        page = await context.new_page()
        try:
            await page.goto(list_url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_selector('a[data-bno]', timeout=10000)
            bno_list = await page.evaluate("""() => {
                const anchors = document.querySelectorAll('a[data-bno]');
                return Array.from(anchors).map(a => a.getAttribute('data-bno')).filter(Boolean);
            }""")
            if bno_list and current_bno:
                idx = next((i for i, b in enumerate(bno_list) if b == current_bno), -1)
                if idx >= 0 and idx + 1 < len(bno_list):
                    return _extract_next_url_from_bno(bno_list[idx + 1])
        finally:
            await page.close()
    except Exception as e:
        logger.warning(f"⚠️ Fallback next_url from list failed: {e}")
    return None


async def handle_kt_notice_main(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    KT 공지사항 메인 목록 페이지 처리
    - 첫 번째 공지사항부터 다음글 링크를 따라가며 처리
    - 1년 이내 게시물만 처리
    - 브라우저 1개 재사용, 타임아웃 시 목록 페이지 fallback
    """
    logger.info(f"🔗 KT notice main: {url}")
    cutoff_date = datetime.now() - timedelta(days=365)
    
    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        first_notice_link = None
        
        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logger.error(f"❌ HTTP {status_code}: {url}")
        
        for attempt in range(3):
            try:
                await page.wait_for_selector('a[data-bno]', timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(2000)
            first_notice_link = await page.evaluate("""() => {
                const firstElement = document.querySelector('a[data-bno]');
                if (firstElement) {
                    const bno = firstElement.getAttribute('data-bno');
                    return `https://inside.kt.com/html/notice/notice_detail.html?bno=${bno}`;
                }
                return null;
            }""")
            if first_notice_link:
                break
        await page.close()
        
        if not first_notice_link:
            await browser.close()
            return {"error": "첫 번째 공지사항 링크를 찾을 수 없습니다"}
        
        total_processed = 0
        current_url = first_notice_link
        menus, datas = [], []
        consecutive_errors = 0
        max_consecutive_errors = 3
        list_url = url
        
        while current_url and total_processed < 1000:
            try:
                logger.info(f"🔍 Processing {total_processed + 1}: {current_url}")
                current_bno = None
                m = re.search(r'bno=(\d+)', current_url)
                if m:
                    current_bno = m.group(1)
                
                try:
                    result = await asyncio.wait_for(
                        handle_kt_notice_detail(current_url, fclient, cutoff_date, context=context),
                        timeout=150
                    )
                    consecutive_errors = 0
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Timeout (150s): {current_url}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"❌ Stopped: {max_consecutive_errors} consecutive failures")
                        break
                    current_url = await _get_next_url_from_list_page(context, list_url, current_bno or "")
                    if not current_url:
                        break
                    await asyncio.sleep(2)
                    continue
                
                if "error" in result:
                    logger.warning(f"❌ Failed: {result['error']}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"❌ Stopped: {max_consecutive_errors} consecutive failures")
                        break
                    current_url = result.get("next_url")
                    continue
                
                if result.get("date_cutoff_reached"):
                    logger.info(f"🔍 Date cutoff reached")
                    break
                
                formatted_date = ''
                if result.get('date'):
                    date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                    if date_match:
                        formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
                
                title_clean = sanitize_filename(result.get('title', 'unknown'))
                last_folder = f"({formatted_date}){title_clean}" if formatted_date else title_clean
                
                menus.append({
                    'menu': f"{menu}^{last_folder}" if menu else last_folder,
                    'url': current_url
                })
                datas.append(result)
                total_processed += 1
                
                current_url = result.get("next_url")
                if not current_url:
                    logger.info("🔗 No next link")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Error: {str(e)}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"❌ Stopped: {max_consecutive_errors} consecutive failures")
                    break
                if current_bno:
                    current_url = await _get_next_url_from_list_page(context, list_url, current_bno)
                    if current_url:
                        await asyncio.sleep(2)
                        continue
                break
        
        await browser.close()
    
    logger.info(f"✅ KT notice done: {total_processed} items")
    
    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 게시물 처리됨"
    }


# 핸들러 등록
register_page_handler(
    r'https?://inside\.kt\.com/html/notice/notice_list\.html',
    handle_kt_notice_main
)




