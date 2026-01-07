"""Menu application service - orchestrates use cases"""
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.menu.entities.menu_link import MenuLink
from app.domains.menu.entities.menu_manager import MenuManagerInfo
from app.domains.menu.repositories.menu_repository import MenuRepository
from app.domains.menu.services.menu_domain_service import MenuDomainService
from app.domains.menu.schemas.menu_link_schemas import (
    MenuLinkCreate, MenuLinkUpdate, MenuLinkResponse, MenuLinksListResponse, MenuLinkDeleteResponse
)
from app.domains.menu.schemas.menu_manager_schemas import (
    MenuManagerInfoCreate, MenuManagerInfoUpdate, MenuManagerInfoResponse, 
    MenuManagerInfoListResponse, MenuManagerInfoDeleteResponse
)
from app.domains.menu.schemas.combined_schemas import MenuLinkWithManagerResponse
from app.shared.exceptions.base import (
    MenuLinkNotFoundError, MenuManagerInfoNotFoundError, BusinessRuleViolationError
)


class MenuApplicationService:
    """Application service for menu use cases"""
    
    def __init__(self, db_session: AsyncSession):
        self.repository = MenuRepository(db_session)
        self.domain_service = MenuDomainService(self.repository)
        self.db_session = db_session
    
    # Menu Link Use Cases
    async def create_menu_link(self, menu_link_data: MenuLinkCreate) -> MenuLinkResponse:
        """Create a new menu link"""
        try:
            # Validate business rules
            if not self.domain_service.validate_menu_path(menu_link_data.menu_path):
                raise BusinessRuleViolationError("Invalid menu path format")
            
            # Create entity
            menu_link = MenuLink(**menu_link_data.model_dump())
            
            # Save through repository
            created_menu_link = await self.repository.create_menu_link(menu_link)
            
            return MenuLinkResponse.model_validate(created_menu_link)
            
        except Exception as e:
            await self.db_session.rollback()
            raise e
    
    async def get_menu_link(self, menu_link_id: int) -> Optional[MenuLinkResponse]:
        """Get a menu link by ID"""
        menu_link = await self.repository.get_menu_link_by_id(menu_link_id)
        if not menu_link:
            return None
        
        return MenuLinkResponse.model_validate(menu_link)
    
    async def get_menu_links(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: Optional[str] = None
    ) -> MenuLinksListResponse:
        """Get menu links with pagination and search"""
        menu_links, total = await self.repository.get_menu_links(skip, limit, search)
        
        items = [MenuLinkResponse.model_validate(link) for link in menu_links]
        pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return MenuLinksListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            size=limit,
            pages=pages
        )
    
    async def get_available_menu_links_for_manager(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: Optional[str] = None
    ) -> MenuLinksListResponse:
        """Get menu links available for manager assignment"""
        menu_links, total = await self.repository.get_available_menu_links_for_manager(skip, limit, search)
        
        items = [MenuLinkResponse.model_validate(link) for link in menu_links]
        pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return MenuLinksListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            size=limit,
            pages=pages
        )
    
    async def update_menu_link(
        self, 
        menu_link_id: int, 
        menu_link_data: MenuLinkUpdate
    ) -> Optional[MenuLinkResponse]:
        """Update a menu link"""
        try:
            menu_link = await self.repository.get_menu_link_by_id(menu_link_id)
            if not menu_link:
                return None
            
            # Validate business rules if menu_path is being updated
            update_data = menu_link_data.model_dump(exclude_unset=True)
            if 'menu_path' in update_data:
                if not self.domain_service.validate_menu_path(update_data['menu_path']):
                    raise BusinessRuleViolationError("Invalid menu path format")
            
            # Update entity
            for field, value in update_data.items():
                setattr(menu_link, field, value)
            
            updated_menu_link = await self.repository.update_menu_link(menu_link)
            return MenuLinkResponse.model_validate(updated_menu_link)
            
        except Exception as e:
            await self.db_session.rollback()
            raise e
    
    async def delete_menu_link(self, menu_link_id: int) -> MenuLinkDeleteResponse:
        """Delete a menu link"""
        try:
            success = await self.repository.delete_menu_link(menu_link_id)
            
            if success:
                return MenuLinkDeleteResponse(
                    success=True,
                    message="Menu link deleted successfully",
                    deleted_id=menu_link_id
                )
            else:
                return MenuLinkDeleteResponse(
                    success=False,
                    message="Menu link not found",
                    deleted_id=None
                )
                
        except Exception as e:
            await self.db_session.rollback()
            raise e
    
    # Manager Info Use Cases
    async def create_manager_info(self, manager_info_data: MenuManagerInfoCreate) -> MenuManagerInfoResponse:
        """Create menu manager info"""
        try:
            # Validate business rules
            if not self.domain_service.validate_team_name(manager_info_data.team_name):
                raise BusinessRuleViolationError("Invalid team name format")
            
            if not self.domain_service.validate_manager_names(manager_info_data.manager_names):
                raise BusinessRuleViolationError("Invalid manager names format")
            
            # Use domain service for business logic
            manager_info = await self.domain_service.assign_manager_to_menu(
                menu_id=manager_info_data.menu_id,
                team_name=manager_info_data.team_name,
                manager_names=manager_info_data.manager_names,
                created_by=getattr(manager_info_data, 'created_by', None)
            )
            
            return MenuManagerInfoResponse.model_validate(manager_info)
            
        except Exception as e:
            await self.db_session.rollback()
            raise e
    
    async def get_manager_info(self, manager_info_id: int) -> Optional[MenuManagerInfoResponse]:
        """Get manager info by ID"""
        manager_info = await self.repository.get_manager_info_by_id(manager_info_id)
        if not manager_info:
            return None
        
        return MenuManagerInfoResponse.model_validate(manager_info)
    
    async def get_manager_info_by_menu_id(self, menu_id: int) -> Optional[MenuManagerInfoResponse]:
        """Get manager info by menu ID"""
        manager_info = await self.repository.get_manager_info_by_menu_id(menu_id)
        if not manager_info:
            return None
        
        return MenuManagerInfoResponse.model_validate(manager_info)
    
    async def get_manager_info_list(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: Optional[str] = None
    ) -> MenuManagerInfoListResponse:
        """Get manager info list with pagination"""
        manager_infos, total = await self.repository.get_manager_info_list(skip, limit, search)
        
        # menu_path를 포함하여 응답 생성
        items = []
        for info in manager_infos:
            response = MenuManagerInfoResponse.model_validate(info)
            # menu_link relationship에서 menu_path 가져오기
            if info.menu_link:
                response.menu_path = info.menu_link.menu_path
            items.append(response)
        
        pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return MenuManagerInfoListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            size=limit,
            pages=pages
        )
    
    async def update_manager_info(
        self, 
        manager_info_id: int, 
        manager_info_data: MenuManagerInfoUpdate
    ) -> Optional[MenuManagerInfoResponse]:
        """Update manager info"""
        try:
            manager_info = await self.repository.get_manager_info_by_id(manager_info_id)
            if not manager_info:
                return None
            
            # Validate business rules
            update_data = manager_info_data.model_dump(exclude_unset=True)
            if 'team_name' in update_data:
                if not self.domain_service.validate_team_name(update_data['team_name']):
                    raise BusinessRuleViolationError("Invalid team name format")
            
            if 'manager_names' in update_data:
                if not self.domain_service.validate_manager_names(update_data['manager_names']):
                    raise BusinessRuleViolationError("Invalid manager names format")
            
            # Update entity
            manager_info.update_team_info(
                team_name=update_data.get('team_name'),
                manager_names=update_data.get('manager_names'),
                updated_by=update_data.get('updated_by')
            )
            
            updated_manager_info = await self.repository.update_manager_info(manager_info)
            return MenuManagerInfoResponse.model_validate(updated_manager_info)
            
        except Exception as e:
            await self.db_session.rollback()
            raise e
    
    async def delete_manager_info(self, manager_info_id: int) -> MenuManagerInfoDeleteResponse:
        """Delete manager info"""
        try:
            success = await self.repository.delete_manager_info(manager_info_id)
            
            if success:
                return MenuManagerInfoDeleteResponse(
                    success=True,
                    message="Manager info deleted successfully",
                    deleted_id=manager_info_id
                )
            else:
                return MenuManagerInfoDeleteResponse(
                    success=False,
                    message="Manager info not found",
                    deleted_id=None
                )
                
        except Exception as e:
            await self.db_session.rollback()
            raise e
    
    # Combined Use Cases
    async def get_menu_links_with_managers(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: Optional[str] = None
    ) -> List[MenuLinkWithManagerResponse]:
        """Get menu links with their manager info"""
        menu_links, total = await self.repository.get_menu_links_with_managers(skip, limit, search)
        
        result = []
        for menu_link in menu_links:
            menu_response = MenuLinkResponse.model_validate(menu_link)
            manager_response = None
            
            if menu_link.manager_info:
                manager_response = MenuManagerInfoResponse.model_validate(menu_link.manager_info)
            
            combined_response = MenuLinkWithManagerResponse(
                **menu_response.model_dump(),
                manager_info=manager_response
            )
            result.append(combined_response)
        
        return result
