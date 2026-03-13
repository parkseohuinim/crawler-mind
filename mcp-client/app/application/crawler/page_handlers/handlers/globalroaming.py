"""
글로벌로밍 관련 핸들러

로밍 공지사항 목록 및 상세 페이지 처리
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler
from ..utils import (
    sanitize_filename, 
    format_content, 
    create_markdown, 
    to_mglobalroaming_url,
    smart_goto,
    launch_chromium,
)

logger = logging.getLogger(__name__)


async def handle_roaming_notice(
    url: str, 
    fclient: Any, 
    list_date: Optional[str] = None, 
    list_title: Optional[str] = None
) -> Dict[str, Any]:
    """
    로밍 공지사항 상세 페이지 처리
    """
    logger.info(f"🔗 Roaming notice detail: {url}")
    
    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            response = await smart_goto(page, url, wait_for_selector='div.txt', timeout=30000)
            
            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logger.error(f"❌ HTTP {status_code}: {url}")
                elif status_code >= 300:
                    logger.warning(f"⚠️ HTTP {status_code} redirect: {url}")
                else:
                    logger.info(f"✅ HTTP {status_code}: {url}")
            
            metadata = await page.evaluate("""() => {
                const getText = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? (el.textContent || '').trim() : '';
                };

                let title = getText('.contents-title') ||
                            getText('.board-view .subject') ||
                            getText('h2.title') ||
                            getText('.title') ||
                            getText('h1');
                if (!title) {
                    const og = document.querySelector('meta[property="og:title"]')?.getAttribute('content')?.trim();
                    if (og) title = og;
                }

                const rawDate = getText('.reg_date') ||
                                getText('.date') ||
                                getText('.info .date') ||
                                getText('.board-info .date') ||
                                '날짜 정보 없음';

                const contentElement = document.querySelector('div.txt') ||
                                       document.querySelector('.board-content') ||
                                       document.querySelector('#cfmClContents') ||
                                       document.querySelector('.content') ||
                                       document.querySelector('.board-body');
                const contentHtml = contentElement ? contentElement.innerHTML : '';

                let nextLink = '';
                let nextText = '';
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                for (const a of anchors) {
                    const t = (a.textContent || '').trim();
                    if (/다음글|다음|Next/i.test(t)) {
                        nextLink = a.getAttribute('href') || '';
                        nextText = t;
                        break;
                    }
                }

                return {
                    title: title || '제목 없음',
                    rawDate,
                    contentHtml,
                    nextLink,
                    nextText
                };
            }""")
            
            await browser.close()
        except Exception as e:
            await browser.close()
            logger.error(f"❌ Playwright error: {str(e)}")
            return {"error": f"Playwright 처리 실패: {str(e)}"}
    
    # 컨텐츠 HTML을 마크다운으로 변환
    if metadata['contentHtml']:
        content = md(metadata['contentHtml'])
        logger.info(f"✅ Markdown converted: {len(content)} chars")
    else:
        logger.info("⚠️ No HTML, trying fallback")
        try:
            result = await fclient.scrape_single_url(url)
            if result.get("markdown"):
                content = result["markdown"]
                logger.info(f"✅ Fallback success: {len(content)} chars")
            else:
                content = "컨텐츠 스크래핑 실패"
                logger.error("❌ Fallback failed")
        except Exception as e:
            content = "컨텐츠 스크래핑 실패"
            logger.error(f"❌ Fallback failed: {str(e)}")
    
    # 카테고리와 날짜 분리 처리
    category = ''
    category_date_match = re.search(r'^(.+?)\s*(\d{4}[\.\-]\d{2}[\.\-]\d{2})', metadata['rawDate'])
    if category_date_match:
        category = category_date_match.group(1).strip()
        actual_date = category_date_match.group(2).replace('-', '.')
    else:
        date_only_match = re.search(r'(\d{4}[\.\-]\d{2}[\.\-]\d{2})', metadata['rawDate'])
        if date_only_match:
            actual_date = date_only_match.group(1).replace('-', '.')
        else:
            if list_date:
                list_date_match = re.search(r'(\d{4}[\.\-]\d{2}[\.\-]\d{2})', list_date)
                if list_date_match:
                    actual_date = list_date_match.group(1).replace('-', '.')
                else:
                    actual_date = ''
            else:
                actual_date = ''
    
    # 마크다운 콘텐츠 포맷팅
    formatted_content = format_content(content)
    date_display = f"{actual_date}" + (f" (카테고리: {category})" if category else "")
    
    final_title = metadata['title'] if metadata['title'] else (list_title or '제목 없음')
    markdown_content = create_markdown(final_title, date_display, formatted_content)
    
    # 다음글 URL 처리
    next_url = None
    if metadata['nextLink']:
        base_url = url.split('/news/')[0]
        next_url = f"{base_url}/news/{metadata['nextLink']}"
    
    # startdate/enddate 계산
    def _normalize_hyphen_date(s: str) -> str:
        s = s.strip()
        m = re.search(r"(\d{4})[\.\-년]\s*(\d{1,2})[\.\-월]\s*(\d{1,2})", s)
        if not m:
            m = re.search(r"(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})", s)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
        return ""

    startdate_hyphen = "1900-01-01"
    enddate_hyphen = "2999-12-31"

    text_for_range = (metadata.get('contentHtml') or '') + ' ' + (content or '')
    inherit_left_year = False
    m_range = re.search(
        r"(\d{4}[년\.\-]\s*\d{1,2}[월\.\-]\s*\d{1,2}일?)\s*[~\-–]\s*(\d{4}[년\.\-]?\s*\d{1,2}[월\.\-]\s*\d{1,2}일?)", 
        text_for_range
    )
    if not m_range:
        m_range = re.search(
            r"(\d{4}[년\.\-]\s*\d{1,2}[월\.\-]\s*\d{1,2}일?)\s*[~\-–]\s*(\d{1,2}[월\.\-]\s*\d{1,2}일?)", 
            text_for_range
        )
        if m_range:
            inherit_left_year = True

    if m_range:
        left = m_range.group(1)
        right = m_range.group(2)
        left_h = _normalize_hyphen_date(left)
        if inherit_left_year and left_h:
            ly = left_h.split('-')[0]
            m_right = re.search(r"(\d{1,2})[월\.\-]\s*(\d{1,2})", right)
            if m_right:
                right_h = f"{ly}-{m_right.group(1).zfill(2)}-{m_right.group(2).zfill(2)}"
            else:
                right_h = _normalize_hyphen_date(right)
        else:
            right_h = _normalize_hyphen_date(right)
        if left_h:
            startdate_hyphen = left_h
        if right_h:
            enddate_hyphen = right_h
    else:
        if actual_date:
            startdate_hyphen = actual_date.replace('.', '-')

    logger.info(f"✅ Roaming notice done: '{final_title}'")

    return {
        "url": url,
        "murl": to_mglobalroaming_url(url),
        "title": final_title,
        "date": actual_date,
        "markdown": markdown_content,
        "html": metadata['contentHtml'] or content,
        "startdate": startdate_hyphen,
        "enddate": enddate_hyphen,
        "next_url": next_url,
        "special_processed": True,
        "playwright_processed": True
    }


async def handle_globalroaming_notice_main(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    글로벌로밍 공지사항 메인 목록 페이지 처리
    - 목록에서 공지사항 정보 추출
    - 각 공지사항 상세 페이지 처리
    - 1년 이내 게시물만 처리
    """
    logger.info(f"🔗 Global roaming notice main: {url}")
    cutoff_date = datetime.now() - timedelta(days=365)
    
    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        
        # 공지사항 목록 대기
        try:
            await page.wait_for_selector('.board-content, table.board', timeout=15000)
            logger.info("✅ Roaming notice list loaded")
        except Exception as e:
            logger.warning(f"⚠️ Notice list not loaded: {e}")
        await page.wait_for_timeout(2000)
        
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logger.error(f"❌ HTTP {status_code}: {url}")
            elif status_code >= 300:
                logger.warning(f"⚠️ HTTP {status_code} redirect: {url}")
            else:
                logger.info(f"✅ HTTP {status_code}: {url}")
        
        notice_data = await page.evaluate(r"""() => {
            const table = document.querySelector('table.board.dir-vertical');
            if (!table) return { error: 'table not found' };
            
            const notices = [];
            const links = table.querySelectorAll('a[href*="view.asp"]');
            
            links.forEach(link => {
                const row = link.closest('tr');
                if (row) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 4) {
                        notices.push({
                            title: link.textContent.trim(),
                            href: link.href,
                            number: cells[0] ? cells[0].textContent.trim() : '',
                            date: cells[2] ? cells[2].textContent.trim() : '',
                            views: cells[3] ? cells[3].textContent.trim() : ''
                        });
                    }
                }
            });
            
            return { notices: notices };
        }""")
        await browser.close()
    
    notices = notice_data.get('notices', [])
    if not notices:
        return {"message": "No roaming notices found", "total_processed": 0}
    
    logger.info(f"🔍 Found {len(notices)} roaming notices")
    
    menus, datas = [], []
    total_processed = 0
    
    consecutive_errors = 0
    max_consecutive_errors = 3
    
    for notice in notices:
        try:
            date_str = notice['date']
            date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', date_str)
            if date_match:
                year, month, day = map(int, date_match.groups())
                post_date = datetime(year, month, day)
                if post_date < cutoff_date:
                    break
            
            # 개별 상세 페이지에 120초(2분) 타임아웃 적용
            try:
                result = await asyncio.wait_for(
                    handle_roaming_notice(notice['href'], fclient, notice.get('date')),
                    timeout=120
                )
                consecutive_errors = 0
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Timeout (120s): {notice['href']}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"❌ Stopped: {max_consecutive_errors} consecutive failures")
                    break
                continue
            
            if "error" in result:
                logger.warning(f"❌ Failed: {result['error']}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    break
                continue
            
            formatted_date = ''
            if result.get('date'):
                date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                if date_match:
                    formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            
            title_clean = sanitize_filename(result.get('title', 'unknown'))
            
            menus.append({
                'menu': f"{menu}^{title_clean}" if menu else title_clean,
                'url': notice['href'],
                'murl': to_mglobalroaming_url(notice['href'])
            })

            if not result.get('murl'):
                result['murl'] = to_mglobalroaming_url(result.get('url', notice['href']))
            
            datas.append(result)
            total_processed += 1
            logger.info(f"✅ Done: {total_processed} items")
            
        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                break
            continue
    
    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 로밍 공지사항 처리 완료"
    }


