"""
KT Shop 관련 핸들러

KT Shop 팝업 추출, 모바일 상품 목록, 액세서리, 기획전 등 처리
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin
from asyncio import TimeoutError as AsyncTimeoutError

from playwright.async_api import async_playwright
from markdownify import markdownify as md
from bs4 import BeautifulSoup

from ..handler_registry import register_page_handler
from ..utils import to_mshop_url, sanitize_filename, smart_goto, safe_goto, launch_chromium

logger = logging.getLogger(__name__)


def _process_shop_detail_ocr(detail_html: str) -> str:
    """
    '다음내용참조' alt 이미지를 GPT-4V OCR로 텍스트 추출 후 HTML에 반영.
    OCR 실패 시 원본 HTML 반환.
    """
    try:
        import os
        import base64
        import requests
        from openai import OpenAI

        soup = BeautifulSoup(detail_html, 'html.parser')
        if not os.environ.get('OPENAI_API_KEY'):
            return detail_html

        openai_client = OpenAI()
        images = soup.find_all('img', alt='다음내용참조')
        if not images:
            return detail_html

        logger.info(f"🔍 {len(images)} images found, starting GPT-4V OCR...")
        for img in images:
            try:
                img_url = img.get('src', '')
                if not img_url:
                    continue
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    img_url = 'https://shop.kt.com' + img_url

                img_response = requests.get(img_url, timeout=90)
                from PIL import Image
                from io import BytesIO

                image = Image.open(BytesIO(img_response.content))
                width, height = image.size
                chunk_height = 1000
                image_chunks = []

                if height > chunk_height:
                    for y in range(0, height, chunk_height):
                        box = (0, y, width, min(y + chunk_height, height))
                        chunk = image.crop(box)
                        buffer = BytesIO()
                        chunk.save(buffer, format='JPEG', quality=95)
                        image_chunks.append(base64.b64encode(buffer.getvalue()).decode('utf-8'))
                else:
                    buffer = BytesIO()
                    image.save(buffer, format='JPEG', quality=95)
                    image_chunks.append(base64.b64encode(buffer.getvalue()).decode('utf-8'))

                all_ocr_texts = []
                for chunk_idx, chunk_data in enumerate(image_chunks):
                    api_response = openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "system",
                                "content": """당신은 마케팅 이미지에서 텍스트를 추출하는 OCR 전문가입니다.
1. 이미지에 보이는 모든 텍스트만 추출합니다.
2. 인물, 얼굴은 절대 분석하지 마세요.
3. 마크다운 코드블록 없이 순수 텍스트만 반환하세요."""
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"[이미지 {chunk_idx + 1}/{len(image_chunks)}] 이 마케팅 이미지에서 보이는 텍스트만 추출해주세요."},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{chunk_data}"}}
                                ]
                            }
                        ],
                        max_tokens=5000,
                        temperature=0.0
                    )
                    chunk_text = api_response.choices[0].message.content.strip()
                    chunk_text = re.sub(r'^```(?:plaintext|text|markdown)?\s*\n?', '', chunk_text)
                    chunk_text = re.sub(r'\n?```\s*$', '', chunk_text)
                    chunk_text = chunk_text.strip()

                    refusal_phrases = ["I'm sorry", "I can't assist", "I cannot assist", "I'm unable to", "I cannot help"]
                    if not any(p.lower() in chunk_text.lower() for p in refusal_phrases) and chunk_text:
                        all_ocr_texts.append(chunk_text)

                ocr_text = "\n".join(all_ocr_texts)
                if ocr_text and len(ocr_text) > 10:
                    new_tag = soup.new_tag('div')
                    new_tag.string = f'\n{ocr_text}\n'
                    img.replace_with(new_tag)
            except Exception as ocr_error:
                logger.warning(f"⚠️ OCR failed: {str(ocr_error)}")
                continue

        return str(soup)
    except ImportError:
        return detail_html
    except Exception as e:
        logger.warning(f"⚠️ OCR error: {str(e)}")
        return detail_html


async def handle_mobile_view_detail(
    url: str,
    fclient: Any,
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    shop.kt.com/mobile/view.do 단일 상세 페이지 핸들러.
    재시도(failed_targets) 및 직접 URL 크롤링 시 사용.
    """
    logger.info(f"🔗 KT Shop mobile view detail: {url}")

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        page = await browser.new_page()
        try:
            detail_resp = await safe_goto(
                page, url,
                wait_for_selector='.nwViewProdDetail, #cfmClContents, .prodDetailWrap, .prodDetail',
                base_timeout=75000, retries=3
            )
            if detail_resp is None:
                await browser.close()
                return {"error": "상세 페이지 로드 타임아웃"}

            await page.wait_for_timeout(2000)

            title = await page.evaluate("""
                () => {
                    const sel = document.querySelector('.nwViewProdDetail h1') || document.querySelector('.prd-tit')
                        || document.querySelector('.nwViewProdDetail .title') || document.querySelector('h1')
                        || document.querySelector('#cfmClContents h1');
                    return sel ? sel.textContent.trim() : '';
                }
            """)

            detail_html = await page.evaluate("""
                () => {
                    const containers = [
                        '.nwViewProdDetail', '#cfmClContents', '.prodDetailWrap', '.prodDetail', '#view-1',
                        '.ui-view-info', '.product-detail', 'main', 'article', '#content'
                    ];
                    for (const sel of containers){
                        const el = document.querySelector(sel);
                        if (el && el.innerHTML && el.innerHTML.trim().length>0) {
                            return el.innerHTML;
                        }
                    }
                    return document.body ? document.body.innerHTML : '';
                }
            """)
            detail_html = detail_html or ""
            detail_html = _process_shop_detail_ocr(detail_html)
            markdown_content = md(detail_html)
        finally:
            await browser.close()

    title = (title or "").strip() or "KT Shop 상품"

    return {
        "url": url,
        "murl": to_mshop_url(url),
        "title": title,
        "markdown": markdown_content,
        "html": detail_html,
        "special_processed": True,
        "playwright_processed": True,
    }


