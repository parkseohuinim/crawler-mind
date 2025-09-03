'use client';

import { useState, useCallback, useEffect } from 'react';
import { 
  MenuManagerInfo, 
  MenuLink,
  MenuManagerInfoCreate,
  MenuManagerInfoUpdate
} from '../features/menu-links/types';
import {
  getAvailableMenuLinksForManager,
  getMenuLinks
} from '../features/menu-links/api/menuLinksApi';
import { useMenuManagers } from '../features/menu-links/hooks';
import MenuManagerForm from '../features/menu-links/components/MenuManagerForm';
import MenuManagerTable from '../features/menu-links/components/MenuManagerTable';
import Modal from '../features/menu-links/components/Modal';
import SearchBar from '../features/menu-links/components/SearchBar';
import Pagination from '../features/menu-links/components/Pagination';

export default function MenuManagersPage() {
  const {
    managerInfos,
    loading,
    error,
    totalPages,
    totalItems,
    currentPage,
    pageSize,
    searchTerm,
    createManagerInfo,
    updateManagerInfo,
    deleteManagerInfo,
    searchManagerInfos,
    resetSearch,
    changePage,
    clearError,
  } = useMenuManagers();

  const [availableMenuLinks, setAvailableMenuLinks] = useState<MenuLink[]>([]); // 담당자 배정 가능한 메뉴만
  const [allMenuLinks, setAllMenuLinks] = useState<MenuLink[]>([]); // 모든 메뉴 링크 (테이블 표시용)

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingManagerInfo, setEditingManagerInfo] = useState<MenuManagerInfo | undefined>(undefined);

  // Load menu links data
  const loadMenuLinksData = useCallback(async () => {
    try {
      const [allMenuResponse, availableMenuResponse] = await Promise.all([
        getMenuLinks(1, 1000), // 모든 메뉴 링크 (테이블 표시용)
        getAvailableMenuLinksForManager(1, 100) // 담당자 배정 가능한 메뉴만 (폼용)
      ]);
      
      setAvailableMenuLinks(availableMenuResponse?.items || []);
      setAllMenuLinks(allMenuResponse?.items || []);
      
      console.log('Menu links data loaded:', {
        allMenuResponse,
        availableMenuResponse,
        allMenuLinksCount: allMenuResponse?.items?.length || 0,
        availableMenuLinksCount: availableMenuResponse?.items?.length || 0
      });
      
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
      const success = await createManagerInfo(data as MenuManagerInfoCreate);
      if (success) {
        setIsCreateModalOpen(false);
      }
    }
  }, [createManagerInfo]);

  // Handle edit
  const handleEdit = useCallback((managerInfo: MenuManagerInfo) => {
    setEditingManagerInfo(managerInfo);
    setIsEditModalOpen(true);
  }, []);

  const handleUpdate = useCallback(async (data: MenuManagerInfoUpdate) => {
    if (!editingManagerInfo) return;
    
    const success = await updateManagerInfo(editingManagerInfo.id, data);
    if (success) {
      setIsEditModalOpen(false);
      setEditingManagerInfo(undefined);
    }
  }, [editingManagerInfo, updateManagerInfo]);

  // Handle delete
  const handleDelete = useCallback(async (managerInfo: MenuManagerInfo) => {
    if (!confirm(`"${managerInfo.team_name}" 팀의 매니저 정보를 삭제하시겠습니까?`)) {
      return;
    }
    
    await deleteManagerInfo(managerInfo.id);
  }, [deleteManagerInfo]);

  // Handle search
  const handleSearch = useCallback((searchTerm: string) => {
    searchManagerInfos(searchTerm);
  }, [searchManagerInfos]);

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

      {/* Manager Info Table */}
      <MenuManagerTable 
        managerInfos={managerInfos}
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
        <MenuManagerForm
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
          setEditingManagerInfo(undefined);
        }}
        title="매니저 정보 수정"
      >
        <MenuManagerForm
          menuLinks={allMenuLinks || []} // 수정 시에는 모든 메뉴 전달 (현재 메뉴 포함)
          managerInfo={editingManagerInfo}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditModalOpen(false);
            setEditingManagerInfo(undefined);
          }}
          loading={loading}
          isEdit={true}
        />
      </Modal>
    </div>
  );
}
