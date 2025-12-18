"""
멤버십 관련 핸들러

KT 멤버십 제휴 브랜드 목록 및 FAQ 처리
"""

import logging
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler

logger = logging.getLogger(__name__)


async def handle_membership_partner_list_playwright(url: str, fclient: Any, menu: Optional[str] = None) -> Dict[str, Any]:
    """
    Playwright(로컬)로 KT 멤버십 제휴 브랜드 목록 페이지에서 모든 브랜드 정보를 추출하는 핸들러
    - 더보기 버튼이 display: none 될 때까지 반복 클릭
    - #cfmClContents 영역만 추출하여 마크다운으로 변환
    """
    logger.info(f"🔗 Partner list: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        
        # HTTP 상태 코드 확인
        status_code = response.status if response else None

        # 더보기 버튼이 display:none 될 때까지 반복 클릭
        for _ in range(50):
            try:
                display = await page.eval_on_selector(
                    "#btnMoreData",
                    "el => window.getComputedStyle(el).display"
                )
                if display == "none":
                    break
                btn = await page.query_selector("#btnMoreData button.btn.view-more")
                if btn and await btn.is_enabled() and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(700)
                else:
                    break
            except Exception:
                break

        # #cfmClContents 영역만 추출
        content_html = await page.eval_on_selector("#cfmClContents", "el => el.outerHTML")
        await browser.close()

    # HTML을 마크다운으로 변환
    markdown_body = md(content_html or "(콘텐츠 없음)")

    logger.info(f"✅ Partner list done: {len(markdown_body)} chars")
    
    return {
        "url": url,
        "title": "KT 멤버십 제휴 브랜드 목록",
        "markdown": markdown_body,
        "html": content_html,
        "status_code": status_code,
        "special_processed": True,
        "playwright_processed": True
    }


# 핸들러 등록
register_page_handler(
    r'https?://membership\.kt\.com/discount/partner/PartnerList\.do',
    handle_membership_partner_list_playwright
)


async def handle_membership_faq_all_playwright(url: str, fclient: Any, menu: Optional[str] = None) -> Dict[str, Any]:
    """
    KT 멤버십 FAQ 페이지에서 iframe을 통해 모든 FAQ Q/A를 추출하는 handler
    메인 페이지 -> iframe 접근 -> FAQ 데이터 추출
    """
    logger.info(f"🔗 Membership FAQ: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logger.error(f"❌ HTTP {status_code}: {url}")
            elif status_code >= 300:
                logger.warning(f"⚠️ HTTP {status_code} redirect: {url}")
            else:
                logger.info(f"✅ HTTP {status_code}: {url}")
        else:
            logger.debug(f"🔍 No status code: {url}")

        markdown_body = ""
        all_qa_list = []
        seen_questions = set()  # 중복 제거를 위한 질문 추적
        
        # 기본 페이지 내용 추출 (FAQ 제외) - Playwright 사용
        try:
            logger.info("🔍 Extracting page content")
            
            # FAQ 관련 요소들 및 불필요한 요소 제거
            faq_selectors = [
                # FAQ 관련
                'ul#faqList', '.faqList', 
                '.accordion-area', '.accordion',
                '.faq_box', '.faq', '.faq-list', '.faq-item', 
                '.inquiry', '.answer', '.faqClass',
                'img[src*="faq"]', 'img[src*="FAQ"]',
                'a[href*="faq"]', 'a[href*="FAQ"]',
                'iframe#cpEvent',  # FAQ iframe도 제거
                # Header/Footer/Navigation
                'header', 'footer', 
                '.header', '.footer',
                '#header', '#footer',
                '#cfmClHeader', '#cfmClFooter',
                '.inner', 'nav', '.navigation'
            ]
            
            for selector in faq_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        await element.evaluate('element => element.remove()')
                except:
                    pass  # 셀렉터가 유효하지 않을 수 있음
            
            page_html = await page.content()
            page_markdown = md(page_html) if page_html else ""
            logger.info(f"✅ Page content: {len(page_markdown)} markdown, {len(page_html)} HTML")
        except Exception as e:
            logger.error(f"❌ Page content error: {e}")
            page_markdown = ""
            page_html = ""
        
        # FAQ 추출을 위해 페이지 새로고침
        await page.reload()
        await page.wait_for_timeout(3000)

        # iframe 찾기 및 접근
        iframe_selector = "iframe#cpEvent"
        iframe_element = await page.query_selector(iframe_selector)
        
        if not iframe_element:
            logger.error("❌ FAQ iframe not found")
            await browser.close()
            return {
                "url": url,
                "markdown": "",
                "qa_list": [],
                "total_categories": 0,
                "total_qa": 0,
                "special_processed": True,
                "playwright_processed": True,
                "error": "iframe을 찾을 수 없음"
            }

        # iframe의 실제 src 확인
        iframe_src = await iframe_element.get_attribute("src")
        logger.info(f"발견된 iframe src: {iframe_src}")

        # iframe의 frame 객체 가져오기
        frame = await iframe_element.content_frame()
        if not frame:
            logger.error("❌ Cannot access iframe frame")
            await browser.close()
            return {
                "url": url,
                "markdown": "",
                "qa_list": [],
                "total_categories": 0,
                "total_qa": 0,
                "special_processed": True,
                "playwright_processed": True,
                "error": "iframe frame에 접근할 수 없음"
            }
        
        # iframe 내용이 완전히 로드될 때까지 대기
        try:
            await frame.wait_for_load_state('domcontentloaded', timeout=30000)
            await frame.wait_for_load_state('networkidle', timeout=30000)
            logger.info("✅ iframe loaded")
        except Exception as e:
            logger.warning(f"⚠️ iframe load timeout: {str(e)}")
            # 계속 진행

        logger.info("🔍 Extracting FAQ data")
        await page.wait_for_timeout(5000)  # iframe 로딩 대기 시간 증가

        await frame.wait_for_timeout(2000)  # 페이지 로딩 대기

        # 페이지네이션을 통한 모든 페이지 처리
        page_num = 1
        max_pages = 100  # 충분한 최대 페이지 제한
        visited_first_questions = set()  # 순환 감지를 위한 첫 번째 질문 추적
        
        while page_num <= max_pages:
            logger.info(f"🔍 Page {page_num}...")
            
            # 현재 페이지의 accordion FAQ 항목들 추출 (iframe 내에서)
            accordion_triggers = await frame.query_selector_all('.accordion-trigger')
            
            logger.info(f"🔍 Page {page_num}: {len(accordion_triggers)} FAQ items")
            
            if not accordion_triggers:
                logger.info("🔍 No more FAQ items")
                break
            
            # 순환 감지: 첫 번째 질문으로 이미 방문한 페이지인지 확인
            try:
                first_trigger = accordion_triggers[0]
                first_question_element = await first_trigger.query_selector('.qna span')
                if first_question_element:
                    first_question = await first_question_element.inner_text()
                    if first_question.strip() in visited_first_questions:
                        logger.info(f"⚠️ Loop detected: '{first_question[:50]}...'")
                        break
                    visited_first_questions.add(first_question.strip())
            except Exception as e:
                logger.warning(f"⚠️ Loop detection error: {str(e)}")
            
            # 각 accordion FAQ 항목 처리
            for idx, trigger in enumerate(accordion_triggers):
                try:
                    # 카테고리 추출 (.linked 클래스)
                    category_element = await trigger.query_selector('.linked')
                    category = await category_element.inner_text() if category_element else "기타"
                    
                    # 질문 추출 (.qna span)
                    question_element = await trigger.query_selector('.qna span')
                    question = await question_element.inner_text() if question_element else ""
                        
                    # 답변 추출 (accordion 클릭 필요)
                    answer = ""
                    try:
                        # accordion을 클릭하여 답변 로드
                        await trigger.click()
                        await frame.wait_for_timeout(1000)  # 답변 로딩 대기
                        
                        # 해당하는 답변 요소 찾기
                        answer_id = f"accordionsAnswer-{idx}"
                        answer_element = await frame.query_selector(f'#{answer_id}')
                        
                        if answer_element:
                            answer = await answer_element.inner_text()
                            answer = answer.strip()
                        
                    except Exception as e:
                        logger.warning(f"⚠️ FAQ answer failed: {str(e)}")
                    
                    # 중복 체크 후 유효한 Q/A만 추가
                    if question.strip() and question.strip() not in seen_questions:
                        seen_questions.add(question.strip())  # 중복 방지를 위해 추가
                        
                        # 구조화된 데이터로만 추가 (마크다운 제거)
                        all_qa_list.append({
                            "category": category,
                            "question": question.strip(),
                            "answer": answer.strip(),
                            "page": page_num
                        })
                        
                        logger.info(f"✅ Page {page_num} FAQ {idx + 1}: {question[:50]}...")
                    elif question.strip():
                        logger.info(f"⚠️ Page {page_num} duplicate: {question[:50]}...")
                    else:
                        logger.warning(f"⚠️ Page {page_num} FAQ {idx + 1} empty")
                        
                except Exception as e:
                    logger.error(f"❌ FAQ {idx + 1} failed: {str(e)}")
                    continue
            
            # 다음 페이지로 이동 시도 (동적 페이지네이션)
            try:
                logger.info("🔍 Finding next page...")
                
                # 현재 페이지의 첫 번째 질문을 기억 (이동 확인용)
                current_first_question = ""
                try:
                    first_trigger = await frame.query_selector('.accordion-trigger .qna span')
                    if first_trigger:
                        current_first_question = await first_trigger.inner_text()
                except:
                    pass
                
                # 페이지네이션 영역에서 모든 링크 확인
                pagination_links = await frame.query_selector_all('a')
                
                next_link = None
                
                # 현재 페이지 번호 파악 및 다음 페이지 찾기
                current_page_num = page_num  # 현재 페이지 번호 (카운터)
                next_page_num = current_page_num + 1
                
                # 현재 페이지와 다음 페이지 링크 찾기
                for link in pagination_links:
                    try:
                        link_text = (await link.inner_text()).strip()
                        if link_text.isdigit():
                            page_number = int(link_text)
                            # 현재 페이지보다 큰 첫 번째 페이지 번호 찾기
                            if page_number > current_page_num and await link.is_enabled() and await link.is_visible():
                                next_link = link
                                logger.info(f"🔗 Next page: '{link_text}' (current: {current_page_num})")
                                break
                    except Exception as e:
                        continue
                
                # 숫자 페이지가 없으면 >> (10페이지 이동) 또는 >>| (끝으로) 찾기
                if not next_link:
                    for link in pagination_links:
                        try:
                            link_text = (await link.inner_text()).strip()
                            if link_text in ['>>', '>>|', '다음', 'Next'] and await link.is_enabled():
                                next_link = link
                                logger.info(f"🔗 Navigation link: '{link_text}'")
                                break
                        except Exception as e:
                            continue
                
                if next_link:
                    logger.info("🔍 Navigating...")
                    await next_link.click()
                    await frame.wait_for_timeout(4000)  # 충분한 대기 시간
                    
                    # 페이지 이동 확인
                    page_changed = False
                    try:
                        new_first_trigger = await frame.query_selector('.accordion-trigger .qna span')
                        if new_first_trigger:
                            new_first_question = await new_first_trigger.inner_text()
                            if new_first_question != current_first_question:
                                page_changed = True
                                logger.info(f"✅ Page changed: '{current_first_question[:30]}...' → '{new_first_question[:30]}...'")
                    except:
                        pass
                    
                    if not page_changed:
                        logger.warning("⚠️ Navigation failed - same content")
                        break
                    
                    await frame.wait_for_timeout(1000)
                    
                    page_num += 1  # 페이지 번호는 단순히 카운터로만 사용
                else:
                    logger.info("🔍 No more pages")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Navigation error: {str(e)}")
                break

        await browser.close()
        
        logger.info(f"✅ FAQ done: {len(all_qa_list)} FAQs")
        logger.info(f"✅ qa_list ready: {len(all_qa_list)} FAQs")

    # qa_list를 마크다운으로 변환
    faq_markdown = "# KT 멤버십 FAQ\n\n"
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
    
    # 최종 마크다운: FAQ 마크다운 + 페이지 기본 내용
    final_markdown = faq_markdown
    if page_markdown and page_markdown.strip():
        final_markdown += "\n\n---\n\n# 페이지 기본 정보\n\n" + page_markdown

    return {
        "url": url,
        "title": "KT 멤버십 FAQ",
        "markdown": final_markdown,  # FAQ를 포함한 마크다운
        "html": page_html,
        "qa_list": all_qa_list,
        "total_categories": 1,
        "total_qa": len(all_qa_list),
        "special_processed": True,
        "playwright_processed": True
    }


# FAQ 핸들러 등록
register_page_handler(
    r'https?://membership\.kt\.com/guide/faq/FAQList\.do',
    handle_membership_faq_all_playwright
)
