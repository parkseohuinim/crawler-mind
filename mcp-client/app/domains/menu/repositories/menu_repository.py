"""Menu repository interface and implementation"""
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple

from app.domains.menu.entities.menu_link import MenuLink
from app.domains.menu.entities.menu_manager import MenuManagerInfo
from app.shared.exceptions.base import MenuLinkNotFoundError, MenuManagerInfoNotFoundError


class IMenuRepository(ABC):
    """Menu repository interface"""
    
    @abstractmethod
    async def create_menu_link(self, menu_link: MenuLink) -> MenuLink:
        """Create a new menu link"""
        pass
    
    @abstractmethod
    async def get_menu_link_by_id(self, menu_id: int) -> Optional[MenuLink]:
        """Get menu link by ID"""
        pass
    
    @abstractmethod
    async def get_menu_links(self, skip: int = 0, limit: int = 100, search: str = None) -> Tuple[List[MenuLink], int]:
        """Get menu links with pagination and search"""
        pass
    
    @abstractmethod
    async def update_menu_link(self, menu_link: MenuLink) -> MenuLink:
        """Update menu link"""
        pass
    
    @abstractmethod
    async def delete_menu_link(self, menu_id: int) -> bool:
        """Delete menu link"""
        pass
    
    @abstractmethod
    async def create_manager_info(self, manager_info: MenuManagerInfo) -> MenuManagerInfo:
        """Create manager info"""
        pass
    
    @abstractmethod
    async def get_manager_info_by_id(self, manager_id: int) -> Optional[MenuManagerInfo]:
        """Get manager info by ID"""
        pass
    
    @abstractmethod
    async def get_manager_info_by_menu_id(self, menu_id: int) -> Optional[MenuManagerInfo]:
        """Get manager info by menu ID"""
        pass
    
    @abstractmethod
    async def update_manager_info(self, manager_info: MenuManagerInfo) -> MenuManagerInfo:
        """Update manager info"""
        pass
    
    @abstractmethod
    async def delete_manager_info(self, manager_id: int) -> bool:
        """Delete manager info"""
        pass


class MenuRepository(IMenuRepository):
    """Menu repository implementation"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_menu_link(self, menu_link: MenuLink) -> MenuLink:
        """Create a new menu link"""
        self.session.add(menu_link)
        await self.session.commit()
        await self.session.refresh(menu_link)
        return menu_link
    
    async def get_menu_link_by_id(self, menu_id: int) -> Optional[MenuLink]:
        """Get menu link by ID"""
        result = await self.session.execute(
            select(MenuLink).where(MenuLink.id == menu_id)
        )
        return result.scalar_one_or_none()
    
    async def get_menu_links(self, skip: int = 0, limit: int = 100, search: str = None) -> Tuple[List[MenuLink], int]:
        """Get menu links with pagination and search"""
        query = select(MenuLink)
        count_query = select(func.count(MenuLink.id))
        
        if search:
            search_filter = MenuLink.menu_path.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results with ordering
        query = query.order_by(MenuLink.created_at.desc(), MenuLink.updated_at.desc().nullslast())
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        menu_links = result.scalars().all()
        
        return menu_links, total
    
    async def get_available_menu_links_for_manager(self, skip: int = 0, limit: int = 100, search: str = None) -> Tuple[List[MenuLink], int]:
        """Get menu links that don't have managers assigned"""
        query = select(MenuLink).outerjoin(
            MenuManagerInfo, MenuLink.id == MenuManagerInfo.menu_id
        ).where(MenuManagerInfo.menu_id.is_(None))
        
        count_query = select(func.count(MenuLink.id)).outerjoin(
            MenuManagerInfo, MenuLink.id == MenuManagerInfo.menu_id
        ).where(MenuManagerInfo.menu_id.is_(None))
        
        if search:
            search_filter = MenuLink.menu_path.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results with ordering
        query = query.order_by(MenuLink.created_at.desc(), MenuLink.updated_at.desc().nullslast())
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        menu_links = result.scalars().all()
        
        return menu_links, total
    
    async def get_menu_links_with_managers(self, skip: int = 0, limit: int = 100, search: str = None) -> Tuple[List[MenuLink], int]:
        """Get menu links with manager info"""
        query = select(MenuLink).options(selectinload(MenuLink.manager_info))
        count_query = select(func.count(MenuLink.id))
        
        if search:
            search_filter = MenuLink.menu_path.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        menu_links = result.scalars().all()
        
        return menu_links, total
    
    async def update_menu_link(self, menu_link: MenuLink) -> MenuLink:
        """Update menu link"""
        await self.session.commit()
        await self.session.refresh(menu_link)
        return menu_link
    
    async def delete_menu_link(self, menu_id: int) -> bool:
        """Delete menu link"""
        menu_link = await self.get_menu_link_by_id(menu_id)
        if not menu_link:
            return False
        
        await self.session.delete(menu_link)
        await self.session.commit()
        return True
    
    async def create_manager_info(self, manager_info: MenuManagerInfo) -> MenuManagerInfo:
        """Create manager info"""
        self.session.add(manager_info)
        await self.session.commit()
        await self.session.refresh(manager_info)
        return manager_info
    
    async def get_manager_info_by_id(self, manager_id: int) -> Optional[MenuManagerInfo]:
        """Get manager info by ID"""
        result = await self.session.execute(
            select(MenuManagerInfo).where(MenuManagerInfo.id == manager_id)
        )
        return result.scalar_one_or_none()
    
    async def get_manager_info_by_menu_id(self, menu_id: int) -> Optional[MenuManagerInfo]:
        """Get manager info by menu ID"""
        result = await self.session.execute(
            select(MenuManagerInfo).where(MenuManagerInfo.menu_id == menu_id)
        )
        return result.scalar_one_or_none()
    
    async def get_manager_info_list(self, skip: int = 0, limit: int = 100, search: str = None) -> Tuple[List[MenuManagerInfo], int]:
        """Get manager info list with pagination and search by menu path"""
        query = select(MenuManagerInfo).join(MenuLink, MenuManagerInfo.menu_id == MenuLink.id)
        count_query = select(func.count(MenuManagerInfo.id)).join(MenuLink, MenuManagerInfo.menu_id == MenuLink.id)
        
        if search:
            search_filter = MenuLink.menu_path.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results with ordering
        query = query.order_by(MenuManagerInfo.created_at.desc(), MenuManagerInfo.updated_at.desc().nullslast())
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        manager_infos = result.scalars().all()
        
        return manager_infos, total
    
    async def update_manager_info(self, manager_info: MenuManagerInfo) -> MenuManagerInfo:
        """Update manager info"""
        await self.session.commit()
        await self.session.refresh(manager_info)
        return manager_info
    
    async def delete_manager_info(self, manager_id: int) -> bool:
        """Delete manager info"""
        manager_info = await self.get_manager_info_by_id(manager_id)
        if not manager_info:
            return False
        
        await self.session.delete(manager_info)
        await self.session.commit()
        return True
