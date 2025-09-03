"""Menu domain service - contains business logic"""
from typing import Optional
from app.domains.menu.entities.menu_link import MenuLink
from app.domains.menu.entities.menu_manager import MenuManagerInfo
from app.domains.menu.repositories.menu_repository import IMenuRepository
from app.shared.exceptions.base import DuplicateMenuManagerError, MenuLinkNotFoundError


class MenuDomainService:
    """Domain service for menu business logic"""
    
    def __init__(self, repository: IMenuRepository):
        self.repository = repository
    
    async def can_assign_manager_to_menu(self, menu_id: int) -> bool:
        """Check if a manager can be assigned to a menu"""
        # Business rule: One menu can have only one manager
        existing_manager = await self.repository.get_manager_info_by_menu_id(menu_id)
        return existing_manager is None
    
    async def assign_manager_to_menu(
        self, 
        menu_id: int, 
        team_name: str, 
        manager_names: str, 
        created_by: str = None
    ) -> MenuManagerInfo:
        """Assign a manager to a menu (business logic)"""
        # Verify menu exists
        menu_link = await self.repository.get_menu_link_by_id(menu_id)
        if not menu_link:
            raise MenuLinkNotFoundError(f"Menu link with ID {menu_id} not found")
        
        # Check business rule: no duplicate managers
        if not await self.can_assign_manager_to_menu(menu_id):
            raise DuplicateMenuManagerError(f"Manager already assigned to menu ID {menu_id}")
        
        # Create manager info
        manager_info = MenuManagerInfo(
            menu_id=menu_id,
            team_name=team_name,
            manager_names=manager_names,
            created_by=created_by
        )
        
        return await self.repository.create_manager_info(manager_info)
    
    def validate_menu_path(self, menu_path: str) -> bool:
        """Validate menu path format"""
        # Business rule: menu path should not be empty and follow certain format
        if not menu_path or not menu_path.strip():
            return False
        
        # Additional business rules can be added here
        # For example: path format validation, forbidden characters, etc.
        return True
    
    def validate_manager_names(self, manager_names: str) -> bool:
        """Validate manager names format"""
        if not manager_names or not manager_names.strip():
            return False
        
        # Additional validation rules can be added
        return True
    
    def validate_team_name(self, team_name: str) -> bool:
        """Validate team name format"""
        if not team_name or not team_name.strip():
            return False
        
        # Additional validation rules can be added
        return True
