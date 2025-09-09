'use client';

import { useState, useCallback } from 'react';
import { MenuLink, MenuLinkCreate, MenuLinkUpdate } from '@/app/_lib/domains/menuLink';
import { useMenuLinks, MenuLinkForm, MenuLinkTable } from '@/app/_features/menuManagement';
import ModernModal from '@/app/_components/ui/ModernModal';
import NewSearchBar from '@/app/_components/ui/NewSearchBar';
import ModernPagination from '@/app/_components/ui/ModernPagination';
import ModernPageHeader from '@/app/_components/ui/ModernPageHeader';

export default function MenuLinksPage() {
  const {
    menuLinks,
    loading,
    error,
    totalPages,
    totalItems,
    currentPage,
    pageSize,
    searchTerm,
    createMenuLink,
    updateMenuLink,
    deleteMenuLink,
    searchMenuLinks,
    resetSearch,
    changePage,
    changePageSize,
    clearError,
  } = useMenuLinks();

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingMenuLink, setEditingMenuLink] = useState<MenuLink | null>(null);

  // Handle create
  const handleCreate = useCallback(async (data: MenuLinkCreate) => {
    const success = await createMenuLink(data);
    if (success) {
      setIsCreateModalOpen(false);
    }
  }, [createMenuLink]);

  // Handle edit
  const handleEdit = useCallback((menuLink: MenuLink) => {
    setEditingMenuLink(menuLink);
    setIsEditModalOpen(true);
  }, []);

  const handleUpdate = useCallback(async (data: MenuLinkUpdate) => {
    if (!editingMenuLink) return;
    
    const success = await updateMenuLink(editingMenuLink.id, data);
    if (success) {
      setIsEditModalOpen(false);
      setEditingMenuLink(null);
    }
  }, [updateMenuLink, editingMenuLink]);

  // Handle delete
  const handleDelete = useCallback(async (menuLink: MenuLink) => {
    if (!confirm(`메뉴 경로 "${menuLink.menu_path.split('^').join(' > ')}"을 삭제하시겠습니까?`)) {
      return;
    }
    
    await deleteMenuLink(menuLink.id);
  }, [deleteMenuLink]);

  // Handle search
  const handleSearch = useCallback((searchTerm: string) => {
    searchMenuLinks(searchTerm);
  }, [searchMenuLinks]);

  // Handle reset
  const handleReset = useCallback(() => {
    resetSearch();
  }, [resetSearch]);

  return (
    <div className="menu-links-page">
      <ModernPageHeader
        title="메뉴 링크 관리"
        subtitle="웹사이트의 메뉴 경로와 URL을 관리합니다"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
          </svg>
        }
        status={{
          text: `${totalItems}개 항목`,
          isActive: !loading
        }}
        action={{
          text: "새 메뉴 링크",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          ),
          onClick: () => setIsCreateModalOpen(true)
        }}
      />

      {/* Error Display */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={clearError} className="error-close">×</button>
        </div>
      )}

      {/* Search Area */}
      <NewSearchBar 
        onSearch={handleSearch} 
        onReset={handleReset}
        defaultValue={searchTerm} 
        hasSearchTerm={!!searchTerm}
        placeholder="메뉴 경로를 입력하여 검색하세요..."
        title="메뉴 링크 검색"
        loading={loading}
      />


      {/* Menu Links Table */}
      <MenuLinkTable 
        menuLinks={menuLinks}
        loading={loading}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      {menuLinks.length === 0 && !loading && (
        <div className="empty-state">
          <p>메뉴 링크가 없습니다.</p>
          <button onClick={() => setIsCreateModalOpen(true)} className="create-button">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            첫 번째 메뉴 링크 생성하기
          </button>
        </div>
      )}

      {/* Modern Pagination */}
      <ModernPagination 
        currentPage={currentPage}
        totalPages={totalPages}
        totalItems={totalItems}
        onPageChange={changePage}
        pageSize={pageSize}
        onPageSizeChange={changePageSize}
      />

      {/* Create Modal */}
      <ModernModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="새 메뉴 링크 생성"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
          </svg>
        }
        size="large"
      >
        <MenuLinkForm
          onSubmit={(data) => handleCreate(data as MenuLinkCreate)}
          onCancel={() => setIsCreateModalOpen(false)}
          loading={loading}
          isEdit={false}
        />
      </ModernModal>

      {/* Edit Modal */}
      <ModernModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title="메뉴 링크 수정"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
            <path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
          </svg>
        }
        size="large"
      >
        <MenuLinkForm
          menuLink={editingMenuLink}
          onSubmit={(data) => handleUpdate(data as MenuLinkUpdate)}
          onCancel={() => setIsEditModalOpen(false)}
          loading={loading}
          isEdit={true}
        />
      </ModernModal>

    </div>
  );
}