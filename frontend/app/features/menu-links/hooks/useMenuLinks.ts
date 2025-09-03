/**
 * Custom hook for managing menu links
 */
import { useState, useEffect, useCallback } from 'react';
import { MenuLink, MenuLinkCreate, MenuLinkUpdate, MenuLinksResponse } from '../types';
import * as menuLinksApi from '../api/menuLinksApi';

export function useMenuLinks() {
  const [menuLinks, setMenuLinks] = useState<MenuLink[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState('');

  // Fetch menu links
  const fetchMenuLinks = useCallback(async (page?: number, size?: number, search?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const actualPage = page ?? currentPage;
      const actualSize = size ?? pageSize;
      const actualSearch = search ?? searchTerm;
      
      const response = await menuLinksApi.getMenuLinks(actualPage, actualSize, actualSearch || undefined);
      
      setMenuLinks(response.items);
      setTotalPages(response.pages);
      setTotalItems(response.total);
      setCurrentPage(actualPage);
      setPageSize(actualSize);
      
    } catch (err) {
      console.error('Error fetching menu links:', err);
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

  // Create menu link
  const createMenuLink = useCallback(async (menuLink: MenuLinkCreate): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      await menuLinksApi.createMenuLink(menuLink);
      // Refresh the list after creation
      await fetchMenuLinks();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create menu link');
      console.error('Error creating menu link:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchMenuLinks]);

  // Update menu link
  const updateMenuLink = useCallback(async (id: number, menuLink: MenuLinkUpdate): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      await menuLinksApi.updateMenuLink(id, menuLink);
      // Refresh the list after update
      await fetchMenuLinks();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update menu link');
      console.error('Error updating menu link:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchMenuLinks]);

  // Delete menu link
  const deleteMenuLink = useCallback(async (id: number): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      await menuLinksApi.deleteMenuLink(id);
      // Refresh the list after deletion
      await fetchMenuLinks();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete menu link');
      console.error('Error deleting menu link:', err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchMenuLinks]);

  // Search menu links
  const searchMenuLinks = useCallback(async (search: string) => {
    setSearchTerm(search);
    setCurrentPage(1); // Reset to first page when searching
    await fetchMenuLinks(1, pageSize, search);
  }, [pageSize, fetchMenuLinks]);

  // Reset search and refresh
  const resetSearch = useCallback(async () => {
    setSearchTerm('');
    setCurrentPage(1);
    await fetchMenuLinks(1, pageSize, '');
  }, [pageSize, fetchMenuLinks]);

  // Get assigned menu IDs (menus that already have managers)
  const getAssignedMenuIds = useCallback(async (): Promise<number[]> => {
    try {
      const response = await menuLinksApi.getManagerInfoList(1, 1000); // Get all manager info
      return response.items.map(info => info.menu_id);
    } catch (error) {
      console.error('Failed to get assigned menu IDs:', error);
      return [];
    }
  }, []);

  // Change page
  const changePage = useCallback(async (page: number) => {
    if (page >= 1 && page <= totalPages) {
      await fetchMenuLinks(page, pageSize, searchTerm);
    }
  }, [totalPages, pageSize, searchTerm, fetchMenuLinks]);

  // Change page size
  const changePageSize = useCallback(async (size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page when changing page size
    await fetchMenuLinks(1, size, searchTerm);
  }, [searchTerm, fetchMenuLinks]);

  // Initial load
  useEffect(() => {
    fetchMenuLinks();
  }, []);

  return {
    // Data
    menuLinks,
    loading,
    error,
    totalPages,
    totalItems,
    currentPage,
    pageSize,
    searchTerm,
    
    // Actions
    fetchMenuLinks,
    createMenuLink,
    updateMenuLink,
    deleteMenuLink,
    searchMenuLinks,
    resetSearch,
    getAssignedMenuIds,
    changePage,
    changePageSize,
    
    // Helpers
    clearError: () => setError(null),
  };
}
