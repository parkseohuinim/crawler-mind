/**
 * Custom hook for menu tree functionality
 */
import { useState, useEffect, useCallback } from 'react';

// Use basic types to avoid import issues
interface MenuLink {
  id: number;
  document_id?: string;
  menu_path: string;
  pc_url?: string;
  mobile_url?: string;
  created_by?: string;
  created_at?: string;
  updated_by?: string;
  updated_at?: string;
}

interface MenuManagerInfo {
  id: number;
  menu_id: number;
  team_name: string;
  manager_names: string;
  created_by?: string;
  created_at?: string;
  updated_by?: string;
  updated_at?: string;
}

export interface TreeNode {
  name: string;
  path: string;
  children: TreeNode[];
  count: number;
  totalCount: number;
  level: number;
  menuLinks: MenuLink[];
  managers: MenuManagerInfo[];
}

export function useMenuTree() {
  const [menuLinks, setMenuLinks] = useState<MenuLink[]>([]);
  const [managers, setManagers] = useState<MenuManagerInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [treeData, setTreeData] = useState<TreeNode[]>([]);

  // Fetch menu links and managers
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // First, just get menu links to ensure tree shows up
      const menuLinksResponse = await fetch('/api/menu-links?page=1&size=1000');
      
      if (!menuLinksResponse.ok) {
        throw new Error(`HTTP error! status: ${menuLinksResponse.status}`);
      }
      
      const menuLinksData = await menuLinksResponse.json();
      const allMenuLinks: MenuLink[] = menuLinksData.items || [];
      
      // Try to get managers, but don't fail if it doesn't work
      let allManagers: MenuManagerInfo[] = [];
      try {
        const managersResponse = await fetch('/api/menu-links/manager-info?page=1&size=1000');
        if (managersResponse.ok) {
          const managersData = await managersResponse.json();
          allManagers = managersData.items || [];
        }
      } catch (managerError) {
        console.warn('Could not fetch manager data:', managerError);
        // Continue without manager data
      }
      
      setMenuLinks(allMenuLinks);
      setManagers(allManagers);
      
    } catch (err) {
      console.error('Error fetching menu tree data:', err);
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
  }, []);

  // Build tree structure
  const buildTree = useCallback((menuLinks: MenuLink[], managers: MenuManagerInfo[]): TreeNode[] => {
    const root: TreeNode = {
      name: 'Root',
      path: '',
      children: [],
      count: 0,
      totalCount: 0,
      level: -1,
      menuLinks: [],
      managers: []
    };

    // Build tree structure
    menuLinks.forEach(menuLink => {
      const pathParts = menuLink.menu_path.split('^');
      let currentNode = root;
      let currentPath = '';

      pathParts.forEach((part, index) => {
        currentPath = index === 0 ? part : `${currentPath}^${part}`;
        
        let childNode = currentNode.children.find(child => child.name === part);
        if (!childNode) {
          childNode = {
            name: part,
            path: currentPath,
            children: [],
            count: 0,
            totalCount: 0,
            level: index,
            menuLinks: [],
            managers: []
          };
          currentNode.children.push(childNode);
        }
        
        // If this is the final part, add the menu link
        if (index === pathParts.length - 1) {
          childNode.count++;
          childNode.menuLinks.push(menuLink);
          
          // Find and add associated managers
          const associatedManagers = managers.filter(manager => manager.menu_id === menuLink.id);
          childNode.managers.push(...associatedManagers);
        }
        
        currentNode = childNode;
      });
    });

    // Calculate total counts (including children)
    function calculateTotalCounts(node: TreeNode): number {
      let total = node.count;
      node.children.forEach(child => {
        total += calculateTotalCounts(child);
      });
      node.totalCount = total;
      return total;
    }

    root.children.forEach(calculateTotalCounts);

    // Sort children by total count (descending)
    function sortChildren(node: TreeNode) {
      node.children.sort((a, b) => b.totalCount - a.totalCount);
      node.children.forEach(sortChildren);
    }
    
    sortChildren(root);

    return root.children;
  }, []);

  // Update tree data when menu links or managers change
  useEffect(() => {
    if (menuLinks.length > 0) {
      const tree = buildTree(menuLinks, managers);
      setTreeData(tree);
    }
  }, [menuLinks, managers, buildTree]);

  // Get menu links with managers
  const getMenuLinksWithManagers = useCallback(async () => {
    try {
      const response = await fetch('/api/menu-links/with-managers?page=1&size=1000');
      if (!response.ok) {
        throw new Error('Failed to fetch menu links with managers');
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to get menu links with managers:', error);
      throw error;
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    // Data
    menuLinks,
    managers,
    treeData,
    loading,
    error,
    
    // Actions
    fetchData,
    getMenuLinksWithManagers,
    
    // Helpers
    clearError: () => setError(null),
  };
}
