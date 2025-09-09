/**
 * Menu Manager Info Repository - DB 접근 추상화
 */
import { MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate, MenuManagerInfoResponse } from './types';

const API_BASE_URL = '/api/menu-manager-info';

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
  
  const response = await fetch(`${API_BASE_URL}?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu manager info');
  }
  
  return response.json();
};

export const findById = async (id: number): Promise<MenuManagerInfo> => {
  const response = await fetch(`${API_BASE_URL}/${id}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch menu manager info');
  }
  
  return response.json();
};

export const create = async (data: MenuManagerInfoCreate): Promise<MenuManagerInfo> => {
  const response = await fetch(API_BASE_URL, {
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
  const response = await fetch(`${API_BASE_URL}/${id}`, {
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
  const response = await fetch(`${API_BASE_URL}/${id}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error('Failed to delete menu manager info');
  }
};
