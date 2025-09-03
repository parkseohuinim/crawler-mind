"""Combined menu schemas"""
from pydantic import BaseModel, Field
from typing import Optional
from .menu_link_schemas import MenuLinkResponse
from .menu_manager_schemas import MenuManagerInfoResponse

class MenuLinkWithManagerResponse(MenuLinkResponse):
    """Menu link response with manager info"""
    manager_info: Optional[MenuManagerInfoResponse] = Field(None, description="Associated manager info")
