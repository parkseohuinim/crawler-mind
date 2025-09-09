/**
 * Custom hook for managing menu manager info
 */
import { useState, useEffect, useCallback } from 'react';
import { 
  MenuManagerInfo, 
  MenuManagerInfoCreate, 
  MenuManagerInfoUpdate, 
  MenuManagerInfoResponse 
} from '@/app/_lib/domains/menuManagerInfo';

export function useMenuManagerInfos() {
  const [menuManagerInfos, setMenuManagerInfos] = useState<MenuManagerInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState('');

  // Fetch menu manager infos
  const fetchMenuManagerInfos = useCallback(async (page?: number, size?: number, search?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const actualPage = page ?? currentPage;
      const actualSize = size ?? pageSize;
      const actualSearch = search ?? searchTerm;
      
      const params = new URLSearchParams({
        page: actualPage.toString(),
        size: actualSize.toString(),
      });
      
      if (actualSearch) {
        params.append('search', actualSearch);
      }
      
      const response = await fetch(`/api/menu-manager-info?${params}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch menu manager infos');
      }
      
      const data: MenuManagerInfoResponse = await response.json();
      
      setMenuManagerInfos(data.items);
      setTotalPages(data.pages);
      setTotalItems(data.total);
      setCurrentPage(actualPage);
      setPageSize(actualSize);
      
    } catch (err) {
      console.error('Error fetching menu manager infos:', err);
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

  // Create menu manager info
  const createMenuManagerInfo = useCallback(async (menuManagerInfo: MenuManagerInfoCreate): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/menu-manager-info', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(menuManagerInfo),
      });

      if (!response.ok) {
        throw new Error('Failed to create menu manager info');
      }

      // Refresh the list after creation
      await fetchMenuManagerInfos();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create menu manager info');
      console.error('Error creating menu manager info:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchMenuManagerInfos]);

  // Update menu manager info
  const updateMenuManagerInfo = useCallback(async (id: number, menuManagerInfo: MenuManagerInfoUpdate): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/menu-manager-info/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(menuManagerInfo),
      });

      if (!response.ok) {
        throw new Error('Failed to update menu manager info');
      }

      // Refresh the list after update
      await fetchMenuManagerInfos();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update menu manager info');
      console.error('Error updating menu manager info:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchMenuManagerInfos]);

  // Delete menu manager info
  const deleteMenuManagerInfo = useCallback(async (id: number): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/menu-manager-info/${id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete menu manager info');
      }

      // Refresh the list after deletion
      await fetchMenuManagerInfos();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete menu manager info');
      console.error('Error deleting menu manager info:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchMenuManagerInfos]);

  // Search menu manager infos
  const searchMenuManagerInfos = useCallback(async (search: string) => {
    setSearchTerm(search);
    setCurrentPage(1); // Reset to first page when searching
    await fetchMenuManagerInfos(1, pageSize, search);
  }, [pageSize, fetchMenuManagerInfos]);

  // Reset search and refresh
  const resetSearch = useCallback(async () => {
    setSearchTerm('');
    setCurrentPage(1);
    await fetchMenuManagerInfos(1, pageSize, '');
  }, [pageSize, fetchMenuManagerInfos]);

  // Change page
  const changePage = useCallback(async (page: number) => {
    if (page >= 1 && page <= totalPages) {
      await fetchMenuManagerInfos(page, pageSize, searchTerm);
    }
  }, [totalPages, pageSize, searchTerm, fetchMenuManagerInfos]);

  // Change page size
  const changePageSize = useCallback(async (size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page when changing page size
    await fetchMenuManagerInfos(1, size, searchTerm);
  }, [searchTerm, fetchMenuManagerInfos]);

  // Initial load
  useEffect(() => {
    fetchMenuManagerInfos();
  }, []);

  return {
    // Data
    menuManagerInfos,
    loading,
    error,
    totalPages,
    totalItems,
    currentPage,
    pageSize,
    searchTerm,
    
    // Actions
    fetchMenuManagerInfos,
    createMenuManagerInfo,
    updateMenuManagerInfo,
    deleteMenuManagerInfo,
    searchMenuManagerInfos,
    resetSearch,
    changePage,
    changePageSize,
    
    // Helpers
    clearError: () => setError(null),
  };
}
