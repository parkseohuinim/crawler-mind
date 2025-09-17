"""인증 관련 API 엔드포인트"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.infrastructure.auth.middleware import (
    get_current_user, 
    require_authentication,
    require_admin
)
from app.infrastructure.auth.jwt_service import auth_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

class PermissionsRequest(BaseModel):
    """권한 조회 요청"""
    roles: List[str]

class PermissionsResponse(BaseModel):
    """권한 조회 응답"""
    permissions: List[str]
    success: bool = True

class MenusResponse(BaseModel):
    """메뉴 조회 응답"""
    menus: List[Dict[str, Any]]
    success: bool = True

class UserInfoResponse(BaseModel):
    """사용자 정보 응답"""
    user: Dict[str, Any]
    success: bool = True

@router.post("/permissions", response_model=PermissionsResponse)
async def get_user_permissions(
    request: PermissionsRequest,
    current_user: Dict[str, Any] = Depends(require_authentication)
):
    """사용자 역할 기반 권한 목록 조회"""
    try:
        # 요청된 역할이 현재 사용자의 역할과 일치하는지 확인
        user_roles = current_user.get("roles", [])
        
        # 관리자가 아닌 경우 자신의 역할만 조회 가능
        if not auth_service.check_role(user_roles, ["admin"]):
            # 요청된 역할이 사용자 역할에 포함되어야 함
            if not all(role in user_roles for role in request.roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot query permissions for roles you don't have"
                )
        
        permissions = await auth_service.get_user_permissions(request.roles)
        
        return PermissionsResponse(permissions=permissions)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve permissions"
        )

@router.get("/menus", response_model=MenusResponse)
async def get_accessible_menus(
    current_user: Dict[str, Any] = Depends(require_authentication)
):
    """현재 사용자가 접근 가능한 메뉴 목록 조회"""
    try:
        user_roles = current_user.get("roles", [])
        menus = await auth_service.get_accessible_menus(user_roles)
        
        return MenusResponse(menus=menus)
        
    except Exception as e:
        logger.error(f"Error retrieving accessible menus: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve accessible menus"
        )

@router.get("/profile", response_model=UserInfoResponse)
async def get_user_profile(
    current_user: Dict[str, Any] = Depends(require_authentication)
):
    """현재 사용자 프로필 정보 조회"""
    try:
        # 민감한 정보 제외하고 반환
        safe_user_info = {
            "id": current_user.get("user_id"),
            "username": current_user.get("username"),
            "email": current_user.get("email"),
            "full_name": current_user.get("full_name"),
            "roles": current_user.get("roles", []),
            "permissions": current_user.get("permissions", []),
            "is_active": current_user.get("is_active", False)
        }
        
        return UserInfoResponse(user=safe_user_info)
        
    except Exception as e:
        logger.error(f"Error retrieving user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )

@router.get("/status")
async def auth_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """인증 상태 확인 (선택적 인증)"""
    if current_user:
        return {
            "authenticated": True,
            "user": {
                "username": current_user.get("username"),
                "roles": current_user.get("roles", [])
            }
        }
    else:
        return {
            "authenticated": False,
            "user": None
        }

@router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users():
    """관리자 전용 - 사용자 목록 조회"""
    # 실제 구현에서는 데이터베이스에서 사용자 목록 조회
    return {
        "message": "This would return user list",
        "note": "Admin only endpoint"
    }
