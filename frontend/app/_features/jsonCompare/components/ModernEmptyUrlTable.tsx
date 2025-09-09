'use client';

import React from 'react';
import { EmptyUrlItem } from '@/app/_lib/types';
import ModernTable from '@/app/_components/ui/ModernTable';

interface ModernEmptyUrlTableProps {
  emptyUrlItems: EmptyUrlItem[];
}

export default function ModernEmptyUrlTable({ emptyUrlItems }: ModernEmptyUrlTableProps) {
  const columns = [
    {
      key: 'url',
      label: 'URL',
      className: 'url-cell',
      render: (value: string) => value ? (
        <a href={value} target="_blank" rel="noopener noreferrer">
          {value.length > 50 ? `${value.substring(0, 50)}...` : value}
        </a>
      ) : <span className="no-data">-</span>
    },
    {
      key: 'title',
      label: '페이지 제목',
      className: 'title-cell',
      render: (value: string) => value || <span className="no-data">-</span>
    },
    {
      key: 'hierarchy',
      label: '페이지 경로',
      className: 'hierarchy-cell',
      render: (value: string) => value || <span className="no-data">-</span>
    },
    {
      key: 'manager_info',
      label: '담당자 정보',
      className: 'manager-cell',
      render: (value: any) => (
        <div className="manager-info">
          <div className="team-name">
            <strong>팀:</strong> {value?.team_name || '-'}
          </div>
          <div className="manager-names">
            <strong>담당자:</strong> {value?.manager_names || '-'}
          </div>
        </div>
      )
    }
  ];

  return (
    <ModernTable
      title="murl 필드가 비어있는 항목들의 담당자 정보"
      icon={
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      }
      data={emptyUrlItems}
      loading={false}
      columns={columns}
      emptyMessage="murl 필드가 비어있는 항목이 없습니다."
    />
  );
}
