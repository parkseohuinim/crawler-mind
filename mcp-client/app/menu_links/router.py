"""Menu Links API router"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_database_session
from .models import (
    MenuLinkCreate, MenuLinkUpdate, MenuLinkResponse, MenuLinksListResponse,
    MenuManagerInfoCreate, MenuManagerInfoUpdate, MenuManagerInfoResponse,
    MenuManagerInfoListResponse, MenuLinkWithManagerResponse
)
from .service import MenuLinkService, MenuManagerInfoService

router = APIRouter(prefix="/menu-links", tags=["menu-links"])

# Menu Links endpoints
@router.post("/", response_model=MenuLinkResponse)
async def create_menu_link(
    menu_link_data: MenuLinkCreate,
    db: AsyncSession = Depends(get_database_session)
):
    """Create a new menu link"""
    try:
        menu_link = await MenuLinkService.create_menu_link(db, menu_link_data)
        return MenuLinkResponse.model_validate(menu_link)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=MenuLinksListResponse)
async def get_menu_links(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=1000, description="Page size"),
    search: Optional[str] = Query(None, description="Search term for menu path"),
    db: AsyncSession = Depends(get_database_session)
):
    """Get paginated list of menu links with optional search"""
    skip = (page - 1) * size
    menu_links, total = await MenuLinkService.get_menu_links(db, skip, size, search)
    
    response_items = [MenuLinkResponse.model_validate(link) for link in menu_links]
    total_pages = (total + size - 1) // size
    
    return MenuLinksListResponse(
        items=response_items,
        total=total,
        page=page,
        size=size,
        pages=total_pages
    )

# Menu Manager Info endpoints - 정적 경로를 먼저 배치
@router.get("/manager-info-list", response_model=MenuManagerInfoListResponse)
async def get_manager_info_list(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search term for menu path"),
    db: AsyncSession = Depends(get_database_session)
):
    """Get paginated list of menu manager info"""
    skip = (page - 1) * size
    manager_infos, total = await MenuManagerInfoService.get_manager_info_list(db, skip, size, search)
    
    response_items = [MenuManagerInfoResponse.model_validate(info) for info in manager_infos]
    total_pages = (total + size - 1) // size
    
    return MenuManagerInfoListResponse(
        items=response_items,
        total=total,
        page=page,
        size=size,
        pages=total_pages
    )

@router.post("/manager-info-create", response_model=MenuManagerInfoResponse)
async def create_manager_info(
    manager_info_data: MenuManagerInfoCreate,
    db: AsyncSession = Depends(get_database_session)
):
    """Create a new menu manager info"""
    try:
        manager_info = await MenuManagerInfoService.create_manager_info(db, manager_info_data)
        return MenuManagerInfoResponse.model_validate(manager_info)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/manager-info-by-id/{manager_info_id}", response_model=MenuManagerInfoResponse)
async def get_manager_info(
    manager_info_id: int,
    db: AsyncSession = Depends(get_database_session)
):
    """Get a menu manager info by ID"""
    manager_info = await MenuManagerInfoService.get_manager_info(db, manager_info_id)
    if not manager_info:
        raise HTTPException(status_code=404, detail="Manager info not found")
    return MenuManagerInfoResponse.model_validate(manager_info)

@router.put("/manager-info-update/{manager_info_id}", response_model=MenuManagerInfoResponse)
async def update_manager_info(
    manager_info_id: int,
    manager_info_data: MenuManagerInfoUpdate,
    db: AsyncSession = Depends(get_database_session)
):
    """Update a menu manager info"""
    manager_info = await MenuManagerInfoService.update_manager_info(db, manager_info_id, manager_info_data)
    if not manager_info:
        raise HTTPException(status_code=404, detail="Manager info not found")
    return MenuManagerInfoResponse.model_validate(manager_info)

@router.delete("/manager-info-delete/{manager_info_id}")
async def delete_manager_info(
    manager_info_id: int,
    db: AsyncSession = Depends(get_database_session)
):
    """Delete a menu manager info"""
    success = await MenuManagerInfoService.delete_manager_info(db, manager_info_id)
    if not success:
        raise HTTPException(status_code=404, detail="Manager info not found")
    return {"message": "Manager info deleted successfully"}

# Extended endpoints
@router.get("/with-managers/", response_model=List[MenuLinkWithManagerResponse])
async def get_menu_links_with_managers(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search term for menu path"),
    db: AsyncSession = Depends(get_database_session)
):
    """Get menu links with manager info"""
    skip = (page - 1) * size
    menu_links, total = await MenuManagerInfoService.get_menu_links_with_managers(db, skip, size, search)
    
    response_items = []
    for link in menu_links:
        link_data = MenuLinkResponse.model_validate(link)
        manager_data = None
        if link.manager_info:
            manager_data = MenuManagerInfoResponse.model_validate(link.manager_info)
        
        response_items.append(MenuLinkWithManagerResponse(
            **link_data.model_dump(),
            manager_info=manager_data
        ))
    
    return response_items

@router.get("/available-for-manager", response_model=MenuLinksListResponse)
async def get_available_menu_links_for_manager(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=1000, description="Page size"),
    search: Optional[str] = Query(None, description="Search term for menu path"),
    db: AsyncSession = Depends(get_database_session)
):
    """Get menu links that don't have managers assigned (available for manager assignment)"""
    skip = (page - 1) * size
    menu_links, total = await MenuLinkService.get_available_menu_links_for_manager(db, skip, size, search)
    
    response_items = [MenuLinkResponse.model_validate(link) for link in menu_links]
    total_pages = (total + size - 1) // size
    
    return MenuLinksListResponse(
        items=response_items,
        total=total,
        page=page,
        size=size,
        pages=total_pages
    )

# 동적 경로는 마지막에 배치
@router.get("/{menu_link_id}", response_model=MenuLinkResponse)
async def get_menu_link(
    menu_link_id: int,
    db: AsyncSession = Depends(get_database_session)
):
    """Get a menu link by ID"""
    menu_link = await MenuLinkService.get_menu_link(db, menu_link_id)
    if not menu_link:
        raise HTTPException(status_code=404, detail="Menu link not found")
    return MenuLinkResponse.model_validate(menu_link)

@router.put("/{menu_link_id}", response_model=MenuLinkResponse)
async def update_menu_link(
    menu_link_id: int,
    menu_link_data: MenuLinkUpdate,
    db: AsyncSession = Depends(get_database_session)
):
    """Update a menu link"""
    menu_link = await MenuLinkService.update_menu_link(db, menu_link_id, menu_link_data)
    if not menu_link:
        raise HTTPException(status_code=404, detail="Menu link not found")
    return MenuLinkResponse.model_validate(menu_link)

@router.delete("/{menu_link_id}")
async def delete_menu_link(
    menu_link_id: int,
    db: AsyncSession = Depends(get_database_session)
):
    """Delete a menu link"""
    success = await MenuLinkService.delete_menu_link(db, menu_link_id)
    if not success:
        raise HTTPException(status_code=404, detail="Menu link not found")
    return {"message": "Menu link deleted successfully"}
