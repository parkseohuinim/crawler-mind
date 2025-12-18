"""
네트워크 공지사항 관련 핸들러

네트워크 공지사항 목록 및 상세 페이지 처리
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler
from ..utils import sanitize_filename, format_content, create_markdown

logger = logging.getLogger(__name__)


async def handle_network_notice_detail(
    url: str, 
    fclient: Any, 
    cutoff_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    네트워크 공지사항 개별 게시물 처리 핸들러
    """
    logger.info(f"🔗 Network notice detail: {url}")
    
    if cutoff_date is None:
        cutoff_date = datetime.now() - timedelta(days=365)
    
    metadata = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            response = await page.goto(url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(5000)
            
            status_code = response.status if response else None
            if status_code and status_code >= 400:
                logger.error(f"❌ HTTP {status_code}: {url}")
            
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=30000)
            except Exception as e:
                logger.warning(f"⚠️ Load timeout: {str(e)}")
            
            title = await page.evaluate("""() => {
                const t = document.querySelector('h1.title');
                return t ? t.textContent.trim() : '';
            }""")
            raw_date = await page.evaluate("""() => {
                const d = document.querySelector('.desc');
                return d ? d.textContent.trim() : '';
            }""")
            
            if title and raw_date:
                content_html = ""
                for selector in ['.txt-content', '.contents', '.content', '.detail-content', '.notice-content', 'main', '.main-content']:
                    content_div = await page.query_selector(selector)
                    if content_div:
                        html = await content_div.inner_html()
                        if html.strip():
                            content_html = html
                            break
                
                next_link = await page.evaluate("""() => {
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
                    return nextLink;
                }""")
                
                await browser.close()
                metadata = {
                    'title': title,
                    'rawDate': raw_date,
                    'nextLink': next_link,
                    'contentHtml': content_html
                }
            else:
                await browser.close()
                return {"error": "제목 또는 날짜 정보를 찾을 수 없습니다."}

    except Exception as e:
        logger.error(f"❌ Network notice failed: {str(e)}")
        return {"error": f"페이지 로딩 실패: {str(e)}"}
    
    # 컨텐츠 HTML을 마크다운으로 변환
    if metadata['contentHtml']:
        content = md(metadata['contentHtml'])
    else:
        logger.info("⚠️ No HTML, trying fallback")
        try:
            result = await fclient.scrape_single_url(url)
            if result.get("markdown"):
                content = result["markdown"]
            else:
                content = "컨텐츠 스크래핑 실패"
        except Exception as e:
            content = "컨텐츠 스크래핑 실패"
            logger.error(f"❌ Fallback failed: {str(e)}")
    
    # 카테고리와 날짜 분리
    raw_date = metadata.get('rawDate', '')
    date_only_match = re.search(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', raw_date)
    if date_only_match:
        actual_date = date_only_match.group(1)
        category = raw_date[:raw_date.find(actual_date)].strip() if raw_date.find(actual_date) > 0 else ""
    else:
        return {"error": f"날짜 파싱 실패: {raw_date}"}
    
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
    
    startdate_hyphen = "0000-00-00"
    enddate_hyphen = "9999-99-99"
    try:
        dm = re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", actual_date)
        if dm:
            startdate_hyphen = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    except Exception:
        pass

    logger.info(f"✅ Network notice done: '{metadata['title']}'")

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


async def handle_network_notice_main(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    네트워크 공지사항 메인 목록 페이지 처리
    """
    logger.info(f"🔗 Network notice main: {url}")
    cutoff_date = datetime.now() - timedelta(days=365)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        first_bno = None
        
        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logger.error(f"❌ HTTP {status_code}: {url}")
        
        for attempt in range(3):
            try:
                await page.wait_for_selector('a[data-bno]', timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(2000)
            first_bno = await page.evaluate("""() => {
                const firstLink = document.querySelector('a[data-bno]');
                return firstLink ? firstLink.getAttribute('data-bno') : null;
            }""")
            if first_bno:
                break
        await browser.close()
    
    if not first_bno:
        return {"error": "첫 번째 게시물을 찾을 수 없습니다"}
    
    first_url = f"https://inside.kt.com/html/notice/net_notice_detail.html?bno={first_bno}"
    current_url = first_url
    total_processed = 0
    menus, datas = [], []
    max_iterations = 1000
    
    consecutive_errors = 0
    max_consecutive_errors = 3
    
    for i in range(max_iterations):
        if not current_url:
            break
        try:
            logger.info(f"🔍 Processing {total_processed + 1}: {current_url}")
            
            # 개별 상세 페이지에 120초(2분) 타임아웃 적용
            try:
                result = await asyncio.wait_for(
                    handle_network_notice_detail(current_url, fclient, cutoff_date),
                    timeout=120
                )
                consecutive_errors = 0
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Timeout (120s): {current_url}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"❌ Stopped: {max_consecutive_errors} consecutive failures")
                    break
                break
            
            if "error" in result:
                logger.warning(f"❌ Failed: {result['error']}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    break
                current_url = result.get("next_url")
                continue
            elif result.get("date_cutoff_reached"):
                logger.info("🔍 Date cutoff reached")
                break
            else:
                formatted_date = ''
                if result.get('date'):
                    date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                    if date_match:
                        formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
                
                title_clean = sanitize_filename(result.get('title', 'unknown'))
                last_folder = f"({formatted_date}){title_clean}" if formatted_date else title_clean
                
                menus.append({
                    'menu': f"{menu}^{last_folder}" if menu else last_folder,
                    'url': current_url,
                    'murl': result.get('murl')
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
                break
            break
    
    logger.info(f"✅ Network notice done: {total_processed} items")
    
    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 네트워크 공지사항 처리 완료"
    }


# 핸들러 등록
register_page_handler(
    r'https?://inside\.kt\.com/html/notice/net_notice_list\.html',
    handle_network_notice_main
)




