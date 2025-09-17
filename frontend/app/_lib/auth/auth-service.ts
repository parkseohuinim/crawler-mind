// 인증 서비스 - Aegis Shield Server와 통신
export interface User {
  id: number;
  username: string;
  email: string;
  fullName: string;
  roles: string[];
  permissions?: string[];
  isActive: boolean;
}

export interface LoginRequest {
  usernameOrEmail: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  user: {
    id: number;
    username: string;
    email: string;
    fullName: string;
    isActive: boolean;
  };
  roles: string[];
  expiresAt: string;
}

export interface RefreshRequest {
  refreshToken: string;
}

export interface TokenValidationResponse {
  valid: boolean;
  user?: User;
  timestamp: number;
}

class AuthService {
  private readonly baseUrl = process.env.NEXT_PUBLIC_AUTH_SERVER_URL || 'http://localhost:8080/aegis';
  private readonly tokenKey = 'auth_access_token';
  private readonly refreshTokenKey = 'auth_refresh_token';

  // 로그인
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    console.log('🌐 AuthService: 로그인 요청 시작', this.baseUrl);
    
    const response = await fetch(`${this.baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
    });

    console.log('📡 AuthService: 서버 응답 상태:', response.status);

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      console.error('❌ AuthService: 로그인 실패:', error);
      // 백엔드 ApiErrorResponse 및 ValidationErrorResponse 구조에 맞게 에러 메시지 추출
      let errorMessage = error.message || error.error || `Login failed: ${response.status}`;
      
      // ValidationErrorResponse인 경우 필드별 에러도 확인
      if (error.fieldErrors && typeof error.fieldErrors === 'object') {
        const fieldErrorMessages = Object.values(error.fieldErrors);
        if (fieldErrorMessages.length > 0) {
          errorMessage = fieldErrorMessages[0]; // 첫 번째 필드 에러 사용
        }
      }
      
      throw new Error(errorMessage);
    }

    const loginResponse: LoginResponse = await response.json();
    console.log('✅ AuthService: 로그인 성공, 응답:', loginResponse);
    
    // 토큰 저장
    this.setTokens(loginResponse.accessToken, loginResponse.refreshToken);
    console.log('💾 AuthService: 토큰 저장 완료');
    
    return loginResponse;
  }

  // 로그아웃
  async logout(): Promise<void> {
    try {
      const token = this.getAccessToken();
      if (token) {
        await fetch(`${this.baseUrl}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });
      }
    } catch (error) {
      console.warn('Logout request failed:', error);
    } finally {
      this.clearTokens();
    }
  }

  // 토큰 갱신
  async refreshToken(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      console.log('🔄 AuthService: Refresh token이 없음');
      return false;
    }

    console.log('🔄 AuthService: 토큰 갱신 시도 시작');
    
    try {
      const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refreshToken }),
      });

      console.log('📡 AuthService: 토큰 갱신 응답 상태:', response.status);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        console.error('❌ AuthService: 토큰 갱신 실패:', error);
        return false;
      }

      const refreshResponse: LoginResponse = await response.json();
      console.log('✅ AuthService: 토큰 갱신 성공');
      this.setTokens(refreshResponse.accessToken, refreshResponse.refreshToken);
      return true;
    } catch (error) {
      console.error('❌ AuthService: 토큰 갱신 중 네트워크 오류:', error);
      return false;
    }
  }

  // 토큰 검증 및 사용자 정보 조회
  async validateToken(): Promise<TokenValidationResponse> {
    const token = this.getAccessToken();
    if (!token) {
      console.log('🔍 AuthService: Access token이 없음');
      return { valid: false };
    }

    console.log('🔍 AuthService: 토큰 검증 시도');
    
    try {
      const response = await fetch(`${this.baseUrl}/api/auth/validate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      console.log('📡 AuthService: 토큰 검증 응답 상태:', response.status);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        console.log('❌ AuthService: 토큰 검증 실패:', response.status, error);
        return { valid: false };
      }

      const validationResult = await response.json();
      console.log('✅ AuthService: 토큰 검증 성공');
      return validationResult;
    } catch (error) {
      console.error('❌ AuthService: 토큰 검증 중 네트워크 오류:', error);
      return { valid: false };
    }
  }

  // 현재 사용자 정보 조회
  async getCurrentUser(): Promise<User | null> {
    const validation = await this.validateToken();
    console.log('🔍 AuthService: 토큰 검증 결과:', {
      valid: validation.valid,
      hasUser: !!validation.user,
      user: validation.user,
      fullValidation: validation
    });
    
    if (!validation.valid) {
      console.log('❌ AuthService: 토큰이 유효하지 않음');
      return null;
    }
    
    if (!validation.user) {
      console.log('❌ AuthService: validation.user가 없음 - 서버 응답 구조 확인 필요');
      return null;
    }

    // 사용자 데이터 안전성 확인
    const userData = validation.user;
    const roles = Array.isArray(userData.roles) ? userData.roles : [];
    
    console.log('👤 AuthService: 사용자 데이터 처리:', {
      id: userData.id,
      username: userData.username,
      email: userData.email,
      roles: roles
    });
    
    // MCP Client에서 권한 정보 조회
    const permissions = await this.getUserPermissions(roles);
    
    const finalUser = {
      id: userData.id || 0,
      username: userData.username || '',
      email: userData.email || '',
      fullName: userData.fullName || userData.username || 'Unknown User',
      roles: roles,
      permissions: Array.isArray(permissions) ? permissions : [],
      isActive: userData.isActive ?? true,
    };
    
    console.log('✅ AuthService: 최종 사용자 객체 생성:', finalUser);
    return finalUser;
  }

  // MCP Client에서 사용자 권한 정보 조회
  private async getUserPermissions(roles: string[]): Promise<string[]> {
    try {
      const token = this.getAccessToken();
      if (!token || !Array.isArray(roles) || roles.length === 0) {
        return [];
      }

      const response = await fetch('/api/auth/permissions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ roles }),
      });

      if (!response.ok) {
        console.warn('Failed to fetch permissions:', response.status);
        return [];
      }

      const data = await response.json();
      return Array.isArray(data.permissions) ? data.permissions : [];
    } catch (error) {
      console.warn('Error fetching permissions:', error);
      return [];
    }
  }

  // 토큰 관리 메서드들
  private setTokens(accessToken: string, refreshToken: string): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem(this.tokenKey, accessToken);
      localStorage.setItem(this.refreshTokenKey, refreshToken);
      console.log('💾 AuthService: 토큰 localStorage에 저장 완료');
    } else {
      console.warn('⚠️ AuthService: window 객체가 없어 토큰 저장 불가 (SSR 환경)');
    }
  }

  getAccessToken(): string | null {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem(this.tokenKey);
      console.log('🔑 AuthService: Access token 조회:', token ? '존재함' : '없음');
      return token;
    }
    console.log('🔑 AuthService: window 객체가 없어 토큰 조회 불가 (SSR 환경)');
    return null;
  }

  private getRefreshToken(): string | null {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem(this.refreshTokenKey);
      console.log('🔄 AuthService: Refresh token 조회:', token ? '존재함' : '없음');
      return token;
    }
    console.log('🔄 AuthService: window 객체가 없어 refresh token 조회 불가 (SSR 환경)');
    return null;
  }

  clearTokens(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(this.tokenKey);
      localStorage.removeItem(this.refreshTokenKey);
      console.log('🗑️ AuthService: 토큰 localStorage에서 삭제 완료');
    } else {
      console.log('🗑️ AuthService: window 객체가 없어 토큰 삭제 불가 (SSR 환경)');
    }
  }

  // HTTP 요청에 인증 헤더 추가하는 헬퍼
  getAuthHeaders(): Record<string, string> {
    const token = this.getAccessToken();
    if (token) {
      return {
        'Authorization': `Bearer ${token}`,
      };
    }
    return {};
  }

  // 인증이 필요한 fetch 요청 래퍼
  async authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
    const headers = {
      ...options.headers,
      ...this.getAuthHeaders(),
    };

    const response = await fetch(url, {
      ...options,
      headers,
    });

    // 401 응답 시 토큰 갱신 시도
    if (response.status === 401) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        // 갱신된 토큰으로 재시도
        const newHeaders = {
          ...options.headers,
          ...this.getAuthHeaders(),
        };
        return fetch(url, {
          ...options,
          headers: newHeaders,
        });
      }
    }

    return response;
  }
}

export const authService = new AuthService();
