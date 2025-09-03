'use client';

import React from 'react';
import { MenuManagerInfo, MenuLink } from '../types';

interface MenuManagerTableProps {
  managerInfos: MenuManagerInfo[];
  menuLinks: MenuLink[];
  loading: boolean;
  onEdit: (managerInfo: MenuManagerInfo) => void;
  onDelete: (managerInfo: MenuManagerInfo) => void;
}

export default function MenuManagerTable({
  managerInfos,
  menuLinks,
  loading,
  onEdit,
  onDelete
}: MenuManagerTableProps) {
  // 안전한 배열 체크
  const safeManagerInfos = Array.isArray(managerInfos) ? managerInfos : [];
  const safeMenuLinks = Array.isArray(menuLinks) ? menuLinks : [];
  
  // 디버깅을 위한 로그
  console.log('MenuManagerTable props:', {
    managerInfos: managerInfos,
    menuLinks: menuLinks,
    safeManagerInfos: safeManagerInfos,
    safeMenuLinks: safeMenuLinks
  });

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner"></div>
        <span>로딩 중...</span>
      </div>
    );
  }

  if (safeManagerInfos.length === 0) {
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
          {safeManagerInfos.map((managerInfo) => (
            <tr key={managerInfo.id}>
              <td>{managerInfo.id}</td>
              <td className="menu-path">
                {getMenuPath(managerInfo.menu_id)}
              </td>
              <td className="team-name">
                {managerInfo.team_name}
              </td>
              <td className="manager-names">
                {managerInfo.manager_names}
              </td>
              <td className="user-cell">
                {managerInfo.created_by || (
                  <span className="no-user">-</span>
                )}
              </td>
              <td className="date-cell">
                {managerInfo.created_at 
                  ? new Date(managerInfo.created_at).toLocaleString('ko-KR', {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : '-'}
              </td>
              <td className="user-cell">
                {managerInfo.updated_by || (
                  <span className="no-user">-</span>
                )}
              </td>
              <td className="date-cell">
                {managerInfo.updated_at 
                  ? new Date(managerInfo.updated_at).toLocaleString('ko-KR', {
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
                  onClick={() => onEdit(managerInfo)}
                  className="edit-button"
                >
                  수정
                </button>
                <button
                  onClick={() => onDelete(managerInfo)}
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
