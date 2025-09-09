'use client';

import React, { useState, useEffect } from 'react';

interface SearchBarProps {
  onSearch: (searchTerm: string) => void;
  onReset: () => void;
  defaultValue?: string;
  hasSearchTerm?: boolean;
  placeholder?: string;
}

export default function SearchBar({ onSearch, onReset, defaultValue = '', hasSearchTerm = false, placeholder = '검색...' }: SearchBarProps) {
  const [inputValue, setInputValue] = useState(defaultValue);
  
  // defaultValue가 변경되면 inputValue도 업데이트
  useEffect(() => {
    setInputValue(defaultValue);
  }, [defaultValue]);
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(inputValue);
  };

  const handleReset = () => {
    setInputValue(''); // 입력창 텍스트 초기화
    onReset(); // 부모 컴포넌트 초기화 함수 호출
  };

  return (
    <div className="search-container">
      <form onSubmit={handleSubmit} className="search-form">
        <input
          type="text"
          name="search"
          placeholder={placeholder}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="search-input"
        />
        <button type="submit" className="search-button">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <path d="m21 21-4.35-4.35"></path>
          </svg>
          검색
        </button>
      </form>
      {hasSearchTerm && (
        <button 
          onClick={handleReset} 
          className="reset-button"
          type="button"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 6h18"></path>
            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
            <line x1="10" y1="11" x2="10" y2="17"></line>
            <line x1="14" y1="11" x2="14" y2="17"></line>
          </svg>
          초기화
        </button>
      )}
    </div>
  );
}
