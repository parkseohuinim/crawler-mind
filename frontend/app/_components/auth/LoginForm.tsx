'use client';

import React, { useState } from 'react';
import { useAuth } from '../../_lib/auth/auth-context';

interface LoginFormProps {
  onSuccess?: () => void;
}

function LoginForm({ onSuccess }: LoginFormProps) {
  const { login, isLoading, error, clearError } = useAuth();
  const [credentials, setCredentials] = useState({
    usernameOrEmail: '',
    password: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError(); // 이전 에러 클리어

    try {
      console.log('🔑 로그인 시도:', credentials.usernameOrEmail);
      await login(credentials);
      console.log('✅ 로그인 성공!');
      onSuccess?.();
    } catch (err) {
      console.error('❌ 로그인 실패:', err);
      // 에러는 AuthContext에서 처리되므로 여기서는 별도 처리 불필요
      console.log('🔴 LoginForm: 에러는 AuthContext에서 처리됨');
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setCredentials(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  return (
    <div className="login-form">
      <div className="login-container">
        <div className="login-header">
          <h2>로그인</h2>
          <p>Crawler Mind에 로그인하세요</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form-content">
          <div className="form-group">
            <label htmlFor="usernameOrEmail">사용자명 또는 이메일</label>
            <input
              type="text"
              id="usernameOrEmail"
              name="usernameOrEmail"
              value={credentials.usernameOrEmail}
              onChange={handleChange}
              required
              disabled={isLoading}
              placeholder="사용자명 또는 이메일을 입력하세요"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">비밀번호</label>
            <input
              type="password"
              id="password"
              name="password"
              value={credentials.password}
              onChange={handleChange}
              required
              disabled={isLoading}
              placeholder="비밀번호를 입력하세요"
            />
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading || !credentials.usernameOrEmail || !credentials.password}
            className="login-button"
          >
            {isLoading ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <div className="login-footer">
          <p>테스트 계정:</p>
          <ul>
            <li>관리자: admin / admin123</li>
            <li>사용자: user / user123</li>
            <li>매니저: manager / manager123</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default React.memo(LoginForm);