async def handle_ktshop_popup_extractor(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    KT Shop 페이지에서 팝업 트리거를 모두 순회하여 팝업 내용을 추출
    - layerOpen('#id', this) 형태의 트리거
    - javascript:void(0) + class 'plus' 트리거
    """
    t_start = time.perf_counter()
    logger.info(f"🔗 KT Shop popup: {url}")

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        try:
            t_goto = time.perf_counter()
            response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            logger.info(f"📄 [popup] page.goto 완료: {time.perf_counter() - t_goto:.1f}s, status={response.status if response else None}")
            
            status_code = response.status if response else None
            if status_code and status_code >= 400:
                logger.error(f"❌ HTTP {status_code}: {url}")
            
            # 동적 로딩 대기: 페이지 콘텐츠가 로드될 때까지 대기
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)
                logger.debug(f"📄 [popup] networkidle 완료")
            except Exception as e:
                logger.debug(f"📄 [popup] networkidle skip: {e}")
            await page.wait_for_timeout(2000)

            # 트리거 수집
            t_triggers = time.perf_counter()
            hash_triggers = await page.query_selector_all("*[onclick*='layerOpen(']")
            plus_triggers = await page.query_selector_all(
                "a[href^='javascript:void(0)'].plus, .plus[href^='javascript:void(0)'], *[onclick*='showDeviceModel('], *[onclick*='showDeviceInfo(']"
            )
            logger.info(f"🔍 [popup] Triggers: layerOpen={len(hash_triggers)}, plus={len(plus_triggers)} (수집 {time.perf_counter() - t_triggers:.1f}s)")

            async def _hide_overlays():
                try:
                    await page.evaluate("""
                        () => {
                            const selectors = ['.layerPop', '.modal', '.overlay', '.dim', '.dimmed', '.popup', '.opener'];
                            selectors.forEach(sel => {
                                document.querySelectorAll(sel).forEach(el => {
                                    el.style.display = 'none';
                                    el.style.visibility = 'hidden';
                                    el.style.pointerEvents = 'none';
                                });
                            });
                            document.body.style.overflow = 'auto';
                        }
                    """)
                except Exception:
                    pass

            async def _wait_for_visible_popup_html(timeout_ms=5000, preferred_selectors=None):
                base_candidates = [
                    '.layerPop', '.modal', '.popup', '[role="dialog"]',
                    '#esim-phone-model', '#phone-check-information', '#dual-sim-phone', '#dual-sim-word', '#dualNumber-setting'
                ]
                candidates = list(preferred_selectors or []) + base_candidates
                attempts = max(1, int(timeout_ms / 250))
                for _ in range(attempts):
                    for sel in candidates:
                        try:
                            el = await page.query_selector(sel)
                            if el:
                                visible = await el.evaluate("""
                                    (node) => {
                                        const cs = window.getComputedStyle(node);
                                        const rect = node.getBoundingClientRect();
                                        return cs && cs.display !== 'none' && cs.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                                    }
                                """)
                                if visible:
                                    try:
                                        html = await el.inner_html()
                                        return html
                                    except Exception:
                                        pass
                        except Exception:
                            continue
                    await page.wait_for_timeout(250)
                return ""

            async def _insert_after_trigger(trigger_handle, html_content):
                try:
                    await trigger_handle.evaluate(
                        """
                        (el, html) => {
                            const container = document.createElement('div');
                            container.className = 'ai-popup-extracted';
                            container.innerHTML = html || '';
                            if (el && el.parentNode) {
                                if (el.nextSibling) {
                                    el.parentNode.insertBefore(container, el.nextSibling);
                                } else {
                                    el.parentNode.appendChild(container);
                                }
                            }
                        }
                        """,
                        html_content
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Insert failed: {str(e)}")

            # layerOpen 트리거 처리
            layer_ok, layer_skip, layer_fail = 0, 0, 0
            for idx, a in enumerate(hash_triggers, 1):
                t_loop = time.perf_counter()
                try:
                    onclick_text = await a.get_attribute('onclick')
                    target_id = None
                    if onclick_text:
                        m = re.search(r"layerOpen\(\s*['\"](#[^'\"]+)['\"]", onclick_text)
                        if m:
                            target_id = m.group(1)
                    
                    try:
                        await a.click()
                        click_ok = True
                    except Exception as click_err:
                        await page.evaluate("el => el.click()", a)
                        click_ok = False
                        logger.debug(f"📌 [popup] layerOpen[{idx}/{len(hash_triggers)}] click fallback: {click_err}")
                    await page.wait_for_timeout(900)

                    popup_html = ""
                    if target_id:
                        try:
                            target_el = await page.query_selector(target_id)
                            if target_el and await target_el.is_visible():
                                popup_html = await target_el.inner_html()
                            elif target_el:
                                await page.evaluate(
                                    "sel => { const el = document.querySelector(sel); if (el){ el.style.display='block'; el.style.visibility='visible'; } }", 
                                    target_id
                                )
                                await page.wait_for_timeout(200)
                                popup_html = await target_el.inner_html()
                        except Exception as ext_err:
                            logger.debug(f"📌 [popup] layerOpen[{idx}] target_id={target_id} 추출 실패: {ext_err}")
                    
                    if not popup_html:
                        popup_html = await _wait_for_visible_popup_html(5000)

                    if popup_html:
                        await _insert_after_trigger(a, popup_html)
                        layer_ok += 1
                        logger.info(f"📌 [popup] layerOpen[{idx}/{len(hash_triggers)}] target={target_id or '?'} html={len(popup_html)}chars {time.perf_counter() - t_loop:.1f}s")
                    else:
                        layer_skip += 1
                        logger.info(f"📌 [popup] layerOpen[{idx}/{len(hash_triggers)}] target={target_id or '?'} popup 빈값 {time.perf_counter() - t_loop:.1f}s")

                    await _hide_overlays()
                    try:
                        await page.keyboard.press('Escape')
                    except Exception:
                        pass
                    await page.wait_for_timeout(200)
                except Exception as e:
                    layer_fail += 1
                    logger.warning(f"⚠️ [popup] layerOpen[{idx}/{len(hash_triggers)}] 실패: {str(e)}", exc_info=True)

            # plus 트리거 처리
            plus_ok, plus_skip, plus_fail = 0, 0, 0
            logger.info(f"📌 [popup] layerOpen 완료: ok={layer_ok} skip={layer_skip} fail={layer_fail}")
            for idx, a in enumerate(plus_triggers, 1):
                t_loop = time.perf_counter()
                try:
                    onclick_text = (await a.get_attribute('onclick')) or ''
                    preferred_selectors = []
                    if 'showDeviceModel' in onclick_text:
                        preferred_selectors = ['#esim-phone-model']
                    elif 'showDeviceInfo' in onclick_text:
                        preferred_selectors = ['#phone-check-information']
                    
                    try:
                        await a.click()
                    except Exception as click_err:
                        await page.evaluate("el => el.click()", a)
                        logger.debug(f"📌 [popup] plus[{idx}] click fallback: {click_err}")
                    await page.wait_for_timeout(900)

                    popup_html = await _wait_for_visible_popup_html(5000, preferred_selectors)

                    if popup_html:
                        await _insert_after_trigger(a, popup_html)
                        plus_ok += 1
                        logger.info(f"📌 [popup] plus[{idx}/{len(plus_triggers)}] html={len(popup_html)}chars {time.perf_counter() - t_loop:.1f}s")
                    else:
                        plus_skip += 1
                        logger.info(f"📌 [popup] plus[{idx}/{len(plus_triggers)}] popup 빈값 {time.perf_counter() - t_loop:.1f}s")

                    await _hide_overlays()
                    try:
                        await page.keyboard.press('Escape')
                    except Exception:
                        pass
                    await page.wait_for_timeout(200)
                except Exception as e:
                    plus_fail += 1
                    logger.warning(f"⚠️ [popup] plus[{idx}/{len(plus_triggers)}] 실패: {str(e)}", exc_info=True)

            # 정리
            try:
                await page.evaluate("""
                    () => {
                        document.querySelectorAll('article').forEach(article => {
                            const keeps = Array.from(article.querySelectorAll('.ai-popup-extracted'));
                            while (article.firstChild) article.removeChild(article.firstChild);
                            keeps.forEach(node => {
                                const clone = node.cloneNode(true);
                                article.appendChild(clone);
                            });
                        });
                        const removeSelectors = [
                            '#cfmClHeader', '#cfmClFooter', '#cfmClSkip',
                            '.location', '.sns-area', '.opener'
                        ];
                        removeSelectors.forEach(sel => {
                            document.querySelectorAll(sel).forEach(e => e.remove());
                        });
                    }
                """)
            except Exception:
                pass

            try:
                html_content = await page.eval_on_selector("#cfmClContents", "el => el.outerHTML")
                logger.info(f"📄 [popup] #cfmClContents 추출 성공: {len(html_content)}chars")
            except Exception as ext_err:
                html_content = await page.content()
                logger.info(f"📄 [popup] #cfmClContents 없음, page.content 사용: {len(html_content)}chars ({ext_err})")

            title = await page.title()
            await browser.close()
            elapsed = time.perf_counter() - t_start
            logger.info(f"✅ [popup] 완료: layerOpen ok={layer_ok} skip={layer_skip} fail={layer_fail} | plus ok={plus_ok} skip={plus_skip} fail={plus_fail} | 총 {elapsed:.1f}s")

        except Exception as e:
            elapsed = time.perf_counter() - t_start
            logger.error(f"❌ [popup] Popup failed ({elapsed:.1f}s): {str(e)}", exc_info=True)
            try:
                await browser.close()
            except Exception:
                pass
            return {
                "url": url,
                "title": "KT Shop 팝업 처리 실패",
                "markdown": f"# 처리 실패\n\n오류: {str(e)}",
                "html": f"<h1>처리 실패</h1><p>{str(e)}</p>",
                "status_code": None,
                "special_processed": True,
                "playwright_processed": True,
                "error": str(e)
            }

    try:
        markdown_content = md(html_content, heading_style="ATX")
    except Exception:
        markdown_content = ""

    logger.info(f"✅ Popup done (총 {time.perf_counter() - t_start:.1f}s)")

    return {
        "url": url,
        "murl": to_mshop_url(url),
        "title": title,
        "markdown": markdown_content,
        "html": html_content,
        "status_code": status_code,
        "special_processed": True,
        "playwright_processed": True
    }


# 핸들러 등록 - KT Shop 다양한 URL들
KTSHOP_URLS = [
    r'https?://shop\.kt\.com/direct/directEsim\.do',
    r'https?://shop\.kt\.com/direct/directUsim\.do',
    r'https?://shop\.kt\.com/direct/quickUsim\.do',
    r'https?://shop\.kt\.com/unify/mobile\.do\?.*category=changePhone',
    r'https?://shop\.kt\.com/direct/directPhoneOrder\.do',
    r'https?://shop\.kt\.com/direct/directAddUsim\.do',
    r'https?://shop\.kt\.com/direct/directDual\.do',
    r'https?://shop\.kt\.com/unify/mobile\.do\?.*category=usim',
    r'https?://shop\.kt\.com/direct/directSmart\.do',
    r'https?://shop\.kt\.com/direct/directEsimMove\.do',
]

for pattern in KTSHOP_URLS:
    register_page_handler(pattern, handle_ktshop_popup_extractor)


async def handle_mobile_products_list(url: str, fclient: Any, menu: Optional[str] = None) -> Dict[str, Any]:
    """
    모바일 제품 리스트 페이지 처리 핸들러
    - 리스트에서 prodnm(제품명) 및 상세 진입 정보 수집
    - 각 제품 상세에서 '제품 특징', '유의사항' 추출
    """
    logger.info(f"🔗 Mobile products: url={url}")
    menus, datas = [], []
    base_menu = (menu or '').strip()
    base_title = base_menu.split('^')[-1].strip() if base_menu else '모바일 제품 리스트'
    base_title = sanitize_filename(base_title)

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await safe_goto(page, url, base_timeout=60000, retries=2)
        if response is None:
            await browser.close()
            return {
                'menus': [],
                'datas': [],
                'failed_targets': [{"url": url, "error": "page_load_timeout", "menu": base_menu or "모바일 제품"}],
                'total_processed': 0,
                'status': 'completed',
                'message': "리스트 페이지 로드 실패 (타임아웃)"
            }
        await page.wait_for_timeout(2500)

        for attempt in range(2):
            try:
                await page.wait_for_function(
                    "document.querySelectorAll('.nwProdList input[name=\"prodAttr\"]').length > 0",
                    timeout=20000,
                )
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"⚠️ prodAttr not found, retrying... ({e})")
                    await page.wait_for_timeout(2000)
                else:
                    logger.warning("⚠️ prodAttr not found after retry")

        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logger.error(f"❌ HTTP {status_code}: {url}")

        # 메인 페이지 콘텐츠 추출
        try:
            main_html = await page.evaluate("""
                () => {
                    const selectors = ['.nwListArea.inner', '.nwWrap', '#cfmClContents'];
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

        # 리스트에서 제품명/상세 진입 정보 수집
        product_items = await page.evaluate(r"""
            () => {
                const results = [];
                const roots = Array.from(document.querySelectorAll('.nwProdList'));
                for (const root of roots){
                    root.querySelectorAll('input[name="prodAttr"]').forEach((inp) => {
                        const prodnm = inp.getAttribute('prodnm') || '';
                        const prodno = inp.getAttribute('prodno') || '';
                        const sntyno = inp.getAttribute('sntyno') || '';
                        const pplid = inp.getAttribute('pplid') || '';
                        const svcengtmonstypecd = inp.getAttribute('svcengtmonstypecd') || '';
                        const supporttype = inp.getAttribute('supporttype') || '';
                        if (prodnm) {
                            results.push({ prodnm, prodno, sntyno, pplid, svcengtmonstypecd, supporttype });
                        }
                    });
                }
                return results;
            }
        """)

        logger.info(f"🔍 List: {len(product_items)} items")
        prodnm_list = [pi.get("prodnm", "") for pi in product_items if pi.get("prodnm")]
        logger.info(f"🔍 product_items prodnm: {prodnm_list[:15]}{'...' if len(prodnm_list) > 15 else ''} (총 {len(prodnm_list)}개)")
        for i, pi in enumerate(product_items):
            logger.debug(f"   [product_items][{i}] prodnm={pi.get('prodnm','')} prodno={pi.get('prodno','')}")

        # 제품별 대표 정보 정리
        normalized = []
        seen_names: Set[str] = set()

        for item in product_items:
            prodnm = (item.get('prodnm') or '').strip()
            if not prodnm or prodnm in seen_names:
                if prodnm and prodnm in seen_names:
                    logger.debug(f"   [skip] prodnm 중복: {prodnm} (prodno={item.get('prodno','')})")
                continue
            seen_names.add(prodnm)

            prodno = (item.get('prodno') or '').strip()
            detail_url = url
            if prodno:
                # prodNo만 포함 (sntyNo, pplId, svcEngtMonsTypeCd, supportType 제거)
                detail_url = f"https://shop.kt.com/mobile/view.do?prodNo={prodno}"
            normalized.append({'name': prodnm, 'url': detail_url, 'prodno': prodno})

        normalized_names = [n["name"] for n in normalized]
        logger.info(f"🔍 Normalized: {normalized_names[:15]}{'...' if len(normalized_names) > 15 else ''} (총 {len(normalized)}개)")
        for i, n in enumerate(normalized):
            logger.debug(f"   [normalized][{i}] {n['name']} prodno={n.get('prodno','')} url={n['url'][:80]}...")
        failed_targets = []

        # 각 제품 상세에서 내용 추출
        for idx, prod in enumerate(normalized, 1):
            try:
                logger.info(f"🔍 [{idx}/{len(normalized)}] Detail: {prod['name']}")
                if prod.get('url') and prod['url'] != url:
                    try:
                        detail_resp = await safe_goto(
                            page, prod['url'],
                            wait_for_selector='.nwViewProdDetail, #cfmClContents, .prodDetailWrap, .prodDetail',
                            base_timeout=75000, retries=3
                        )
                        if detail_resp is None:
                            raise Exception("상세 페이지 로드 타임아웃")
                        await page.wait_for_timeout(2000)
                    except Exception as _e:
                        menu_name = f"{base_menu}^{prod['name']}" if base_menu else f"Shop^{prod['name']}"
                        failed_targets.append({"url": prod['url'], "error": f"Navigation failed: {str(_e)}", "menu": menu_name})
                        logger.warning(f"⚠️ [ktshop] Navigation failed: {prod['url']} - {str(_e)}")
                        continue

                detail_html = await page.evaluate("""
                    () => {
                        const containers = [
                            '.nwViewProdDetail', '#cfmClContents', '.prodDetailWrap', '.prodDetail', '#view-1',
                            '.ui-view-info', '.product-detail', 'main', 'article', '#content'
                        ];
                        for (const sel of containers){
                            const el = document.querySelector(sel);
                            if (el && el.innerHTML && el.innerHTML.trim().length>0) {
                                return el.innerHTML;
                            }
                        }
                        return document.body ? document.body.innerHTML : '';
                    }
                """)
                raw_len = len(detail_html or "")
                detail_html = _process_shop_detail_ocr(detail_html or "")
                if raw_len < 500:
                    logger.debug(f"   [detail][{idx}] {prod['name']}: raw_html={raw_len}chars (빈/짧음)")

                md_all = md(detail_html)
                menu_name = f"{base_menu}^{prod['name']}" if base_menu else f"Shop^{prod['name']}"
                menus.append({'menu': menu_name, 'url': prod['url'], 'murl': to_mshop_url(prod['url'])})
                datas.append({
                    'url': prod['url'],
                    'title': prod['name'],
                    'markdown': md_all,
                    'html': detail_html,
                    'special_processed': True,
                    'playwright_processed': True,
                    'murl': to_mshop_url(prod['url'])
                })
                logger.debug(f"   [detail][{idx}] {prod['name']}: OK datas.append (html={len(detail_html)}chars)")
            except Exception as e:
                menu_name = f"{base_menu}^{prod['name']}" if base_menu else f"Shop^{prod['name']}"
                failed_targets.append({"url": prod.get('url', ''), "error": str(e), "menu": menu_name})
                logger.warning(f"⚠️ [ktshop] Detail failed: {prod.get('name','unknown')} ({prod.get('url','')}) - {str(e)}", exc_info=True)
                continue

        await browser.close()

    logger.info(f"✅ KT Shop 목록 처리 완료: {len(datas)}개 수집 (실패 {len(failed_targets)}개)")
    if failed_targets:
        for ft in failed_targets:
            logger.warning(f"   ⚠️ 실패: {ft.get('url', '')[:80]}... | menu={ft.get('menu', '')} | error={str(ft.get('error', ''))[:100]}")
    return {
        'menus': menus,
        'datas': datas,
        'failed_targets': failed_targets,
        'total_processed': len(datas),
        'status': 'completed',
        'message': f"총 {len(datas)}개 모바일 제품 처리 완료"
    }


register_page_handler(
    r'https?://shop\.kt\.com/mobile/products\.do\?category=.*',
    handle_mobile_products_list
)
register_page_handler(
    r'https?://shop\.kt\.com/mobile/view\.do\?prodNo=.*',
    handle_mobile_view_detail
)


async def handle_accessory_detail_page(
    url: str,
    fclient: Any,
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    shop.kt.com/accessory/accsProductView.do 단일 상세 페이지 핸들러.
    재시도(failed_targets) 및 직접 URL 크롤링 시 사용.
    """
    result = await handle_accessory_detail(url, fclient, context=None)
    if result is None:
        return {"error": "액세서리 상세 페이지 추출 실패"}
    return result


async def handle_accessory_detail(url: str, fclient: Any, context=None) -> Optional[Dict[str, Any]]:
    """액세서리 상세 페이지 핸들러 (내부/목록 핸들러에서 호출)"""
    logger.info(f"🔗 Accessory detail: {url}")

    async def _process_detail(ctx) -> Optional[Dict[str, Any]]:
        page = await ctx.new_page()
        status_detail = None
        try:
            try:
                response_detail = await smart_goto(
                    page, url,
                    wait_for_selector='.ui-prd_tit, .prd-tit, h1, .ui-view-info',
                    timeout=60000,
                    selector_timeout=20000,
                    extra_wait=3000
                )
            except Exception:
                logger.error(f"❌ Detail page timeout")
                return None
            status_detail = response_detail.status if response_detail else None

            title = await page.evaluate("""
                () => {
                    const sel = document.querySelector('.ui-prd_tit') || document.querySelector('.prd-tit') 
                        || document.querySelector('h1') || document.querySelector('.ui-view-info h2');
                    return sel ? sel.textContent.trim() : '';
                }
            """)
            info_html = await page.evaluate("""
                () => {
                    const sel = document.querySelector('.ui-view-info') || document.querySelector('.ui-prd_tit')?.closest('.ui-view-info') 
                        || document.querySelector('.product-info') || document.querySelector('.prd-info');
                    return sel ? sel.outerHTML : '';
                }
            """)
            tab_html = await page.evaluate("""
                () => {
                    const sel = document.querySelector('.ui-prdView-tab') || document.querySelector('.prd-tab') 
                        || document.querySelector('[class*="tab"]');
                    return sel ? sel.outerHTML : '';
                }
            """)

            combined_html_parts = [part for part in [info_html, tab_html] if part]
            combined_html = "\n".join(combined_html_parts)
            markdown = md(combined_html) if combined_html else ''

            result = {
                'url': url,
                'murl': to_mshop_url(url),
                'title': title,
                'html': combined_html,
                'markdown': markdown,
                'status_code': status_detail,
                'special_processed': True,
                'playwright_processed': True
            }

            return result
        except Exception as exc:
            logger.warning(f"⚠️ Accessory detail failed ({url}): {exc}")
            return None
        finally:
            try:
                await page.close()
            except Exception:
                pass

    if context is not None:
        return await _process_detail(context)

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context_local = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        try:
            return await _process_detail(context_local)
        finally:
            await browser.close()


async def handle_accessory_display_list(url: str, fclient: Any, menu: Optional[str] = None) -> Dict[str, Any]:
    """액세서리 display 목록 핸들러"""
    logger.info(f"🔗 Accessory list: {url}")

    menus: List[Dict[str, Any]] = []
    datas: List[Dict[str, Any]] = []
    seen_prodnos: Set[str] = set()

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        response = await smart_goto(page, url, wait_for_selector='ul.ui-access-prdLst', timeout=45000)
        status_code = response.status if response else None

        async def extract_items() -> List[Dict[str, Any]]:
            return await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('ul.ui-access-prdLst li a.ui-btn-access')).map((a, index) => ({
                    prodNo: a.getAttribute('prodno') || '',
                    title: (a.querySelector('.prd-tit')?.textContent || a.textContent || '').trim(),
                    index
                }));
            }""")

        async def get_current_page() -> int:
            try:
                current = await page.evaluate("""() => {
                    const strong = document.querySelector('.pageWrap strong');
                    return strong ? strong.textContent.trim() : '';
                }""")
                return int(current or '1')
            except Exception:
                return 1

        async def goto_page(target: int) -> bool:
            locator = page.locator('.pageWrap a', has_text=str(target))
            if await locator.count() > 0:
                try:
                    await locator.first.click()
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(800)
                    return True
                except Exception:
                    pass
            return False

        async def fetch_detail(prod_no: str, title_hint: str) -> Optional[Dict[str, Any]]:
            detail_url = f"https://shop.kt.com/accessory/accsProductView.do?prodNo={prod_no}"
            detail = await handle_accessory_detail(detail_url, fclient, context)
            if not detail:
                return None
            if not detail.get('title') and title_hint:
                detail['title'] = title_hint
            return detail

        current_page = await get_current_page()

        while True:
            items = await extract_items()
            logger.info(f"🔍 Page {current_page}: {len(items)} items")

            for item in items:
                prod_no = (item.get('prodNo') or '').strip()
                title_hint = (item.get('title') or '').strip()
                if not prod_no or prod_no in seen_prodnos:
                    continue
                seen_prodnos.add(prod_no)

                detail = await fetch_detail(prod_no, title_hint)
                if not detail:
                    continue

                base_menu = (menu or '').strip()
                menu_name = f"{base_menu}^{detail['title']}" if base_menu else f"Shop^액세서리 구매^{detail['title']}"

                menus.append({'menu': menu_name, 'url': detail['url'], 'murl': detail.get('murl')})
                datas.append(detail)

            next_target = current_page + 1
            moved = await goto_page(next_target)
            if not moved:
                break

            new_page = await get_current_page()
            if new_page == current_page:
                break
            current_page = new_page

        await browser.close()

    logger.info(f"✅ Accessory done: {len(datas)} items")
    return {
        'menus': menus,
        'datas': datas,
        'total_processed': len(datas),
        'status': 'completed',
        'special_processed': True,
        'playwright_processed': True
    }


# 액세서리 목록 핸들러 등록
ACCESSORY_PATTERNS = [
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR042901',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR042902',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR042903',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043002',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043004',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043005',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043006',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043007',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043101',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043102',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043103',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043104',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043105',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043401',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043402',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043501',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043502',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043503',
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043504',
]

for pattern in ACCESSORY_PATTERNS:
    register_page_handler(pattern, handle_accessory_display_list)


register_page_handler(
    r'https?://shop\.kt\.com/accessory/accsProductView\.do\?prodNo=.*',
    handle_accessory_detail_page
)


async def handle_goodbye_phoneview(url: str, fclient: Any, menu: Optional[str] = None) -> Dict[str, Any]:
    """굿바이 phoneView.do 전용 핸들러 (display:none 모두 표시 후 전체 추출)"""
    logger.info(f"🔗 Goodbye phoneView: {url}")
    menus, datas = [], []

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        
        status_code = response.status if response else None
        
        # 동적 로딩 대기: 액세서리 목록이 로드될 때까지 대기
        try:
            await page.wait_for_selector('.plan-list-area .plan-list li, .accessory-item', timeout=10000)
            logger.info("✅ Accessory list loaded")
        except Exception as e:
            logger.warning(f"⚠️ Accessory list not loaded: {e}")
        await page.wait_for_timeout(1000)

        # display:none/hidden 요소 강제 표시
        await page.evaluate("""
            () => {
                const show = (el) => {
                    if (!el) return;
                    try {
                        el.style.display = 'block';
                        el.style.visibility = 'visible';
                        el.style.opacity = '1';
                        el.style.height = 'auto';
                        el.style.maxHeight = 'none';
                    } catch(e) {}
                };
                document.querySelectorAll('[hidden], .hidden, .is-hidden').forEach(n => {
                    n.removeAttribute('hidden');
                    show(n);
                });
                document.querySelectorAll('*').forEach(n => {
                    const st = (n.getAttribute('style')||'').toLowerCase();
                    if (st.includes('display:none')) show(n);
                    if (st.includes('visibility:hidden')) show(n);
                });
                ['.nwViewProdDetail', '#cfmClContents', '.prodDetailWrap', '.prodDetail', '#view-1', '#view-4']
                  .forEach(sel => show(document.querySelector(sel)));
            }
        """)
        await page.wait_for_timeout(200)

        # 컨테이너 우선 순위로 전체 HTML 획득
        detail_html = await page.evaluate("""
            () => {
                const containers = ['.nwViewProdDetail', '#cfmClContents', '.prodDetailWrap', '.prodDetail', '#content', 'main'];
                for (const sel of containers){
                    const el = document.querySelector(sel);
                    if (el && el.innerHTML && el.innerHTML.trim().length>0) return el.innerHTML;
                }
                return document.body ? document.body.innerHTML : '';
            }
        """)

        md_all = md(detail_html)

        # 타이틀 추출
        base_menu_in = (menu or '').strip()
        try:
            title_text = (await page.evaluate("""
                () => {
                    const pick = (sel) => {
                        const el = document.querySelector(sel);
                        return el ? (el.innerText||'').trim() : '';
                    };
                    return pick('h1') || pick('.title') || pick('.tit') || document.title || '';
                }
            """)) or '굿바이 중고폰 보상'
        except Exception:
            title_text = '굿바이 중고폰 보상'

        if base_menu_in:
            mobile_url = url if '/m/' in url else to_mshop_url(url)
            menus.append({'menu': base_menu_in, 'url': url, 'murl': mobile_url})
        datas.append({
            'url': url,
            'title': title_text,
            'markdown': md_all,
            'html': detail_html,
            'special_processed': True,
            'playwright_processed': True,
            'murl': url if '/m/' in url else to_mshop_url(url)
        })

        await browser.close()

    return {
        'menus': menus,
        'datas': datas,
        'total_processed': len(datas),
        'status': 'completed',
        'message': f"phoneView done ({len(datas)} items)"
    }


register_page_handler(
    r'https?://shop\.kt\.com/goodbye/phoneView\.do.*',
    handle_goodbye_phoneview
)


async def handle_store_plans_list(url: str, fclient: Any, menu: Optional[str] = None) -> Dict[str, Any]:
    """기획전 목록/상세 핸들러 (olhsStore.do → olhsPlan.do)"""
    logger.info(f"🔗 Plans list: {url}")
    menus, datas = [], []

    def _norm_date(dtxt: str) -> str:
        try:
            m = re.search(r'(20\d{2})[\.-]\s*(\d{1,2})[\.-]\s*(\d{1,2})', dtxt)
            if not m:
                return ''
            y, mo, dy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f"{y:04d}-{mo:02d}-{dy:02d}"
        except Exception:
            return ''

    async with async_playwright() as p:
        browser = await launch_chromium(p)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=90000)
        
        status_code = response.status if response else None

        # iframe 탐색 - iframe이 로드될 때까지 대기
        try:
            await page.wait_for_selector('iframe', timeout=10000)
            logger.info("✅ iframe loaded")
        except Exception as e:
            logger.warning(f"⚠️ iframe not found: {e}")
        await page.wait_for_timeout(3000)  # iframe 내용 로딩 대기
        
        target_frame = None
        
        # 1단계: .plan_tit를 포함하는 프레임 찾기
        for fr in page.frames:
            if fr == page.main_frame:
                continue
            try:
                # frame이 실제 콘텐츠를 가지고 있는지 확인
                plan_tit = await fr.query_selector('.plan_tit')
                if plan_tit:
                    target_frame = fr
                    logger.info(f"✅ Found .plan_tit iframe")
                    break
            except Exception:
                continue
        
        # 2단계: .plan_tit가 없으면 콘텐츠가 있는 첫 번째 프레임 선택
        if not target_frame:
            for fr in page.frames:
                if fr == page.main_frame:
                    continue
                try:
                    # 빈 iframe 제외 (실제 콘텐츠가 있는지 확인)
                    content = await fr.content()
                    if content and len(content) > 500:  # 최소 콘텐츠 길이 체크
                        target_frame = fr
                        logger.info(f"✅ Found iframe with content (len: {len(content)})")
                        break
                except Exception:
                    continue

        if not target_frame:
            logger.warning("⚠️ No valid iframe found")
            await browser.close()
            return {'menus': [], 'datas': [], 'total_processed': 0, 'status': 'completed', 'message': '프레임 미탐지'}

        # 총 페이지 수 추정
        try:
            total_pages = await target_frame.evaluate("""
                () => {
                    const pg = document.querySelector('.pageWrap.ui-paging');
                    if (!pg) return 1;
                    let max = 1;
                    pg.querySelectorAll('[pageno]').forEach(a => {
                        const n = parseInt(a.getAttribute('pageno')||'1');
                        if (!isNaN(n) && n>max) max = n;
                    });
                    return max || 1;
                }
            """)
        except Exception:
            total_pages = 1

        logger.info(f"🔍 Total pages: {total_pages}")

        collected = []

        async def extract_page_items() -> list:
            try:
                return await target_frame.evaluate(r"""
                    () => {
                        const items = [];
                        document.querySelectorAll('.plan_tit').forEach(t => {
                            const title = (t.innerText||'').replace(/\s+/g,' ').trim();
                            let href = '';
                            let a = t.closest('a');
                            if (!a || !a.getAttribute('href')){
                                const parent = t.parentElement;
                                if (parent) {
                                    a = parent.querySelector('a[href]');
                                }
                                if ((!a || !a.getAttribute('href')) && parent) {
                                    const grandParent = parent.parentElement;
                                    if (grandParent) {
                                        a = grandParent.querySelector('a[href]');
                                    }
                                }
                            }
                            if (a && a.getAttribute('href')){
                                href = a.href || a.getAttribute('href') || '';
                            }
                            let period = '';
                            const root = t.closest('li') || t.closest('div') || document;
                            const blindSpans = root.querySelectorAll('span.blind');
                            for (const sp of blindSpans){
                                if ((sp.innerText||'').includes('전시기간')){
                                    const par = sp.parentElement;
                                    if (par){ period = par.innerText.replace(/\s+/g,' ').trim(); break; }
                                }
                            }
                            if (title){ items.push({ title, href, period }); }
                        });
                        return items;
                    }
                """)
            except Exception:
                return []

        for pno in range(1, (total_pages or 1)+1):
            try:
                if pno > 1:
                    try:
                        await target_frame.click(f'a[pageno="{pno}"]', timeout=8000)
                        await page.wait_for_timeout(600)
                    except Exception:
                        pass
                rows = await extract_page_items()
                logger.info(f"🔍 Page {pno}: {len(rows)} items")
                for r in rows:
                    if any(x.get('href') == r.get('href') and x.get('title') == r.get('title') for x in collected):
                        continue
                    collected.append(r)
            except Exception as e:
                logger.warning(f"⚠️ Page {pno} failed: {str(e)}")

        logger.info(f"🔍 Collected: {len(collected)} items")

        # 상세 페이지 순회
        for idx, row in enumerate(collected, 1):
            title = (row.get('title') or '').strip()
            href = row.get('href') or ''
            period = row.get('period') or ''
            startdate = _norm_date(period)
            
            detail_url = ''
            if href and not href.lower().startswith('javascript'):
                detail_url = urljoin('https://shop.kt.com', href)
            
            logger.info(f"🔍 [{idx}/{len(collected)}] Detail: {title}")
            detail_html = ''
            md_text = ''
            
            try:
                if detail_url and fclient:
                    # scrape_single_url은 비동기 메서드
                    result = await fclient.scrape_single_url(detail_url)
                    if result and result.get('success'):
                        detail_html = result.get('html', '')
                        md_text = result.get('markdown', '')
            except Exception as e:
                logger.warning(f"⚠️ Detail crawl failed: {str(e)}")

            if not md_text:
                md_text = md(detail_html, heading_style="ATX") if detail_html else ''

            base_menu = (menu or '').strip()
            menu_name = f"{base_menu}^{title}" if base_menu else f"Shop^핫딜/기획전^기획전^통신상품^{title}"
            menus.append({'menu': menu_name, 'url': detail_url or url, 'murl': to_mshop_url(detail_url or url)})
            datas.append({
                'url': detail_url or url,
                'title': title,
                'markdown': md_text or '',
                'html': detail_html or '',
                'special_processed': True,
                'playwright_processed': True,
                'startdate': startdate or '',
                'murl': to_mshop_url(detail_url or url)
            })

        await browser.close()

    return {
        'menus': menus,
        'datas': datas,
        'total_processed': len(datas),
        'status': 'completed',
        'message': f"총 {len(datas)}개 기획전 처리 완료"
    }


register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR05&subDispNo=STOR0501.*',
    handle_store_plans_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR05&subDispNo=STOR0503.*',
    handle_store_plans_list
)
