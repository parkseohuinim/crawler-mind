"""
KT 상품사전(wDic) 핸들러

상품 상세 및 카테고리 목록 페이지 처리
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser
from markdownify import markdownify as md

from ..handler_registry import register_page_handler
from ..utils import launch_chromium, safe_goto

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
    menu: Optional[str] = None,
    browser: Optional[Browser] = None
) -> Optional[Dict[str, Any]]:
    """
    상품 상세 페이지 처리 핸들러
    
    browser가 전달되면 해당 브라우저의 새 페이지 사용 (브라우저 재사용).
    additional_details 재귀 호출 시 동일 브라우저 사용.
    """
    logger.info(f"🔗 Product detail: {url}")
    
    m = re.search(r'ItemCode=(\d+)', url)
    if not m:
        return None
    
    item_code = m.group(1)
    max_retries = 3
    # domcontentloaded + wait_for_selector로 networkidle 대기 완화
    goto_configs = [
        ("domcontentloaded", 35000, 3000),
        ("load", 50000, 5000),
        ("domcontentloaded", 60000, 7000),
    ]
    
    # browser가 닫혔을 때 fallback: 자체 브라우저 생성
    use_passed_browser = bool(browser)
    
    for attempt in range(max_retries):
        try:
            wait_until, timeout, extra_wait = goto_configs[min(attempt, len(goto_configs) - 1)]
            
            if use_passed_browser and browser:
                try:
                    browser_to_use = browser
                    page = await browser.new_page()
                    playwright = None
                except Exception as e:
                    if "has been closed" in str(e).lower() or "target" in str(e).lower():
                        logger.warning(f"⚠️ Passed browser closed, falling back to own browser: {e}")
                        use_passed_browser = False
                        playwright = await async_playwright().start()
                        browser_to_use = await launch_chromium(playwright)
                        page = await browser_to_use.new_page()
                    else:
                        raise
            else:
                playwright = await async_playwright().start()
                browser_to_use = await launch_chromium(playwright)
                page = await browser_to_use.new_page()
            
            try:
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)
                
                # 상품 상세 페이지 콘텐츠 대기
                try:
                    await page.wait_for_selector('.product-title, .prd-tit, .ui-view-info', timeout=10000)
                except Exception:
                    pass
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
                                clean_name = clean_name.strip()
                                
                                detail_url = link_info['href']
                                sub_result = await handle_product_detail(
                                    detail_url, fclient=fclient, menu=menu,
                                    browser=browser_to_use
                                )
                                
                                if sub_result and not sub_result.get("_failed"):
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

            finally:
                await page.close()
                if playwright is not None:
                    await browser_to_use.close()
                    await playwright.stop()
            
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
                logger.warning(f"⚠️ [wdic] Attempt {attempt + 1} failed: {url} - {str(e)}")
                await asyncio.sleep(5)
                continue
            else:
                err_msg = str(e)
                logger.error(f"❌ [wdic] Product detail failed: {url} - {err_msg}", exc_info=True)
                return {"_failed": True, "url": url, "error": err_msg}


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

    async def _safe_evaluate(page, script: str, default=None, max_retries: int = 3):
        """Execution context destroyed 시 재시도하는 page.evaluate 래퍼"""
        last_err = None
        for attempt in range(max_retries):
            try:
                return await page.evaluate(script)
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if ("execution context was destroyed" in err_str or "navigation" in err_str) and attempt < max_retries - 1:
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=3000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(800)
                    continue
                raise
        return default

    async def _capture_list_snapshot(page, base_menu: str = "", tab_text: str = "", sub_filter_text: str = "", safe_eval=None):
        eval_fn = safe_eval if safe_eval else (lambda s: page.evaluate(s))
        try:
            html = await eval_fn("""
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

    async def _click_more_until_exhausted(page, safe_eval=None) -> int:
        eval_fn = safe_eval if safe_eval else (lambda s: page.evaluate(s))
        clicks = 0
        guard = 0
        while guard < 50:
            guard += 1
            try:
                before = await eval_fn("document.querySelectorAll('.plan-list-area .plan-list li').length")
                
                clicked = await eval_fn(r"""
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

                after = await eval_fn("document.querySelectorAll('.plan-list-area .plan-list li').length")

                if after <= before:
                    await page.wait_for_timeout(1500)
                    after = await eval_fn("document.querySelectorAll('.plan-list-area .plan-list li').length")

                if after <= before:
                    btn_check = await eval_fn(r"""
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
            except Exception:
                break
        return clicks

    async def _ensure_filter_all(page, safe_eval=None):
        eval_fn = safe_eval if safe_eval else (lambda s: page.evaluate(s))
        try:
            changed = await eval_fn(r"""
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
        except Exception:
            pass

    async def _extract_items(page, safe_eval=None) -> list:
        eval_fn = safe_eval if safe_eval else (lambda s: page.evaluate(s))
        items = await eval_fn("""
            () => {
                const results = [];
                const anchors = Array.from(document.querySelectorAll('.plan-list-area .btns a[href*="productDetail"]'));

                function toAbs(href){
                    try {
                        const a = document.createElement('a');
                        a.href = href;
                        return a.href;
                    } catch(e) { return href; }
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
                    const fullUrl = toAbs(href);
                    const title = getNearestTitle(a);
                    results.push({ title: title || '', relHref: fullUrl });
                });

                return results;
            }
        """)
        return items or []

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        page = await browser.new_page()
        response = await safe_goto(
            page, url,
            wait_for_selector='.plan-list-area .plan-list li, ul.N-compare-suggest-list li',
            base_timeout=60000, retries=2
        )
        if response is None:
            await browser.close()
            return {
                "menus": [],
                "datas": [],
                "total_processed": 0,
                "status": "completed",
                "message": "상품 목록 페이지 로드 실패 (타임아웃)"
            }
        
        await page.wait_for_timeout(1200)

        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logger.error(f"❌ HTTP {status_code}: {url}")

        try:
            await page.wait_for_selector('ul.ui-tab-list, ul.red-select', timeout=10000)
        except:
            pass

        async def _eval(script):
            return await _safe_evaluate(page, script)

        tabs = await _eval("""
            () => {
                const arr = [];
                const ulSelectors = ['ul.ui-tab-list', 'ul.red-select'];
                let ul = null;
                
                for (const sel of ulSelectors) {
                    ul = document.querySelector(sel);
                    if (ul) break;
                }
                
                if (!ul) {
                    arr.push({ liId: null, text: '전체' });
                    return arr;
                }
                
                const liElements = Array.from(ul.querySelectorAll('li'));
                liElements.forEach((li) => {
                    const a = li.querySelector('a');
                    if (!a) return;
                    
                    const text = (a.textContent || '').trim();
                    if (text === '추천') return;
                    
                    const liId = li.getAttribute('id') || li.id || null;
                    arr.push({ liId, text });
                });
                
                return arr;
            }
        """)
        if not tabs:
            tabs = [{'liId': None, 'text': '전체'}]

        detail_targets = []

        try:
            await _capture_list_snapshot(page, base_menu=(menu or "").strip(), safe_eval=_eval)
        except Exception:
            pass

        for tab in tabs:
            try:
                li_id = tab.get('liId')
                if li_id is not None:
                    # 클릭 전 리스트 개수 기록
                    prev_count = await _eval("document.querySelectorAll('.plan-list-area .plan-list li').length")
                    
                    tab_clicked = await _eval(f"""
                        () => {{
                            const ulSelectors = ['ul.ui-tab-list', 'ul.red-select'];
                            let ul = null;
                            
                            for (const sel of ulSelectors) {{
                                ul = document.querySelector(sel);
                                if (ul) break;
                            }}
                            
                            if (!ul) return false;
                            
                            const li = ul.querySelector('li[id="{li_id}"]') || ul.querySelector('li#{li_id}');
                            if (!li) return false;
                            
                            const a = li.querySelector('a');
                            if (!a) return false;
                            
                            a.click();
                            return true;
                        }}
                    """)
                    if tab_clicked:
                        # 1) 네트워크가 안정될 때까지 대기
                        try:
                            await page.wait_for_load_state('networkidle', timeout=5000)
                        except Exception:
                            pass
                        # 2) domcontentloaded로 컨텍스트 안정화
                        try:
                            await page.wait_for_load_state('domcontentloaded', timeout=3000)
                        except Exception:
                            pass
                        await page.wait_for_timeout(500)
                        
                        # 추가로 리스트 업데이트 확인 (최대 3초)
                        for _ in range(6):
                            await page.wait_for_timeout(500)
                            new_count = await _eval("document.querySelectorAll('.plan-list-area .plan-list li').length")
                            if new_count > 0:
                                break

                await _ensure_filter_all(page, safe_eval=_eval)
                await page.wait_for_timeout(800)

                sub_filters = await _eval("""
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
                    # 서브 필터가 있으면 모두 순회 (중복은 나중에 제거)
                    logger.info(f"탭 '{tab.get('text','')}': 서브 필터 {len(sub_filters)}개 발견, 모두 순회")
                    
                    for sub_filter in sub_filters:
                        
                        try:
                            # 서브 필터 클릭 전 현재 리스트 개수 기록
                            prev_count = await _eval("document.querySelectorAll('.plan-list-area .plan-list li').length")
                            
                            # 서브 필터 클릭
                            sub_clicked = await _eval(f"""
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
                                # 1) 네트워크가 안정될 때까지 대기 (최대 5초)
                                try:
                                    await page.wait_for_load_state('networkidle', timeout=5000)
                                except Exception:
                                    pass
                                # 2) domcontentloaded로 컨텍스트 안정화
                                try:
                                    await page.wait_for_load_state('domcontentloaded', timeout=3000)
                                except Exception:
                                    pass
                                await page.wait_for_timeout(500)
                                
                                # 추가로 리스트 업데이트 확인 (최대 3초)
                                for _ in range(6):
                                    await page.wait_for_timeout(500)
                                    new_count = await _eval("document.querySelectorAll('.plan-list-area .plan-list li').length")
                                    if new_count > 0 and new_count != prev_count:
                                        break

                            clicks = await _click_more_until_exhausted(page, safe_eval=_eval)
                            items = await _extract_items(page, safe_eval=_eval)
                            
                            # 현재 탭+서브필터의 목록 화면도 캡처
                            try:
                                await _capture_list_snapshot(
                                    page,
                                    base_menu=(menu or "").strip(),
                                    tab_text=tab.get('text', '').strip(),
                                    sub_filter_text=sub_filter.get('text', '').strip(),
                                    safe_eval=_eval
                                )
                            except Exception:
                                pass

                            li_count = await _eval("document.querySelectorAll('.plan-list-area .plan-list li').length")
                            
                            # 상세링크 0개일 때 방어 로직: 재시도
                            if len(items) == 0:
                                if clicks == 0 and li_count == 0:
                                    # 더보기 클릭이 0회이고 리스트도 없는 경우: 페이지 새로고침 후 재시도
                                    logger.warning(f"⚠️  더보기 클릭 0회, 상세링크 0개 (li={li_count}) - 페이지 새로고침 후 재시도 중...")
                                    await page.reload(timeout=10000)
                                    await page.wait_for_timeout(2000)
                                    try:
                                        await page.wait_for_load_state('networkidle', timeout=5000)
                                    except Exception:
                                        pass
                                    # 서브 필터 다시 클릭
                                    if sub_clicked:
                                        sub_clicked = await _eval(f"""
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
                                            await page.wait_for_timeout(2000)
                                    clicks = await _click_more_until_exhausted(page, safe_eval=_eval)
                                    items = await _extract_items(page, safe_eval=_eval)
                                    li_count = await _eval("document.querySelectorAll('.plan-list-area .plan-list li').length")
                                elif li_count > 0:
                                    # 리스트는 있지만 상세링크가 없는 경우: 페이지 로드 대기 후 재시도
                                    logger.warning(f"⚠️  상세링크 0개 감지 (li={li_count}), 페이지 로드 재시도 중...")
                                    await page.wait_for_timeout(2000)
                                    try:
                                        await page.wait_for_load_state('networkidle', timeout=5000)
                                    except Exception:
                                        pass
                                    items = await _extract_items(page, safe_eval=_eval)
                                
                                if len(items) == 0:
                                    logger.error(f"❌ 재시도 후에도 상세링크 0개: 탭='{tab.get('text','')}', 서브필터='{sub_filter.get('text','')}', clicks={clicks}, li={li_count}")
                            
                            logger.info(f"탭 '{tab.get('text','')}' > 서브필터 '{sub_filter.get('text','')}' 더보기 클릭 {clicks}회, li={li_count}, 상세링크={len(items)}개 수집")

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
                            logger.warning(f"서브 필터 '{sub_filter.get('text','')}' 처리 중 오류: {str(e)}")
                            continue
                else:
                    # 서브 필터 없으면 기존 로직
                    clicks = await _click_more_until_exhausted(page, safe_eval=_eval)
                    items = await _extract_items(page, safe_eval=_eval)
                    
                    # 현재 탭의 목록 화면도 캡처
                    try:
                        await _capture_list_snapshot(
                            page,
                            base_menu=(menu or "").strip(),
                            tab_text=tab.get('text', '').strip(),
                            safe_eval=_eval
                        )
                    except Exception:
                        pass

                    li_count = await _eval("document.querySelectorAll('.plan-list-area .plan-list li').length")
                    
                    # 상세링크 0개일 때 방어 로직: 재시도
                    if len(items) == 0:
                        if clicks == 0 and li_count == 0:
                            # 더보기 클릭이 0회이고 리스트도 없는 경우: 페이지 새로고침 후 재시도
                            logger.warning(f"⚠️  더보기 클릭 0회, 상세링크 0개 (li={li_count}) - 페이지 새로고침 후 재시도 중...")
                            await page.reload(timeout=10000)
                            await page.wait_for_timeout(2000)
                            try:
                                await page.wait_for_load_state('networkidle', timeout=5000)
                            except Exception:
                                pass
                            clicks = await _click_more_until_exhausted(page, safe_eval=_eval)
                            items = await _extract_items(page, safe_eval=_eval)
                            li_count = await _eval("document.querySelectorAll('.plan-list-area .plan-list li').length")
                        elif li_count > 0:
                            # 리스트는 있지만 상세링크가 없는 경우: 페이지 로드 대기 후 재시도
                            logger.warning(f"⚠️  상세링크 0개 감지 (li={li_count}), 페이지 로드 재시도 중...")
                            await page.wait_for_timeout(2000)
                            try:
                                await page.wait_for_load_state('networkidle', timeout=5000)
                            except Exception:
                                pass
                            items = await _extract_items(page, safe_eval=_eval)
                        
                        if len(items) == 0:
                            logger.error(f"❌ 재시도 후에도 상세링크 0개: 탭='{tab.get('text','')}', clicks={clicks}, li={li_count}")
                    
                    logger.info(f"탭 '{tab.get('text','')}' 더보기 클릭 {clicks}회, li={li_count}, 상세링크={len(items)}개 수집")

                    for it in items:
                        if not it.get('relHref'):
                            continue
                        detail_targets.append({
                            'tab': tab.get('text', ''),
                            'title': it.get('title', '').strip() or '(제목 없음)',
                            'relHref': it['relHref']
                        })
            except Exception as e:
                logger.warning(f"탭 처리 중 오류: {str(e)}")
                continue

        # 중복 제거 (ItemCode 기준) - "전체"보다 특정 탭 우선
        def count_specific_filters(target):
            """
            "전체"가 아닌 구체적인 필터의 개수를 카운트
            개수가 많을수록 더 구체적인 경로
            """
            tab = target.get('tab', '').strip()
            sub_filter = target.get('sub_filter', '').strip()
            
            count = 0
            if tab and tab != '전체':
                count += 1
            if sub_filter and sub_filter != '전체':
                count += 1
            
            return count
        
        seen_itemcodes = {}  # itemcode -> 가장 구체적인 target 정보
        unique_targets = []
        duplicate_items = []  # 중복 제거된 아이템 목록
        
        for target in detail_targets:
            match = re.search(r'ItemCode=(\d+)', target['relHref'])
            if match:
                itemcode = match.group(1)
                if itemcode in seen_itemcodes:
                    existing_target = seen_itemcodes[itemcode]
                    existing_count = count_specific_filters(existing_target)
                    current_count = count_specific_filters(target)
                    
                    # 현재 항목이 더 구체적이면 교체
                    if current_count > existing_count:
                        # 기존 항목을 중복 목록에 추가
                        duplicate_items.append({
                            'itemcode': itemcode,
                            'kept_tab': target['tab'],
                            'kept_sub': target.get('sub_filter', ''),
                            'removed_tab': existing_target['tab'],
                            'removed_sub': existing_target.get('sub_filter', ''),
                            'title': target.get('title', ''),
                            'reason': f'더 구체적 (특정 필터 {current_count}개 > {existing_count}개)'
                        })
                        # 기존 항목을 unique_targets에서 제거하고 현재 항목으로 교체
                        unique_targets = [t for t in unique_targets if not (re.search(r'ItemCode=(\d+)', t['relHref']) and re.search(r'ItemCode=(\d+)', t['relHref']).group(1) == itemcode)]
                        seen_itemcodes[itemcode] = target
                        unique_targets.append(target)
                    else:
                        # 기존 항목이 더 구체적이거나 같으면 현재 항목 버림
                        duplicate_items.append({
                            'itemcode': itemcode,
                            'kept_tab': existing_target['tab'],
                            'kept_sub': existing_target.get('sub_filter', ''),
                            'removed_tab': target['tab'],
                            'removed_sub': target.get('sub_filter', ''),
                            'title': target.get('title', ''),
                            'reason': f'덜 구체적이거나 동일 (특정 필터 {current_count}개 <= {existing_count}개)'
                        })
                    continue
                seen_itemcodes[itemcode] = target
            unique_targets.append(target)
        
        # 탭별 개수 카운트 (중복 제거 전과 후)
        tab_counts_before = {}
        for target in detail_targets:
            tab = target.get('tab', '기타')
            tab_counts_before[tab] = tab_counts_before.get(tab, 0) + 1
        
        tab_counts_after = {}
        for target in unique_targets:
            tab = target.get('tab', '기타')
            tab_counts_after[tab] = tab_counts_after.get(tab, 0) + 1
        
        logger.info(f"중복 제거: 전체 {len(detail_targets)}개 → 유니크 {len(unique_targets)}개 (중복 {len(duplicate_items)}개 제거)")
        
        # 중복 제거된 아이템 상세 로깅
        if duplicate_items:
            logger.info(f"\n{'='*80}")
            logger.info(f"🔍 중복 제거된 아이템 목록 ({len(duplicate_items)}개):")
            logger.info(f"{'='*80}")
            for i, dup in enumerate(duplicate_items, 1):
                kept_location = f"{dup['kept_tab']}"
                if dup['kept_sub']:
                    kept_location += f" > {dup['kept_sub']}"
                
                removed_location = f"{dup['removed_tab']}"
                if dup['removed_sub']:
                    removed_location += f" > {dup['removed_sub']}"
                
                logger.info(f"   {i}. ItemCode={dup['itemcode']}")
                logger.info(f"      유지: [{kept_location}]")
                logger.info(f"      삭제: [{removed_location}]")
                logger.info(f"      사유: {dup['reason']}")
                logger.info(f"      제목: {dup['title'][:50]}")
            logger.info(f"{'='*80}\n")
        
        if tab_counts_after:
            # 탭별 중복 제거 전후 비교
            logger.info("📊 탭별 개수 (중복 제거 전 → 후):")
            for tab in sorted(set(list(tab_counts_before.keys()) + list(tab_counts_after.keys()))):
                before = tab_counts_before.get(tab, 0)
                after = tab_counts_after.get(tab, 0)
                diff = before - after
                if diff > 0:
                    logger.info(f"   {tab}: {before} → {after} (중복 {diff}개)")
                else:
                    logger.info(f"   {tab}: {after}")
        
        detail_targets = unique_targets
        failed_targets = []

        # 상세 처리
        for i, target in enumerate(detail_targets, 1):
            detail_url = urljoin(base_host, target['relHref'])
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

            try:
                result = await handle_product_detail(detail_url, fclient, menu, browser=browser)
                if not result:
                    failed_targets.append({"url": detail_url, "error": "추출 실패 (handle_product_detail 반환 None)", "menu": final_menu})
                    logger.warning(f"⚠️ [wdic] 상세 추출 실패: {detail_url} (menu={final_menu})")
                    continue
                if isinstance(result, dict) and result.get("_failed"):
                    err_msg = result.get("error", "알 수 없음")
                    failed_targets.append({"url": detail_url, "error": err_msg, "menu": final_menu})
                    logger.warning(f"⚠️ [wdic] 상세 추출 실패: {detail_url} - {err_msg[:150]}")
                    continue

                menus.append({'menu': final_menu or (result.get('title') or ''), 'url': detail_url})
                datas.append(result)
                
                # additional_details 처리: N-pdt-compare-column의 "자세히 보기" 링크로 추출된 하위 상품들
                additional_details = result.get('additional_details', [])
                if additional_details:
                    logger.info(f"  📦 하위 상품 {len(additional_details)}개 발견")
                    for sub_result in additional_details:
                        # 하위 상품의 메뉴 구성: final_menu^하위상품명
                        sub_product_name = sub_result.get('parent_product_name') or sub_result.get('title', '')
                        if sub_product_name:
                            # 이름 정제 (줄바꿈, 연속 공백 제거)
                            sub_product_name = re.sub(r'[\r\n]+', ' ', sub_product_name)
                            sub_product_name = re.sub(r'\s+', ' ', sub_product_name).strip()
                            sub_menu = f"{final_menu}^{sub_product_name}"
                        else:
                            sub_menu = final_menu
                        
                        sub_url = sub_result.get('url', '')
                        menus.append({'menu': sub_menu, 'url': sub_url, 'murl': sub_result.get('murl', '')})
                        datas.append(sub_result)
                        logger.info(f"    └─ 하위 상품 추가: {sub_menu}")
                
                logger.info(f"[{i}/{len(detail_targets)}] 상세 처리 완료: {detail_url}")
            except Exception as e:
                logger.error(f"❌ [wdic] 상세 처리 중 오류: {detail_url} - {str(e)}", exc_info=True)
                failed_targets.append({"url": detail_url, "error": str(e), "menu": final_menu})
                continue

        await browser.close()

    logger.info(f"✅ wDic 목록 처리 완료: {len(datas)}개 아이템 수집 (실패 {len(failed_targets)}개)")
    if failed_targets:
        for ft in failed_targets:
            logger.warning(f"   ⚠️ 실패: {ft.get('url', '')[:80]}... | menu={ft.get('menu', '')} | error={str(ft.get('error', ''))[:100]}")

    return {
        'menus': menus,
        'datas': datas,
        'failed_targets': failed_targets,
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




