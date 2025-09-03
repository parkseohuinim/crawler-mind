/**
 * Menu Manager Info Service - 비즈니스 로직
 */
import * as repository from './repository';
import { MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate, MenuManagerInfoResponse } from './types';

export const getMenuManagerInfos = async (
  page: number = 1, 
  size: number = 10, 
  search?: string
): Promise<MenuManagerInfoResponse> => {
  return repository.findAll(page, size, search);
};

export const getMenuManagerInfoById = async (id: number): Promise<MenuManagerInfo> => {
  return repository.findById(id);
};

export const createMenuManagerInfo = async (data: MenuManagerInfoCreate): Promise<MenuManagerInfo> => {
  // 비즈니스 로직 검증
  if (!data.team_name.trim()) {
    throw new Error('팀명은 필수입니다.');
  }
  
  if (!data.manager_names.trim()) {
    throw new Error('담당자명은 필수입니다.');
  }
  
  if (!data.menu_id || data.menu_id <= 0) {
    throw new Error('메뉴 ID는 필수입니다.');
  }
  
  return repository.create(data);
};

export const updateMenuManagerInfo = async (id: number, data: MenuManagerInfoUpdate): Promise<MenuManagerInfo> => {
  // 비즈니스 로직 검증
  if (data.team_name !== undefined && !data.team_name.trim()) {
    throw new Error('팀명은 필수입니다.');
  }
  
  if (data.manager_names !== undefined && !data.manager_names.trim()) {
    throw new Error('담당자명은 필수입니다.');
  }
  
  return repository.update(id, data);
};

export const deleteMenuManagerInfo = async (id: number): Promise<void> => {
  return repository.remove(id);
};
