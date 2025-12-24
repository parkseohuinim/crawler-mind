"""
Page Handlers 유틸리티 함수들

URL 변환, 파일명 정제, 날짜 포맷팅 등 공용 유틸리티 함수를 제공합니다.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)

# 글로벌 타임스탬프 변수
CURRENT_TIMESTAMP: Optional[str] = None


def set_current_timestamp(timestamp_str: Optional[str]) -> None:
    """타임스탬프 설정"""
    global CURRENT_TIMESTAMP
    if timestamp_str is not None:
        CURRENT_TIMESTAMP = timestamp_str
    else:
        CURRENT_TIMESTAMP = None


def get_current_timestamp() -> str:
    """현재 타임스탬프 반환 (없으면 새로 생성)"""
    global CURRENT_TIMESTAMP
    if CURRENT_TIMESTAMP is None:
        CURRENT_TIMESTAMP = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        logger.info(f"🕐 새로운 타임스탬프 생성: {CURRENT_TIMESTAMP}")
    return CURRENT_TIMESTAMP


def sanitize_filename(filename: str, max_length: int = 100) -> str:
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


def format_date_show(date_str: str) -> str:
    """공연예매 날짜 형식 변환"""
    if not date_str:
        return ""
    
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


def format_content(content: str) -> str:
    """콘텐츠 포맷팅"""
    if not content:
        return ""
    
    # 불필요한 공백 제거
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    content = re.sub(r'^\s+|\s+$', '', content, flags=re.MULTILINE)
    
    return content


def create_markdown(title: str, date: str, content: str) -> str:
    """마크다운 문서 생성"""
    return f"""# {title}

**날짜:** {date}

---

{content}
"""


async def smart_goto(
    page,
    url: str,
    wait_for_selector: Optional[str] = None,
    timeout: int = 60000,
    selector_timeout: int = 100000,
    extra_wait: int = 6000
):
    """
    효율적인 페이지 로드 함수
    
    - domcontentloaded로 빠르게 로드
    - 필요한 요소만 추가 대기 (없으면 skip)
    - 불필요한 networkidle 대기 없음
    
    Args:
        page: Playwright page 객체
        url: 접속할 URL
        wait_for_selector: 대기할 CSS selector (optional)
        timeout: goto 타임아웃 (기본 30초)
        selector_timeout: selector 대기 타임아웃 (기본 10초)
        extra_wait: 추가 렌더링 대기 (기본 1.5초)
    
    Returns:
        response: Playwright Response 객체
    """
    # 1단계: 빠른 DOM 로드
    response = await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
    
    # 2단계: 필요한 요소 대기 (있으면 즉시 진행, 없으면 skip)
    if wait_for_selector:
        try:
            await page.wait_for_selector(wait_for_selector, timeout=selector_timeout)
        except Exception:
            logger.debug(f"🔍 Selector not found, continuing: {wait_for_selector}")
    
    # 3단계: JS 렌더링 버퍼
    if extra_wait > 0:
        await page.wait_for_timeout(extra_wait)
    
    return response


async def smart_goto_with_status(
    page,
    url: str,
    wait_for_selector: Optional[str] = None,
    timeout: int = 30000,
    selector_timeout: int = 10000,
    extra_wait: int = 1500
):
    """
    smart_goto + HTTP 상태 코드 로깅
    
    Returns:
        tuple: (response, status_code)
    """
    response = await smart_goto(
        page, url, 
        wait_for_selector=wait_for_selector,
        timeout=timeout,
        selector_timeout=selector_timeout,
        extra_wait=extra_wait
    )
    
    status_code = response.status if response else None
    
    if status_code:
        if status_code >= 400:
            logger.error(f"❌ HTTP {status_code}: {url}")
        elif status_code >= 300:
            logger.warning(f"⚠️ HTTP {status_code} redirect: {url}")
    
    return response, status_code




