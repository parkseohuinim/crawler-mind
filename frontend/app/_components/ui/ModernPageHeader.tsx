'use client';

import React from 'react';

interface ModernPageHeaderProps {
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  status?: {
    text: string;
    isActive?: boolean;
  };
  action?: {
    text: string;
    icon?: React.ReactNode;
    onClick: () => void;
    href?: string;
  };
  className?: string;
}

export default function ModernPageHeader({
  title,
  subtitle,
  icon,
  status,
  action,
  className = ''
}: ModernPageHeaderProps) {
  return (
    <div className={`modern-page-header ${className}`}>
      <div className="modern-page-header-content">
        <div className="modern-page-header-left">
          <div className="modern-page-header-icon">
            {icon}
          </div>
          <div className="modern-page-header-text">
            <h1 className="modern-page-title">{title}</h1>
            {subtitle && (
              <p className="modern-page-subtitle">{subtitle}</p>
            )}
          </div>
        </div>
        
        {(status || action) && (
          <div className="modern-page-header-right">
            {status && (
              <div className="modern-page-status">
                <div className={`modern-page-status-icon ${status.isActive ? 'active' : ''}`}></div>
                {status.text}
              </div>
            )}
            
            {action && (
              <button
                className="modern-page-action"
                onClick={action.onClick}
                type="button"
              >
                {action.icon && <span>{action.icon}</span>}
                {action.text}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
