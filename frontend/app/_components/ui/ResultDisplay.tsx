'use client';

import { RAGCrawlingResult } from '@/app/_lib/types';

interface ResultDisplayProps {
  result: RAGCrawlingResult[] | { error: string };
}

export default function ResultDisplay({ result }: ResultDisplayProps) {
  // 에러 케이스 처리
  if ('error' in result) {
    return (
      <div className="result-container">
        <div className="result-title" style={{ color: '#f56565' }}>오류 발생</div>
        <div style={{ color: '#f56565', fontSize: '0.875rem' }}>
          {result.error}
        </div>
      </div>
    );
  }

  if (!result || result.length === 0) {
    return (
      <div className="result-container">
        <div className="result-title">RAG 크롤링 결과</div>
        <div style={{ color: '#a0aec0', fontSize: '0.875rem' }}>
          결과가 없습니다.
        </div>
      </div>
    );
  }

  return (
    <div className="result-container">
      <div className="result-title">RAG 크롤링 결과 ({result.length}개)</div>
      
      {result.map((item, index) => (
        <div key={index} className="result-item" style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '0.5rem' }}>
          <div className="result-item">
            <span className="result-label">URL:</span>
            <a href={item.url} target="_blank" rel="noopener noreferrer" className="result-value" style={{ color: '#3182ce' }}>
              {item.url}
            </a>
          </div>
          
          {item.murl && (
            <div className="result-item">
              <span className="result-label">모바일 URL:</span>
              <a href={item.murl} target="_blank" rel="noopener noreferrer" className="result-value" style={{ color: '#3182ce' }}>
                {item.murl}
              </a>
            </div>
          )}
          
          <div className="result-item">
            <span className="result-label">제목:</span>
            <span className="result-value">{item.title}</span>
          </div>
          
          {item.hierarchy && item.hierarchy.length > 0 && (
            <div className="result-item">
              <span className="result-label">계층구조:</span>
              <span className="result-value">{item.hierarchy.join(' > ')}</span>
            </div>
          )}
          
          <div className="result-item">
            <span className="result-label">텍스트 길이:</span>
            <span className="result-value">{item.text.length.toLocaleString()}자</span>
          </div>
          
          {item.metadata?.images && item.metadata.images.length > 0 && (
            <div className="result-item">
              <span className="result-label">이미지 개수:</span>
              <span className="result-value">{item.metadata.images.length}개</span>
            </div>
          )}
          
          {item.metadata?.links && item.metadata.links.length > 0 && (
            <div className="result-item">
              <span className="result-label">링크 개수:</span>
              <span className="result-value">{item.metadata.links.length}개</span>
            </div>
          )}
          
          {item.error && (
            <div className="result-item">
              <span className="result-label" style={{ color: '#f56565' }}>오류:</span>
              <span className="result-value" style={{ color: '#f56565' }}>{item.error}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
