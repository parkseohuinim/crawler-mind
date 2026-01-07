"""Menu Manager Info domain schemas"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MenuManagerInfoBase(BaseModel):
    """Base menu manager info schema"""
    menu_id: int = Field(..., description="Menu link ID")
    team_name: str = Field(..., description="Team name", min_length=1)
    manager_names: str = Field(..., description="Manager names", min_length=1)

class MenuManagerInfoCreate(MenuManagerInfoBase):
    """Menu manager info creation schema"""
    created_by: Optional[str] = Field(None, description="Creator username")

class MenuManagerInfoUpdate(BaseModel):
    """Menu manager info update schema"""
    team_name: Optional[str] = Field(None, description="Team name", min_length=1)
    manager_names: Optional[str] = Field(None, description="Manager names", min_length=1)
    updated_by: Optional[str] = Field(None, description="Updater username")

class MenuManagerInfoResponse(MenuManagerInfoBase):
    """Menu manager info response schema"""
    id: int = Field(..., description="Menu manager info ID")
    menu_path: Optional[str] = Field(None, description="Menu path from related MenuLink")
    created_by: Optional[str] = Field(None, description="Creator username")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_by: Optional[str] = Field(None, description="Updater username")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True

class MenuManagerInfoListResponse(BaseModel):
    """Menu manager info list response schema"""
    items: List[MenuManagerInfoResponse] = Field(..., description="List of menu manager info")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total pages")

class MenuManagerInfoDeleteResponse(BaseModel):
    """Menu manager info deletion response schema"""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Response message")
    deleted_id: Optional[int] = Field(None, description="ID of deleted menu manager info")