async def handle_globalroaming_product_main(
    url: str,
    fclient: Any,
    menu: Optional[str] = None,
) -> Dict[str, Any]:
    """
    글로벌로밍 상품 메인 페이지 처리 (데이터/음성 등)
    - 탭별 .prodBox (display:none) 를 모두 노출
    - .prodList li a[href] 에서 개별 상품 링크를 수집
    - 각 상품 상세 페이지를 fclient.scrape() 로 추출
    """
    logger.info(f"🔗 Global roaming product main: {url}")

    from urllib.parse import urljoin

    base_url = re.match(r'(https?://[^/]+)', url)
    base_origin = base_url.group(1) if base_url else "http://globalroaming.kt.com"

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/122.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        try:
            response = await smart_goto(
                page, url,
                wait_for_selector=".prodList",
                timeout=60000,
                selector_timeout=15000,
            )
            status_code = response.status if response else None
            if status_code and status_code >= 400:
                logger.error(f"❌ HTTP {status_code}: {url}")

            # 모든 .prodBox display:none 해제
            await page.evaluate("""() => {
                document.querySelectorAll('.prodBox').forEach(el => {
                    el.style.display = 'block';
                    el.style.visibility = 'visible';
                });
            }""")
            await page.wait_for_timeout(500)

            # .prodList 안의 링크 + 상품명 수집
            product_links = await page.evaluate("""(baseOrigin) => {
                const results = [];
                const seen = new Set();
                document.querySelectorAll('.prodList li > a[href]').forEach(a => {
                    const href = a.getAttribute('href') || '';
                    if (!href || href.startsWith('javascript')) return;
                    const name = (a.textContent || '').trim();
                    const fullUrl = href.startsWith('http')
                        ? href
                        : baseOrigin + (href.startsWith('/') ? '' : '/') + href;
                    if (!seen.has(fullUrl)) {
                        seen.add(fullUrl);
                        results.push({ name, url: fullUrl });
                    }
                });
                return results;
            }""", base_origin)

            await browser.close()
        except Exception as e:
            await browser.close()
            logger.error(f"❌ Playwright error: {str(e)}")
            return {
                "menus": [], "datas": [],
                "total_processed": 0,
                "status": "error",
                "message": f"메인 페이지 처리 실패: {str(e)}",
            }

    if not product_links:
        logger.warning("⚠️ No product links found")
        return {
            "menus": [], "datas": [],
            "total_processed": 0,
            "status": "completed",
            "message": "상품 링크를 찾지 못했습니다",
        }

    logger.info(f"🔍 Found {len(product_links)} product links")

    menus, datas = [], []
    consecutive_errors = 0
    max_consecutive_errors = 3

    for idx, prod in enumerate(product_links, 1):
        prod_url = prod["url"]
        prod_name = prod["name"] or "unknown"

        logger.info(f"🔍 [{idx}/{len(product_links)}] Scraping: {prod_name} ({prod_url})")

        try:
            result = await asyncio.wait_for(
                fclient.scrape(prod_url),
                timeout=120,
            )
            consecutive_errors = 0
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Timeout (120s): {prod_url}")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"❌ Stopped: {max_consecutive_errors} consecutive failures")
                break
            continue
        except Exception as e:
            logger.warning(f"⚠️ Scrape failed: {prod_url} - {str(e)}")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                break
            continue

        if not result.get("success"):
            logger.warning(f"⚠️ Scrape unsuccessful: {prod_url}")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                break
            continue

        title = result.get("title") or prod_name
        murl = to_mglobalroaming_url(prod_url)
        menu_entry = f"{menu}^{title}" if menu else title

        menus.append({"menu": menu_entry, "url": prod_url, "murl": murl})
        datas.append({
            "url": prod_url,
            "murl": murl,
            "title": title,
            "markdown": result.get("markdown", ""),
            "html": result.get("html", ""),
            "startdate": "1900-01-01",
            "enddate": "2999-12-31",
            "special_processed": True,
            "playwright_processed": False,
        })

        logger.info(f"✅ [{idx}/{len(product_links)}] Done: {title}")

    logger.info(f"✅ Global roaming product main completed: {len(datas)} items")

    return {
        "menus": menus,
        "datas": datas,
        "total_processed": len(datas),
        "status": "completed",
        "message": f"총 {len(datas)}개 로밍 상품 처리 완료",
    }


# 핸들러 등록
register_page_handler(
    r'https?://globalroaming\.kt\.com/product/(?:data|voice)/main\.asp',
    handle_globalroaming_product_main
)

register_page_handler(
    r'https?://globalroaming\.kt\.com/news/list\.asp(?:\?.*)?$',
    handle_globalroaming_notice_main
)




