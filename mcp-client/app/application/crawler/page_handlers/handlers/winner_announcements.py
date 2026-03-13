"""
당첨자발표 관련 핸들러

KT Shop 당첨자발표 페이지 처리
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright
from markdownify import markdownify as md

from ..handler_registry import register_page_handler
from ..utils import to_mshop_url, smart_goto, launch_chromium

logger = logging.getLogger(__name__)


async def handle_event_winner_announcements(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    KT Shop 당첨자발표 페이지 처리
    
    Args:
        url: 당첨자발표 목록 페이지 URL
        fclient: 스크래핑 클라이언트
        menu: 메뉴 정보
    
    Returns:
        dict: 추출된 데이터
    """
    try:
        logger.info(f"🎯 Winner Announcement page processing started: {url}")
        
        # Playwright를 사용하여 페이지 접근
        async with async_playwright() as p:
            browser = await launch_chromium(p)
            context = await browser.new_context()
            page = await context.new_page()
            
            # 페이지 로드
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # iframe 로딩 대기
            try:
                await page.wait_for_selector('iframe[src*="planDispEvent.do"]', timeout=15000)
                logger.info("✅ Winner announcement iframe loaded")
            except Exception as e:
                logger.warning(f"⚠️ iframe not loaded: {e}")
            await page.wait_for_timeout(2000)
            
            # iframe으로 이동
            iframe = await page.query_selector('iframe[src*="planDispEvent.do"]')
            if not iframe:
                raise Exception("Winner Announcement iframe not found")
            
            frame = await iframe.content_frame()
            if not frame:
                raise Exception("Cannot access iframe content")
            
            # 1단계: 페이지네이션을 통해 모든 게시물 링크 수집
            all_posts: List[Dict[str, Any]] = []
            current_page = 1
            max_pages = 20  # 안전장치
            no_new_posts_count = 0  # 연속으로 새 게시물이 없는 횟수
            
            while current_page <= max_pages:
                logger.info(f"📄 Processing page {current_page}...")
                
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
                    logger.info(f"📄 No posts found on page {current_page}. Collection complete.")
                    break
                
                # 중복 게시물 체크 (같은 uniqueId가 이미 있는지 확인)
                new_posts = []
                existing_ids = {post['uniqueId'] for post in all_posts}
                
                for post in page_posts:
                    if post['uniqueId'] not in existing_ids:
                        new_posts.append(post)
                
                if not new_posts:
                    no_new_posts_count += 1
                    logger.info(f"📄 Page {current_page}: No new posts ({no_new_posts_count}/3)")
                    
                    if no_new_posts_count >= 3:  # 연속 3번 새 게시물이 없으면 종료
                        logger.info("📄 No new posts consecutively, collection complete.")
                        break
                else:
                    no_new_posts_count = 0  # 새 게시물이 있으면 카운터 리셋
                
                all_posts.extend(new_posts)
                logger.info(f"📄 Page {current_page}: {len(new_posts)} new posts collected (Total {len(all_posts)} posts)")
                
                # 다음 페이지로 이동 시도 (allListClick 함수 사용)
                try:
                    next_page = current_page + 1
                    await frame.evaluate(f"allListClick({next_page})")
                    await page.wait_for_timeout(2000)
                    current_page = next_page
                except Exception as e:
                    logger.info(f"📄 Page navigation failed: {e}. Collection complete.")
                    break
            
            await browser.close()
            
            logger.info(f"✅ Total {len(all_posts)} posts collected")
            
            # 2단계: 병렬로 상세 정보 추출
            menus: List[Dict[str, Any]] = []
            datas: List[Dict[str, Any]] = []
            
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
            
            async def extract_post_detail(post: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    try:
                        logger.info(f"🔍 Extracting details: {post['eventName']}")
                        
                        # 새로운 브라우저 인스턴스로 상세 페이지 접근
                        async with async_playwright() as p:
                            browser = await launch_chromium(p)
                            context = await browser.new_context()
                            detail_page = await context.new_page()
                            
                            # 목록 페이지로 이동
                            await smart_goto(detail_page, "https://shop.kt.com/plan/planDispEvent.do", timeout=30000)
                            
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
                        logger.error(f"❌ Detail extraction failed ({post['eventName']}): {e}")
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
            
            logger.info(f"✅ Winner Announcement processing completed: {success_count}/{len(all_posts)} details extracted")
            
            return {
                'menus': menus,
                'datas': datas,
                'total_processed': len(datas),
                'status': 'completed',
                'special_processed': True,
                'playwright_processed': True
            }
            
    except Exception as e:
        logger.error(f"❌ Error during Winner Announcement processing: {e}")
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
