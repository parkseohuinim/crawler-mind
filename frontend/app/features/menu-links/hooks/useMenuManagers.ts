/**
 * Custom hook for managing menu managers
 */
import { useState, useEffect, useCallback } from 'react';
import { MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate } from '../types';
import * as menuLinksApi from '../api/menuLinksApi';

export function useMenuManagers() {
  const [managerInfos, setManagerInfos] = useState<MenuManagerInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState('');

  // Fetch manager infos
  const fetchManagerInfos = useCallback(async (page?: number, size?: number, search?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const actualPage = page ?? currentPage;
      const actualSize = size ?? pageSize;
      const actualSearch = search ?? searchTerm;
      
      const response = await menuLinksApi.getManagerInfoList(actualPage, actualSize, actualSearch || undefined);
      
      setManagerInfos(response.items);
      setTotalPages(response.pages);
      setTotalItems(response.total);
      setCurrentPage(actualPage);
      setPageSize(actualSize);
      
    } catch (err) {
      console.error('Error fetching manager infos:', err);
      let errorMessage = 'Unknown error occurred';
      
      if (err instanceof Error) {
        errorMessage = err.message;
      } else if (typeof err === 'string') {
        errorMessage = err;
      } else if (err && typeof err === 'object') {
        errorMessage = JSON.stringify(err);
      }
      
      // Check if it's a network error
      if (errorMessage.includes('fetch')) {
        errorMessage = '서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.';
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, searchTerm]);

  // Create manager info
  const createManagerInfo = useCallback(async (managerInfo: MenuManagerInfoCreate): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      await menuLinksApi.createManagerInfo(managerInfo);
      // Refresh the list after creation
      await fetchManagerInfos();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create manager info');
      console.error('Error creating manager info:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchManagerInfos]);

  // Update manager info
  const updateManagerInfo = useCallback(async (id: number, managerInfo: MenuManagerInfoUpdate): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      await menuLinksApi.updateManagerInfo(id, managerInfo);
      // Refresh the list after update
      await fetchManagerInfos();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update manager info');
      console.error('Error updating manager info:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchManagerInfos]);

  // Delete manager info
  const deleteManagerInfo = useCallback(async (id: number): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      await menuLinksApi.deleteManagerInfo(id);
      // Refresh the list after deletion
      await fetchManagerInfos();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete manager info');
      console.error('Error deleting manager info:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchManagerInfos]);

  // Search manager infos
  const searchManagerInfos = useCallback(async (search: string) => {
    setSearchTerm(search);
    setCurrentPage(1); // Reset to first page when searching
    await fetchManagerInfos(1, pageSize, search);
  }, [pageSize, fetchManagerInfos]);

  // Reset search and refresh
  const resetSearch = useCallback(async () => {
    setSearchTerm('');
    setCurrentPage(1);
    await fetchManagerInfos(1, pageSize, '');
  }, [pageSize, fetchManagerInfos]);

  // Change page
  const changePage = useCallback(async (page: number) => {
    if (page >= 1 && page <= totalPages) {
      await fetchManagerInfos(page, pageSize, searchTerm);
    }
  }, [totalPages, pageSize, searchTerm, fetchManagerInfos]);

  // Change page size
  const changePageSize = useCallback(async (size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page when changing page size
    await fetchManagerInfos(1, size, searchTerm);
  }, [searchTerm, fetchManagerInfos]);

  // Initial load
  useEffect(() => {
    fetchManagerInfos();
  }, []);

  return {
    // Data
    managerInfos,
    loading,
    error,
    totalPages,
    totalItems,
    currentPage,
    pageSize,
    searchTerm,
    
    // Actions
    fetchManagerInfos,
    createManagerInfo,
    updateManagerInfo,
    deleteManagerInfo,
    searchManagerInfos,
    resetSearch,
    changePage,
    changePageSize,
    
    // Helpers
    clearError: () => setError(null),
  };
}
