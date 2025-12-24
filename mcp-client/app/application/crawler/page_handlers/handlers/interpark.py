"""
인터파크 공연예매 관련 핸들러

공연예매 공지사항 목록 및 상세 페이지 처리
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler
from ..utils import sanitize_filename, format_date_show, format_content, create_markdown, smart_goto

logger = logging.getLogger(__name__)


async def handle_show_notice(url: str, fclient: Any) -> Dict[str, Any]:
    """
    공연예매 공지사항 개별 게시물 처리 핸들러
    - 제목, 날짜, 다음글 링크만 selector로 추출
    - 전체 컨텐츠는 Playwright로 처리, 실패 시 fclient fallback
    """
    logger.info(f"🔗 Show notice detail: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        response = await smart_goto(page, url, wait_for_selector='.vip-detail-content', timeout=30000)
        
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logger.error(f"❌ HTTP {status_code}: {url}")
            elif status_code >= 300:
                logger.warning(f"⚠️ HTTP {status_code} redirect: {url}")
            else:
                logger.info(f"✅ HTTP {status_code}: {url}")
        
        metadata = await page.evaluate("""() => {
            const title = document.querySelector('.sub-title06')?.textContent?.trim() || '';
            const date = document.querySelector('.reverse li:first-child')?.textContent?.trim() || '';
            const prevElement = document.querySelector('.inventory-list li:has(strong.next) div a');
            const prevLink = prevElement?.getAttribute('href') || '';
            const prevText = prevElement?.textContent || '';
            
            let contentHtml = '';
            const contentSelectors = ['.vip-detail-content', '.contents', '.content', '.detail-content', '.notice-content', 'main', '.main-content'];
            for (let selector of contentSelectors) {
                const contentDiv = document.querySelector(selector);
                if (contentDiv && contentDiv.innerHTML.trim()) {
                    contentHtml = contentDiv.innerHTML;
                    break;
                }
            }
            
            return {title, date, prevLink, prevText, contentHtml};
        }""")
        await browser.close()
    
    if not metadata['title'] or not metadata['date']:
        return {"error": "제목 또는 날짜 정보를 찾을 수 없습니다."}
    
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
                logger.info("✅ Fallback success")
            else:
                content = "컨텐츠 스크래핑 실패"
                logger.error("❌ Fallback failed")
        except Exception as e:
            logger.error(f"❌ Fallback failed: {str(e)}")
            content = "컨텐츠 스크래핑 실패"
    
    # 날짜 검증 및 포맷팅
    formatted_date = format_date_show(metadata['date'])
    if not formatted_date:
        return {"error": "날짜 형식 변환 실패"}
    
    formatted_content = format_content(content)
    markdown_content = create_markdown(metadata['title'], metadata['date'].replace('날짜', ''), formatted_content)
    
    # 다음글 URL 처리
    next_url = None
    if metadata['prevLink'] and "이전글이 없습니다" not in metadata['prevText']:
        base_url = url.split('/Partner/KT/Event/')[0]
        next_url = f"{base_url}/Partner/KT/Event/{metadata['prevLink']}"
    
    # startdate/enddate 계산
    startdate_hyphen = "0000-00-00"
    enddate_hyphen = "9999-99-99"
    try:
        dm = re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", metadata.get('date', ''))
        if dm:
            startdate_hyphen = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    except Exception:
        pass

    logger.info(f"✅ Show notice done: '{metadata['title']}'")
    
    return {
        "url": url,
        "title": metadata['title'],
        "date": metadata['date'],
        "startdate": startdate_hyphen,
        "enddate": enddate_hyphen,
        "markdown": markdown_content,
        "html": metadata['contentHtml'] or content,
        "next_url": next_url,
        "special_processed": True,
        "playwright_processed": True
    }


async def handle_interpark_notice_main(url: str, fclient: Any, menu: Optional[str] = None) -> Dict[str, Any]:
    """
    인터파크 공연예매 공지사항 메인 목록 페이지 처리
    - 목록에서 공지사항 정보 추출
    - 각 공지사항 상세 페이지 처리
    - 1년 이내 게시물만 처리
    """
    logger.info(f"🔗 Show notice main: {url}")
    cutoff_date = datetime.now() - timedelta(days=365)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(2000)
        
        status_code = response.status if response else None
        
        notice_data = await page.evaluate(r"""() => {
            const notices = [];
            
            let table = document.querySelector('table.board.dir-vertical');
            
            if (!table) {
                const tables = document.querySelectorAll('table');
                for (let t of tables) {
                    if (t.querySelector('a[href*="NoticeView"]')) {
                        table = t;
                        break;
                    }
                }
            }
            
            if (!table) {
                const links = document.querySelectorAll('a[href*="NoticeView"]');
                links.forEach((link, index) => {
                    let dateText = '';
                    let numberText = (index + 1).toString();
                    let viewsText = '';
                    
                    const row = link.closest('tr');
                    if (row) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            numberText = cells[0] ? cells[0].textContent.trim() : numberText;
                            dateText = cells[2] ? cells[2].textContent.trim() : '';
                            viewsText = cells[3] ? cells[3].textContent.trim() : '';
                        }
                    }
                    
                    if (!dateText || !/\d{4}[.\-]\d{1,2}[.\-]\d{1,2}/.test(dateText)) {
                        const parentText = link.parentElement ? link.parentElement.textContent : '';
                        const dateMatch = parentText.match(/(\d{4}[.\-]\d{1,2}[.\-]\d{1,2})/);
                        if (dateMatch) {
                            dateText = dateMatch[1];
                        } else {
                            dateText = new Date().toISOString().split('T')[0];
                        }
                    }
                    
                    notices.push({
                        number: numberText,
                        title: link.textContent.trim(),
                        date: dateText,
                        views: viewsText,
                        relativeHref: link.getAttribute('href'),
                        fullHref: link.href
                    });
                });
                
                return { notices: notices, method: 'direct_links' };
            }
            
            const rows = table.querySelectorAll('tr:not(:first-child)');
            
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 3) {
                    let link = cells[1] ? cells[1].querySelector('a[href*="NoticeView"]') : null;
                    
                    if (!link) {
                        for (let cell of cells) {
                            link = cell.querySelector('a[href*="NoticeView"]');
                            if (link) break;
                        }
                    }
                    
                    if (link) {
                        notices.push({
                            number: cells[0] ? cells[0].textContent.trim() : '',
                            title: link.textContent.trim(),
                            date: cells[2] ? cells[2].textContent.trim() : '',
                            views: cells[3] ? cells[3].textContent.trim() : '',
                            relativeHref: link.getAttribute('href'),
                            fullHref: link.href
                        });
                    }
                }
            });
            
            return { notices: notices, method: 'table', tableFound: !!table };
        }""")
        await browser.close()
    
    notices = notice_data.get('notices', [])
    method = notice_data.get('method', 'unknown')
    
    if not notices:
        logger.warning("⚠️ No notices found")
        return {"message": "No notices found", "total_processed": 0}
    
    logger.info(f"🔍 Found {len(notices)} notices (method: {method})")
    
    menus, datas = [], []
    total_processed = 0
    
    for notice in notices:
        try:
            date_str = notice['date']
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_str)
            if date_match:
                year, month, day = map(int, date_match.groups())
                post_date = datetime(year, month, day)
                if post_date < cutoff_date:
                    logger.info(f"🔍 Date cutoff: '{notice['title'][:30]}...'")
                    break
            
            logger.info(f"🔍 [{total_processed+1}/{len(notices)}] Processing: {notice['title'][:50]}...")
            result = await handle_show_notice(notice['fullHref'], fclient)
            
            if "error" in result:
                logger.warning(f"❌ Failed: {result['error']}")
                continue
            
            formatted_date = ''
            if result.get('date'):
                date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                if date_match:
                    formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            
            title_clean = sanitize_filename(result.get('title', 'unknown'))
            last_folder = f"({formatted_date}){title_clean}" if formatted_date else title_clean
            
            menus.append({
                'menu': f"{menu}^{last_folder}" if menu else last_folder,
                'url': notice['fullHref']
            })
            datas.append(result)
            total_processed += 1
            logger.info(f"✅ Done: {total_processed} items")
            
        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            continue
    
    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 공지사항 처리 완료",
        "status_code": status_code
    }


# 핸들러 등록
register_page_handler(
    r'https?://kt\.interpark\.com/Partner/KT/Event/NoticeList\.asp.*',
    handle_interpark_notice_main
)




