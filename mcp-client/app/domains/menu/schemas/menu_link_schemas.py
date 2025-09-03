"""Menu Link domain schemas"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MenuLinkBase(BaseModel):
    """Base menu link schema"""
    document_id: Optional[str] = Field(None, description="Document ID (optional)", max_length=50)
    menu_path: str = Field(..., description="Menu path (required)", min_length=1)
    pc_url: Optional[str] = Field(None, description="PC URL (optional)")
    mobile_url: Optional[str] = Field(None, description="Mobile URL (optional)")

class MenuLinkCreate(MenuLinkBase):
    """Menu link creation schema"""
    created_by: Optional[str] = Field(None, description="Creator username")

class MenuLinkUpdate(BaseModel):
    """Menu link update schema"""
    document_id: Optional[str] = Field(None, description="Document ID", max_length=50)
    menu_path: Optional[str] = Field(None, description="Menu path", min_length=1)
    pc_url: Optional[str] = Field(None, description="PC URL")
    mobile_url: Optional[str] = Field(None, description="Mobile URL")
    updated_by: Optional[str] = Field(None, description="Updater username")

class MenuLinkResponse(MenuLinkBase):
    """Menu link response schema"""
    id: int = Field(..., description="Menu link ID")
    created_by: Optional[str] = Field(None, description="Creator username")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_by: Optional[str] = Field(None, description="Updater username")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True

class MenuLinksListResponse(BaseModel):
    """Menu links list response schema"""
    items: List[MenuLinkResponse] = Field(..., description="List of menu links")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total pages")

class MenuLinkDeleteResponse(BaseModel):
    """Menu link deletion response schema"""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Response message")
    deleted_id: Optional[int] = Field(None, description="ID of deleted menu link")
