'use client';

import React, { ReactNode, useMemo } from 'react';
import { useAuth } from '../../_lib/auth/auth-context';
import LoginForm from './LoginForm';

interface AuthGuardProps {
  children: ReactNode;
  requiredRoles?: string[];
  requiredPermissions?: string[];
  fallback?: ReactNode;
}

export default function AuthGuard({ 
  children, 
  requiredRoles = [], 
  requiredPermissions = [],
  fallback 
}: AuthGuardProps) {
  const { isAuthenticated, isLoading, user, hasAnyRole, hasPermission } = useAuth();

  // 디버깅을 위한 로그
  console.log('🛡️ AuthGuard 상태:', { 
    isAuthenticated, 
    isLoading, 
    user: user ? { username: user.username, roles: user.roles } : null 
  });

  // 로딩 중
  if (isLoading) {
    return (
      <div className="auth-loading">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>인증 정보를 확인하고 있습니다...</p>
        </div>
      </div>
    );
  }

  // 로그인되지 않음
  const loginForm = useMemo(() => <LoginForm />, []);
  if (!isAuthenticated) {
    console.log('🔒 인증되지 않음 - 로그인 폼 표시');
    return loginForm;
  }

  // 역할 확인
  if (requiredRoles.length > 0 && !hasAnyRole(requiredRoles)) {
    return (
      <div className="auth-error">
        <div className="error-container">
          <h3>접근 권한이 없습니다</h3>
          <p>이 페이지에 접근하기 위해서는 다음 역할 중 하나가 필요합니다:</p>
          <ul>
            {requiredRoles.map(role => (
              <li key={role}>{role}</li>
            ))}
          </ul>
          <p>현재 사용자 역할: {user?.roles.join(', ')}</p>
          {fallback && <div className="fallback-content">{fallback}</div>}
        </div>
      </div>
    );
  }

  // 권한 확인
  if (requiredPermissions.length > 0) {
    const missingPermissions = requiredPermissions.filter(permission => !hasPermission(permission));
    if (missingPermissions.length > 0) {
      return (
        <div className="auth-error">
          <div className="error-container">
            <h3>권한이 부족합니다</h3>
            <p>이 페이지에 접근하기 위해서는 다음 권한이 필요합니다:</p>
            <ul>
              {missingPermissions.map(permission => (
                <li key={permission}>{permission}</li>
              ))}
            </ul>
            {fallback && <div className="fallback-content">{fallback}</div>}
          </div>
        </div>
      );
    }
  }

  // 모든 조건 통과
  return <>{children}</>;
}

// 특정 컴포넌트를 권한으로 보호하는 HOC
export function withAuth<P extends object>(
  Component: React.ComponentType<P>,
  options: {
    requiredRoles?: string[];
    requiredPermissions?: string[];
    fallback?: ReactNode;
  } = {}
) {
  return function AuthenticatedComponent(props: P) {
    return (
      <AuthGuard {...options}>
        <Component {...props} />
      </AuthGuard>
    );
  };
}
