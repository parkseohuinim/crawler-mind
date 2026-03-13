"""InputUrl Repository - 크롤링 대상 URL 저장소"""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.base import get_database_session
from app.domains.crawler.entities.input_url import InputUrl

logger = logging.getLogger(__name__)


class InputUrlRepository:
    """InputUrl 테이블 저장소"""
    
    async def get_active_urls(
        self, 
        force_recrawl: bool = False,
        limit: Optional[int] = None
    ) -> List[InputUrl]:
        """
        활성화된 크롤링 대상 URL 조회
        
        Args:
            force_recrawl: True면 이미 성공한 URL도 포함
            limit: 최대 조회 개수
            
        Returns:
            InputUrl 목록 (priority DESC 정렬)
        """
        async for session in get_database_session():
            stmt = select(InputUrl).where(InputUrl.is_active == True)
            
            if not force_recrawl:
                # 성공한 URL 제외 (last_status != 'success' 또는 NULL)
                stmt = stmt.where(
                    (InputUrl.last_status != 'success') | 
                    (InputUrl.last_status.is_(None))
                )
            
            stmt = stmt.order_by(InputUrl.priority.desc(), InputUrl.id.asc())
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await session.execute(stmt)
            urls = result.scalars().all()
            logger.info(f"📋 활성 URL {len(urls)}개 조회됨 (force_recrawl={force_recrawl})")
            return list(urls)
        
        return []
    
    async def get_all_urls(self) -> List[InputUrl]:
        """모든 URL 조회"""
        async for session in get_database_session():
            stmt = select(InputUrl).order_by(InputUrl.priority.desc(), InputUrl.id.asc())
            result = await session.execute(stmt)
            return list(result.scalars().all())
        return []
    
    async def get_by_id(self, url_id: int) -> Optional[InputUrl]:
        """ID로 조회"""
        async for session in get_database_session():
            stmt = select(InputUrl).where(InputUrl.id == url_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        return None
    
    async def get_by_ids(self, url_ids: List[int]) -> List[InputUrl]:
        """ID 목록으로 조회 (테스트용)"""
        if not url_ids:
            return []
        async for session in get_database_session():
            stmt = (
                select(InputUrl)
                .where(InputUrl.id.in_(url_ids))
                .order_by(InputUrl.id.asc())
            )
            result = await session.execute(stmt)
            urls = list(result.scalars().all())
            logger.info(f"📋 ID로 URL {len(urls)}개 조회됨 (요청: {len(url_ids)}개)")
            return urls
        return []
    
    async def get_by_pc_url(self, pc_url: str) -> Optional[InputUrl]:
        """PC URL로 조회"""
        async for session in get_database_session():
            stmt = select(InputUrl).where(InputUrl.pc_url == pc_url)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        return None
    
    async def update_crawl_status(
        self,
        url_id: int,
        status: str,
        error: Optional[str] = None,
        handler_name: Optional[str] = None
    ) -> None:
        """
        크롤링 상태 업데이트
        
        Args:
            url_id: InputUrl ID
            status: 'success', 'failed', 'skipped'
            error: 에러 메시지 (실패 시)
            handler_name: 사용된 핸들러 이름 (선택)
        """
        async for session in get_database_session():
            update_values = {
                "last_crawled_at": datetime.now(),
                "last_status": status,
                "last_error": error,
                "updated_at": datetime.now()
            }
            
            # handler_name이 제공된 경우에만 업데이트
            if handler_name is not None:
                update_values["handler_name"] = handler_name
            
            stmt = (
                update(InputUrl)
                .where(InputUrl.id == url_id)
                .values(**update_values)
            )
            await session.execute(stmt)
            await session.commit()
            logger.debug(f"✅ URL {url_id} 상태 업데이트: {status}" + (f", handler: {handler_name}" if handler_name else ""))
            break
    
    async def deactivate_url(self, url_id: int, reason: str = "") -> None:
        """
        URL 비활성화 (is_active = False)
        페이지가 더 이상 유효하지 않을 때 호출
        """
        async for session in get_database_session():
            stmt = (
                update(InputUrl)
                .where(InputUrl.id == url_id)
                .values(
                    is_active=False,
                    last_status="deactivated",
                    last_error=reason[:500] if reason else None,
                    last_crawled_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
            await session.execute(stmt)
            await session.commit()
            logger.info(f"🚫 URL {url_id} 비활성화: {reason[:100]}")
            break

    async def get_stats(self) -> dict:
        """통계 조회"""
        async for session in get_database_session():
            # 전체 개수
            total_stmt = select(func.count(InputUrl.id))
            total_result = await session.execute(total_stmt)
            total = total_result.scalar() or 0
            
            # 활성 개수
            active_stmt = select(func.count(InputUrl.id)).where(InputUrl.is_active == True)
            active_result = await session.execute(active_stmt)
            active = active_result.scalar() or 0
            
            # 성공 개수
            success_stmt = select(func.count(InputUrl.id)).where(InputUrl.last_status == 'success')
            success_result = await session.execute(success_stmt)
            success = success_result.scalar() or 0
            
            # 실패 개수
            failed_stmt = select(func.count(InputUrl.id)).where(InputUrl.last_status == 'failed')
            failed_result = await session.execute(failed_stmt)
            failed = failed_result.scalar() or 0
            
            return {
                "total": total,
                "active": active,
                "success": success,
                "failed": failed,
                "pending": active - success - failed
            }
        
        return {}


# 싱글톤 인스턴스
input_url_repository = InputUrlRepository()


