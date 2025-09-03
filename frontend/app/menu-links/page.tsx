'use client';

import { useState, useCallback } from 'react';
import { MenuLink, MenuLinkCreate, MenuLinkUpdate } from '@/app/domains/menuLink';
import { useMenuLinks, MenuLinkForm, MenuLinkTable } from '@/app/features/menuManagement';
import Modal from '@/app/components/Modal';
import SearchBar from '@/app/components/SearchBar';
import Pagination from '@/app/components/Pagination';

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
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingMenuLink, setDeletingMenuLink] = useState<MenuLink | null>(null);

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
  const handleDelete = useCallback((menuLink: MenuLink) => {
    setDeletingMenuLink(menuLink);
    setIsDeleteModalOpen(true);
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!deletingMenuLink) return;
    
    const success = await deleteMenuLink(deletingMenuLink.id);
    if (success) {
      setIsDeleteModalOpen(false);
      setDeletingMenuLink(null);
    }
  }, [deleteMenuLink, deletingMenuLink]);

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
      <div className="page-header">
        <h1 className="page-title">메뉴 링크 관리</h1>
        <p className="page-subtitle">웹사이트의 메뉴 경로와 URL을 관리합니다</p>
      </div>

      {/* Search and Actions */}
      <div className="page-actions">
        <SearchBar 
          onSearch={handleSearch} 
          onReset={handleReset}
          defaultValue={searchTerm} 
          hasSearchTerm={!!searchTerm}
          placeholder="메뉴 경로로 검색..."
        />
        
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="create-button"
        >
          + 새 메뉴 링크
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={clearError} className="error-close">×</button>
        </div>
      )}

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
            첫 번째 메뉴 링크 생성하기
          </button>
        </div>
      )}

      {/* Pagination */}
      <Pagination 
        currentPage={currentPage}
        totalPages={totalPages}
        totalItems={totalItems}
        onPageChange={changePage}
      />

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="새 메뉴 링크 생성"
      >
        <MenuLinkForm
          onSubmit={(data) => handleCreate(data as MenuLinkCreate)}
          onCancel={() => setIsCreateModalOpen(false)}
          loading={loading}
          isEdit={false}
        />
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title="메뉴 링크 수정"
      >
        <MenuLinkForm
          menuLink={editingMenuLink}
          onSubmit={(data) => handleUpdate(data as MenuLinkUpdate)}
          onCancel={() => setIsEditModalOpen(false)}
          loading={loading}
          isEdit={true}
        />
      </Modal>

      {/* Delete Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="메뉴 링크 삭제"
      >
        {deletingMenuLink && (
          <div>
            <p>다음 메뉴 링크를 삭제하시겠습니까?</p>
            <div className="delete-preview">
              <strong>메뉴 경로:</strong> {deletingMenuLink.menu_path.split('^').join(' > ')}
              <br />
              {deletingMenuLink.pc_url && (
                <>
                  <strong>PC URL:</strong> {deletingMenuLink.pc_url}
                  <br />
                </>
              )}
              {deletingMenuLink.mobile_url && (
                <>
                  <strong>모바일 URL:</strong> {deletingMenuLink.mobile_url}
                </>
              )}
            </div>
            <p className="warning">이 작업은 되돌릴 수 없습니다.</p>
            
            <div className="modal-actions">
              <button
                onClick={() => setIsDeleteModalOpen(false)}
                className="cancel-button"
              >
                취소
              </button>
              <button
                onClick={confirmDelete}
                className="delete-button"
                disabled={loading}
              >
                {loading ? '삭제 중...' : '삭제'}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}