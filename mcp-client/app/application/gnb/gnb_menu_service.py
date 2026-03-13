"""
GNB 메뉴 추출 서비스
- Step 1: KT 메인 페이지 DOM 추출 (Playwright headless)
- Step 2: GNB 메뉴 트리 파싱 (BeautifulSoup)
- Step 3: 각 메뉴 URL 방문하여 서브메뉴 추출 (Playwright async)
"""
import json
import asyncio
import logging
import re
import uuid
from copy import copy
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from collections import Counter
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.application.crawler.page_handlers.utils import launch_chromium
from app.domains.gnb.repositories.menu_repository import menu_repository

logger = logging.getLogger(__name__)


class GnbExtractionTask:
    """GNB 추출 태스크 상태"""

    def __init__(self, task_id: str, save_to_db: bool, delay: float):
        self.task_id = task_id
        self.save_to_db = save_to_db
        self.delay = delay
        self.status = "pending"  # pending / running / completed / failed
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.error: Optional[str] = None
        self.step = ""
        self.progress: Dict[str, Any] = {}
        self.result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "step": self.step,
            "progress": self.progress,
            "result": self.result,
        }


class GnbMenuService:
    """GNB 메뉴 추출 서비스 — 3단계 파이프라인을 단일 클래스로 통합"""

    PAGE_URL = "https://www.kt.com"

    # ── 크롤링 스킵 URL 패턴 (페이지 자체를 방문하지 않음) ──
    SKIP_CRAWL_PATTERNS = [
        'plnDispNo=2642', 'plnDispNo=2468', 'plnDispNo=2574',
        'plnDispNo=2708', 'dispNo=STOR04',
        'deal5g.do', 'phoneView.do', 'halfPricList.do',
        '/direct/', '/wire/',
        'soho/marketing.do', 'soho/productDetail.do',
        '/benefit/', 'hotdeal.kt.com', '/deal/', '/rental/',
        'supportAmtList.do',
        'ermsweb.kt.com/pc/qna/', 'ermsweb.kt.com/pc/compliment/',
        'membership.kt.com/more/MembershipMileageInfo.do',
        'membership.kt.com/culture/movie/BookingInfo.do',
        'membership.kt.com/culture/movie/HistoryInfo.do',
        'membership.kt.com/culture/show/BookingInfo.do',
        'membership.kt.com/culture/show/MyCultureInfo.do',
        'membership.kt.com/vip/lounge/',
        '/unify/orderHistory.do', '/person/', '/uniteOrder/',
        'my.kt.com/myinfo/', 'my.kt.com/contract/',
        'my.kt.com/myproduct/', 'my.kt.com/pause/',
        'my.kt.com/lostas/', 'my.kt.com/number/',
        'my.kt.com/install/', 'my.kt.com/usage/',
        'my.kt.com/bill/', 'my.kt.com/statement/',
        'my.kt.com/payment/', 'my.kt.com/legal/',
        'my.kt.com/advance/', 'my.kt.com/membership/',
        'my.kt.com/mypoint/',
    ]

    # ── 제외 이름 패턴 (UI 요소) ──
    EXCLUDE_NAME_PATTERNS = [
        r'^_?닫기_?$', r'^주문하기$', r'^이전\s*다음$', r'^확인$', r'^동의$', r'^검색$',
        r'^레이어\s*닫기$', r'^목록$', r'^장바구니$', r'^마이샵$', r'^로그인$', r'^회원가입$',
        r'자세히\s*보기$', r'^더보기$', r'^TOP$', r'^맨위로$', r'^공유하기$', r'^찜하기$',
        r'^비교하기$', r'\(?바로가기\)?$', r'^이전$', r'^다음$', r'^이전글$', r'^다음글$',
        r'^HOME$', r'^홈$', r'^메뉴$', r'^전체메뉴$', r'^레이어\s*팝업$', r'^팝업\s*닫기$',
        r'^SNS\s*공유$', r'^카카오톡$', r'^페이스북$', r'^트위터$', r'^링크\s*복사$',
        r'신청하기$', r'상담\s*신청', r'가입\s*상담', r'구매하기$',
        r'하러\s*가기$', r'변경하기$',
        r'^상품안내$',
        r'^다운로드$',
    ]

    # ── GNB 메뉴 트리에서 제외할 키워드 (네비게이션 탭 — 해당 노드와 하위 전체 제외) ──
    EXCLUDE_MENU_KEYWORDS = ["인기메뉴", "신규메뉴"]

    # ── 추출된 이름에서 제거할 뱃지 접두사 ──
    BADGE_PREFIXES = ["추천 ", "인기 ", "간편가입 ", "NEW "]

    # ── 제외 URL 패턴 ──
    EXCLUDE_URL_PATTERNS = [
        '/mobile/view.do', '/accessory/accsProductView.do',
        '/orderCartView.do', '/orderHistory.do',
        '/login', '/member/', 'javascript:', '#',
        '.exe',
    ]

    # ── 동적 페이지 설정 (패턴별 크롤링 규칙) ──
    DYNAMIC_PAGE_CONFIGS = [
        # 1. wDic 상품사전 (탭 + 서브필터 + 더보기)
        {
            'pattern': r'product\.kt\.com/wDic/.*index\.do\?CateCode=',
            'tab_selector': 'ul.ui-tab-list li, ul.red-select li, .ui-tab-lst li',
            'tab_item_selector': 'a',  # 탭 내 클릭할 요소
            'sub_filter_selector': '.type-sub-item a, .type-sub-item button, .type-sub-item label',
            'more_button_selector': '.btn-more, .btn_more, button:has-text("더보기")',
            'item_selector': '.plan-list-area .btns a[href*="productDetail"], .plan-list li a[href*="productDetail"]',
            'item_title_selector': '.title, .plan_tit, .tit, strong',
            'tab_wait': 3000,         # 5G/3G 등 탭 전환 후 콘텐츠 로딩 대기
            'sub_filter_wait': 3000,  # 만 18세 이하 등 서브필터 전환 후 대기
        },
        # 2. 기가지니 서비스 상세 (탭 버튼 순회)
        {
            'pattern': r'gigagenie\.kt\.com/whyGenieServiceDetail\.do',
            'tab_selector': '#depth2Level li',
            'tab_item_selector': 'button',
            'extract_tabs_as_items': True,  # 탭 자체를 메뉴 아이템으로 추출
        },
        # 3. 기가지니 지니소식 (더보기 + 목록)
        {
            'pattern': r'gigagenie\.kt\.com/whyGenieNews\.do',
            'more_button_selector': 'button#btn_more',
            'item_selector': 'ul#bloglist li a.thumbnail',
            'item_title_selector': '.text-box .title', # 썸네일 내부 타이틀
        },
        # 4. 기가지니 FAQ (상품 버튼 탭 + 페이지네이션 + 질문 목록)
        {
            'pattern': r'gigagenie\.kt\.com/whyGenieFaq\.do',
            'tab_selector': 'button[class*="fjbCard"]', # 상품 버튼을 탭으로 취급
            'tab_item_selector': None, # selector 자체가 클릭 대상
            'pagination_selector': 'a[onclick*="selectFaqList"]', # 페이지네이션 (JS 실행 필요할 수 있음)
            'item_selector': 'ul#faqList li a.fjbQuestion',
            'item_title_selector': None, # selector 텍스트 자체 사용
        },
        # 5. ERMS FAQ (탭 + 페이지네이션 + 아코디언)
        {
            'pattern': r'ermsweb\.kt\.com/pc/faq/faqList\.do',
            'tab_selector': 'ul#tab-slide-menu li',
            'tab_item_selector': 'a',
            'pagination_selector': '.pagination .scope a',
            'item_selector': 'ul.accordions > li.liWrap .qna',
        }
    ]

    # ── 태스크 관리 ──
    _tasks: Dict[str, GnbExtractionTask] = {}

    def create_extraction_task(self, save_to_db: bool = True, delay: float = 1.0) -> str:
        task_id = str(uuid.uuid4())
        task = GnbExtractionTask(task_id, save_to_db, delay)
        self._tasks[task_id] = task
        logger.info(f"✅ GNB extraction task created: {task_id}")
        asyncio.create_task(self._process_extraction_task(task))
        return task_id

    def get_extraction_task(self, task_id: str) -> Optional[GnbExtractionTask]:
        return self._tasks.get(task_id)

    def get_extraction_tasks(self, limit: int = 10) -> List[dict]:
        sorted_tasks = sorted(
            self._tasks.values(), key=lambda t: t.created_at, reverse=True
        )
        return [t.to_dict() for t in sorted_tasks[:limit]]

    async def _process_extraction_task(self, task: GnbExtractionTask) -> None:
        try:
            task.status = "running"
            pipeline_start = datetime.now()

            # Step 1
            task.step = "dom_extraction"
            task.progress = {"message": "KT 메인 페이지 DOM 추출 중..."}
            html = await self.extract_dom()

            # Step 2
            task.step = "gnb_parsing"
            task.progress = {"message": "GNB 메뉴 트리 파싱 중..."}
            menu_tree = self.parse_gnb_menu(html)

            # Step 3
            task.step = "submenu_extraction"
            total_leaf = self._count_nodes(menu_tree)["crawl"]
            task.progress = {
                "message": "서브메뉴 추출 중...",
                "current": 0,
                "total": total_leaf,
            }
            menu_tree = await self.extract_submenus(
                menu_tree, delay=task.delay, task=task,
            )

            # Flatten & save
            task.step = "saving"
            task.progress = {"message": "DB 저장 중..."}
            flat_menus = self.flatten_menu_tree(menu_tree)
            logger.info(f"📊 평탄화 결과: {len(flat_menus)}개 URL")

            saved_count = 0
            if task.save_to_db and flat_menus:
                saved_count = await self.save_to_database(flat_menus)

            elapsed = str(datetime.now() - pipeline_start)
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            task.step = "done"
            task.result = {
                "total_menus": len(flat_menus),
                "saved_count": saved_count,
                "elapsed": elapsed,
            }
            task.progress = {"message": f"완료: {len(flat_menus)}개 추출, {saved_count}개 DB 저장"}
            logger.info(f"🎉 GNB extraction task completed: {task.task_id} ({elapsed})")

        except Exception as e:
            task.status = "failed"
            task.completed_at = datetime.now().isoformat()
            task.error = str(e)
            task.progress = {"message": f"실패: {e}"}
            logger.error(f"❌ GNB extraction task failed: {task.task_id} - {e}", exc_info=True)

    # ── 링크 추출 전 제거 셀렉터 ──
    DECOMPOSE_SELECTORS = [
        '#cfmClHeader', '#cfmClFooter', '#cfmClSkip', '.header', '.footer',
        '.navigation', '.sidebar', '.banner', '.popup', '.overlay', '.sns-area', '.location',
        '.gnb', '.lnb', '.snb', '.util', '.quick', '.ui-tab-lst', '.ui-tab-top-lst',
        '.btn_auto_ga', '.btn_rpeSIM',
        '.link-list-area', '.link-list',
        'a[class*="_link"]', 'a[class*="link"]',
        'a[target="_blank"]', '.button-solid',
    ]

    # ── <a> 내부 제목 우선 탐색 셀렉터 (순서대로 시도) ──
    TITLE_SELECTORS_IN_A = [
        '[class*="Title"]', '[class*="title"]',
        '[class*="Tit"]', '[class*="tit"]',
        '[class*="Name"]', '[class*="name"]',
        '[class*="heading"]',
    ]

    # ── 텍스트 제외 셀렉터 ──
    EXCLUDE_TEXT_SELECTORS = [
        '.date', '.txt', '.desc', '.category', '.tag', '.badge', '.icon',
        '.num', '.count', '.view', '.hit',
        'span.sub', 'em.sub', '.sub-txt',
        '.blind', '.sr-only', '.hidden', '.hidetxt',
        '.btn', '.more', '.linked', '.breadcrumb', '.path',
        '[class*="biz-m-"]',
    ]

    # ──────────────────────────────────────────────
    #  Helper Methods
    # ──────────────────────────────────────────────

    STRIP_QUERY_PARAMS = {"option_code", "pageSize"}

    @classmethod
    def _normalize_url(cls, href: str, page_url: str) -> Optional[str]:
        if not href:
            return None
        href = href.strip()
        if href.startswith("javascript:"):
            m = re.search(r"'(https?://[^']+)'", href)
            href = m.group(1) if m else None
            if not href:
                return None
        elif not href.startswith("http"):
            href = urljoin(page_url, href)
        return cls._strip_noisy_params(href)

    @classmethod
    def _strip_noisy_params(cls, url: str) -> str:
        """option_code, pageSize 등 크롤링 비교 시 노이즈가 되는 쿼리 파라미터 제거"""
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in params.items() if k not in cls.STRIP_QUERY_PARAMS}
        new_query = urlencode(filtered, doseq=True)
        return urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment,
        ))

    def _should_skip(self, url: str) -> bool:
        return any(p in url for p in self.SKIP_CRAWL_PATTERNS)

    @staticmethod
    def _is_kt_domain(url: str) -> bool:
        return url.startswith('http') and '.kt.com' in url

    @staticmethod
    def _get_base_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _is_excluded_name(self, name: str) -> bool:
        return any(re.search(p, name.strip(), re.IGNORECASE) for p in self.EXCLUDE_NAME_PATTERNS)

    def _is_excluded_url(self, url: str) -> bool:
        return any(p in url for p in self.EXCLUDE_URL_PATTERNS)

    def _extract_title_from_a(self, a_tag) -> str:
        """<a> 태그에서 제목 텍스트를 우선순위에 따라 추출"""
        excluded_ids = set()
        for sel in self.EXCLUDE_TEXT_SELECTORS:
            for el in a_tag.select(sel):
                excluded_ids.add(id(el))

        for sel in self.TITLE_SELECTORS_IN_A:
            el = a_tag.select_one(sel)
            if el and id(el) not in excluded_ids:
                text = el.get_text(strip=True)
                if text:
                    return text
        a_copy = copy(a_tag)
        for sel in self.EXCLUDE_TEXT_SELECTORS:
            for el in a_copy.select(sel):
                el.decompose()
        return a_copy.get_text(strip=True)

    # ── 안전한 네비게이션/클릭 헬퍼 ──

    @staticmethod
    async def _safe_goto(page, url: str, timeout: int = 30000, retries: int = 1):
        """
        page.goto를 재시도 포함하여 안전하게 실행.
        최종 실패 시 None 반환 (예외를 던지지 않음).
        """
        for attempt in range(1 + retries):
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                return True
            except Exception as e:
                if attempt < retries:
                    logger.warning(f"⏳ 페이지 로딩 재시도 ({attempt + 1}/{retries}): {url}")
                    await page.wait_for_timeout(2000)
                else:
                    logger.warning(f"⏭️ 페이지 로딩 타임아웃, 스킵: {url} ({e.__class__.__name__})")
                    return False

    @staticmethod
    async def _safe_click(locator, timeout: int = 5000) -> bool:
        """
        locator가 존재하고 visible일 때만 클릭.
        타임아웃이나 visibility 실패 시 False 반환.
        """
        try:
            if await locator.count() == 0:
                return False
            if not await locator.is_visible():
                return False
            await locator.click(timeout=timeout)
            return True
        except Exception:
            return False

    # ──────────────────────────────────────────────
    #  Step 1 — DOM 추출 (Playwright headless)
    # ──────────────────────────────────────────────

    async def extract_dom(self) -> str:
        """KT 메인 페이지 접속 후 모든 메뉴를 펼친 상태의 전체 DOM HTML 반환"""
        logger.info("🚀 [Step 1] KT 메인 페이지 DOM 추출 시작")
        async with async_playwright() as p:
            browser = await launch_chromium(p)
            page = await browser.new_page()

            try:
                await page.goto(self.PAGE_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                await browser.close()
                raise RuntimeError(f"페이지 로딩 실패: {e}")

            logger.info(f"Page Title: {await page.title()}")

            # 모든 visible <a> 태그에 hover
            links = page.locator("a:visible")
            link_count = await links.count()
            logger.info(f"visible a 태그 수: {link_count}")
            for i in range(link_count):
                try:
                    await links.nth(i).hover(timeout=500)
                    await page.wait_for_timeout(100)
                except Exception:
                    pass

            # 모든 visible <button> 태그 클릭
            buttons = page.locator("button:visible")
            button_count = await buttons.count()
            logger.info(f"visible button 태그 수: {button_count}")
            for i in range(button_count):
                try:
                    await buttons.nth(i).click(timeout=500)
                    await page.wait_for_timeout(100)
                except Exception:
                    pass

            html = await page.content()
            await browser.close()

        logger.info(f"✅ [Step 1] DOM 추출 완료 ({len(html):,} bytes)")
        return html

    # ──────────────────────────────────────────────
    #  Step 2 — GNB 메뉴 트리 파싱
    # ──────────────────────────────────────────────

    def parse_gnb_menu(self, html: str) -> list:
        """DOM HTML에서 GNB(#cfmClGnb) 메뉴 트리를 재귀적으로 추출"""
        logger.info("🚀 [Step 2] GNB 메뉴 트리 파싱 시작")
        soup = BeautifulSoup(html, "html.parser")

        gnb = soup.find("div", id="cfmClGnb")
        if not gnb:
            raise RuntimeError("cfmClGnb 요소를 찾을 수 없습니다")

        top_ul = gnb.find("ul")
        if not top_ul:
            raise RuntimeError("1뎁스 ul 요소를 찾을 수 없습니다")

        menu_tree = []
        for li in top_ul.find_all("li", recursive=False):
            menu = self._parse_menu_item(li, self.PAGE_URL)
            if menu:
                menu_tree.append(menu)

        depth_counts: Dict[int, int] = {}
        for menu in menu_tree:
            self._count_menu(menu, depth_counts)
        for d in sorted(depth_counts):
            logger.info(f"  {d} depth: {depth_counts[d]}개")
        logger.info(f"✅ [Step 2] 파싱 완료 — 총 {sum(depth_counts.values())}개 메뉴")

        return menu_tree

    def _parse_menu_item(self, li, page_url: str) -> Optional[dict]:
        tag_a = li.find("a", recursive=False)
        if not tag_a:
            return None
        name = tag_a.get_text(strip=True)
        if not name:
            return None
        if any(kw in name for kw in self.EXCLUDE_MENU_KEYWORDS):
            return None
        url = self._normalize_url(tag_a.get("href"), page_url)
        sub_ul = li.find("ul", class_=lambda x: x and "depth" in x)
        children = []
        if sub_ul:
            for sub_li in sub_ul.find_all("li", recursive=False):
                child = self._parse_menu_item(sub_li, page_url)
                if child:
                    children.append(child)
        return {"name": name, "url": url, "children": children}

    @staticmethod
    def _count_menu(menu: dict, depth_counts: dict, depth: int = 1):
        depth_counts[depth] = depth_counts.get(depth, 0) + 1
        for child in menu.get("children", []):
            GnbMenuService._count_menu(child, depth_counts, depth + 1)

    # ──────────────────────────────────────────────
    #  Step 3 — 서브메뉴 추출
    # ──────────────────────────────────────────────

    async def extract_submenus(
        self, menu_tree: list, delay: float = 1.0,
        task: Optional[GnbExtractionTask] = None,
    ) -> list:
        """빈 children을 가진 노드의 URL을 방문하여 서브메뉴 채우기"""
        logger.info("🚀 [Step 3] 서브메뉴 추출 시작")
        stats = self._count_nodes(menu_tree)
        logger.info(f"  전체: {stats['total']}개, 크롤링 대상: {stats['crawl']}개, 스킵: {stats['skip']}개")

        crawled_counter = {"n": 0, "total": stats["crawl"]}

        start = datetime.now()
        for i, menu in enumerate(menu_tree, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"[{i}/{len(menu_tree)}] {menu.get('name', '')}")
            await self._process_node(menu, [], delay, task=task, counter=crawled_counter)

        elapsed = datetime.now() - start
        logger.info(f"✅ [Step 3] 서브메뉴 추출 완료 (소요시간: {elapsed})")
        return menu_tree

    def _count_nodes(self, tree: list) -> dict:
        stats = {'total': 0, 'empty': 0, 'skip': 0, 'crawl': 0}

        def _walk(nodes):
            for n in nodes:
                stats['total'] += 1
                children = n.get('children', [])
                url = n.get('url', '')
                if isinstance(children, list) and not children and url.startswith('http'):
                    stats['empty'] += 1
                    if self._should_skip(url):
                        stats['skip'] += 1
                    else:
                        stats['crawl'] += 1
                elif isinstance(children, list) and children:
                    _walk(children)

        _walk(tree)
        return stats

    async def _process_node(
        self, menu: dict, hierarchy: list, delay: float = 1.0,
        task: Optional[GnbExtractionTask] = None,
        counter: Optional[dict] = None,
    ):
        name = menu.get('name', '')
        url = menu.get('url', '')
        children = menu.get('children', [])
        current = hierarchy + [name]

        if isinstance(children, list) and not children and url.startswith('http'):
            logger.info(f"🔍 [{len(current)}depth] {' > '.join(current)}")
            logger.info(f"   URL: {url}")

            result = await self._crawl_page(url)

            if result['success']:
                if result.get('skipped'):
                    logger.info("⏭️ 스킵됨")
                    menu['children'] = []
                elif result.get('subtree'):
                    menu['children'] = result['subtree']
                    logger.info(f"✅ 구조화된 서브트리 적용 ({len(menu['children'])}개 1뎁스 자식)")
                else:
                    links = result.get('links', [])
                    menu['children'] = [{'name': l['name'], 'url': l['url']} for l in links]
                    logger.info(f"✅ 완료 ({len(links)}개)" if links else "⚠️ 추출 결과 없음")
            else:
                logger.error(f"❌ 실패: {result.get('error')}")
                menu['children'] = []

            if not result.get('skipped'):
                await asyncio.sleep(delay)

            if counter is not None:
                counter["n"] += 1
                if task is not None:
                    task.progress = {
                        "message": f"서브메뉴 추출 중... ({counter['n']}/{counter['total']})",
                        "current": counter["n"],
                        "total": counter["total"],
                        "current_menu": " > ".join(current),
                    }

        elif isinstance(children, list) and children:
            for child in children:
                await self._process_node(child, current, delay, task=task, counter=counter)

    # ── 페이지 크롤링 (우선순위별 추출) ──

    async def _crawl_page(self, url: str) -> dict:
        if self._should_skip(url):
            logger.info(f"⏭️ 스킵: {url}")
            return {'success': True, 'links': [], 'skipped': True}

        try:
            async with async_playwright() as p:
                browser = await launch_chromium(p)
                page = await browser.new_page()

                if not await self._safe_goto(page, url, timeout=60000, retries=1):
                    await browser.close()
                    return {'success': True, 'links': [], 'skipped': False}

                # [동적 페이지 처리] 설정 기반 크롤링
                for config in self.DYNAMIC_PAGE_CONFIGS:
                    if re.search(config['pattern'], url):
                        logger.info(f"🔄 동적 페이지 패턴 매칭: {url}")
                        subtree = await self._crawl_dynamic_page(page, config)
                        await browser.close()
                        return {'success': True, 'subtree': subtree}

                await page.wait_for_timeout(5000)
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2000)

                # 0-a) display:none 강제 노출 (globalroaming, ktshop 패턴)
                await self._force_show_hidden_elements(page)

                # 0-b) 아코디언 확장 (membership, faq, wdic 패턴)
                await self._expand_accordions(page)

                # 0-c) iframe[title] 우선
                all_iframes = await page.locator('iframe[title]').all()
                for iframe_el in all_iframes:
                    title = await iframe_el.get_attribute('title')
                    if title:
                        links = await self._extract_from_titled_iframe(page, title)
                        if links:
                            await browser.close()
                            return {'success': True, 'links': links}

                # 1) 상품
                products = await self._extract_products(page)
                if products:
                    await browser.close()
                    return {'success': True, 'links': products}

                # 2) 게시판
                links = await self._extract_board_links(page)
                if links:
                    await browser.close()
                    return {'success': True, 'links': links}

                # 3) 탭
                tabs = await self._extract_tabs(page)
                if tabs:
                    await browser.close()
                    return {'success': True, 'links': tabs}

                # 4) iframe + 페이지네이션
                iframe_links = await self._try_extract_from_iframes(page)
                if iframe_links:
                    await browser.close()
                    return {'success': True, 'links': iframe_links}

                # 5) 다음글 체인 (kt_notice, safety_notice 패턴)
                chain_links = await self._extract_next_link_chain(page)
                if chain_links:
                    await browser.close()
                    return {'success': True, 'links': chain_links}

                # 6) 최종 fallback: 페이지 본문 링크 추출
                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                base_url = self._get_base_url(page.url)
                fallback_links = self._extract_links_from_soup(soup, base_url, min_count=3)
                if fallback_links:
                    await browser.close()
                    return {'success': True, 'links': fallback_links}

                await browser.close()
                logger.info("⚠️ 추출 대상 없음")
                return {'success': True, 'links': []}

        except Exception as e:
            logger.error(f"❌ 크롤링 실패: {e}")
            return {'success': False, 'error': str(e), 'links': []}

    # ── 동적 페이지(탭/필터/더보기) 크롤링 로직 (내재화) ──

    async def _crawl_dynamic_page(self, page, config: dict) -> list:
        """
        설정(config)에 따라 탭 -> 서브필터 -> 더보기/페이지네이션 순으로 순회하며
        계층형 메뉴 구조(subtree)를 추출한다.
        """
        # 1. 탭 목록 추출
        tabs = []
        if config.get('tab_selector'):
            tabs = await self._extract_elements_info(page, config['tab_selector'], config.get('tab_item_selector'))
            if tabs:
                logger.info(f"  📊 탭 목록 추출: {len(tabs)}개 found ({', '.join([t['text'] for t in tabs])})")
        
        # 탭이 없으면 '전체' 탭 하나가 있는 것으로 간주
        if not tabs:
            tabs = [{'index': None, 'text': None, 'selector': None}]

        subtree = []

        for tab in tabs:
            tab_name = tab['text']
            tab_idx = tab['index']
            
            logger.info(f"  👉 탭 진입: {tab_name if tab_name else '(기본)'}")

            # 탭 클릭
            if tab_idx is not None:
                logger.debug(f"    🔄 탭 클릭 시도: {tab_name} (index {tab_idx})")
                clicked = await self._click_element_by_index(page, config['tab_selector'], tab_idx, config.get('tab_item_selector'))
                if clicked:
                    try:
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception:
                        pass
                    tab_wait = config.get('tab_wait', 1000)
                    await page.wait_for_timeout(tab_wait)
                else:
                    logger.warning(f"    ⚠️ 탭 클릭 실패: {tab_name}")
                    continue

            # 탭 자체를 아이템으로 추출하는 경우 (예: 기가지니 상세)
            if config.get('extract_tabs_as_items') and tab_name:
                subtree.append({
                    'name': tab_name,
                    'url': page.url,
                    'children': []
                })
                continue

            # 2. 서브 필터 추출
            sub_filters = []
            if config.get('sub_filter_selector'):
                sub_filters = await self._extract_elements_info(page, config['sub_filter_selector'])
                if sub_filters:
                    logger.info(f"    📊 서브필터 목록: {len(sub_filters)}개")

            # 서브 필터가 없으면 '전체' 필터 하나가 있는 것으로 간주
            if not sub_filters:
                sub_filters = [{'index': None, 'text': None}]

            tab_children = []

            for sub in sub_filters:
                sub_name = sub['text']
                sub_idx = sub['index']
                
                if sub_name:
                    logger.info(f"      👉 서브필터 진입: {sub_name}")

                # 서브 필터 클릭
                if sub_idx is not None:
                    clicked = await self._click_element_by_index(page, config['sub_filter_selector'], sub_idx)
                    if clicked:
                        try:
                            await page.wait_for_load_state('networkidle', timeout=5000)
                        except Exception:
                            pass
                        sub_filter_wait = config.get('sub_filter_wait', 1000)
                        await page.wait_for_timeout(sub_filter_wait)
                    else:
                        continue

                # 3. 더보기 / 페이지네이션 → 4. 아이템 추출 (0개 시 재시도)
                max_retries = 2 if sub_idx is not None else 0
                items = await self._extract_items_with_retry(
                    page, config, max_retries=max_retries,
                    label=sub_name or tab_name or '',
                )
                
                # 아이템들을 자식 노드로 변환
                item_nodes = [{'name': item['name'], 'url': item['url'], 'children': []} for item in items]

                if sub_name:
                    # 서브 필터가 있으면: 탭 > 서브필터 > 아이템
                    tab_children.append({
                        'name': sub_name,
                        'url': page.url,
                        'children': item_nodes
                    })
                else:
                    # 서브 필터가 없으면: 탭 > 아이템
                    tab_children.extend(item_nodes)

            if tab_name:
                subtree.append({
                    'name': tab_name,
                    'url': page.url,
                    'children': tab_children
                })
            else:
                subtree.extend(tab_children)

        return subtree

    async def _extract_elements_info(self, page, selector: str, child_selector: str = None) -> list:
        """지정된 셀렉터의 요소들 정보를 추출 (index, text)"""
        return await page.evaluate(f"""
            () => {{
                const els = Array.from(document.querySelectorAll('{selector}'));
                return els.map((el, idx) => {{
                    // visible check
                    if (el.offsetParent === null) return null;

                    let target = el;
                    if ('{child_selector or ""}') {{
                        target = el.querySelector('{child_selector or ""}');
                    }}
                    if (!target) return null;
                    
                    const text = (target.textContent || '').trim();
                    if (!text || text === '추천') return null;
                    
                    return {{ index: idx, text: text }};
                }}).filter(x => x !== null);
            }}
        """)

    async def _click_element_by_index(self, page, selector: str, index: int, child_selector: str = None) -> bool:
        """인덱스로 요소 클릭"""
        return await page.evaluate(f"""
            () => {{
                const els = document.querySelectorAll('{selector}');
                if (els.length <= {index}) return false;
                let target = els[{index}];
                
                // visible check
                if (target.offsetParent === null) return false;

                if ('{child_selector or ""}') {{
                    target = target.querySelector('{child_selector or ""}');
                }}
                if (!target) return false;
                
                target.click();
                return true;
            }}
        """)

    async def _click_more_until_exhausted(self, page, selector: str):
        """더보기 버튼 반복 클릭 (Playwright locator 사용 — :has-text() 등 지원)"""
        for attempt in range(20):
            try:
                btn = page.locator(selector).first
                if await btn.count() == 0:
                    break
                if not await btn.is_visible():
                    break
                await btn.click(timeout=3000)
                logger.debug(f"  🔘 더보기 클릭 ({attempt + 1}회)")
                await page.wait_for_timeout(1500)
            except Exception:
                break

    async def _extract_items_with_retry(
        self, page, config: dict, max_retries: int = 2, label: str = '',
    ) -> list:
        """
        더보기 클릭 + 아이템 추출. 0개면 추가 대기 후 재시도.
        서브필터 전환 직후 DOM 업데이트가 늦는 경우를 대비.
        """
        retry_wait = 3000

        for attempt in range(1 + max_retries):
            if config.get('more_button_selector'):
                await self._click_more_until_exhausted(page, config['more_button_selector'])

            items = []
            if config.get('item_selector'):
                items = await self._extract_dynamic_items(
                    page, config['item_selector'], config.get('item_title_selector'),
                )

            if items:
                item_names = [i['name'] for i in items[:5]]
                suffix = f"... 외 {len(items)-5}개" if len(items) > 5 else ""
                logger.info(
                    f"        📦 아이템 {len(items)}개 추출: "
                    f"{', '.join(item_names)}{suffix}"
                )
                return items

            if attempt < max_retries:
                logger.info(
                    f"        ⏳ [{label}] 아이템 0개 → "
                    f"재시도 {attempt + 1}/{max_retries} ({retry_wait}ms 대기)"
                )
                await page.wait_for_timeout(retry_wait)
                retry_wait = min(retry_wait * 2, 10000)

        if label:
            logger.warning(f"        ⚠️ [{label}] 재시도 후에도 아이템 0개")
        return []

    async def _extract_dynamic_items(self, page, item_selector: str, title_selector: str = None) -> list:
        """리스트 아이템 추출"""
        base_url = self._get_base_url(page.url)
        
        script = f"""
            () => {{
                const results = [];
                const items = Array.from(document.querySelectorAll('{item_selector}'));
                const ignoreTexts = ['상세보기', '자세히보기', '자세히 보기', '신청하기', '바로가기', '더보기', 'Go', '링크', '이동', '인기', '추천', '덤 혜택', '간편가입'];
                
                items.forEach(item => {{
                    let href = item.getAttribute('href') || '';
                    if (!href || href === '#' || href.startsWith('javascript:')) {{
                        const onclick = item.getAttribute('onclick') || '';
                        const match = onclick.match(/goDetPage\((\d+)\)/);
                        if (match) {{
                            href = 'detail.do?seq=' + match[1];
                        }} else {{
                            return;
                        }}
                    }}
                    
                    let title = '';
                    
                    // 1. title_selector가 있으면 상위 요소 탐색하며 찾기
                    if ('{title_selector or ""}') {{
                        let current = item;
                        // 최대 5단계 부모까지 확인
                        for(let i=0; i<5; i++) {{
                            current = current.parentElement;
                            if(!current) break;
                            
                            // title_selector에 해당하는 모든 요소 찾기
                            const tEls = Array.from(current.querySelectorAll('{title_selector or ""}'));
                            
                            // 불용어가 아닌 유효한 텍스트를 가진 첫 번째 요소 찾기
                            for (const tEl of tEls) {{
                                const text = (tEl.textContent || '').replace(/[\\n\\r]+/g, ' ').replace(/\\s+/g, ' ').trim();
                                if (text && !ignoreTexts.includes(text)) {{
                                    title = text;
                                    break;
                                }}
                            }}
                            if (title) break;
                        }}
                    }}
                    
                    // 2. 못 찾았으면 자신의 텍스트 사용
                    if (!title) {{
                        title = (item.textContent || '').replace(/[\\n\\r]+/g, ' ').replace(/\\s+/g, ' ').trim();
                    }}
                    
                    // 3. 이미지 alt fallback
                    if (!title || ignoreTexts.includes(title)) {{
                        const img = item.querySelector('img');
                        if (img) title = (img.alt || '').replace(/[\\n\\r]+/g, ' ').replace(/\\s+/g, ' ').trim();
                    }}
                    
                    // 불용어 필터링
                    if (ignoreTexts.includes(title)) return;
                    
                    // 뱃지 접두사 제거
                    const badgePrefixes = ['추천 ', '인기 ', '간편가입 ', 'NEW '];
                    for (const bp of badgePrefixes) {{
                        if (title.startsWith(bp)) {{
                            title = title.slice(bp.length);
                            break;
                        }}
                    }}
                    
                    if (title && href) {{
                        results.push({{ name: title, url: href }});
                    }}
                }});
                return results;
            }}
        """
        
        items = await page.evaluate(script)
        
        normalized_items = []
        seen = set()
        for item in items:
            name = item['name']
            url = self._normalize_url(item['url'], base_url)
            
            # 파이썬 측에서도 한 번 더 필터링
            if name in ['자세히보기', '자세히 보기', '신청하기', '바로가기', '더보기', '인기', '추천', '덤 혜택', '간편가입']:
                continue

            for prefix in self.BADGE_PREFIXES:
                if name.startswith(prefix):
                    name = name[len(prefix):]
                    break

            key = f"{name}|{url}"
            if url and key not in seen:
                seen.add(key)
                normalized_items.append({'name': name, 'url': url})
                
        return normalized_items

    # ── 핸들러 패턴 마이그레이션 ──

    @staticmethod
    async def _force_show_hidden_elements(page) -> None:
        """display:none / visibility:hidden 요소를 강제로 노출 (globalroaming, ktshop 패턴)"""
        try:
            await page.evaluate("""
                () => {
                    const selectors = [
                        '.prodBox', '.prodList', '.product-list', '.plan-list',
                        '[class*="depth"]', '[class*="sub-menu"]', '[class*="submenu"]',
                        '.tab-content', '.tab-pane', '.panel-collapse',
                    ];
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            const style = getComputedStyle(el);
                            if (style.display === 'none') {
                                el.style.display = 'block';
                            }
                            if (style.visibility === 'hidden') {
                                el.style.visibility = 'visible';
                            }
                        });
                    });
                }
            """)
        except Exception:
            pass

    @staticmethod
    async def _expand_accordions(page) -> None:
        """아코디언 트리거를 클릭하여 숨겨진 콘텐츠 노출 (membership, faq, wdic 패턴)"""
        try:
            triggers = page.locator(
                '.accordion-trigger:not(.active), '
                '[data-toggle="collapse"]:not(.active), '
                '.faq-question:not(.active), '
                'button[aria-expanded="false"]'
            )
            count = await triggers.count()
            for i in range(min(count, 30)):
                try:
                    await triggers.nth(i).click(timeout=1000)
                    await page.wait_for_timeout(300)
                except Exception:
                    pass
        except Exception:
            pass

    async def _extract_next_link_chain(self, page) -> list:
        """다음글 링크를 따라가며 순차 추출 (kt_notice, safety_notice 패턴)"""
        links, seen = [], set()
        base_url = self._get_base_url(page.url)
        max_pages = 50

        for _ in range(max_pages):
            current_url = page.url
            if current_url in seen:
                break
            seen.add(current_url)

            try:
                title = await page.title()
                title = (title or "").strip()
                if title and len(title) >= 2:
                    links.append({"name": title, "url": current_url})
            except Exception:
                pass

            next_link = page.locator(
                'a.next-area:visible, '
                'a[data-bno].next-area:visible, '
                'a:has-text("다음글"):visible'
            ).first

            if not await self._safe_click(next_link):
                break
            await page.wait_for_timeout(2000)

        return links

    # ── 링크 추출 유틸 ──

    def _extract_links_from_soup(self, soup, base_url: str, min_count: int = 1) -> list:
        links, seen = [], set()

        for sel in self.DECOMPOSE_SELECTORS:
            for el in soup.select(sel):
                el.decompose()

        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if href.startswith('/'):
                href = f"{base_url}{href}"
            if not self._is_kt_domain(href) or self._is_excluded_url(href) or href in seen:
                continue

            if '/wDic/productDetail.do' in href:
                if 'ItemCode=' not in href or not a.get('title'):
                    continue

            onclick = a.get('onclick', '')
            if 'javascript:' in onclick.lower():
                continue

            a_check = copy(a)
            for sel in self.EXCLUDE_TEXT_SELECTORS:
                for el in a_check.select(sel):
                    el.decompose()
            visible_text = a_check.get_text(strip=True)
            if not visible_text and not a.get('title'):
                continue

            text = ''

            parent_li = a.find_parent('li')
            if parent_li:
                tit = parent_li.select_one('.plan_tit em')
                if tit:
                    text = tit.get_text(strip=True)

            if not text:
                onclick = a.get('onclick', '')
                if onclick and 'EVENT_LABEL' in onclick:
                    match = re.search(r"EVENT_LABEL\s*:\s*'([^']+)'", onclick)
                    if match:
                        text = match.group(1).rsplit('_', 1)[0]

            if not text:
                text = self._extract_title_from_a(a)

            if not text:
                text = a.get('title', '').strip()

            if not text or len(text) < 2 or self._is_excluded_name(text):
                continue
            if len(text) > 150:
                text = text[:150] + '...'

            seen.add(href)
            links.append({'name': text, 'url': href})

        return links if len(links) >= min_count else []

    @staticmethod
    def _filter_by_dominant_pattern(links: list) -> list:
        def _get_pattern(url):
            match = re.search(r'/([a-zA-Z]+\.do)', url)
            return match.group(1) if match else 'other'

        pattern_counts = Counter(_get_pattern(l['url']) for l in links)
        if not pattern_counts:
            return links
        dominant = pattern_counts.most_common(1)[0][0]
        return [l for l in links if _get_pattern(l['url']) == dominant]

    # ── iframe 추출 ──

    async def _extract_from_titled_iframe(self, page, iframe_title: str) -> list:
        try:
            iframe_locator = page.locator(f'iframe[title="{iframe_title}"]')
            if await iframe_locator.count() == 0:
                return []

            frame = iframe_locator.content_frame
            await page.wait_for_timeout(2000)

            all_links, seen = [], set()
            page_num = 1
            base_url = self._get_base_url(page.url)

            while True:
                links = await frame.locator('a[href]').all()
                count_before = len(all_links)

                for link in links:
                    try:
                        href = await link.get_attribute('href')

                        if not href or href == '#':
                            onclick = await link.get_attribute('onclick')
                            if onclick and 'eventListView' in onclick:
                                match = re.search(
                                    r"eventListView\((\d+),\s*'(\d+)',\s*'(\d+)'\)", onclick
                                )
                                if match:
                                    href = (
                                        f"{base_url}/plan/planDispView.do?"
                                        f"plnDispNo={match.group(1)}"
                                        f"&plnDispTypeCd={match.group(2)}"
                                        f"&evtNo={match.group(3)}"
                                    )

                        if not href or href == '#':
                            continue
                        href = href.strip()
                        if href.startswith('/'):
                            href = f"{base_url}{href}"
                        if not href.startswith('http') or href in seen or not self._is_kt_domain(href):
                            continue

                        text = ''
                        try:
                            onclick = await link.get_attribute('onclick')
                            if onclick and 'EVENT_LABEL' in onclick:
                                match = re.search(r"EVENT_LABEL\s*:\s*'([^']+)'", onclick)
                                if match:
                                    text = match.group(1).rsplit('_', 1)[0]
                        except Exception:
                            pass

                        if text and len(text) >= 2 and not self._is_excluded_name(text):
                            seen.add(href)
                            all_links.append({'name': text, 'url': href})
                    except Exception:
                        continue

                if len(all_links) - count_before == 0 and page_num > 1:
                    break

                next_btn = frame.locator(f'a[pageno="{page_num + 1}"]:not(.page)').first
                if await next_btn.count() == 0:
                    next_btn = frame.locator(f'a[pageno="{page_num + 1}"]').first

                if not await self._safe_click(next_btn):
                    break
                await page.wait_for_timeout(2000)
                page_num += 1

            if all_links:
                all_links = self._filter_by_dominant_pattern(all_links)
            return all_links

        except Exception as e:
            logger.error(f"❌ iframe[title=\"{iframe_title}\"] 처리 실패: {e}")
            return []

    async def _try_extract_from_iframes(self, page) -> list:
        # 1차: projectList + 페이지네이션
        for i, frame in enumerate(page.frames):
            try:
                html = await frame.content()
                soup = BeautifulSoup(html, 'html.parser')
                if len(soup.select('ul.projectList li a[href]')) >= 3 and soup.select_one('a[pageno]'):
                    return await self._extract_with_pagination(frame)
            except Exception:
                continue

        # 2차: pageno 기반
        for i, frame in enumerate(page.frames):
            try:
                html = await frame.content()
                soup = BeautifulSoup(html, 'html.parser')
                if soup.select_one('a[pageno]') and len(soup.select('li a[href]')) >= 3:
                    links = await self._extract_with_pagination_generic(frame)
                    if links:
                        return links
            except Exception:
                continue

        # 3차: projectList / ui-slide
        for i, frame in enumerate(page.frames):
            try:
                html = await frame.content()
                soup = BeautifulSoup(html, 'html.parser')
                if len(soup.select('ul.projectList li a[href]')) >= 3 or len(soup.select('ul.ui-slide li a[href]')) >= 3:
                    links = self._extract_links_from_soup(soup, self._get_base_url(frame.url), min_count=3)
                    if links:
                        return links
            except Exception:
                continue

        return []

    async def _extract_with_pagination(self, frame) -> list:
        all_links, seen = [], set()
        page_num = 1
        base_url = self._get_base_url(frame.url)

        while True:
            html = await frame.content()
            soup = BeautifulSoup(html, 'html.parser')
            count_before = len(all_links)

            for li in soup.select('ul.projectList li'):
                a = li.select_one('a[href]')
                if not a:
                    continue
                href = a.get('href', '')
                if href.startswith('/'):
                    href = f"{base_url}{href}"
                if href in seen or self._is_excluded_url(href):
                    continue

                tit = li.select_one('.plan_tit em')
                text = tit.get_text(strip=True) if tit else ''
                if not text:
                    img = a.find('img')
                    text = img.get('alt', '').strip() if img else ''
                if not text:
                    text = self._extract_title_from_a(a)

                if text and len(text) >= 2:
                    seen.add(href)
                    all_links.append({'name': text, 'url': href})

            if len(all_links) - count_before == 0 and page_num > 1:
                break

            next_locator = frame.locator(f'a[pageno="{page_num + 1}"]').first
            if not await self._safe_click(next_locator):
                break
            await frame.page.wait_for_timeout(2000)
            page_num += 1

        return all_links

    async def _extract_with_pagination_generic(self, frame) -> list:
        all_links, seen = [], set()
        page_num = 1
        base_url = self._get_base_url(frame.url)

        while True:
            html = await frame.content()
            soup = BeautifulSoup(html, 'html.parser')
            for sel in self.DECOMPOSE_SELECTORS:
                for el in soup.select(sel):
                    el.decompose()
            count_before = len(all_links)

            for a in soup.find_all('a', href=True):
                href = a.get('href', '').strip()
                if href.startswith('/'):
                    href = f"{base_url}{href}"
                if not href.startswith('http') or self._is_excluded_url(href) or href in seen:
                    continue
                if not self._is_kt_domain(href):
                    continue
                text = self._extract_title_from_a(a)
                if text and len(text) >= 2 and not self._is_excluded_name(text):
                    seen.add(href)
                    all_links.append({'name': text, 'url': href})

            if len(all_links) - count_before == 0 and page_num > 1:
                break

            next_locator = frame.locator(f'a[pageno="{page_num + 1}"]').first
            if not await self._safe_click(next_locator):
                break
            await frame.page.wait_for_timeout(2000)
            page_num += 1

        return all_links

    # ── 탭 / 상품 / 게시판 추출 ──

    async def _extract_tabs(self, page) -> list:
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        base_url = self._get_base_url(page.url)
        tabs, seen = [], set()

        for link in soup.find_all('a', href=True):
            img = link.find('img')
            if not img or 'tab' not in img.get('src', '').lower():
                continue
            href = link['href']
            if href.startswith('/'):
                href = f"{base_url}{href}"
            if not href.startswith('http') or href in seen:
                continue
            name = img.get('alt', '') or link.get_text(strip=True)
            if name:
                seen.add(href)
                tabs.append({'name': name, 'url': href})

        return tabs if len(tabs) >= 2 else []

    async def _extract_products(self, page) -> list:
        base_url = self._get_base_url(page.url)
        products, seen = [], set()
        page_num = 1

        while True:
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            count_before = len(products)

            for inp in soup.find_all('input', {'name': 'prodAttr'}):
                name, no = inp.get('prodnm', ''), inp.get('prodno', '')
                if name and no and no not in seen:
                    seen.add(no)
                    products.append({
                        'name': name,
                        'url': f"{base_url}/mobile/view.do?prodNo={no}"
                    })

            for a in soup.find_all('a', attrs={'prodno': True}):
                no = a.get('prodno', '')
                if not no or no in seen:
                    continue
                name = ''
                parent_li = a.find_parent('li')
                if parent_li:
                    tit = parent_li.select_one('.prd-tit')
                    if tit:
                        name = tit.get_text(strip=True)
                    if not name:
                        img = parent_li.select_one('img[alt]')
                        if img:
                            name = img.get('alt', '').strip()
                if not name:
                    tit = a.find(class_='prd-tit')
                    if tit:
                        name = tit.get_text(strip=True)
                if not name:
                    img = a.find('img')
                    if img:
                        name = img.get('alt', '').strip()
                if name and no:
                    seen.add(no)
                    products.append({
                        'name': name,
                        'url': f"{base_url}/mobile/view.do?prodNo={no}"
                    })

            if len(products) - count_before == 0 and page_num > 1:
                break

            next_btn = page.locator(f'a[pageno="{page_num + 1}"]:visible').first
            if not await self._safe_click(next_btn):
                break
            await page.wait_for_timeout(2000)
            page_num += 1

        return products

    async def _extract_board_links(self, page) -> list:
        base_url = self._get_base_url(page.url)
        all_links, seen = [], set()
        page_num = 1
        zero_count = 0

        while True:
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            count_before = len(all_links)

            for el in soup.find_all(style=lambda s: s and 'display' in s.lower() and 'none' in s.lower()):
                el.decompose()

            for a in soup.find_all('a', attrs={'data-apcturl': True}):
                url = a.get('data-apcturl', '').strip()
                if not url or url in seen:
                    continue
                title_el = a.select_one('.title')
                text = title_el.get_text(strip=True) if title_el else ''
                if not text:
                    img = a.find('img')
                    if img:
                        text = img.get('alt', '').strip()
                if not text:
                    text = self._extract_title_from_a(a)
                if text and len(text) >= 2:
                    seen.add(url)
                    all_links.append({'name': text, 'url': url})

            for a in soup.find_all('a', onclick=True):
                onclick = a.get('onclick', '')
                match = re.search(r'goDetPage\((\d+)\)', onclick)
                if not match:
                    continue
                seq = match.group(1)
                url = f"{base_url}/blog/detail.do?seq={seq}"
                if url in seen:
                    continue
                img = a.find('img')
                text = img.get('alt', '').strip() if img else ''
                if not text:
                    text = self._extract_title_from_a(a)
                if text and len(text) >= 2:
                    seen.add(url)
                    all_links.append({'name': text, 'url': url})

            if count_before == len(all_links):
                for sel in self.DECOMPOSE_SELECTORS:
                    for el in soup.select(sel):
                        el.decompose()
                for tag in soup(['script', 'style', 'noscript']):
                    tag.decompose()
                for link in self._extract_links_from_soup(soup, base_url, min_count=1):
                    if link['url'] not in seen:
                        seen.add(link['url'])
                        all_links.append(link)

            added = len(all_links) - count_before
            if added == 0:
                zero_count += 1
                if zero_count >= 2:
                    break
            else:
                zero_count = 0

            if page_num == 1 and len(all_links) < 3:
                break

            next_page = page_num + 1

            # pageno 속성으로 다음 페이지 버튼 탐색
            next_btn = page.locator(f'a[pageno="{next_page}"]:visible').first
            if await next_btn.count() == 0:
                next_btn = page.locator(
                    f'.paging a:text-is("{next_page}"):visible, .pagination a:text-is("{next_page}"):visible'
                ).first

            # arrow 버튼 (visible 한정 — 슬라이더 등 숨겨진 .next 요소 제외)
            if await next_btn.count() == 0:
                arrow_btn = page.locator(
                    'a.dir.next:visible, a.btn-next:visible, a.next-page:visible'
                ).first
                if await self._safe_click(arrow_btn):
                    await page.wait_for_timeout(2000)
                    next_btn = page.locator(f'a[pageno="{next_page}"]:visible').first
                    if await next_btn.count() == 0:
                        next_btn = page.locator(
                            f'.paging a:text-is("{next_page}"):visible, .pagination a:text-is("{next_page}"):visible'
                        ).first
                    await self._safe_click(next_btn)
                    await page.wait_for_timeout(2000)
                    page_num += 1
                    continue

            # 더보기 버튼
            if await next_btn.count() == 0:
                more_btn = page.locator(
                    '#btn_more:visible, .fjbBtnMore:visible, '
                    'button:has-text("더보기"):visible, .btn-more:visible, '
                    '.more-btn:visible, .load-more:visible'
                ).first
                if await self._safe_click(more_btn):
                    try:
                        more_text = await more_btn.inner_text(timeout=3000)
                        match = re.search(r'(\d+)/(\d+)', more_text)
                        if match and match.group(1) == match.group(2):
                            break
                    except Exception:
                        pass
                    await page.wait_for_timeout(2000)
                    page_num += 1
                    continue

            if await next_btn.count() == 0:
                break

            if await self._safe_click(next_btn):
                await page.wait_for_timeout(2000)
            else:
                break
            page_num += 1

        return all_links

    # ──────────────────────────────────────────────
    #  Pipeline & DB 저장
    # ──────────────────────────────────────────────

    async def run_full_extraction(self, save_to_db: bool = True, delay: float = 1.0) -> dict:
        """
        전체 파이프라인 실행:
        Step 1 (DOM 추출) → Step 2 (메뉴 파싱) → Step 3 (서브메뉴 추출) → DB 저장
        
        Returns:
            { menu_tree, flat_menus, saved_count, elapsed }
        """
        pipeline_start = datetime.now()
        logger.info("=" * 60)
        logger.info("🚀 GNB 메뉴 추출 전체 파이프라인 시작")
        logger.info("=" * 60)

        html = await self.extract_dom()
        menu_tree = self.parse_gnb_menu(html)
        menu_tree = await self.extract_submenus(menu_tree, delay=delay)

        flat_menus = self.flatten_menu_tree(menu_tree)
        logger.info(f"📊 평탄화 결과: {len(flat_menus)}개 URL")

        saved_count = 0
        if save_to_db and flat_menus:
            saved_count = await self.save_to_database(flat_menus)

        elapsed = str(datetime.now() - pipeline_start)
        logger.info(f"🎉 전체 파이프라인 완료 (소요시간: {elapsed})")

        return {
            "menu_tree": menu_tree,
            "flat_menus": flat_menus,
            "saved_count": saved_count,
            "elapsed": elapsed,
        }

    def flatten_menu_tree(self, menu_tree: list, parent_path: str = "") -> list:
        """메뉴 트리를 평탄화하여 DB 저장용 딕셔너리 리스트로 변환"""
        rows = []

        def _walk(nodes, path_prefix):
            for item in nodes:
                name = item.get('name', '')
                url = item.get('url', '')
                children = item.get('children', [])
                current_path = f"{path_prefix}^{name}" if path_prefix else name

                if url and url.startswith('http'):
                    rows.append({
                        'pc_url': url,
                        'menu_path': current_path,
                    })

                if children:
                    _walk(children, current_path)

        _walk(menu_tree, parent_path)
        return self._postprocess_flat_menus(rows)

    # ── 메뉴 경로 제외 패턴 (마지막 depth 기준) ──
    EXCLUDE_LAST_SEGMENT_PATTERNS = [
        r'^\[공지\]',         # [공지]로 시작
        r'^KT 로그인$',       # "KT 로그인" 자체가 title
        r'^["\u201c\u201d]',  # 쿼테이션(", \u201c, \u201d)으로 시작
        r'.+\s>\s.+\s>\s',    # breadcrumb 경로 (> 구분자 2개 이상)
    ]

    def _postprocess_flat_menus(self, flat_menus: list) -> list:
        """
        평탄화된 메뉴 리스트 후처리

        1) menu_path 정제:
           - 마지막 depth가 ' 상세'로 끝나면 제거
           - 마지막 depth에 '|KT' / '| KT' 패턴이 있으면 '|' 이전까지만 유지
        2) 불필요한 항목 제외:
           - 마지막 depth가 [공지], KT 로그인, 쿼테이션, breadcrumb 경로
        3) 같은 URL에 대해 depth가 더 깊은 중복 제거
           (단, 하위 항목이 존재하는 중간 카테고리 노드는 보존)
        """
        result = []

        for item in flat_menus:
            menu_path = item.get('menu_path', '')
            if not menu_path:
                continue

            parts = [p.strip() for p in menu_path.split('^')]
            last = parts[-1]

            # ── 제외 패턴 검사 (마지막 segment) ──
            if any(re.search(p, last) for p in self.EXCLUDE_LAST_SEGMENT_PATTERNS):
                continue

            # ── 정제: trailing ' 상세' 제거 ──
            if last.endswith(' 상세'):
                last = last[:-3].strip()

            # ── 정제: '|KT' / '| KT...' 패턴 제거 (공백 유무 모두 처리) ──
            if re.search(r'\|\s*KT', last):
                cleaned = re.split(r'\s*\|', last)[0].strip()
                if cleaned:
                    last = cleaned

            parts[-1] = last
            item['menu_path'] = '^'.join(parts)
            result.append(item)

        # ── 같은 URL 중복 제거 ──
        # 경로가 상위 항목의 직접 확장(prefix)인 경우만 제거.
        # 다른 카테고리 경로(5G^전체^X vs 5G^만18세이하^X)는 보존.
        all_paths = {item['menu_path'] for item in result}

        url_groups: Dict[str, list] = {}
        for item in result:
            url_groups.setdefault(item.get('pc_url', ''), []).append(item)

        deduped = []
        for url, items in url_groups.items():
            if len(items) == 1:
                deduped.append(items[0])
                continue

            items.sort(key=lambda x: x['menu_path'].count('^'))
            kept = []
            for item in items:
                path = item['menu_path']
                is_redundant_extension = any(
                    path.startswith(k['menu_path'] + '^') for k in kept
                )
                if is_redundant_extension:
                    has_descendants = any(
                        p.startswith(path + '^') for p in all_paths
                    )
                    if not has_descendants:
                        continue
                kept.append(item)
            deduped.extend(kept)

        removed = len(result) - len(deduped)
        if removed:
            logger.info(f"📊 메뉴 후처리: {removed}건 제거 ({len(result)} → {len(deduped)})")

        return deduped

    async def save_to_database(self, flat_menus: list) -> int:
        """추출된 메뉴를 menus 테이블에 저장 (전체 교체)"""
        logger.info(f"💾 menus 테이블 저장 시작 ({len(flat_menus)}개)")
        count = await menu_repository.replace_all(flat_menus)
        logger.info(f"✅ menus 테이블 저장 완료 ({count}개)")
        return count

    async def update_mobile_urls(self) -> int:
        """
        모바일 URL 후처리.
        기존 page_handlers/utils.py의 도메인별 변환 함수를 재사용하여
        PC URL → 모바일 URL 변환을 수행한다.
        이벤트 URL(event.kt.com)은 별도 매핑 테이블이 필요하므로 스킵.
        """
        from app.application.crawler.page_handlers.utils import (
            to_mshop_url,
            to_mproduct_url,
            to_mglobalroaming_url,
            to_gigagenie_murl,
        )

        # 도메인 → 변환 함수 디스패치 맵
        converters = {
            "shop.kt.com": to_mshop_url,
            "product.kt.com": to_mproduct_url,
            "globalroaming.kt.com": to_mglobalroaming_url,
            "m.globalroaming.kt.com": to_mglobalroaming_url,
            "gigagenie.kt.com": to_gigagenie_murl,
        }

        # 단순 도메인 치환 대상 (변환 함수가 없는 경우)
        simple_replace = {
            "www.kt.com": "m.kt.com",
            "inside.kt.com": "m.kt.com",
        }

        # 변환 스킵 도메인 (별도 매핑 필요)
        skip_domains = {"event.kt.com"}

        menus = await menu_repository.get_active_menus()
        url_map: Dict[int, str] = {}

        for menu in menus:
            if not menu.pc_url or menu.mobile_url:
                continue

            parsed = urlparse(menu.pc_url)
            host = parsed.netloc.split(":")[0]  # 포트 제거

            if host in skip_domains:
                continue

            # 1) 전용 변환 함수가 있는 도메인
            converter = None
            for domain, func in converters.items():
                if host == domain or host.endswith(f".{domain}"):
                    converter = func
                    break

            if converter:
                mobile_url = converter(menu.pc_url)
                if mobile_url:
                    url_map[menu.id] = mobile_url
                continue

            # 2) 단순 도메인 치환
            for pc_domain, mobile_domain in simple_replace.items():
                if host == pc_domain or host.endswith(f".{pc_domain}"):
                    mobile_url = menu.pc_url.replace(pc_domain, mobile_domain, 1)
                    url_map[menu.id] = mobile_url
                    break

        if url_map:
            count = await menu_repository.bulk_update_mobile_urls(url_map)
            logger.info(
                f"📱 모바일 URL 변환 완료: {count}개 변환, "
                f"{len(menus) - count}개 스킵 (이벤트/매핑없음)"
            )
            return count
        return 0


gnb_menu_service = GnbMenuService()
