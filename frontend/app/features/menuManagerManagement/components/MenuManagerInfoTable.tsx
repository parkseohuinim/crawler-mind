'use client';

import React from 'react';
import { MenuManagerInfo } from '@/app/domains/menuManagerInfo';
import { MenuLink } from '@/app/domains/menuLink';

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

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner-large"></div>
        <span className="loading-text">메뉴 매니저 정보를 불러오는 중...</span>
      </div>
    );
  }

  if (safeMenuManagerInfos.length === 0) {
    return (
      <div className="empty-state">
        <p>메뉴 매니저 정보가 없습니다.</p>
      </div>
    );
  }

  const getMenuPath = (menuId: number) => {
    const menu = safeMenuLinks.find(m => m.id === menuId);
    return menu ? menu.menu_path.split('^').join(' > ') : '알 수 없음';
  };

  return (
    <div className="table-container">
      <table className="menu-manager-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>메뉴 경로</th>
            <th>팀명</th>
            <th>담당자명</th>
            <th>생성자</th>
            <th>생성일</th>
            <th>수정자</th>
            <th>수정일</th>
            <th>작업</th>
          </tr>
        </thead>
        <tbody>
          {safeMenuManagerInfos.map((menuManagerInfo) => (
            <tr key={menuManagerInfo.id}>
              <td>{menuManagerInfo.id}</td>
              <td className="menu-path">
                {getMenuPath(menuManagerInfo.menu_id)}
              </td>
              <td className="team-name">
                {menuManagerInfo.team_name}
              </td>
              <td className="manager-names">
                {menuManagerInfo.manager_names}
              </td>
              <td className="user-cell">
                {menuManagerInfo.created_by || (
                  <span className="no-user">-</span>
                )}
              </td>
              <td className="date-cell">
                {menuManagerInfo.created_at 
                  ? new Date(menuManagerInfo.created_at).toLocaleString('ko-KR', {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : '-'}
              </td>
              <td className="user-cell">
                {menuManagerInfo.updated_by || (
                  <span className="no-user">-</span>
                )}
              </td>
              <td className="date-cell">
                {menuManagerInfo.updated_at 
                  ? new Date(menuManagerInfo.updated_at).toLocaleString('ko-KR', {
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
                  onClick={() => onEdit(menuManagerInfo)}
                  className="edit-button"
                >
                  수정
                </button>
                <button
                  onClick={() => onDelete(menuManagerInfo)}
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
