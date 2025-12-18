"""
KT 상품사전(wDic) 핸들러

상품 상세 및 카테고리 목록 페이지 처리
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler

logger = logging.getLogger(__name__)


def _to_murl(u: str) -> str:
    """PC URL을 모바일 URL로 변환"""
    if not u or not u.startswith('http'):
        return ''
    m = u.replace('https://product.kt.com', 'https://m.product.kt.com')
    m = m.replace('/wDic/', '/mDic/')
    return m


async def handle_product_detail(
    url: str, 
    fclient: Any = None, 
    menu: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    상품 상세 페이지 처리 핸들러
    """
    logger.info(f"🔗 Product detail: {url}")
    
    m = re.search(r'ItemCode=(\d+)', url)
    if not m:
        return None
    
    item_code = m.group(1)
    max_retries = 3
    base_timeout = 60000
    
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                wait_until = "domcontentloaded"
                timeout = 30000
                extra_wait = 3000
            elif attempt == 1:
                wait_until = "load"
                timeout = 45000
                extra_wait = 5000
            else:
                wait_until = "networkidle"
                timeout = base_timeout
                extra_wait = 7000
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)
                await page.wait_for_timeout(extra_wait)
                
                status_code = response.status if response else None
                if status_code and status_code >= 400:
                    logger.error(f"❌ HTTP {status_code}: {url}")
                
                try:
                    await page.wait_for_selector("#cfmClContents", timeout=10000)
                except:
                    logger.warning("⚠️ Main content load failed")
                
                title = await page.evaluate("""
                    () => {
                        const titleEl = document.querySelector('h1') || document.querySelector('.product-title') || document.querySelector('h2');
                        return titleEl ? titleEl.textContent.trim() : 'No title found';
                    }
                """)
                
                # 아코디언 트리거 탐지 및 클릭
                accordion_triggers = await page.evaluate("""
                    () => {
                        const triggers = [];
                        for (let i = 1; i <= 10; i++) {
                            const trigger = document.querySelector(`#title${i}`);
                            if (trigger) {
                                triggers.push({
                                    id: `title${i}`,
                                    text: trigger.textContent.trim(),
                                    visible: trigger.offsetParent !== null
                                });
                            }
                        }
                        return triggers;
                    }
                """)
                
                if accordion_triggers:
                    for trigger in accordion_triggers:
                        try:
                            await page.click(f"#{trigger['id']}", timeout=5000)
                            await page.wait_for_timeout(1000)
                        except:
                            continue
                
                # 추천 컨텐츠 추출
                recommendations = []
                try:
                    await page.wait_for_timeout(3000)
                    
                    raw_reco = await page.evaluate("""() => {
                        const abs = (u) => {
                            try { const a = document.createElement('a'); a.href = u; return a.href; } catch(e){ return u; }
                        };
                        const top = Array.from(document.querySelectorAll('ul.three-list li a')).map(a => ({
                            title: (a.textContent||'').trim(),
                            url: abs(a.getAttribute('href')||a.href||'')
                        })).filter(x => x.title && x.url);

                        const bundle = [];
                        ['#trigger1-1-1', '#trigger1-1-2'].forEach(sel => {
                            const root = document.querySelector(sel);
                            if (!root) return;
                            root.querySelectorAll('.bxslider li a').forEach(a => {
                                const title = ((a.querySelector('p')?.textContent) || a.textContent || '').trim();
                                const url = abs(a.getAttribute('href')||a.href||'');
                                const main = (a.querySelector('.recommend-main-info')?.textContent||'').trim();
                                const sub = (a.querySelector('.recommend-sub-info')?.textContent||'').trim();
                                const desc = [main, sub].filter(Boolean).join(' ');
                                if (title && url) bundle.push({ title, url, desc });
                            });
                        });

                        const planVariant = Array.from(document.querySelectorAll('.N-head-btn-area a'))
                            .filter(a => !a.classList.contains('icon'))
                            .map(a => ({
                                title: (a.textContent||'').trim(),
                                url: abs(a.getAttribute('href')||a.href||'')
                            }))
                            .filter(x => x.title && x.url && !x.url.startsWith('javascript:'));

                        const otherPlan = [];
                        const extraService = [];
                        Array.from(document.querySelectorAll('ul.N-compare-suggest-list li a')).forEach(a => {
                            const title = ((a.querySelector('strong.tit')?.textContent) || a.textContent || '').trim();
                            const url = abs(a.getAttribute('href')||a.href||'');
                            const onclick = (a.getAttribute('onclick')||'');
                            if (title && url) {
                                if (onclick.includes('추천부가서비스')) extraService.push({ title, url });
                                else otherPlan.push({ title, url });
                            }
                        });

                        return { top, bundle, planVariant, otherPlan, extraService };
                    }""")
                    
                    def to_abs(u: str) -> str:
                        if not u:
                            return ''
                        if u.startswith('http'):
                            return u
                        if u.startswith('/'):
                            return f"https://product.kt.com{u}"
                        return u

                    recommendations_list = []
                    
                    for item in raw_reco.get('top', [])[:10]:
                        url_abs = to_abs(item.get('url', ''))
                        if url_abs:
                            recommendations_list.append({
                                'kind': 'top',
                                'name': item.get('title', ''),
                                'desc': '',
                                'url': url_abs,
                                'murl': _to_murl(url_abs)
                            })

                    seen = set()
                    for item in raw_reco.get('bundle', [])[:20]:
                        url_abs = to_abs(item.get('url', ''))
                        if not url_abs or url_abs in seen:
                            continue
                        seen.add(url_abs)
                        recommendations_list.append({
                            'kind': 'bundle_option',
                            'name': item.get('title', ''),
                            'desc': item.get('desc') or '',
                            'url': url_abs,
                            'murl': _to_murl(url_abs)
                        })

                    for item in raw_reco.get('planVariant', [])[:10]:
                        url_abs = to_abs(item.get('url', ''))
                        if url_abs and not url_abs.startswith('javascript:'):
                            recommendations_list.append({
                                'kind': 'plan_variant',
                                'name': item.get('title', ''),
                                'desc': '',
                                'url': url_abs,
                                'murl': _to_murl(url_abs)
                            })

                    for item in raw_reco.get('otherPlan', [])[:10]:
                        url_abs = to_abs(item.get('url', ''))
                        if url_abs:
                            recommendations_list.append({
                                'kind': 'other_plan',
                                'name': item.get('title', ''),
                                'desc': '',
                                'url': url_abs,
                                'murl': _to_murl(url_abs)
                            })

                    for item in raw_reco.get('extraService', [])[:10]:
                        url_abs = to_abs(item.get('url', ''))
                        if url_abs:
                            recommendations_list.append({
                                'kind': 'extra_service',
                                'name': item.get('title', ''),
                                'desc': '',
                                'url': url_abs,
                                'murl': _to_murl(url_abs)
                            })

                    recommendations = recommendations_list
                    
                except Exception as e:
                    logger.error(f"❌ Recommendations failed: {str(e)}")
                    recommendations = []

                # N-pdt-compare-column 자세히 보기 추출
                additional_details = []
                try:
                    detail_links = await page.evaluate("""() => {
                        const abs = (u) => {
                            try { const a = document.createElement('a'); a.href = u; return a.href; } catch(e){ return u; }
                        };
                        
                        const results = [];
                        const columns = document.querySelectorAll('.N-pdt-compare-column');
                        
                        columns.forEach(col => {
                            const link = col.querySelector('a.btn-reduced');
                            if (!link) return;
                            
                            const linkText = (link.textContent || '').trim();
                            if (linkText !== '자세히 보기') return;
                            
                            const nameEl = col.querySelector('strong.name');
                            if (!nameEl) return;
                            
                            const name = (nameEl.textContent || '').trim();
                            const href = abs(link.getAttribute('href') || link.href || '');
                            
                            if (name && href && href.startsWith('http')) {
                                results.push({ name, href });
                            }
                        });
                        
                        return results;
                    }""")
                    
                    if detail_links:
                        for link_info in detail_links:
                            try:
                                clean_name = link_info['name']
                                clean_name = re.sub(r'[\r\n]+', ' ', clean_name)
                                clean_name = re.sub(r'\s+', ' ', clean_name)
                                clean_name = re.sub(r'[^\w\sㄱ-ㅎㅏ-ㅣ가-힣/\-\(\)]', '', clean_name)
                                clean_name = clean_name.strip()
                                
                                detail_url = link_info['href']
                                sub_result = await handle_product_detail(detail_url, fclient=fclient, menu=menu)
                                
                                if sub_result:
                                    sub_result['parent_product_name'] = clean_name
                                    sub_result['parent_url'] = url
                                    additional_details.append(sub_result)
                            except:
                                continue
                except:
                    pass

                # 콘텐츠 수집
                combined_html = ""
                markdown_text = ""
                try:
                    combined_html = await page.evaluate("""
                        () => {
                            const mainContent = document.querySelector('#cfmClContents');
                            if (!mainContent) return '';
                            
                            const excludeSelectors = [
                                '#cfmClHeader', '#cfmClFooter', '#cfmClSkip', 
                                'form', '.header', '.footer', '.nav', ".swiper-controls-wrapper",
                                ".opage-hashtag-arrow", ".swiper-button-next", ".swiper-button-prev",
                                ".icon.kakao", ".icon.facebook", ".icon.twitter", ".icon.youtube",
                                ".location", ".sns-area", ".opener", "a[onclick*='KT_trackClicks']", 
                                '.together-recommend-area', ".N-compare-suggest-list", ".top-three-box", ".tabs",
                            ];
                            
                            const contentClone = mainContent.cloneNode(true);
                            
                            excludeSelectors.forEach(selector => {
                                const elements = contentClone.querySelectorAll(selector);
                                elements.forEach(el => el.remove());
                            });
                            
                            return contentClone.outerHTML;
                        }
                    """)
                    
                    if combined_html:
                        markdown_text = md(combined_html)
                    else:
                        combined_html = await page.eval_on_selector("body", "el => el.outerHTML")
                        markdown_text = md(combined_html)
                        
                except Exception as e:
                    logger.error(f"❌ Content failed: {str(e)}")
                    markdown_text = "콘텐츠 처리 실패"

                await browser.close()
                
                logger.info(f"✅ Product detail done: '{title}'")
                
                return {
                    "url": url,
                    "murl": _to_murl(url),
                    "title": title,
                    "markdown": markdown_text,
                    "html": combined_html or "",
                    "item_code": item_code,
                    "accordion_count": len(accordion_triggers),
                    "content_length": len(combined_html) if combined_html else 0,
                    "recommendations": recommendations or [],
                    "additional_details": additional_details or [],
                    "special_processed": True,
                    "playwright_processed": True
                }
                
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(5)
                continue
            else:
                logger.error(f"❌ Product detail failed: {str(e)}")
                return None


