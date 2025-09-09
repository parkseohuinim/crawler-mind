/**
 * Menu Manager Info Domain Types
 */

export interface MenuManagerInfo {
  id: number;
  menu_id: number;
  team_name: string;
  manager_names: string; // 여러 담당자명을 슬래시(/)로 구분하여 저장
  created_by?: string;
  created_at?: string;
  updated_by?: string;
  updated_at?: string;
}

export interface MenuManagerInfoCreate {
  menu_id: number;
  team_name: string;
  manager_names: string;
  created_by?: string;
}

export interface MenuManagerInfoUpdate {
  team_name?: string;
  manager_names?: string;
  updated_by?: string;
}

export interface MenuManagerInfoResponse {
  items: MenuManagerInfo[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface MenuManagerInfoDeleteResponse {
  success: boolean;
  message: string;
  deleted_id?: number;
}
