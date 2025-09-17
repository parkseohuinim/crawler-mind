'use client';

import React from 'react';
import Link from 'next/link';
import { useAuth } from '../../_lib/auth/auth-context';

interface MenuItem {
  id: number;
  name: string;
  path: string;
  icon: string;
  description?: string;
  parent_id?: number;
  order_index: number;
}

interface NavigationProps {
  className?: string;
}

export default function ProtectedNavigation({ className = '' }: NavigationProps) {
  const { user, hasPermission, hasAnyRole } = useAuth();
  
  // 기본 메뉴 구조 (권한 기반으로 필터링됨)
  const menuItems: MenuItem[] = [
    {
      id: 1,
      name: '홈',
      path: '/',
      icon: 'home',
      order_index: 1,
      description: '크롤링 메인 페이지'
    },
    {
      id: 2,
      name: 'RAG 시스템',
      path: '/rag',
      icon: 'document',
      order_index: 2,
      description: 'RAG 데이터 관리 시스템'
    },
    {
      id: 4,
      name: '메뉴 링크 관리',
      path: '/menu-links',
      icon: 'link',
      order_index: 3,
      description: '메뉴 링크 관리'
    },
    {
      id: 5,
      name: '메뉴 매니저 관리',
      path: '/menu-managers',
      icon: 'user',
      order_index: 4,
      description: '메뉴 매니저 관리'
    },
    {
      id: 6,
      name: '메뉴 트리뷰',
      path: '/menu-links/tree',
      icon: 'tree',
      order_index: 5,
      description: '메뉴 트리 구조 보기'
    },
    {
      id: 7,
      name: 'JSON 비교',
      path: '/json-compare',
      icon: 'compare',
      order_index: 6,
      description: 'JSON 데이터 비교 도구'
    }
  ];

  // 권한별 메뉴 필터링
  const getAccessibleMenus = (): MenuItem[] => {
    if (!user) return [];

    return menuItems.filter(menu => {
      // 관리자는 모든 메뉴 접근 가능
      if (hasAnyRole(['admin'])) {
        return true;
      }

      // 각 메뉴별 권한 확인
      switch (menu.path) {
        case '/':
          return hasPermission('crawler:read');
        case '/rag':
          return hasPermission('rag:read') || hasPermission('rag:search');
        case '/menu-links':
          return hasPermission('menu_links:read');
        case '/menu-managers':
          return hasPermission('menu_manager:read');
        case '/menu-links/tree':
          return hasPermission('menu_links:read');
        case '/json-compare':
          return hasPermission('json:read');
        default:
          return false;
      }
    }).sort((a, b) => a.order_index - b.order_index);
  };

  const getIconComponent = (iconName: string) => {
    const iconClass = "w-5 h-5";
    
    switch (iconName) {
      case 'home':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        );
      case 'document':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        );
      case 'link':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
        );
      case 'user':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        );
      case 'tree':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14-7H5m14 14H5" />
          </svg>
        );
      case 'compare':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h2M9 5a2 2 0 012 2v10a2 2 0 01-2 2M9 5a2 2 0 012-2h2a2 2 0 012 2M15 5h2a2 2 0 012 2v10a2 2 0 01-2 2h-2" />
          </svg>
        );
      default:
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        );
    }
  };

  const accessibleMenus = getAccessibleMenus();

  if (!user || accessibleMenus.length === 0) {
    return null;
  }

  return (
    <nav className={`protected-navigation ${className}`}>
      <div className="navigation-header">
        <h3>메뉴</h3>
        <span className="user-role-indicator">
          {user.roles.join(', ')}
        </span>
      </div>
      
      <ul className="navigation-list">
        {accessibleMenus.map((menu) => (
          <li key={menu.id} className="navigation-item">
            <Link href={menu.path} className="navigation-link">
              <span className="navigation-icon">
                {getIconComponent(menu.icon)}
              </span>
              <span className="navigation-text">{menu.name}</span>
            </Link>
          </li>
        ))}
      </ul>
      
      {hasAnyRole(['admin']) && (
        <div className="admin-section">
          <div className="admin-indicator">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>관리자 권한</span>
          </div>
        </div>
      )}
    </nav>
  );
}
