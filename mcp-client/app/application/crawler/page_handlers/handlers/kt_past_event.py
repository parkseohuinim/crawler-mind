"""
KT 지난 이벤트 관련 핸들러

지난 이벤트 목록 및 상세 페이지 처리
(현재 주석 처리되어 있음 - 필요시 활성화)
"""

import asyncio
import logging
import re
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md
from bs4 import BeautifulSoup

from ..handler_registry import register_page_handler

logger = logging.getLogger(__name__)


def _pc_to_mobile_url(pc_url: str) -> str:
    """PC 이벤트 URL을 모바일 URL로 변환"""
    if not pc_url:
        return ""
    m = re.search(r"pcEvtNo=(\d+)", pc_url)
    if not m:
        return pc_url.replace('https://event.kt.com', 'https://m.kt.com').replace('pcEvtNo=', 'mblevtno=')
    pc_no = int(m.group(1))
    mb_no = pc_no + 1
    mobile = pc_url.replace('https://event.kt.com', 'https://m.kt.com')
    mobile = re.sub(r"pcEvtNo=\d+", f"mblevtno={mb_no}", mobile)
    return mobile


def _parse_date_to_hyphen(s: str) -> str:
    """날짜 문자열을 YYYY-MM-DD 형식으로 변환"""
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s or "")
    if not m:
        return ""
    return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"


