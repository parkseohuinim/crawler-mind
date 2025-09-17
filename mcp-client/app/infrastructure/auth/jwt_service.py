"""JWT 토큰 검증 서비스 - Aegis Shield Server와 통신"""
try:
    import jwt
except ImportError:
    print("PyJWT not installed. Please run: pip install PyJWT cryptography")
    raise

import logging
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger(__name__)

class JWTService:
    """JWT 토큰 검증 및 사용자 정보 관리"""
    
    def __init__(self):
        self.aegis_server_url = settings.aegis_server_url
        
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Aegis Shield Server에서 토큰 검증"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.aegis_server_url}/api/auth/validate",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("valid", False):
                        return data
                        
                logger.warning(f"Token validation failed: {response.status_code}")
                return None
                
        except httpx.TimeoutException:
            logger.error("Token validation timeout")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None
    
    def extract_token_from_header(self, authorization_header: Optional[str]) -> Optional[str]:
        """Authorization 헤더에서 Bearer 토큰 추출"""
        if not authorization_header:
            return None
            
        if not authorization_header.startswith("Bearer "):
            return None
            
        return authorization_header[7:]  # "Bearer " 제거
    
    def decode_token_locally(self, token: str) -> Optional[Dict[str, Any]]:
        """로컬에서 JWT 토큰 디코드 (검증 없이 정보만 추출)"""
        try:
            # 서명 검증 없이 디코드 (정보 추출용)
            decoded = jwt.decode(token, options={"verify_signature": False})
            return decoded
        except Exception as e:
            logger.error(f"Token decode error: {e}")
            return None

class AuthService:
    """인증 및 권한 관리 서비스"""
    
    def __init__(self):
        self.jwt_service = JWTService()
        
    async def authenticate_user(self, token: str) -> Optional[Dict[str, Any]]:
        """사용자 인증 및 정보 반환"""
        validation_result = await self.jwt_service.validate_token(token)
        
        if not validation_result:
            return None
            
        user_info = validation_result.get("user")
        if not user_info:
            return None
            
        return {
            "user_id": user_info.get("id"),
            "username": user_info.get("username"),
            "email": user_info.get("email"),
            "full_name": user_info.get("fullName"),
            "roles": user_info.get("roles", []),
            "is_active": user_info.get("isActive", False)
        }
    
    async def get_user_permissions(self, roles: List[str]) -> List[str]:
        """역할 기반 사용자 권한 조회"""
        try:
            from app.shared.database.connection import get_db_connection
            
            # crawler_mind 데이터베이스에서 권한 조회
            async with get_db_connection() as conn:
                query = """
                SELECT DISTINCT p.name
                FROM auth_system.role_permissions rp
                JOIN auth_system.permissions p ON rp.permission_id = p.id
                WHERE rp.role_name = ANY($1) AND p.is_active = true
                ORDER BY p.name
                """
                
                rows = await conn.fetch(query, roles)
                permissions = [row['name'] for row in rows]
                
                logger.info(f"Retrieved {len(permissions)} permissions for roles {roles}")
                return permissions
                
        except Exception as e:
            logger.error(f"Error retrieving permissions: {e}")
            return []
    
    async def get_accessible_menus(self, roles: List[str]) -> List[Dict[str, Any]]:
        """역할 기반 접근 가능한 메뉴 조회"""
        try:
            from app.shared.database.connection import get_db_connection
            
            async with get_db_connection() as conn:
                query = """
                SELECT DISTINCT
                    m.id,
                    m.parent_id,
                    m.name,
                    m.path,
                    m.icon,
                    m.order_index,
                    m.description
                FROM auth_system.accessible_menus_by_role_view amv
                JOIN auth_system.menus m ON amv.menu_id = m.id
                WHERE amv.role_name = ANY($1)
                ORDER BY m.order_index, m.name
                """
                
                rows = await conn.fetch(query, roles)
                menus = [dict(row) for row in rows]
                
                logger.info(f"Retrieved {len(menus)} accessible menus for roles {roles}")
                return menus
                
        except Exception as e:
            logger.error(f"Error retrieving accessible menus: {e}")
            return []
    
    def check_permission(self, user_permissions: List[str], required_permission: str) -> bool:
        """권한 확인"""
        return required_permission in user_permissions
    
    def check_role(self, user_roles: List[str], required_roles: List[str]) -> bool:
        """역할 확인 (하나라도 일치하면 true)"""
        return any(role in user_roles for role in required_roles)

# 전역 인스턴스
auth_service = AuthService()
