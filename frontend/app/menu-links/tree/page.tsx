'use client';

import React, { useState } from 'react';
import { MenuTreeChart } from '../../features/menu-links/components';
import { useMenuLinks } from '../../features/menu-links/hooks/useMenuLinks';

export default function MenuTreePage() {
  const { menuLinks, loading, error, fetchMenuLinks } = useMenuLinks();
  
  // Fetch all menu links for tree visualization
  React.useEffect(() => {
    fetchMenuLinks(1, 1000); // Get all menu links (up to 1000)
  }, [fetchMenuLinks]);

  if (error) {
    return (
      <div className="menu-links-page">
        <div className="error-banner">
          <span>메뉴 데이터를 불러오는데 실패했습니다: {error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="menu-links-page">
      <div className="page-header">
        <h1 className="page-title">메뉴 구조 트리 차트</h1>
        <p className="page-subtitle">
          실제 DB 데이터로 구성된 계층형 메뉴 구조를 시각적 인포그래픽으로 확인하세요
        </p>
        <div className="page-stats">
          <div className="stat-badge">
            <span className="stat-number">{menuLinks.length}</span>
            <span className="stat-label">총 메뉴</span>
          </div>
          <div className="stat-badge">
            <span className="stat-number">
              {new Set(menuLinks.map(m => m.menu_path.split('^')[0])).size}
            </span>
            <span className="stat-label">최상위 카테고리</span>
          </div>
          <div className="stat-badge">
            <span className="stat-number">
              {Math.max(...menuLinks.map(m => m.menu_path.split('^').length))}
            </span>
            <span className="stat-label">최대 깊이</span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="loading-spinner">
          <div className="spinner"></div>
          <span>실제 DB에서 메뉴 데이터를 불러오는 중...</span>
        </div>
      ) : (
        <MenuTreeChart menuLinks={menuLinks} />
      )}
    </div>
  );
}
