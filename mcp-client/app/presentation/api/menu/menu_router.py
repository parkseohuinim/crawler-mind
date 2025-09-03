"""Menu API router - FastAPI endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.shared.database.base import get_database_session
from app.application.menu.menu_service import MenuApplicationService
from app.domains.menu.schemas.menu_link_schemas import (
    MenuLinkCreate, MenuLinkUpdate, MenuLinkResponse, MenuLinksListResponse, MenuLinkDeleteResponse
)
from app.domains.menu.schemas.menu_manager_schemas import (
    MenuManagerInfoCreate, MenuManagerInfoUpdate, MenuManagerInfoResponse, 
    MenuManagerInfoListResponse, MenuManagerInfoDeleteResponse
)
from app.domains.menu.schemas.combined_schemas import MenuLinkWithManagerResponse
from app.shared.exceptions.base import (
    MenuLinkNotFoundError, MenuManagerInfoNotFoundError, 
    BusinessRuleViolationError, DuplicateMenuManagerError
)

router = APIRouter(prefix="/menu-links", tags=["menu-links"])

async def get_menu_service(db: AsyncSession = Depends(get_database_session)) -> MenuApplicationService:
    """Dependency to get menu application service"""
    return MenuApplicationService(db)

# Menu Links Endpoints
@router.post("/", response_model=MenuLinkResponse, status_code=201)
async def create_menu_link(
    menu_link: MenuLinkCreate,
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Create a new menu link"""
    try:
        return await service.create_menu_link(menu_link)
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{menu_link_id}", response_model=MenuLinkResponse)
async def get_menu_link(
    menu_link_id: int = Path(..., description="Menu link ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get a menu link by ID"""
    try:
        menu_link = await service.get_menu_link(menu_link_id)
        if not menu_link:
            raise HTTPException(status_code=404, detail="Menu link not found")
        return menu_link
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/", response_model=MenuLinksListResponse)
async def get_menu_links(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=1000, description="Page size"),
    search: Optional[str] = Query(None, description="Search term"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get menu links with pagination and search"""
    try:
        skip = (page - 1) * size
        return await service.get_menu_links(skip, size, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/available-for-manager/", response_model=MenuLinksListResponse)
async def get_available_menu_links_for_manager(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=1000, description="Page size"),
    search: Optional[str] = Query(None, description="Search term"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get menu links available for manager assignment"""
    try:
        skip = (page - 1) * size
        return await service.get_available_menu_links_for_manager(skip, size, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{menu_link_id}", response_model=MenuLinkResponse)
async def update_menu_link(
    menu_link_id: int = Path(..., description="Menu link ID"),
    menu_link_update: MenuLinkUpdate = ...,
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Update a menu link"""
    try:
        updated_menu_link = await service.update_menu_link(menu_link_id, menu_link_update)
        if not updated_menu_link:
            raise HTTPException(status_code=404, detail="Menu link not found")
        return updated_menu_link
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{menu_link_id}", response_model=MenuLinkDeleteResponse)
async def delete_menu_link(
    menu_link_id: int = Path(..., description="Menu link ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Delete a menu link"""
    try:
        return await service.delete_menu_link(menu_link_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Manager Info Endpoints
@router.post("/manager-info-create/", response_model=MenuManagerInfoResponse, status_code=201)
async def create_manager_info(
    manager_info: MenuManagerInfoCreate,
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Create menu manager info"""
    try:
        return await service.create_manager_info(manager_info)
    except (BusinessRuleViolationError, DuplicateMenuManagerError, MenuLinkNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/manager-info/{manager_info_id}", response_model=MenuManagerInfoResponse)
async def get_manager_info(
    manager_info_id: int = Path(..., description="Manager info ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get manager info by ID"""
    try:
        manager_info = await service.get_manager_info(manager_info_id)
        if not manager_info:
            raise HTTPException(status_code=404, detail="Manager info not found")
        return manager_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/manager-info/", response_model=MenuManagerInfoListResponse)
async def get_manager_info_list(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=1000, description="Page size"),
    search: Optional[str] = Query(None, description="Search term"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get manager info list with pagination"""
    try:
        skip = (page - 1) * size
        return await service.get_manager_info_list(skip, size, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/manager-info-update/{manager_info_id}", response_model=MenuManagerInfoResponse)
async def update_manager_info(
    manager_info_id: int = Path(..., description="Manager info ID"),
    manager_info_update: MenuManagerInfoUpdate = ...,
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Update manager info"""
    try:
        updated_manager_info = await service.update_manager_info(manager_info_id, manager_info_update)
        if not updated_manager_info:
            raise HTTPException(status_code=404, detail="Manager info not found")
        return updated_manager_info
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/manager-info-delete/{manager_info_id}", response_model=MenuManagerInfoDeleteResponse)
async def delete_manager_info(
    manager_info_id: int = Path(..., description="Manager info ID"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Delete manager info"""
    try:
        return await service.delete_manager_info(manager_info_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Combined Endpoints
@router.get("/with-managers/", response_model=List[MenuLinkWithManagerResponse])
async def get_menu_links_with_managers(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=1000, description="Page size"),
    search: Optional[str] = Query(None, description="Search term"),
    service: MenuApplicationService = Depends(get_menu_service)
):
    """Get menu links with their manager info"""
    try:
        skip = (page - 1) * size
        return await service.get_menu_links_with_managers(skip, size, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
