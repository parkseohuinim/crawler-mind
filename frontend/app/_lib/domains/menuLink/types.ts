/**
 * MenuLink Domain Types
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
