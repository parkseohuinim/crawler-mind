/**
 * Menu Links API functions
 */
import { MenuLink, MenuLinkCreate, MenuLinkUpdate, MenuLinksResponse, MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate } from '../types';

const API_BASE_URL = '/api/menu-links';

// Menu Links API
export const createMenuLink = async (data: MenuLinkCreate): Promise<MenuLink> => {
  const response = await fetch(API_BASE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to create menu link');
  }
  
  return response.json();
};

export const getMenuLinks = async (page: number = 1, size: number = 10, search?: string): Promise<MenuLinksResponse> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });
  
  if (search) {
    params.append('search', search);
  }
  
  const response = await fetch(`${API_BASE_URL}?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu links');
  }
  
  return response.json();
};

export const getMenuLink = async (id: number): Promise<MenuLink> => {
  const response = await fetch(`${API_BASE_URL}/${id}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu link');
  }
  
  return response.json();
};

export const updateMenuLink = async (id: number, data: MenuLinkUpdate): Promise<MenuLink> => {
  const response = await fetch(`${API_BASE_URL}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to update menu link');
  }
  
  return response.json();
};

export const deleteMenuLink = async (id: number): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/${id}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error('Failed to delete menu link');
  }
};

// Menu Manager Info API
export const createManagerInfo = async (data: MenuManagerInfoCreate): Promise<MenuManagerInfo> => {
  const response = await fetch(`${API_BASE_URL}/manager-info-create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to create manager info');
  }
  
  return response.json();
};

export const getManagerInfo = async (id: number): Promise<MenuManagerInfo> => {
  const response = await fetch(`${API_BASE_URL}/manager-info-by-id/${id}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch manager info');
  }
  
  return response.json();
};

export const getManagerInfoList = async (page: number = 1, size: number = 10): Promise<{ items: MenuManagerInfo[], total: number, page: number, size: number, pages: number }> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });
  
  const response = await fetch(`${API_BASE_URL}/manager-info-list?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch manager info list');
  }
  
  return response.json();
};

export const updateManagerInfo = async (id: number, data: MenuManagerInfoUpdate): Promise<MenuManagerInfo> => {
  const response = await fetch(`${API_BASE_URL}/manager-info-update/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to update manager info');
  }
  
  return response.json();
};

export const deleteManagerInfo = async (id: number): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/manager-info-delete/${id}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error('Failed to delete manager info');
  }
};

// Extended API
export const getMenuLinksWithManagers = async (page: number = 1, size: number = 10, search?: string): Promise<{ items: (MenuLink & { manager_info?: MenuManagerInfo })[], total: number, page: number, size: number, pages: number }> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });
  
  if (search) {
    params.append('search', search);
  }
  
  const response = await fetch(`${API_BASE_URL}/with-managers?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu links with managers');
  }
  
  return response.json();
};

// 새로운 API: 담당자 배정 가능한 메뉴만 가져오기
export const getAvailableMenuLinksForManager = async (page: number = 1, size: number = 10, search?: string): Promise<{ items: MenuLink[], total: number, page: number, size: number, pages: number }> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });
  
  if (search) {
    params.append('search', search);
  }
  
  const response = await fetch(`${API_BASE_URL}/available-for-manager?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch available menu links for manager');
  }
  
  return response.json();
};
