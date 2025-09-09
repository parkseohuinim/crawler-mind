'use client';

import React from 'react';

interface ModernTableProps {
  title: string;
  icon: React.ReactNode;
  data: any[];
  loading: boolean;
  columns: {
    key: string;
    label: string;
    render?: (value: any, row: any) => React.ReactNode;
    className?: string;
  }[];
  onEdit?: (item: any) => void;
  onDelete?: (item: any) => void;
  emptyMessage?: string;
}

export default function ModernTable({
  title,
  icon,
  data,
  loading,
  columns,
  onEdit,
  onDelete,
  emptyMessage = '데이터가 없습니다.'
}: ModernTableProps) {
  if (loading) {
    return (
      <div className="modern-table-container">
        <div className="modern-table-header">
          <div className="modern-table-title">
            <div className="modern-table-icon">
              {icon}
            </div>
            {title}
          </div>
        </div>
        <div className="modern-loading-container">
          <div className="modern-spinner"></div>
          <p className="modern-loading-text">데이터를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="modern-table-container">
        <div className="modern-table-header">
          <div className="modern-table-title">
            <div className="modern-table-icon">
              {icon}
            </div>
            {title}
          </div>
          <div className="modern-table-count">
            {data.length}개 항목
          </div>
        </div>
        <div className="modern-empty-state">
          <div className="modern-empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="9" y1="9" x2="15" y2="15"></line>
              <line x1="15" y1="9" x2="9" y2="15"></line>
            </svg>
          </div>
          <p className="modern-empty-text">{emptyMessage}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="modern-table-container">
      <div className="modern-table-header">
        <div className="modern-table-title">
          <div className="modern-table-icon">
            {icon}
          </div>
          {title}
        </div>
        <div className="modern-table-count">
          {data.length}개 항목
        </div>
      </div>
      
      <div className="modern-table-wrapper">
        <table className="modern-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>
                  {column.label}
                </th>
              ))}
              {(onEdit || onDelete) && (
                <th>작업</th>
              )}
            </tr>
          </thead>
          <tbody>
            {data.map((row, index) => (
              <tr key={row.id || index}>
                {columns.map((column) => (
                  <td key={column.key} className={column.className}>
                    {column.render 
                      ? column.render(row[column.key], row)
                      : row[column.key] || <span className="no-data">-</span>
                    }
                  </td>
                ))}
                {(onEdit || onDelete) && (
                  <td className="actions-cell">
                    {onEdit && (
                      <button
                        onClick={() => onEdit(row)}
                        className="action-button edit-button"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                          <path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                        수정
                      </button>
                    )}
                    {onDelete && (
                      <button
                        onClick={() => onDelete(row)}
                        className="action-button delete-button"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M3 6h18"></path>
                          <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                          <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                        </svg>
                        삭제
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
