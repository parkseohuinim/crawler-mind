"""
기가지니 관련 핸들러

기가지니 서비스 상세, FAQ, 뉴스 목록 처리
"""

import logging
import re
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler
from ..utils import to_gigagenie_murl, smart_goto

logger = logging.getLogger(__name__)


def clean_img_alt(md_text: str) -> str:
    """alt에 <가 포함된 경우 alt를 비움"""
    def repl(match):
        alt = match.group(1)
        url = match.group(2)
        if '<' in alt:
            return f"![]({url})"
        else:
            return match.group(0)
    return re.sub(r'!\[(.*?)\]\((.*?)\)', repl, md_text, flags=re.DOTALL)


async def handle_gigagenie_detail(
    url: str, 
    fclient: Any = None, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    기가지니 서비스 상세 페이지 크롤링
    - 2뎁스 버튼들을 모두 순회하며 클릭
    - 각 버튼 클릭 후 본문 내용을 추출
    """
    logger.info(f"Gigagenie detail page processing started: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await smart_goto(page, url, wait_for_selector="#depth2Level", timeout=30000)
        
        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logger.error(f"❌ Gigagenie detail ({url}): HTTP {status_code} error")

        # 2뎁스 버튼 목록 추출
        buttons = await page.query_selector_all("#depth2Level li button")
        markdown_content = ""
        html_content = ""
        
        if buttons and len(buttons) > 0:
            tab_infos = []
            for btn in buttons:
                span = await btn.query_selector("span")
                tab_name = (await span.inner_text()).strip() if span else (await btn.inner_text()).strip()
                tab_infos.append({"button": btn, "tab_name": tab_name})

            for tab in tab_infos:
                btn = tab["button"]
                tab_name = tab["tab_name"]
                try:
                    await btn.click()
                    await page.wait_for_timeout(1200)
                    content_div = await page.query_selector("div.fjbInnerTabBox[class*='fjbTabCon'][class~='on']")
                    if content_div:
                        html = await content_div.inner_html()
                        md_text = md(html)
                        md_text = clean_img_alt(md_text)
                        markdown_content += f"# {tab_name}\n\n{md_text}\n\n"
                        html_content += f"<h1>{tab_name}</h1>\n{html}\n\n"
                    else:
                        markdown_content += f"# {tab_name}\n\n(내용 없음)\n\n"
                        html_content += f"<h1>{tab_name}</h1>\n(내용 없음)\n\n"
                except Exception as e:
                    logger.warning(f"⚠️ Tab '{tab_name}' click/extraction failed: {str(e)}")
                    markdown_content += f"# {tab_name}\n\n(탭 추출 실패)\n\n"
                    html_content += f"<h1>{tab_name}</h1>\n(탭 추출 실패)\n\n"
        else:
            # depth2Level이 없는 경우: 기본 콘텐츠만 추출
            content_div = await page.query_selector("div.fjbInnerTabBox[class*='fjbTabCon'][class~='on']")
            if not content_div:
                content_divs = await page.query_selector_all("div.fjbInnerTabBox[class*='fjbTabCon']")
                content_div = content_divs[0] if content_divs else None
            if content_div:
                html = await content_div.inner_html()
                md_text = md(html)
                md_text = clean_img_alt(md_text)
                markdown_content += f"# 기본 콘텐츠\n\n{md_text}\n\n"
                html_content += f"<h1>기본 콘텐츠</h1>\n{html}\n\n"
            else:
                markdown_content += f"# 기본 콘텐츠\n\n(내용 없음)\n\n"
                html_content += f"<h1>기본 콘텐츠</h1>\n(내용 없음)\n\n"
        
        await browser.close()

    logger.info(f"✅ Gigagenie detail page completed: {len(markdown_content)} chars")

    return {
        "url": url,
        "murl": to_gigagenie_murl(url),
        "markdown": markdown_content.strip(),
        "html": html_content.strip(),
        "special_processed": True,
        "playwright_processed": True
    }


async def handle_gigagenie_faq_playwright(url: str, fclient: Any) -> Dict[str, Any]:
    """
    기가지니 자주하는질문 전체 페이지 FAQ 추출
    - 상품별 버튼을 클릭하여 각 상품의 FAQ 추출
    - 페이지네이션 처리 (selectFaqList 함수 사용)
    """
    logger.info(f"Gigagenie FAQ processing started: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        status_code = response.status if response else None
        
        # 동적 로딩 대기: FAQ 목록이 로드될 때까지 대기
        try:
            await page.wait_for_selector('.faq-list, .board-list, tbody tr', timeout=15000)
            logger.info("✅ FAQ list loaded")
        except Exception as e:
            logger.warning(f"⚠️ FAQ list not loaded: {e}")
        await page.wait_for_timeout(2000)
        if status_code and status_code >= 400:
            logger.error(f"❌ Gigagenie FAQ ({url}): HTTP {status_code} error")
        
        try:
            await page.wait_for_selector("button[class*='fjbCard']", timeout=30000)
            logger.info("FAQ page loading completed")
        except Exception as e:
            logger.warning(f"⚠️ FAQ page loading wait failed: {e}")

        # 상품 버튼 목록 추출
        product_buttons = await page.query_selector_all("button[class*='fjbCard']")
        logger.info(f"🔍 Total {len(product_buttons)} product buttons found")
        
        all_qa_list = []
        
        for product_idx in range(len(product_buttons)):
            try:
                # 항상 최신 버튼 핸들로 재조회 (DOM 변경 대응)
                product_buttons = await page.query_selector_all("button[class*='fjbCard']")
                button = product_buttons[product_idx]
                
                # 상품명 추출
                product_name = await button.get_attribute("id-name")
                if not product_name:
                    product_name = await button.inner_text()
                    product_name = product_name.replace('\n', ' ').strip()
                
                logger.info(f"🔍 Product {product_idx + 1}/{len(product_buttons)} processing: {product_name}")
                
                # 상품 버튼 클릭
                await button.click()
                await page.wait_for_timeout(2000)
                
                # 페이지네이션 처리
                page_num = 1
                max_pages = 50
                seen_questions = set()
                
                while page_num <= max_pages:
                    # Q/A 추출
                    qa_items = await page.query_selector_all("ul#faqList li")
                    logger.info(f"  Page {page_num}: {len(qa_items)} FAQ items found")
                    
                    if not qa_items:
                        break
                    
                    for qa in qa_items:
                        try:
                            q_elem = await qa.query_selector("a.fjbQuestion")
                            if q_elem:
                                question = (await q_elem.inner_text()).strip()
                                
                                # 중복 체크
                                if question in seen_questions:
                                    continue
                                seen_questions.add(question)
                                
                                # 질문 클릭하여 답변 표시
                                await q_elem.click()
                                await page.wait_for_timeout(500)
                                
                                # 답변 추출
                                a_elem = await qa.query_selector("div.fjbAnser")
                                answer = ""
                                if a_elem:
                                    answer_html = await a_elem.inner_html()
                                    answer = md(answer_html).strip()
                                
                                all_qa_list.append({
                                    "product": product_name,
                                    "question": question,
                                    "answer": answer
                                })
                        except Exception as e:
                            logger.warning(f"⚠️ Q/A extraction failed: {e}")
                    
                    # 다음 페이지 확인 및 이동 (selectFaqList 함수 사용)
                    next_page_num = page_num + 1
                    try:
                        # 1. onclick에 selectFaqList가 있는 링크 찾기
                        next_page_selector = f"a[onclick*='selectFaqList({next_page_num})']"
                        next_page_link = await page.query_selector(next_page_selector)
                        
                        if next_page_link and await next_page_link.is_visible():
                            logger.info(f"  Navigating to page {next_page_num} (link click)")
                            await next_page_link.click()
                            await page.wait_for_timeout(3000)
                            page_num = next_page_num
                        else:
                            # 2. JavaScript 함수 직접 실행
                            try:
                                await page.evaluate(f"selectFaqList({next_page_num})")
                                await page.wait_for_timeout(3000)
                                
                                # 실제로 페이지가 변경되었는지 확인
                                new_qa_items = await page.query_selector_all("ul#faqList li")
                                if new_qa_items:
                                    logger.info(f"  Page {next_page_num} navigation successful (JS execution)")
                                    page_num = next_page_num
                                else:
                                    logger.info(f"  Page {next_page_num} not found. Moving to next product")
                                    break
                            except Exception as e:
                                logger.info(f"  Page {next_page_num} navigation failed: {str(e)}")
                                break
                    except Exception as e:
                        logger.info(f"  Pagination processing failed: {str(e)}")
                        break
                        
            except Exception as e:
                logger.warning(f"⚠️ Product FAQ processing failed: {e}")
        
        await browser.close()
    
    logger.info(f"✅ Gigagenie FAQ completed: {len(all_qa_list)} Q/A")
    
    # 결과 마크다운 생성
    markdown_content = "# 기가지니 자주하는질문\n\n"
    markdown_content += f"총 {len(all_qa_list)}개 FAQ\n\n---\n\n"
    
    html_content = f"<h1>기가지니 자주하는질문</h1>\n<p>총 {len(all_qa_list)}개 FAQ</p>\n<hr/>\n"
    
    current_product = ""
    for qa in all_qa_list:
        if qa["product"] != current_product:
            current_product = qa["product"]
            markdown_content += f"\n## {current_product}\n\n"
            html_content += f"<h2>{current_product}</h2>\n"
        
        markdown_content += f"### Q: {qa['question']}\n\n**A:** {qa['answer']}\n\n---\n\n"
        html_content += f"<h3>Q: {qa['question']}</h3>\n<p><strong>A:</strong> {qa['answer']}</p>\n<hr/>\n"
    
    # FAQ가 없는 경우 안내 메시지
    if not all_qa_list:
        markdown_content += "\n> FAQ를 추출하지 못했습니다. 페이지 구조가 변경되었을 수 있습니다.\n"
        html_content += "<p><em>FAQ를 추출하지 못했습니다.</em></p>\n"

    return {
        "url": url,
        "title": "기가지니 자주하는질문",
        "markdown": markdown_content.strip(),
        "html": html_content.strip(),
        "qa_list": all_qa_list,
        "qa_count": len(all_qa_list),
        "special_processed": True,
        "playwright_processed": True
    }


# 핸들러 등록
register_page_handler(
    r'https?://gigagenie\.kt\.com/whyGenieServiceDetail\.do\?serviceCate=.*',
    handle_gigagenie_detail
)

register_page_handler(
    r'https?://gigagenie\.kt\.com/whyGenieFaq\.do.*',
    handle_gigagenie_faq_playwright
)


async def handle_gigagenie_news_list(url: str, fclient: Any, menu: Optional[str] = None) -> Dict[str, Any]:
    """
    기가지니 지니소식 목록 Playwright 핸들러
    - "더보기" 버튼을 끝까지 클릭해 전체 게시물을 노출
    - 목록에서 seq, 제목을 추출해 상세 URL을 구성
    - 각 상세 페이지에서 제목, 날짜, 본문을 추출하여 Markdown/HTML 생성
    """
    import asyncio
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    
    logger.info(f"🔗 Gigagenie News List handler entered: url={url}, menu={menu}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        response = await page.goto(url, wait_until="domcontentloaded", timeout=40000)

        status_code = response.status if response else None
        
        # 동적 로딩 대기: 뉴스 목록이 로드될 때까지 대기
        try:
            await page.wait_for_selector('.news-list, .board-list, tbody tr', timeout=15000)
            logger.info("✅ News list loaded")
        except Exception as e:
            logger.warning(f"⚠️ News list not loaded: {e}")
        await page.wait_for_timeout(2000)
        if status_code:
            if status_code >= 400:
                logger.error(f"❌ Gigagenie News List ({url}): HTTP {status_code} error")
            elif status_code >= 300:
                logger.warning(f"⚠️ Gigagenie News List ({url}): HTTP {status_code} redirect")
            else:
                logger.info(f"✅ Gigagenie News List ({url}): HTTP {status_code} success")

        load_more_selector = "button#btn_more"
        try:
            while True:
                load_more_button = await page.query_selector(load_more_selector)
                if not load_more_button:
                    logger.info("Load More button not found, assuming all posts loaded")
                    break
                if not await load_more_button.is_visible():
                    logger.info("Load More button hidden, loading complete")
                    break
                if not await load_more_button.is_enabled():
                    logger.info("Load More button disabled, loading complete")
                    break
                try:
                    await load_more_button.click()
                except PlaywrightTimeoutError:
                    logger.warning("⚠️ Load More button click timeout, assuming loading complete")
                    break
                logger.info("Load More button clicked, waiting for additional posts")
                await page.wait_for_timeout(2000)
        except PlaywrightTimeoutError as timeout_err:
            logger.warning(f"⚠️ Load More button processing timeout: {str(timeout_err)}")
        except Exception as e:
            logger.warning(f"⚠️ Load More button processing error: {str(e)}")

        card_selector = "ul#bloglist li"
        try:
            await page.wait_for_selector(card_selector, timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning("⚠️ Gigagenie News cards not loaded within timeout")
        except Exception as wait_err:
            logger.warning(f"⚠️ Exception waiting for Gigagenie News cards: {wait_err}")
        cards = await page.query_selector_all(card_selector)
        logger.info(f"🔍 {len(cards)} Gigagenie News cards found")

        base_menu = menu or "지니소식"
        datas = []
        menus = []

        semaphore = asyncio.Semaphore(5)

        async def process_detail(detail_url: str, parent_menu: str, original_idx: int):
            async with semaphore:
                detail_page = await browser.new_page()

                try:
                    detail_response = await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=40000)

                    detail_status = detail_response.status if detail_response else None
                    
                    # 상세 페이지 콘텐츠 대기
                    try:
                        await detail_page.wait_for_selector('.content, .detail-content', timeout=10000)
                    except Exception:
                        pass
                    await detail_page.wait_for_timeout(2000)
                    if detail_status:
                        if detail_status >= 400:
                            logger.error(f"❌ Gigagenie News detail ({detail_url}): HTTP {detail_status} error")
                        elif detail_status >= 300:
                            logger.warning(f"⚠️ Gigagenie News detail ({detail_url}): HTTP {detail_status} redirect")
                        else:
                            logger.info(f"✅ Gigagenie News detail ({detail_url}): HTTP {detail_status} success")

                    title_selector = "h3.cfmOllehNewsTitle div.inner"
                    date_selector = "h3.cfmOllehNewsTitle div.inner span.date"

                    title_element = await detail_page.query_selector(title_selector)
                    raw_title = (await title_element.inner_text()) if title_element else ""
                    title_clean = re.sub(r"\s+", " ", raw_title).strip()

                    date_element = await detail_page.query_selector(date_selector)
                    raw_date = (await date_element.inner_text()) if date_element else ""
                    date_text = raw_date.strip()

                    startdate = "1900-01-01"
                    if date_text:
                        m = re.match(r"(\d{2})\.(\d{2})\.(\d{2})", date_text)
                        if m:
                            year = int(m.group(1))
                            year += 2000 if year < 70 else 1900
                            startdate = f"{year}-{m.group(2)}-{m.group(3)}"

                    content_selectors = [
                        "div.cfmOllehNewsCont",
                        "div.fjbNewsArea",
                        "div[style*='background']"
                    ]
                    inner_html = ""
                    for selector in content_selectors:
                        elem = await detail_page.query_selector(selector)
                        if elem:
                            inner_html = await elem.inner_html()
                            if inner_html and inner_html.strip():
                                break

                    if not inner_html:
                        logger.warning(f"⚠️ Main content not found: {detail_url}")

                    markdown_content = md(inner_html, heading_style="ATX") if inner_html else ""
                    html_content = inner_html or ""

                    # 파일명 안전 변환
                    title_for_menu = re.sub(r'[\\/*?:"<>|]', '', title_clean) if title_clean else "지니소식"
                    final_menu = f"{parent_menu}^{title_for_menu}" if parent_menu else title_for_menu

                    datas.append({
                        "url": detail_url,
                        "title": title_clean,
                        "date": date_text,
                        "startdate": startdate,
                        "markdown": markdown_content,
                        "html": html_content,
                        "status_code": detail_status,
                        "special_processed": True,
                        "playwright_processed": True,
                        "murl": to_gigagenie_murl(detail_url),
                        "original_index": original_idx
                    })

                    menus.append({
                        "menu": final_menu,
                        "url": detail_url,
                        "mobile_url": detail_url,
                        "murl": to_gigagenie_murl(detail_url),
                        "original_index": original_idx
                    })

                    logger.info(f"✅ Gigagenie News detail extracted: title='{title_clean}', startdate='{startdate}'")

                except Exception as detail_err:
                    logger.error(f"❌ Gigagenie News detail processing failed ({detail_url}): {str(detail_err)}")
                    datas.append({
                        "url": detail_url,
                        "title": "",
                        "date": "",
                        "startdate": "0000-00-00",
                        "markdown": "",
                        "html": "",
                        "error": str(detail_err),
                        "special_processed": True,
                        "playwright_processed": True,
                        "murl": to_gigagenie_murl(detail_url),
                        "original_index": original_idx
                    })
                    menus.append({
                        "menu": parent_menu,
                        "url": detail_url,
                        "mobile_url": detail_url,
                        "murl": to_gigagenie_murl(detail_url),
                        "original_index": original_idx
                    })
                finally:
                    await detail_page.close()

        for idx, card in enumerate(cards):
            try:
                thumbnail_link = await card.query_selector("a.thumbnail")
                if not thumbnail_link:
                    logger.warning("⚠️ Thumbnail link missing, skipping card")
                    continue

                onclick_attr = await thumbnail_link.get_attribute("onclick") or ""
                seq_match = re.search(r"goDetPage\((\d+)\)", onclick_attr)
                seq = seq_match.group(1) if seq_match else None

                if seq:
                    detail_url = f"https://gigagenie.kt.com/blog/detail.do?seq={seq}"
                else:
                    href_attr = await thumbnail_link.get_attribute("href") or ""
                    if href_attr.startswith("http"):
                        detail_url = href_attr
                    else:
                        detail_url = f"https://gigagenie.kt.com{href_attr}" if href_attr else ""

                if not detail_url:
                    logger.warning("⚠️ Cannot construct detail URL, skipping card")
                    continue

                await process_detail(detail_url, base_menu, idx)

            except Exception as card_err:
                logger.error(f"❌ Gigagenie News card processing failed: {str(card_err)}")
                continue
        await browser.close()

    logger.info(f"✅ Gigagenie News List completed: Total {len(datas)} posts")

    return {
        "menus": menus,
        "datas": datas,
        "total_processed": len(datas),
        "status": "completed",
        "message": f"총 {len(datas)}개 지니소식 게시물 처리 완료",
        "special_processed": True,
        "playwright_processed": True
    }


register_page_handler(
    r'https?://gigagenie\.kt\.com/whyGenieNews\.do',
    handle_gigagenie_news_list
)
