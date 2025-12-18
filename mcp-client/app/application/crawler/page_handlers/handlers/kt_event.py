"""
KT 이벤트 관련 핸들러

진행중인 이벤트/지난 이벤트 목록 및 상세 페이지 처리
"""

import logging
import re
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md
from bs4 import BeautifulSoup

from ..handler_registry import register_page_handler

logger = logging.getLogger(__name__)


def _pc_to_mobile_url(pc_url: str) -> str:
    """PC 이벤트 URL을 모바일 URL로 변환 (mblevtno = pcEvtNo + 1)"""
    if not pc_url:
        return ""
    m = re.search(r"pcEvtNo=(\d+)", pc_url)
    if not m:
        mobile = pc_url.replace('https://event.kt.com', 'https://m.kt.com')
        mobile = mobile.replace('pcEvtNo=', 'mblevtno=')
        if 'past_event_view.html' in mobile and 'rows=' not in mobile:
            mobile += ('&' if '?' in mobile else '?') + 'rows=10'
        return mobile
    pc_no = int(m.group(1))
    mb_no = pc_no + 1
    mobile = pc_url.replace('https://event.kt.com', 'https://m.kt.com')
    mobile = re.sub(r"pcEvtNo=\d+", f"mblevtno={mb_no}", mobile)
    if 'past_event_view.html' in mobile and 'rows=' not in mobile:
        mobile += ('&' if '?' in mobile else '?') + 'rows=10'
    return mobile


def _parse_date_to_hyphen(s: str) -> str:
    """날짜 문자열을 YYYY-MM-DD 형식으로 변환"""
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s or "")
    if not m:
        return ""
    return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"


