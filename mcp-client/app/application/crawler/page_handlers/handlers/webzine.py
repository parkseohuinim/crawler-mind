"""
웹진 핸들러

shop.kt.com/unify/webzineList.do 처리
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler
from ..utils import to_mshop_url, sanitize_filename, smart_goto, launch_chromium

logger = logging.getLogger(__name__)


async def handle_webzine_list(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    Webzine 리스트 페이지 처리 핸들러
    """
    logger.info(f"Webzine List processing started: {url}")
    menus, datas = [], []
    base_menu = (menu or '').strip()
    base_title = base_menu.split('^')[-1].strip() if base_menu else 'Webzine 리스트'
    base_title = sanitize_filename(base_title)

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await smart_goto(page, url, wait_for_selector='ul.webzine_list', timeout=30000)

        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logger.error(f"❌ Webzine List ({url}): HTTP {status_code} error")

        # 메인 페이지 콘텐츠 추출
        try:
            main_html = await page.evaluate("""
                () => {
                    const selectors = ['ul.webzine_list', '.webzine_list', '#cfmClContents'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.innerHTML && el.innerHTML.trim().length > 0) {
                            return el.innerHTML;
                        }
                    }
                    return document.body ? document.body.innerHTML : '';
                }
            """)
        except Exception:
            main_html = await page.content()

        if main_html:
            main_markdown = md(main_html)
            if base_menu:
                menus.append({'menu': base_menu, 'url': url, 'murl': to_mshop_url(url)})
            datas.append({
                'url': url,
                'title': base_title,
                'markdown': main_markdown,
                'html': main_html,
                'special_processed': True,
                'playwright_processed': True,
                'murl': to_mshop_url(url)
            })

        # 리스트에서 a href 수집
        webzine_items = await page.evaluate("""
            () => {
                const results = [];
                const webzineList = document.querySelector('ul.webzine_list');
                if (!webzineList) {
                    return results;
                }
                
                const links = webzineList.querySelectorAll('a[href]');
                links.forEach(a => {
                    const href = a.getAttribute('href') || '';
                    const fullText = (a.textContent || '').trim();
                    
                    if (href) {
                        try {
                            const absUrl = new URL(href, location.href).href;
                            let cleanTitle = fullText;
                            cleanTitle = cleanTitle.replace(/^\\d{4}\\.\\s*\\d{1,2}\\s*/, '');
                            const lines = cleanTitle.split(/\\n/).map(l => l.trim()).filter(l => l.length > 0);
                            if (lines.length > 1) {
                                cleanTitle = lines[0];
                            } else if (lines.length === 1) {
                                cleanTitle = lines[0];
                            }
                            cleanTitle = cleanTitle.replace(/\\s+/g, ' ').trim();
                            
                            const dateMatch = fullText.match(/(\\d{4})\\.\\s*(\\d{1,2})/);
                            let year = null;
                            let month = null;
                            if (dateMatch) {
                                year = dateMatch[1];
                                month = dateMatch[2];
                            }
                            
                            results.push({
                                url: absUrl,
                                title: cleanTitle || '제목 없음',
                                fullText: fullText,
                                year: year,
                                month: month
                            });
                        } catch(e) {
                            results.push({
                                url: href,
                                title: fullText || '제목 없음',
                                fullText: fullText,
                                year: null,
                                month: null
                            });
                        }
                    }
                });
                
                return results;
            }
        """)

        logger.info(f"🔍 Webzine list collected: {len(webzine_items)} items")

        # 중복 제거
        seen_urls = set()
        normalized = []
        for item in webzine_items:
            item_url = item.get('url', '').strip()
            if item_url and item_url not in seen_urls:
                seen_urls.add(item_url)
                
                try:
                    parsed = urlparse(item_url)
                    params = parse_qs(parsed.query)
                    url_year = params.get('year', [None])[0]
                    url_month = params.get('month', [None])[0]
                    
                    if url_year:
                        year_val = int(url_year)
                        if year_val < 100:
                            year_val = 2000 + year_val
                        item['year'] = str(year_val)
                    if url_month:
                        item['month'] = url_month.zfill(2)
                except Exception:
                    pass
                
                normalized.append({
                    'url': item_url,
                    'title': item.get('title', '').strip() or '제목 없음',
                    'year': item.get('year'),
                    'month': item.get('month')
                })

        logger.info(f"🔍 Normalized Webzine items: {len(normalized)} items")

        # 각 상세 페이지에서 콘텐츠 추출
        for idx, item in enumerate(normalized, 1):
            try:
                logger.info(f"🔍 [{idx}/{len(normalized)}] Detail extraction: {item['title']}")
                
                try:
                    await page.goto(item['url'], wait_until='domcontentloaded', timeout=60000)
                    # 웹진 콘텐츠 대기
                    try:
                        await page.wait_for_selector('div.webzine_content, .content', timeout=10000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to navigate to detail page: {item['url']} - {e}")
                    continue

                detail_html = await page.evaluate("""
                    () => {
                        const contentEl = document.querySelector('div.webzine_content');
                        if (contentEl && contentEl.innerHTML && contentEl.innerHTML.trim().length > 0) {
                            return contentEl.innerHTML;
                        }
                        
                        const fallbackSelectors = ['#cfmClContents', '.content', '.main-content', 'main'];
                        for (const sel of fallbackSelectors) {
                            const el = document.querySelector(sel);
                            if (el && el.innerHTML && el.innerHTML.trim().length > 0) {
                                return el.innerHTML;
                            }
                        }
                        
                        return document.body ? document.body.innerHTML : '';
                    }
                """)

                if not detail_html or len(detail_html.strip()) < 50:
                    logger.warning(f"⚠️ {item['title']}: Content extraction failed")
                    continue

                md_content = md(detail_html)
                
                startdate = "1900-01-01"
                if item.get('year') and item.get('month'):
                    year = item['year']
                    month = item['month'].zfill(2)
                    startdate = f"{year}-{month}-01"
                
                menu_name = f"{base_menu}^{item['title']}" if base_menu else f"Shop^{item['title']}"
                menus.append({'menu': menu_name, 'url': item['url'], 'murl': to_mshop_url(item['url'])})
                datas.append({
                    'url': item['url'],
                    'title': item['title'],
                    'markdown': md_content,
                    'html': detail_html,
                    'startdate': startdate,
                    'enddate': '2999-12-31',
                    'special_processed': True,
                    'playwright_processed': True,
                    'murl': to_mshop_url(item['url'])
                })
            except Exception as e:
                logger.warning(f"⚠️ Detail extraction failed: {item.get('title', 'unknown')}: {str(e)}")
                continue

        await browser.close()

    logger.info(f"✅ Webzine List completed: {len(datas)} items processed")

    return {
        'menus': menus,
        'datas': datas,
        'total_processed': len(datas),
        'status': 'completed',
        'message': f"총 {len(datas)}개 Webzine 항목 처리 완료"
    }


# 핸들러 등록
register_page_handler(
    r'https?://shop\.kt\.com/unify/webzineList\.do.*',
    handle_webzine_list
)




