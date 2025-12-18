import logging
import re
import asyncio
import os
from typing import Dict, Any, List, Callable, Pattern, Tuple, Optional, Awaitable, Set
from urllib.parse import urlparse, unquote
import html
from bs4 import BeautifulSoup, NavigableString
from playwright.async_api import async_playwright, TimeoutError as AsyncTimeoutError
from markdownify import markdownify as md
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

 

# 글로벌 타임스탬프 변수 (preview.py에서 설정)
CURRENT_TIMESTAMP = None

def set_current_timestamp(timestamp_str):
    """preview.py에서 호출하여 타임스탬프 설정"""
    global CURRENT_TIMESTAMP
    # None이 아닌 값만 설정 (None은 초기화 목적이므로 실제로는 기존값 유지)
    if timestamp_str is not None:
        CURRENT_TIMESTAMP = timestamp_str
    else:
        CURRENT_TIMESTAMP = None

def get_current_timestamp():
    """현재 타임스탬프 반환 (없으면 새로 생성)"""
    from datetime import datetime
    global CURRENT_TIMESTAMP
    if CURRENT_TIMESTAMP is None:
        CURRENT_TIMESTAMP = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        logging.info(f"🕐 새로운 타임스탬프 생성: {CURRENT_TIMESTAMP}")
    else:
        # logging.info(f"🕐 기존 타임스탬프 사용: {CURRENT_TIMESTAMP}")
        pass
    return CURRENT_TIMESTAMP

# 페이지별 처리 함수 타입 힌트
PageHandlerFunc = Callable[[str, Any], Dict[str, Any]]
AsyncPageHandlerFunc = Callable[[str, Any], Awaitable[Dict[str, Any]]]

# URL 패턴과 핸들러 함수를 매핑하는 글로벌 레지스트리
URL_PATTERNS = []  # (컴파일된 정규식 패턴, 핸들러 함수) 튜플 목록

# =========================
# 1. 공용 유틸리티 함수
# =========================
def sanitize_filename(filename, max_length=100):
    """
    파일명을 안전하고 가독성 있게 변환
    
    Args:
        filename: 원본 파일명
        max_length: 최대 길이 (기본값: 100)
    
    Returns:
        str: 변환된 안전한 파일명
    """
    # 1. 카테고리 태그 처리: [공지] → (공지)
    sanitized = re.sub(r'\[([^]]+)\]', r'(\1)', filename)
    
    # 2. 시간 표기 개선: 03/12(수) 01:00 ~ 08:00 → 0312수(0100-0800)
    # 날짜/시간 패턴 찾기
    datetime_pattern = r'(\d{1,2})/(\d{1,2})\(([^)]+)\)\s*(\d{1,2}):(\d{2})\s*~\s*(\d{1,2}):(\d{2})'
    datetime_match = re.search(datetime_pattern, sanitized)
    if datetime_match:
        month, day, weekday, start_hour, start_min, end_hour, end_min = datetime_match.groups()
        time_str = f"{month.zfill(2)}{day.zfill(2)}{weekday}({start_hour.zfill(2)}{start_min}-{end_hour.zfill(2)}{end_min})"
        sanitized = re.sub(datetime_pattern, time_str, sanitized)
    
    # 3. 기타 시간 패턴들 처리
    # HH:MM 형식 → HHMM
    sanitized = re.sub(r'(\d{1,2}):(\d{2})', r'\1\2', sanitized)
    
    # MM/DD 형식 → MMDD
    sanitized = re.sub(r'(\d{1,2})/(\d{1,2})', r'\1\2', sanitized)
    
    # 4. 특수문자를 의미 있게 변환
    # ~ (물결표) → to
    sanitized = re.sub(r'\s*~\s*', 'to', sanitized)
    
    # 연속된 공백을 하나로
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # 5. 길이 제한
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # 6. 파일명으로 사용할 수 없는 문자 제거
    sanitized = re.sub(r'[<>:"/\\|?*]', '', sanitized)
    
    return sanitized.strip()


def to_mshop_url(url: str) -> str:
    """KT Shop PC URL을 모바일(https://m.shop.kt.com:444) 형태로 변환"""
    if not url or not url.startswith('http'):
        return ''
    return url.replace('https://shop.kt.com', 'https://m.shop.kt.com:444/m')

