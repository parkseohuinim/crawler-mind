"""Menu Links service layer"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple
from .database import MenuLink, MenuManagerInfo
from .models import (
    MenuLinkCreate, MenuLinkUpdate, MenuLinkResponse, MenuLinksListResponse,
    MenuManagerInfoCreate, MenuManagerInfoUpdate, MenuManagerInfoResponse, 
    MenuManagerInfoListResponse, MenuLinkWithManagerResponse
)

class MenuLinkService:
    """Service for menu link operations"""
    
    @staticmethod
    async def create_menu_link(db: AsyncSession, menu_link_data: MenuLinkCreate) -> Optional[MenuLink]:
        """Create a new menu link"""
        try:
            db_menu_link = MenuLink(**menu_link_data.model_dump())
            db.add(db_menu_link)
            await db.commit()
            await db.refresh(db_menu_link)
            return db_menu_link
        except Exception as e:
            await db.rollback()
            raise e
    
    @staticmethod
    async def get_menu_link(db: AsyncSession, menu_link_id: int) -> Optional[MenuLink]:
        """Get a menu link by ID"""
        result = await db.execute(
            select(MenuLink).where(MenuLink.id == menu_link_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_menu_links(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ) -> Tuple[List[MenuLink], int]:
        """Get menu links with pagination and search"""
        query = select(MenuLink)
        count_query = select(func.count(MenuLink.id))
        
        if search:
            search_filter = MenuLink.menu_path.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results with ordering
        # 최신 등록순으로 정렬 (created_at DESC, updated_at DESC)
        # 검색 결과도 동일한 정렬 순서 유지
        query = query.order_by(MenuLink.created_at.desc(), MenuLink.updated_at.desc().nullslast())
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        menu_links = result.scalars().all()
        
        return menu_links, total

    @staticmethod
    async def get_available_menu_links_for_manager(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ) -> Tuple[List[MenuLink], int]:
        """Get menu links that don't have managers assigned (available for manager assignment)"""
        # LEFT JOIN으로 menu_links와 menu_manager_info를 조인
        # menu_manager_info.menu_id가 NULL인 경우만 선택 (담당자 미배정)
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
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results with ordering
        query = query.order_by(MenuLink.created_at.desc(), MenuLink.updated_at.desc().nullslast())
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        menu_links = result.scalars().all()
        
        return menu_links, total
    
    @staticmethod
    async def update_menu_link(
        db: AsyncSession, 
        menu_link_id: int, 
        menu_link_data: MenuLinkUpdate
    ) -> Optional[MenuLink]:
        """Update a menu link"""
        try:
            db_menu_link = await MenuLinkService.get_menu_link(db, menu_link_id)
            if not db_menu_link:
                return None
            
            update_data = menu_link_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_menu_link, field, value)
            
            await db.commit()
            await db.refresh(db_menu_link)
            return db_menu_link
        except Exception as e:
            await db.rollback()
            raise e
    
    @staticmethod
    async def delete_menu_link(db: AsyncSession, menu_link_id: int) -> bool:
        """Delete a menu link"""
        try:
            db_menu_link = await MenuLinkService.get_menu_link(db, menu_link_id)
            if not db_menu_link:
                return False
            
            await db.delete(db_menu_link)
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise e

class MenuManagerInfoService:
    """Service for menu manager info operations"""
    
    @staticmethod
    async def create_manager_info(
        db: AsyncSession, 
        manager_info_data: MenuManagerInfoCreate
    ) -> Optional[MenuManagerInfo]:
        """Create a new menu manager info"""
        try:
            # Check if menu link exists
            menu_link = await MenuLinkService.get_menu_link(db, manager_info_data.menu_id)
            if not menu_link:
                raise ValueError(f"Menu link with ID {manager_info_data.menu_id} not found")
            
            # Check if manager info already exists for this menu
            existing = await MenuManagerInfoService.get_manager_info_by_menu_id(db, manager_info_data.menu_id)
            if existing:
                raise ValueError(f"Manager info already exists for menu ID {manager_info_data.menu_id}")
            
            db_manager_info = MenuManagerInfo(**manager_info_data.model_dump())
            db.add(db_manager_info)
            await db.commit()
            await db.refresh(db_manager_info)
            return db_manager_info
        except Exception as e:
            await db.rollback()
            raise e
    
    @staticmethod
    async def get_manager_info(db: AsyncSession, manager_info_id: int) -> Optional[MenuManagerInfo]:
        """Get a menu manager info by ID"""
        result = await db.execute(
            select(MenuManagerInfo).where(MenuManagerInfo.id == manager_info_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_manager_info_by_menu_id(db: AsyncSession, menu_id: int) -> Optional[MenuManagerInfo]:
        """Get manager info by menu ID"""
        result = await db.execute(
            select(MenuManagerInfo).where(MenuManagerInfo.menu_id == menu_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_manager_info_list(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ) -> Tuple[List[MenuManagerInfo], int]:
        """Get menu manager info list with pagination and search by menu path"""
        # JOIN MenuLink to search by menu_path
        query = select(MenuManagerInfo).join(MenuLink, MenuManagerInfo.menu_id == MenuLink.id)
        count_query = select(func.count(MenuManagerInfo.id)).join(MenuLink, MenuManagerInfo.menu_id == MenuLink.id)
        
        if search:
            search_filter = MenuLink.menu_path.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results with ordering
        # 최신 등록순으로 정렬 (created_at DESC, updated_at DESC)
        # 검색 결과도 동일한 정렬 순서 유지
        query = query.order_by(MenuManagerInfo.created_at.desc(), MenuManagerInfo.updated_at.desc().nullslast())
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        manager_infos = result.scalars().all()
        
        return manager_infos, total
    
    @staticmethod
    async def update_manager_info(
        db: AsyncSession, 
        manager_info_id: int, 
        manager_info_data: MenuManagerInfoUpdate
    ) -> Optional[MenuManagerInfo]:
        """Update a menu manager info"""
        try:
            db_manager_info = await MenuManagerInfoService.get_manager_info(db, manager_info_id)
            if not db_manager_info:
                return None
            
            update_data = manager_info_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_manager_info, field, value)
            
            await db.commit()
            await db.refresh(db_manager_info)
            return db_manager_info
        except Exception as e:
            await db.rollback()
            raise e
    
    @staticmethod
    async def delete_manager_info(db: AsyncSession, manager_info_id: int) -> bool:
        """Delete a menu manager info"""
        try:
            db_manager_info = await MenuManagerInfoService.get_manager_info(db, manager_info_id)
            if not db_manager_info:
                return False
            
            await db.delete(db_manager_info)
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise e
    
    @staticmethod
    async def get_menu_links_with_managers(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ) -> Tuple[List[MenuLink], int]:
        """Get menu links with manager info"""
        query = select(MenuLink).options(selectinload(MenuLink.manager_info))
        count_query = select(func.count(MenuLink.id))
        
        if search:
            search_filter = MenuLink.menu_path.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        menu_links = result.scalars().all()
        
        return menu_links, total
