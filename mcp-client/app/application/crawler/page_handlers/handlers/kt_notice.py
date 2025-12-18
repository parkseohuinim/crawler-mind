"""
KT 공지사항 관련 핸들러

KT 공지사항, 네트워크 공지, 안전한통신생활 공지 처리
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


async def handle_kt_notice_detail(
    url: str, 
    fclient: Any, 
    cutoff_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    KT 공지사항 개별 게시물 처리 핸들러
    """
    if cutoff_date is None:
        cutoff_date = datetime.now() - timedelta(days=365)
    
    logger.info(f"🔗 KT notice detail: {url}")
    
    max_retries = 3
    metadata = None
    
    for attempt in range(max_retries):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                if attempt == 0:
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await page.wait_for_timeout(3000)
                elif attempt == 1:
                    response = await page.goto(url, wait_until='load', timeout=40000)
                    await page.wait_for_timeout(5000)
                else:
                    response = await page.goto(url, wait_until='networkidle', timeout=50000)
                    await page.wait_for_timeout(7000)
                
                status_code = response.status if response else None
                if status_code and status_code >= 400:
                    logger.error(f"❌ HTTP {status_code}: {url}")
                
                metadata = await page.evaluate("""() => {
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
                
                await browser.close()
                
                if metadata['title'] and metadata['rawDate']:
                    break
                elif attempt < max_retries - 1:
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed, retrying...")
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
    
    startdate_hyphen = "0000-00-00"
    enddate_hyphen = "9999-99-99"
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


async def handle_kt_notice_main(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    KT 공지사항 메인 목록 페이지 처리
    - 첫 번째 공지사항부터 다음글 링크를 따라가며 처리
    - 1년 이내 게시물만 처리
    """
    logger.info(f"🔗 KT notice main: {url}")
    cutoff_date = datetime.now() - timedelta(days=365)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
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
        await browser.close()
    
    if not first_notice_link:
        return {"error": "첫 번째 공지사항 링크를 찾을 수 없습니다"}
    
    total_processed = 0
    current_url = first_notice_link
    menus, datas = [], []
    
    consecutive_errors = 0
    max_consecutive_errors = 3  # 연속 3회 실패 시 중단
    
    while current_url and total_processed < 1000:
        try:
            logger.info(f"🔍 Processing {total_processed + 1}: {current_url}")
            
            # 개별 상세 페이지에 120초(2분) 타임아웃 적용
            try:
                result = await asyncio.wait_for(
                    handle_kt_notice_detail(current_url, fclient, cutoff_date),
                    timeout=120
                )
                consecutive_errors = 0  # 성공 시 에러 카운터 초기화
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Timeout (120s): {current_url}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"❌ Stopped: {max_consecutive_errors} consecutive failures")
                    break
                # 타임아웃 시 다음 URL을 알 수 없으므로 중단
                break
            
            if "error" in result:
                logger.warning(f"❌ Failed: {result['error']}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"❌ Stopped: {max_consecutive_errors} consecutive failures")
                    break
                # 다음 URL로 계속 시도 (next_url이 있으면)
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
            # 예외 발생 시 다음 URL을 알 수 없으므로 중단
            break
    
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




