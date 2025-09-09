'use client';

import { useState, FormEvent, ChangeEvent } from 'react';
import { ProcessingMode } from '@/app/_lib/types';

interface ChatInputProps {
  onSubmit: (url: string, mode: ProcessingMode) => void;
  isProcessing: boolean;
}

export default function ChatInput({ onSubmit, isProcessing }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<ProcessingMode>('auto');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    
    if (!input.trim() || isProcessing) return;
    
    // URL 형식 간단 검증
    const urlPattern = /^https?:\/\/.+/i;
    if (!urlPattern.test(input.trim())) {
      alert('올바른 URL을 입력해주세요 (http:// 또는 https://로 시작)');
      return;
    }
    
    onSubmit(input.trim(), mode);
    setInput('');
  };

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleModeChange = (e: ChangeEvent<HTMLInputElement>) => {
    setMode(e.target.value as ProcessingMode);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <div className="input-container">
      <form onSubmit={handleSubmit} className="input-form">
        <div className="input-wrapper">
          <div className="mode-selector">
            <label className="mode-option">
              <input
                type="radio"
                name="mode"
                value="auto"
                checked={mode === 'auto'}
                onChange={handleModeChange}
                disabled={isProcessing}
              />
              AI 자동 분석
            </label>
            <label className="mode-option">
              <input
                type="radio"
                name="mode"
                value="basic"
                checked={mode === 'basic'}
                onChange={handleModeChange}
                disabled={isProcessing}
              />
              기본 크롤링
            </label>
          </div>
          <textarea
            className="input-field"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="분석할 웹사이트 URL을 입력하세요... (예: https://example.com)"
            disabled={isProcessing}
            rows={1}
          />
        </div>
        <button
          type="submit"
          className="submit-button"
          disabled={!input.trim() || isProcessing}
        >
          {isProcessing ? (
            <>
              <div className="loading-spinner" style={{ marginRight: '0.5rem' }} />
              처리중...
            </>
          ) : (
            '분석 시작'
          )}
        </button>
      </form>
    </div>
  );
}
