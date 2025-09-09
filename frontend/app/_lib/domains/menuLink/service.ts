/**
 * MenuLink Service - 비즈니스 로직
 */
import * as repository from './repository';
import { MenuLink, MenuLinkCreate, MenuLinkUpdate, MenuLinksResponse } from './types';

export const getMenuLinks = async (
  page: number = 1, 
  size: number = 10, 
  search?: string
): Promise<MenuLinksResponse> => {
  return repository.findAll(page, size, search);
};

export const getMenuLinkById = async (id: number): Promise<MenuLink> => {
  return repository.findById(id);
};

export const createMenuLink = async (data: MenuLinkCreate): Promise<MenuLink> => {
  // 비즈니스 로직 검증
  if (!data.menu_path.trim()) {
    throw new Error('메뉴 경로는 필수입니다.');
  }
  
  return repository.create(data);
};

export const updateMenuLink = async (id: number, data: MenuLinkUpdate): Promise<MenuLink> => {
  // 비즈니스 로직 검증
  if (data.menu_path !== undefined && !data.menu_path.trim()) {
    throw new Error('메뉴 경로는 필수입니다.');
  }
  
  return repository.update(id, data);
};

export const deleteMenuLink = async (id: number): Promise<void> => {
  return repository.remove(id);
};

export const getAvailableMenuLinksForManager = async (
  page: number = 1, 
  size: number = 10, 
  search?: string
): Promise<MenuLinksResponse> => {
  return repository.findAvailableForManager(page, size, search);
};

export const getMenuLinksWithManagers = async (
  page: number = 1, 
  size: number = 10, 
  search?: string
) => {
  return repository.findWithManagers(page, size, search);
};