async def handle_kt_past_event_detail(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None,
    main_event_info: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    KT 지난 이벤트 상세 페이지 핸들러
    """
    logger.info(f"KT Past Event detail processing started: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            max_retries = 3
            retry_count = 0
            response = None
            
            while retry_count < max_retries:
                try:
                    response = await page.goto(url, wait_until='networkidle', timeout=60000)
                    await page.wait_for_timeout(5000)
                    break
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise e
                    await page.wait_for_timeout(3000)
            
            status_code = response.status if response else None
            if status_code and status_code >= 400:
                logger.error(f"❌ KT Past Event detail ({url}): HTTP {status_code} error")
            
            # 페이지 콘텐츠 확인
            page_content = await page.evaluate("""() => {
                const contentsDiv = document.querySelector('.contents');
                if (!contentsDiv) {
                    return { empty: true, text: '', terminated: false, error: 'Contents div not found' };
                }
                
                const boxClose = contentsDiv.querySelector('.box-close');
                const isTerminated = boxClose && boxClose.textContent.includes('이벤트가 종료');
                
                const titleElem = contentsDiv.querySelector('#contents-title, .contents-title');
                const title = titleElem ? titleElem.textContent.trim() : '';
                
                return {
                    empty: false,
                    terminated: isTerminated,
                    title: title,
                    contentsHTML: contentsDiv.outerHTML,
                    terminatedMessage: boxClose ? boxClose.textContent.trim() : ''
                };
            }""")
            
            evt_no_match = re.search(r'pcEvtNo=(\d+)', url)
            evt_no = evt_no_match.group(1) if evt_no_match else 'unknown'
            
            if page_content.get('empty', False):
                await browser.close()
                return {
                    "datas": [{
                        "markdown": f"# 종료된 이벤트({evt_no})\n\n이벤트가 종료되었습니다.",
                        "html": f"<h1>종료된 이벤트({evt_no})</h1><p>이벤트가 종료되었습니다.</p>",
                        "url": url,
                        "title": f"종료된 이벤트({evt_no})",  # title 추가
                        "metadata": {
                            "title": f"종료된 이벤트({evt_no})",
                            "evt_no": evt_no,
                            "status": "종료",
                            "empty_content": True,
                            "startdate": "1900-01-01",
                            "enddate": "2999-12-31"
                        }
                    }]
                }
            
            # 이벤트 정보 추출
            event_info = await page.evaluate("""() => {
                const info = {};
                const contentsDiv = document.querySelector('.contents');
                if (contentsDiv) {
                    const titleElem = contentsDiv.querySelector('#contents-title, .contents-title');
                    if (titleElem) {
                        info.title = titleElem.textContent.trim();
                    }
                    
                    const iframe = contentsDiv.querySelector('iframe');
                    if (iframe && iframe.getAttribute('src')) {
                        info.iframe_src = iframe.getAttribute('src');
                    }
                }
                return info;
            }""")
            
            if main_event_info and main_event_info.get('title'):
                event_info['title'] = main_event_info['title']
            
            startdate = '1900-01-01'
            enddate = '2999-12-31'
            period_text = event_info.get('period') or ''
            if period_text:
                parts = [p.strip() for p in re.split(r"~|–|-|to", period_text) if p and p.strip()]
                if len(parts) >= 1:
                    sd = _parse_date_to_hyphen(parts[0])
                    if sd:
                        startdate = sd
                if len(parts) >= 2:
                    ed = _parse_date_to_hyphen(parts[1])
                    if ed:
                        enddate = ed
            
            content_html = page_content.get('contentsHTML', '')
            
            # iframe 처리
            if event_info.get('iframe_src'):
                try:
                    iframe_page = await context.new_page()
                    await iframe_page.goto(event_info['iframe_src'], wait_until='networkidle', timeout=60000)
                    await iframe_page.wait_for_timeout(8000)
                    
                    iframe_data = await iframe_page.evaluate("""() => {
                        const elementsToRemove = document.querySelectorAll('script, style, noscript, .ad, .banner, .popup');
                        elementsToRemove.forEach(el => el.remove());
                        const mainContent = document.querySelector('body') || document.documentElement;
                        return {
                            html: mainContent ? mainContent.innerHTML : ''
                        };
                    }""")
                    
                    iframe_content = iframe_data.get('html', '')
                    content_html += f"\n\n<div class='iframe-content'>{iframe_content}</div>"
                    
                    await iframe_page.close()
                    
                except Exception as e:
                    logger.warning(f"⚠️ iframe processing failed: {str(e)}")
            
            # 마크다운 생성
            markdown_content = f"# {event_info.get('title', 'KT 지난 이벤트')}\n\n"
            
            if content_html:
                try:
                    soup = BeautifulSoup(content_html, 'html.parser')
                    for tag in soup(['script', 'style', 'noscript']):
                        tag.decompose()
                    for selector in ['.btn-twitter', '.btn-facebook', '.btn-kakao', '.btn-youtube']:
                        for element in soup.select(selector):
                            element.decompose()
                    
                    cleaned_html = str(soup)
                    content_markdown = md(cleaned_html)
                    markdown_content += content_markdown
                except Exception as e:
                    markdown_content += f"콘텐츠 변환 실패: {str(e)}\n"
            else:
                markdown_content += "이벤트 상세 내용을 불러올 수 없습니다.\n"
            
            # HTML 생성
            html_content = f"<h1>{event_info.get('title', 'KT 지난 이벤트')}</h1>"
            if content_html:
                html_content += content_html
            else:
                html_content += "<p>이벤트 상세 내용을 불러올 수 없습니다.</p>"
            
            await browser.close()
            
            return {
                "datas": [{
                    "markdown": markdown_content,
                    "html": html_content,
                    "url": url,
                    "title": event_info.get('title', 'KT 지난 이벤트'),  # title 추가
                    "metadata": {
                        "title": event_info.get('title', 'KT 지난 이벤트'),
                        "evt_no": evt_no,
                        "status": "종료",
                        "startdate": startdate,
                        "enddate": enddate,
                        "special_processed": True,
                        "playwright_processed": True
                    }
                }]
            }
            
        except Exception as e:
            logger.error(f"❌ KT Past Event detail processing failed: {str(e)}")
            await browser.close()
            
            evt_no_match = re.search(r'pcEvtNo=(\d+)', url)
            evt_no = evt_no_match.group(1) if evt_no_match else 'unknown'
            
            return {
                "datas": [{
                    "markdown": f"# KT 지난 이벤트 처리 실패\n\n오류: {str(e)}",
                    "html": f"<h1>KT 지난 이벤트 처리 실패</h1><p>오류: {str(e)}</p>",
                    "url": url,
                    "title": "KT 지난 이벤트 처리 실패",  # title 추가
                    "metadata": {
                        "title": "KT 지난 이벤트 처리 실패",
                        "evt_no": evt_no,
                        "error": str(e),
                        "status": "오류"
                    }
                }]
            }


async def handle_kt_past_event_main(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    KT 지난 이벤트 메인 페이지 핸들러
    """
    logger.info(f"🎯 KT Past Event main processing started: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            response = await page.goto(url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(5000)
            
            status_code = response.status if response else None
            if status_code and status_code >= 400:
                logger.error(f"❌ KT Past Event main ({url}): HTTP {status_code} error")
            
            # 페이지네이션 정보 추출
            pagination_info = await page.evaluate("""() => {
                const pagination = document.querySelector('.pagination');
                if (!pagination) return { total_pages: 1, current_page: 1 };
                
                const currentPageElem = pagination.querySelector('span[title="현재위치"]');
                const currentPage = currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                
                const pageLinks = pagination.querySelectorAll('a[data-page]');
                let maxPage = currentPage;
                
                pageLinks.forEach(link => {
                    const dataPage = link.getAttribute('data-page');
                    if (dataPage) {
                        const pageNum = parseInt(dataPage);
                        if (!isNaN(pageNum) && pageNum > maxPage) {
                            maxPage = pageNum;
                        }
                    }
                });
                
                const lastLink = pagination.querySelector('a.last');
                const nextLink = pagination.querySelector('a.next');
                
                return { 
                    total_pages: maxPage, 
                    current_page: currentPage,
                    has_next: !!nextLink,
                    has_last: !!lastLink
                };
            }""")
            
            all_event_infos = []
            
            # 마지막 페이지 확인
            if pagination_info.get('has_last', False):
                try:
                    await page.evaluate("""() => {
                        const pagination = document.querySelector('.pagination');
                        if (pagination) {
                            const lastLink = pagination.querySelector('a.last');
                            if (lastLink) {
                                lastLink.click();
                            }
                        }
                    }""")
                    
                    await page.wait_for_timeout(3000)
                    
                    last_page_info = await page.evaluate("""() => {
                        const pagination = document.querySelector('.pagination');
                        if (!pagination) return { last_page: 1 };
                        
                        const currentPageElem = pagination.querySelector('span[title="현재위치"]');
                        const lastPage = currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                        
                        return { last_page: lastPage };
                    }""")
                    
                    total_pages = last_page_info.get('last_page', pagination_info.get('total_pages', 1))
                    
                    await page.evaluate("""() => {
                        const pagination = document.querySelector('.pagination');
                        if (pagination) {
                            const firstLink = pagination.querySelector('a.first');
                            if (firstLink) {
                                firstLink.click();
                            }
                        }
                    }""")
                    
                    await page.wait_for_timeout(3000)
                    
                except Exception:
                    total_pages = pagination_info.get('total_pages', 1)
            else:
                total_pages = pagination_info.get('total_pages', 1)
            
            logger.info(f"📄 Starting event collection from {total_pages} pages")
            
            # 모든 페이지 처리
            current_page = 1
            for page_num in range(1, total_pages + 1):
                if page_num > current_page:
                    while current_page < page_num:
                        page_moved = await page.evaluate("""() => {
                            const pagination = document.querySelector('.pagination');
                            if (!pagination) return false;
                            const nextLink = pagination.querySelector('a.next');
                            if (nextLink) {
                                nextLink.click();
                                return true;
                            }
                            return false;
                        }""")
                        
                        if page_moved:
                            await page.wait_for_timeout(3000)
                            actual_page = await page.evaluate("""() => {
                                const pagination = document.querySelector('.pagination');
                                if (!pagination) return 1;
                                const currentPageElem = pagination.querySelector('span[title="현재위치"]');
                                return currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                            }""")
                            
                            if actual_page > current_page:
                                current_page = actual_page
                            else:
                                break
                        else:
                            break
                    
                    if current_page != page_num:
                        continue
                
                # 현재 페이지의 이벤트 추출
                page_events = await page.evaluate(f"""() => {{
                    const events = [];
                    const table = document.querySelector('table.board');
                    if (!table) return events;
                    
                    const tbody = table.querySelector('tbody');
                    if (!tbody) return events;
                    
                    const rows = tbody.querySelectorAll('tr');
                    
                    rows.forEach((row) => {{
                        const link = row.querySelector('a[data-pcevtno]');
                        if (link) {{
                            const evtNo = link.getAttribute('data-pcevtno');
                            if (evtNo) {{
                                const title = link.textContent.trim();
                                const cells = row.querySelectorAll('td');
                                const period = cells.length > 1 ? cells[1].textContent.trim() : '';
                                
                                events.push({{
                                    page: {page_num},
                                    evt_no: evtNo,
                                    title: title,
                                    period: period,
                                    link_href: link.href || ''
                                }});
                            }}
                        }}
                    }});
                    
                    return events;
                }}""")
                
                all_event_infos.extend(page_events)
                logger.info(f"📄 Page {page_num}/{total_pages}: {len(page_events)} events")
            
            # 진입 페이지 추출
            entry_page_html = await page.content()
            entry_page_markdown = md(entry_page_html, heading_style="ATX")
            
            entry_page_data = {
                "markdown": entry_page_markdown,
                "html": entry_page_html,
                "url": url,
                "title": f"{menu or 'KT 지난 이벤트'} 목록",  # title 추가
                "metadata": {
                    "title": f"{menu or 'KT 지난 이벤트'} 목록",
                    "is_entry_page": True,
                    "total_events": len(all_event_infos),
                    "total_pages": total_pages,
                    "special_processed": True,
                    "playwright_processed": True
                }
            }
            
            await browser.close()
            
            # 중복 제거
            unique_events = {}
            for event in all_event_infos:
                evt_no = event['evt_no']
                if evt_no not in unique_events:
                    unique_events[evt_no] = event
            
            unique_event_list = list(unique_events.values())
            logger.info(f"🎯 After duplicate removal: {len(unique_event_list)} events")
            
            # 병렬 처리
            individual_posts = [entry_page_data]
            if unique_event_list:
                logger.info(f"🚀 Starting parallel processing for {len(unique_event_list)} events")
                
                semaphore = asyncio.Semaphore(15)
                
                async def process_single_event(event_info, event_index):
                    async with semaphore:
                        try:
                            detail_url = f"https://event.kt.com/html/event/past_event_view.html?page={event_info['page']}&searchCtg=ALL&pcEvtNo={event_info['evt_no']}"
                            detail_result = await handle_kt_past_event_detail(detail_url, fclient, menu, event_info)
                            
                            if detail_result and "datas" in detail_result and detail_result["datas"]:
                                individual_post = detail_result["datas"][0]
                                individual_post["metadata"].update({
                                    "evt_no": event_info['evt_no'],
                                    "post_index": event_index + 1,
                                    "total_posts": len(unique_event_list),
                                    "source_page": event_info['page']
                                })
                                return individual_post, event_info
                            else:
                                display_title = event_info['title'] if event_info['title'].strip() else f"지난 이벤트({event_info['evt_no']})"
                                individual_post = {
                                    "markdown": f"# {display_title}\n\n이벤트가 종료되었습니다.",
                                    "html": f"<h1>{display_title}</h1><p>이벤트가 종료되었습니다.</p>",
                                    "url": detail_url,
                                    "title": display_title,  # title 추가
                                    "metadata": {
                                        "title": display_title,
                                        "evt_no": event_info['evt_no'],
                                        "status": "종료",
                                        "detail_processing_failed": True
                                    }
                                }
                                return individual_post, event_info
                                
                        except Exception as e:
                            logger.error(f"❌ Event processing failed: {str(e)}")
                            display_title = event_info['title'] if event_info['title'].strip() else f"지난 이벤트({event_info['evt_no']})"
                            individual_post = {
                                "markdown": f"# {display_title}\n\n처리 실패: {str(e)}",
                                "html": f"<h1>{display_title}</h1><p>처리 실패: {str(e)}</p>",
                                "url": f"https://event.kt.com/html/event/past_event_view.html?pcEvtNo={event_info['evt_no']}",
                                "title": display_title,  # title 추가
                                "metadata": {
                                    "title": display_title,
                                    "evt_no": event_info['evt_no'],
                                    "error": str(e)
                                }
                            }
                            return individual_post, event_info
                
                tasks = [process_single_event(event_info, i) for i, event_info in enumerate(unique_event_list)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"❌ Parallel processing exception: {str(result)}")
                    else:
                        individual_post, event_info = result
                        individual_posts.append(individual_post)
            
            # menus 배열 생성
            menus = [{
                "menu": menu or "KT 지난 이벤트",
                "url": url,
                "murl": url.replace('https://event.kt.com', 'https://m.kt.com')
            }]
            
            for post in individual_posts:
                post_metadata = post.get('metadata', {})
                post_title = post_metadata.get('title', '제목 없음')
                evt_no = post_metadata.get('evt_no', 'unknown')
                post_url = post.get('url', '')
                
                final_menu = f"{menu}^{post_title}({evt_no})" if menu else f"{post_title}({evt_no})"
                
                menus.append({
                    "menu": final_menu,
                    "url": post_url,
                    "murl": _pc_to_mobile_url(post_url)
                })
            
            logger.info(f"✅ KT Past Event main completed: {len(unique_event_list)} events")
            
            return {
                "datas": individual_posts,
                "menus": menus,
                "metadata": {
                    "title": "KT 지난 이벤트",
                    "total_events": len(unique_event_list),
                    "total_pages": total_pages,
                    "url": url,
                    "special_processed": True,
                    "playwright_processed": True,
                    "parallel_processed": True
                }
            }
            
        except Exception as e:
            logger.error(f"❌ KT Past Event main processing failed: {str(e)}")
            await browser.close()
            return {
                "markdown": f"# KT 지난 이벤트 페이지 처리 실패\n\n오류: {str(e)}",
                "html": f"<h1>KT 지난 이벤트 페이지 처리 실패</h1><p>오류: {str(e)}</p>",
                "datas": [],
                "error": str(e)
            }


# 핸들러 등록
register_page_handler(
    r'https?://event\.kt\.com/html/event/past_event_list\.html',
    handle_kt_past_event_main
)

register_page_handler(
    r'https?://event\.kt\.com/html/event/past_event_view\.html\?.*pcEvtNo=\d+',
    handle_kt_past_event_detail
)


