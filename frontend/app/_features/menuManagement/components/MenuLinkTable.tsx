'use client';

import React from 'react';
import { MenuLink } from '@/app/_lib/domains/menuLink';
import ModernTable from '@/app/_components/ui/ModernTable';

interface MenuLinkTableProps {
  menuLinks: MenuLink[];
  loading: boolean;
  onEdit: (menuLink: MenuLink) => void;
  onDelete: (menuLink: MenuLink) => void;
}

export default function MenuLinkTable({ menuLinks, loading, onEdit, onDelete }: MenuLinkTableProps) {
  const columns = [
    {
      key: 'id',
      label: 'ID',
      className: 'id-cell',
      render: (value: number) => value
    },
    {
      key: 'document_id',
      label: '문서 ID',
      render: (value: string) => value || <span className="no-data">-</span>
    },
    {
      key: 'menu_path',
      label: '메뉴 경로',
      className: 'menu-path-cell',
      render: (value: string) => value.split('^').join(' > ')
    },
    {
      key: 'pc_url',
      label: 'PC URL',
      className: 'url-cell',
      render: (value: string) => value ? (
        <a href={value} target="_blank" rel="noopener noreferrer">
          {value.length > 50 ? `${value.substring(0, 50)}...` : value}
        </a>
      ) : <span className="no-data">-</span>
    },
    {
      key: 'mobile_url',
      label: '모바일 URL',
      className: 'url-cell',
      render: (value: string) => value ? (
        <a href={value} target="_blank" rel="noopener noreferrer">
          {value.length > 50 ? `${value.substring(0, 50)}...` : value}
        </a>
      ) : <span className="no-data">-</span>
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
      title="메뉴 링크 목록"
      icon={
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
        </svg>
      }
      data={menuLinks}
      loading={loading}
      columns={columns}
      onEdit={onEdit}
      onDelete={onDelete}
      emptyMessage="메뉴 링크가 없습니다."
    />
  );
}
