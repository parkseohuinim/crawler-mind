'use client';

import React from 'react';

interface ModernFormProps {
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  onSubmit?: (e: React.FormEvent) => void;
  className?: string;
}

export default function ModernForm({
  title,
  subtitle,
  icon,
  children,
  onSubmit,
  className = ''
}: ModernFormProps) {
  return (
    <div className={`modern-form-container ${className}`}>
      <div className="modern-form-header">
        <div className="modern-form-icon">
          {icon}
        </div>
        <div>
          <h2 className="modern-form-title">{title}</h2>
          {subtitle && (
            <p className="modern-form-subtitle">{subtitle}</p>
          )}
        </div>
      </div>
      
      <form onSubmit={onSubmit}>
        {children}
      </form>
    </div>
  );
}

// 폼 그룹 컴포넌트
interface ModernFormGroupProps {
  children: React.ReactNode;
  className?: string;
}

export function ModernFormGroup({ children, className = '' }: ModernFormGroupProps) {
  return (
    <div className={`modern-form-group ${className}`}>
      {children}
    </div>
  );
}

// 폼 행 컴포넌트
interface ModernFormRowProps {
  children: React.ReactNode;
  className?: string;
}

export function ModernFormRow({ children, className = '' }: ModernFormRowProps) {
  return (
    <div className={`modern-form-row ${className}`}>
      {children}
    </div>
  );
}

// 라벨 컴포넌트
interface ModernFormLabelProps {
  children: React.ReactNode;
  htmlFor?: string;
  required?: boolean;
  className?: string;
}

export function ModernFormLabel({ 
  children, 
  htmlFor, 
  required = false, 
  className = '' 
}: ModernFormLabelProps) {
  return (
    <label 
      htmlFor={htmlFor} 
      className={`modern-form-label ${required ? 'required' : ''} ${className}`}
    >
      {children}
    </label>
  );
}

// 입력 필드 컴포넌트
interface ModernFormInputProps {
  type?: string;
  id?: string;
  name?: string;
  value?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  maxLength?: number;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
  className?: string;
  error?: string;
  help?: string;
}

export function ModernFormInput({
  type = 'text',
  id,
  name,
  value,
  placeholder,
  required = false,
  disabled = false,
  maxLength,
  onChange,
  onBlur,
  className = '',
  error,
  help
}: ModernFormInputProps) {
  return (
    <div>
      <input
        type={type}
        id={id}
        name={name}
        value={value}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        maxLength={maxLength}
        onChange={onChange}
        onBlur={onBlur}
        className={`modern-form-input ${className}`}
      />
      {error && (
        <div className="modern-form-error">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
          {error}
        </div>
      )}
      {help && !error && (
        <div className="modern-form-help">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          {help}
        </div>
      )}
    </div>
  );
}

// 텍스트 영역 컴포넌트
interface ModernFormTextareaProps {
  id?: string;
  name?: string;
  value?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onBlur?: (e: React.FocusEvent<HTMLTextAreaElement>) => void;
  className?: string;
  error?: string;
  help?: string;
  rows?: number;
}

export function ModernFormTextarea({
  id,
  name,
  value,
  placeholder,
  required = false,
  disabled = false,
  onChange,
  onBlur,
  className = '',
  error,
  help,
  rows = 4
}: ModernFormTextareaProps) {
  return (
    <div>
      <textarea
        id={id}
        name={name}
        value={value}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        onChange={onChange}
        onBlur={onBlur}
        className={`modern-form-textarea ${className}`}
        rows={rows}
      />
      {error && (
        <div className="modern-form-error">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
          {error}
        </div>
      )}
      {help && !error && (
        <div className="modern-form-help">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          {help}
        </div>
      )}
    </div>
  );
}

// 셀렉트 박스 컴포넌트
interface ModernFormSelectProps {
  id?: string;
  name?: string;
  value?: string;
  required?: boolean;
  disabled?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  onBlur?: (e: React.FocusEvent<HTMLSelectElement>) => void;
  className?: string;
  error?: string;
  help?: string;
  children: React.ReactNode;
}

export function ModernFormSelect({
  id,
  name,
  value,
  required = false,
  disabled = false,
  onChange,
  onBlur,
  className = '',
  error,
  help,
  children
}: ModernFormSelectProps) {
  return (
    <div>
      <select
        id={id}
        name={name}
        value={value}
        required={required}
        disabled={disabled}
        onChange={onChange}
        onBlur={onBlur}
        className={`modern-form-select ${className}`}
      >
        {children}
      </select>
      {error && (
        <div className="modern-form-error">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
          {error}
        </div>
      )}
      {help && !error && (
        <div className="modern-form-help">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          {help}
        </div>
      )}
    </div>
  );
}

// 액션 버튼 그룹 컴포넌트
interface ModernFormActionsProps {
  children: React.ReactNode;
  className?: string;
}

export function ModernFormActions({ children, className = '' }: ModernFormActionsProps) {
  return (
    <div className={`modern-form-actions ${className}`}>
      {children}
    </div>
  );
}

// 버튼 컴포넌트
interface ModernFormButtonProps {
  type?: 'button' | 'submit' | 'reset';
  variant?: 'primary' | 'secondary' | 'danger';
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  icon?: React.ReactNode;
}

export function ModernFormButton({
  type = 'button',
  variant = 'primary',
  children,
  onClick,
  disabled = false,
  loading = false,
  className = '',
  icon
}: ModernFormButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`modern-form-button ${variant} ${loading ? 'loading' : ''} ${className}`}
    >
      {icon && !loading && (
        <span>{icon}</span>
      )}
      <span>{children}</span>
    </button>
  );
}
