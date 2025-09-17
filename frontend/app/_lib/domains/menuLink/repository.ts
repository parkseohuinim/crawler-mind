/**
 * MenuLink Repository - DB 접근 추상화
 */
import { MenuLink, MenuLinkCreate, MenuLinkUpdate, MenuLinksResponse } from './types';
import { authService } from '../../auth/auth-service';

// MCP Client에 직접 요청 (Next.js API 라우트 우회)
const API_BASE_URL = process.env.NEXT_PUBLIC_MCP_API_URL || 'http://localhost:8000';
const MENU_LINKS_ENDPOINT = `${API_BASE_URL}/api/menu-links`;

export const findAll = async (
  page: number = 1, 
  size: number = 10, 
  search?: string
): Promise<MenuLinksResponse> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });
  
  if (search) {
    params.append('search', search);
  }
  
  const response = await authService.authenticatedFetch(`${MENU_LINKS_ENDPOINT}?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu links');
  }
  
  return response.json();
};

export const findById = async (id: number): Promise<MenuLink> => {
  const response = await authService.authenticatedFetch(`${MENU_LINKS_ENDPOINT}/${id}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu link');
  }
  
  return response.json();
};

export const create = async (data: MenuLinkCreate): Promise<MenuLink> => {
  const response = await authService.authenticatedFetch(MENU_LINKS_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to create menu link');
  }
  
  return response.json();
};

export const update = async (id: number, data: MenuLinkUpdate): Promise<MenuLink> => {
  const response = await authService.authenticatedFetch(`${MENU_LINKS_ENDPOINT}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to update menu link');
  }
  
  return response.json();
};

export const remove = async (id: number): Promise<void> => {
  const response = await authService.authenticatedFetch(`${MENU_LINKS_ENDPOINT}/${id}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error('Failed to delete menu link');
  }
};

export const findAvailableForManager = async (
  page: number = 1, 
  size: number = 10, 
  search?: string
): Promise<MenuLinksResponse> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });
  
  if (search) {
    params.append('search', search);
  }
  
  const response = await authService.authenticatedFetch(`${MENU_LINKS_ENDPOINT}/available-for-manager?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch available menu links for manager');
  }
  
  return response.json();
};

export const findWithManagers = async (
  page: number = 1, 
  size: number = 10, 
  search?: string
): Promise<{ items: (MenuLink & { manager_info?: any })[], total: number, page: number, size: number, pages: number }> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });
  
  if (search) {
    params.append('search', search);
  }
  
  const response = await authService.authenticatedFetch(`${MENU_LINKS_ENDPOINT}/with-managers?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu links with managers');
  }
  
  return response.json();
};
