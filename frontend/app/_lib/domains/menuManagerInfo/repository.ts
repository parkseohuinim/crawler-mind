/**
 * Menu Manager Info Repository - DB 접근 추상화
 */
import { MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate, MenuManagerInfoResponse } from './types';
import { authService } from '../../auth/auth-service';

// MCP Client에 직접 요청 (Next.js API 라우트 우회)
const API_BASE_URL = process.env.NEXT_PUBLIC_MCP_API_URL || 'http://localhost:8000';
const MENU_MANAGER_INFO_ENDPOINT = `${API_BASE_URL}/api/menu-links/manager-info-list`;

export const findAll = async (
  page: number = 1, 
  size: number = 10, 
  search?: string
): Promise<MenuManagerInfoResponse> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });
  
  if (search) {
    params.append('search', search);
  }
  
  const response = await authService.authenticatedFetch(`${MENU_MANAGER_INFO_ENDPOINT}?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu manager info');
  }
  
  return response.json();
};

export const findById = async (id: number): Promise<MenuManagerInfo> => {
  // Note: MCP Client에 개별 ID 조회 엔드포인트가 있는지 확인 필요
  const response = await authService.authenticatedFetch(`${API_BASE_URL}/api/menu-manager-info/${id}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu manager info');
  }
  
  return response.json();
};

export const create = async (data: MenuManagerInfoCreate): Promise<MenuManagerInfo> => {
  const response = await authService.authenticatedFetch(`${API_BASE_URL}/api/menu-manager-info`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to create menu manager info');
  }
  
  return response.json();
};

export const update = async (id: number, data: MenuManagerInfoUpdate): Promise<MenuManagerInfo> => {
  const response = await authService.authenticatedFetch(`${API_BASE_URL}/api/menu-manager-info/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to update menu manager info');
  }
  
  return response.json();
};

export const remove = async (id: number): Promise<void> => {
  const response = await authService.authenticatedFetch(`${API_BASE_URL}/api/menu-manager-info/${id}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error('Failed to delete menu manager info');
  }
};
