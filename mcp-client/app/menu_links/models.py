"""Menu Links Pydantic models"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MenuLinkBase(BaseModel):
    """Base menu link model"""
    document_id: Optional[str] = Field(None, description="Document ID (optional)", max_length=50)
    menu_path: str = Field(..., description="Menu path (required)", min_length=1)
    pc_url: Optional[str] = Field(None, description="PC URL (optional)")
    mobile_url: Optional[str] = Field(None, description="Mobile URL (optional)")

class MenuLinkCreate(MenuLinkBase):
    """Menu link creation model"""
    created_by: Optional[str] = Field(None, description="Creator username")

class MenuLinkUpdate(BaseModel):
    """Menu link update model"""
    document_id: Optional[str] = Field(None, description="Document ID", max_length=50)
    menu_path: Optional[str] = Field(None, description="Menu path", min_length=1)
    pc_url: Optional[str] = Field(None, description="PC URL")
    mobile_url: Optional[str] = Field(None, description="Mobile URL")
    updated_by: Optional[str] = Field(None, description="Updater username")

class MenuLinkResponse(MenuLinkBase):
    """Menu link response model"""
    id: int = Field(..., description="Menu link ID")
    created_by: Optional[str] = Field(None, description="Creator username")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_by: Optional[str] = Field(None, description="Updater username")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True

class MenuLinksListResponse(BaseModel):
    """Menu links list response model"""
    items: List[MenuLinkResponse] = Field(..., description="List of menu links")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total pages")

class MenuLinkDeleteResponse(BaseModel):
    """Menu link deletion response model"""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Response message")
    deleted_id: Optional[int] = Field(None, description="ID of deleted menu link")

# Menu Manager Info Models
class MenuManagerInfoBase(BaseModel):
    """Base menu manager info model"""
    menu_id: int = Field(..., description="Menu link ID")
    team_name: str = Field(..., description="Team name", min_length=1)
    manager_names: str = Field(..., description="Manager names", min_length=1)

class MenuManagerInfoCreate(MenuManagerInfoBase):
    """Menu manager info creation model"""
    pass

class MenuManagerInfoUpdate(BaseModel):
    """Menu manager info update model"""
    team_name: Optional[str] = Field(None, description="Team name", min_length=1)
    manager_names: Optional[str] = Field(None, description="Manager names", min_length=1)

class MenuManagerInfoResponse(MenuManagerInfoBase):
    """Menu manager info response model"""
    id: int = Field(..., description="Menu manager info ID")
    created_by: Optional[str] = Field(None, description="Creator username")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_by: Optional[str] = Field(None, description="Updater username")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True

class MenuManagerInfoListResponse(BaseModel):
    """Menu manager info list response model"""
    items: List[MenuManagerInfoResponse] = Field(..., description="List of menu manager info")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total pages")

class MenuManagerInfoDeleteResponse(BaseModel):
    """Menu manager info deletion response model"""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Response message")
    deleted_id: Optional[int] = Field(None, description="ID of deleted menu manager info")

# Extended Menu Link Response with Manager Info
class MenuLinkWithManagerResponse(MenuLinkResponse):
    """Menu link response with manager info"""
    manager_info: Optional[MenuManagerInfoResponse] = Field(None, description="Associated manager info")
