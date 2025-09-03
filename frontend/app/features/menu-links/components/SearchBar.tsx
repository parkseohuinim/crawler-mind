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
  
  // 디버깅을 위한 로그
  console.log('SearchBar props:', { defaultValue, hasSearchTerm, inputValue });
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Search submitted:', inputValue);
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
          검색
        </button>
      </form>
      {hasSearchTerm && (
        <button 
          onClick={handleReset} 
          className="reset-button"
          type="button"
        >
          초기화
        </button>
      )}
    </div>
  );
}
