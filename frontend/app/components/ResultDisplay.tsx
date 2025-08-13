'use client';

import { CrawlingResult } from '../types';

interface ResultDisplayProps {
  result: CrawlingResult;
}

export default function ResultDisplay({ result }: ResultDisplayProps) {
  if (result.error) {
    return (
      <div className="result-container">
        <div className="result-title">❌ 오류 발생</div>
        <div style={{ color: '#f56565', fontSize: '0.875rem' }}>
          {result.error}
        </div>
      </div>
    );
  }

  return (
    <div className="result-container">
      <div className="result-title">📊 크롤링 결과</div>
      
      {result.title && (
        <div className="result-item">
          <span className="result-label">페이지 제목:</span>
          <span className="result-value">{result.title}</span>
        </div>
      )}
      
      {result.textLength != null && result.textLength !== undefined && (
        <div className="result-item">
          <span className="result-label">텍스트 길이:</span>
          <span className="result-value">{result.textLength.toLocaleString()}자</span>
        </div>
      )}
      
      {result.linkCount !== undefined && (
        <div className="result-item">
          <span className="result-label">링크 개수:</span>
          <span className="result-value">{result.linkCount}개</span>
        </div>
      )}
      
      {result.summary && (
        <div className="result-item">
          <span className="result-label">요약:</span>
          <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', lineHeight: '1.5' }}>
            {result.summary}
          </div>
        </div>
      )}
      
      {result.links && result.links.length > 0 && (
        <div className="result-links">
          <div className="result-links-title">발견된 링크들:</div>
          <div className="result-links-list">
            {result.links.slice(0, 10).map((link, index) => {
              const safeHref = link && link.trim().toLowerCase().startsWith('javascript:') ? '#' : link;
              return (
                <a
                  key={index}
                  href={safeHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="result-link"
                >
                  {link}
                </a>
              );
            })}
            {result.links.length > 10 && (
              <div style={{ color: '#a0aec0', fontSize: '0.75rem', padding: '0.5rem 0' }}>
                ... 그 외 {result.links.length - 10}개 링크
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
