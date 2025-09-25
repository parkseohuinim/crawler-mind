'use client';

import { useState, FormEvent, ChangeEvent } from 'react';

interface ChatInputProps {
  onSubmit: (url: string) => void;
  isProcessing: boolean;
}

export default function ChatInput({ onSubmit, isProcessing }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    
    if (!input.trim() || isProcessing) return;
    
    // URL 형식 간단 검증
    const urlPattern = /^https?:\/\/.+/i;
    if (!urlPattern.test(input.trim())) {
      alert('올바른 URL을 입력해주세요 (http:// 또는 https://로 시작)');
      return;
    }
    
    onSubmit(input.trim());
    setInput('');
  };

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };


  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <div className="home-input-container">
      <form onSubmit={handleSubmit} className="home-input-form">
        <div className="home-input-wrapper">
          <div className="input-field-container">
            <textarea
              className="home-input-field"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="분석할 웹사이트 URL을 입력하세요... (예: https://example.com)"
              disabled={isProcessing}
              rows={1}
            />
            <button
              type="submit"
              className="home-submit-button"
              disabled={!input.trim() || isProcessing}
            >
              {isProcessing ? (
                <>
                  <div className="loading-spinner" />
                  <span>처리중...</span>
                </>
              ) : (
                <>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 2L11 13"></path>
                    <path d="M22 2L15 22L11 13L2 9L22 2Z"></path>
                  </svg>
                  <span>분석 시작</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
