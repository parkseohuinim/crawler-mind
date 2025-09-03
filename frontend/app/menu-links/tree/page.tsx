'use client';

import { useMenuTree, MenuTreeView } from '@/app/features/menuTree';

export default function MenuTreePage() {
  const {
    menuLinks,
    loading,
    error,
    clearError,
  } = useMenuTree();

  return (
    <div className="menu-tree-page">
      <div className="page-header">
        <h1 className="page-title">메뉴 트리 구조</h1>
        <p className="page-subtitle">메뉴의 계층 구조와 담당자 정보를 한눈에 확인합니다</p>
      </div>

      {/* Error Display */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={clearError} className="error-close">×</button>
        </div>
      )}

      <div className="tree-page-content">
        {/* Tree View */}
        <div className="tree-section">
          {loading ? (
            <div className="loading-container" style={{ minHeight: '60vh' }}>
              <div className="spinner-large"></div>
              <span className="loading-text">메뉴 트리 데이터를 불러오는 중...</span>
            </div>
          ) : (
            <MenuTreeView menuLinks={menuLinks} />
          )}
        </div>
      </div>
    </div>
  );
}