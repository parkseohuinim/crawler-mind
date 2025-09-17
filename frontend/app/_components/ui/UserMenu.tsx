'use client';

import React, { useState } from 'react';
import { useAuth } from '../../_lib/auth/auth-context';

export default function UserMenu() {
  const { user, logout, isAuthenticated } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  if (!isAuthenticated || !user) {
    return null;
  }

  const handleLogout = () => {
    logout();
    setIsMenuOpen(false);
  };

  return (
    <div className="user-menu">
      <button
        className="user-menu-button"
        onClick={() => setIsMenuOpen(!isMenuOpen)}
      >
        <div className="user-avatar">
          {user.fullName.charAt(0).toUpperCase()}
        </div>
        <span className="user-name">{user.fullName}</span>
        <svg
          className={`chevron ${isMenuOpen ? 'open' : ''}`}
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M4 6L8 10L12 6"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {isMenuOpen && (
        <div className="user-menu-dropdown">
          <div className="user-info">
            <div className="user-details">
              <p className="user-full-name">{user.fullName}</p>
              <p className="user-email">{user.email}</p>
              <p className="user-username">@{user.username}</p>
            </div>
            <div className="user-roles">
              <p className="roles-label">역할:</p>
              <div className="roles-list">
                {user.roles.map(role => (
                  <span key={role} className="role-badge">
                    {role}
                  </span>
                ))}
              </div>
            </div>
          </div>
          
          <div className="menu-separator"></div>
          
          <div className="menu-actions">
            <button
              className="menu-item logout-button"
              onClick={handleLogout}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path
                  d="M6 2H3C2.44772 2 2 2.44772 2 3V13C2 13.5523 2.44772 14 3 14H6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M11 6L14 8L11 10"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M14 8H6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              로그아웃
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
