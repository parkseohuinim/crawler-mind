"""Menu Repository - GNB 메뉴 저장소"""
import logging
from datetime import datetime
from typing import List, Optional, Dict

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.base import get_database_session
from app.domains.gnb.entities.menu import Menu

logger = logging.getLogger(__name__)


class MenuRepository:
    """menus 테이블 저장소"""
    
    async def get_all(self) -> List[Menu]:
        """전체 메뉴 조회"""
        async for session in get_database_session():
            stmt = select(Menu).order_by(Menu.id.asc())
            result = await session.execute(stmt)
            return list(result.scalars().all())
        return []
    
    async def get_active_menus(self) -> List[Menu]:
        """활성 메뉴 조회"""
        async for session in get_database_session():
            stmt = (
                select(Menu)
                .where(Menu.is_active == True)
                .order_by(Menu.priority.desc(), Menu.id.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        return []
    
    async def get_by_id(self, menu_id: int) -> Optional[Menu]:
        """ID로 조회"""
        async for session in get_database_session():
            stmt = select(Menu).where(Menu.id == menu_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        return None
    
    async def get_by_pc_url(self, pc_url: str) -> Optional[Menu]:
        """PC URL로 조회"""
        async for session in get_database_session():
            stmt = select(Menu).where(Menu.pc_url == pc_url)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        return None
    
    async def replace_all(self, menus: List[Dict]) -> int:
        """
        전체 교체: 기존 데이터 삭제 후 새 데이터 일괄 삽입.
        일일 배치에서 전체 메뉴 트리를 갱신할 때 사용.
        
        Returns:
            삽입된 레코드 수
        """
        async for session in get_database_session():
            await session.execute(delete(Menu))
            
            menu_objects = []
            for item in menus:
                menu = Menu(
                    pc_url=item["pc_url"],
                    mobile_url=item.get("mobile_url"),
                    menu_path=item.get("menu_path"),
                    handler_name=item.get("handler_name"),
                    priority=item.get("priority", 0),
                    is_active=item.get("is_active", True),
                )
                menu_objects.append(menu)
            
            session.add_all(menu_objects)
            await session.commit()
            
            logger.info(f"✅ menus 테이블 갱신 완료: {len(menu_objects)}개 레코드")
            return len(menu_objects)
        return 0
    
    async def update_mobile_url(self, menu_id: int, mobile_url: str) -> None:
        """모바일 URL 업데이트 (후처리용)"""
        async for session in get_database_session():
            stmt = (
                update(Menu)
                .where(Menu.id == menu_id)
                .values(mobile_url=mobile_url, updated_at=datetime.now())
            )
            await session.execute(stmt)
            await session.commit()
            break
    
    async def bulk_update_mobile_urls(self, url_map: Dict[int, str]) -> int:
        """모바일 URL 일괄 업데이트"""
        updated = 0
        async for session in get_database_session():
            for menu_id, mobile_url in url_map.items():
                stmt = (
                    update(Menu)
                    .where(Menu.id == menu_id)
                    .values(mobile_url=mobile_url, updated_at=datetime.now())
                )
                await session.execute(stmt)
                updated += 1
            await session.commit()
            logger.info(f"✅ 모바일 URL {updated}개 업데이트 완료")
            return updated
        return 0
    
    async def get_stats(self) -> dict:
        """통계 조회"""
        async for session in get_database_session():
            total = (await session.execute(
                select(func.count(Menu.id))
            )).scalar() or 0
            
            active = (await session.execute(
                select(func.count(Menu.id)).where(Menu.is_active == True)
            )).scalar() or 0
            
            with_mobile = (await session.execute(
                select(func.count(Menu.id)).where(Menu.mobile_url.isnot(None))
            )).scalar() or 0
            
            return {
                "total": total,
                "active": active,
                "with_mobile_url": with_mobile,
                "without_mobile_url": total - with_mobile,
            }
        return {}


menu_repository = MenuRepository()