def to_mglobalroaming_url(url: str) -> str:
    """글로벌로밍 PC URL을 모바일(https://m.globalroaming.kt.com) 형태로 변환"""
    if not url or not url.startswith('http'):
        return ''

    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    mobile_netloc = parsed.netloc.replace('globalroaming.kt.com', 'm.globalroaming.kt.com')

    if parsed.path.startswith('/news/view.asp'):
        idx_val = query_params.get('idx', [''])[0]
        mobile_path = '/news/view.asp'
        mobile_query = urlencode({'idx': idx_val})
        return urlunparse((parsed.scheme, mobile_netloc, mobile_path, '', mobile_query, ''))

    return urlunparse((parsed.scheme, mobile_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

def to_gigagenie_murl(url: str) -> str:
    """기가지니 블로그 PC URL을 모바일(https://gigagenie.kt.com/m/blog) 형태로 변환"""
    if not url or not url.startswith('http'):
        return ''
    return url.replace('https://gigagenie.kt.com/blog/', 'https://gigagenie.kt.com/m/blog/')

def format_date_show(date_str):
    """공연예매 날짜 형식 변환"""
    if not date_str:
        return ""
    
    # 기존 패턴들
    patterns = [
        (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', r'\1-\2-\3'),
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', r'\1-\2-\3'),
        (r'(\d{1,2})/(\d{1,2})/(\d{4})', r'\3-\1-\2'),
    ]
    
    for pattern, replacement in patterns:
        match = re.search(pattern, date_str)
        if match:
            return re.sub(pattern, replacement, date_str)
    
    return date_str

def format_content(content):
    """콘텐츠 포맷팅"""
    if not content:
        return ""
    
    # 불필요한 공백 제거
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    content = re.sub(r'^\s+|\s+$', '', content, flags=re.MULTILINE)
    
    return content

def create_markdown(title, date, content):
    """마크다운 문서 생성"""
    return f"""# {title}

**날짜:** {date}

---

{content}
"""

async def get_page_status_code(page):
    """페이지의 HTTP 상태 코드를 가져오는 유틸리티 함수"""
    try:
        # Playwright에서 응답 객체를 통해 상태 코드 확인
        response = page.url
        # 현재 페이지의 응답 정보 확인
        if hasattr(page, '_response') and page._response:
            return page._response.status
        return None
    except Exception:
        return None

# =========================
# 2. 핸들러 등록 및 라우팅
# =========================
def register_page_handler(url_pattern: str, handler_func: AsyncPageHandlerFunc):
    """
    URL 패턴과 핸들러 함수를 등록
    
    Args:
        url_pattern: 정규식 패턴
        handler_func: 핸들러 함수 (비동기)
    """
    compiled_pattern = re.compile(url_pattern)
    URL_PATTERNS.append((compiled_pattern, handler_func))

def get_registered_handlers():
    """등록된 핸들러 목록 반환"""
    return [(pattern.pattern, func.__name__) for pattern, func in URL_PATTERNS]

async def route_url(url: str, fclient, menu: str = None) -> Optional[Dict[str, Any]]:
    """
    URL에 맞는 핸들러를 찾아서 실행
    
    Args:
        url: 처리할 URL
        fclient: 스크래핑 클라이언트
        menu: 메뉴 정보
        
    Returns:
        Optional[Dict[str, Any]]: 핸들러 결과 또는 빈 딕셔너리 (기본 스크래핑용)
    """
    for pattern, handler_func in URL_PATTERNS:
        if pattern.match(url):
            try:
                # handle_gigagenie_faq_playwright는 2개 인자만 받음
                if handler_func.__name__ == "handle_gigagenie_faq_playwright":
                    result = await handler_func(url, fclient)
                else:
                    result = await handler_func(url, fclient, menu)
                return result
            except Exception as e:
                logging.error(f"❌ 핸들러 실행 중 오류: {handler_func.__name__} - {str(e)}")
                return None
    
    # 핸들러가 없는 경우 None 반환 (기본 스크래핑 실행을 위해)
    logging.info(f"🔍 URL에 맞는 핸들러가 없어 기본 스크래핑을 실행합니다: {url}")
    return None


async def handle_membership_partner_list_playwright(url: str, fclient, menu=None) -> dict:
    """
    Playwright(로컬)로 KT 멤버십 제휴 브랜드 목록 페이지에서 모든 브랜드 정보를 추출하는 핸들러
    - 더보기 버튼이 display: none 될 때까지 반복 클릭
    - #cfmClContents 영역만 추출하여 마크다운으로 변환
    """


    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # HTTP 상태 코드 확인
        status_code = response.status if response else None

        # 더보기 버튼이 display:none 될 때까지 반복 클릭
        for _ in range(50):  # 안전하게 최대 30회 제한
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
    markdown = markdown_body

    return {
        "url": url,
        "title": "KT 멤버십 제휴 브랜드 목록",
        "markdown": markdown,
        "html": content_html,
        "status_code": status_code,
        "special_processed": True,
        "playwright_processed": True
    }

register_page_handler(
    r'https?://membership\.kt\.com/discount/partner/PartnerList\.do',
    handle_membership_partner_list_playwright
)


# =========================
# 3. 공연예매 관련 핸들러
# =========================
async def handle_interpark_notice_main(url: str, fclient, menu=None) -> dict:
    from datetime import datetime, timedelta
    import re
    logging.info(f"공연예매 공지사항 메인 페이지 처리 시작: {url}")
    cutoff_date = datetime.now() - timedelta(days=365)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded')
        await page.wait_for_timeout(2000)
        
        # HTTP 상태 코드 확인
        status_code = response.status if response else None
        notice_data = await page.evaluate(r"""() => {
            const notices = [];
            
            // 방법 1: 기존 방식 (table.board.dir-vertical)
            let table = document.querySelector('table.board.dir-vertical');
            
            // 방법 2: 일반적인 테이블 찾기
            if (!table) {
                const tables = document.querySelectorAll('table');
                for (let t of tables) {
                    // NoticeView 링크가 있는 테이블 찾기
                    if (t.querySelector('a[href*="NoticeView"]')) {
                        table = t;
                        break;
                    }
                }
            }
            
            // 방법 3: NoticeView 링크들을 직접 찾기
            if (!table) {
                const links = document.querySelectorAll('a[href*="NoticeView"]');
                links.forEach((link, index) => {
                    // 링크 주변에서 날짜 정보 찾기
                    let dateText = '';
                    let numberText = (index + 1).toString();
                    let viewsText = '';
                    
                    // 부모 행에서 날짜 찾기
                    const row = link.closest('tr');
                    if (row) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            numberText = cells[0] ? cells[0].textContent.trim() : numberText;
                            dateText = cells[2] ? cells[2].textContent.trim() : '';
                            viewsText = cells[3] ? cells[3].textContent.trim() : '';
                        }
                    }
                    
                    // 날짜 패턴으로 유효성 검증
                    if (!dateText || !/\d{4}[.\-]\d{1,2}[.\-]\d{1,2}/.test(dateText)) {
                        // 링크 주변 텍스트에서 날짜 찾기
                        const parentText = link.parentElement ? link.parentElement.textContent : '';
                        const dateMatch = parentText.match(/(\d{4}[.\-]\d{1,2}[.\-]\d{1,2})/);
                        if (dateMatch) {
                            dateText = dateMatch[1];
                        } else {
                            dateText = new Date().toISOString().split('T')[0]; // fallback
                        }
                    }
                    
                    notices.push({
                        number: numberText,
                        title: link.textContent.trim(),
                        date: dateText,
                        views: viewsText,
                        relativeHref: link.getAttribute('href'),
                        fullHref: link.href
                    });
                });
                
                return { notices: notices, method: 'direct_links' };
            }
            
            // 테이블이 있는 경우의 처리
            const rows = table.querySelectorAll('tr:not(:first-child)'); // 헤더 제외
            
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 3) {
                    // 두 번째 셀에서 링크 찾기
                    let link = cells[1] ? cells[1].querySelector('a[href*="NoticeView"]') : null;
                    
                    // 다른 셀에서도 링크 찾기
                    if (!link) {
                        for (let cell of cells) {
                            link = cell.querySelector('a[href*="NoticeView"]');
                            if (link) break;
                        }
                    }
                    
                    if (link) {
                        notices.push({
                            number: cells[0] ? cells[0].textContent.trim() : '',
                            title: link.textContent.trim(),
                            date: cells[2] ? cells[2].textContent.trim() : '',
                            views: cells[3] ? cells[3].textContent.trim() : '',
                            relativeHref: link.getAttribute('href'),
                            fullHref: link.href
                        });
                    }
                }
            });
            
            return { notices: notices, method: 'table', tableFound: !!table };
        }""")
        await browser.close()
    notices = notice_data.get('notices', [])
    method = notice_data.get('method', 'unknown')
    table_found = notice_data.get('tableFound', False)
    if not notices:
        logging.warning("인터파크 공지사항을 찾을 수 없습니다")
        return {"message": "인터파크 공지사항이 없습니다", "total_processed": 0}
    logging.info(f"총 {len(notices)}개 인터파크 공지사항 발견 (추출방식: {method})")
    menus, datas = [], []
    total_processed = 0
    for notice in notices:
        try:
            date_str = notice['date']
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_str)
            if date_match:
                year, month, day = map(int, date_match.groups())
                post_date = datetime(year, month, day)
                if post_date < cutoff_date:
                    logging.info(f"게시물 '{notice['title'][:30]}...' 날짜({post_date.strftime('%Y-%m-%d')})가 기준일 이전입니다")
                    break
            logging.info(f"[{total_processed+1}/{len(notices)}] 처리 중: {notice['title'][:50]}...")
            result = await handle_show_notice(notice['fullHref'], fclient)
            if "error" in result:
                logging.warning(f"게시물 처리 실패: {result['error']}")
                continue
            # 폴더명 생성
            formatted_date = ''
            if result.get('date'):
                date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                if date_match:
                    formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            title_clean = sanitize_filename(result.get('title', 'unknown'))
            last_folder = f"({formatted_date}){title_clean}" if formatted_date else title_clean
            menus.append({'menu': f"{menu}^{last_folder}" if menu else last_folder, 'url': notice['fullHref']})
            datas.append(result)
            total_processed += 1
            logging.info(f"처리 완료: {total_processed}개")
        except Exception as e:
            logging.error(f"게시물 처리 중 오류: {str(e)}")
            continue
    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 공지사항 처리 완료",
        "status_code": status_code
    }

register_page_handler(
    r'https?://kt\.interpark\.com/Partner/KT/Event/NoticeList\.asp.*',
    handle_interpark_notice_main
)

async def handle_show_notice(url: str, fclient) -> dict:
    """
    공연예매 공지사항 개별 게시물 처리 핸들러 (crawl4ai 사용)
    - 제목, 날짜, 다음글 링크만 selector로 추출
    - 전체 컨텐츠는 crawl4ai로 처리
    """
    from datetime import datetime
    
    # 1. 제목, 날짜, 다음글 링크만 playwright로 추출
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # 페이지 로딩 시도 - 더 여유로운 옵션
        response = await page.goto(url, wait_until='networkidle', timeout=60000)  # networkidle로 변경, 타임아웃 60초
        await page.wait_for_timeout(5000)  # 추가 대기 시간을 5초로 늘림
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 공연예매 공지 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 공연예매 공지 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 공연예매 공지 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 공연예매 공지 ({url}): 상태 코드 정보 없음")
        
        # 페이지가 완전히 로드될 때까지 추가 대기
        try:
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            await page.wait_for_load_state('networkidle', timeout=30000)
        except Exception as e:
            logging.warning(f"공연예매 공지사항 페이지 로드 상태 대기 중 타임아웃: {str(e)}")
        
        # 제목, 날짜, 다음글 링크, 컨텐츠를 모두 추출
        metadata = await page.evaluate("""() => {
            const title = document.querySelector('.sub-title06')?.textContent?.trim() || '';
            const date = document.querySelector('.reverse li:first-child')?.textContent?.trim() || '';
            const prevElement = document.querySelector('.inventory-list li:has(strong.next) div a');
            const prevLink = prevElement?.getAttribute('href') || '';
            const prevText = prevElement?.textContent || '';
            
            // 인터파크 공지사항 내용 추출 (실제 셀렉터 우선)
            let contentHtml = '';
            const contentSelectors = ['.vip-detail-content', '.contents', '.content', '.detail-content', '.notice-content', 'main', '.main-content'];
            for (let selector of contentSelectors) {
                const contentDiv = document.querySelector(selector);
                if (contentDiv && contentDiv.innerHTML.trim()) {
                    contentHtml = contentDiv.innerHTML;
                    break;
                }
            }
            
            return {title, date, prevLink, prevText, contentHtml};
        }""")
        await browser.close()
    
    if not metadata['title'] or not metadata['date']:
        return {"error": "제목 또는 날짜 정보를 찾을 수 없습니다."}
    
    # 2. 추출된 컨텐츠 HTML을 마크다운으로 변환
    if metadata['contentHtml']:
        content = md(metadata['contentHtml'])
        logging.info(f"✅ Playwright로 공연예매 공지사항 내용 추출 성공: {len(content)}자")
    else:
        logging.warning("⚠️ 공지사항 내용 영역을 찾을 수 없음, crawl4ai fallback 시도")
        # fallback으로 crawl4ai 시도
        try:
            result = fclient.scrape_url(url)
            if result.success:
                content = result.markdown
                logging.info("✅ Crawl4ai fallback 성공")
            else:
                content = "컨텐츠 스크래핑 실패"
                logging.error("❌ Crawl4ai fallback 실패")
        except Exception as e:
            logging.error(f"❌ Crawl4ai fallback도 실패: {str(e)}")
            content = "컨텐츠 스크래핑 실패"
    
    # 3. 날짜 검증 및 포맷팅
    formatted_date = format_date_show(metadata['date'])
    if not formatted_date:
        return {"error": "날짜 형식 변환 실패"}
    
    # 마크다운 콘텐츠 포맷팅
    formatted_content = format_content(content)
    markdown_content = create_markdown(metadata['title'], metadata['date'].replace('날짜', ''), formatted_content)
    
    # 다음글 URL 처리
    next_url = None
    if metadata['prevLink'] and "이전글이 없습니다" not in metadata['prevText']:
        base_url = url.split('/Partner/KT/Event/')[0]
        next_url = f"{base_url}/Partner/KT/Event/{metadata['prevLink']}"
    
    logging.info(f"🎉 공연예매 공지사항 처리 완료: '{metadata['title']}'")
    # startdate/enddate 계산 (공지: 게시일만 → startdate)
    startdate_hyphen = "0000-00-00"
    enddate_hyphen = "9999-99-99"
    try:
        import re as _re
        dm = _re.search(r"(\\d{4})[.\\-](\\d{2})[.\\-](\\d{2})", metadata.get('date', ''))
        if dm:
            startdate_hyphen = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    except Exception:
        pass

    return {
        "url": url,
        "title": metadata['title'],
        "date": metadata['date'],
        "startdate": startdate_hyphen,
        "enddate": enddate_hyphen,
        "markdown": markdown_content,
        "html": metadata['contentHtml'] or content,
        "next_url": next_url,
        "special_processed": True,
        "playwright_processed": True
    }


# =========================
# 5. 로밍 관련 핸들러
# =========================
async def handle_globalroaming_notice_main(url: str, fclient, menu=None) -> dict:
    from datetime import datetime, timedelta
    import re
    cutoff_date = datetime.now() - timedelta(days=365)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded')
        await page.wait_for_timeout(2000)
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 글로벌로밍 공지 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 글로벌로밍 공지 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 글로벌로밍 공지 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 글로벌로밍 공지 ({url}): 상태 코드 정보 없음")
        notice_data = await page.evaluate(r"""() => {
            const table = document.querySelector('table.board.dir-vertical');
            if (!table) return { error: 'table not found' };
            
            const notices = [];
            const links = table.querySelectorAll('a[href*="view.asp"]');
            
            links.forEach(link => {
                // 테이블 행에서 추가 정보 추출
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
        return {"message": "로밍 공지사항이 없습니다", "total_processed": 0}
    menus, datas = [], []
    total_processed = 0
    for notice in notices:
        try:
            date_str = notice['date']
            date_match = re.search(r'(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})', date_str)
            if date_match:
                year, month, day = map(int, date_match.groups())
                post_date = datetime(year, month, day)
                if post_date < cutoff_date:
                    break
            # 상세 페이지에서 날짜가 없을 수 있어 목록의 등록일자를 전달하여 fallback으로 사용
            result = await handle_roaming_notice(notice['href'], fclient, notice.get('date'))
            if "error" in result:
                logging.warning(f"⚠️ 게시물 처리 실패: {result['error']}")
                continue
            formatted_date = ''
            if result.get('date'):
                date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                if date_match:
                    formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            title_clean = sanitize_filename(result.get('title', 'unknown'))
            last_folder = title_clean
            menus.append({
                'menu': f"{menu}^{last_folder}" if menu else last_folder,
                'url': notice['href'],
                'murl': to_mglobalroaming_url(notice['href'])
            })

            if not result.get('murl'):
                result['murl'] = to_mglobalroaming_url(result.get('url', notice['href']))
            datas.append(result)
            total_processed += 1
            logging.info(f"✅ 처리 완료: {total_processed}개")
        except Exception as e:
            logging.error(f"❌ 게시물 처리 중 오류: {str(e)}")
            continue
    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 로밍 공지사항 처리 완료"
    }
# 글로벌로밍 공지사항 메인 목록 페이지 등록
register_page_handler(
    r'https?://globalroaming\.kt\.com/news/list\.asp(?:\?.*)?$',
    handle_globalroaming_notice_main
)
async def handle_roaming_notice(url: str, fclient, list_date: str = None, list_title: str = None) -> dict:
    """
    로밍 공지사항 상세 페이지 처리
    """
    func_name = "handle_roaming_notice"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        page = await context.new_page()
        
        try:
            # 페이지 로딩 시도 - 더 여유로운 옵션
            response = await page.goto(url, wait_until='networkidle', timeout=60000)  # networkidle로 변경, 타임아웃 60초
            await page.wait_for_timeout(5000)  # 추가 대기 시간을 5초로 늘림
            
            # HTTP 상태 코드 확인 및 로깅
            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logging.error(f"❌ 로밍 공지 ({url}): HTTP {status_code} 오류")
                elif status_code >= 300:
                    logging.warning(f"⚠️ 로밍 공지 ({url}): HTTP {status_code} 리다이렉트")
                else:
                    logging.info(f"✅ 로밍 공지 ({url}): HTTP {status_code} 성공")
            else:
                logging.debug(f"🔍 로밍 공지 ({url}): 상태 코드 정보 없음")
            
            # 페이지가 완전히 로드될 때까지 추가 대기
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=30000)
            except Exception as e:
                logging.warning(f"로밍 공지사항 페이지 로드 상태 대기 중 타임아웃: {str(e)}")
            
            # 1. 메타데이터 추출
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

                // 다음글 링크 텍스트 기반 탐지
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
            logging.error(f"❌ Playwright 처리 중 오류: {str(e)}")
            return {"error": f"Playwright 처리 실패: {str(e)}"}
    
    # 2. 추출된 컨텐츠 HTML을 마크다운으로 변환
    if metadata['contentHtml']:
        content = md(metadata['contentHtml'])
        logging.info(f"✅ 로밍 공지사항 HTML을 마크다운으로 변환 성공: 길이={len(content)}")
    else:
        # fallback으로 crawl4ai 시도
        logging.info("⚠️ 로밍 공지사항 HTML 내용이 없어 crawl4ai fallback 시도")
        try:
            result = await fclient.scrape_single_url(url)
            if result.get("markdown"):
                content = result["markdown"]
                logging.info(f"✅ 로밍 공지사항 crawl4ai fallback 성공: 길이={len(content)}")
            else:
                content = "컨텐츠 스크래핑 실패"
                logging.error("❌ 로밍 공지사항 crawl4ai fallback 실패: markdown 없음")
        except Exception as e:
            content = "컨텐츠 스크래핑 실패"
            logging.error(f"❌ 로밍 공지사항 crawl4ai fallback 실패: {str(e)}")
    
    # 3. 카테고리와 날짜 분리 처리
    category = ''
    category_date_match = re.search(r'^(.+?)\s*(\d{4}[\.\-]\d{2}[\.\-]\d{2})', metadata['rawDate'])
    if category_date_match:
        category = category_date_match.group(1).strip()
        actual_date = category_date_match.group(2).replace('-', '.')
        logging.info(f"✅ 로밍 공지사항 날짜 파싱 성공: date='{actual_date}', category='{category}'")
    else:
        # 분리 실패 시 전체를 날짜로 처리 시도
        date_only_match = re.search(r'(\d{4}[\.\-]\d{2}[\.\-]\d{2})', metadata['rawDate'])
        if date_only_match:
            actual_date = date_only_match.group(1).replace('-', '.')
            logging.info(f"✅ 로밍 공지사항 날짜 파싱 성공 (fallback): date='{actual_date}'")
        else:
            # 목록 페이지의 등록일자를 fallback으로 사용 시도
            if list_date:
                list_date_match = re.search(r'(\d{4}[\.\-]\d{2}[\.\-]\d{2})', list_date)
                if list_date_match:
                    actual_date = list_date_match.group(1).replace('-', '.')
                    logging.info(f"✅ 로밍 공지사항 날짜 파싱 성공 (list fallback): date='{actual_date}'")
                else:
                    logging.error(f"❌ 로밍 공지사항 날짜 파싱 실패 (list fallback 불가): raw='{metadata['rawDate']}', list='{list_date}'")
                    actual_date = ''
            else:
                logging.error(f"❌ 로밍 공지사항 날짜 파싱 실패: {metadata['rawDate']}")
                actual_date = ''
    
    # 4. 마크다운 콘텐츠 포맷팅
    formatted_content = format_content(content)
    # 카테고리 정보도 마크다운에 포함
    date_display = f"{actual_date}" + (f" (카테고리: {category})" if category else "")
    
    # 제목 최종 결정 (상세가 비면 목록 제목 사용)
    final_title = metadata['title'] if metadata['title'] else (list_title or '제목 없음')
    markdown_content = create_markdown(final_title, date_display, formatted_content)
    
    # 다음글 URL 처리
    next_url = None
    if metadata['nextLink']:
        base_url = url.split('/news/')[0]
        next_url = f"{base_url}/news/{metadata['nextLink']}"
    
    logging.info(f"🎉 로밍 공지사항 처리 완료: title='{final_title}', date='{actual_date}'")

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

    startdate_hyphen = "0000-00-00"
    enddate_hyphen = "9999-99-99"

    text_for_range = (metadata.get('contentHtml') or '') + ' ' + (content or '')
    inherit_left_year = False
    m_range = re.search(r"(\d{4}[년\.\-]\s*\d{1,2}[월\.\-]\s*\d{1,2}일?)\s*[~\-–]\s*(\d{4}[년\.\-]?\s*\d{1,2}[월\.\-]\s*\d{1,2}일?)", text_for_range)
    if not m_range:
        m_range = re.search(r"(\d{4}[년\.\-]\s*\d{1,2}[월\.\-]\s*\d{1,2}일?)\s*[~\-–]\s*(\d{1,2}[월\.\-]\s*\d{1,2}일?)", text_for_range)
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

# =========================
# 6. KT 공지/네트워크/안전한 통신생활 관련 핸들러
# =========================
async def handle_kt_notice_main(url: str, fclient, menu=None) -> dict:
    logging.info(f"KT 공지사항 메인 핸들러 진입: url={url}, menu={menu}")
    from datetime import datetime, timedelta
    import re
    cutoff_date = datetime.now() - timedelta(days=365)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded')
        first_notice_link = None
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ KT 공지 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ KT 공지 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ KT 공지 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 KT 공지 ({url}): 상태 코드 정보 없음")
        for attempt in range(3):
            try:
                await page.wait_for_selector('a[data-bno]', timeout=10000)
            except Exception as e:
                pass
            await page.wait_for_timeout(2000)
            first_notice_link = await page.evaluate("""() => {
                const firstElement = document.querySelector('a[data-bno]');
                if (firstElement) {
                    const bno = firstElement.getAttribute('data-bno');
                    return `https://inside.kt.com/html/notice/notice_detail.html?bno=${bno}`;
                }
                return null;
            }""")
            if first_notice_link:
                break
            elif attempt < 2:
                pass
        await browser.close()
    if not first_notice_link:
        return {"error": "첫 번째 공지사항 링크를 찾을 수 없습니다"}
    total_processed = 0
    current_url = first_notice_link
    menus, datas = [], []
    logging.info(f"총 {total_processed}개 공지사항 게시물 처리 시작")
    while current_url and total_processed < 1000:
        try:
            logging.info(f"🔄 {total_processed + 1}번째 공지사항 처리 시작: url={current_url}")
            result = await handle_kt_notice_detail(current_url, fclient, cutoff_date)
            if "error" in result:
                logging.warning(f"❌ {total_processed + 1}번째 공지사항 처리 실패: {result['error']}")
                break
            if result.get("date_cutoff_reached"):
                logging.info(f"⏰ 날짜 cutoff 도달: {result.get('date', 'unknown')}")
                break
            formatted_date = ''
            if result.get('date'):
                date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                if date_match:
                    formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            title_clean = sanitize_filename(result.get('title', 'unknown'))
            last_folder = f"({formatted_date}){title_clean}" if formatted_date else title_clean
            menus.append({'menu': f"{menu}^{last_folder}" if menu else last_folder, 'url': current_url})
            datas.append(result)
            total_processed += 1
            logging.info(f"✅ {total_processed}번째 공지사항 처리 완료: '{result.get('title', 'unknown')}' ({formatted_date})")
            current_url = result.get("next_url")
            if not current_url:
                logging.info("🔗 다음 게시물 링크가 없어 처리 종료")
                break
        except Exception as e:
            logging.error(f"❌ {total_processed + 1}번째 공지사항 처리 중 오류: {str(e)}")
            break
    logging.info(f"🎉 KT 공지사항 메인 처리 완료: 총 {total_processed}개 게시물 처리됨")
    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 게시물 처리됨"
    }

async def handle_kt_notice_detail(url: str, fclient, cutoff_date=None) -> dict:
    """
    KT 공지사항 개별 게시물 처리 핸들러 (crawl4ai 사용)
    - 제목, 날짜(카테고리), 다음글 링크만 selector로 추출
    - 전체 컨텐츠는 crawl4ai로 처리
    """
    from datetime import datetime
    import re
    
    if cutoff_date is None:
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=365)
    
    logging.info(f"🔄 KT 공지사항 개별 게시물 처리: {url}")
    
    # 1. 제목, 날짜, 다음글 링크만 playwright로 추출
    max_retries = 3
    metadata = None
    
    for attempt in range(max_retries):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                # 로딩 전략을 시도별로 다르게 적용
                if attempt == 0:
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await page.wait_for_timeout(3000)
                elif attempt == 1:
                    response = await page.goto(url, wait_until='load', timeout=40000)
                    await page.wait_for_timeout(5000)
                else:
                    response = await page.goto(url, wait_until='networkidle', timeout=50000)
                    await page.wait_for_timeout(7000)
                
                # HTTP 상태 코드 확인 및 로깅
                status_code = response.status if response else None
                if status_code:
                    if status_code >= 400:
                        logging.error(f"❌ KT 공지 상세 ({url}): HTTP {status_code} 오류")
                    elif status_code >= 300:
                        logging.warning(f"⚠️ KT 공지 상세 ({url}): HTTP {status_code} 리다이렉트")
                    else:
                        logging.info(f"✅ KT 공지 상세 ({url}): HTTP {status_code} 성공")
                else:
                    logging.debug(f"🔍 KT 공지 상세 ({url}): 상태 코드 정보 없음")
                
                # 제목, 날짜, 다음글 링크, 컨텐츠를 모두 추출
                metadata = await page.evaluate("""() => {
                    const title = document.querySelector('h1.title');
                    const dateElement = document.querySelector('.desc');
                    const contentDiv = document.querySelector('.txt-content');
                    
                    // 다음글 링크 찾기 - data-bno 속성 기반
                    let nextLink = '';
                    
                    // 방법 1: data-bno 속성이 있고 "다음글" 관련 요소
                    const nextElement = document.querySelector('a[data-bno].next-area');
                    if (nextElement) {
                        const nextBno = nextElement.getAttribute('data-bno');
                        if (nextBno) {
                            const currentUrl = window.location.href;
                            const baseUrl = currentUrl.split('?')[0];
                            nextLink = `${baseUrl}?bno=${nextBno}`;
                        }
                    }
                    
                    // 방법 2: "다음글" 텍스트가 포함된 요소에서 data-bno 찾기
                    if (!nextLink) {
                        const allElements = document.querySelectorAll('*');
                        for (let elem of allElements) {
                            if (elem.textContent && elem.textContent.includes('다음글')) {
                                const parent = elem.closest('a[data-bno]');
                                if (parent) {
                                    const nextBno = parent.getAttribute('data-bno');
                                    if (nextBno) {
                                        const currentUrl = window.location.href;
                                        const baseUrl = currentUrl.split('?')[0];
                                        nextLink = `${baseUrl}?bno=${nextBno}`;
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    
                    // 방법 3: 기존 방식 (href에 bno가 있는 경우)
                    if (!nextLink) {
                        const nextLinks = document.querySelectorAll('a[href*="bno="]');
                        for (let link of nextLinks) {
                            if (link.textContent.includes('다음글') || link.textContent.includes('다음')) {
                                nextLink = link.href;
                                break;
                            }
                        }
                    }
                    
                    return {
                        title: title ? title.textContent.trim() : '',
                        rawDate: dateElement ? dateElement.textContent.trim() : '',
                        nextLink: nextLink,
                        contentHtml: contentDiv ? contentDiv.innerHTML : ''
                    };
                }""")
                
                await browser.close()
                
                # 데이터 유효성 검증
                if metadata['title'] and metadata['rawDate']:
                    if attempt > 0:
                        logging.info(f"✅ 재시도 {attempt + 1}회차에서 성공")
                    break
                elif attempt < max_retries - 1:
                    logging.warning(f"⚠️ 시도 {attempt + 1}회차 실패 - 제목/날짜 정보 없음, 재시도 중...")
                    continue
                else:
                    return {"error": "제목 또는 날짜 정보를 찾을 수 없습니다."}
                    
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"⚠️ 시도 {attempt + 1}회차에서 에러 발생: {str(e)} - 재시도 중...")
                continue
            else:
                logging.error(f"❌ 모든 재시도 실패: {str(e)}")
                return {"error": f"페이지 로딩 실패: {str(e)}"}
    
    # 2. 추출된 컨텐츠 HTML을 마크다운으로 변환
    if metadata['contentHtml']:
        content = md(metadata['contentHtml'])
        logging.info(f"✅ Playwright로 공지사항 내용 추출 성공: {len(content)}자")
    else:
        logging.warning("⚠️ '.txt-content' 영역을 찾을 수 없음, crawl4ai fallback 시도")
        # fallback으로 crawl4ai 시도
        try:
            result = fclient.scrape_url(url)
            if result.success:
                content = result.markdown
                logging.info("✅ Crawl4ai fallback 성공")
            else:
                content = "컨텐츠 스크래핑 실패"
                logging.error("❌ Crawl4ai fallback 실패")
        except Exception as e:
            logging.error(f"❌ Crawl4ai fallback도 실패: {str(e)}")
            content = "컨텐츠 스크래핑 실패"
    
    # 3. 카테고리와 날짜 분리 처리
    category = ""
    actual_date = ""
    
    category_date_match = re.match(r'^(.+?)(\d{4}\.\d{2}\.\d{2})$', metadata['rawDate'])
    if category_date_match:
        category = category_date_match.group(1).strip()
        actual_date = category_date_match.group(2)
        logging.info(f"✅ 카테고리 분리 성공: 카테고리='{category}', 날짜='{actual_date}'")
    else:
        # 분리 실패 시 전체를 날짜로 처리 시도
        date_only_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', metadata['rawDate'])
        if date_only_match:
            actual_date = date_only_match.group(1)
            logging.warning(f"⚠️ 카테고리 분리 실패, 날짜만 추출: '{actual_date}'")
        else:
            logging.warning(f"❌ 날짜 파싱 실패: {metadata['rawDate']}")
            return {"error": f"날짜 파싱 실패: {metadata['rawDate']}"}
    
    # 날짜 cutoff 체크
    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', actual_date)
    if date_match:
        year, month, day = map(int, date_match.groups())
        post_date = datetime(year, month, day)
        
        if post_date < cutoff_date:
            logging.info(f"⏰ 게시물 날짜({post_date.strftime('%Y-%m-%d')})가 기준일 이전입니다")
            return {"date_cutoff_reached": True}
    else:
        logging.warning(f"❌ 날짜 파싱 실패: {actual_date}")
    
    # 4. 마크다운 콘텐츠 포맷팅
    formatted_content = format_content(content)
    # 카테고리 정보도 마크다운에 포함
    date_display = f"{actual_date}" + (f" (카테고리: {category})" if category else "")
    markdown_content = create_markdown(metadata['title'], date_display, formatted_content)
    
    # 다음글 URL 처리
    next_url = None
    if metadata['nextLink'] and 'bno=' in metadata['nextLink']:
        next_url = metadata['nextLink']
    
    # 모바일 URL 생성 (inside.kt.com -> m.kt.com)
    mobile_url = url.replace('inside.kt.com', 'm.kt.com') if 'inside.kt.com' in url else None
    
    logging.info(f"🎉 KT 공지사항 상세 처리 완료: title='{metadata['title']}', date='{actual_date}'")
    # startdate/enddate (공지: 게시일만 → startdate에 저장)
    startdate_hyphen = "0000-00-00"
    enddate_hyphen = "9999-99-99"
    try:
        dm = re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", actual_date)
        if dm:
            startdate_hyphen = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    except Exception:
        pass

    return {
        "url": url,
        "mobile_url": mobile_url,
        "murl": mobile_url or '',
        "title": metadata['title'],
        "category": category,
        "date": actual_date,
        "raw_date": metadata['rawDate'],
        "startdate": startdate_hyphen,
        "enddate": enddate_hyphen,
        "markdown": markdown_content,
        "html": metadata['contentHtml'] or content,
        "next_url": next_url,
        "special_processed": True,
        "playwright_processed": True
    }

register_page_handler(
    r'https?://inside\.kt\.com/html/notice/notice_list\.html',
    handle_kt_notice_main
)

async def handle_network_notice_main(url: str, fclient, menu=None) -> dict:
    logging.info(f"네트워크 공지사항 메인 핸들러 진입: url={url}, menu={menu}")
    from datetime import datetime, timedelta
    import re
    cutoff_date = datetime.now() - timedelta(days=365)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded')
        first_bno = None
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 네트워크 공지 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 네트워크 공지 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 네트워크 공지 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 네트워크 공지 ({url}): 상태 코드 정보 없음")
        for attempt in range(3):
            try:
                await page.wait_for_selector('a[data-bno]', timeout=10000)
            except Exception as e:
                pass
            await page.wait_for_timeout(2000)
            first_bno = await page.evaluate("""() => {
                const firstLink = document.querySelector('a[data-bno]');
                return firstLink ? firstLink.getAttribute('data-bno') : null;
            }""")
            if first_bno:
                break
            elif attempt < 2:
                pass
        await browser.close()
    if not first_bno:
        return {"error": "첫 번째 게시물을 찾을 수 없습니다"}
    first_url = f"https://inside.kt.com/html/notice/net_notice_detail.html?bno={first_bno}"
    current_url = first_url
    total_processed = 0
    menus, datas = [], []
    max_iterations = 1000
    logging.info(f"총 {total_processed}개 네트워크 공지사항 게시물 처리 시작")
    for i in range(max_iterations):
        if not current_url:
            break
        try:
            logging.info(f"🔄 {total_processed + 1}번째 네트워크 공지사항 처리 시작: url={current_url}")
            result = await handle_network_notice_detail(current_url, fclient, cutoff_date)
            if "error" in result:
                logging.warning(f"❌ {total_processed + 1}번째 네트워크 공지사항 처리 실패: {result['error']}")
                break
            elif result.get("date_cutoff_reached"):
                logging.info(f"⏰ 날짜 cutoff 도달: {result.get('date', 'unknown')}")
                break
            else:
                formatted_date = ''
                if result.get('date'):
                    date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                    if date_match:
                        formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
                title_clean = sanitize_filename(result.get('title', 'unknown'))
                last_folder = f"({formatted_date}){title_clean}" if formatted_date else title_clean
                menus.append({'menu': f"{menu}^{last_folder}" if menu else last_folder, 'url': current_url, 'murl': result.get('murl')})
                datas.append(result)
                total_processed += 1
                logging.info(f"✅ {total_processed}번째 네트워크 공지사항 처리 완료: '{result.get('title', 'unknown')}' ({formatted_date})")
                current_url = result.get("next_url")
                if not current_url:
                    logging.info("🔗 다음 게시물 링크가 없어 처리 종료")
                    break
        except Exception as e:
            logging.error(f"❌ {total_processed + 1}번째 네트워크 공지사항 처리 중 오류: {str(e)}")
            break
    logging.info(f"🎉 네트워크 공지사항 메인 처리 완료: 총 {total_processed}개 게시물 처리됨")
    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 네트워크 공지사항 처리 완료"
    }
async def handle_network_notice_detail(url: str, fclient, cutoff_date=None) -> dict:
    logging.info(f"네트워크 공지사항 상세 핸들러 진입: url={url}, cutoff_date={cutoff_date}")
    """
    네트워크 공지사항 개별 게시물 처리 핸들러 (crawl4ai 사용)
    - 제목, 날짜(카테고리), 다음글 링크만 selector로 추출
    - 전체 컨텐츠는 crawl4ai로 처리
    """
    from datetime import datetime
    func_name = "handle_network_notice_detail"
    import re
    
    if cutoff_date is None:
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=365)
    
    # 1. 제목, 날짜, 다음글 링크만 playwright로 추출
    metadata = None
    try:
        logging.info(f"🔄 네트워크 공지사항 상세 페이지 진입: url={url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            # 페이지 로딩 시도 - 더 여유로운 옵션
            response = await page.goto(url, wait_until='networkidle', timeout=60000)  # networkidle로 변경, 타임아웃 60초
            await page.wait_for_timeout(5000)  # 추가 대기 시간을 5초로 늘림
            
            # HTTP 상태 코드 확인 및 로깅
            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logging.error(f"❌ 네트워크 공지 상세 ({url}): HTTP {status_code} 오류")
                elif status_code >= 300:
                    logging.warning(f"⚠️ 네트워크 공지 상세 ({url}): HTTP {status_code} 리다이렉트")
                else:
                    logging.info(f"✅ 네트워크 공지 상세 ({url}): HTTP {status_code} 성공")
            else:
                logging.debug(f"🔍 네트워크 공지 상세 ({url}): 상태 코드 정보 없음")
            
            # 페이지가 완전히 로드될 때까지 추가 대기
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=30000)
            except Exception as e:
                logging.warning(f"네트워크 공지사항 페이지 로드 상태 대기 중 타임아웃: {str(e)}")
            
            # 제목, 날짜, 다음글 링크 추출
            title = await page.evaluate("""() => {
                const t = document.querySelector('h1.title');
                return t ? t.textContent.trim() : '';
            }""")
            raw_date = await page.evaluate("""() => {
                const d = document.querySelector('.desc');
                return d ? d.textContent.trim() : '';
            }""")
            
            # 성공 조건 체크: 제목과 날짜가 모두 있으면 성공으로 간주
            if title and raw_date:
                logging.info(f"✅ 네트워크 공지사항 상세 페이지 진입 성공: title='{title}', date='{raw_date}'")
                # 본문 여러 후보 셀렉터 순차 시도
                content_html = ""
                for selector in ['.txt-content', '.contents', '.content', '.detail-content', '.notice-content', 'main', '.main-content']:
                    content_div = await page.query_selector(selector)
                    if content_div:
                        html = await content_div.inner_html()
                        if html.strip():
                            content_html = html
                            logging.info(f"✅ 네트워크 공지사항 본문 추출 성공: selector='{selector}', 길이={len(html)}")
                            break
                if not content_html:
                    logging.warning("⚠️ 네트워크 공지사항 본문 추출 실패: 모든 셀렉터에서 내용을 찾을 수 없음")
                
                # 다음글 링크 추출
                next_link = await page.evaluate("""() => {
                    let nextLink = '';
                    const nextElement = document.querySelector('a[data-bno].next-area');
                    if (nextElement) {
                        const nextBno = nextElement.getAttribute('data-bno');
                        if (nextBno) {
                            const currentUrl = window.location.href;
                            const baseUrl = currentUrl.split('?')[0];
                            nextLink = `${baseUrl}?bno=${nextBno}`;
                        }
                    }
                    if (!nextLink) {
                        const allElements = document.querySelectorAll('*');
                        for (let elem of allElements) {
                            if (elem.textContent && elem.textContent.includes('다음글')) {
                                const parent = elem.closest('a[data-bno]');
                                if (parent) {
                                    const nextBno = parent.getAttribute('data-bno');
                                    if (nextBno) {
                                        const currentUrl = window.location.href;
                                        const baseUrl = currentUrl.split('?')[0];
                                        nextLink = `${baseUrl}?bno=${nextBno}`;
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    if (!nextLink) {
                        const nextLinks = document.querySelectorAll('a[href*="bno="]');
                        for (let link of nextLinks) {
                            if (link.textContent.includes('다음글') || link.textContent.includes('다음')) {
                                nextLink = link.href;
                                break;
                            }
                        }
                    }
                    return nextLink;
                }""")
                if next_link:
                    logging.info(f"🔗 네트워크 공지사항 다음글 링크 발견: {next_link}")
                else:
                    logging.info("🔗 네트워크 공지사항 다음글 링크 없음")
                await browser.close()
                metadata = {
                    'title': title,
                    'rawDate': raw_date,
                    'nextLink': next_link,
                    'contentHtml': content_html
                }
            else:
                logging.error(f"❌ 네트워크 공지사항 상세 페이지 진입 실패: 제목='{title}', 날짜='{raw_date}'")
                await browser.close()
                return {"error": "제목 또는 날짜 정보를 찾을 수 없습니다."}

    except Exception as e:
        logging.error(f"❌ 네트워크 공지사항 상세 페이지 진입 실패: {str(e)}")
        return {"error": f"페이지 로딩 실패: {str(e)}"}
    
    # 2. 추출된 컨텐츠 HTML을 마크다운으로 변환
    if metadata['contentHtml']:
        content = md(metadata['contentHtml'])
        logging.info(f"✅ 네트워크 공지사항 HTML을 마크다운으로 변환 성공: 길이={len(content)}")
    else:
        # fallback으로 crawl4ai 시도
        logging.info("⚠️ 네트워크 공지사항 HTML 내용이 없어 crawl4ai fallback 시도")
        try:
            result = await fclient.scrape_single_url(url)
            if result.get("markdown"):
                content = result["markdown"]
                logging.info(f"✅ 네트워크 공지사항 crawl4ai fallback 성공: 길이={len(content)}")
            else:
                content = "컨텐츠 스크래핑 실패"
                logging.error("❌ 네트워크 공지사항 crawl4ai fallback 실패: markdown 없음")
        except Exception as e:
            content = "컨텐츠 스크래핑 실패"
            logging.error(f"❌ 네트워크 공지사항 crawl4ai fallback 실패: {str(e)}")
    
    # 3. 카테고리와 날짜 분리 처리 (정규식으로 robust하게)
    raw_date = metadata.get('rawDate', '')
    date_only_match = re.search(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', raw_date)
    if date_only_match:
        actual_date = date_only_match.group(1)
        category = raw_date[:raw_date.find(actual_date)].strip() if raw_date.find(actual_date) > 0 else ""
        logging.info(f"✅ 네트워크 공지사항 날짜 파싱 성공: date='{actual_date}', category='{category}'")
    else:
        actual_date = ""
        category = ""
        logging.error(f"❌ 네트워크 공지사항 날짜 파싱 실패: raw_date='{raw_date}'")
        return {"error": f"날짜 파싱 실패: {raw_date}"}
    
    # 날짜 cutoff 체크
    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', actual_date)
    if date_match:
        year, month, day = map(int, date_match.groups())
        post_date = datetime(year, month, day)
        if post_date < cutoff_date:
            logging.info(f"⏰ 네트워크 공지사항 날짜 cutoff 도달: {actual_date} < {cutoff_date.strftime('%Y.%m.%d')}")
            return {"date_cutoff_reached": True}
    else:
        pass
    
    # 4. 마크다운 콘텐츠 포맷팅
    formatted_content = format_content(content)
    date_display = f"{actual_date}" + (f" (카테고리: {category})" if category else "")
    markdown_content = create_markdown(metadata['title'], date_display, formatted_content)
    logging.info(f"✅ 네트워크 공지사항 마크다운 생성 완료: title='{metadata['title']}', 길이={len(markdown_content)}")
    
    # 다음글 URL 처리
    next_url = None
    if metadata['nextLink'] and 'bno=' in metadata['nextLink']:
        next_url = metadata['nextLink']
    
    # 모바일 URL 생성 (inside.kt.com -> m.kt.com)
    mobile_url = url.replace('inside.kt.com', 'm.kt.com') if 'inside.kt.com' in url else None
    
    logging.info(f"🎉 네트워크 공지사항 상세 처리 완료: title='{metadata['title']}', date='{actual_date}'")
    # startdate/enddate (공지: 게시일만 → startdate에 저장)
    startdate_hyphen = "0000-00-00"
    enddate_hyphen = "9999-99-99"
    try:
        dm = re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", actual_date)
        if dm:
            startdate_hyphen = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    except Exception:
        pass

    return {
        "url": url,
        "mobile_url": mobile_url,
        "murl": mobile_url or '',
        "title": metadata['title'],
        "category": category,
        "date": actual_date,
        "raw_date": metadata['rawDate'],
        "startdate": startdate_hyphen,
        "enddate": enddate_hyphen,
        "markdown": markdown_content,
        "html": metadata['contentHtml'] or content,
        "next_url": next_url,
        "special_processed": True,
        "playwright_processed": True
    }

register_page_handler(
    r'https?://inside\.kt\.com/html/notice/net_notice_list\.html',
    handle_network_notice_main
)

async def handle_safety_notice_main(url: str, fclient, menu=None) -> dict:
    logging.info(f"안전한통신생활 공지 메인 핸들러 진입: url={url}, menu={menu}")
    """
    안전한 통신생활 공지사항 메인 페이지 처리 핸들러 (input_urls의 menu 컬럼 사용)
    - data-bno 속성을 가진 링크들 추출 (기존 KT 공지사항과 동일 구조)
    - 가장 최신 게시물부터 1년 전까지 순차 처리
    - 각 게시물의 menu는 input_urls에서 상위에서 받아옴
    - menus, datas 리스트로 누적/반환
    """
    from datetime import datetime, timedelta
    
    # 1년 전 날짜 계산
    cutoff_date = datetime.now() - timedelta(days=365)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded')
        first_notice_link = None
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 안전한통신생활 공지 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 안전한통신생활 공지 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 안전한통신생활 공지 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 안전한통신생활 공지 ({url}): 상태 코드 정보 없음")
        for attempt in range(3):
            try:
                await page.wait_for_selector('a[data-bno]', timeout=10000)
            except Exception as e:
                logging.warning(f"'a[data-bno]' 요소 대기 실패 (시도 {attempt+1}/3): {str(e)}")
            await page.wait_for_timeout(2000)
            first_notice_link = await page.evaluate("""() => {
                const firstElement = document.querySelector('a[data-bno]');
                if (firstElement) {
                    const bno = firstElement.getAttribute('data-bno');
                    // 안전한 통신생활은 safety_detail.html을 사용할 것으로 추정
                    return `https://inside.kt.com/html/safety/notice_detail.html?bno=${bno}`;
                }
                return null;
            }""")
            if first_notice_link:
                break
            elif attempt < 2:
                pass
        await browser.close()
    
    if not first_notice_link:
        return {"error": "첫 번째 안전한 통신생활 공지사항 링크를 찾을 수 없습니다"}
    
    # 첫 번째 게시물부터 순차 처리 시작
    total_processed = 0
    current_url = first_notice_link
    menus = []
    datas = []
    logging.info(f"총 {total_processed}개 안전한통신생활 공지사항 게시물 처리 시작")

    while current_url and total_processed < 1000:  # 안전장치: 최대 1000개
        try:
            logging.info(f"🔄 {total_processed + 1}번째 안전한통신생활 공지사항 처리 시작: url={current_url}")
            # 상세 핸들러 호출 (menu명을 상위에서 주입)
            result = await handle_safety_notice_detail(current_url, fclient)

            if "error" in result:
                logging.warning(f"❌ {total_processed + 1}번째 안전한통신생활 공지사항 처리 실패: {result['error']}")
                break

            if result.get("date_cutoff_reached"):
                logging.info(f"⏰ 날짜 cutoff 도달: {result.get('date', 'unknown')}")
                break

            # === 게시물 정보 추가 ===
            import re
            from datetime import datetime
            # 날짜 파싱 및 yy-mm-dd 생성
            formatted_date = ''
            if result.get('date'):
                date_match = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', result['date'])
                if date_match:
                    formatted_date = f"{date_match.group(1)[2:]}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            # 제목 정제
            title_clean = sanitize_filename(result.get('title', 'unknown'))
            # 마지막 폴더명: (yy-mm-dd){title}
            last_folder = f"({formatted_date}){title_clean}" if formatted_date else title_clean

            # menus, datas 리스트에 정보 추가
            menus.append({'menu': f"{menu}^{last_folder}" if menu else last_folder, 'url': current_url, 'murl': result.get('murl')})
            datas.append(result)

            total_processed += 1
            logging.info(f"✅ {total_processed}번째 안전한통신생활 공지사항 처리 완료: '{result.get('title', 'unknown')}' ({formatted_date})")
            current_url = result.get("next_url")

            if not current_url:
                logging.info("🔗 다음 게시물 링크가 없어 처리 종료")
                break

        except Exception as e:
            logging.error(f"❌ {total_processed + 1}번째 안전한통신생활 공지사항 처리 중 오류: {str(e)}")
            break

    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_processed,
        "status": "completed",
        "message": f"총 {total_processed}개 안전한 통신생활 공지사항 처리 완료"
    }

register_page_handler(
    r'https?://inside\.kt\.com/html/safety/notice_list\.html',
    handle_safety_notice_main
)

async def handle_safety_notice_detail(url: str, fclient, cutoff_date=None) -> dict:
    logging.info(f"안전한통신생활 공지 상세 핸들러 진입: url={url}, cutoff_date={cutoff_date}")
    """
    안전한 통신생활 공지사항 개별 게시물 처리 핸들러 (crawl4ai 사용)
    - 제목, 날짜(카테고리), 다음글 링크만 selector로 추출
    - 전체 컨텐츠는 crawl4ai로 처리
    """
    from datetime import datetime
    func_name = "handle_safety_notice_detail"
    import re
    
    if cutoff_date is None:
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=365)
    
    # 1. 제목, 날짜, 다음글 링크만 playwright로 추출
    metadata = None
    try:
        logging.info(f"🔄 안전한통신생활 공지사항 상세 페이지 진입: url={url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            # 페이지 로딩 시도 - 더 여유로운 옵션
            response = await page.goto(url, wait_until='networkidle', timeout=60000)  # networkidle로 변경, 타임아웃 60초
            await page.wait_for_timeout(5000)  # 추가 대기 시간을 5초로 늘림
            
            # HTTP 상태 코드 확인 및 로깅
            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logging.error(f"❌ 안전한통신생활 공지 상세 ({url}): HTTP {status_code} 오류")
                elif status_code >= 300:
                    logging.warning(f"⚠️ 안전한통신생활 공지 상세 ({url}): HTTP {status_code} 리다이렉트")
                else:
                    logging.info(f"✅ 안전한통신생활 공지 상세 ({url}): HTTP {status_code} 성공")
            else:
                logging.debug(f"🔍 안전한통신생활 공지 상세 ({url}): 상태 코드 정보 없음")
            
            # 페이지가 완전히 로드될 때까지 추가 대기
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=30000)
            except Exception as e:
                logging.warning(f"안전한통신생활 공지사항 페이지 로드 상태 대기 중 타임아웃: {str(e)}")
            
            # 제목, 날짜, 다음글 링크 추출
            title = await page.evaluate("""() => {
                const t = document.querySelector('h1.title');
                return t ? t.textContent.trim() : '';
            }""")
            raw_date = await page.evaluate("""() => {
                const d = document.querySelector('.desc');
                return d ? d.textContent.trim() : '';
            }""")
            
            # 성공 조건 체크: 제목과 날짜가 모두 있으면 성공으로 간주
            if title and raw_date:
                logging.info(f"✅ 안전한통신생활 공지사항 상세 페이지 진입 성공: title='{title}', date='{raw_date}'")
                # 본문 여러 후보 셀렉터 순차 시도
                content_html = ""
                for selector in ['.txt-content', '.contents', '.content', '.detail-content', '.notice-content', 'main', '.main-content']:
                    content_div = await page.query_selector(selector)
                    if content_div:
                        html = await content_div.inner_html()
                        if html.strip():
                            content_html = html
                            logging.info(f"✅ 안전한통신생활 공지사항 본문 추출 성공: selector='{selector}', 길이={len(html)}")
                            break
                if not content_html:
                    logging.warning("⚠️ 안전한통신생활 공지사항 본문 추출 실패: 모든 셀렉터에서 내용을 찾을 수 없음")
                
                # 다음글 링크 추출
                next_link = await page.evaluate("""() => {
                    let nextLink = null;
                    const nextLinks = document.querySelectorAll('a[href*="bno="]');
                    for (let link of nextLinks) {
                        if (link.textContent.includes('다음글') || link.textContent.includes('다음')) {
                            nextLink = link.href;
                            break;
                        }
                    }
                    return nextLink;
                }""")
                if next_link:
                    logging.info(f"🔗 안전한통신생활 공지사항 다음글 링크 발견: {next_link}")
                else:
                    logging.info("🔗 안전한통신생활 공지사항 다음글 링크 없음")
                await browser.close()
                metadata = {
                    'title': title,
                    'rawDate': raw_date,
                    'nextLink': next_link,
                    'contentHtml': content_html
                }
            else:
                logging.error(f"❌ 안전한통신생활 공지사항 상세 페이지 진입 실패: 제목='{title}', 날짜='{raw_date}'")
                await browser.close()
                return {"error": f"페이지 로딩 실패: 제목 또는 날짜를 찾을 수 없음"}

    except Exception as e:
        logging.error(f"❌ 안전한통신생활 공지사항 상세 페이지 진입 실패: {str(e)}")
        return {"error": f"페이지 로딩 실패: {str(e)}"}
    
    # 2. 추출된 컨텐츠 HTML을 마크다운으로 변환
    if metadata['contentHtml']:
        content = md(metadata['contentHtml'])
        logging.info(f"✅ 안전한통신생활 공지사항 HTML을 마크다운으로 변환 성공: 길이={len(content)}")
    else:
        # fallback으로 crawl4ai 시도
        logging.info("⚠️ 안전한통신생활 공지사항 HTML 내용이 없어 crawl4ai fallback 시도")
        try:
            result = await fclient.scrape_single_url(url)
            if result.get("markdown"):
                content = result["markdown"]
                logging.info(f"✅ 안전한통신생활 공지사항 crawl4ai fallback 성공: 길이={len(content)}")
            else:
                content = "컨텐츠 스크래핑 실패"
                logging.error("❌ 안전한통신생활 공지사항 crawl4ai fallback 실패: markdown 없음")
        except Exception as e:
            content = "컨텐츠 스크래핑 실패"
            logging.error(f"❌ 안전한통신생활 공지사항 crawl4ai fallback 실패: {str(e)}")
    
    # 3. 카테고리와 날짜 분리 처리 (정규식으로 robust하게)
    raw_date = metadata.get('rawDate', '')
    date_only_match = re.search(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', raw_date)
    if date_only_match:
        actual_date = date_only_match.group(1)
        category = raw_date[:raw_date.find(actual_date)].strip() if raw_date.find(actual_date) > 0 else ""
        logging.info(f"✅ 안전한통신생활 공지사항 날짜 파싱 성공: date='{actual_date}', category='{category}'")
    else:
        actual_date = ""
        category = ""
        logging.error(f"❌ 안전한통신생활 공지사항 날짜 파싱 실패: raw_date='{raw_date}'")
        return {"error": f"날짜 파싱 실패: {raw_date}"}
    
    # 날짜 cutoff 체크
    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', actual_date)
    if date_match:
        year, month, day = map(int, date_match.groups())
        post_date = datetime(year, month, day)
        if post_date < cutoff_date:
            logging.info(f"⏰ 안전한통신생활 공지사항 날짜 cutoff 도달: {actual_date} < {cutoff_date.strftime('%Y.%m.%d')}")
            return {"date_cutoff_reached": True}
    else:
        pass
    
    # 4. 마크다운 콘텐츠 포맷팅
    formatted_content = format_content(content)
    date_display = f"{actual_date}" + (f" (카테고리: {category})" if category else "")
    markdown_content = create_markdown(metadata['title'], date_display, formatted_content)
    logging.info(f"✅ 안전한통신생활 공지사항 마크다운 생성 완료: title='{metadata['title']}', 길이={len(markdown_content)}")
    
    # 다음글 URL 처리
    next_url = None
    if metadata['nextLink'] and 'bno=' in metadata['nextLink']:
        next_url = metadata['nextLink']
    
    # 모바일 URL 생성 (inside.kt.com -> m.kt.com)
    mobile_url = url.replace('inside.kt.com', 'm.kt.com') if 'inside.kt.com' in url else None
    
    # startdate/enddate (공지: 게시일만 → startdate에 저장)
    startdate_hyphen = "0000-00-00"
    enddate_hyphen = "9999-99-99"
    try:
        dm = re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", actual_date)
        if dm:
            startdate_hyphen = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    except Exception:
        pass

    logging.info(f"🎉 안전한통신생활 공지사항 상세 처리 완료: title='{metadata['title']}', date='{actual_date}'")
    return {
        "url": url,
        "mobile_url": mobile_url,
        "murl": mobile_url or '',
        "title": metadata['title'],
        "category": category,
        "date": actual_date,
        "raw_date": metadata['rawDate'],
        "startdate": startdate_hyphen,
        "enddate": enddate_hyphen,
        "markdown": markdown_content,
        "html": metadata['contentHtml'] or content,
        "next_url": next_url,
        "special_processed": True,
        "playwright_processed": True
    }
    
async def handle_product_detail(url: str, fclient=None, menu=None) -> dict:
    logging.info(f"상품 상세 핸들러 진입: url={url}, menu={menu}")
    """
    상품 상세 페이지 처리 핸들러
    - title 탐지 -> 클릭 -> 추출이 주요 목적
    - URL에서 ItemCode 추출하여 handler 적격성 판단
    - menu_name은 input_urls의 menu 컬럼 값 사용
    - 일반 상품과 soho 상품 모두 동일한 구조로 처리
    - 타임아웃 및 재시도 메커니즘 포함
    """
    logging.info(f"상품 상세 핸들러 진입: url={url}, menu={menu}")
    
    # URL에서 ItemCode 추출 (handler 적격성 판단용)
    m = re.search(r'ItemCode=(\d+)', url)
    if not m:
        return None  # 일반 스크래핑으로 fallback
    
    item_code = m.group(1)

    # 재시도 메커니즘 설정
    max_retries = 3
    base_timeout = 60000  # 60초 기본 타임아웃
    
    for attempt in range(max_retries):
        try:
            logging.info(f"상품 상세 페이지 진입 시도 {attempt + 1}/{max_retries}: url={url}, item_code={item_code}")
            
            # 시도별로 다른 로딩 전략 적용
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
            
            # 완전히 새로운 브라우저 세션으로 시작
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # 페이지 로드
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)
                await page.wait_for_timeout(extra_wait)
                
                # HTTP 상태 코드 확인 및 로깅
                status_code = response.status if response else None
                if status_code:
                    if status_code >= 400:
                        logging.error(f"❌ 상품 상세 ({url}): HTTP {status_code} 오류")
                    elif status_code >= 300:
                        logging.warning(f"⚠️ 상품 상세 ({url}): HTTP {status_code} 리다이렉트")
                    else:
                        logging.info(f"✅ 상품 상세 ({url}): HTTP {status_code} 성공")
                else:
                    logging.debug(f"🔍 상품 상세 ({url}): 상태 코드 정보 없음")
                
                # 메인 콘텐츠 영역 로드 대기
                try:
                    await page.wait_for_selector("#cfmClContents", timeout=10000)
                    logging.info("메인 콘텐츠 영역 로드 완료")
                except:
                    logging.warning("메인 콘텐츠 영역 로드 실패, 계속 진행")
                
                # 페이지 제목 추출
                title = await page.evaluate("""
                    () => {
                        const titleEl = document.querySelector('h1') || document.querySelector('.product-title') || document.querySelector('h2');
                        return titleEl ? titleEl.textContent.trim() : 'No title found';
                    }
                """)
                
                logging.info(f"상품 상세 페이지 제목 추출: '{title}'")
                
                # 아코디언 트리거 탐지
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
                
                logging.info(f"상품 상세 페이지 아코디언 트리거 {len(accordion_triggers)}개 발견")
                
                # 모든 아코디언 트리거 클릭하여 숨겨진 내용 모두 표시
                if accordion_triggers:
                    for i, trigger in enumerate(accordion_triggers, 1):
                        try:
                            trigger_id = trigger['id']
                            trigger_text = trigger['text']
                            
                            logging.info(f"상품 상세 아코디언 클릭 {i}/{len(accordion_triggers)}: {trigger_id} - '{trigger_text}'")
                            await page.click(f"#{trigger_id}", timeout=5000)
                            await page.wait_for_timeout(1000)
                            logging.info(f"상품 상세 아코디언 클릭 성공: {trigger_id}")
                            
                        except Exception as e:
                            logging.warning(f"상품 상세 아코디언 클릭 실패 {i}/{len(accordion_triggers)}: {trigger_id}, 에러: {str(e)}")
                            continue
                
                # 추천 컨텐츠 추출 (recommendations)
                combined_html = ""
                markdown_text = ""
                additional_details = []  # N-pdt-compare-column 자세히 보기로 추출된 하위 상품들
                
                try:
                    logging.info(f"상품 상세 recommendations 추출 시작: url={url}")
                    
                    # 기본 대기 시간
                    await page.wait_for_timeout(3000)
                    
                    # JS에서 필요한 정보를 수집하고 Python에서 정제
                    raw_reco = await page.evaluate("""() => {
                        const abs = (u) => {
                            try { const a = document.createElement('a'); a.href = u; return a.href; } catch(e){ return u; }
                        };
                        // top
                        const top = Array.from(document.querySelectorAll('ul.three-list li a')).map(a => ({
                            title: (a.textContent||'').trim(),
                            url: abs(a.getAttribute('href')||a.href||'')
                        })).filter(x => x.title && x.url);

                        // bundle_option
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

                        // plan_variant (공유 아이콘 제외, javascript 제외)
                        const planVariant = Array.from(document.querySelectorAll('.N-head-btn-area a'))
                            .filter(a => !a.classList.contains('icon'))
                            .map(a => ({
                                title: (a.textContent||'').trim(),
                                url: abs(a.getAttribute('href')||a.href||'')
                            }))
                            .filter(x => x.title && x.url && !x.url.startsWith('javascript:'));

                        // other_plan / extra_service
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
                            
                    # 데이터 검증 및 로깅
                    if raw_reco and any([
                        len(raw_reco.get('top', [])) > 0,
                        len(raw_reco.get('bundle', [])) > 0,
                        len(raw_reco.get('planVariant', [])) > 0,
                        len(raw_reco.get('otherPlan', [])) > 0,
                        len(raw_reco.get('extraService', [])) > 0
                    ]):
                        logging.info(f"✅ Recommendations 추출 성공: url={url}, top={len(raw_reco.get('top', []))}, bundle={len(raw_reco.get('bundle', []))}, planVariant={len(raw_reco.get('planVariant', []))}, otherPlan={len(raw_reco.get('otherPlan', []))}, extraService={len(raw_reco.get('extraService', []))}")
                    else:
                        # 실패 원인 분석을 위한 디버깅 정보 수집
                        debug_info = await page.evaluate("""() => {
                            const debug = {};
                            
                            // 각 선택자별 요소 개수 확인
                            debug.top_count = document.querySelectorAll('ul.three-list li a').length;
                            debug.bundle_trigger1 = document.querySelector('#trigger1-1-1') ? document.querySelector('#trigger1-1-1').querySelectorAll('.bxslider li a').length : 0;
                            debug.bundle_trigger2 = document.querySelector('#trigger1-1-2') ? document.querySelector('#trigger1-1-2').querySelectorAll('.bxslider li a').length : 0;
                            debug.plan_variant_count = document.querySelectorAll('.N-head-btn-area a').length;
                            debug.plan_variant_icon_count = document.querySelectorAll('.N-head-btn-area a.icon').length;
                            debug.compare_list_count = document.querySelectorAll('ul.N-compare-suggest-list li a').length;
                            
                            // 실제 HTML 구조 확인 (첫 번째 요소만)
                            debug.top_sample = document.querySelector('ul.three-list li a') ? document.querySelector('ul.three-list li a').outerHTML.substring(0, 200) : '없음';
                            debug.bundle_sample = document.querySelector('#trigger1-1-1 .bxslider li a') ? document.querySelector('#trigger1-1-1 .bxslider li a').outerHTML.substring(0, 200) : '없음';
                            
                            return debug;
                        }""")
                        
                        logging.warning(f"⚠️ Recommendations 추출 실패: url={url}")
                        logging.warning(f"   - top: {debug_info.get('top_count', 0)}개, bundle: {debug_info.get('bundle_trigger1', 0)}+{debug_info.get('bundle_trigger2', 0)}개")
                        logging.warning(f"   - plan_variant: {debug_info.get('plan_variant_count', 0)}개 (icon 제외: {debug_info.get('plan_variant_count', 0) - debug_info.get('plan_variant_icon_count', 0)}개)")
                        logging.warning(f"   - compare_list: {debug_info.get('compare_list_count', 0)}개")
                        logging.warning(f"   - top 샘플: {debug_info.get('top_sample', 'N/A')}")
                        logging.warning(f"   - bundle 샘플: {debug_info.get('bundle_sample', 'N/A')}")
                        
                        raw_reco = {'top': [], 'bundle': [], 'planVariant': [], 'otherPlan': [], 'extraService': []}

                    # Python 측 정제 및 포맷 통일
                    def to_abs(u: str) -> str:
                        if not u:
                            return ''
                        if u.startswith('http'):
                            return u
                        if u.startswith('/'):
                            return f"https://product.kt.com{u}"
                        return u

                    def to_murl(u: str) -> str:
                        if not u or not u.startswith('http'):
                            return ''
                        m = u.replace('https://product.kt.com', 'https://m.product.kt.com')
                        # wDic 경로를 mDic로 변환
                        m = m.replace('/wDic/', '/mDic/')
                        return m

                    recommendations_list = []

                    # top
                    top_count = 0
                    top_raw = raw_reco.get('top', [])
                    for item in top_raw[:10]:
                        url_abs = to_abs(item.get('url', ''))
                        if url_abs:
                            recommendations_list.append({
                                'kind': 'top',
                                'name': item.get('title', ''),
                                'desc': '',
                                'url': url_abs,
                                'murl': to_murl(url_abs)
                            })
                            top_count += 1

                    # bundle_option (중복 제거 by url)
                    seen = set()
                    bundle_count = 0
                    bundle_raw = raw_reco.get('bundle', [])
                    for item in bundle_raw[:20]:
                        url_abs = to_abs(item.get('url', ''))
                        if not url_abs or url_abs in seen:
                            continue
                        seen.add(url_abs)
                        desc = item.get('desc') or ''
                        recommendations_list.append({
                            'kind': 'bundle_option',
                            'name': item.get('title', ''),
                            'desc': desc,
                            'url': url_abs,
                            'murl': to_murl(url_abs)
                        })
                        bundle_count += 1

                    # plan_variant (공유 링크 제거됨)
                    plan_variant_count = 0
                    plan_variant_raw = raw_reco.get('planVariant', [])
                    for item in plan_variant_raw[:10]:
                        url_abs = to_abs(item.get('url', ''))
                        if url_abs and not url_abs.startswith('javascript:'):
                            recommendations_list.append({
                                'kind': 'plan_variant',
                                'name': item.get('title', ''),
                                'desc': '',
                                'url': url_abs,
                                'murl': to_murl(url_abs)
                            })
                            plan_variant_count += 1

                    # other_plan
                    other_plan_count = 0
                    other_plan_raw = raw_reco.get('otherPlan', [])
                    for item in other_plan_raw[:10]:
                        url_abs = to_abs(item.get('url', ''))
                        if url_abs:
                            recommendations_list.append({
                                'kind': 'other_plan',
                                'name': item.get('title', ''),
                                'desc': '',
                                'url': url_abs,
                                'murl': to_murl(url_abs)
                            })
                            other_plan_count += 1

                    # extra_service
                    extra_service_count = 0
                    extra_service_raw = raw_reco.get('extraService', [])
                    for item in extra_service_raw[:10]:
                        url_abs = to_abs(item.get('url', ''))
                        if url_abs:
                            recommendations_list.append({
                                'kind': 'extra_service',
                                'name': item.get('title', ''),
                                'desc': '',
                                'url': url_abs,
                                'murl': to_murl(url_abs)
                            })
                            extra_service_count += 1

                    recommendations = recommendations_list
                    logging.info(f"상품 상세 총 recommendations: {len(recommendations)}개 (처리됨)")
                    
                except Exception as e:
                    logging.error(f"상품 상세 recommendations 추출 실패: {str(e)}")
                    recommendations = []

                # N-pdt-compare-column 내 "자세히 보기" 링크 추출 및 처리
                try:
                    logging.info(f"상품 상세 N-pdt-compare-column 자세히 보기 추출 시작: url={url}")
                    
                    # N-pdt-compare-column에서 "자세히 보기" 링크 추출
                    detail_links = await page.evaluate("""() => {
                        const abs = (u) => {
                            try { const a = document.createElement('a'); a.href = u; return a.href; } catch(e){ return u; }
                        };
                        
                        const results = [];
                        const columns = document.querySelectorAll('.N-pdt-compare-column');
                        
                        columns.forEach(col => {
                            // btn-reduced 링크 찾기
                            const link = col.querySelector('a.btn-reduced');
                            if (!link) return;
                            
                            // 링크 텍스트가 "자세히 보기"인지 확인
                            const linkText = (link.textContent || '').trim();
                            if (linkText !== '자세히 보기') return;
                            
                            // 상품명 추출 (strong.name)
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
                    
                    if detail_links and len(detail_links) > 0:
                        logging.info(f"✅ N-pdt-compare-column 자세히 보기 링크 {len(detail_links)}개 발견: url={url}")
                        
                        # 추출된 링크들을 재귀적으로 handle_product_detail에 전달
                        for link_info in detail_links:
                            try:
                                # 이름 정제: 줄바꿈, 특수문자 제거
                                clean_name = link_info['name']
                                # 줄바꿈 제거
                                clean_name = re.sub(r'[\r\n]+', ' ', clean_name)
                                # 연속된 공백을 하나로
                                clean_name = re.sub(r'\s+', ' ', clean_name)
                                # 특수문자 제거 (한글, 영문, 숫자, 공백, 슬래시만 허용)
                                clean_name = re.sub(r'[^\w\sㄱ-ㅎㅏ-ㅣ가-힣/\-\(\)]', '', clean_name)
                                clean_name = clean_name.strip()
                                
                                detail_url = link_info['href']
                                
                                logging.info(f"상품 상세 재귀 호출: name='{clean_name}', url={detail_url}")
                                
                                # 재귀적으로 handle_product_detail 호출
                                sub_result = await handle_product_detail(detail_url, fclient=fclient, menu=menu)
                                
                                if sub_result:
                                    # 원래 이름 정보를 메타데이터로 추가
                                    sub_result['parent_product_name'] = clean_name
                                    sub_result['parent_url'] = url
                                    additional_details.append(sub_result)
                                    logging.info(f"✅ 상품 상세 재귀 호출 성공: '{clean_name}'")
                                else:
                                    logging.warning(f"⚠️ 상품 상세 재귀 호출 실패: '{clean_name}'")
                                    
                            except Exception as e:
                                logging.error(f"❌ 상품 상세 재귀 호출 오류: name='{link_info.get('name', 'N/A')}', error={str(e)}")
                                continue
                        
                        # 추가된 상세 정보가 있으면 로깅
                        if additional_details:
                            logging.info(f"✅ 상품 상세 재귀 호출 완료: {len(additional_details)}개 처리됨")
                            # 추가된 정보를 결과에 포함 (나중에 사용할 수 있도록)
                            # 이 정보는 반환값의 일부로 저장됩니다
                        
                    else:
                        logging.debug(f"N-pdt-compare-column 자세히 보기 링크 없음: url={url}")
                    
                except Exception as e:
                    logging.error(f"상품 상세 N-pdt-compare-column 처리 실패: {str(e)}")

                # 모든 아코디언 클릭 후 전체 cfmClContents 내용 수집
                try:
                    logging.info("상품 상세 콘텐츠 수집 시작")
                    combined_html = await page.evaluate("""
                        () => {
                            const mainContent = document.querySelector('#cfmClContents');
                            if (!mainContent) return '';
                            
                            // 제외할 요소들 제거
                            const excludeSelectors = [
                                '#cfmClHeader', '#cfmClFooter', '#cfmClSkip', 
                                'form', '.header', '.footer', '.nav', ".swiper-controls-wrapper",".opage-hashtag-arrow", ".swiper-button-next", ".swiper-button-prev",
                                ".icon.kakao", ".icon.facebook", ".icon.twitter", ".icon.youtube",
                                ".location", ".sns-area", ".opener", "a[onclick*='KT_trackClicks']", '.together-recommend-area',
                                ".N-compare-suggest-list", ".top-three-box", ".tabs",
                            ];
                            
                            // 복사본 생성하여 원본 변경 방지
                            const contentClone = mainContent.cloneNode(true);
                            
                            // 제외 요소들 제거
                            excludeSelectors.forEach(selector => {
                                const elements = contentClone.querySelectorAll(selector);
                                elements.forEach(el => el.remove());
                            });
                            
                            return contentClone.outerHTML;
                        }
                    """)
                    
                    if combined_html:
                        markdown_text = md(combined_html)
                        logging.info(f"상품 상세 콘텐츠 수집 성공: HTML 길이={len(combined_html)}, 마크다운 길이={len(markdown_text)}")
                    else:
                        # fallback
                        logging.warning("상품 상세 메인 콘텐츠 없음, body 전체로 fallback")
                        combined_html = await page.eval_on_selector("body", "el => el.outerHTML")
                        markdown_text = md(combined_html)
                        logging.info(f"상품 상세 fallback 콘텐츠 수집 완료: HTML 길이={len(combined_html)}, 마크다운 길이={len(markdown_text)}")
                        
                except Exception as e:
                    logging.error(f"상품 상세 콘텐츠 수집 실패: {str(e)}")
                    combined_html = ""
                    markdown_text = "콘텐츠 처리에 실패했습니다."

                # 성공적으로 처리된 경우 결과 반환
                logging.info(f"상품 상세 처리 완료: title='{title}', accordion_count={len(accordion_triggers)}, content_length={len(combined_html) if combined_html else 0}, additional_details={len(additional_details)}")
                return {
                    "url": url,
                    "murl": to_murl(url),
                    "title": title,
                    "markdown": markdown_text,
                    "html": combined_html or "",
                    "item_code": item_code,
                    "accordion_count": len(accordion_triggers),
                    "content_length": len(combined_html) if combined_html else 0,
                    "recommendations": recommendations or [],
                    "additional_details": additional_details or [],  # N-pdt-compare-column 자세히 보기로 추출된 하위 상품들
                    "special_processed": True,
                    "playwright_processed": True
                }
                
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"상품 상세 페이지 처리 시도 {attempt + 1} 실패: {str(e)} - 재시도 중...")
                await asyncio.sleep(5)  # 재시도 전 5초 대기
                continue
            else:
                logging.error(f"상품 상세 페이지 처리 최종 실패: {str(e)}")
                return None  # 일반 스크래핑으로 fallback

register_page_handler(
    r'https?://product\.kt\.com/wDic/(soho/)?productDetail\.do\?ItemCode=.*',
    handle_product_detail
)


async def handle_wdic_mobile_list(url: str, fclient, menu=None) -> dict:
    """
    KT 상품사전(wDic) 카테고리 목록 핸들러 (일반/소상공인 모두 지원)
    지원 페이지:
    - 일반 상품: product.kt.com/wDic/index.do?CateCode=6002/6003 등
    - 소상공인: product.kt.com/wDic/soho/index.do?CateCode=7002 등
    
    요구사항:
    - 탭 순회: ul.ui-tab-list 또는 ul.red-select ('추천' 탭 제외)
    - .type-sub-item이 있으면 모든 서브 필터 순회
    - '더보기(.btn-more)'가 사라질 때까지 클릭해 전체 펼침
    - 상세 URL은 '.btns a[href*="productDetail"]'만 사용 (ItemCode 기반)
    - 모든 탭 순회 후 ItemCode 기준 중복 제거
    - 메뉴 구조: {menu}^{탭명}^{서브필터명}^{아이템 제목}
    - 수집된 상세 URL들을 handle_product_detail로 전달하여 datas 구성
    """
    import logging
    from urllib.parse import urljoin
    from playwright.async_api import async_playwright
    from markdownify import markdownify as md

    base_host = 'https://product.kt.com'

    def _to_murl(u: str) -> str:
        if not u or not u.startswith('http'):
            return ''
        m = u.replace('https://product.kt.com', 'https://m.product.kt.com')
        m = m.replace('/wDic/', '/mDic/')
        return m

    async def _capture_list_snapshot(page, base_menu: str = "", tab_text: str = "", sub_filter_text: str = ""):
        """현재 목록 화면의 본문(html, markdown)을 캡처하여 datas/menus에 추가"""
        try:
            # 본문 영역 우선, 없으면 body 전체
            html = await page.evaluate("""
                () => {
                    const root = document.querySelector('#cfmClContents') || document.body;
                    const clone = root.cloneNode(true);
                    // 불필요 요소 제거 (헤더/푸터/스킵, 위치, SNS, 파인드센터 등)
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
            # 메뉴명 구성: menu ^ 탭 ^ 서브필터
            final_menu = (base_menu or "").strip()
            if tab_text:
                final_menu = f"{final_menu}^{tab_text}" if final_menu else tab_text
            if sub_filter_text:
                final_menu = f"{final_menu}^{sub_filter_text}" if final_menu else sub_filter_text
            # 목록 접미사 없이 그대로 사용
            # 결과 추가
            menus.append({ 'menu': final_menu, 'url': page.url, 'murl': _to_murl(page.url) })
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
            logging.info(f"목록 스냅샷 캡처 완료: menu='{final_menu}', html_len={len(html) if html else 0}")
        except Exception as e:
            logging.warning(f"목록 스냅샷 캡처 실패: {str(e)}")

    async def _click_more_until_exhausted(page) -> int:
        """MCP 검증 로직과 완전 동일: JavaScript로 직접 클릭"""
        clicks = 0
        guard = 0
        while guard < 50:
            guard += 1
            try:
                # 클릭 전 li 개수
                before = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")
                
                # MCP와 동일: JavaScript로 버튼 체크 및 직접 클릭
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

                # 클릭 후 li 개수 확인
                after = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")

                # 증가 없으면 추가 대기 후 재확인 (MCP와 동일)
                if after <= before:
                    await page.wait_for_timeout(1500)
                    after = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")

                # 여전히 증가 없고 버튼이 안 보이면 종료
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
            except Exception as e:
                logging.warning(f"더보기 클릭 중 오류: {str(e)}")
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
        except Exception:
            pass

    async def _ensure_type_sub_all(page):
        try:
            changed = await page.evaluate(r"""
                () => {
                    function isVisible(el){
                        if(!el) return false;
                        const style = getComputedStyle(el);
                        return el.offsetParent !== null && style.display !== 'none' && style.visibility !== 'hidden';
                    }
                    const root = document.querySelector('.type-sub-item');
                    if (!root) return false;
                    const cands = Array.from(root.querySelectorAll('a, button, label'));
                    for (const el of cands){
                        const txt = (el.textContent||'').replace(/\s+/g,'').trim();
                        if (txt.includes('전체') && isVisible(el)){
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

    async def _extract_items(page) -> list:
        """MCP 검증 로직과 동일: .plan-list-area .btns a[href*='productDetail']만 수집"""
        items = await page.evaluate("""
            () => {
                const results = [];
                // MCP와 동일: .plan-list-area에서만 수집
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
                    
                    // span 태그를 제외하고 텍스트 추출하는 함수
                    function extractTextWithoutSpan(element) {
                        if (!element) return '';
                        
                        // .title 클래스를 가진 th나 div인 경우, span 제외하고 strong 등의 텍스트만 추출
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
                    
                    let el = anchor.closest('li, tr, .plan-list li, .prd-list li, .result-list li, .list-item, .card, .box');
                    if (el){
                        const t = el.querySelector(titleSelector);
                        if (t) return extractTextWithoutSpan(t);
                    }
                    // 이전 형제 검색
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
                    // 상위에서 검색
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

    menus, datas = [], []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(1200)

        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logging.error(f"❌ wDic 목록 ({url}): HTTP {status_code} 오류")

        # 탭 로드 대기 (여러 선택자 시도)
        try:
            await page.wait_for_selector('ul.ui-tab-list, ul.red-select', timeout=10000)
        except Exception:
            pass

        # 탭 수집 (여러 선택자 대응: ui-tab-list 또는 red-select)
        # '추천' 탭 제외
        tabs = await page.evaluate("""
            () => {
                const arr = [];
                // 여러 탭 컨테이너 선택자 시도
                const selectors = ['ul.ui-tab-list li a', 'ul.red-select li a'];
                let anchors = [];
                for (const sel of selectors) {
                    anchors = Array.from(document.querySelectorAll(sel));
                    if (anchors.length > 0) break;
                }
                
                let idx = 0;
                if (anchors.length === 0) {
                    arr.push({ index: -1, text: '전체' });
                } else {
                    anchors.forEach((a, originalIdx) => {
                        const text = (a.textContent||'').trim();
                        // '추천' 탭 제외
                        if (text === '추천') return;
                        arr.push({ index: originalIdx, text });
                    });
                }
                return arr;
            }
        """)
        if not tabs:
            tabs = [{ 'index': -1, 'text': '전체' }]

        detail_targets = []

        # 초기(기본) 목록 페이지도 캡처
        try:
            await _capture_list_snapshot(page, base_menu=(menu or "").strip())
        except Exception:
            pass

        for tab in tabs:
            try:
                # 탭 클릭 (여러 선택자 대응: JavaScript로 직접 클릭)
                if tab.get('index', -1) >= 0:
                    tab_clicked = await page.evaluate(f"""
                        () => {{
                            // 여러 탭 선택자 시도
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
                        # 네트워크가 안정될 때까지 대기
                        try:
                            await page.wait_for_load_state('networkidle', timeout=5000)
                        except Exception:
                            await page.wait_for_timeout(1200)

                # 상위 필터 '전체' 보정
                await _ensure_filter_all(page)
                await page.wait_for_timeout(800)

                # type-sub-item 확인 및 처리 (모든 서브 필터 순회)
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

                if sub_filters and len(sub_filters) > 0:
                    # 서브 필터가 있으면 모든 필터 순회
                    logging.info(f"탭 '{tab.get('text','')}': 서브 필터 {len(sub_filters)}개 발견, 모두 순회")
                    for sub_filter in sub_filters:
                        try:
                            # 서브 필터 클릭 전 현재 리스트 개수 기록
                            prev_count = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")
                            
                            # 서브 필터 클릭
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
                                # 네트워크가 안정될 때까지 대기 (최대 5초)
                                try:
                                    await page.wait_for_load_state('networkidle', timeout=5000)
                                except Exception:
                                    pass
                                
                                # 추가로 리스트 업데이트 확인 (최대 3초)
                                for _ in range(6):
                                    await page.wait_for_timeout(500)
                                    new_count = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")
                                    if new_count > 0 and new_count != prev_count:
                                        break

                            clicks = await _click_more_until_exhausted(page)
                            items = await _extract_items(page)
                            
                            # 현재 탭+서브필터의 목록 화면도 캡처
                            try:
                                await _capture_list_snapshot(
                                    page,
                                    base_menu=(menu or "").strip(),
                                    tab_text=tab.get('text', '').strip(),
                                    sub_filter_text=sub_filter.get('text', '').strip()
                                )
                            except Exception:
                                pass

                            li_count = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")
                            
                            # 상세링크 0개일 때 방어 로직: 재시도
                            if len(items) == 0:
                                if clicks == 0 and li_count == 0:
                                    # 더보기 클릭이 0회이고 리스트도 없는 경우: 페이지 새로고침 후 재시도
                                    logging.warning(f"⚠️  더보기 클릭 0회, 상세링크 0개 (li={li_count}) - 페이지 새로고침 후 재시도 중...")
                                    await page.reload(timeout=10000)
                                    await page.wait_for_timeout(2000)
                                    try:
                                        await page.wait_for_load_state('networkidle', timeout=5000)
                                    except Exception:
                                        pass
                                    # 서브 필터 다시 클릭
                                    if sub_clicked:
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
                                            await page.wait_for_timeout(2000)
                                    clicks = await _click_more_until_exhausted(page)
                                    items = await _extract_items(page)
                                    li_count = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")
                                elif li_count > 0:
                                    # 리스트는 있지만 상세링크가 없는 경우: 페이지 로드 대기 후 재시도
                                    logging.warning(f"⚠️  상세링크 0개 감지 (li={li_count}), 페이지 로드 재시도 중...")
                                    await page.wait_for_timeout(2000)
                                    try:
                                        await page.wait_for_load_state('networkidle', timeout=5000)
                                    except Exception:
                                        pass
                                    items = await _extract_items(page)
                                
                                if len(items) == 0:
                                    logging.error(f"❌ 재시도 후에도 상세링크 0개: 탭='{tab.get('text','')}', 서브필터='{sub_filter.get('text','')}', clicks={clicks}, li={li_count}")
                            
                            logging.info(f"탭 '{tab.get('text','')}' > 서브필터 '{sub_filter.get('text','')}' 더보기 클릭 {clicks}회, li={li_count}, 상세링크={len(items)}개 수집")

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
                            logging.warning(f"서브 필터 '{sub_filter.get('text','')}' 처리 중 오류: {str(e)}")
                            continue
                else:
                    # 서브 필터 없으면 기존 로직
                    clicks = await _click_more_until_exhausted(page)
                    items = await _extract_items(page)
                    
                    # 현재 탭의 목록 화면도 캡처
                    try:
                        await _capture_list_snapshot(
                            page,
                            base_menu=(menu or "").strip(),
                            tab_text=tab.get('text', '').strip()
                        )
                    except Exception:
                        pass

                    li_count = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")
                    
                    # 상세링크 0개일 때 방어 로직: 재시도
                    if len(items) == 0:
                        if clicks == 0 and li_count == 0:
                            # 더보기 클릭이 0회이고 리스트도 없는 경우: 페이지 새로고침 후 재시도
                            logging.warning(f"⚠️  더보기 클릭 0회, 상세링크 0개 (li={li_count}) - 페이지 새로고침 후 재시도 중...")
                            await page.reload(timeout=10000)
                            await page.wait_for_timeout(2000)
                            try:
                                await page.wait_for_load_state('networkidle', timeout=5000)
                            except Exception:
                                pass
                            clicks = await _click_more_until_exhausted(page)
                            items = await _extract_items(page)
                            li_count = await page.evaluate("document.querySelectorAll('.plan-list-area .plan-list li').length")
                        elif li_count > 0:
                            # 리스트는 있지만 상세링크가 없는 경우: 페이지 로드 대기 후 재시도
                            logging.warning(f"⚠️  상세링크 0개 감지 (li={li_count}), 페이지 로드 재시도 중...")
                            await page.wait_for_timeout(2000)
                            try:
                                await page.wait_for_load_state('networkidle', timeout=5000)
                            except Exception:
                                pass
                            items = await _extract_items(page)
                        
                        if len(items) == 0:
                            logging.error(f"❌ 재시도 후에도 상세링크 0개: 탭='{tab.get('text','')}', clicks={clicks}, li={li_count}")
                    
                    logging.info(f"탭 '{tab.get('text','')}' 더보기 클릭 {clicks}회, li={li_count}, 상세링크={len(items)}개 수집")

                    for it in items:
                        if not it.get('relHref'):
                            continue
                        detail_targets.append({
                            'tab': tab.get('text', ''),
                            'title': it.get('title', '').strip() or '(제목 없음)',
                            'relHref': it['relHref']
                        })
            except Exception as e:
                logging.warning(f"탭 처리 중 오류: {str(e)}")
                continue

        # 중복 제거: ItemCode 기준으로 (URL에서 추출)
        import re
        seen_itemcodes = set()
        unique_targets = []
        for target in detail_targets:
            # URL에서 ItemCode 추출
            match = re.search(r'ItemCode=(\d+)', target['relHref'])
            if match:
                itemcode = match.group(1)
                if itemcode in seen_itemcodes:
                    continue
                seen_itemcodes.add(itemcode)
            unique_targets.append(target)
        
        logging.info(f"중복 제거: 전체 {len(detail_targets)}개 → 유니크 {len(unique_targets)}개")
        detail_targets = unique_targets

        # 상세 처리 (직렬)
        for i, target in enumerate(detail_targets, 1):
            detail_url = urljoin(base_host, target['relHref'])
            try:
                result = await handle_product_detail(detail_url, fclient, menu)
                if not result:
                    logging.warning(f"상세 처리 실패 또는 빈 결과: {detail_url}")
                    continue

                base_menu = (menu or '').strip()
                tab_prefix = target.get('tab', '').strip()
                sub_filter_name = target.get('sub_filter', '').strip()
                title_suffix = target.get('title', '').strip()
                final_menu = base_menu
                if tab_prefix:
                    final_menu = f"{final_menu}^{tab_prefix}" if final_menu else tab_prefix
                if sub_filter_name:
                    final_menu = f"{final_menu}^{sub_filter_name}" if final_menu else sub_filter_name
                if title_suffix:
                    final_menu = f"{final_menu}^{title_suffix}" if final_menu else title_suffix

                menus.append({ 'menu': final_menu or (result.get('title') or ''), 'url': detail_url })
                datas.append(result)
                logging.info(f"[{i}/{len(detail_targets)}] 상세 처리 완료: {detail_url}")
            except Exception as e:
                logging.error(f"상세 처리 중 오류: {detail_url} - {str(e)}")
                continue

        await browser.close()

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

register_page_handler(
    r'https?://product\.kt\.com/wDic/.*index\.do\?CateCode=\d+',
    handle_wdic_mobile_list
)


async def handle_gigagenie_detail(url: str, fclient=None, menu=None) -> dict:
    """
    기가지니 서비스 상세 페이지(2뎁스 탭/버튼 동적 순회) 크롤링 및 마크다운/HTML 반환
    - 2뎁스 버튼(ul#depth2Level li button)들을 모두 순회하며 클릭
    - 각 버튼 클릭 후 본문(div.fjbInnerTabBox.fjbTabCon*.on) 내용을 추출
    - # {탭명}\n... 형식으로 마크다운 누적
    - depth2Level이 없는 경우, 기본 콘텐츠만 추출
    - 반환값: {url, markdown, html, special_processed, playwright_processed}
    """
    import re
    from markdownify import markdownify as md
    import logging
    from playwright.async_api import async_playwright

    def clean_img_alt(md_text):
        # alt에 <가 포함된 경우 alt를 비움 (줄바꿈 포함)
        def repl(match):
            alt = match.group(1)
            url = match.group(2)
            if '<' in alt:
                return f"![]({url})"
            else:
                return match.group(0)
        return re.sub(r'!\[(.*?)\]\((.*?)\)', repl, md_text, flags=re.DOTALL)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 기가지니 상세 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 기가지니 상세 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 기가지니 상세 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 기가지니 상세 ({url}): 상태 코드 정보 없음")

        # 2뎁스 버튼 목록 추출
        buttons = await page.query_selector_all("#depth2Level li button")
        markdown_content = ""
        html_content = ""
        if buttons and len(buttons) > 0:
            tab_infos = []
            for btn in buttons:
                # 탭명 추출 (span 텍스트)
                span = await btn.query_selector("span")
                tab_name = (await span.inner_text()).strip() if span else (await btn.inner_text()).strip()
                tab_infos.append({"button": btn, "tab_name": tab_name})

            for tab in tab_infos:
                btn = tab["button"]
                tab_name = tab["tab_name"]
                try:
                    await btn.click()
                    await page.wait_for_timeout(1200)
                    # 본문 추출: div.fjbInnerTabBox.fjbTabCon*.on (on 클래스가 붙은 것만)
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
                    logging.warning(f"탭 '{tab_name}' 클릭/추출 실패: {str(e)}")
                    markdown_content += f"# {tab_name}\n\n(탭 추출 실패)\n\n"
                    html_content += f"<h1>{tab_name}</h1>\n(탭 추출 실패)\n\n"
        else:
            # depth2Level이 없는 경우: 기본 콘텐츠만 추출
            content_div = await page.query_selector("div.fjbInnerTabBox[class*='fjbTabCon'][class~='on']")
            if not content_div:
                # on이 없으면 fjbTabCon* 중 첫 번째 사용
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
        # 전체 페이지 HTML도 저장
        page_html = await page.content()
        await browser.close()

    return {
        "url": url,
        "markdown": markdown_content.strip(),
        "html": html_content.strip(),
        "special_processed": True,
        "playwright_processed": True
    }

register_page_handler(
    r'https?://gigagenie\.kt\.com/whyGenieServiceDetail\.do\?serviceCate=.*',
    handle_gigagenie_detail
)

async def handle_gigagenie_faq_playwright(url: str, fclient) -> dict:
    """
    Playwright로 기가지니 자주하는질문 전체 페이지(상품별 버튼, 페이지네이션 포함) Q/A 추출 핸들러
    - 상품별 버튼을 클릭하여 각 상품의 FAQ 추출
    - selectFaqList() 함수를 사용한 페이지네이션 처리
    - 질문/답변 구조: ul#faqList li > a.fjbQuestion (클릭) + div.fjbAnser
    - 타임아웃 시 완전한 브라우저 세션 재시작 메커니즘 포함
    """
    logging.info(f"기가지니 FAQ 핸들러 진입: url={url}")
    
    # FAQ는 상태 보존이 중요하므로 단일 시도로 처리
    # 타임아웃 발생 시에만 완전 재시작
    logging.info(f"기가지니 FAQ 페이지 진입: url={url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # FAQ 페이지 로드 (충분한 타임아웃 설정)
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)  # 충분한 대기 시간
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 기가지니 FAQ ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 기가지니 FAQ ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 기가지니 FAQ ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 기가지니 FAQ ({url}): 상태 코드 정보 없음")
        
        # 페이지 로딩 상태 확인
        try:
            await page.wait_for_selector("button[class*='fjbCard']", timeout=30000)
            logging.info("FAQ 페이지 로딩 완료")
        except Exception as e:
            logging.warning(f"FAQ 페이지 로딩 대기 실패: {e}, 계속 진행")

        markdown_body = ""
        all_qa_list = []
        
        # 기본 페이지 내용 추출 (FAQ 제외) - Playwright 사용
        try:
            logging.info("기본 페이지 내용 추출 시작")
            from markdownify import markdownify as md
            
            # FAQ 관련 요소들 및 불필요한 요소 제거
            faq_selectors = [
                # FAQ 관련
                'ul#faqList', '.faqList', 
                '.accordion-area', '.accordion',
                '.faq_box', '.faq', '.faq-list', '.faq-item', 
                '.inquiry', '.answer', '.faqClass',
                'img[src*="faq"]', 'img[src*="FAQ"]',
                'a[href*="faq"]', 'a[href*="FAQ"]',
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
            logging.info(f"기본 페이지 내용 추출 완료: 마크다운 {len(page_markdown)}자, HTML {len(page_html)}자")
        except Exception as e:
            logging.error(f"기본 페이지 내용 추출 중 오류: {e}")
            page_markdown = ""
            page_html = ""
        
        # FAQ 추출을 위해 페이지 새로고침
        await page.reload()
        await page.wait_for_timeout(3000)
        
        # 1. 상품별 버튼 목록 추출 (다양한 클래스명 고려)
        product_buttons = await page.query_selector_all("button[class*='fjbCard']")
        logging.info(f"총 {len(product_buttons)}개 상품 버튼 발견. FAQ 추출 시작")
        
        for product_idx in range(len(product_buttons)):
            try:
                # 항상 최신 버튼 핸들로 재조회
                product_buttons = await page.query_selector_all("button[class*='fjbCard']")
                button = product_buttons[product_idx]
                # 상품명 추출
                product_name = await button.get_attribute("id-name")
                if not product_name:
                    product_name = await button.inner_text()
                    product_name = product_name.replace('\n', ' ').strip()
                
                logging.info(f"상품 {product_idx + 1}/{len(product_buttons)} 처리 시작: {product_name}")
                
                # 상품 버튼 클릭
                await button.click()
                await page.wait_for_timeout(2000)
                
                # 2. 페이지네이션 처리 (selectFaqList 함수 사용)
                page_num = 1
                while True:
                    logging.info(f"  {product_name} - 페이지 {page_num} 처리 중...")
                    # 올바른 셀렉터 사용: ul#faqList li
                    qa_items = await page.query_selector_all("ul#faqList li")
                    
                    # FAQ가 없으면 새로고침 후 동일 상품/동일 페이지로 복원해서 한 번 더 시도
                    if not qa_items:
                        logging.warning(f"  페이지 {page_num}에서 FAQ 항목이 없음. 새로고침 후 재시도")
                        try:
                            await page.reload()
                            await page.wait_for_timeout(3000)
                            # 상품 버튼 다시 클릭 (새로고침 후)
                            product_buttons = await page.query_selector_all("button[class*='fjbCard']")
                            # 새로고침 후 product_buttons 길이 체크
                            if product_idx >= len(product_buttons):
                                logging.warning(f"  새로고침 후 상품 버튼 개수가 줄어듦. 원래: {product_idx + 1}개, 현재: {len(product_buttons)}개. 해당 상품 건너뜀")
                                break
                            button = product_buttons[product_idx]
                            await button.click()
                            await page.wait_for_timeout(2000)
                            # 해당 페이지로 이동
                            if page_num > 1:
                                await page.evaluate(f"selectFaqList({page_num})")
                                await page.wait_for_timeout(2000)
                            # 다시 FAQ 리스트 쿼리
                            qa_items = await page.query_selector_all("ul#faqList li")
                            if not qa_items:
                                logging.warning(f"  새로고침 후에도 페이지 {page_num} FAQ 없음. 다음으로 이동")
                                break
                        except Exception as e:
                            logging.error(f"  새로고침 후 복원 실패: {str(e)}. 해당 상품 건너뜀")
                            break
                    
                    logging.info(f"  페이지 {page_num}에서 {len(qa_items)}개 FAQ 항목 발견")
                    
                    for qa_idx, qa_item in enumerate(qa_items):
                        try:
                            # 질문 링크 찾기
                            question_link = await qa_item.query_selector("a.fjbQuestion")
                            if not question_link:
                                logging.warning(f"    FAQ {qa_idx + 1}: 질문 링크 없음")
                                continue
                            
                            # 카테고리 추출
                            category_elem = await question_link.query_selector("span.fjbCategory")
                            category = await category_elem.inner_text() if category_elem else ""
                            
                            # 질문 제목 추출
                            title_elem = await question_link.query_selector("span.fjbTit")
                            question_title = await title_elem.inner_text() if title_elem else ""
                            
                            # 전체 질문 텍스트 (카테고리 + 제목)
                            if category and question_title:
                                question = f"[{category}] {question_title}"
                            else:
                                question = question_title or (await question_link.inner_text())
                            
                            # 답변 요소 확인 (아코디언 클릭 없이 바로 추출)
                            answer_elem = await qa_item.query_selector("div.fjbAnser")
                            answer = ""
                            if answer_elem:
                                answer_p = await answer_elem.query_selector("p")
                                if answer_p:
                                    answer = await answer_p.inner_text()
                                else:
                                    answer = await answer_elem.inner_text()
                                # HTML 엔티티 정리
                                answer = answer.replace('&gt;', '>').replace('&lt;', '<').replace('&nbsp;', ' ')
                                # 불필요한 공백 정리
                                answer = re.sub(r'\s+', ' ', answer).strip()
                            else:
                                logging.warning(f"    FAQ {qa_idx + 1}: 답변 요소 없음")
                            
                            # 유효한 Q/A만 추가
                            if question.strip() and answer.strip():
                                # 구조화된 데이터로만 추가 (마크다운 제거)
                                all_qa_list.append({
                                    "product": product_name,
                                    "category": category,
                                    "question": question.strip(),
                                    "answer": answer.strip(),
                                    "page": page_num
                                })
                                
                                logging.info(f"    FAQ {qa_idx + 1} 추출 완료: {question[:50]}...")
                            else:
                                logging.warning(f"    FAQ {qa_idx + 1} 추출 실패: 질문='{question[:30]}', 답변='{answer[:30]}'")
                        except Exception as e:
                            logging.error(f"  FAQ 항목 {qa_idx + 1} 추출 실패: {str(e)}")
                            continue
                        
                        # TEST CODE
                        break
                    
                    # 다음 페이지 확인 및 이동 (selectFaqList 함수 사용)
                    page_num += 1
                    next_page_selector = f"a[onclick*='selectFaqList({page_num})']"
                    try:
                        next_page_link = await page.query_selector(next_page_selector)
                        if next_page_link and await next_page_link.is_visible():
                            logging.info(f"  페이지 {page_num}로 이동 (selectFaqList)")
                            await next_page_link.click()
                            await page.wait_for_timeout(10000)  # 페이지네이션 클릭 후 충분히 대기
                        else:
                            # JavaScript 함수 직접 실행
                            try:
                                await page.evaluate(f"selectFaqList({page_num})")
                                await page.wait_for_timeout(10000)  # JS로 이동 후에도 충분히 대기
                                # 실제로 페이지가 변경되었는지 확인
                                new_qa_items = await page.query_selector_all("ul#faqList li")
                                if new_qa_items:
                                    logging.info(f"  페이지 {page_num}로 이동 성공 (JavaScript 직접 실행)")
                                else:
                                    logging.info(f"  페이지 {page_num}가 없어 다음 상품으로 이동")
                                    break
                            except Exception as e:
                                logging.info(f"  페이지 {page_num} JavaScript 실행 실패: {str(e)}")
                                break
                    except Exception as e:
                        logging.info(f"  페이지 {page_num} 이동 실패: {str(e)}")
                        break
                
                product_qa_count = len([qa for qa in all_qa_list if qa['product'] == product_name])
                logging.info(f"상품 {product_idx + 1}/{len(product_buttons)} 처리 완료: {product_name} (FAQ {product_qa_count}개)")
            except Exception as e:
                logging.error(f"상품 {product_idx + 1} 처리 실패: {str(e)}")
                continue

        await browser.close()

    logging.info(f"기가지니 FAQ 전체 추출 완료: 총 상품 {len(product_buttons)}개, 총 FAQ {len(all_qa_list)}개")
    logging.info(f"qa_list 준비 완료: {len(all_qa_list)}개 FAQ")
    
    return {
        "url": url,  # URL 필드 추가 (url.txt 생성용)
        "markdown": page_markdown,  # FAQ 제외한 일반 페이지 내용
        "html": page_html,
        "qa_list": all_qa_list,  # FAQ 데이터만 별도 저장
        "total_products": len(product_buttons) if 'product_buttons' in locals() else 0,
        "total_qa": len(all_qa_list),
        "special_processed": True,
        "playwright_processed": True
    }

register_page_handler(
    r'https?://gigagenie\.kt\.com/whyGenieFaq\.do',
    handle_gigagenie_faq_playwright
)
async def handle_gigagenie_news_list(url: str, fclient, menu: str = None) -> dict:
    """
    기가지니 지니소식 목록 Playwright 핸들러
    - "더보기" 버튼을 끝까지 클릭해 전체 게시물을 노출
    - 목록에서 seq, 제목을 추출해 상세 URL을 구성
    - 입력 menu 값에 게시물 제목을 붙여 menu^{title} 형태로 메뉴 경로 구성
    - 각 상세 페이지에서 제목, 날짜(startdate), 본문을 추출하여 Markdown/HTML 생성
    """
    import logging
    import re
    import asyncio
    from markdownify import markdownify as md
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

    logging.info(f"기가지니 지니소식 목록 핸들러 진입: url={url}, menu={menu}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        response = await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(4000)

        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 기가지니 지니소식 목록 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 기가지니 지니소식 목록 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 기가지니 지니소식 목록 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 기가지니 지니소식 목록 ({url}): 상태 코드 정보 없음")

        load_more_selector = "button#btn_more"
        try:
            while True:
                load_more_button = await page.query_selector(load_more_selector)
                if not load_more_button:
                    logging.info("더보기 버튼이 없어 모든 게시물이 노출된 것으로 판단")
                    break
                # is_visible 체크를 추가하여 display:none 상태에서 불필요한 클릭 시도를 방지
                if not await load_more_button.is_visible():
                    logging.info("더보기 버튼이 숨겨져 있어 로딩 완료로 판단")
                    break
                if not await load_more_button.is_enabled():
                    logging.info("더보기 버튼이 비활성화되어 로딩 완료")
                    break
                try:
                    await load_more_button.click()
                except PlaywrightTimeoutError:
                    logging.warning("더보기 버튼 클릭 중 타임아웃 발생 → 로딩 완료로 판단")
                    break
                logging.info("더보기 버튼 클릭 → 추가 게시물 로딩 대기")
                await page.wait_for_timeout(2000)
        except PlaywrightTimeoutError as timeout_err:
            logging.warning(f"더보기 버튼 처리 중 타임아웃 발생: {str(timeout_err)}")
        except Exception as e:
            logging.warning(f"더보기 버튼 처리 중 예외 발생: {str(e)}")

        card_selector = "ul#bloglist li"
        try:
            await page.wait_for_selector(card_selector, timeout=5000)
        except PlaywrightTimeoutError:
            logging.warning("지니소식 카드가 일정 시간 내 로드되지 않았습니다 (타임아웃)")
        except Exception as wait_err:
            logging.warning(f"지니소식 카드 대기 중 예외 발생: {wait_err}")
        cards = await page.query_selector_all(card_selector)
        logging.info(f"지니소식 카드 {len(cards)}개 발견")

        base_menu = menu or "지니소식"
        datas = []
        menus = []

        semaphore = asyncio.Semaphore(5)

        async def process_detail(detail_url: str, parent_menu: str, original_idx: int):
            async with semaphore:
                detail_page = await browser.new_page()

                try:
                    detail_response = await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=40000)
                    await detail_page.wait_for_timeout(3000)

                    detail_status = detail_response.status if detail_response else None
                    if detail_status:
                        if detail_status >= 400:
                            logging.error(f"❌ 지니소식 상세 ({detail_url}): HTTP {detail_status} 오류")
                        elif detail_status >= 300:
                            logging.warning(f"⚠️ 지니소식 상세 ({detail_url}): HTTP {detail_status} 리다이렉트")
                        else:
                            logging.info(f"✅ 지니소식 상세 ({detail_url}): HTTP {detail_status} 성공")

                    title_selector = "h3.cfmOllehNewsTitle div.inner"
                    date_selector = "h3.cfmOllehNewsTitle div.inner span.date"

                    title_element = await detail_page.query_selector(title_selector)
                    raw_title = (await title_element.inner_text()) if title_element else ""
                    title_clean = re.sub(r"\s+", " ", raw_title).strip()

                    date_element = await detail_page.query_selector(date_selector)
                    raw_date = (await date_element.inner_text()) if date_element else ""
                    date_text = raw_date.strip()

                    startdate = "0000-00-00"
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
                        logging.warning(f"본문 콘텐츠를 찾지 못했습니다: {detail_url}")

                    markdown_content = md(inner_html, heading_style="ATX") if inner_html else ""
                    html_content = inner_html or ""

                    title_for_menu = sanitize_filename(title_clean) if title_clean else "지니소식"
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

                    logging.info(f"지니소식 상세 추출 완료: title='{title_clean}', startdate='{startdate}'")

                except Exception as detail_err:
                    logging.error(f"지니소식 상세 페이지 처리 실패 ({detail_url}): {str(detail_err)}")
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
                    logging.warning("썸네일 링크가 없어 카드 건너뜀")
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
                    logging.warning("상세 URL을 구성할 수 없어 카드 건너뜀")
                    continue

                await process_detail(detail_url, base_menu, idx)

            except Exception as card_err:
                logging.error(f"지니소식 카드 처리 실패: {str(card_err)}")
                continue
        await browser.close()

    logging.info(f"기가지니 지니소식 목록 처리 완료: 총 {len(datas)}개 게시물")

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
# =========================
# 8. 고객문의 FAQ 전체 페이지 추출 핸들러
# =========================

async def handle_membership_faq_all_playwright(url: str, fclient, menu=None) -> dict:
    """
    KT 멤버십 FAQ 페이지에서 iframe을 통해 모든 FAQ Q/A를 추출하는 handler
    메인 페이지 -> iframe 접근 -> FAQ 데이터 추출
    """
    logging.info(f"KT 멤버십 FAQ 핸들러 진입: url={url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)
        
        # HTTP 상태 코드 확인 및 로깅
        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 멤버십 FAQ ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 멤버십 FAQ ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 멤버십 FAQ ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 멤버십 FAQ ({url}): 상태 코드 정보 없음")

        markdown_body = ""
        all_qa_list = []
        seen_questions = set()  # 중복 제거를 위한 질문 추적
        
        # 기본 페이지 내용 추출 (FAQ 제외) - Playwright 사용
        try:
            logging.info("기본 페이지 내용 추출 시작")
            from markdownify import markdownify as md
            
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
            logging.info(f"기본 페이지 내용 추출 완료: 마크다운 {len(page_markdown)}자, HTML {len(page_html)}자")
        except Exception as e:
            logging.error(f"기본 페이지 내용 추출 중 오류: {e}")
            page_markdown = ""
            page_html = ""
        
        # FAQ 추출을 위해 페이지 새로고침
        await page.reload()
        await page.wait_for_timeout(3000)

        # iframe 찾기 및 접근
        iframe_selector = "iframe#cpEvent"
        iframe_element = await page.query_selector(iframe_selector)
        
        if not iframe_element:
            logging.error("FAQ iframe을 찾을 수 없습니다")
            await browser.close()
            return {
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
        logging.info(f"발견된 iframe src: {iframe_src}")

        # iframe의 frame 객체 가져오기
        frame = await iframe_element.content_frame()
        if not frame:
            logging.error("iframe의 frame 컨텐츠에 접근할 수 없습니다")
            await browser.close()
            return {
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
            logging.info("iframe 로딩 완료")
        except Exception as e:
            logging.warning(f"iframe 로딩 대기 중 타임아웃: {str(e)}")
            # 계속 진행

        logging.info("iframe 접근 성공, FAQ 데이터 추출 시작")
        await page.wait_for_timeout(5000)  # iframe 로딩 대기 시간 증가



        await frame.wait_for_timeout(2000)  # 페이지 로딩 대기

        # 페이지네이션을 통한 모든 페이지 처리
        page_num = 1
        max_pages = 100  # 충분한 최대 페이지 제한
        visited_first_questions = set()  # 순환 감지를 위한 첫 번째 질문 추적
        
        while page_num <= max_pages:
            logging.info(f"페이지 {page_num} 처리 중...")
            
            # 현재 페이지의 accordion FAQ 항목들 추출 (iframe 내에서)
            accordion_triggers = await frame.query_selector_all('.accordion-trigger')
            
            logging.info(f"페이지 {page_num}에서 {len(accordion_triggers)}개 accordion FAQ 항목 발견")
            
            if not accordion_triggers:
                logging.info("더 이상 FAQ 항목이 없습니다.")
                break
            
            # 순환 감지: 첫 번째 질문으로 이미 방문한 페이지인지 확인
            try:
                first_trigger = accordion_triggers[0]
                first_question_element = await first_trigger.query_selector('.qna span')
                if first_question_element:
                    first_question = await first_question_element.inner_text()
                    if first_question.strip() in visited_first_questions:
                        logging.info(f"순환 감지: 이미 처리한 페이지 (첫 번째 질문: '{first_question[:50]}...')")
                        break
                    visited_first_questions.add(first_question.strip())
            except Exception as e:
                logging.warning(f"순환 감지 중 오류: {str(e)}")
            

            
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
                        logging.warning(f"FAQ 답변 추출 실패: {str(e)}")
                    
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
                        
                        logging.info(f"페이지 {page_num} FAQ {idx + 1} 추출 완료: {question[:50]}...")
                    elif question.strip():
                        logging.info(f"페이지 {page_num} 중복 FAQ 건너뜀: {question[:50]}...")
                    else:
                        logging.warning(f"페이지 {page_num} FAQ {idx + 1} 질문이 비어있음")
                        
                except Exception as e:
                    logging.error(f"FAQ 항목 {idx + 1} 처리 실패: {str(e)}")
                    continue
            
            # 다음 페이지로 이동 시도 (동적 페이지네이션)
            try:
                logging.info("다음 페이지 링크 찾는 중...")
                
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
                                logging.info(f"다음 페이지 링크 발견: '{link_text}' (현재: {current_page_num})")
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
                                logging.info(f"페이지 이동 링크 발견: '{link_text}'")
                                break
                        except Exception as e:
                            continue
                
                if next_link:
                    logging.info("페이지 이동 시도")
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
                                logging.info(f"페이지 이동 확인됨: '{current_first_question[:30]}...' → '{new_first_question[:30]}...'")
                    except:
                        pass
                    
                    if not page_changed:
                        logging.warning("페이지 이동 실패 - 같은 내용")
                        break
                    
                    await frame.wait_for_timeout(1000)
                    
                    page_num += 1  # 페이지 번호는 단순히 카운터로만 사용
                else:
                    logging.info("더 이상 페이지가 없습니다.")
                    break
                    
            except Exception as e:
                logging.error(f"페이지 이동 중 오류: {str(e)}")
                break

        await browser.close()
        
        logging.info(f"FAQ 추출 완료: 총 {len(all_qa_list)}개 FAQ")
        logging.info(f"qa_list 준비 완료: {len(all_qa_list)}개 FAQ")

    return {
        "url": url,  # URL 필드 추가 (url.txt 생성용)
        "markdown": page_markdown,  # FAQ 제외한 일반 페이지 내용
        "html": page_html,
        "qa_list": all_qa_list,
        "total_categories": 1,  # 단일 페이지에서 추출
        "total_qa": len(all_qa_list),
        "special_processed": True,
        "playwright_processed": True
    }

# 핸들러 등록 - 메인 주소로 등록
register_page_handler(
    r'https?://membership\.kt\.com/guide/faq/FAQList\.do',
    handle_membership_faq_all_playwright
)

# =========================
# 8. KT 이벤트 관련 핸들러
# =========================

async def handle_kt_event_main(url: str, fclient, menu=None) -> dict:
    logging.info(f"KT 이벤트 메인 핸들러 진입: url={url}, menu={menu}")
    """
    KT 이벤트 메인 페이지 핸들러
    https://event.kt.com/html/event/ongoing_event_list.html
    """
    from playwright.async_api import async_playwright
    import re
    from datetime import datetime
    
    logging.info(f"🎯 KT 이벤트 메인 페이지 처리: {url}")
    
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
            
            # HTTP 상태 코드 확인 및 로깅
            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logging.error(f"❌ KT 이벤트 메인 ({url}): HTTP {status_code} 오류")
                elif status_code >= 300:
                    logging.warning(f"⚠️ KT 이벤트 메인 ({url}): HTTP {status_code} 리다이렉트")
                else:
                    logging.info(f"✅ KT 이벤트 메인 ({url}): HTTP {status_code} 성공")
            else:
                logging.debug(f"🔍 KT 이벤트 메인 ({url}): 상태 코드 정보 없음")
            
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
                    logging.info(f"🔄 페이지 {page_num}로 이동 시도 중...")
                    
                    # 페이지 이동 시도
                    await page.evaluate(f"""() => {{
                        const pageLinks = document.querySelectorAll('a[data-page="{page_num}"]');
                        if (pageLinks.length > 0) {{
                            pageLinks[0].click();
                        }}
                    }}""")
                    
                    await page.wait_for_timeout(2000)
                    
                    # 페이지 이동 성공 여부 확인
                    current_page = await page.evaluate("""() => {
                        const pagination = document.querySelector('.pagination');
                        if (!pagination) return 1;
                        const currentPageElem = pagination.querySelector('span[title="현재위치"], .current');
                        return currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                    }""")
                    
                    if current_page == page_num:
                        logging.info(f"✅ 페이지 {page_num}로 이동 성공")
                    else:
                        logging.warning(f"⚠️ 페이지 {page_num}로 이동 실패 (현재: {current_page})")
                        
                        # 재시도 로직
                        max_retries = 3
                        for retry in range(1, max_retries + 1):
                            logging.info(f"🔄 페이지 {page_num} 이동 재시도 {retry}/{max_retries}")
                            
                            await page.evaluate(f"""() => {{
                                const pageLinks = document.querySelectorAll('a[data-page="{page_num}"]');
                                if (pageLinks.length > 0) {{
                                    pageLinks[0].click();
                                }}
                            }}""")
                            
                            await page.wait_for_timeout(3000)
                            
                            retry_current_page = await page.evaluate("""() => {
                                const pagination = document.querySelector('.pagination');
                                if (!pagination) return 1;
                                const currentPageElem = pagination.querySelector('span[title="현재위치"], .current');
                                return currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                            }""")
                            
                            if retry_current_page == page_num:
                                logging.info(f"✅ 페이지 {page_num} 이동 재시도 성공")
                                break
                            else:
                                logging.warning(f"⚠️ 페이지 {page_num} 이동 재시도 {retry} 실패 (현재: {retry_current_page})")
                        
                        # 최종 확인
                        final_page = await page.evaluate("""() => {
                            const pagination = document.querySelector('.pagination');
                            if (!pagination) return 1;
                            const currentPageElem = pagination.querySelector('span[title="현재위치"], .current');
                            return currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                        }""")
                        
                        if final_page != page_num:
                            logging.error(f"❌ 페이지 {page_num}로 이동 최종 실패 (현재: {final_page})")
                            continue
                else:
                    logging.info(f"📄 첫 번째 페이지 처리 중...")
                
                # 현재 페이지의 이벤트 추출
                page_events = await page.evaluate("""() => {
                    const events = [];
                    const eventLinks = document.querySelectorAll('a[data-pcevtno]');
                    
                    eventLinks.forEach(link => {
                        const evtNo = link.getAttribute('data-pcevtno');
                        const apctUrl = link.getAttribute('data-apcturl');
                        const linkType = link.getAttribute('data-pcevtlinktype');
                        
                        // 썸네일 정보
                        const thumb = link.querySelector('.thumb');
                        const img = thumb ? thumb.querySelector('img') : null;
                        const dDay = thumb ? thumb.querySelector('.d-day') : null;
                        
                        // 요약 정보
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
                logging.info(f"📄 페이지 {page_num}/{total_pages} 처리 완료: {len(page_events)}개 이벤트")
            
            # 진입 페이지(목록 페이지) 자체도 추출
            logging.info(f"📄 진입 페이지 추출 시작")
            entry_page_html = await page.content()
            
            # markdownify로 변환
            from markdownify import markdownify as md_convert
            entry_page_markdown = md_convert(entry_page_html, heading_style="ATX")
            
            # 진입 페이지 데이터 구성
            entry_page_data = {
                "markdown": entry_page_markdown,
                "html": entry_page_html,
                "url": url,
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
            logging.info(f"✅ 진입 페이지 추출 완료")
            
            await browser.close()
            
            # 각 이벤트의 상세 페이지를 처리하여 개별 게시물로 구성
            individual_posts = [entry_page_data]  # 진입 페이지를 첫 번째로 추가
            logging.info(f"총 {len(all_events)}개 이벤트 상세 페이지 처리 시작")
            
            for i, event in enumerate(all_events, 1):
                try:
                    logging.info(f"{i}/{len(all_events)}번째 이벤트 상세 페이지 처리 시작: '{event['title']}' (evt_no: {event['evt_no']})")
                    # 상세 페이지 URL 구성
                    detail_url = f"https://event.kt.com/html/event/ongoing_event_view.html?page=1&searchCtg=ALL&sort=&pcEvtNo={event['evt_no']}"
                    
                    # 상세 페이지 핸들러 호출
                    detail_result = await handle_kt_event_detail(detail_url, fclient, menu)
                    
                    if detail_result and "datas" in detail_result and detail_result["datas"]:
                        # 상세 페이지에서 추출한 데이터 사용
                        individual_post = detail_result["datas"][0]
                        # 추가 메타데이터 병합
                        individual_post["metadata"].update({
                            "evt_no": event['evt_no'],
                            "original_url": url,
                            "post_index": i,
                            "total_posts": len(all_events)
                        })
                        # 상세 타이틀로 보정 (메뉴명이 ... 로 잘리는 문제 예방)
                        detail_title = individual_post["metadata"].get('title', '').strip()
                        if detail_title:
                            event['title'] = detail_title
                        logging.info(f"{i}/{len(all_events)}번째 이벤트 상세 페이지 처리 성공: '{event['title']}'")
                    else:
                        # 상세 페이지 처리 실패 시 목록 정보로 fallback
                        logging.warning(f"{i}/{len(all_events)}번째 이벤트 상세 페이지 처리 실패, 목록 정보로 fallback: '{event['title']}'")
                        individual_post = {
                            "markdown": f"# {event['title']}\n\n{event['evt_no']}\n{event['date']}\n{event['type']}\n{event['d_day']}\n{event['apct_url']}",
                            "html": f"<h1>{event['title']}</h1><p>{event['evt_no']}</p><p>{event['date']}</p><p>{event['type']}</p><p>{event['d_day']}</p><p><a href='{event['apct_url']}'>{event['apct_url']}</a></p>",
                            "url": detail_url,
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
                    logging.info(f"{i}/{len(all_events)}번째 이벤트 처리 완료: '{event['title']}'")
                    
                except Exception as e:
                    logging.error(f"{i}/{len(all_events)}번째 이벤트 처리 실패: '{event['title']}', 에러: {str(e)}")
                    # 에러 시 목록 정보로 fallback
                    individual_post = {
                        "markdown": f"# {event['title']}\n\n{event['evt_no']}\n{event['date']}\n{event['type']}\n{event['d_day']}\n{event['apct_url']}\n\n상세 페이지 처리 실패: {str(e)}",
                        "html": f"<h1>{event['title']}</h1><p>{event['evt_no']}</p><p>{event['date']}</p><p>{event['type']}</p><p>{event['d_day']}</p><p><a href='{event['apct_url']}'>{event['apct_url']}</a></p><p>상세 페이지 처리 실패: {str(e)}</p>",
                        "url": f"https://event.kt.com/html/event/ongoing_event_view.html?page=1&searchCtg=ALL&sort=&pcEvtNo={event['evt_no']}",
                        "metadata": {
                            "title": event['title'],
                            "evt_no": event['evt_no'],
                            "period": event['date'],
                            "type": event['type'],
                            "d_day": event['d_day'],
                            "original_url": url,
                            "post_index": i,
                            "total_posts": len(all_events),
                            "error": str(e)
                        }
                    }
                    individual_posts.append(individual_post)
            
            # menus 배열 생성 (다른 핸들러와 동일한 패턴)
            menus = []
            
            # 진입 페이지를 첫 번째 메뉴로 추가
            menus.append({
                "menu": menu or "KT 이벤트",
                "url": url,
                "mobile_url": url.replace('https://event.kt.com', 'https://m.kt.com')
            })
            
            def _to_m(u: str) -> str:
                import re as _re
                if not u:
                    return ""
                m = _re.search(r"pcEvtNo=(\d+)", u)
                if not m:
                    mobile = u.replace('https://event.kt.com', 'https://m.kt.com').replace('pcEvtNo=', 'mblevtno=')
                    if 'past_event_view.html' in mobile and 'rows=' not in mobile:
                        mobile += ('&' if ('?' in mobile) else '?') + 'rows=10'
                    return mobile
                pc_no = int(m.group(1))
                mb_no = pc_no + 1
                mobile = u.replace('https://event.kt.com', 'https://m.kt.com')
                mobile = _re.sub(r"pcEvtNo=\d+", f"mblevtno={mb_no}", mobile)
                if 'past_event_view.html' in mobile and 'rows=' not in mobile:
                    mobile += ('&' if ('?' in mobile) else '?') + 'rows=10'
                return mobile
            for event in all_events:
                view_url = f"https://event.kt.com/html/event/ongoing_event_view.html?page=1&searchCtg=ALL&sort=&pcEvtNo={event['evt_no']}"
                menus.append({
                    "menu": f"{menu}^{event['title']}",
                    "url": view_url,
                    "mobile_url": _to_m(view_url)
                })
            
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
            logging.error(f"❌ KT 이벤트 메인 페이지 처리 실패: {str(e)}")
            await browser.close()
            return {
                "markdown": f"# KT 이벤트 페이지 처리 실패\n\n오류: {str(e)}",
                "html": f"<h1>KT 이벤트 페이지 처리 실패</h1><p>오류: {str(e)}</p>",
                "datas": [],
                "error": str(e)
            }
async def handle_kt_event_detail(url: str, fclient, menu=None) -> dict:
    logging.info(f"KT 이벤트 상세 핸들러 진입: url={url}, menu={menu}")
    """
    KT 이벤트 상세 페이지 핸들러
    https://event.kt.com/html/event/ongoing_event_view.html?pcEvtNo=13532
    """
    from playwright.async_api import async_playwright
    import re
    
    logging.info(f"KT 이벤트 상세 페이지 처리 시작: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            logging.info(f"이벤트 상세 페이지 진입: url={url}")
            response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)
            
            # HTTP 상태 코드 확인 및 로깅
            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logging.error(f"❌ KT 이벤트 상세 ({url}): HTTP {status_code} 오류")
                elif status_code >= 300:
                    logging.warning(f"⚠️ KT 이벤트 상세 ({url}): HTTP {status_code} 리다이렉트")
                else:
                    logging.info(f"✅ KT 이벤트 상세 ({url}): HTTP {status_code} 성공")
            else:
                logging.debug(f"🔍 KT 이벤트 상세 ({url}): 상태 코드 정보 없음")
            
            # 이벤트 정보 추출
            event_info = await page.evaluate("""() => {
                const info = {};
                
                // 제목
                const titleElem = document.querySelector('#contents-title, .contents-title, h1, .title');
                if (titleElem) {
                    // SNS 공유 버튼 제거
                    const snsButtons = titleElem.querySelectorAll('.btn-twitter, .btn-facebook, .btn-kakao, .btn-youtube, [class*="share"], [onclick*="share"], [href*="facebook"], [href*="twitter"], [href*="kakao"]');
                    snsButtons.forEach(btn => btn.remove());
                    info.title = titleElem.textContent.trim();
                } else {
                    info.title = '';
                }
                
                // 이벤트 정보
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
                
                // D-Day
                const dDayElem = document.querySelector('.d-day, [class*="d-day"]');
                info.d_day = dDayElem ? dDayElem.textContent.trim() : '';
                
                // iframe 정보
                const iframe = document.querySelector('#evtThumb iframe, .thumb iframe');
                if (iframe) {
                    info.iframe_src = iframe.getAttribute('src');
                    info.iframe_width = iframe.getAttribute('width');
                    info.iframe_height = iframe.getAttribute('height');
                    info.iframe_title = iframe.getAttribute('title');
                }
                
                return info;
            }""")
            
            logging.info(f"이벤트 정보 추출 성공: title='{event_info.get('title', 'unknown')}', period='{event_info.get('period', 'unknown')}'")
            
            # 기간 파싱 (startdate/enddate)
            def _parse_to_hyphen(s: str) -> str:
                import re as _re
                m = _re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s or "")
                if not m:
                    return ""
                return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

            startdate = '0000-00-00'
            enddate = '9999-99-99'
            period_text = event_info.get('period') or ''
            if period_text:
                import re as _re
                parts = [_p.strip() for _p in _re.split(r"~|–|-|to", period_text) if _p and _p.strip()]
                if len(parts) >= 1:
                    sd = _parse_to_hyphen(parts[0])
                    if sd:
                        startdate = sd
                if len(parts) >= 2:
                    ed = _parse_to_hyphen(parts[1])
                    if ed:
                        enddate = ed
            # iframe 내용 처리 (도메인 제한 없이 무조건 추출)
            iframe_content = ""
            iframe_html = ""
            if event_info.get('iframe_src'):
                try:
                    logging.info(f"이벤트 iframe 처리 시작: {event_info['iframe_src']}")
                    
                    # iframe 내부로 이동
                    iframe_page = await context.new_page()
                    await iframe_page.goto(event_info['iframe_src'], wait_until='domcontentloaded', timeout=60000)
                    await iframe_page.wait_for_timeout(5000)  # iframe 로딩 대기
                    
                    # iframe 내용 추출
                    iframe_data = await iframe_page.evaluate("""() => {
                        // 불필요한 요소 제거
                        const elementsToRemove = document.querySelectorAll('script, style, noscript, .ad, .banner, .popup');
                        elementsToRemove.forEach(el => el.remove());
                        
                        // 메인 콘텐츠 영역 찾기
                        const mainContent = document.querySelector('body') || document.documentElement;
                        return {
                            html: mainContent ? mainContent.innerHTML : '',
                            title: document.title || '',
                            url: window.location.href
                        };
                    }""")
                    
                    iframe_html = iframe_data.get('html', '')
                    iframe_content = iframe_html
                    logging.info(f"이벤트 iframe 처리 성공: 길이={len(iframe_html)}")
                    
                    await iframe_page.close()
                    
                except Exception as e:
                    logging.warning(f"이벤트 iframe 처리 실패: {str(e)}")
                    iframe_content = f"<p>iframe 로딩 실패: {str(e)}</p>"
                    iframe_html = iframe_content
            else:
                logging.info("이벤트 iframe 없음")
            
            # 마크다운 생성
            markdown_content = f"# {event_info.get('title', 'KT 이벤트')}\n\n"
            
            if event_info.get('period'):
                markdown_content += f"{event_info['period']}\n"
            if event_info.get('target'):
                markdown_content += f"{event_info['target']}\n"
            if event_info.get('announcement'):
                markdown_content += f"{event_info['announcement']}\n"
            if event_info.get('inquiry'):
                markdown_content += f"{event_info['inquiry']}\n"
            if event_info.get('d_day'):
                markdown_content += f"{event_info['d_day']}\n"
            
            markdown_content += f"\n"
            
            if iframe_content:
                # iframe 내용을 마크다운으로 변환
                try:
                    from bs4 import BeautifulSoup
                    from markdownify import markdownify as md
                    
                    soup = BeautifulSoup(iframe_content, 'html.parser')
                    # 불필요한 태그 제거
                    for tag in soup(['script', 'style', 'noscript']):
                        tag.decompose()
                    # SNS 버튼 제거
                    for selector in ['.btn-twitter', '.btn-facebook', '.btn-kakao', '.btn-youtube']:
                        for element in soup.select(selector):
                            element.decompose()
                    
                    cleaned_html = str(soup)
                    iframe_markdown = md(cleaned_html)
                    markdown_content += iframe_markdown
                    logging.info(f"이벤트 iframe 마크다운 변환 성공: 길이={len(iframe_markdown)}")
                    
                except Exception as e:
                    logging.warning(f"이벤트 iframe 마크다운 변환 실패: {str(e)}")
                    markdown_content += f"iframe 내용을 마크다운으로 변환할 수 없습니다: {str(e)}\n"
            else:
                markdown_content += "이벤트 상세 내용을 불러올 수 없습니다.\n"
            
            # HTML 생성
            html_content = f"<h1>{event_info.get('title', 'KT 이벤트')}</h1>"
            if event_info.get('period'):
                html_content += f"<p>{event_info['period']}</p>"
            if event_info.get('target'):
                html_content += f"<p>{event_info['target']}</p>"
            if event_info.get('announcement'):
                html_content += f"<p>{event_info['announcement']}</p>"
            if event_info.get('inquiry'):
                html_content += f"<p>{event_info['inquiry']}</p>"
            if event_info.get('d_day'):
                html_content += f"<p>{event_info['d_day']}</p>"
            if iframe_html:
                html_content += iframe_html
            else:
                html_content += "<p>이벤트 상세 내용을 불러올 수 없습니다.</p>"
            
            # 모바일 이벤트 URL 생성 규칙 (요청: mblevtno = pcEvtNo + 1)
            def _pc_to_m_url(pc_url: str) -> str:
                import re as _re
                if not pc_url:
                    return ""
                m = _re.search(r"pcEvtNo=(\d+)", pc_url)
                if not m:
                    return pc_url.replace('https://event.kt.com', 'https://m.kt.com').replace('pcEvtNo=', 'mblevtno=')
                pc_no = int(m.group(1))
                mb_no = pc_no + 1
                mobile = pc_url.replace('https://event.kt.com', 'https://m.kt.com')
                mobile = _re.sub(r"pcEvtNo=\d+", f"mblevtno={mb_no}", mobile)
                return mobile

            mobile_url_from_detail = _pc_to_m_url(url)

            await browser.close()
            
            logging.info(f"KT 이벤트 상세 처리 완료: title='{event_info.get('title', 'unknown')}', iframe_processed={bool(iframe_content)}")
                        
            return {
                "datas": [{
                    "markdown": markdown_content,
                    "html": html_content,
                    "url": url,
                    "mobile_url": mobile_url_from_detail,
                        "murl": mobile_url_from_detail,
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
                    "menu": f"{menu}^{event_info.get('title', 'unknown')}",
                    "url": url,
                    "murl": mobile_url_from_detail
                }],
                # 상위(return) 레벨은 그대로 유지
            }
            
        except Exception as e:
            logging.error(f"KT 이벤트 상세 페이지 처리 실패: {str(e)}")
            await browser.close()
            return {
                "datas": [{
                    "markdown": f"# KT 이벤트 상세 페이지 처리 실패\n\n오류: {str(e)}",
                    "html": f"<h1>KT 이벤트 상세 페이지 처리 실패</h1><p>오류: {str(e)}</p>",
                    "url": url,
                    "error": str(e)
                }]
            }

async def handle_kt_past_event_main(url: str, fclient, menu=None) -> dict:
    logging.info(f"KT 지난 이벤트 메인 핸들러 진입: url={url}, menu={menu}")
    """
    KT 지난 이벤트 메인 페이지 핸들러
    https://event.kt.com/html/event/past_event_list.html
    
    페이지네이션을 순회하면서 모든 data-pcevtno 값을 수집한 후,
    병렬 처리로 상세 페이지들을 스크래핑
    """
    from playwright.async_api import async_playwright
    import asyncio
    import re
    from datetime import datetime
    
    logging.info(f"🎯 KT 지난 이벤트 메인 페이지 처리: {url}")
    
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
            
            # HTTP 상태 코드 확인 및 로깅
            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logging.error(f"❌ KT 지난 이벤트 메인 ({url}): HTTP {status_code} 오류")
                elif status_code >= 300:
                    logging.warning(f"⚠️ KT 지난 이벤트 메인 ({url}): HTTP {status_code} 리다이렉트")
                else:
                    logging.info(f"✅ KT 지난 이벤트 메인 ({url}): HTTP {status_code} 성공")
            else:
                logging.debug(f"🔍 KT 지난 이벤트 메인 ({url}): 상태 코드 정보 없음")
            
            # 페이지네이션 정보 추출
            pagination_info = await page.evaluate("""() => {
                const pagination = document.querySelector('.pagination');
                if (!pagination) return { total_pages: 1, current_page: 1 };
                
                // 현재 페이지 확인 (title="현재위치"인 span 요소)
                const currentPageElem = pagination.querySelector('span[title="현재위치"]');
                const currentPage = currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                
                // data-page 속성이 있는 모든 링크에서 최대 페이지 번호 찾기
                const pageLinks = pagination.querySelectorAll('a[data-page]');
                let maxPage = currentPage; // 현재 페이지부터 시작
                
                pageLinks.forEach(link => {
                    const dataPage = link.getAttribute('data-page');
                    if (dataPage) {
                        const pageNum = parseInt(dataPage);
                        if (!isNaN(pageNum) && pageNum > maxPage) {
                            maxPage = pageNum;
                        }
                    }
                });
                
                // 마지막 페이지 링크가 있는지 확인하여 더 많은 페이지가 있는지 판단
                const lastLink = pagination.querySelector('a.last');
                const nextLink = pagination.querySelector('a.next');
                
                // 다음 페이지나 마지막 페이지 링크가 있으면 더 많은 페이지가 있을 수 있음
                if (lastLink || nextLink) {
                    // 보수적으로 현재 보이는 최대 페이지보다 더 있다고 가정
                    // 실제로는 마지막 페이지를 클릭해서 확인해야 하지만, 
                    // 일단 현재 보이는 페이지들을 기준으로 함
                }
                
                return { 
                    total_pages: maxPage, 
                    current_page: currentPage,
                    has_next: !!nextLink,
                    has_last: !!lastLink
                };
            }""")
            
            all_event_infos = []
            
            # 먼저 마지막 페이지를 확인하여 정확한 총 페이지 수를 알아냄
            if pagination_info.get('has_last', False):
                logging.info("🔍 마지막 페이지 확인하여 정확한 총 페이지 수 파악 중...")
                try:
                    # 마지막 페이지로 이동
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
                    
                    # 마지막 페이지 번호 확인
                    last_page_info = await page.evaluate("""() => {
                        const pagination = document.querySelector('.pagination');
                        if (!pagination) return { last_page: 1 };
                        
                        const currentPageElem = pagination.querySelector('span[title="현재위치"]');
                        const lastPage = currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                        
                        return { last_page: lastPage };
                    }""")
                    
                    total_pages = last_page_info.get('last_page', pagination_info.get('total_pages', 1))
                    logging.info(f"✅ 정확한 총 페이지 수 확인: {total_pages}페이지")
                    
                    # 첫 페이지로 돌아가기
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
                    
                except Exception as e:
                    logging.warning(f"마지막 페이지 확인 실패, 기본값 사용: {str(e)}")
                    total_pages = pagination_info.get('total_pages', 1)
            else:
                total_pages = pagination_info.get('total_pages', 1)
            
            logging.info(f"📄 총 {total_pages}개 페이지에서 이벤트 정보 수집 시작")
            
            # 모든 페이지 순차적으로 처리
            current_page = 1
            for page_num in range(1, total_pages + 1):
                if page_num > current_page:
                    # 다음 페이지로 순차적으로 이동
                    while current_page < page_num:
                        logging.info(f"🔄 페이지 {current_page} -> {current_page + 1}로 이동 중...")
                        
                        # 다음 페이지 버튼 클릭
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
                            await page.wait_for_timeout(3000)  # 페이지 로딩 대기
                            
                            # 실제 이동된 페이지 확인
                            actual_page = await page.evaluate("""() => {
                                const pagination = document.querySelector('.pagination');
                                if (!pagination) return 1;
                                
                                const currentPageElem = pagination.querySelector('span[title="현재위치"]');
                                return currentPageElem ? parseInt(currentPageElem.textContent) : 1;
                            }""")
                            
                            if actual_page > current_page:
                                current_page = actual_page
                                logging.info(f"✅ 페이지 {current_page}로 이동 성공")
                            else:
                                logging.warning(f"⚠️ 페이지 이동이 예상과 다름: 현재 {actual_page}")
                                break
                        else:
                            logging.warning(f"⚠️ 다음 페이지 버튼을 찾을 수 없음")
                            break
                    
                    if current_page != page_num:
                        logging.warning(f"⚠️ 목표 페이지 {page_num}에 도달하지 못함 (현재: {current_page})")
                        continue
                else:
                    logging.info(f"📄 첫 번째 페이지 처리 중...")
                
                # 현재 페이지의 이벤트 정보 추출 (정확한 HTML 구조에 맞게)
                page_events = await page.evaluate(f"""() => {{
                    const events = [];
                    
                    // 테이블 구조: table.board tbody tr
                    const table = document.querySelector('table.board');
                    if (!table) {{
                        console.log('Table not found');
                        return events;
                    }}
                    
                    const tbody = table.querySelector('tbody');
                    if (!tbody) {{
                        console.log('Tbody not found');
                        return events;
                    }}
                    
                    const rows = tbody.querySelectorAll('tr');
                    console.log('Found rows:', rows.length);
                    
                    rows.forEach((row, index) => {{
                        const link = row.querySelector('a[data-pcevtno]');
                        if (link) {{
                            const evtNo = link.getAttribute('data-pcevtno');
                            if (evtNo) {{
                                // 제목: 링크의 텍스트 (예: "KT 장기고객 감사 이벤트")
                                const title = link.textContent.trim();
                                
                                // 기간: 두 번째 td (예: "2025.08.28 ~ 2025.09.10")
                                const cells = row.querySelectorAll('td');
                                const period = cells.length > 1 ? cells[1].textContent.trim() : '';
                                
                                console.log(`Event ${{index + 1}}: ${{title}} (${{evtNo}})`);
                                
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
                    
                    console.log('Total events found:', events.length);
                    return events;
                }}""")
                
                all_event_infos.extend(page_events)
                logging.info(f"📄 페이지 {page_num}/{total_pages} 처리 완료: {len(page_events)}개 이벤트")
                
                # 페이지별 이벤트 상세 로깅
                if len(page_events) == 0:
                    logging.error(f"❌ 페이지 {page_num}에서 이벤트를 찾을 수 없습니다")
                else:
                    evt_nos_on_page = [e['evt_no'] for e in page_events]
                    logging.info(f"📄 페이지 {page_num} 이벤트 번호들: {evt_nos_on_page}")
            
            # 진입 페이지(목록 페이지) 자체도 추출
            logging.info(f"📄 진입 페이지 추출 시작")
            entry_page_html = await page.content()
            
            # markdownify로 변환
            from markdownify import markdownify as md_convert
            entry_page_markdown = md_convert(entry_page_html, heading_style="ATX")
            
            # 진입 페이지 데이터 구성
            entry_page_data = {
                "markdown": entry_page_markdown,
                "html": entry_page_html,
                "url": url,
                "metadata": {
                    "title": f"{menu or 'KT 지난 이벤트'} 목록",
                    "is_entry_page": True,
                    "total_events": len(all_event_infos),
                    "total_pages": total_pages,
                    "original_url": url,
                    "special_processed": True,
                    "playwright_processed": True
                }
            }
            logging.info(f"✅ 진입 페이지 추출 완료")
            
            await browser.close()
            
            logging.info(f"🎯 총 {len(all_event_infos)}개 지난 이벤트 정보 수집 완료")
            
            # 중복 제거 (evt_no 기준)
            unique_events = {}
            duplicates = []
            for event in all_event_infos:
                evt_no = event['evt_no']
                if evt_no not in unique_events:
                    unique_events[evt_no] = event
                else:
                    duplicates.append(evt_no)
            
            unique_event_list = list(unique_events.values())
            logging.info(f"🎯 중복 제거 후: {len(unique_event_list)}개 이벤트")
            
            if duplicates:
                duplicate_counts = {}
                for dup in duplicates:
                    duplicate_counts[dup] = duplicate_counts.get(dup, 0) + 1
                logging.warning(f"⚠️ 중복 발견된 이벤트들: {dict(duplicate_counts)} (총 {len(duplicates)}개 중복)")
            
            # 병렬 처리로 상세 페이지들 스크래핑
            individual_posts = [entry_page_data]  # 진입 페이지를 첫 번째로 추가
            if unique_event_list:
                logging.info(f"🚀 {len(unique_event_list)}개 이벤트 상세 페이지 병렬 처리 시작")
                
                # 병렬 처리를 위한 세마포어 (동시 처리 개수 제한)
                semaphore = asyncio.Semaphore(15)  # 최대 15개 동시 처리
                
                async def process_single_event(event_info, event_index):
                    async with semaphore:
                        try:
                            logging.info(f"[{event_index+1}/{len(unique_event_list)}] 이벤트 상세 페이지 처리 시작: '{event_info['title']}' (evt_no: {event_info['evt_no']})")
                            
                            # 상세 페이지 URL 구성
                            detail_url = f"https://event.kt.com/html/event/past_event_view.html?page={event_info['page']}&searchCtg=ALL&pcEvtNo={event_info['evt_no']}"
                            
                            # 상세 페이지 핸들러 호출 (제목 정보 전달)
                            detail_result = await handle_kt_past_event_detail(detail_url, fclient, menu, event_info)
                            
                            if detail_result and "datas" in detail_result and detail_result["datas"]:
                                # 상세 페이지에서 추출한 데이터 사용
                                individual_post = detail_result["datas"][0]
                                # 추가 메타데이터 병합
                                individual_post["metadata"].update({
                                    "evt_no": event_info['evt_no'],
                                    "original_url": url,
                                    "post_index": event_index + 1,
                                    "total_posts": len(unique_event_list),
                                    "source_page": event_info['page']
                                })
                                # 상세 타이틀로 보정
                                detail_title = individual_post["metadata"].get('title', '').strip()
                                if detail_title:
                                    event_info['title'] = detail_title
                                logging.info(f"[{event_index+1}/{len(unique_event_list)}] 이벤트 상세 페이지 처리 성공: '{event_info['title']}'")
                                return individual_post, event_info
                            else:
                                # 상세 페이지 처리 실패 시 목록 정보로 fallback
                                logging.warning(f"[{event_index+1}/{len(unique_event_list)}] 이벤트 상세 페이지 처리 실패, 목록 정보로 fallback: '{event_info['title']}'")
                                
                                # 제목이 비어있으면 이벤트 번호로 제목 생성
                                display_title = event_info['title'] if event_info['title'].strip() else f"지난 이벤트({event_info['evt_no']})"
                                
                                individual_post = {
                                    "markdown": f"# {display_title}\\n\\n이벤트 번호: {event_info['evt_no']}\\n기간: {event_info['period']}\\n\\n이벤트가 종료되었습니다.",
                                    "html": f"<h1>{display_title}</h1><p>이벤트 번호: {event_info['evt_no']}</p><p>기간: {event_info['period']}</p><p>이벤트가 종료되었습니다.</p>",
                                    "url": detail_url,
                                    "metadata": {
                                        "title": display_title,
                                        "evt_no": event_info['evt_no'],
                                        "period": event_info['period'],
                                        "status": "종료",
                                        "original_url": url,
                                        "post_index": event_index + 1,
                                        "total_posts": len(unique_event_list),
                                        "source_page": event_info['page'],
                                        "detail_processing_failed": True,
                                        "startdate": "1900-01-01",
                                        "enddate": "2999-12-31"
                                    }
                                }
                                return individual_post, event_info
                                
                        except Exception as e:
                            logging.error(f"[{event_index+1}/{len(unique_event_list)}] 이벤트 처리 실패: '{event_info['title']}', 에러: {str(e)}")
                            # 에러 시 목록 정보로 fallback
                            
                            # 제목이 비어있으면 이벤트 번호로 제목 생성
                            display_title = event_info['title'] if event_info['title'].strip() else f"지난 이벤트({event_info['evt_no']})"
                            
                            individual_post = {
                                "markdown": f"# {display_title}\\n\\n이벤트 번호: {event_info['evt_no']}\\n기간: {event_info['period']}\\n\\n상세 페이지 처리 실패: {str(e)}",
                                "html": f"<h1>{display_title}</h1><p>이벤트 번호: {event_info['evt_no']}</p><p>기간: {event_info['period']}</p><p>상세 페이지 처리 실패: {str(e)}</p>",
                                "url": f"https://event.kt.com/html/event/past_event_view.html?page={event_info['page']}&searchCtg=ALL&pcEvtNo={event_info['evt_no']}",
                                "metadata": {
                                    "title": display_title,
                                    "evt_no": event_info['evt_no'],
                                    "period": event_info['period'],
                                    "status": "오류",
                                    "original_url": url,
                                    "post_index": event_index + 1,
                                    "total_posts": len(unique_event_list),
                                    "source_page": event_info['page'],
                                    "error": str(e),
                                    "startdate": "1900-01-01",
                                    "enddate": "2999-12-31"
                                }
                            }
                            return individual_post, event_info
                
                # 모든 이벤트를 병렬로 처리
                tasks = [process_single_event(event_info, i) for i, event_info in enumerate(unique_event_list)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 결과 정리 및 누락 추적
                processed_evt_nos = set()
                failed_evt_nos = []
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logging.error(f"❌ 병렬 처리 중 예외 발생 ({i+1}/{len(results)}): {str(result)}")
                        if i < len(unique_event_list):
                            failed_evt_no = unique_event_list[i].get('evt_no', 'unknown')
                            failed_evt_nos.append(failed_evt_no)
                            logging.error(f"❌ 실패한 이벤트 번호: {failed_evt_no}")
                    else:
                        individual_post, event_info = result
                        individual_posts.append(individual_post)
                        evt_no = event_info.get('evt_no', 'unknown')
                        processed_evt_nos.add(evt_no)
                
                # 누락된 이벤트 확인
                expected_evt_nos = {event['evt_no'] for event in unique_event_list}
                missing_evt_nos = expected_evt_nos - processed_evt_nos
                
                if missing_evt_nos:
                    logging.error(f"❌ 누락된 이벤트들 ({len(missing_evt_nos)}개): {sorted(missing_evt_nos)}")
                    for missing_no in sorted(missing_evt_nos):
                        # 누락된 이벤트 정보 찾기
                        missing_event = next((e for e in unique_event_list if e['evt_no'] == missing_no), None)
                        if missing_event:
                            logging.error(f"❌ 누락 이벤트 상세: 번호={missing_no}, 제목='{missing_event.get('title', 'unknown')}', 페이지={missing_event.get('page', 'unknown')}")
                
                if failed_evt_nos:
                    logging.error(f"❌ 처리 실패한 이벤트들 ({len(failed_evt_nos)}개): {failed_evt_nos}")
                
                logging.info(f"📊 이벤트 처리 통계: 전체={len(unique_event_list)}, 성공={len(processed_evt_nos)}, 실패={len(failed_evt_nos)}, 누락={len(missing_evt_nos)}")
            
            # menus 배열 생성 (individual_posts 처리 후 실제 제목으로)
            menus = []
            
            # 진입 페이지를 첫 번째 메뉴로 추가
            menus.append({
                "menu": menu or "KT 지난 이벤트",
                "url": url,
                "murl": url.replace('https://event.kt.com', 'https://m.kt.com')
            })
            
            def _to_m(u: str) -> str:
                import re as _re
                if not u:
                    return ""
                m = _re.search(r"pcEvtNo=(\d+)", u)
                if not m:
                    return u.replace('https://event.kt.com', 'https://m.kt.com').replace('pcEvtNo=', 'mblevtno=')
                pc_no = int(m.group(1))
                mb_no = pc_no + 1
                mobile = u.replace('https://event.kt.com', 'https://m.kt.com')
                mobile = _re.sub(r"pcEvtNo=\d+", f"mblevtno={mb_no}", mobile)
                return mobile
            
            # 각 게시물 데이터에 murl 주입
            for _post in individual_posts:
                try:
                    _u = _post.get('url', '')
                    if _u:
                        _post['murl'] = _to_m(_u)
                except Exception:
                    pass

            # individual_posts에서 실제 처리된 제목과 URL 사용
            for post in individual_posts:
                post_metadata = post.get('metadata', {})
                post_title = post_metadata.get('title', '제목 없음')
                evt_no = post_metadata.get('evt_no', 'unknown')
                post_url = post.get('url', '')
                
                # 메뉴 구조: 혜택^이벤트/핫딜^지난 이벤트^{이벤트명}({evt_no})
                # evt_no를 포함하여 고유성 보장
                final_menu = f"{menu}^{post_title}({evt_no})"
                
                menus.append({
                    "menu": final_menu,
                    "url": post_url,
                    "murl": _to_m(post_url)
                })
            
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
            logging.error(f"❌ KT 지난 이벤트 메인 페이지 처리 실패: {str(e)}")
            await browser.close()
            return {
                "markdown": f"# KT 지난 이벤트 페이지 처리 실패\\n\\n오류: {str(e)}",
                "html": f"<h1>KT 지난 이벤트 페이지 처리 실패</h1><p>오류: {str(e)}</p>",
                "datas": [],
                "error": str(e)
            }
async def handle_kt_past_event_detail(url: str, fclient, menu=None, main_event_info=None) -> dict:
    logging.info(f"KT 지난 이벤트 상세 핸들러 진입: url={url}, menu={menu}")
    """
    KT 지난 이벤트 상세 페이지 핸들러
    https://event.kt.com/html/event/past_event_view.html?page=1&searchCtg=ALL&pcEvtNo=13590
    """
    from playwright.async_api import async_playwright
    import re
    
    logging.info(f"KT 지난 이벤트 상세 페이지 처리 시작: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            # 재시도 로직 추가
            max_retries = 3
            retry_count = 0
            response = None
            
            while retry_count < max_retries:
                try:
                    logging.info(f"지난 이벤트 상세 페이지 진입 시도 {retry_count + 1}/{max_retries}: url={url}")
                    # 타임아웃을 60초로 늘리고 더 관대한 로딩 조건 사용
                    response = await page.goto(url, wait_until='networkidle', timeout=60000)
                    await page.wait_for_timeout(5000)  # 페이지 안정화 대기
                    break  # 성공하면 루프 탈출
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logging.error(f"지난 이벤트 상세 페이지 로딩 실패 (최대 재시도 초과): {str(e)}")
                        raise e
                    else:
                        logging.warning(f"지난 이벤트 상세 페이지 로딩 실패, 재시도 {retry_count}/{max_retries}: {str(e)}")
                        await page.wait_for_timeout(3000)  # 재시도 전 대기
            
            # HTTP 상태 코드 확인 및 로깅
            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logging.error(f"❌ KT 지난 이벤트 상세 ({url}): HTTP {status_code} 오류")
                elif status_code >= 300:
                    logging.warning(f"⚠️ KT 지난 이벤트 상세 ({url}): HTTP {status_code} 리다이렉트")
                else:
                    logging.info(f"✅ KT 지난 이벤트 상세 ({url}): HTTP {status_code} 성공")
            else:
                logging.debug(f"🔍 KT 지난 이벤트 상세 ({url}): 상태 코드 정보 없음")
            
            # 페이지 콘텐츠 구조 확인 (.contents 영역 기준)
            page_content = await page.evaluate("""() => {
                // .contents 영역 확인
                const contentsDiv = document.querySelector('.contents');
                if (!contentsDiv) {
                    return { empty: true, text: '', terminated: false, error: 'Contents div not found' };
                }
                
                // .box-close 클래스에서 종료 메시지 확인
                const boxClose = contentsDiv.querySelector('.box-close');
                const isTerminated = boxClose && boxClose.textContent.includes('이벤트가 종료');
                
                // 제목 확인
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
            
            if page_content.get('empty', False):
                logging.warning(f"지난 이벤트 상세 페이지가 비어있거나 종료 메시지만 있음: {url}")
                
                # URL에서 pcEvtNo 추출
                evt_no_match = re.search(r'pcEvtNo=(\d+)', url)
                evt_no = evt_no_match.group(1) if evt_no_match else 'unknown'
                
                await browser.close()
                return {
                    "datas": [{
                        "markdown": f"# 종료된 이벤트({evt_no})\\n\\n이벤트 번호: {evt_no}\\n\\n이벤트가 종료되었습니다.",
                        "html": f"<h1>종료된 이벤트({evt_no})</h1><p>이벤트 번호: {evt_no}</p><p>이벤트가 종료되었습니다.</p>",
                        "url": url,
                        "metadata": {
                            "title": f"종료된 이벤트({evt_no})",
                            "evt_no": evt_no,
                            "period": "",
                            "status": "종료",
                            "empty_content": True,
                            "startdate": "1900-01-01",
                            "enddate": "2999-12-31"
                        }
                    }]
                }
            
            # 이벤트 정보 추출 (간단하게 제목만 추출, 나머지는 .contents 전체 사용)
            event_info = await page.evaluate("""() => {
                const info = {};
                
                // .contents 영역에서 제목만 추출
                const contentsDiv = document.querySelector('.contents');
                if (contentsDiv) {
                    // 제목: #contents-title 또는 .contents-title
                    const titleElem = contentsDiv.querySelector('#contents-title, .contents-title');
                    if (titleElem) {
                        info.title = titleElem.textContent.trim();
                        console.log('Title found:', info.title);
                    }
                    
                    // iframe 확인 (필요시)
                    const iframe = contentsDiv.querySelector('iframe');
                    if (iframe && iframe.getAttribute('src')) {
                        info.iframe_src = iframe.getAttribute('src');
                        console.log('Iframe found:', info.iframe_src);
                    }
                } else {
                    console.log('Contents div not found');
                }
                
                return info;
            }""")
            
            # 메인 페이지에서 전달받은 제목 우선 사용
            if main_event_info and main_event_info.get('title'):
                event_info['title'] = main_event_info['title']
            
            logging.info(f"지난 이벤트 정보 추출 성공: title='{event_info.get('title', 'unknown')}', period='{event_info.get('period', 'unknown')}'")
            
            # 기간 파싱 (startdate/enddate)
            def _parse_to_hyphen(s: str) -> str:
                import re as _re
                m = _re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s or "")
                if not m:
                    return ""
                return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

            startdate = '1900-01-01'
            enddate = '2999-12-31'
            period_text = event_info.get('period') or ''
            if period_text:
                import re as _re
                parts = [_p.strip() for _p in _re.split(r"~|–|-|to", period_text) if _p and _p.strip()]
                if len(parts) >= 1:
                    sd = _parse_to_hyphen(parts[0])
                    if sd:
                        startdate = sd
                if len(parts) >= 2:
                    ed = _parse_to_hyphen(parts[1])
                    if ed:
                        enddate = ed
            
            # 콘텐츠 처리 (.contents 영역 전체 사용)
            content_html = page_content.get('contentsHTML', '')
            
            # iframe이 있다면 별도 처리
            if event_info.get('iframe_src'):
                try:
                    logging.info(f"지난 이벤트 iframe 처리 시작: {event_info['iframe_src']}")
                    
                    # iframe 내부로 이동
                    iframe_page = await context.new_page()
                    await iframe_page.goto(event_info['iframe_src'], wait_until='networkidle', timeout=60000)
                    await iframe_page.wait_for_timeout(8000)  # iframe 로딩 대기
                    
                    # iframe 내용 추출
                    iframe_data = await iframe_page.evaluate("""() => {
                        // 불필요한 요소 제거
                        const elementsToRemove = document.querySelectorAll('script, style, noscript, .ad, .banner, .popup');
                        elementsToRemove.forEach(el => el.remove());
                        
                        // 메인 콘텐츠 영역 찾기
                        const mainContent = document.querySelector('body') || document.documentElement;
                        return {
                            html: mainContent ? mainContent.innerHTML : '',
                            title: document.title || '',
                            url: window.location.href
                        };
                    }""")
                    
                    iframe_content = iframe_data.get('html', '')
                    # .contents HTML과 iframe 내용 결합
                    content_html += f"\\n\\n<div class='iframe-content'>{iframe_content}</div>"
                    logging.info(f"지난 이벤트 iframe 처리 성공: 길이={len(iframe_content)}")
                    
                    await iframe_page.close()
                    
                except Exception as e:
                    logging.warning(f"지난 이벤트 iframe 처리 실패: {str(e)}")
                    content_html += f"\\n\\n<p>iframe 로딩 실패: {str(e)}</p>"
            
            logging.info(f"지난 이벤트 콘텐츠 사용: 길이={len(content_html)}")
            
            # 마크다운 생성
            markdown_content = f"# {event_info.get('title', 'KT 지난 이벤트')}\\n\\n"
            
            if event_info.get('period'):
                markdown_content += f"**기간**: {event_info['period']}\\n\\n"
            if event_info.get('target'):
                markdown_content += f"**대상**: {event_info['target']}\\n\\n"
            if event_info.get('announcement'):
                markdown_content += f"**당첨자발표**: {event_info['announcement']}\\n\\n"
            if event_info.get('inquiry'):
                markdown_content += f"**문의**: {event_info['inquiry']}\\n\\n"
            if event_info.get('d_day'):
                markdown_content += f"**상태**: {event_info['d_day']}\\n\\n"
            
            if content_html:
                # HTML 내용을 마크다운으로 변환
                try:
                    from bs4 import BeautifulSoup
                    from markdownify import markdownify as md
                    
                    soup = BeautifulSoup(content_html, 'html.parser')
                    # 불필요한 태그 제거
                    for tag in soup(['script', 'style', 'noscript']):
                        tag.decompose()
                    # SNS 버튼 제거
                    for selector in ['.btn-twitter', '.btn-facebook', '.btn-kakao', '.btn-youtube']:
                        for element in soup.select(selector):
                            element.decompose()
                    
                    cleaned_html = str(soup)
                    content_markdown = md(cleaned_html)
                    markdown_content += content_markdown
                    logging.info(f"지난 이벤트 콘텐츠 마크다운 변환 성공: 길이={len(content_markdown)}")
                    
                except Exception as e:
                    logging.warning(f"지난 이벤트 콘텐츠 마크다운 변환 실패: {str(e)}")
                    markdown_content += f"콘텐츠를 마크다운으로 변환할 수 없습니다: {str(e)}\\n"
            else:
                markdown_content += "이벤트 상세 내용을 불러올 수 없습니다.\\n"
            
            # HTML 생성
            html_content = f"<h1>{event_info.get('title', 'KT 지난 이벤트')}</h1>"
            if event_info.get('period'):
                html_content += f"<p><strong>기간</strong>: {event_info['period']}</p>"
            if event_info.get('target'):
                html_content += f"<p><strong>대상</strong>: {event_info['target']}</p>"
            if event_info.get('announcement'):
                html_content += f"<p><strong>당첨자발표</strong>: {event_info['announcement']}</p>"
            if event_info.get('inquiry'):
                html_content += f"<p><strong>문의</strong>: {event_info['inquiry']}</p>"
            if event_info.get('d_day'):
                html_content += f"<p><strong>상태</strong>: {event_info['d_day']}</p>"
            
            if content_html:
                html_content += content_html
            else:
                html_content += "<p>이벤트 상세 내용을 불러올 수 없습니다.</p>"
            
            # URL에서 pcEvtNo 추출
            evt_no_match = re.search(r'pcEvtNo=(\d+)', url)
            evt_no = evt_no_match.group(1) if evt_no_match else 'unknown'
            
            await browser.close()
            
            return {
                "datas": [{
                    "markdown": markdown_content,
                    "html": html_content,
                    "url": url,
                    "metadata": {
                        "title": event_info.get('title', 'KT 지난 이벤트'),
                        "evt_no": evt_no,
                        "period": event_info.get('period', ''),
                        "target": event_info.get('target', ''),
                        "announcement": event_info.get('announcement', ''),
                        "inquiry": event_info.get('inquiry', ''),
                        "d_day": event_info.get('d_day', ''),
                        "status": "종료",
                        "startdate": startdate,
                        "enddate": enddate,
                        "iframe_src": event_info.get('iframe_src', ''),
                        "special_processed": True,
                        "playwright_processed": True
                    }
                }]
            }
            
        except Exception as e:
            logging.error(f"❌ KT 지난 이벤트 상세 페이지 처리 실패: {str(e)}")
            await browser.close()
            
            # URL에서 pcEvtNo 추출
            evt_no_match = re.search(r'pcEvtNo=(\d+)', url)
            evt_no = evt_no_match.group(1) if evt_no_match else 'unknown'
            
            return {
                "datas": [{
                    "markdown": f"# KT 지난 이벤트 처리 실패\\n\\n이벤트 번호: {evt_no}\\n\\n오류: {str(e)}",
                    "html": f"<h1>KT 지난 이벤트 처리 실패</h1><p>이벤트 번호: {evt_no}</p><p>오류: {str(e)}</p>",
                    "url": url,
                    "metadata": {
                        "title": "KT 지난 이벤트 처리 실패",
                        "evt_no": evt_no,
                        "error": str(e),
                        "status": "오류"
                    }
                }]
            }


# KT 이벤트 핸들러 등록
register_page_handler(
    r'https?://event\.kt\.com/html/event/ongoing_event_list\.html',
    handle_kt_event_main
)

register_page_handler(
    r'https?://event\.kt\.com/html/event/ongoing_event_view\.html\?.*pcEvtNo=\d+',
    handle_kt_event_detail
)
# # KT 지난 이벤트 핸들러 등록
# register_page_handler(
#     r'https?://event\.kt\.com/html/event/past_event_list\.html',
#     handle_kt_past_event_main
# )

# register_page_handler(
#     r'https?://event\.kt\.com/html/event/past_event_view\.html\?.*pcEvtNo=\d+',
#     handle_kt_past_event_detail
# )


# =========================
# 10-F. KT Shop 액세서리 목록/상세 핸들러
# =========================
async def handle_accessory_detail(url: str, fclient, context=None) -> Optional[Dict[str, Any]]:
    from markdownify import markdownify as md

    logging.info(f"액세서리 상세 핸들러 시작: url={url}")

    async def _process_detail(ctx) -> Optional[Dict[str, Any]]:
        page = await ctx.new_page()
        status_detail = None
        try:
            try:
                response_detail = await page.goto(url, wait_until='networkidle', timeout=60000)
            except AsyncTimeoutError as te:
                logging.warning(f"액세서리 상세 페이지 로드 타임아웃(networkidle) - 재시도 시도: {te}")
                try:
                    response_detail = await page.goto(url, wait_until='load', timeout=45000)
                except AsyncTimeoutError as te2:
                    logging.warning(f"액세서리 상세 페이지 로드 타임아웃(load) - 최종 재시도(domcontentloaded): {te2}")
                    try:
                        response_detail = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    except AsyncTimeoutError as te3:
                        logging.error(f"액세서리 상세 페이지 로드 최종 타임아웃(domcontentloaded): {te3}")
                        # Playwright 로딩이 모두 실패한 경우: fclient 폴백 수행
                        if fclient:
                            try:
                                logging.info("액세서리 상세: Playwright 타임아웃으로 fclient 폴백 수행")
                                fallback = await fclient.scrape_single_url(url)
                                combined_html = fallback.get('html', '')
                                markdown = fallback.get('markdown', '')
                                result = {
                                    'url': url,
                                    'murl': to_mshop_url(url),
                                    'title': '',
                                    'html': combined_html,
                                    'markdown': markdown,
                                    'status_code': None,
                                    'recommendations': [],
                                    'special_processed': True,
                                    'playwright_processed': False
                                }
                                return result
                            except Exception as fallback_exc:
                                logging.warning(f"액세서리 상세 fclient 폴백 실패: {fallback_exc}")
                        return None
            status_detail = response_detail.status if response_detail else None

            if status_detail and status_detail >= 400:
                logging.error(f"❌ 액세서리 상세 ({url}): HTTP {status_detail} 오류")
            else:
                logging.info(f"✅ 액세서리 상세 ({url}): HTTP {status_detail or 'unknown'}")

            await page.wait_for_timeout(1500)

            title = await page.evaluate("document.querySelector('.ui-prd_tit')?.textContent?.trim() || ''")
            info_html = await page.evaluate("document.querySelector('.ui-view-info')?.outerHTML || ''")
            tab_html = await page.evaluate("document.querySelector('.ui-prdView-tab')?.outerHTML || ''")
            recommend_html = await page.evaluate("document.querySelector('.ui-viewPrd-cont.ui-best-cont')?.outerHTML || ''")

            combined_html_parts = [part for part in [info_html, tab_html] if part]
            combined_html = "\n".join(combined_html_parts)
            markdown = md(combined_html) if combined_html else ''

            if (not combined_html or not markdown) and fclient:
                try:
                    logging.info("액세서리 상세 기본 추출 실패, fclient fallback 시도")
                    fallback = await fclient.scrape_single_url(url)
                    combined_html = fallback.get('html', combined_html)
                    markdown = fallback.get('markdown', markdown)
                except Exception as fallback_exc:
                    logging.warning(f"액세서리 상세 fallback 실패: {fallback_exc}")

            recommendations = await page.evaluate("""() => {
                const results = [];
                const seen = new Set();
                const container = document.querySelector('.ui-viewPrd-cont.ui-best-cont');
                if (!container) {
                    return results;
                }
                container.querySelectorAll('li a').forEach(a => {
                    const href = a.getAttribute('href') || '';
                    let abs = '';
                    if (href) {
                        try {
                            abs = new URL(href, window.location.href).href;
                        } catch (err) {
                            abs = href;
                        }
                    }
                    if (!abs || seen.has(abs)) {
                        return;
                    }
                    seen.add(abs);
                    const name = (a.querySelector('.prd-tit')?.textContent || a.textContent || '').trim();
                    const desc = (a.querySelector('.total-price em, .price em, .prd-price em')?.textContent || '').trim();
                    const image = a.querySelector('img')?.src || '';
                    if (!name && !desc) {
                        return;
                    }
                    results.push({
                        kind: 'best',
                        name,
                        desc,
                        url: abs,
                        image
                    });
                });
                return results;
            }""")

            result = {
                'url': url,
                'murl': to_mshop_url(url),
                'title': title,
                'html': combined_html,
                'markdown': markdown,
                'status_code': status_detail,
                'recommendations': recommendations or [],
                'special_processed': True,
                'playwright_processed': True
            }

            if recommend_html:
                result['recommendations_html'] = recommend_html

            return result
        except Exception as exc:
            logging.warning(f"액세서리 상세 추출 실패 ({url}): {exc}")
            return None
        finally:
            try:
                await page.close()
            except Exception:
                pass

    if context is not None:
        return await _process_detail(context)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_local = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        )
        try:
            return await _process_detail(context_local)
        finally:
            await browser.close()


async def handle_accessory_display_list(url: str, fclient, menu: str = None) -> dict:
    from markdownify import markdownify as md

    logging.info(f"액세서리 display 핸들러 시작: url={url}, menu={menu}")

    menus: List[Dict[str, Any]] = []
    datas: List[Dict[str, Any]] = []
    seen_prodnos: Set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='networkidle', timeout=60000)
        status_code = response.status if response else None

        if status_code and status_code >= 400:
            logging.error(f"❌ 액세서리 목록 ({url}): HTTP {status_code} 오류")
        else:
            logging.info(f"✅ 액세서리 목록 ({url}): HTTP {status_code or 'unknown'}")

        await page.wait_for_timeout(1500)

        async def extract_items() -> List[Dict[str, Any]]:
            return await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('ul.ui-access-prdLst li a.ui-btn-access')).map((a, index) => ({
                    prodNo: a.getAttribute('prodno') || '',
                    onclick: a.getAttribute('onclick') || '',
                    title: (a.querySelector('.prd-tit')?.textContent || a.textContent || '').trim(),
                    price: (a.querySelector('.total-price em, .price-txt em, .payment em')?.textContent || '').replace(/[^0-9]/g, ''),
                    image: a.querySelector('img')?.src || '',
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
                except Exception as exc:
                    logging.debug(f"페이지 번호 {target} 이동 실패: {exc}")
            arrow_locator = page.locator('.pageWrap a')
            count = await arrow_locator.count()
            for idx in range(count):
                try:
                    text = (await arrow_locator.nth(idx).inner_text()).strip()
                except Exception:
                    continue
                if text == '>':
                    try:
                        await arrow_locator.nth(idx).click()
                        await page.wait_for_load_state('networkidle')
                        await page.wait_for_timeout(800)
                        return True
                    except Exception as exc:
                        logging.debug(f"다음 페이지 이동 실패: {exc}")
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
            logging.info(f"페이지 {current_page}: {len(items)}개 상품 발견")

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

    logging.info(f"총 {len(datas)}개 액세서리 상세 처리 완료")
    return {
        'menus': menus,
        'datas': datas,
        'total_processed': len(datas),
        'status': 'completed',
        'special_processed': True,
        'playwright_processed': True
    }


register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR042901',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR042902',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR042903',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043002',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043004',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043005',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043006',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043007',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043101',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043102',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043103',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043104',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043105',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043401',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043402',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043501',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043502',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043503',
    handle_accessory_display_list
)
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR043504',
    handle_accessory_display_list
)
# =========================
# 9. 영화예매 고객센터 FAQ 핸들러
# =========================

async def handle_movie_customer_center_faq_playwright(url: str, fclient, menu=None) -> dict:
    """
    영화예매 고객센터 FAQ 페이지 처리 핸들러
    - iframe 내부의 실제 FAQ URL을 처리하여 구조화된 FAQ로 변환
    - 모든 카테고리와 페이지네이션 처리
    - FAQ 외의 일반 페이지 내용도 함께 추출
    """
    logging.info(f"영화예매 고객센터 FAQ 핸들러 진입: url={url}")
    
    # 카테고리 정의
    categories = [
        {"id": "7", "name": "신규이용자"},
        {"id": "10", "name": "예매 관련"},
        {"id": "12", "name": "결제 관련"},
        {"id": "13", "name": "예매 취소"}
    ]
    
    all_qa_list = []
    page_content = ""
    page_html = ""
    
    # 먼저 기본 페이지 내용 추출 (FAQ 제외) - Playwright 사용
    try:
        logging.info("기본 페이지 내용 추출 시작")
        from playwright.async_api import async_playwright
        from markdownify import markdownify as md
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(url, wait_until='domcontentloaded')
            await page.wait_for_timeout(3000)  # 페이지 로딩 대기
            
            # iframe 처리 - FAQ 내용이 iframe 안에 있으므로 iframe으로 이동
            iframe_element = await page.query_selector('#iFrmMileage')
            if iframe_element:
                logging.info("iframe 발견, iframe 내부로 이동")
                frame = await iframe_element.content_frame()
                
                if frame:
                    # iframe 내부에서 content-box 요소 찾기
                    content_element = await frame.query_selector('div.content-box')
                    if content_element:
                        # FAQ 관련 요소들 및 불필요한 요소 제거
                        faq_selectors = [
                            # FAQ 관련
                            '.faq_box', '.faq', '.faq-list', '.faq-item', '.inquiry', '.answer', '.faqClass',
                            'img[src*="faq"]', 'img[src*="FAQ"]',
                            'a[href*="faq"]', 'a[href*="FAQ"]',
                            'p:has-text("FAQ")', 'p:has-text("faq")',
                            'div:has-text("FAQ")', 'div:has-text("faq")',
                            'span:has-text("FAQ")', 'span:has-text("faq")',
                            'li:has-text("FAQ")', 'li:has-text("faq")',
                            # Header/Footer/Navigation
                            'header', 'footer', 
                            '.header', '.footer',
                            '#header', '#footer',
                            '#cfmClHeader', '#cfmClFooter',
                            '.inner', 'nav', '.navigation'
                        ]
                        
                        for selector in faq_selectors:
                            try:
                                elements = await content_element.query_selector_all(selector)
                                for element in elements:
                                    await element.evaluate('element => element.remove()')
                            except:
                                pass  # 셀렉터가 유효하지 않을 수 있음
                        
                        page_html = await content_element.inner_html()
                        page_markdown = md(page_html) if page_html else ""
                        logging.info(f"iframe 내부에서 기본 페이지 내용 추출 완료: 마크다운 {len(page_markdown)}자, HTML {len(page_html)}자")
                    else:
                        logging.warning("iframe 내부에서 content-box 요소를 찾을 수 없습니다")
                        page_markdown = ""
                        page_html = ""
                else:
                    logging.warning("iframe에 접근할 수 없습니다 (cross-origin)")
                    page_markdown = ""
                    page_html = ""
            else:
                # iframe이 없으면 cfmClContents에서 추출
                content_element = await page.query_selector('#cfmClContents')
                if content_element:
                    page_html = await content_element.inner_html()
                    page_markdown = md(page_html) if page_html else ""
                    logging.info(f"cfmClContents에서 기본 페이지 내용 추출 완료: 마크다운 {len(page_markdown)}자, HTML {len(page_html)}자")
                else:
                    logging.warning("cfmClContents 요소를 찾을 수 없습니다")
                    page_markdown = ""
                    page_html = ""
            
            await browser.close()
        
    except Exception as e:
        logging.error(f"기본 페이지 내용 추출 중 오류: {e}")
        page_markdown = ""
        page_html = ""
    
    # FAQ 추출
    logging.info("FAQ 추출 시작")
    
    # 각 카테고리별로 FAQ 추출
    for category in categories:
        logging.info(f"카테고리 처리 시작: {category['name']}")
        
        page_num = 1
        category_qa_count = 0
        
        while True:
            # 카테고리별 페이지 URL 구성
            category_url = f"https://showmovie.mobile.kt.com/Customer/FaqList.aspx?qIdx={category['id']}&Page={page_num}"
            logging.info(f"  페이지 {page_num} 처리: {category_url}")
            
            try:
                # HTTP 요청으로 페이지 내용 가져오기 (더 빠름)
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(category_url) as response:
                        # HTTP 상태 코드 확인 및 로깅
                        if response.status >= 400:
                            logging.error(f"❌ 영화예매 FAQ ({category_url}): HTTP {response.status} 오류")
                        elif response.status >= 300:
                            logging.warning(f"⚠️ 영화예매 FAQ ({category_url}): HTTP {response.status} 리다이렉트")
                        else:
                            logging.info(f"✅ 영화예매 FAQ ({category_url}): HTTP {response.status} 성공")
                        
                        if response.status == 200:
                            page_content = await response.text()
                        else:
                            logging.warning(f"페이지 요청 실패: {response.status}")
                            break
                
                # HTML에서 FAQ 파싱
                page_faqs = parse_movie_faq_from_html_content(page_content, category['name'])
                
                if not page_faqs:
                    logging.info(f"  페이지 {page_num}에 FAQ가 없음. 카테고리 처리 종료")
                    break
                
                # 결과에 추가
                for faq in page_faqs:
                    faq['page'] = page_num
                    all_qa_list.append(faq)
                    category_qa_count += 1
                
                logging.info(f"  페이지 {page_num} 완료: {len(page_faqs)}개 FAQ 추출")
                
                # 다음 페이지 확인 (페이지네이션 링크가 있는지 확인)
                if f'Page={page_num + 1}' in page_content:
                    page_num += 1
                else:
                    logging.info(f"  더 이상 페이지가 없음. 카테고리 처리 종료")
                    break
                    
            except Exception as e:
                logging.error(f"카테고리 {category['name']} 페이지 {page_num} 처리 실패: {str(e)}")
                break
        
        logging.info(f"카테고리 {category['name']} 처리 완료: 총 {category_qa_count}개 FAQ")
    
    logging.info(f"영화예매 고객센터 FAQ 전체 추출 완료: 총 {len(all_qa_list)}개 FAQ")
    
    # crawl4ai에서 이미 마크다운을 받았으므로 추가 변환 불필요
    
    logging.info(f"qa_list 준비 완료: {len(all_qa_list)}개 FAQ")
    
    return {
        "url": url,  # URL 필드 추가 (url.txt 생성용)
        "markdown": page_markdown,  # FAQ 제외한 일반 페이지 내용만
        "html": page_html,  # HTML은 유지
        "qa_list": all_qa_list,  # FAQ 데이터만 별도 저장
        "total_categories": len(categories),
        "total_qa": len(all_qa_list),
        "special_processed": True,
        "playwright_processed": True
    }

def parse_movie_faq_from_html_content(html_content: str, category_name: str) -> list:
    """HTML 내용에서 FAQ 리스트를 파싱하여 반환"""
    try:
        import re
        
        faqs = []
        
        # 정규식으로 FAQ 패턴 찾기
        faq_pattern = r'<a href="#" class="inquiry"><em class="icon_q">Q 질문</em><span>([^<]+)</span></a>\s*<div class="answer">.*?<div class="answer-inner">\s*<p>(.*?)</p>'
        matches = re.findall(faq_pattern, html_content, re.DOTALL)
        
        logging.info(f"  {category_name} 카테고리에서 발견된 FAQ: {len(matches)}개")
        
        for idx, (question, answer) in enumerate(matches):
            try:
                question = question.strip()
                answer = answer.strip()
                
                # HTML 엔티티 디코딩 및 정리
                question = question.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                answer = answer.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                answer = answer.replace('<br/>', '\n').replace('<br>', '\n')
                
                if question and answer:
                    faqs.append({
                        "category": category_name,
                        "question": question,
                        "answer": answer
                    })
                    logging.info(f"    FAQ {idx+1} 파싱 완료: {question[:50]}...")
            
            except Exception as e:
                logging.error(f"    FAQ 항목 {idx+1} 파싱 실패: {str(e)}")
                continue
        
        return faqs
        
    except Exception as e:
        logging.error(f"HTML 파싱 실패: {str(e)}")
        return []
def parse_movie_faq_from_html(html_content: str) -> dict:
    """HTML 내용에서 FAQ를 파싱하여 구조화된 데이터로 변환"""
    try:
        import re
        
        markdown_body = ""
        all_qa_list = []
        
        logging.info(f"HTML 파싱 시작: 내용 길이 {len(html_content)} 문자")
        
        # 정규식으로 FAQ 패턴 찾기
        # <span>질문</span> 다음에 오는 <div class="answer-inner"><p>답변</p></div> 패턴
        faq_pattern = r'<span>([^<]+)</span>.*?<div class="answer-inner">\s*<p>(.*?)</p>'
        matches = re.findall(faq_pattern, html_content, re.DOTALL)
        
        logging.info(f"정규식으로 발견된 FAQ 패턴: {len(matches)}개")
        
        if len(matches) < 5:  # 예상보다 적으면 다른 패턴 시도
            # 더 포괄적인 패턴으로 재시도
            faq_pattern2 = r'<a href="#" class="inquiry"><em class="icon_q">Q 질문</em><span>([^<]+)</span></a>\s*<div class="answer">.*?<div class="answer-inner">\s*<p>(.*?)</p>'
            matches2 = re.findall(faq_pattern2, html_content, re.DOTALL)
            logging.info(f"포괄적 패턴으로 발견된 FAQ: {len(matches2)}개")
            if len(matches2) > len(matches):
                matches = matches2
        
        for idx, (question, answer) in enumerate(matches):
            try:
                question = question.strip()
                answer = answer.strip()
                
                # HTML 엔티티 디코딩
                question = question.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                answer = answer.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                
                if question and answer:
                    category_name = "신규이용자"  # 기본 카테고리
                    all_qa_list.append({
                        "category": category_name,
                        "question": question,
                        "answer": answer,
                        "page": 1
                    })
                    logging.info(f"정규식 FAQ 파싱 완료 {idx+1}: {question[:50]}...")
            
            except Exception as e:
                logging.error(f"FAQ 항목 {idx+1} 파싱 실패: {str(e)}")
                continue
        
        logging.info(f"HTML 파싱 완료: 총 {len(all_qa_list)}개 FAQ")
        
        # qa_list는 app.py에서 저장하므로 여기서는 반환만 함
        return {
            "markdown": "",  # FAQ 내용 제거
            "qa_list": all_qa_list,
            "total_categories": 1,
            "total_qa": len(all_qa_list),
            "special_processed": True,
            "playwright_processed": True
        }
        
    except Exception as e:
        logging.error(f"HTML 파싱 실패: {str(e)}")
        return {
            "markdown": "",
            "qa_list": [],
            "total_categories": 0,
            "total_qa": 0,
            "special_processed": True,
            "playwright_processed": True
        }

def parse_movie_faq_from_markdown(markdown_content: str) -> dict:
    """마크다운 내용에서 FAQ를 파싱하여 구조화된 데이터로 변환"""
    try:
        import re
        
        markdown_body = ""
        all_qa_list = []
        
        # FAQ 패턴 찾기
        # "Q 질문" 다음에 오는 텍스트를 질문으로, 그 다음 블록을 답변으로 추출
        faq_pattern = r'\*Q 질문\*([^\n]+)\n\n\s*\*Q\*\n\n(.+?)(?=\n\n\s*상세보기 닫힘|\n\n\*Q 질문\*|$)'
        matches = re.findall(faq_pattern, markdown_content, re.DOTALL)
        
        logging.info(f"마크다운에서 발견된 FAQ 패턴: {len(matches)}개")
        
        for idx, (question, answer) in enumerate(matches):
            question = question.strip()
            answer = answer.strip()
            
            if question and answer:
                category_name = "신규이용자"  # 기본 카테고리
                all_qa_list.append({
                    "category": category_name,
                    "question": question,
                    "answer": answer,
                    "page": 1
                })
                logging.info(f"마크다운 FAQ 파싱 완료 {idx+1}: {question[:50]}...")
        
        logging.info(f"마크다운 파싱 완료: 총 {len(all_qa_list)}개 FAQ")
        
        return {
            "markdown": "",  # FAQ 내용 제거
            "qa_list": all_qa_list,
            "total_categories": 1,
            "total_qa": len(all_qa_list),
            "special_processed": True,
            "playwright_processed": True
        }
        
    except Exception as e:
        logging.error(f"마크다운 파싱 실패: {str(e)}")
        return {
            "markdown": "",
            "qa_list": [],
            "total_categories": 0,
            "total_qa": 0,
            "special_processed": True,
            "playwright_processed": True
        }



# 영화예매 고객센터 FAQ 핸들러 등록
register_page_handler(
    r'https?://membership\.kt\.com/culture/movie/CustomerCenterInfo\.do',
    handle_movie_customer_center_faq_playwright
)
async def handle_ermsweb_faq_all_playwright(url: str, fclient, menu=None) -> dict:
    """
    모든 카테고리, 모든 페이지, 모든 Q/A를 gigagenie handler 포맷으로 추출하는 handler
    - 타임아웃 개선 및 안정성 향상
    """
    logging.info(f"ERMS FAQ 핸들러 진입: url={url}")
    
    # 재시도 메커니즘 설정
    max_retries = 2
    base_timeout = 60000  # 60초 기본 타임아웃
    
    for attempt in range(max_retries):
        try:
            logging.info(f"ERMS FAQ 페이지 진입 시도 {attempt + 1}/{max_retries}: url={url}")
            
            # 시도별로 다른 로딩 전략 적용
            if attempt == 0:
                wait_until = "domcontentloaded"
                timeout = 50000
                extra_wait = 5000
            else:
                wait_until = "networkidle"
                timeout = base_timeout
                extra_wait = 8000
            
            # 완전히 새로운 브라우저 세션으로 시작
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # 페이지 로드
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)
                await page.wait_for_timeout(extra_wait)
                
                # HTTP 상태 코드 확인 및 로깅
                status_code = response.status if response else None
                if status_code:
                    if status_code >= 400:
                        logging.error(f"❌ ERMS FAQ ({url}): HTTP {status_code} 오류")
                    elif status_code >= 300:
                        logging.warning(f"⚠️ ERMS FAQ ({url}): HTTP {status_code} 리다이렉트")
                    else:
                        logging.info(f"✅ ERMS FAQ ({url}): HTTP {status_code} 성공")
                else:
                    logging.debug(f"🔍 ERMS FAQ ({url}): 상태 코드 정보 없음")
                
                # 페이지 로딩 상태 확인
                try:
                    await page.wait_for_selector("ul#tab-slide-menu li a", timeout=30000)
                    logging.info("ERMS FAQ 페이지 로딩 완료")
                except Exception as e:
                    logging.warning(f"ERMS FAQ 페이지 로딩 대기 실패: {e}, 계속 진행")

                markdown_body = ""
                all_qa_list = []
                page_html = ""
                
                # 기본 페이지 내용 추출 (FAQ 제외) - Playwright 사용
                try:
                    logging.info("기본 페이지 내용 추출 시작")
                    from markdownify import markdownify as md
                    
                    # FAQ 관련 요소들 및 불필요한 요소 제거
                    faq_selectors = [
                        # FAQ 관련
                        'ul#faqList', '.faqList', 
                        '.accordion-area', '.accordion',
                        '.faq_box', '.faq', '.faq-list', '.faq-item', 
                        '.inquiry', '.answer', '.faqClass',
                        'img[src*="faq"]', 'img[src*="FAQ"]',
                        'a[href*="faq"]', 'a[href*="FAQ"]',
                        'ul.accordions',  # ERMS FAQ 리스트
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
                    logging.info(f"기본 페이지 내용 추출 완료: 마크다운 {len(page_markdown)}자, HTML {len(page_html)}자")
                except Exception as e:
                    logging.error(f"기본 페이지 내용 추출 중 오류: {e}")
                    page_markdown = ""
                    page_html = ""
                
                # FAQ 추출을 위해 페이지 새로고침
                await page.reload()
                await page.wait_for_timeout(3000)

                # 1. 카테고리 추출
                categories = await page.query_selector_all("ul#tab-slide-menu li a")
                category_info = []
                for a in categories:
                    nodeid = await a.get_attribute("data-nodeid")
                    nodename = await a.get_attribute("data-nodename") or (await a.inner_text()).replace('\n', ' ').strip()
                    category_info.append({"nodeid": nodeid, "nodename": nodename, "element": a})
                
                logging.info(f"총 {len(category_info)}개 카테고리 발견: {[cat['nodename'] for cat in category_info]}")

                for cat_idx, cat in enumerate(category_info):
                    # 카테고리 클릭
                    await cat["element"].click()
                    await page.wait_for_timeout(1500)
                    faq_category = cat["nodename"]
                    logging.info(f"카테고리 {cat_idx + 1}/{len(category_info)} 처리 시작: {faq_category}")

                    # 마지막 페이지 번호 추출
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
                    
                    logging.info(f"카테고리 '{faq_category}': 총 {last_page}개 페이지 발견")

                    category_qa_count = 0
                    for page_num in range(1, last_page + 1):
                        # 페이지 이동 (1페이지는 이미 로딩됨)
                        if page_num > 1:
                            page_btns = await page.query_selector_all('.pagination .scope a')
                            for btn in page_btns:
                                if (await btn.inner_text()).strip() == str(page_num):
                                    await btn.click()
                                    await page.wait_for_timeout(1500)
                                    break

                        # Q/A 추출
                        faq_items = await page.query_selector_all('ul.accordions > li.liWrap')
                        logging.info(f"페이지 {page_num}/{last_page}: {len(faq_items)}개 FAQ 항목 발견")
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
                                # 마크다운/구조화
                                markdown_body += f"{category}\n{question}\n{answer}\n***\n"
                                all_qa_list.append({
                                    "category": category,
                                    "question": question,
                                    "answer": answer,
                                    "page": page_num
                                })
                                category_qa_count += 1
                            except Exception as e:
                                logging.warning(f"FAQ 항목 처리 실패: {str(e)}")
                                continue
                    
                    logging.info(f"카테고리 '{faq_category}' 처리 완료: 총 {category_qa_count}개 FAQ")

                await browser.close()
                
                # 성공적으로 처리된 경우 결과 반환
                logging.info(f"🎉 ERMS FAQ 전체 추출 완료: 총 카테고리 {len(category_info)}개, 총 FAQ {len(all_qa_list)}개")
                logging.info(f"qa_list 준비 완료: {len(all_qa_list)}개 FAQ")
                
                return {
                    "url": url,  # URL 필드 추가 (url.txt 생성용)
                    "markdown": page_markdown,  # FAQ 제외한 일반 페이지 내용
                    "html": page_html,
                    "qa_list": all_qa_list,
                    "total_categories": len(category_info),
                    "total_qa": len(all_qa_list),
                    "special_processed": True,
                    "playwright_processed": True
                }
                
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"ERMS FAQ 페이지 처리 시도 {attempt + 1} 실패: {str(e)} - 재시도 중...")
                await asyncio.sleep(5)  # 재시도 전 5초 대기
                continue
            else:
                logging.error(f"ERMS FAQ 페이지 처리 최종 실패: {str(e)}")
                return {
                    "markdown": f"ERMS FAQ 처리 실패: {str(e)}",
                    "html": f"<p>ERMS FAQ 처리 실패: {str(e)}</p>",
                    "qa_list": [],
                    "total_categories": 0,
                    "total_qa": 0,
                    "special_processed": True,
                    "playwright_processed": True,
                    "error": str(e)
                }


# ermsweb FAQ 핸들러 등록
register_page_handler(
    r'https?://ermsweb\.kt\.com/pc/faq/faqList\.do',
    handle_ermsweb_faq_all_playwright
)

# =========================
# 10-B. KT Shop 팝업 처리 공통 핸들러 (layerOpen/hash, void(0)+.plus)
# =========================
async def handle_ktshop_popup_extractor(url: str, fclient, menu=None) -> dict:
    """
    KT Shop 페이지에서 다음 조건의 트리거를 모두 순회하여 팝업 내용을 추출하고,
    트리거 위치에 팝업 내용을 삽입한 뒤 article 태그의 원본 팝업 영역은 제외하여 최종 콘텐츠를 구성한다.

    - 해시 대상 + layerOpen('#id', this)
    - href="javascript:void(0)" 이고 class에 'plus' 포함

    규칙:
    1) 기본 페이지 내용은 유지하되, 팝업 내용만 트리거 위치에 인라인 삽입
    2) 팝업 추출 후 오버레이는 닫거나 무시하도록 처리
    3) 팝업 외 원본 article 태그는 최종 HTML에서 제거
    """
    import re
    import time
    logging.info(f"KT Shop 팝업 처리 핸들러 진입: url={url}, menu={menu}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        try:
            response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(2500)

            status_code = response.status if response else None
            if status_code:
                if status_code >= 400:
                    logging.error(f"❌ KT Shop 팝업 ({url}): HTTP {status_code} 오류")
                elif status_code >= 300:
                    logging.warning(f"⚠️ KT Shop 팝업 ({url}): HTTP {status_code} 리다이렉트")
                else:
                    logging.info(f"✅ KT Shop 팝업 ({url}): HTTP {status_code} 성공")
            else:
                logging.debug(f"🔍 KT Shop 팝업 ({url}): 상태 코드 정보 없음")

            # 트리거 수집: layerOpen('#id') 형태 (모든 태그 대상)
            hash_triggers = await page.query_selector_all("*[onclick*='layerOpen(']")
            # 트리거 수집: javascript:void(0) + class 포함 'plus', 또는 showDeviceModel/showDeviceInfo 호출 요소
            plus_triggers = await page.query_selector_all(
                "a[href^='javascript:void(0)'].plus, .plus[href^='javascript:void(0)'], *[onclick*='showDeviceModel('], *[onclick*='showDeviceInfo(']"
            )

            logging.info(f"발견된 트리거: layerOpen={len(hash_triggers)}, plus={len(plus_triggers)}")

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
                            // body 스크롤 제한 해제
                            document.body.style.overflow = 'auto';
                        }
                    """)
                except Exception as e:
                    logging.debug(f"오버레이 숨김 실패(무시): {str(e)}")

            async def _wait_for_visible_popup_html(timeout_ms=5000, preferred_selectors=None):
                """클릭 후 지정 시간 동안 반복적으로 가시 팝업을 탐지하여 HTML을 반환"""
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
                    logging.warning(f"트리거 뒤 삽입 실패: {str(e)}")

            # 1) layerOpen('#id') 트리거 처리
            for idx, a in enumerate(hash_triggers, 1):
                try:
                    onclick_text = await a.get_attribute('onclick')
                    target_id = None
                    if onclick_text:
                        m = re.search(r"layerOpen\(\s*['\"](#[^'\"]+)['\"]", onclick_text)
                        if m:
                            target_id = m.group(1)
                    logging.info(f"[layerOpen] 트리거 {idx}/{len(hash_triggers)} 처리: target={target_id}")
                    try:
                        await a.click()
                    except Exception:
                        # click 막힐 경우 JS로 직접 호출 시도
                        await page.evaluate("el => el.click()", a)
                    await page.wait_for_timeout(900)

                    popup_html = ""
                    if target_id:
                        try:
                            target_el = await page.query_selector(target_id)
                            if target_el and await target_el.is_visible():
                                popup_html = await target_el.inner_html()
                            elif target_el:
                                # 보이지 않아도 강제로 표시 후 추출
                                await page.evaluate("sel => { const el = document.querySelector(sel); if (el){ el.style.display='block'; el.style.visibility='visible'; el.style.opacity='1'; } }", target_id)
                                await page.wait_for_timeout(200)
                                popup_html = await target_el.inner_html()
                        except Exception as e:
                            logging.warning(f"target 엘리먼트 추출 실패: {str(e)}")
                    if not popup_html:
                        # 가시 팝업을 최대 5초까지 탐지
                        popup_html = await _wait_for_visible_popup_html(5000)

                    if popup_html:
                        await _insert_after_trigger(a, popup_html)
                    else:
                        logging.info("팝업 내용이 비어있음")

                    # 오버레이 닫기/무시 처리
                    await _hide_overlays()
                    # ESC 시도 (일부 레이어)
                    try:
                        await page.keyboard.press('Escape')
                    except Exception:
                        pass
                    await page.wait_for_timeout(200)
                except Exception as e:
                    logging.warning(f"layerOpen 트리거 처리 실패 {idx}: {str(e)}")

            # 2) javascript:void(0) + .plus 트리거 처리
            for idx, a in enumerate(plus_triggers, 1):
                try:
                    onclick_text = (await a.get_attribute('onclick')) or ''
                    logging.info(f"[plus] 트리거 {idx}/{len(plus_triggers)} 처리 onclick='{onclick_text[:60]}'")
                    preferred_selectors = []
                    if 'showDeviceModel' in onclick_text:
                        preferred_selectors = ['#esim-phone-model']
                    elif 'showDeviceInfo' in onclick_text:
                        preferred_selectors = ['#phone-check-information']
                    try:
                        await a.click()
                    except Exception:
                        await page.evaluate("el => el.click()", a)
                    await page.wait_for_timeout(900)

                    # 가시 팝업을 최대 5초까지 탐지 (우선 선택자 먼저)
                    popup_html = await _wait_for_visible_popup_html(5000, preferred_selectors)

                    if popup_html:
                        await _insert_after_trigger(a, popup_html)
                    else:
                        logging.info("plus 트리거 팝업 내용이 비어있음")

                    await _hide_overlays()
                    try:
                        await page.keyboard.press('Escape')
                    except Exception:
                        pass
                    await page.wait_for_timeout(200)
                except Exception as e:
                    logging.warning(f"plus 트리거 처리 실패 {idx}: {str(e)}")

            # 팝업 원본 article 내용 제거 (삽입본만 유지)
            try:
                await page.evaluate("""
                    () => {
                        // article 태그 내부를 비우되, ai-popup-extracted 만 보존
                        document.querySelectorAll('article').forEach(article => {
                            const keeps = Array.from(article.querySelectorAll('.ai-popup-extracted'));
                            // 기존 내용 제거
                            while (article.firstChild) article.removeChild(article.firstChild);
                            // 보존 요소 재삽입
                            keeps.forEach(node => {
                                // 원래 노드를 이동시키면 원본 위치에서 빠질 수 있으니 복제본을 사용
                                const clone = node.cloneNode(true);
                                article.appendChild(clone);
                            });
                        });
                        // 공통 불필요 요소 제거
                        const removeSelectors = [
                            '#cfmClHeader', '#cfmClFooter', '#cfmClSkip',
                            '.location', '.sns-area', '.opener',
                            '.swiper-controls-wrapper', '.opage-hashtag-arrow', '.swiper-button-next', '.swiper-button-prev',
                            '.icon.kakao', '.icon.facebook', '.icon.twitter', '.icon.youtube',
                            '.btn-twitter', '.btn-facebook', '.btn-kakao', '.btn-youtube'
                        ];
                        removeSelectors.forEach(sel => {
                            document.querySelectorAll(sel).forEach(e => e.remove());
                        });
                        // 숨김 요소 제거
                        document.querySelectorAll('[style*="display:none"]').forEach(e => e.remove());
                        document.querySelectorAll('.invisible').forEach(e => e.remove());
                    }
                """)
            except Exception as e:
                logging.debug(f"article 제거/정리 실패(무시): {str(e)}")

            # 최종 HTML 수집 (#cfmClContents 우선)
            try:
                html_content = await page.eval_on_selector("#cfmClContents", "el => el.outerHTML")
            except Exception:
                html_content = await page.content()

            title = await page.title()
            await browser.close()

        except Exception as e:
            logging.error(f"❌ KT Shop 팝업 처리 실패: {str(e)}")
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

    # HTML → 마크다운 변환 (추가 포맷 없이 본문만)
    try:
        from markdownify import markdownify as md
        markdown_content = md(html_content, heading_style="ATX")
    except Exception as e:
        logging.warning(f"마크다운 변환 실패: {str(e)}")
        markdown_content = ""

    logging.info("🎉 KT Shop 팝업 처리 완료")

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

# 핸들러 등록 - 지정 URL들 (기존 전용 핸들러 미사용 대상)
register_page_handler(
    r'https?://shop\.kt\.com/direct/directEsim\.do',
    handle_ktshop_popup_extractor
)

register_page_handler(
    r'https?://shop\.kt\.com/direct/directUsim\.do',
    handle_ktshop_popup_extractor
)

register_page_handler(
    r'https?://shop\.kt\.com/direct/quickUsim\.do',
    handle_ktshop_popup_extractor
)

register_page_handler(
    r'https?://shop\.kt\.com/direct/directChangeRate\.do',
    handle_ktshop_popup_extractor
)
register_page_handler(
    r'https?://shop\.kt\.com/direct/directSharing\.do',
    handle_ktshop_popup_extractor
)

# 듀얼번호가입
register_page_handler(
    r'https?://shop\.kt\.com/direct/directDual\.do',
    handle_ktshop_popup_extractor
)

# 선불USIM구매충전
register_page_handler(
    r'https?://shop\.kt\.com/unify/mobile\.do\?.*category=usim',
    handle_ktshop_popup_extractor
)

# 스마트기기요금제가입
register_page_handler(
    r'https?://shop\.kt\.com/direct/directSmart\.do',
    handle_ktshop_popup_extractor
)

# eSIM이동
register_page_handler(
    r'https?://shop\.kt\.com/direct/directEsimMove\.do',
    handle_ktshop_popup_extractor
)
# =========================
# 10-C. 모바일 제품 리스트 핸들러 (products.do?category=*)
# =========================
async def handle_mobile_products_list(url: str, fclient, menu=None) -> dict:
    """
    모바일 제품 리스트 페이지 처리 핸들러
    - 리스트에서 prodnm(제품명) 및 상세 진입 정보 수집
    - 각 제품 상세에서 '제품 특징', '유의사항' 추출
    - 메뉴명: Shop^모바일 가입^핸드폰^{prodnm}
    """
    from markdownify import markdownify as md
    logging.info(f"모바일 제품 리스트 핸들러 진입: url={url}, menu={menu}")
    menus, datas = [], []
    base_menu = (menu or '').strip()
    base_title = base_menu.split('^')[-1].strip() if base_menu else '모바일 제품 리스트'
    base_title = sanitize_filename(base_title)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(2500)

        try:
            await page.wait_for_function(
                "document.querySelectorAll('.nwProdList input[name=\"prodAttr\"]').length > 0",
                timeout=20000,
            )
        except Exception:
            logging.warning(
                "⚠️ 모바일 제품 리스트: prodAttr 요소를 찾지 못했습니다. 기본 페이지 캡처만 진행될 수 있습니다."
            )

        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ 모바일 제품 리스트 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ 모바일 제품 리스트 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ 모바일 제품 리스트 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 모바일 제품 리스트 ({url}): 상태 코드 정보 없음")

        # 메인 페이지 콘텐츠 추출 (메뉴 기본 페이지 저장)
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
            logging.warning("⚠️ 모바일 제품 리스트: 메인 영역 HTML 추출 실패, body 전체를 사용합니다.")
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

        # 1) 리스트에서 제품명/상세 진입 정보 수집
        product_items = await page.evaluate(r"""
            () => {
                const results = [];
                // 리스트 컨테이너 한정
                const roots = Array.from(document.querySelectorAll('.nwProdList'));
                for (const root of roots){
                    // 숨겨진 input[name=prodAttr]에서 메타 수집 (상세 view.do 구성용 파라미터 포함)
                    root.querySelectorAll('input[name="prodAttr"]').forEach((inp) => {
                        const prodnm = inp.getAttribute('prodnm') || '';
                        const prodno = inp.getAttribute('prodno') || '';
                        const imageurl = inp.getAttribute('imageurl') || '';
                        const sntyno = inp.getAttribute('sntyno') || '';
                        const pplid = inp.getAttribute('pplid') || '';
                        const svcengtmonstypecd = inp.getAttribute('svcengtmonstypecd') || '';
                        const supporttype = inp.getAttribute('supporttype') || '';
                        if (prodnm) {
                            results.push({ prodnm, prodno, imageurl, sntyno, pplid, svcengtmonstypecd, supporttype });
                        }
                    });
                    // 앵커 기반 상세 경로 추정 (가능하면) — 리스트 내부로 제한
                    root.querySelectorAll('a[href]').forEach(a => {
                        const href = a.getAttribute('href')||'';
                        const title = (a.textContent||'').trim();
                        if (/productDetail\.do\?ItemCode=/.test(href) || /mobile\/view\.do\?/.test(href)){
                            try {
                                const abs = new URL(href, location.href).href;
                                results.push({ anchorHref: abs, title });
                            } catch(e) {}
                        }
                    });
                }
                return results;
            }
        """)

        logging.info(f"리스트 수집: {len(product_items)}개 원시 항목")

        # 2) 제품별 대표 정보 정리 및 상세 추출
        normalized = []
        seen_names = set()

        for item in product_items:
            try:
                # 제품명은 prodnm(숨겨진 input 기반)만 인정
                prodnm = (item.get('prodnm') or '').strip()
            except Exception:
                prodnm = ''
            if not prodnm or prodnm in seen_names:
                continue
            seen_names.add(prodnm)
            # 상세 URL 구성: 우선 anchorHref, 없으면 view.do 조합 시도, 최종 폴백은 리스트 URL
            detail_url = item.get('anchorHref')
            if not detail_url:
                prodno = (item.get('prodno') or '').strip()
                sntyno = (item.get('sntyno') or '').strip()
                pplid = (item.get('pplid') or '').strip()
                svc_value = item.get('svcengtmonstypecd') or ''
                svc = svc_value.strip()
                support = (item.get('supporttype') or '').strip()
                if prodno:
                    const_params = []
                    if sntyno:
                        const_params.append(f"sntyNo={sntyno}")
                    if pplid:
                        const_params.append(f"pplId={pplid}")
                    if svc:
                        const_params.append(f"svcEngtMonsTypeCd={svc}")
                    if support:
                        const_params.append(f"supportType={support}")
                    qp = ("&".join(const_params))
                    base = f"https://shop.kt.com/mobile/view.do?prodNo={prodno}"
                    detail_url = base + (f"&{qp}" if qp else '')
            normalized.append({ 'name': prodnm, 'url': detail_url or url, 'prodno': item.get('prodno','') })

        logging.info(f"정규화된 제품: {len(normalized)}개")

        # 3) 각 제품 상세에서 '제품 특징', '유의사항' 추출
        for idx, prod in enumerate(normalized, 1):
            try:
                logging.info(f"[{idx}/{len(normalized)}] 상세 추출: {prod['name']}")
                # 제품 상세 페이지로 이동
                if prod.get('url') and prod['url'] != url:
                    try:
                        await page.goto(prod['url'], wait_until='domcontentloaded', timeout=60000)
                        await page.wait_for_timeout(1200)
                    except Exception as _e:
                        logging.warning(f"상세 페이지 이동 실패(무시하고 계속): {prod['url']} -> {_e}")

                # 상세 컨테이너 한정 추출 + 탭 클릭 시도(유의사항/상품정보)
                await page.evaluate(r"""
                    () => {
                        // 상세 영역 근처만 대상으로 탭 클릭을 시도한다
                        const roots = ['#cfmClContents', '.nwViewProdDetail', '.prodDetailWrap', '.prodDetail'];
                        const within = [];
                        for (const sel of roots){
                            const el = document.querySelector(sel);
                            if (el) within.push(el);
                        }
                        const clickByText = (root, text) => {
                            const cands = root.querySelectorAll('a,button,[role="tab"],li');
                            for (const el of cands){
                                const t = (el.innerText||'').replace(/\s+/g,' ').trim();
                                if (!t) continue;
                                if (t === text || t.includes(text)){
                                    if (el.classList && el.classList.contains('nwWindowPop')) continue; // 외부 팝업 배제
                                    try { el.click(); return true; } catch(e) {}
                                }
                            }
                            return false;
                        };
                        const clickBySelector = (sel) => {
                            const el = document.querySelector(sel);
                            if (!el) return false;
                            try { el.click(); return true; } catch(e) { return false; }
                        };
                        for (const root of within){
                            // 1) 명시적 ID/속성 우선: prodDetailTab, [nw-target="#view-1"]
                            if (clickBySelector('#prodDetailTab')) continue;
                            if (clickBySelector('[nw-target="#view-1"]')) continue;
                            // 2) 텍스트 폴백
                            clickByText(root, '상품정보');
                        }
                    }
                """)
                await page.wait_for_timeout(300)
                # display:none 패널 강제 표시 후, 상세 루트 전체 추출 우선
                await page.evaluate("""
                    () => {
                        const root = document.querySelector('.nwViewProdDetail')
                          || document.querySelector('#cfmClContents')
                          || document.querySelector('.prodDetailWrap')
                          || document.querySelector('.prodDetail');
                        if (!root) return;
                        const show = (el) => {
                            if (!el) return;
                            try {
                                el.style.display = 'block';
                                el.style.visibility = 'visible';
                                el.style.opacity = '1';
                                el.style.height = 'auto';
                                el.style.maxHeight = 'none';
                            } catch (e) {}
                        };
                        ['#view-1', '#view-4'].forEach(sel => show(root.querySelector(sel)));
                        root.querySelectorAll('[nw-tab]').forEach(show);
                    }
                """)
                await page.wait_for_timeout(120)

                detail_html = await page.evaluate("""
                    () => {
                        // 가능하면 상세 루트(.nwViewProdDetail) 전체를 우선
                        const containers = ['.nwViewProdDetail', '#cfmClContents', '.prodDetailWrap', '.prodDetail', '#view-1'];
                        let targetEl = null;
                        for (const sel of containers){
                            const el = document.querySelector(sel);
                            if (el && el.innerHTML && el.innerHTML.trim().length>0) {
                                targetEl = el;
                                break;
                            }
                        }
                        if (!targetEl) {
                            targetEl = document.body;
                        }
                        
                        // 유의사항, 구매후기, 전문상담 영역 제거 (정확한 셀렉터 사용)
                        if (targetEl) {
                            const clone = targetEl.cloneNode(true);
                            
                            // 정확한 셀렉터로 제거
                            const removeSelectors = [
                                '#noteArea',            // 유의사항 컨텐츠 영역
                                '#noteTab',             // 유의사항 컨텐츠 영역 (다른 구조)
                                '#view-4',              // 유의사항 탭 패널
                                'button[nw-target="#noteTab"]',     // 유의사항 탭 버튼
                                'button[nw-target="#view-4"]',      // 유의사항 탭 버튼 (다른 구조)
                                '[nw-tab="#view-4"]',   // 유의사항 탭 패널
                                '#reviewTab',           // 구매후기 컨텐츠 영역
                                '#prodReviewTab',       // 구매후기 탭 버튼
                                '#counselTab',          // 전문상담 컨텐츠 영역
                                'button[nw-target="#counselTab"]'  // 전문상담 탭 버튼
                            ];
                            
                            removeSelectors.forEach(selector => {
                                try {
                                    const el = clone.querySelector(selector);
                                    if (el) {
                                        el.remove();
                                    }
                                } catch(e) {
                                    // 셀렉터 오류 무시
                                }
                            });
                            
                            // "유의사항" 텍스트를 포함한 탭 버튼과 그 연결된 컨텐츠 제거
                            try {
                                const allButtons = clone.querySelectorAll('button, a, [role="tab"]');
                                allButtons.forEach(btn => {
                                    const text = (btn.textContent || '').trim();
                                    if (text === '유의사항' || text.includes('유의사항')) {
                                        // 버튼이 가리키는 타겟도 제거
                                        const target = btn.getAttribute('nw-target');
                                        if (target) {
                                            const targetEl = clone.querySelector(target);
                                            if (targetEl) targetEl.remove();
                                        }
                                        // 버튼 자체도 제거
                                        btn.remove();
                                    }
                                });
                            } catch(e) {
                                // 오류 무시
                            }
                            
                            return clone.innerHTML || '';
                        }
                        return '';
                    }
                """)
                
                # "다음내용참조" alt를 가진 이미지를 GPT-4V로 처리
                try:
                    import requests
                    from io import BytesIO
                    import base64
                    from openai import OpenAI
                    import os
                    
                    soup = BeautifulSoup(detail_html, 'html.parser')
                    openai_client = None
                    
                    # OpenAI 클라이언트 초기화 (최초 1회만)
                    if 'OPENAI_API_KEY' in os.environ:
                        openai_client = OpenAI()
                        logging.info("🤖 GPT-4V OCR 준비 완료")
                    
                    # "다음내용참조" alt를 가진 이미지 찾기
                    images = soup.find_all('img', alt='다음내용참조')
                    if images:
                        logging.info(f"🔍 '다음내용참조' 이미지 {len(images)}개 발견, GPT-4V OCR 처리 시작...")
                        
                        for img in images:
                            try:
                                img_url = img.get('src', '')
                                if not img_url:
                                    continue
                                
                                # 상대 경로를 절대 경로로 변환
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                elif img_url.startswith('/'):
                                    img_url = 'https://shop.kt.com' + img_url
                                
                                logging.info(f"📸 GPT-4V OCR 처리 중: {img_url}")
                                
                                if not openai_client:
                                    logging.warning("⚠️ OpenAI API 키가 설정되지 않음")
                                    continue
                                
                                # 이미지 다운로드 및 base64 인코딩
                                response = requests.get(img_url, timeout=90)
                                image_data = base64.b64encode(response.content).decode('utf-8')
                                
                                # GPT-4V로 OCR 수행
                                api_response = openai_client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=[
                                        {
                                            "role": "system",
                                            "content": """당신은 이미지 OCR 전문가입니다. 

                                                        중요 규칙:
                                                        1. 이미지에 보이는 모든 텍스트를 100% 정확하게 추출해야 합니다
                                                        2. 한국어, 영어, 숫자, 특수문자 모두 포함
                                                        3. 표나 리스트는 구조를 유지하여 마크다운으로 변환
                                                        4. 절대로 "I can't", "I'm sorry", "unable", "텍스트 없음" 같은 거부 응답을 하지 마세요
                                                        5. 텍스트가 없다면 빈 문자열("")을 반환하세요
                                                        6. 추출할 텍스트가 있는데도 거부하는 것은 엄격히 금지됩니다"""
                                        },
                                        {
                                            "role": "user",
                                            "content": [
                                                {
                                                    "type": "text",
                                                    "text": """이 이미지에서 모든 텍스트를 추출하세요.

                                                            요구사항:
                                                            1. 이미지에 보이는 모든 텍스트를 추출 (제품명, 규격, 설명, 가격 등)
                                                            2. 표가 있으면 마크다운 테이블 형식으로 변환
                                                            3. 리스트가 있으면 마크다운 리스트로 변환
                                                            4. 문단은 그대로 유지
                                                            5. 한국어와 영어가 섞여 있어도 모두 추출

                                                            중요: 
                                                            - 텍스트가 실제로 없다면 빈 문자열("")을 반환
                                                            - 텍스트가 있는데 추출을 거부하지 마세요
                                                            - 절대로 "I can't", "I'm sorry" 같은 문구를 사용하지 마세요

                                                            추출된 텍스트를 그대로 반환하세요:"""
                                                },
                                                {
                                                    "type": "image_url",
                                                    "image_url": {
                                                        "url": f"data:image/jpeg;base64,{image_data}"
                                                    }
                                                }
                                            ]
                                        }
                                    ],
                                    max_tokens=4000,
                                    temperature=0.0  # 완전한 일관성을 위해 0.0 설정
                                )
                                
                                ocr_text = api_response.choices[0].message.content.strip()
                                
                                # 잘못된 응답 필터링 - 더 강력하게
                                invalid_responses = [
                                    "i'm sorry", "i can't", "cannot", "unable", "can't help",
                                    "i don't", "i cannot", "not able", "no text", "텍스트 없음",
                                    "빈 이미지", "no content", "empty"
                                ]
                                is_invalid = any(phrase.lower() in ocr_text.lower() for phrase in invalid_responses)
                                
                                # 응답이 너무 짧거나 특정 패턴을 포함하면 무효
                                if len(ocr_text) < 10 and ocr_text.lower() not in ["", "na"]:
                                    is_invalid = True
                                
                                if ocr_text and not is_invalid:
                                    logging.info(f"✅ OCR 결과: {len(ocr_text)}자 추출됨")
                                    # 이미지를 추출된 텍스트로 대체
                                    new_tag = soup.new_tag('div')
                                    new_tag.string = f'\n{ocr_text}\n'
                                    img.replace_with(new_tag)
                                else:
                                    logging.warning(f"⚠️ OCR 결과 없음 또는 잘못된 응답: {img_url}")
                                    # 텍스트를 특별 표시
                                    new_tag = soup.new_tag('div')
                                    new_tag.string = '\n[이미지 텍스트 추출 실패]\n'
                                    img.replace_with(new_tag)
                                    
                            except Exception as ocr_error:
                                logging.warning(f"⚠️ GPT-4V OCR 처리 실패: {img_url} - {str(ocr_error)}")
                                continue
                        
                        # 수정된 HTML로 업데이트
                        detail_html = str(soup)
                        logging.info("✅ GPT-4V OCR 처리 완료")
                    
                except ImportError as ie:
                    logging.warning(f"⚠️ OpenAI 라이브러리가 설치되지 않음: {str(ie)}")
                except Exception as e:
                    logging.warning(f"⚠️ GPT-4V OCR 처리 중 오류: {str(e)}")

                md_all = md(detail_html)
                # 간결화: 상세 루트 전체를 그대로 사용
                content = md_all

                # 입력 menu를 기반으로 메뉴명 구성 (하드코딩 제거)
                base_menu = (menu or '').strip()
                menu_name = f"{base_menu}^{prod['name']}" if base_menu else f"Shop^{prod['name']}"
                menus.append({ 'menu': menu_name, 'url': prod['url'], 'murl': to_mshop_url(prod['url']) })
                datas.append({
                    'url': prod['url'],
                    'title': prod['name'],
                    'markdown': content,
                    'html': detail_html,
                    'special_processed': True,
                    'playwright_processed': True,
                    'murl': to_mshop_url(prod['url'])
                })
            except Exception as e:
                logging.warning(f"상세 추출 실패: {prod.get('name','unknown')}: {str(e)}")
                continue

        await browser.close()

    return {
        'menus': menus,
        'datas': datas,
        'total_processed': len(datas),
        'status': 'completed',
        'message': f"총 {len(datas)}개 모바일 제품 처리 완료"
    }

register_page_handler(
    r'https?://shop\.kt\.com/mobile/products\.do\?category=.*',
    handle_mobile_products_list
)
# =========================
# 10-D. 굿바이 phoneView.do 전용 핸들러 (display:none 모두 표시 후 전체 추출)
# =========================
async def handle_goodbye_phoneview(url: str, fclient, menu=None) -> dict:
    logging.info(f"굿바이 phoneView 핸들러 진입: url={url}, menu={menu}")
    menus, datas = [], []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(600)

        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logging.error(f"❌ phoneView ({url}): HTTP {status_code} 오류")
        else:
            logging.info(f"✅ phoneView ({url}): HTTP {status_code or 'unknown'}")

        # 1) display:none/hidden 요소 강제 표시
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
                // 전역적으로 숨김 제거
                document.querySelectorAll('[hidden], .hidden, .is-hidden').forEach(n => {
                    n.removeAttribute('hidden');
                    show(n);
                });
                document.querySelectorAll('*').forEach(n => {
                    const st = (n.getAttribute('style')||'').toLowerCase();
                    if (st.includes('display:none')) show(n);
                    if (st.includes('visibility:hidden')) show(n);
                });
                // 주요 탭/패널 후보들
                ['.nwViewProdDetail', '#cfmClContents', '.prodDetailWrap', '.prodDetail', '#view-1', '#view-4']
                  .forEach(sel => show(document.querySelector(sel)));
            }
        """)
        await page.wait_for_timeout(200)

        # 2) 컨테이너 우선 순위로 전체 HTML 획득
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

        from markdownify import markdownify as md
        md_all = md(detail_html)

        # 메뉴/타이틀: 입력 menu를 그대로 사용하고, 타이틀은 h1/문서제목에서 추출
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
            menus.append({ 'menu': base_menu_in, 'url': url, 'murl': mobile_url })
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
        'message': f"phoneView 처리 완료 ({len(datas)}개)"
    }

register_page_handler(
    r'https?://shop\.kt\.com/goodbye/phoneView\.do.*',
    handle_goodbye_phoneview
)


# =========================
# 10-E. 기획전 목록/상세 핸들러 (olhsStore.do → olhsPlan.do)
# - iframe 내부 목록 + 페이지네이션 순회
# - 제목(plan_tit) → 메뉴명 suffix, 전시기간 → startdate
# =========================
async def handle_store_plans_list(url: str, fclient, menu=None) -> dict:
    import re
    from markdownify import markdownify as md
    logging.info(f"기획전 목록 핸들러 진입: url={url}, menu={menu}")
    menus, datas = [], []

    def _norm_date(dtxt: str) -> str:
        # 예: 2025.9.10 ~ → 2025-09-10
        try:
            m = re.search(r'(20\d{2})[\.-]\s*(\d{1,2})[\.-]\s*(\d{1,2})', dtxt)
            if not m:
                return ''
            y, mo, dy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f"{y:04d}-{mo:02d}-{dy:02d}"
        except Exception:
            return ''

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=90000)
        await page.wait_for_timeout(800)

        status_code = response.status if response else None
        if status_code and status_code >= 400:
            logging.error(f"❌ 기획전 목록 ({url}): HTTP {status_code} 오류")
        else:
            logging.info(f"✅ 기획전 목록 ({url}): HTTP {status_code or 'unknown'}")

        # iframe 탐색: 첫 가시 프레임 또는 .plan_tit를 포함하는 프레임
        await page.wait_for_selector('iframe', timeout=10000)
        target_frame = None
        for fr in page.frames:
            if fr == page.main_frame:
                continue
            try:
                if await fr.query_selector('.plan_tit'):
                    target_frame = fr
                    break
            except Exception:
                continue
        if not target_frame:
            # 가시 프레임 중 첫 번째
            for fr in page.frames:
                if fr != page.main_frame:
                    target_frame = fr
                    break

        if not target_frame:
            await browser.close()
            return { 'menus': [], 'datas': [], 'total_processed': 0, 'status': 'completed', 'message': '프레임 미탐지' }

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

        logging.info(f"기획전 목록 총 페이지: {total_pages}")

        collected = []

        async def extract_page_items() -> list:
            try:
                return await target_frame.evaluate(r"""
                    () => {
                        const items = [];
                        document.querySelectorAll('.plan_tit').forEach(t => {
                            const title = (t.innerText||'').replace(/\s+/g,' ').trim();
                            let href = '';
                            // 타이틀 주변 a[href] - 조부모까지 확인
                            let a = t.closest('a');
                            if (!a || !a.getAttribute('href')){
                                // 부모에서 찾기
                                const parent = t.parentElement;
                                if (parent) {
                                    a = parent.querySelector('a[href]');
                                }
                                // 조부모에서 찾기
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
                            // 전시기간 텍스트 추정
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
                        # 대체 클릭: evaluate로 클릭
                        try:
                            await target_frame.evaluate("""
                                (n) => {
                                    const el = document.querySelector(`a[pageno="${n}"]`);
                                    if (el) el.click();
                                }
                            """, pno)
                            await page.wait_for_timeout(600)
                        except Exception:
                            pass
                rows = await extract_page_items()
                logging.info(f"페이지 {pno}: {len(rows)}건 수집")
                for r in rows:
                    if any(x.get('href') == r.get('href') and x.get('title') == r.get('title') for x in collected):
                        continue
                    collected.append(r)
            except Exception as e:
                logging.warning(f"페이지 {pno} 처리 실패: {str(e)}")

        logging.info(f"총 수집 항목: {len(collected)}")

        # 상세 페이지 순회
        for idx, row in enumerate(collected, 1):
            title = (row.get('title') or '').strip()
            href = row.get('href') or ''
            period = row.get('period') or ''
            startdate = _norm_date(period)
            # 상세 URL 절대경로 보정
            from urllib.parse import urljoin
            detail_url = ''
            if href:
                if not href.lower().startswith('javascript'):
                    detail_url = urljoin('https://shop.kt.com', href)
            logging.info(f"[{idx}/{len(collected)}] 상세 추출: {title}")
            logging.info(f"[DEBUG] 상세 URL: {detail_url}")
            detail_html = ''
            try:
                if detail_url:
                    # Crawl4AI 기본 스크래핑 직접 호출 (route_url 우회)
                    try:
                        if hasattr(fclient, 'crawler') and fclient.crawler:
                            from crawl4ai.async_configs import CrawlerRunConfig, CacheMode
                            
                            # 기본 스크래핑 설정
                            run_config = CrawlerRunConfig(
                                verbose=False,
                                word_count_threshold=10,
                                exclude_external_links=True,
                                remove_overlay_elements=False,
                                process_iframes=True,
                                ignore_body_visibility=True,
                                js_only=False,
                                cache_mode=CacheMode.BYPASS,
                                excluded_tags=['form', 'header', 'footer', 'nav'],
                                excluded_selector="#cfmClHeader, #cfmClFooter, #cfmClSkip, .location, .sns-area",
                                wait_until="networkidle",
                                delay_before_return_html=6,
                                simulate_user=True,
                                override_navigator=True,
                                page_timeout=120000,
                            )
                            
                            crawl_result = await fclient.crawler.arun(url=detail_url, config=run_config)
                            if crawl_result and crawl_result.success:
                                html_content = crawl_result.html or ''
                                md_content = crawl_result.markdown or ''
                                logging.info(f"[DEBUG] 크롤링 성공: HTML={len(html_content)}자, MD={len(md_content)}자")
                                c4_result = {
                                    'html': html_content,
                                    'markdown': md_content,
                                    'status_code': getattr(crawl_result, 'status_code', None)
                                }
                                # html/markdown 우선 사용
                                detail_html = html_content.strip()
                                pre_md_text = md_content.strip()
                                # 아래 md_text 생성 전에 우선값으로 전달하기 위해 locals에 저장
                                if pre_md_text:
                                    md_text = pre_md_text
                            else:
                                logging.warning(f"Crawl4AI 크롤링 실패: {detail_url} - success={getattr(crawl_result, 'success', None)}")
                        else:
                            logging.warning("fclient.crawler 사용 불가")
                    except Exception as ce:
                        logging.warning(f"Crawl4AI 직접 호출 오류(무시): {str(ce)}")
            except Exception as e:
                logging.warning(f"상세 이동 실패(무시): {str(e)}")

            # 위에서 c4 결과로 md_text가 이미 채워졌다면 유지, 아니면 변환
            try:
                md_text
            except NameError:
                md_text = ''
            if not md_text:
                md_text = md(detail_html, heading_style="ATX") if detail_html else ''

            base_menu = (menu or '').strip()
            menu_name = f"{base_menu}^{title}" if base_menu else f"Shop^핫딜/기획전^기획전^통신상품^{title}"
            menus.append({ 'menu': menu_name, 'url': detail_url or url, 'murl': to_mshop_url(detail_url or url) })
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

# =========================
# 지니 TV 채널 편성표 핸들러
# =========================
async def handle_whygenietv_channel_schedule(url: str, fclient, menu: Optional[str] = None) -> dict:
    """
    지니 TV(WhyGenieTV) 채널 편성표 추출 핸들러

    요구사항:
    - ul.channel_select.tv_live 이하 탭 정보를 이용해 각 상품 플랜을 순회
    - 각 채널 항목의 번호, 명칭, alt(비고) 정보를 수집
    - 마크다운 표 형태(| 채널 번호 | 채널명 | 비고 |)로 저장
    - 메뉴 경로는 {menu 또는 기본값}^{플랜명} 형태로 구성
    """
    import requests

    logging.info(f"🎬 지니 TV 채널 편성표 처리 시작: url={url}")

    base_menu = (menu or "상품^WhyGenieTV^채널 편성표").strip()
    menus: List[Dict[str, Any]] = []
    datas: List[Dict[str, Any]] = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": url
    })

    try:
        response = await asyncio.to_thread(session.get, url, timeout=30)
    except Exception as e:
        session.close()
        logging.error(f"❌ 지니 TV 채널 편성표 페이지 요청 실패: {e}")
        return {
            "menus": [],
            "datas": [],
            "total_processed": 0,
            "status": "failed",
            "message": f"지니 TV 채널 편성표 페이지 요청 실패: {e}"
        }

    status_code = getattr(response, "status_code", None)
    if not response or not getattr(response, "text", ""):
        session.close()
        logging.error("❌ 지니 TV 채널 편성표 응답이 비어 있습니다.")
        return {
            "menus": [],
            "datas": [],
            "total_processed": 0,
            "status": "failed",
            "status_code": status_code,
            "message": "지니 TV 채널 편성표 응답이 비어 있습니다."
        }

    response.encoding = "euc-kr"
    soup = BeautifulSoup(response.text, "html.parser")

    channel_guide_el = soup.select_one("div.channel_guide")
    noti_desc_el = soup.select_one("div.noti_desc")

    def normalize_multiline(text: str) -> str:
        if not text:
            return ""
        # 연속 공백을 줄이고, 줄바꿈 사이 불필요한 공백 제거
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        return cleaned.strip()

    channel_guide_text = normalize_multiline(channel_guide_el.get_text("\n", strip=True)) if channel_guide_el else ""
    noti_desc_text = normalize_multiline(noti_desc_el.get_text("\n", strip=True)) if noti_desc_el else ""
    channel_guide_html = str(channel_guide_el) if channel_guide_el else ""
    noti_desc_html = str(noti_desc_el) if noti_desc_el else ""

    super_tab_pattern = re.compile(r"fnSearchChannel\((?P<ch_type>[^,]+),'(?P<prod>[^']*)',\s*(?P<mid>[^)]+)\)")
    plan_pattern = re.compile(r"fnSearchChannelNoSubmit\('(?P<ch_type>[^']*)','(?P<product_cd>[^']*)',\s*(?P<mid>[^)]+)\)")

    super_tabs: List[Dict[str, Any]] = []
    for anchor in soup.select(".channel_content .sub-tabs-1st .sub-trigger"):
        tab_name = (anchor.get_text(" ", strip=True) or "").replace("\xa0", " ").strip()
        href = (anchor.get("href") or "").strip()
        if not tab_name or not href:
            continue
        match = super_tab_pattern.search(anchor.get("onclick") or "")
        if not match:
            continue
        ch_type = match.group("ch_type").strip() or "3"
        target = soup.select_one(href)
        if not target:
            continue
        plan_ul = target.select_one("ul.channel_select")
        if not plan_ul:
            continue
        super_tabs.append({
            "name": tab_name,
            "ch_type": ch_type,
            "plan_ul": plan_ul
        })

    if not super_tabs:
        # fallback: 기존 방식 (지니 TV 기본 탭만)
        plan_container = soup.select_one("div#trigger2-1-1 ul.channel_select.tv_live") or soup.select_one("ul.channel_select.tv_live")
        if plan_container:
            super_tabs.append({
                "name": "지니 TV",
                "ch_type": "3",
                "plan_ul": plan_container
            })

    if not super_tabs:
        session.close()
        logging.error("❌ 지니 TV 탭 정보를 찾을 수 없습니다.")
        return {
            "menus": [],
            "datas": [],
            "total_processed": 0,
            "status": "failed",
            "status_code": status_code,
            "message": "지니 TV 탭 정보를 찾을 수 없습니다."
        }

    channel_cache: Dict[Tuple[str, str, str], Tuple[int, str]] = {}

    def parse_channel_html(html_text: str) -> List[Dict[str, str]]:
        if not html_text:
            return []
        inner_soup = BeautifulSoup(html_text, "html.parser")
        channels: List[Dict[str, str]] = []
        for anchor in inner_soup.select("ul.channel li a"):
            span = anchor.select_one("span.ch")
            if not span:
                continue

            text_parts: List[str] = []
            for node in span.contents:
                if isinstance(node, NavigableString):
                    value = str(node).strip()
                    if value:
                        text_parts.append(value)

            channel_text = " ".join(text_parts).replace("\xa0", " ")
            channel_text = re.sub(r"\s+", " ", channel_text).strip()
            if not channel_text:
                continue

            channel_text = html.unescape(unquote(channel_text))

            number = channel_text
            name = ""
            number_match = re.match(r"^(\S+)\s+(.*)$", channel_text)
            if number_match:
                number = number_match.group(1).strip()
                name = number_match.group(2).strip()

            alt_text = html.unescape(unquote((anchor.get("alt") or "").strip()))

            channels.append({
                "channel_number": number,
                "channel_name": name,
                "note": alt_text
            })
        return channels

    async def fetch_channels(ch_type: str, product_cd: str, parent_menu_id: str) -> Tuple[int, List[Dict[str, str]]]:
        cache_key = (ch_type, product_cd or "", parent_menu_id or "0")
        if cache_key in channel_cache:
            cached_status, cached_html = channel_cache[cache_key]
            return cached_status, parse_channel_html(cached_html)

        data = {
            "ch_type": ch_type,
            "parent_menu_id": parent_menu_id or "0",
            "product_cd": product_cd or "",
            "option_cd_list": ""
        }

        try:
            resp = await asyncio.to_thread(session.post, "https://tv.kt.com/tv/channel/pChList.asp", data=data, timeout=30)
        except Exception as e:
            logging.error(f"❌ 채널 목록 요청 실패 (product_cd={product_cd}): {e}")
            return None, []

        resp.encoding = "euc-kr"
        channel_cache[cache_key] = (resp.status_code, resp.text)
        return resp.status_code, parse_channel_html(resp.text)

    def escape_md(value: str) -> str:
        if not value:
            return ""
        return value.replace("|", "\\|")

    total_plans_processed = 0

    for super_tab in super_tabs:
        super_name = super_tab["name"]
        super_ch_type = super_tab["ch_type"]
        plan_ul = super_tab["plan_ul"]

        seen_codes: Set[str] = set()
        plan_entries: List[Dict[str, str]] = []

        for anchor in plan_ul.select("li a"):
            onclick = anchor.get("onclick") or ""
            match = plan_pattern.search(onclick)
            if not match:
                continue

            product_cd = match.group("product_cd").strip()
            parent_menu_id = match.group("mid").strip().strip(";") or "0"

            span = anchor.select_one("span")
            raw_title = (span.get_text(" ", strip=True) if span else "").replace("\xa0", " ").strip()
            clean_title = re.sub(r"\([^)]*\)", "", raw_title).strip()

            if not raw_title or not product_cd:
                continue
            if not clean_title or clean_title in ("전체",):
                continue
            if "선택형" in clean_title:
                continue
            if product_cd in seen_codes:
                continue

            seen_codes.add(product_cd)
            plan_entries.append({
                "title": clean_title,
                "raw_title": raw_title,
                "ch_type": super_ch_type,
                "product_cd": product_cd,
                "parent_menu_id": parent_menu_id
            })

        if not plan_entries:
            logging.warning(f"⚠️ '{super_name}' 플랜 정보를 찾지 못했습니다.")
            continue

        for plan in plan_entries:
            plan_title = plan["title"]
            plan_code = plan["product_cd"]
            plan_ch_type = plan["ch_type"]
            parent_menu_id = plan["parent_menu_id"]

            channel_status, channels = await fetch_channels(plan_ch_type, plan_code, parent_menu_id)
            channel_count = len(channels)

            markdown_lines = [
                "| 채널 번호 | 채널명 | 비고 |",
                "| --- | --- | --- |"
            ]
            for channel in channels:
                markdown_lines.append(
                    f"| {escape_md(channel['channel_number'])} | {escape_md(channel['channel_name'])} | {escape_md(channel['note'])} |"
                )
            markdown_table = "\n".join(markdown_lines)

            markdown_sections: List[str] = []
            markdown_sections.append(f"# {super_name} - {plan_title}")
            markdown_sections.append(markdown_table)
            if channel_guide_text:
                markdown_sections.append(channel_guide_text)
            if noti_desc_text:
                markdown_sections.append(noti_desc_text)
            full_markdown = "\n\n".join(markdown_sections)

            menu_path = f"{base_menu}^{super_name}^{plan_title}" if base_menu else f"{super_name}^{plan_title}"
            menus.append({
                "menu": menu_path,
                "url": url
            })
            datas.append({
                "menu": menu_path,
                "title": plan_title,
                "parent_tab": super_name,
                "url": url,
                "plan_code": plan_code,
                "ch_type": plan_ch_type,
                "parent_menu_id": parent_menu_id,
                "channel_count": channel_count,
                "channels": channels,
                "channel_guide_text": channel_guide_text,
                "channel_guide_html": channel_guide_html,
                "noti_desc_text": noti_desc_text,
                "noti_desc_html": noti_desc_html,
                "markdown": full_markdown,
                "status_code": channel_status
            })

            total_plans_processed += 1
            logging.info(f"✅ 지니 TV 채널 플랜 처리 완료: parent='{super_name}', plan='{plan_title}', channel_count={channel_count}")

    session.close()

    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_plans_processed,
        "status": "completed",
        "status_code": status_code,
        "message": f"지니 TV 채널 편성표 플랜 {total_plans_processed}건 처리 완료"
    }

register_page_handler(
    r'https?://tv\.kt\.com/tv/channel/pChInfo\.asp.*',
    handle_whygenietv_channel_schedule
)

# =========================
# 당첨자발표 처리 핸들러
# =========================
async def handle_event_winner_announcements(url: str, fclient, menu=None) -> dict:
    """
    KT Shop 당첨자발표 페이지 처리
    
    Args:
        url: 당첨자발표 목록 페이지 URL
        fclient: Firecrawl 클라이언트
        menu: 메뉴 정보
    
    Returns:
        dict: 추출된 데이터
    """
    try:
        logging.info(f"🎯 당첨자발표 페이지 처리 시작: {url}")
        
        # Playwright를 사용하여 페이지 접근
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # 페이지 로드
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)  # 추가 로딩 대기
            
            # iframe으로 이동
            iframe = await page.query_selector('iframe[src*="planDispEvent.do"]')
            if not iframe:
                raise Exception("당첨자발표 iframe을 찾을 수 없습니다.")
            
            frame = await iframe.content_frame()
            if not frame:
                raise Exception("iframe 내부로 접근할 수 없습니다.")
            
            # 1단계: 페이지네이션을 통해 모든 게시물 링크 수집
            all_posts = []
            current_page = 1
            max_pages = 20  # 안전장치
            no_new_posts_count = 0  # 연속으로 새 게시물이 없는 횟수
            
            while current_page <= max_pages:
                logging.info(f"📄 페이지 {current_page} 처리 중...")
                
                # 현재 페이지의 게시물들 수집 (iframe 내부에서)
                page_posts = await frame.evaluate("""
                    () => {
                        const allTable = document.querySelector('#tabCont01 table.board_list');
                        if (!allTable) return [];
                        
                        const rows = allTable.querySelectorAll('tbody tr');
                        return Array.from(rows).map((row, index) => {
                            const cells = row.querySelectorAll('td');
                            const link = row.querySelector('a');
                            
                            if (!link || !link.onclick) return null;
                            
                            // onclick에서 ID 추출
                            const onclickStr = link.onclick.toString();
                            const eventListViewMatch = onclickStr.match(/eventListView\\((\\d+),'(\\d+)','(\\d+)'\\)/);
                            
                            if (!eventListViewMatch) return null;
                            
                            // 이벤트 기간을 startdate, enddate로 분리
                            const periodText = cells[2]?.textContent?.trim() || '';
                            const periodMatch = periodText.match(/(\\d{4})\\.(\\d{2})\\.(\\d{2})\\s*~\\s*(\\d{4})\\.(\\d{2})\\.(\\d{2})/);
                            const startdate = periodMatch ? `${periodMatch[1]}-${periodMatch[2]}-${periodMatch[3]}` : '';
                            const enddate = periodMatch ? `${periodMatch[4]}-${periodMatch[5]}-${periodMatch[6]}` : '';
                            
                            return {
                                index: index + 1,
                                number: cells[0]?.textContent?.trim() || '',
                                eventName: cells[1]?.textContent?.trim() || '',
                                period: periodText,
                                startdate: startdate,
                                enddate: enddate,
                                announcementDate: cells[3]?.textContent?.trim() || '',
                                eventId1: eventListViewMatch[1],
                                eventId2: eventListViewMatch[2],
                                eventId3: eventListViewMatch[3],
                                uniqueId: `${eventListViewMatch[1]}_${eventListViewMatch[3]}`,
                                filePath: `Shop^핫딜/기획전^기획전^당첨자발표^${cells[1]?.textContent?.trim() || ''}`
                            };
                        }).filter(post => post !== null);
                    }
                """)
                
                if not page_posts:
                    logging.info(f"📄 페이지 {current_page}에서 게시물을 찾을 수 없음. 수집 완료.")
                    break
                
                # 중복 게시물 체크 (같은 uniqueId가 이미 있는지 확인)
                new_posts = []
                existing_ids = {post['uniqueId'] for post in all_posts}
                
                for post in page_posts:
                    if post['uniqueId'] not in existing_ids:
                        new_posts.append(post)
                
                if not new_posts:
                    no_new_posts_count += 1
                    logging.info(f"📄 페이지 {current_page}: 새로운 게시물 없음 ({no_new_posts_count}/3)")
                    
                    if no_new_posts_count >= 3:  # 연속 3번 새 게시물이 없으면 종료
                        logging.info("📄 연속으로 새로운 게시물이 없어 수집 완료.")
                        break
                else:
                    no_new_posts_count = 0  # 새 게시물이 있으면 카운터 리셋
                
                all_posts.extend(new_posts)
                logging.info(f"📄 페이지 {current_page}: {len(new_posts)}개 새 게시물 수집 (총 {len(all_posts)}개)")
                
                # 다음 페이지로 이동 시도 (allListClick 함수 사용)
                try:
                    next_page = current_page + 1
                    await frame.evaluate(f"allListClick({next_page})")
                    await page.wait_for_timeout(2000)
                    current_page = next_page
                except Exception as e:
                    logging.info(f"📄 페이지 이동 실패: {e}. 수집 완료.")
                    break
            
            await browser.close()
            
            logging.info(f"✅ 총 {len(all_posts)}개 게시물 수집 완료")
            
            # 2단계: 병렬로 상세 정보 추출
            from markdownify import markdownify as md
            
            menus = []
            datas = []
            
            # 메인 페이지도 저장
            base_menu = (menu or '').strip()
            menus.append({'menu': base_menu, 'url': url, 'murl': to_mshop_url(url)})
            datas.append({
                'url': url,
                'murl': to_mshop_url(url),
                'title': '당첨자발표 목록',
                'markdown': f"# 당첨자발표 목록\n\n총 {len(all_posts)}개 이벤트 당첨자발표",
                'html': f"<h1>당첨자발표 목록</h1><p>총 {len(all_posts)}개 이벤트 당첨자발표</p>",
                'special_processed': True,
                'playwright_processed': True
            })
            
            # 병렬 처리를 위한 세마포어 (동시 요청 수 제한)
            semaphore = asyncio.Semaphore(5)  # 최대 5개 동시 요청
            
            async def extract_post_detail(post):
                async with semaphore:
                    try:
                        logging.info(f"🔍 상세 정보 추출 중: {post['eventName']}")
                        
                        # 새로운 브라우저 인스턴스로 상세 페이지 접근
                        async with async_playwright() as p:
                            browser = await p.chromium.launch(headless=True)
                            context = await browser.new_context()
                            detail_page = await context.new_page()
                            
                            # 목록 페이지로 이동
                            await detail_page.goto("https://shop.kt.com/plan/planDispEvent.do", wait_until='networkidle', timeout=60000)
                            
                            # eventListView 함수 실행하여 상세 페이지로 이동
                            await detail_page.evaluate(f"""
                                eventListView({post['eventId1']}, '{post['eventId2']}', '{post['eventId3']}');
                            """)
                            
                            await detail_page.wait_for_timeout(3000)  # 페이지 로딩 대기
                            
                            # 상세 HTML 추출
                            detail_html = await detail_page.evaluate("""
                                () => {
                                    // 상세 영역 추출
                                    const boardView = document.querySelector('table.board_view');
                                    if (boardView) {
                                        return boardView.outerHTML;
                                    }
                                    
                                    // board_view가 없으면 본문 전체
                                    const content = document.querySelector('.content, #content, .board_content');
                                    if (content) {
                                        return content.outerHTML;
                                    }
                                    
                                    return document.body ? document.body.innerHTML : '';
                                }
                            """)
                            
                            await browser.close()
                            
                            # 마크다운 변환
                            detail_markdown = md(detail_html) if detail_html else ''
                            
                            # 상세 URL 구성
                            detail_url = f"https://shop.kt.com/plan/planDispEvent.do?eventId={post['eventId1']}&eventId2={post['eventId2']}&eventId3={post['eventId3']}"
                            
                            return {
                                'success': True,
                                'post': post,
                                'html': detail_html,
                                'markdown': detail_markdown,
                                'url': detail_url
                            }
                            
                    except Exception as e:
                        logging.error(f"❌ 상세 정보 추출 실패 ({post['eventName']}): {e}")
                        return {
                            'success': False,
                            'post': post,
                            'error': str(e)
                        }
            
            # 병렬로 상세 정보 추출
            detailed_results = await asyncio.gather(*[extract_post_detail(post) for post in all_posts])
            
            # 3단계: 결과를 menus와 datas에 추가
            success_count = 0
            for result in detailed_results:
                post = result.get('post', {})
                event_name = post.get('eventName', '알 수 없음')
                
                # 메뉴 구성
                menu_name = f"{base_menu}^{event_name}" if base_menu else f"당첨자발표^{event_name}"
                detail_url = result.get('url', url)
                
                menus.append({
                    'menu': menu_name,
                    'url': detail_url,
                    'murl': to_mshop_url(detail_url)
                })
                
                if result.get('success'):
                    # 성공한 경우
                    markdown_content = f"# {event_name}\n\n"
                    markdown_content += f"**이벤트 기간**: {post.get('period', '')}\n\n"
                    markdown_content += f"**당첨자 발표일**: {post.get('announcementDate', '')}\n\n"
                    markdown_content += "---\n\n"
                    markdown_content += result.get('markdown', '')
                    
                    datas.append({
                        'url': detail_url,
                        'murl': to_mshop_url(detail_url),
                        'title': event_name,
                        'markdown': markdown_content,
                        'html': result.get('html', ''),
                        'startdate': post.get('startdate', ''),
                        'enddate': post.get('enddate', ''),
                        'special_processed': True,
                        'playwright_processed': True
                    })
                    success_count += 1
                else:
                    # 실패한 경우
                    datas.append({
                        'url': detail_url,
                        'murl': to_mshop_url(detail_url),
                        'title': event_name,
                        'markdown': f"# {event_name}\n\n상세 정보 추출 실패: {result.get('error', '알 수 없는 오류')}",
                        'html': f"<h1>{event_name}</h1><p>상세 정보 추출 실패</p>",
                        'startdate': post.get('startdate', ''),
                        'enddate': post.get('enddate', ''),
                        'special_processed': True,
                        'playwright_processed': True,
                        'error': result.get('error', '')
                    })
            
            logging.info(f"✅ 당첨자발표 처리 완료: {success_count}/{len(all_posts)}개 상세 정보 추출 성공")
            
            return {
                'menus': menus,
                'datas': datas,
                'total_processed': len(datas),
                'status': 'completed'
            }
            
    except Exception as e:
        logging.error(f"❌ 당첨자발표 처리 중 오류 발생: {e}")
        base_menu = (menu or '').strip()
        return {
            'menus': [{'menu': base_menu, 'url': url, 'murl': to_mshop_url(url)}],
            'datas': [{
                'url': url,
                'murl': to_mshop_url(url),
                'title': '당첨자발표',
                'markdown': f"# 당첨자발표 처리 실패\n\n오류: {str(e)}",
                'html': f"<h1>당첨자발표 처리 실패</h1><p>오류: {str(e)}</p>",
                'error': str(e),
                'special_processed': True,
                'playwright_processed': True
            }],
            'total_processed': 0,
            'status': 'failed',
            'error': str(e)
        }

# 당첨자발표 핸들러 등록
register_page_handler(
    r'https?://shop\.kt\.com/display/olhsStore\.do\?dispNo=STOR05&subDispNo=STOR0506.*',
    handle_event_winner_announcements
)

# =========================
# Webzine 리스트 핸들러 (webzineList.do)
# =========================
async def handle_webzine_list(url: str, fclient, menu=None) -> dict:
    """
    Webzine 리스트 페이지 처리 핸들러
    - 리스트에서 ul.webzine_list 아래의 a href 수집
    - 각 상세 페이지에서 div.webzine_content 추출
    """
    from markdownify import markdownify as md
    logging.info(f"Webzine 리스트 핸들러 진입: url={url}, menu={menu}")
    menus, datas = [], []
    base_menu = (menu or '').strip()
    base_title = base_menu.split('^')[-1].strip() if base_menu else 'Webzine 리스트'
    base_title = sanitize_filename(base_title)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(2500)

        try:
            await page.wait_for_selector('ul.webzine_list', timeout=20000)
        except Exception:
            logging.warning(
                "⚠️ Webzine 리스트: ul.webzine_list 요소를 찾지 못했습니다."
            )

        status_code = response.status if response else None
        if status_code:
            if status_code >= 400:
                logging.error(f"❌ Webzine 리스트 ({url}): HTTP {status_code} 오류")
            elif status_code >= 300:
                logging.warning(f"⚠️ Webzine 리스트 ({url}): HTTP {status_code} 리다이렉트")
            else:
                logging.info(f"✅ Webzine 리스트 ({url}): HTTP {status_code} 성공")
        else:
            logging.debug(f"🔍 Webzine 리스트 ({url}): 상태 코드 정보 없음")

        # 메인 페이지 콘텐츠 추출 (메뉴 기본 페이지 저장)
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
            logging.warning("⚠️ Webzine 리스트: 메인 영역 HTML 추출 실패, body 전체를 사용합니다.")
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

        # 1) 리스트에서 a href 수집
        webzine_items = await page.evaluate("""
            () => {
                const results = [];
                const webzineList = document.querySelector('ul.webzine_list');
                if (!webzineList) {
                    return results;
                }
                
                // ul.webzine_list 아래의 모든 a 태그 수집
                const links = webzineList.querySelectorAll('a[href]');
                links.forEach(a => {
                    const href = a.getAttribute('href') || '';
                    const fullText = (a.textContent || '').trim();
                    
                    if (href) {
                        try {
                            // 상대 경로를 절대 경로로 변환
                            const absUrl = new URL(href, location.href).href;
                            
                            // 텍스트에서 날짜와 카테고리 제거, 제목만 추출
                            let cleanTitle = fullText;
                            
                            // 날짜 패턴 제거 (YYYY. MM 또는 YYYY.MM)
                            cleanTitle = cleanTitle.replace(/^\\d{4}\\.\\s*\\d{1,2}\\s*/, '');
                            
                            // 줄바꿈으로 분리하여 마지막 줄(카테고리) 제거
                            const lines = cleanTitle.split(/\\n/).map(l => l.trim()).filter(l => l.length > 0);
                            if (lines.length > 1) {
                                // 첫 번째 줄이 제목, 마지막 줄이 카테고리로 추정
                                cleanTitle = lines[0];
                            } else if (lines.length === 1) {
                                cleanTitle = lines[0];
                            }
                            
                            // 연속된 공백 제거
                            cleanTitle = cleanTitle.replace(/\\s+/g, ' ').trim();
                            
                            // 원본 텍스트에서 날짜 추출 (YYYY. MM 형식)
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
                            // URL 변환 실패 시 원본 href 사용
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

        logging.info(f"Webzine 리스트 수집: {len(webzine_items)}개 항목")

        # 중복 제거 (URL 기준)
        seen_urls = set()
        normalized = []
        for item in webzine_items:
            item_url = item.get('url', '').strip()
            if item_url and item_url not in seen_urls:
                seen_urls.add(item_url)
                
                # URL 파라미터에서 year, month 추출 시도
                try:
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(item_url)
                    params = parse_qs(parsed.query)
                    
                    # URL 파라미터가 있으면 우선 사용
                    url_year = params.get('year', [None])[0]
                    url_month = params.get('month', [None])[0]
                    
                    if url_year:
                        # year=24 -> 2024로 변환
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

        logging.info(f"정규화된 Webzine 항목: {len(normalized)}개")

        # 2) 각 상세 페이지에서 div.webzine_content 추출
        for idx, item in enumerate(normalized, 1):
            try:
                logging.info(f"[{idx}/{len(normalized)}] 상세 추출: {item['title']}")
                
                # 상세 페이지로 이동
                try:
                    await page.goto(item['url'], wait_until='domcontentloaded', timeout=60000)
                    await page.wait_for_timeout(1200)
                except Exception as _e:
                    logging.warning(f"상세 페이지 이동 실패(무시하고 계속): {item['url']} -> {_e}")
                    continue

                # div.webzine_content 추출
                detail_html = await page.evaluate("""
                    () => {
                        const contentEl = document.querySelector('div.webzine_content');
                        if (contentEl && contentEl.innerHTML && contentEl.innerHTML.trim().length > 0) {
                            return contentEl.innerHTML;
                        }
                        
                        // 폴백: 전체 컨텐츠 영역 추출
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
                    logging.warning(f"⚠️ {item['title']}: 컨텐츠 추출 실패 또는 비어있음")
                    continue

                md_content = md(detail_html)
                
                # 날짜 파싱 (startdate 설정)
                startdate = "1900-01-01"
                if item.get('year') and item.get('month'):
                    year = item['year']
                    month = item['month'].zfill(2)
                    startdate = f"{year}-{month}-01"
                
                # 메뉴명 구성 (제목만 사용)
                menu_name = f"{base_menu}^{item['title']}" if base_menu else f"Shop^{item['title']}"
                menus.append({ 'menu': menu_name, 'url': item['url'], 'murl': to_mshop_url(item['url']) })
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
                logging.warning(f"상세 추출 실패: {item.get('title', 'unknown')}: {str(e)}")
                continue

        await browser.close()

    return {
        'menus': menus,
        'datas': datas,
        'total_processed': len(datas),
        'status': 'completed',
        'message': f"총 {len(datas)}개 Webzine 항목 처리 완료"
    }

register_page_handler(
    r'https?://shop\.kt\.com/unify/webzineList\.do.*',
    handle_webzine_list
)