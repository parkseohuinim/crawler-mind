'use client';

import { useState, useCallback, useEffect } from 'react';
import { MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate } from '@/app/domains/menuManagerInfo';
import { MenuLink, menuLinkService } from '@/app/domains/menuLink';
import { useMenuManagerInfos, MenuManagerInfoForm, MenuManagerInfoTable } from '@/app/features/menuManagerManagement';
import Modal from '@/app/components/Modal';
import SearchBar from '@/app/components/SearchBar';
import Pagination from '@/app/components/Pagination';

export default function MenuManagersPage() {
  const {
    menuManagerInfos,
    loading,
    error,
    totalPages,
    totalItems,
    currentPage,
    pageSize,
    searchTerm,
    createMenuManagerInfo,
    updateMenuManagerInfo,
    deleteMenuManagerInfo,
    searchMenuManagerInfos,
    resetSearch,
    changePage,
    clearError,
  } = useMenuManagerInfos();

  const [availableMenuLinks, setAvailableMenuLinks] = useState<MenuLink[]>([]); // 담당자 배정 가능한 메뉴만
  const [allMenuLinks, setAllMenuLinks] = useState<MenuLink[]>([]); // 모든 메뉴 링크 (테이블 표시용)

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingMenuManagerInfo, setEditingMenuManagerInfo] = useState<MenuManagerInfo | undefined>(undefined);

  // Load menu links data
  const loadMenuLinksData = useCallback(async () => {
    try {
      const [allMenuResponse, availableMenuResponse] = await Promise.all([
        menuLinkService.getMenuLinks(1, 1000), // 모든 메뉴 링크 (테이블 표시용)
        menuLinkService.getAvailableMenuLinksForManager(1, 100) // 담당자 배정 가능한 메뉴만 (폼용)
      ]);
      
      setAvailableMenuLinks(availableMenuResponse?.items || []);
      setAllMenuLinks(allMenuResponse?.items || []);
      
    } catch (err) {
      console.error('Error loading menu links:', err);
    }
  }, []);

  // Load initial data
  useEffect(() => {
    loadMenuLinksData();
  }, [loadMenuLinksData]);

  // Handle create
  const handleCreate = useCallback(async (data: MenuManagerInfoCreate | MenuManagerInfoUpdate) => {
    if ('menu_id' in data) {
      const success = await createMenuManagerInfo(data as MenuManagerInfoCreate);
      if (success) {
        setIsCreateModalOpen(false);
        // Reload available menu links after creating a menu manager info
        await loadMenuLinksData();
      }
    }
  }, [createMenuManagerInfo, loadMenuLinksData]);

  // Handle edit
  const handleEdit = useCallback((menuManagerInfo: MenuManagerInfo) => {
    setEditingMenuManagerInfo(menuManagerInfo);
    setIsEditModalOpen(true);
  }, []);

  const handleUpdate = useCallback(async (data: MenuManagerInfoUpdate) => {
    if (!editingMenuManagerInfo) return;
    
    const success = await updateMenuManagerInfo(editingMenuManagerInfo.id, data);
    if (success) {
      setIsEditModalOpen(false);
      setEditingMenuManagerInfo(undefined);
    }
  }, [editingMenuManagerInfo, updateMenuManagerInfo]);

  // Handle delete
  const handleDelete = useCallback(async (menuManagerInfo: MenuManagerInfo) => {
    if (!confirm(`"${menuManagerInfo.team_name}" 팀의 매니저 정보를 삭제하시겠습니까?`)) {
      return;
    }
    
    const success = await deleteMenuManagerInfo(menuManagerInfo.id);
    if (success) {
      // Reload available menu links after deleting a menu manager info
      await loadMenuLinksData();
    }
  }, [deleteMenuManagerInfo, loadMenuLinksData]);

  // Handle search
  const handleSearch = useCallback((searchTerm: string) => {
    searchMenuManagerInfos(searchTerm);
  }, [searchMenuManagerInfos]);

  // Handle reset
  const handleReset = useCallback(() => {
    resetSearch();
  }, [resetSearch]);

  return (
    <div className="menu-managers-page">
      <div className="page-header">
        <h1 className="page-title">메뉴 매니저 관리</h1>
        <p className="page-subtitle">메뉴별 담당 팀과 담당자를 관리합니다</p>
      </div>

      {/* Error Display */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={clearError} className="error-close">×</button>
        </div>
      )}

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
          + 새 매니저 정보
        </button>
      </div>

      {/* Menu Manager Info Table */}
      <MenuManagerInfoTable 
        menuManagerInfos={menuManagerInfos}
        menuLinks={allMenuLinks || []}
        loading={loading}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

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
        title="새 매니저 정보 생성"
      >
        <MenuManagerInfoForm
          menuLinks={availableMenuLinks} // 배정되지 않은 메뉴만 전달
          onSubmit={handleCreate}
          onCancel={() => setIsCreateModalOpen(false)}
          loading={loading}
          isEdit={false}
        />
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setEditingMenuManagerInfo(undefined);
        }}
        title="매니저 정보 수정"
      >
        <MenuManagerInfoForm
          menuLinks={allMenuLinks || []} // 수정 시에는 모든 메뉴 전달 (현재 메뉴 포함)
          menuManagerInfo={editingMenuManagerInfo}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditModalOpen(false);
            setEditingMenuManagerInfo(undefined);
          }}
          loading={loading}
          isEdit={true}
        />
      </Modal>
    </div>
  );
}