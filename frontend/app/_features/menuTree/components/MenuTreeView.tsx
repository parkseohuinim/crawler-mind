'use client';

import React from 'react';
import MenuTreeChart from './MenuTreeChart';

interface MenuLink {
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

interface MenuTreeViewProps {
  menuLinks: MenuLink[];
}

export default function MenuTreeView({ menuLinks }: MenuTreeViewProps) {
  return <MenuTreeChart menuLinks={menuLinks} />;
}
