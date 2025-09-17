'use client';

import React from 'react';
import { useAuth } from '../../_lib/auth/auth-context';
import ProtectedNavigation from '../navigation/ProtectedNavigation';
import UserMenu from '../ui/UserMenu';
import AuthGuard from '../auth/AuthGuard';

interface AuthenticatedLayoutProps {
  children: React.ReactNode;
}

export default function AuthenticatedLayout({ children }: AuthenticatedLayoutProps) {
  const { isAuthenticated, isLoading } = useAuth();

  // 로딩 중에는 간단한 로딩 화면 표시
  if (isLoading) {
    return (
      <div className="loading-layout">
        <div className="loading-content">
          <div className="loading-spinner">
            <div className="spinner"></div>
          </div>
          <h2>Crawler Mind</h2>
          <p>인증 정보를 확인하고 있습니다...</p>
        </div>
      </div>
    );
  }

  // 인증되지 않은 경우 AuthGuard가 로그인 폼을 표시
  if (!isAuthenticated) {
    return (
      <AuthGuard>
        {children}
      </AuthGuard>
    );
  }

  // 인증된 사용자를 위한 메인 레이아웃
  return (
    <div className="authenticated-layout">
      {/* 헤더 */}
      <header className="layout-header">
        <div className="header-content">
          <div className="header-left">
            <h1 className="app-title">Crawler Mind</h1>
            <span className="app-subtitle">Enterprise Edition</span>
          </div>
          <div className="header-right">
            <UserMenu />
          </div>
        </div>
      </header>

      {/* 메인 컨텐츠 영역 */}
      <div className="layout-main">
        {/* 사이드바 네비게이션 */}
        <aside className="layout-sidebar">
          <ProtectedNavigation />
        </aside>

        {/* 컨텐츠 영역 */}
        <main className="layout-content">
          <div className="content-wrapper">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
