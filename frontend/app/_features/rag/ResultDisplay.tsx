'use client';

import { CrawlingResult } from '@/app/_lib/types';

interface ResultDisplayProps {
  result: CrawlingResult;
}

export default function ResultDisplay({ result }: ResultDisplayProps) {
  const downloadTextFile = (content: string, filename: string, mime: string) => {
    try {
      const blob = new Blob([content], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('파일 다운로드 실패:', e);
      alert('파일 다운로드 중 오류가 발생했습니다.');
    }
  };

  const handleDownloadJSON = () => {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    const HH = String(now.getHours()).padStart(2, '0');
    const MM = String(now.getMinutes()).padStart(2, '0');
    const timestamp = `${yyyy}-${mm}-${dd}_${HH}${MM}`;
    const filename = `rag_crawl_result_${timestamp}.json`;
    const payload: any = Array.isArray((result as any)?.json_data)
      ? (result as any).json_data
      : result;
    const json = JSON.stringify(payload, null, 2);
    downloadTextFile(json, filename, 'application/json;charset=utf-8');
  };

  // CSV 다운로드는 요구사항에 따라 제거됨

  if (result.error) {
    return (
      <div className="result-container">
        <div className="result-title">오류 발생</div>
        <div style={{ color: '#f56565', fontSize: '0.875rem' }}>
          {result.error}
        </div>
      </div>
    );
  }

  return (
    <div className="result-container">
      <div className="result-title">크롤링 결과</div>
      <div style={{ display: 'flex', gap: '0.5rem', margin: '0.75rem 0 1.25rem' }}>
        <button onClick={handleDownloadJSON} className="btn btn-primary" aria-label="결과 JSON 다운로드">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          결과 JSON 다운로드
        </button>
      </div>
      
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
