"""
FAQ 관련 핸들러

영화예매 고객센터 FAQ, ERMS FAQ 등
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler

logger = logging.getLogger(__name__)


def parse_movie_faq_from_html_content(html_content: str, category_name: str) -> List[Dict[str, str]]:
    """HTML 내용에서 FAQ 리스트를 파싱하여 반환"""
    try:
        faqs = []
        
        faq_pattern = r'<a href="#" class="inquiry"><em class="icon_q">Q 질문</em><span>([^<]+)</span></a>\s*<div class="answer">.*?<div class="answer-inner">\s*<p>(.*?)</p>'
        matches = re.findall(faq_pattern, html_content, re.DOTALL)
        
        for idx, (question, answer) in enumerate(matches):
            try:
                question = question.strip()
                answer = answer.strip()
                
                question = question.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                answer = answer.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                answer = answer.replace('<br/>', '\n').replace('<br>', '\n')
                
                if question and answer:
                    faqs.append({
                        "category": category_name,
                        "question": question,
                        "answer": answer
                    })
            except Exception:
                continue
        
        return faqs
        
    except Exception as e:
        logger.error(f"❌ HTML parse failed: {str(e)}")
        return []


async def handle_movie_customer_center_faq_playwright(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    영화예매 고객센터 FAQ 페이지 처리 핸들러
    """
    logger.info(f"🔗 Movie FAQ: {url}")
    
    categories = [
        {"id": "7", "name": "신규이용자"},
        {"id": "10", "name": "예매 관련"},
        {"id": "12", "name": "결제 관련"},
        {"id": "13", "name": "예매 취소"}
    ]
    
    all_qa_list = []
    page_markdown = ""
    page_html = ""
    
    # 기본 페이지 내용 추출
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # FAQ 콘텐츠 대기
            try:
                await page.wait_for_selector('.faq-list, .board-list, iframe', timeout=15000)
                logger.info("✅ FAQ page loaded")
            except Exception as e:
                logger.warning(f"⚠️ FAQ page not loaded: {e}")
            await page.wait_for_timeout(2000)
            
            iframe_element = await page.query_selector('#iFrmMileage')
            if iframe_element:
                frame = await iframe_element.content_frame()
                if frame:
                    content_element = await frame.query_selector('div.content-box')
                    if content_element:
                        faq_selectors = [
                            '.faq_box', '.faq', '.faq-list', '.faq-item', 
                            '.inquiry', '.answer', '.faqClass',
                            'header', 'footer', '.header', '.footer'
                        ]
                        
                        for selector in faq_selectors:
                            try:
                                elements = await content_element.query_selector_all(selector)
                                for element in elements:
                                    await element.evaluate('element => element.remove()')
                            except:
                                pass
                        
                        page_html = await content_element.inner_html()
                        page_markdown = md(page_html) if page_html else ""
            else:
                content_element = await page.query_selector('#cfmClContents')
                if content_element:
                    page_html = await content_element.inner_html()
                    page_markdown = md(page_html) if page_html else ""
            
            await browser.close()
        
    except Exception as e:
        logger.error(f"❌ Page content error: {e}")
    
    # FAQ 추출
    import aiohttp
    
    for category in categories:
        logger.info(f"🔍 Processing: {category['name']}")
        
        page_num = 1
        
        while True:
            category_url = f"https://showmovie.mobile.kt.com/Customer/FaqList.aspx?qIdx={category['id']}&Page={page_num}"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(category_url) as response:
                        if response.status == 200:
                            page_content = await response.text()
                        else:
                            break
                
                page_faqs = parse_movie_faq_from_html_content(page_content, category['name'])
                
                if not page_faqs:
                    break
                
                for faq in page_faqs:
                    faq['page'] = page_num
                    all_qa_list.append(faq)
                
                logger.info(f"  Page {page_num}: {len(page_faqs)} FAQs")
                
                if f'Page={page_num + 1}' in page_content:
                    page_num += 1
                else:
                    break
                    
            except Exception as e:
                logger.error(f"❌ Category failed: {category['name']}: {str(e)}")
                break
    
    logger.info(f"✅ Movie FAQ done: {len(all_qa_list)} FAQs")
    
    # qa_list를 마크다운으로 변환
    faq_markdown = "# 영화예매 고객센터 FAQ\n\n"
    faq_markdown += f"총 {len(all_qa_list)}개 FAQ\n\n---\n\n"
    
    current_category = ""
    for qa in all_qa_list:
        category = qa.get("category", "기타")
        if category != current_category:
            current_category = category
            faq_markdown += f"## {category}\n\n"
        
        question = qa.get("question", "")
        answer = qa.get("answer", "")
        faq_markdown += f"### Q: {question}\n\n"
        faq_markdown += f"**A:** {answer}\n\n---\n\n"
    
    # 최종 마크다운
    final_markdown = faq_markdown
    if page_markdown and page_markdown.strip():
        final_markdown += "\n\n---\n\n# 페이지 기본 정보\n\n" + page_markdown
    
    return {
        "url": url,
        "title": "영화예매 고객센터 FAQ",
        "markdown": final_markdown,
        "html": page_html,
        "qa_list": all_qa_list,
        "total_categories": len(categories),
        "total_qa": len(all_qa_list),
        "special_processed": True,
        "playwright_processed": True
    }


