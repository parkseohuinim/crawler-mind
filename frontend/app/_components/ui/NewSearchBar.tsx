'use client';

import React, { useState, useEffect } from 'react';

interface NewSearchBarProps {
  onSearch: (searchTerm: string) => void;
  onReset: () => void;
  defaultValue?: string;
  hasSearchTerm?: boolean;
  placeholder?: string;
  title?: string;
  loading?: boolean;
}

export default function NewSearchBar({ 
  onSearch, 
  onReset, 
  defaultValue = '', 
  hasSearchTerm = false, 
  placeholder = '검색어를 입력하세요...',
  title = '검색',
  loading = false
}: NewSearchBarProps) {
  const [inputValue, setInputValue] = useState(defaultValue);
  
  // defaultValue가 변경되면 inputValue도 업데이트
  useEffect(() => {
    setInputValue(defaultValue);
  }, [defaultValue]);
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      onSearch(inputValue.trim());
    }
  };

  const handleReset = () => {
    setInputValue('');
    onReset();
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit(e);
    }
  };

  return (
    <div className="new-search-area">
      <div className="search-area-header">
        <div className="search-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <path d="m21 21-4.35-4.35"></path>
          </svg>
        </div>
        <h2 className="search-title">{title}</h2>
      </div>

      <div className="new-search-form-container">
        <form onSubmit={handleSubmit} className="new-search-form">
          <input
            type="text"
            name="search"
            placeholder={placeholder}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            className="new-search-input"
            disabled={loading}
          />
          <button 
            type="submit" 
            className={`new-search-button ${loading ? 'loading' : ''}`}
            disabled={loading || !inputValue.trim()}
          >
            {!loading && (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8"></circle>
                  <path d="m21 21-4.35-4.35"></path>
                </svg>
                검색
              </>
            )}
          </button>
          {hasSearchTerm && (
            <button 
              onClick={handleReset} 
              className="new-reset-button"
              type="button"
              disabled={loading}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18"></path>
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                <line x1="10" y1="11" x2="10" y2="17"></line>
                <line x1="14" y1="11" x2="14" y2="17"></line>
              </svg>
              초기화
            </button>
          )}
        </form>

        {hasSearchTerm && (
          <div className="search-status">
            <div className="search-status-indicator"></div>
            <span className="search-status-text">검색 결과를 표시 중입니다</span>
          </div>
        )}
      </div>
    </div>
  );
}
