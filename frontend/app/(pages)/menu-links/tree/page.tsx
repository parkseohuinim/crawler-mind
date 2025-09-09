'use client';

import { useMenuTree, MenuTreeView } from '@/app/_features/menuTree';
import ModernPageHeader from '@/app/_components/ui/ModernPageHeader';

export default function MenuTreePage() {
  const {
    menuLinks,
    loading,
    error,
    clearError,
  } = useMenuTree();

  return (
    <div className="menu-tree-page">
      <ModernPageHeader
        title="메뉴 트리 구조"
        subtitle="메뉴의 계층 구조와 담당자 정보를 한눈에 확인합니다"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
          </svg>
        }
        status={{
          text: `${menuLinks.length}개 메뉴`,
          isActive: !loading
        }}
      />

      {/* Error Display */}
      {error && (
        <div className="modern-error-banner">
          <div className="modern-error-content">
            <div className="modern-error-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
              </svg>
            </div>
            <span className="modern-error-text">{error}</span>
          </div>
          <button onClick={clearError} className="modern-error-close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      )}

      {/* Tree Content */}
      <div className="modern-tree-content">
        {loading ? (
          <div className="modern-loading-container">
            <div className="modern-loading-content">
              <div className="modern-spinner-large"></div>
              <div className="modern-loading-text">메뉴 트리 데이터를 불러오는 중...</div>
              <div className="modern-loading-subtext">잠시만 기다려주세요</div>
            </div>
          </div>
        ) : (
          <div className="modern-tree-section">
            <MenuTreeView menuLinks={menuLinks} />
          </div>
        )}
      </div>
    </div>
  );
}