async def handle_ermsweb_faq_all_playwright(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    ERMS FAQ 페이지 처리 핸들러
    """
    logger.info(f"🔗 ERMS FAQ: {url}")
    
    max_retries = 2
    base_timeout = 60000
    
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                wait_until = "domcontentloaded"
                timeout = 50000
                extra_wait = 5000
            else:
                wait_until = "networkidle"
                timeout = base_timeout
                extra_wait = 8000
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)
                await page.wait_for_timeout(extra_wait)
                
                status_code = response.status if response else None
                if status_code and status_code >= 400:
                    logger.error(f"❌ HTTP {status_code}: {url}")
                
                try:
                    await page.wait_for_selector("ul#tab-slide-menu li a", timeout=30000)
                except Exception:
                    logger.warning("⚠️ Page load wait failed")

                markdown_body = ""
                all_qa_list = []
                page_html = ""
                
                # 기본 페이지 내용 추출
                try:
                    faq_selectors = [
                        'ul#faqList', '.faqList', '.accordion-area', '.accordion',
                        '.faq_box', '.faq', '.faq-list', '.faq-item',
                        'ul.accordions', 'header', 'footer', '#header', '#footer'
                    ]
                    
                    for selector in faq_selectors:
                        try:
                            elements = await page.query_selector_all(selector)
                            for element in elements:
                                await element.evaluate('element => element.remove()')
                        except:
                            pass
                    
                    page_html = await page.content()
                    page_markdown = md(page_html) if page_html else ""
                except Exception as e:
                    logger.error(f"❌ Page content error: {e}")
                    page_markdown = ""
                    page_html = ""
                
                # FAQ 추출을 위해 페이지 새로고침
                await page.reload()
                await page.wait_for_timeout(3000)

                # 카테고리 추출
                categories = await page.query_selector_all("ul#tab-slide-menu li a")
                category_info = []
                for a in categories:
                    nodeid = await a.get_attribute("data-nodeid")
                    nodename = await a.get_attribute("data-nodename") or (await a.inner_text()).replace('\n', ' ').strip()
                    category_info.append({"nodeid": nodeid, "nodename": nodename, "element": a})
                
                logger.info(f"🔍 Found {len(category_info)} categories")

                for cat_idx, cat in enumerate(category_info):
                    await cat["element"].click()
                    await page.wait_for_timeout(1500)
                    faq_category = cat["nodename"]

                    last_page = 1
                    page_links = await page.query_selector_all('.pagination .scope a')
                    for a in page_links:
                        txt = (await a.inner_text()).strip()
                        if txt.isdigit():
                            last_page = max(last_page, int(txt))
                        if 'last' in (await a.get_attribute('class') or ''):
                            href = await a.get_attribute('href')
                            m = re.search(r'gotoAjax\((\d+),', href or '')
                            if m:
                                last_page = max(last_page, int(m.group(1)))

                    for page_num in range(1, last_page + 1):
                        if page_num > 1:
                            page_btns = await page.query_selector_all('.pagination .scope a')
                            for btn in page_btns:
                                if (await btn.inner_text()).strip() == str(page_num):
                                    await btn.click()
                                    await page.wait_for_timeout(1500)
                                    break

                        faq_items = await page.query_selector_all('ul.accordions > li.liWrap')
                        for li in faq_items:
                            try:
                                category_elem = await li.query_selector('.linked')
                                category = await category_elem.inner_text() if category_elem else ""
                                question_elem = await li.query_selector('.qna span')
                                if question_elem:
                                    question = await question_elem.inner_text()
                                else:
                                    qna_elem = await li.query_selector('.qna')
                                    question = await qna_elem.inner_text() if qna_elem else ""
                                trigger = await li.query_selector('.accordion-trigger')
                                answerDiv = await li.query_selector('.accordion-contents')
                                if answerDiv and (await answerDiv.evaluate('el => getComputedStyle(el).display')) == 'none':
                                    if trigger:
                                        await trigger.click()
                                        await page.wait_for_timeout(500)
                                answer_elem = await li.query_selector('.accordion-contents .faqClass')
                                answer = await answer_elem.inner_text() if answer_elem else ""
                                
                                markdown_body += f"{category}\n{question}\n{answer}\n***\n"
                                all_qa_list.append({
                                    "category": category,
                                    "question": question,
                                    "answer": answer,
                                    "page": page_num
                                })
                            except Exception:
                                continue

                await browser.close()
                
                logger.info(f"✅ ERMS FAQ done: {len(all_qa_list)} FAQs")
                
                # qa_list를 마크다운으로 변환
                faq_markdown = "# ERMS FAQ\n\n"
                faq_markdown += f"총 {len(all_qa_list)}개 FAQ\n\n---\n\n"
                
                current_category = ""
                for qa in all_qa_list:
                    category = qa.get("category", "기타")
                    if category != current_category:
                        current_category = category
                        faq_markdown += f"## {category}\n\n"
                    
                    question = qa.get("question", "")
                    answer = qa.get("answer", "")
                    faq_markdown += f"### Q: {question}\n\n"
                    faq_markdown += f"**A:** {answer}\n\n---\n\n"
                
                # 최종 마크다운
                final_markdown = faq_markdown
                if page_markdown and page_markdown.strip():
                    final_markdown += "\n\n---\n\n# 페이지 기본 정보\n\n" + page_markdown
                
                return {
                    "url": url,
                    "title": "ERMS FAQ",
                    "markdown": final_markdown,
                    "html": page_html,
                    "qa_list": all_qa_list,
                    "total_categories": len(category_info),
                    "total_qa": len(all_qa_list),
                    "special_processed": True,
                    "playwright_processed": True
                }
                
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(5)
                continue
            else:
                logger.error(f"❌ ERMS FAQ failed: {str(e)}")
                return {
                    "markdown": f"ERMS FAQ 처리 실패: {str(e)}",
                    "html": "",
                    "qa_list": [],
                    "total_categories": 0,
                    "total_qa": 0,
                    "special_processed": True,
                    "playwright_processed": True,
                    "error": str(e)
                }


# 핸들러 등록
register_page_handler(
    r'https?://membership\.kt\.com/culture/movie/CustomerCenterInfo\.do',
    handle_movie_customer_center_faq_playwright
)

register_page_handler(
    r'https?://ermsweb\.kt\.com/pc/faq/faqList\.do',
    handle_ermsweb_faq_all_playwright
)


