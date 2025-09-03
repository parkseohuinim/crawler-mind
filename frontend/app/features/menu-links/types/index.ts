/**
 * Menu Links Types
 */

export interface MenuLink {
  id: number;
  document_id?: string;
  menu_path: string;
  pc_url?: string;
  mobile_url?: string;
  created_by?: string;
  created_at?: string;
  updated_by?: string;
  updated_at?: string;
}

export interface MenuLinkCreate {
  document_id?: string;
  menu_path: string;
  pc_url?: string;
  mobile_url?: string;
  created_by?: string;
}

export interface MenuLinkUpdate {
  document_id?: string;
  menu_path?: string;
  pc_url?: string;
  mobile_url?: string;
  updated_by?: string;
}

// Menu Manager Info Types
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
  manager_names: string; // 여러 담당자명을 슬래시(/)로 구분하여 저장
}

export interface MenuManagerInfoUpdate {
  team_name?: string;
  manager_names?: string; // 여러 담당자명을 슬래시(/)로 구분하여 저장
}

// Extended Menu Link with Manager Info
export interface MenuLinkWithManager extends MenuLink {
  manager_info?: MenuManagerInfo;
}

export interface MenuLinksResponse {
  items: MenuLink[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface MenuLinkDeleteResponse {
  success: boolean;
  message: string;
  deleted_id?: number;
}
