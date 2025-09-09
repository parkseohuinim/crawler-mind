'use client';

import React from 'react';
import { MenuManagerInfo } from '@/app/_lib/domains/menuManagerInfo';
import { MenuLink } from '@/app/_lib/domains/menuLink';
import ModernTable from '@/app/_components/ui/ModernTable';

interface MenuManagerInfoTableProps {
  menuManagerInfos: MenuManagerInfo[];
  menuLinks: MenuLink[];
  loading: boolean;
  onEdit: (menuManagerInfo: MenuManagerInfo) => void;
  onDelete: (menuManagerInfo: MenuManagerInfo) => void;
}

export default function MenuManagerInfoTable({
  menuManagerInfos,
  menuLinks,
  loading,
  onEdit,
  onDelete
}: MenuManagerInfoTableProps) {
  // 안전한 배열 체크
  const safeMenuManagerInfos = Array.isArray(menuManagerInfos) ? menuManagerInfos : [];
  const safeMenuLinks = Array.isArray(menuLinks) ? menuLinks : [];

  const getMenuPath = (menuId: number) => {
    const menu = safeMenuLinks.find(m => m.id === menuId);
    return menu ? menu.menu_path.split('^').join(' > ') : '알 수 없음';
  };

  const columns = [
    {
      key: 'id',
      label: 'ID',
      className: 'id-cell',
      render: (value: number) => value
    },
    {
      key: 'menu_id',
      label: '메뉴 경로',
      className: 'menu-path-cell',
      render: (value: number) => getMenuPath(value)
    },
    {
      key: 'team_name',
      label: '팀명',
      render: (value: string) => value
    },
    {
      key: 'manager_names',
      label: '담당자명',
      render: (value: string) => value
    },
    {
      key: 'created_by',
      label: '생성자',
      className: 'user-cell',
      render: (value: string) => value || <span className="no-data">-</span>
    },
    {
      key: 'created_at',
      label: '생성일',
      className: 'date-cell',
      render: (value: string) => value ? new Date(value).toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      }) : '-'
    },
    {
      key: 'updated_by',
      label: '수정자',
      className: 'user-cell',
      render: (value: string) => value || <span className="no-data">-</span>
    },
    {
      key: 'updated_at',
      label: '수정일',
      className: 'date-cell',
      render: (value: string) => value ? new Date(value).toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      }) : '-'
    }
  ];

  return (
    <ModernTable
      title="메뉴 매니저 목록"
      icon={
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      }
      data={safeMenuManagerInfos}
      loading={loading}
      columns={columns}
      onEdit={onEdit}
      onDelete={onDelete}
      emptyMessage="메뉴 매니저 정보가 없습니다."
    />
  );
}