async def handle_kt_event_detail(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    KT 이벤트 상세 페이지 핸들러
    """
    logger.info(f"KT Event detail processing started: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)
            
            status_code = response.status if response else None
            if status_code and status_code >= 400:
                logger.error(f"❌ KT Event detail ({url}): HTTP {status_code} error")
            
            # 이벤트 정보 추출
            event_info = await page.evaluate("""() => {
                const info = {};
                
                const titleElem = document.querySelector('#contents-title, .contents-title, h1, .title');
                if (titleElem) {
                    const snsButtons = titleElem.querySelectorAll('.btn-twitter, .btn-facebook, .btn-kakao, .btn-youtube, [class*="share"], [onclick*="share"]');
                    snsButtons.forEach(btn => btn.remove());
                    info.title = titleElem.textContent.trim();
                } else {
                    info.title = '';
                }
                
                const infoElem = document.querySelector('#eventInfo, .info');
                if (infoElem) {
                    const infoItems = infoElem.querySelectorAll('div');
                    infoItems.forEach(item => {
                        const text = item.textContent.trim();
                        if (text.includes('응모기간')) {
                            info.period = text.replace('응모기간 : ', '').trim();
                        } else if (text.includes('응모대상')) {
                            info.target = text.replace('응모대상 : ', '').trim();
                        } else if (text.includes('당첨자발표')) {
                            info.announcement = text.replace('당첨자발표 : ', '').trim();
                        } else if (text.includes('이벤트문의')) {
                            info.inquiry = text.replace('이벤트문의 : ', '').trim();
                        }
                    });
                }
                
                const dDayElem = document.querySelector('.d-day, [class*="d-day"]');
                info.d_day = dDayElem ? dDayElem.textContent.trim() : '';
                
                const iframe = document.querySelector('#evtThumb iframe, .thumb iframe');
                if (iframe) {
                    info.iframe_src = iframe.getAttribute('src');
                    info.iframe_width = iframe.getAttribute('width');
                    info.iframe_height = iframe.getAttribute('height');
                    info.iframe_title = iframe.getAttribute('title');
                }
                
                return info;
            }""")
            
            # 기간 파싱
            startdate = '0000-00-00'
            enddate = '9999-99-99'
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
            
            # iframe 내용 처리
            iframe_content = ""
            iframe_html = ""
            if event_info.get('iframe_src'):
                try:
                    logger.info(f"🔍 Event iframe processing: {event_info['iframe_src']}")
                    iframe_page = await context.new_page()
                    await iframe_page.goto(event_info['iframe_src'], wait_until='domcontentloaded', timeout=60000)
                    await iframe_page.wait_for_timeout(5000)
                    
                    iframe_data = await iframe_page.evaluate("""() => {
                        const elementsToRemove = document.querySelectorAll('script, style, noscript, .ad, .banner, .popup');
                        elementsToRemove.forEach(el => el.remove());
                        const mainContent = document.querySelector('body') || document.documentElement;
                        return {
                            html: mainContent ? mainContent.innerHTML : '',
                            title: document.title || '',
                            url: window.location.href
                        };
                    }""")
                    
                    iframe_html = iframe_data.get('html', '')
                    iframe_content = iframe_html
                    await iframe_page.close()
                except Exception as e:
                    logger.warning(f"⚠️ iframe processing failed: {str(e)}")
                    iframe_content = f"<p>iframe 로딩 실패: {str(e)}</p>"
                    iframe_html = iframe_content
            
            # 마크다운 생성
            markdown_content = f"# {event_info.get('title', 'KT 이벤트')}\n\n"
            for key in ['period', 'target', 'announcement', 'inquiry', 'd_day']:
                if event_info.get(key):
                    markdown_content += f"{event_info[key]}\n"
            markdown_content += "\n"
            
            if iframe_content:
                try:
                    soup = BeautifulSoup(iframe_content, 'html.parser')
                    for tag in soup(['script', 'style', 'noscript']):
                        tag.decompose()
                    for selector in ['.btn-twitter', '.btn-facebook', '.btn-kakao', '.btn-youtube']:
                        for element in soup.select(selector):
                            element.decompose()
                    cleaned_html = str(soup)
                    iframe_markdown = md(cleaned_html)
                    markdown_content += iframe_markdown
                except Exception as e:
                    markdown_content += f"iframe 내용 변환 실패: {str(e)}\n"
            else:
                markdown_content += "이벤트 상세 내용을 불러올 수 없습니다.\n"
            
            # HTML 생성
            html_content = f"<h1>{event_info.get('title', 'KT 이벤트')}</h1>"
            for key in ['period', 'target', 'announcement', 'inquiry', 'd_day']:
                if event_info.get(key):
                    html_content += f"<p>{event_info[key]}</p>"
            if iframe_html:
                html_content += iframe_html
            else:
                html_content += "<p>이벤트 상세 내용을 불러올 수 없습니다.</p>"
            
            mobile_url = _pc_to_mobile_url(url)
            
            await browser.close()
            
            logger.info(f"✅ KT Event detail completed: '{event_info.get('title', 'unknown')}'")
            
            return {
                "datas": [{
                    "markdown": markdown_content,
                    "html": html_content,
                    "url": url,
                    "title": event_info.get('title', 'KT 이벤트'),  # title을 최상위에 추가
                    "mobile_url": mobile_url,
                    "murl": mobile_url,
                    "startdate": startdate,
                    "enddate": enddate,
                    "metadata": {
                        "title": event_info.get('title', 'KT 이벤트'),
                        "period": event_info.get('period', ''),
                        "target": event_info.get('target', ''),
                        "announcement": event_info.get('announcement', ''),
                        "inquiry": event_info.get('inquiry', ''),
                        "d_day": event_info.get('d_day', ''),
                        "iframe_src": event_info.get('iframe_src', ''),
                        "iframe_processed": bool(iframe_content)
                    }
                }],
                "menus": [{
                    "menu": f"{menu}^{event_info.get('title', 'unknown')}" if menu else event_info.get('title', 'unknown'),
                    "url": url,
                    "murl": mobile_url
                }],
            }
            
        except Exception as e:
            logger.error(f"❌ KT Event detail processing failed: {str(e)}")
            await browser.close()
            return {
                "datas": [{
                    "markdown": f"# KT 이벤트 상세 페이지 처리 실패\n\n오류: {str(e)}",
                    "html": f"<h1>KT 이벤트 상세 페이지 처리 실패</h1><p>오류: {str(e)}</p>",
                    "url": url,
                    "error": str(e)
                }]
            }


async def handle_kt_event_main(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    KT 이벤트 메인 페이지 핸들러 (진행중인 이벤트)
    """
    logger.info(f"🎯 KT Event main processing started: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)
            
            status_code = response.status if response else None
            if status_code and status_code >= 400:
                logger.error(f"❌ KT Event main ({url}): HTTP {status_code} error")
            
            # 페이지네이션 정보 추출
            pagination_info = await page.evaluate("""() => {
                const pagination = document.querySelector('.pagination');
                if (!pagination) return { total_pages: 1, current_page: 1 };
                
                const pageLinks = pagination.querySelectorAll('a[data-page]');
                let maxPage = 1;
                pageLinks.forEach(link => {
                    const pageNum = parseInt(link.getAttribute('data-page'));
                    if (pageNum > maxPage) maxPage = pageNum;
                });
                
                const currentPageElem = pagination.querySelector('span[title="현재위치"], .current');
                const currentPage = currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                
                return { total_pages: maxPage, current_page: currentPage };
            }""")
            
            all_events = []
            total_pages = pagination_info.get('total_pages', 1)
            
            # 모든 페이지 순회
            for page_num in range(1, total_pages + 1):
                if page_num > 1:
                    logger.info(f"🔄 Navigating to page {page_num}...")
                    
                    await page.evaluate(f"""() => {{
                        const pageLinks = document.querySelectorAll('a[data-page="{page_num}"]');
                        if (pageLinks.length > 0) {{
                            pageLinks[0].click();
                        }}
                    }}""")
                    
                    await page.wait_for_timeout(2000)
                
                # 현재 페이지의 이벤트 추출
                page_events = await page.evaluate("""() => {
                    const events = [];
                    const eventLinks = document.querySelectorAll('a[data-pcevtno]');
                    
                    eventLinks.forEach(link => {
                        const evtNo = link.getAttribute('data-pcevtno');
                        const apctUrl = link.getAttribute('data-apcturl');
                        const linkType = link.getAttribute('data-pcevtlinktype');
                        
                        const thumb = link.querySelector('.thumb');
                        const img = thumb ? thumb.querySelector('img') : null;
                        const dDay = thumb ? thumb.querySelector('.d-day') : null;
                        
                        const summary = link.querySelector('.summary');
                        const title = summary ? summary.querySelector('.title') : null;
                        const date = summary ? summary.querySelector('.date') : null;
                        const type = summary ? summary.querySelector('.type') : null;
                        
                        events.push({
                            evt_no: evtNo,
                            apct_url: apctUrl,
                            link_type: linkType,
                            title: title ? title.textContent.trim() : '',
                            date: date ? date.textContent.trim() : '',
                            type: type ? type.textContent.trim() : '',
                            img_src: img ? img.getAttribute('src') : '',
                            img_alt: img ? img.getAttribute('alt') : '',
                            d_day: dDay ? dDay.textContent.trim() : '',
                            full_href: link.href || ''
                        });
                    });
                    
                    return events;
                }""")
                
                all_events.extend(page_events)
                logger.info(f"📄 Page {page_num}/{total_pages}: {len(page_events)} events")
            
            # 진입 페이지 추출
            entry_page_html = await page.content()
            entry_page_markdown = md(entry_page_html, heading_style="ATX")
            
            entry_page_data = {
                "markdown": entry_page_markdown,
                "html": entry_page_html,
                "url": url,
                "title": f"{menu or 'KT 이벤트'} 목록",  # title 추가
                "metadata": {
                    "title": f"{menu or 'KT 이벤트'} 목록",
                    "is_entry_page": True,
                    "total_events": len(all_events),
                    "total_pages": total_pages,
                    "original_url": url,
                    "special_processed": True,
                    "playwright_processed": True
                }
            }
            
            await browser.close()
            
            # 각 이벤트의 상세 페이지 처리
            individual_posts = [entry_page_data]
            logger.info(f"🔍 Starting detail processing for {len(all_events)} events")
            
            for i, event in enumerate(all_events, 1):
                try:
                    detail_url = f"https://event.kt.com/html/event/ongoing_event_view.html?page=1&searchCtg=ALL&sort=&pcEvtNo={event['evt_no']}"
                    detail_result = await handle_kt_event_detail(detail_url, fclient, menu)
                    
                    if detail_result and "datas" in detail_result and detail_result["datas"]:
                        individual_post = detail_result["datas"][0]
                        individual_post["metadata"].update({
                            "evt_no": event['evt_no'],
                            "original_url": url,
                            "post_index": i,
                            "total_posts": len(all_events)
                        })
                        detail_title = individual_post["metadata"].get('title', '').strip()
                        if detail_title:
                            event['title'] = detail_title
                    else:
                        individual_post = {
                            "markdown": f"# {event['title']}\n\n{event['evt_no']}\n{event['date']}\n",
                            "html": f"<h1>{event['title']}</h1><p>{event['evt_no']}</p><p>{event['date']}</p>",
                            "url": detail_url,
                            "title": event['title'],  # title 추가
                            "metadata": {
                                "title": event['title'],
                                "evt_no": event['evt_no'],
                                "period": event['date'],
                                "type": event['type'],
                                "d_day": event['d_day'],
                                "original_url": url,
                                "post_index": i,
                                "total_posts": len(all_events),
                                "detail_processing_failed": True
                            }
                        }
                    
                    individual_posts.append(individual_post)
                    logger.info(f"✅ {i}/{len(all_events)} completed: '{event['title']}'")
                    
                except Exception as e:
                    logger.error(f"❌ {i}/{len(all_events)} failed: {str(e)}")
                    individual_posts.append({
                        "markdown": f"# {event['title']}\n\n처리 실패: {str(e)}",
                        "html": f"<h1>{event['title']}</h1><p>처리 실패: {str(e)}</p>",
                        "url": f"https://event.kt.com/html/event/ongoing_event_view.html?pcEvtNo={event['evt_no']}",
                        "title": event['title'],  # title 추가
                        "metadata": {
                            "title": event['title'],
                            "evt_no": event['evt_no'],
                            "error": str(e)
                        }
                    })
            
            # menus 배열 생성
            menus = [{
                "menu": menu or "KT 이벤트",
                "url": url,
                "mobile_url": url.replace('https://event.kt.com', 'https://m.kt.com')
            }]
            
            for event in all_events:
                view_url = f"https://event.kt.com/html/event/ongoing_event_view.html?page=1&searchCtg=ALL&sort=&pcEvtNo={event['evt_no']}"
                menus.append({
                    "menu": f"{menu}^{event['title']}" if menu else event['title'],
                    "url": view_url,
                    "mobile_url": _pc_to_mobile_url(view_url)
                })
            
            logger.info(f"✅ KT Event main completed: {len(all_events)} events")
            
            return {
                "datas": individual_posts,
                "menus": menus,
                "metadata": {
                    "title": "KT 진행중인 이벤트",
                    "total_events": len(all_events),
                    "total_pages": total_pages,
                    "url": url,
                    "special_processed": True,
                    "playwright_processed": True
                }
            }
            
        except Exception as e:
            logger.error(f"❌ KT Event main processing failed: {str(e)}")
            await browser.close()
            return {
                "markdown": f"# KT 이벤트 페이지 처리 실패\n\n오류: {str(e)}",
                "html": f"<h1>KT 이벤트 페이지 처리 실패</h1><p>오류: {str(e)}</p>",
                "datas": [],
                "error": str(e)
            }


# 핸들러 등록
register_page_handler(
    r'https?://event\.kt\.com/html/event/ongoing_event_list\.html',
    handle_kt_event_main
)

register_page_handler(
    r'https?://event\.kt\.com/html/event/ongoing_event_view\.html\?.*pcEvtNo=\d+',
    handle_kt_event_detail
)


