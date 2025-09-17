'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { authService, User, LoginRequest } from './auth-service';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  clearError: () => void;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<boolean>;
  hasRole: (role: string) => boolean;
  hasPermission: (permission: string) => boolean;
  hasAnyRole: (roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 초기 로드 시 토큰 확인
    const initializeAuth = async () => {
      try {
        const currentUser = await authService.getCurrentUser();
        if (currentUser && currentUser.roles && Array.isArray(currentUser.roles)) {
          console.log('✅ AuthContext: 기존 인증 정보 복원:', currentUser.username);
          setUser(currentUser);
        } else if (currentUser) {
          console.warn('⚠️ AuthContext: 사용자 데이터 구조가 올바르지 않음:', currentUser);
          authService.clearTokens();
          setUser(null);
        } else {
          console.log('ℹ️ AuthContext: 저장된 인증 정보 없음 (첫 방문 또는 로그아웃 상태)');
          setUser(null);
        }
      } catch (error) {
        console.log('⚠️ AuthContext: 토큰 검증 실패, 갱신 시도:', error);
        
        // 토큰 갱신 시도
        try {
          const refreshed = await authService.refreshToken();
          if (refreshed) {
            console.log('🔄 AuthContext: 토큰 갱신 성공, 사용자 정보 재조회');
            const refreshedUser = await authService.getCurrentUser();
            if (refreshedUser && refreshedUser.roles && Array.isArray(refreshedUser.roles)) {
              console.log('✅ AuthContext: 갱신된 토큰으로 인증 정보 복원:', refreshedUser.username);
              setUser(refreshedUser);
            } else {
              console.log('❌ AuthContext: 갱신 후에도 사용자 정보 조회 실패');
              authService.clearTokens();
              setUser(null);
            }
          } else {
            console.log('❌ AuthContext: 토큰 갱신 실패, 로그아웃 처리');
            authService.clearTokens();
            setUser(null);
          }
        } catch (refreshError) {
          console.log('❌ AuthContext: 토큰 갱신 중 오류:', refreshError);
          authService.clearTokens();
          setUser(null);
        }
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, []);

  const login = async (credentials: LoginRequest) => {
    setIsLoading(true);
    setError(null); // 로그인 시도 시 이전 에러 클리어
    
    try {
      console.log('🔐 AuthContext: 로그인 시작');
      const loginResponse = await authService.login(credentials);
      console.log('📥 AuthContext: 로그인 응답 받음:', loginResponse);
      console.log('🔍 AuthContext: user 객체:', loginResponse.user);
      console.log('🔍 AuthContext: roles 배열:', loginResponse.roles);
      
      // Aegis Shield Server 응답 구조: { user: UserDto, roles: string[], ... }
      if (loginResponse.user && Array.isArray(loginResponse.roles)) {
        const userData = {
          ...loginResponse.user,
          roles: loginResponse.roles, // 서버에서 별도로 제공하는 roles 사용
          permissions: [] // 초기값, 나중에 MCP Client에서 조회
        };
        
        console.log('✅ AuthContext: 사용자 상태 업데이트:', userData);
        setUser(userData);
      } else {
        console.error('❌ AuthContext: 잘못된 응답 구조:', {
          hasUser: !!loginResponse.user,
          hasRoles: Array.isArray(loginResponse.roles),
          rolesType: typeof loginResponse.roles,
          response: loginResponse
        });
        const errorMsg = 'Invalid user data received from server';
        setError(errorMsg);
        throw new Error(errorMsg);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '로그인에 실패했습니다.';
      console.log('🔴 AuthContext: 에러 상태 설정:', errorMessage);
      setError(errorMessage);
      throw err; // 에러를 다시 던져서 LoginForm에서도 처리할 수 있도록
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  const refreshToken = async (): Promise<boolean> => {
    try {
      const success = await authService.refreshToken();
      if (success) {
        const currentUser = await authService.getCurrentUser();
        if (currentUser && Array.isArray(currentUser.roles)) {
          setUser(currentUser);
        } else {
          logout();
          return false;
        }
      }
      return success;
    } catch (error) {
      logout();
      return false;
    }
  };

  const hasRole = (role: string): boolean => {
    return user?.roles && Array.isArray(user.roles) ? user.roles.includes(role) : false;
  };

  const hasPermission = (permission: string): boolean => {
    return user?.permissions && Array.isArray(user.permissions) ? user.permissions.includes(permission) : false;
  };

  const hasAnyRole = (roles: string[]): boolean => {
    if (!user?.roles || !Array.isArray(user.roles)) return false;
    return roles.some(role => hasRole(role));
  };

  const clearError = () => {
    setError(null);
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    error,
    clearError,
    login,
    logout,
    refreshToken,
    hasRole,
    hasPermission,
    hasAnyRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
