'use client';

import React from 'react';
import { MenuLink } from '@/app/domains/menuLink';

interface MenuLinkTableProps {
  menuLinks: MenuLink[];
  loading: boolean;
  onEdit: (menuLink: MenuLink) => void;
  onDelete: (menuLink: MenuLink) => void;
}

export default function MenuLinkTable({ menuLinks, loading, onEdit, onDelete }: MenuLinkTableProps) {
  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner-large"></div>
        <span className="loading-text">메뉴 링크를 불러오는 중...</span>
      </div>
    );
  }

  if (menuLinks.length === 0) {
    return (
      <div className="empty-state">
        <p>메뉴 링크가 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="menu-links-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>문서 ID</th>
            <th>메뉴 경로</th>
            <th>PC URL</th>
            <th>모바일 URL</th>
            <th>생성자</th>
            <th>생성일</th>
            <th>수정자</th>
            <th>수정일</th>
            <th>작업</th>
          </tr>
        </thead>
        <tbody>
          {menuLinks.map((menuLink) => (
            <tr key={menuLink.id}>
              <td>{menuLink.id}</td>
              <td className="document-id">
                {menuLink.document_id || (
                  <span className="no-document-id">-</span>
                )}
              </td>
              <td className="menu-path">
                {menuLink.menu_path.split('^').join(' > ')}
              </td>
              <td className="url-cell">
                {menuLink.pc_url ? (
                  <a href={menuLink.pc_url} target="_blank" rel="noopener noreferrer">
                    {menuLink.pc_url.length > 120 
                      ? `${menuLink.pc_url.substring(0, 120)}...` 
                      : menuLink.pc_url}
                  </a>
                ) : (
                  <span className="no-url">-</span>
                )}
              </td>
              <td className="url-cell">
                {menuLink.mobile_url ? (
                  <a href={menuLink.mobile_url} target="_blank" rel="noopener noreferrer">
                    {menuLink.mobile_url.length > 120 
                      ? `${menuLink.mobile_url.substring(0, 120)}...` 
                      : menuLink.mobile_url}
                  </a>
                ) : (
                  <span className="no-url">-</span>
                )}
              </td>
              <td className="user-cell">
                {menuLink.created_by || (
                  <span className="no-user">-</span>
                )}
              </td>
              <td className="date-cell">
                {menuLink.created_at 
                  ? new Date(menuLink.created_at).toLocaleString('ko-KR', {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : '-'}
              </td>
              <td className="user-cell">
                {menuLink.updated_by || (
                  <span className="no-user">-</span>
                )}
              </td>
              <td className="date-cell">
                {menuLink.updated_at 
                  ? new Date(menuLink.updated_at).toLocaleString('ko-KR', {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : '-'}
              </td>
              <td className="actions-cell">
                <button
                  onClick={() => onEdit(menuLink)}
                  className="edit-button"
                >
                  수정
                </button>
                <button
                  onClick={() => onDelete(menuLink)}
                  className="delete-button"
                >
                  삭제
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