async def handle_wdic_mobile_list(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    KT 상품사전(wDic) 카테고리 목록 핸들러
    """
    logger.info(f"🔗 wDic list: {url}")
    
    base_host = 'https://product.kt.com'
    menus, datas = [], []

    async def _capture_list_snapshot(page, base_menu: str = "", tab_text: str = "", sub_filter_text: str = ""):
        try:
            html = await page.evaluate("""
                () => {
                    const root = document.querySelector('#cfmClContents') || document.body;
                    if (!root) return '';
                    const clone = root.cloneNode(true);
                    const removeSelectors = [
                        '#cfmClHeader', '#cfmClFooter', '#cfmClSkip',
                        '.location', '.sns-area', '.find-center'
                    ];
                    removeSelectors.forEach(sel => {
                        clone.querySelectorAll(sel).forEach(el => el.remove());
                    });
                    return clone.outerHTML;
                }
            """)
            markdown_text = md(html) if html else ""
            final_menu = (base_menu or "").strip()
            if tab_text:
                final_menu = f"{final_menu}^{tab_text}" if final_menu else tab_text
            if sub_filter_text:
                final_menu = f"{final_menu}^{sub_filter_text}" if final_menu else sub_filter_text
            menus.append({'menu': final_menu, 'url': page.url, 'murl': _to_murl(page.url)})
            datas.append({
                "url": page.url,
                "murl": _to_murl(page.url),
                "title": final_menu,
                "markdown": markdown_text,
                "html": html or "",
                "special_processed": True,
                "playwright_processed": True,
                "is_list_snapshot": True
            })
        except Exception as e:
            logger.debug(f"🔍 Snapshot failed: {str(e)}")

    async def _click_more_until_exhausted(page) -> int:
        clicks = 0
        guard = 0
        while guard < 50:
            guard += 1
            try:
                before = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")
                
                clicked = await page.evaluate(r"""
                    () => {
                        const btn = document.querySelector('.btn-more');
                        if (!btn) return false;
                        const style = btn.getAttribute('style') || '';
                        const css = getComputedStyle(btn);
                        const visible = btn.offsetParent !== null && css.display !== 'none' && css.visibility !== 'hidden' && !/display:\s*none/i.test(style);
                        if (!visible) return false;
                        btn.click();
                        return true;
                    }
                """)
                
                if not clicked:
                    break
                
                clicks += 1
                await page.wait_for_timeout(1200)

                after = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")

                if after <= before:
                    await page.wait_for_timeout(1500)
                    after = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")

                if after <= before:
                    btn_check = await page.evaluate(r"""
                        () => {
                            const b = document.querySelector('.btn-more');
                            if (!b) return false;
                            const s = b.getAttribute('style')||'';
                            const c = getComputedStyle(b);
                            return b.offsetParent !== null && c.display !== 'none' && c.visibility !== 'hidden' && !/display:\s*none/i.test(s);
                        }
                    """)
                    if not btn_check:
                        break
            except:
                break
        return clicks

    async def _ensure_filter_all(page):
        try:
            changed = await page.evaluate(r"""
                () => {
                    function isVisible(el){
                        if(!el) return false;
                        const style = getComputedStyle(el);
                        return el.offsetParent !== null && style.display !== 'none' && style.visibility !== 'hidden';
                    }
                    const cands = Array.from(document.querySelectorAll('a, button, label'));
                    for(const el of cands){
                        const txt = (el.textContent||'').replace(/\s+/g,'').trim();
                        if (txt.includes('전체') && isVisible(el)) {
                            try { el.click(); return true; } catch(e) { return false; }
                        }
                    }
                    return false;
                }
            """)
            if changed:
                await page.wait_for_timeout(600)
        except:
            pass

    async def _extract_items(page) -> list:
        items = await page.evaluate("""
            () => {
                const results = [];
                const anchors = Array.from(document.querySelectorAll('.plan-list-area .btns a[href*="productDetail"]'));

                function normRel(href){
                    try{
                        const a = document.createElement('a');
                        a.href = href;
                        const rel = `${a.pathname}${a.search||''}`;
                        return rel.startsWith('/wDic/') ? rel : (rel.startsWith('/') ? rel : `/wDic/${rel}`);
                    }catch(e){
                        return href.startsWith('/wDic/') ? href : (href.startsWith('/') ? href : `/wDic/${href}`);
                    }
                }

                function getNearestTitle(anchor){
                    const titleSelector = '.title, .plan_tit, .tit, .name, strong, span.two-line';
                    
                    function extractTextWithoutSpan(element) {
                        if (!element) return '';
                        if (element.classList && element.classList.contains('title')) {
                            let text = '';
                            for (const child of element.childNodes) {
                                if (child.nodeType === Node.TEXT_NODE) {
                                    text += child.textContent;
                                } else if (child.nodeType === Node.ELEMENT_NODE && child.tagName !== 'SPAN') {
                                    text += child.textContent;
                                }
                            }
                            return text.trim();
                        }
                        return (element.textContent || '').trim();
                    }
                    
                    let el = anchor.closest('li, tr, .plan-list li, .prd-list li');
                    if (el){
                        const t = el.querySelector(titleSelector);
                        if (t) return extractTextWithoutSpan(t);
                    }
                    let cur = anchor.parentElement;
                    for (let depth=0; depth<5 && cur; depth++){
                        let prev = cur.previousElementSibling;
                        let hops = 0;
                        while(prev && hops < 10){
                            const t = prev.querySelector(titleSelector);
                            if (t) return extractTextWithoutSpan(t);
                            prev = prev.previousElementSibling;
                            hops++;
                        }
                        cur = cur.parentElement;
                    }
                    let parent = anchor.parentElement;
                    for (let i=0; i<6 && parent; i++){
                        const t = parent.querySelector(titleSelector);
                        if (t) return extractTextWithoutSpan(t);
                        parent = parent.parentElement;
                    }
                    const at = (anchor.textContent||'').trim();
                    if (!/상세|자세히/.test(at)) return at;
                    return '';
                }

                anchors.forEach(a => {
                    const href = a.getAttribute('href') || a.href || '';
                    if (!href || href === '#' || href.startsWith('javascript:')) return;
                    const rel = normRel(href);
                    const title = getNearestTitle(a);
                    results.push({ title: title || '', relHref: rel });
                });

                return results;
            }
        """)
        return items or []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(1200)

        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logger.error(f"❌ HTTP {status_code}: {url}")

        try:
            await page.wait_for_selector('ul.ui-tab-list, ul.red-select', timeout=10000)
        except:
            pass

        tabs = await page.evaluate("""
            () => {
                const arr = [];
                const selectors = ['ul.ui-tab-list li a', 'ul.red-select li a'];
                let anchors = [];
                for (const sel of selectors) {
                    anchors = Array.from(document.querySelectorAll(sel));
                    if (anchors.length > 0) break;
                }
                
                if (anchors.length === 0) {
                    arr.push({ index: -1, text: '전체' });
                } else {
                    anchors.forEach((a, originalIdx) => {
                        const text = (a.textContent||'').trim();
                        if (text === '추천') return;
                        arr.push({ index: originalIdx, text });
                    });
                }
                return arr;
            }
        """)
        if not tabs:
            tabs = [{'index': -1, 'text': '전체'}]

        detail_targets = []

        try:
            await _capture_list_snapshot(page, base_menu=(menu or "").strip())
        except:
            pass

        for tab in tabs:
            try:
                if tab.get('index', -1) >= 0:
                    tab_clicked = await page.evaluate(f"""
                        () => {{
                            const selectors = ['ul.ui-tab-list li a', 'ul.red-select li a'];
                            let tabs = [];
                            for (const sel of selectors) {{
                                tabs = Array.from(document.querySelectorAll(sel));
                                if (tabs.length > 0) break;
                            }}
                            
                            if (tabs.length > {tab['index']}) {{
                                tabs[{tab['index']}].click();
                                return true;
                            }}
                            return false;
                        }}
                    """)
                    if tab_clicked:
                        try:
                            await page.wait_for_load_state('networkidle', timeout=5000)
                        except:
                            await page.wait_for_timeout(1200)

                await _ensure_filter_all(page)
                await page.wait_for_timeout(800)

                sub_filters = await page.evaluate("""
                    () => {
                        const root = document.querySelector('.type-sub-item');
                        if (!root) return [];
                        const filters = Array.from(root.querySelectorAll('a, button, label'));
                        const result = [];
                        filters.forEach((el, idx) => {
                            const text = (el.textContent||'').trim();
                            if (text) result.push({ index: idx, text });
                        });
                        return result;
                    }
                """)

                if sub_filters:
                    for sub_filter in sub_filters:
                        try:
                            sub_clicked = await page.evaluate(f"""
                                () => {{
                                    const root = document.querySelector('.type-sub-item');
                                    if (!root) return false;
                                    const filters = Array.from(root.querySelectorAll('a, button, label'));
                                    if (filters.length > {sub_filter['index']}) {{
                                        filters[{sub_filter['index']}].click();
                                        return true;
                                    }}
                                    return false;
                                }}
                            """)
                            if sub_clicked:
                                try:
                                    await page.wait_for_load_state('networkidle', timeout=5000)
                                except:
                                    pass
                                await page.wait_for_timeout(1500)

                            clicks = await _click_more_until_exhausted(page)
                            items = await _extract_items(page)
                            
                            try:
                                await _capture_list_snapshot(
                                    page,
                                    base_menu=(menu or "").strip(),
                                    tab_text=tab.get('text', '').strip(),
                                    sub_filter_text=sub_filter.get('text', '').strip()
                                )
                            except:
                                pass

                            for it in items:
                                if not it.get('relHref'):
                                    continue
                                detail_targets.append({
                                    'tab': tab.get('text', ''),
                                    'sub_filter': sub_filter.get('text', ''),
                                    'title': it.get('title', '').strip() or '(제목 없음)',
                                    'relHref': it['relHref']
                                })
                        except Exception as e:
                            logger.warning(f"⚠️ Sub-filter error: {str(e)}")
                            continue
                else:
                    clicks = await _click_more_until_exhausted(page)
                    items = await _extract_items(page)
                    
                    try:
                        await _capture_list_snapshot(
                            page,
                            base_menu=(menu or "").strip(),
                            tab_text=tab.get('text', '').strip()
                        )
                    except:
                        pass

                    for it in items:
                        if not it.get('relHref'):
                            continue
                        detail_targets.append({
                            'tab': tab.get('text', ''),
                            'title': it.get('title', '').strip() or '(제목 없음)',
                            'relHref': it['relHref']
                        })
            except Exception as e:
                logger.warning(f"⚠️ Tab error: {str(e)}")
                continue

        # 중복 제거
        seen_itemcodes = set()
        unique_targets = []
        for target in detail_targets:
            match = re.search(r'ItemCode=(\d+)', target['relHref'])
            if match:
                itemcode = match.group(1)
                if itemcode in seen_itemcodes:
                    continue
                seen_itemcodes.add(itemcode)
            unique_targets.append(target)
        
        logger.info(f"🔍 Dedupe: {len(detail_targets)} → {len(unique_targets)}")
        detail_targets = unique_targets

        # 상세 처리
        for i, target in enumerate(detail_targets, 1):
            detail_url = urljoin(base_host, target['relHref'])
            try:
                result = await handle_product_detail(detail_url, fclient, menu)
                if not result:
                    continue

                base_menu_str = (menu or '').strip()
                tab_prefix = target.get('tab', '').strip()
                sub_filter_name = target.get('sub_filter', '').strip()
                title_suffix = target.get('title', '').strip()
                final_menu = base_menu_str
                if tab_prefix:
                    final_menu = f"{final_menu}^{tab_prefix}" if final_menu else tab_prefix
                if sub_filter_name:
                    final_menu = f"{final_menu}^{sub_filter_name}" if final_menu else sub_filter_name
                if title_suffix:
                    final_menu = f"{final_menu}^{title_suffix}" if final_menu else title_suffix

                menus.append({'menu': final_menu or (result.get('title') or ''), 'url': detail_url})
                datas.append(result)
                logger.info(f"✅ [{i}/{len(detail_targets)}] Done: {detail_url}")
            except Exception as e:
                logger.error(f"❌ Detail error: {detail_url} - {str(e)}")
                continue

        await browser.close()

    logger.info(f"✅ wDic list done: {len(datas)} items")

    return {
        'menus': menus,
        'datas': datas,
        'metadata': {
            'url': url,
            'total_items': len(datas),
            'source': 'wdic_list',
            'special_processed': True,
            'playwright_processed': True
        }
    }


# 핸들러 등록
register_page_handler(
    r'https?://product\.kt\.com/wDic/(soho/)?productDetail\.do\?ItemCode=.*',
    handle_product_detail
)

register_page_handler(
    r'https?://product\.kt\.com/wDic/.*index\.do\?CateCode=\d+',
    handle_wdic_mobile_list
)




