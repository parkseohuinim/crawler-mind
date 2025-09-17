"""인증 미들웨어 - FastAPI 의존성 주입 기반"""
from typing import Optional, List, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.infrastructure.auth.jwt_service import auth_service
import logging

logger = logging.getLogger(__name__)

# HTTP Bearer 토큰 스키마
security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """현재 사용자 정보 조회 (선택적 인증)"""
    if not credentials:
        return None
    
    token = credentials.credentials
    user_info = await auth_service.authenticate_user(token)
    
    if user_info:
        # 사용자 권한 조회하여 추가
        permissions = await auth_service.get_user_permissions(user_info["roles"])
        user_info["permissions"] = permissions
        
        # 접근 가능한 메뉴 조회하여 추가
        accessible_menus = await auth_service.get_accessible_menus(user_info["roles"])
        user_info["accessible_menus"] = accessible_menus
        
        logger.info(f"User authenticated: {user_info['username']} with roles {user_info['roles']}")
    
    return user_info

async def require_authentication(
    user: Optional[Dict[str, Any]] = Depends(get_current_user)
) -> Dict[str, Any]:
    """인증 필수 - 로그인된 사용자만 접근 가능"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user

def require_roles(required_roles: List[str]):
    """특정 역할 필요 - 데코레이터 팩토리"""
    async def check_roles(
        user: Dict[str, Any] = Depends(require_authentication)
    ) -> Dict[str, Any]:
        user_roles = user.get("roles", [])
        
        if not auth_service.check_role(user_roles, required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {required_roles}. User roles: {user_roles}"
            )
        
        return user
    
    return check_roles

def require_permissions(required_permissions: List[str]):
    """특정 권한 필요 - 데코레이터 팩토리"""
    async def check_permissions(
        user: Dict[str, Any] = Depends(require_authentication)
    ) -> Dict[str, Any]:
        user_permissions = user.get("permissions", [])
        
        missing_permissions = [
            perm for perm in required_permissions 
            if not auth_service.check_permission(user_permissions, perm)
        ]
        
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {missing_permissions}"
            )
        
        return user
    
    return check_permissions

def require_permission(required_permission: str):
    """단일 권한 필요 - 편의 함수"""
    return require_permissions([required_permission])

# 관리자 권한 필수
require_admin = require_roles(["admin"])

# 사용자 권한 이상 필수 (user, manager, admin 등)
require_user = require_roles(["user", "manager", "admin"])

# 매니저 권한 이상 필수
require_manager = require_roles(["manager", "admin"])

# 크롤링 권한
require_crawler_read = require_permission("crawler:read")
require_crawler_write = require_permission("crawler:write")

# RAG 권한
require_rag_read = require_permission("rag:read")
require_rag_write = require_permission("rag:write")
require_rag_search = require_permission("rag:search")

# 메뉴 관리 권한
require_menu_links_read = require_permission("menu_links:read")
require_menu_links_write = require_permission("menu_links:write")

# JSON 비교 권한
require_json_read = require_permission("json:read")
require_json_write = require_permission("json:write")
