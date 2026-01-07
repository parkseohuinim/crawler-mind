'use client';

import { useState, useCallback, useEffect } from 'react';
import { MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate } from '@/app/_lib/domains/menuManagerInfo';
import { MenuLink, menuLinkService } from '@/app/_lib/domains/menuLink';
import { useMenuManagerInfos, MenuManagerInfoForm, MenuManagerInfoTable } from '@/app/_features/menuManagerManagement';
import ModernModal from '@/app/_components/ui/ModernModal';
import NewSearchBar from '@/app/_components/ui/NewSearchBar';
import ModernPagination from '@/app/_components/ui/ModernPagination';
import ModernPageHeader from '@/app/_components/ui/ModernPageHeader';

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
    changePageSize,
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
      <ModernPageHeader
        title="메뉴 매니저 관리"
        subtitle="메뉴별 담당 팀과 담당자를 관리합니다"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
          </svg>
        }
        status={{
          text: `${totalItems}개 항목`,
          isActive: !loading
        }}
        action={{
          text: "새 매니저 정보",
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
        title="메뉴 매니저 검색"
        loading={loading}
      />


      {/* Menu Manager Info Table */}
      <MenuManagerInfoTable 
        menuManagerInfos={menuManagerInfos}
        loading={loading}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

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
        title="새 매니저 정보 생성"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
          </svg>
        }
        size="large"
      >
        <MenuManagerInfoForm
          menuLinks={availableMenuLinks} // 배정되지 않은 메뉴만 전달
          onSubmit={handleCreate}
          onCancel={() => setIsCreateModalOpen(false)}
          loading={loading}
          isEdit={false}
        />
      </ModernModal>

      {/* Edit Modal */}
      <ModernModal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setEditingMenuManagerInfo(undefined);
        }}
        title="매니저 정보 수정"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
            <path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
          </svg>
        }
        size="large"
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
      </ModernModal>
    </div>
  );
}