'use client';

import React, { useState, useEffect } from 'react';
import { useDailyCrawling, DailyCrawlingOptions } from '@/app/_lib/contexts/DailyCrawlingContext';
import ModernPageHeader from '@/app/_components/ui/ModernPageHeader';

export default function DailyCrawlingPage() {
  const {
    currentTask,
    taskHistory,
    isRunning,
    startCrawling,
    cancelCrawling,
    clearTask,
    addToast,
  } = useDailyCrawling();

  // Options state
  const [mode, setMode] = useState<'parallel' | 'sequential'>('parallel');
  const [concurrency, setConcurrency] = useState<string>('3');
  const [forceRecrawl, setForceRecrawl] = useState(true);
  const [updateMenuLinks, setUpdateMenuLinks] = useState(true);
  const [limit, setLimit] = useState<string>('');
  const [urlIds, setUrlIds] = useState<string>('');
  
  // Stats
  const [stats, setStats] = useState<{
    total: number;
    active: number;
    success: number;
    failed: number;
    pending: number;
  } | null>(null);

  // Fetch stats on mount
  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/daily-crawling/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const handleStartCrawling = async () => {
    // URL IDs 파싱 (콤마 또는 공백으로 구분된 숫자 목록)
    const parsedUrlIds = urlIds
      .split(/[\s,]+/)
      .map(id => parseInt(id.trim()))
      .filter(id => !isNaN(id));

    const options: DailyCrawlingOptions = {
      mode,
      concurrency: parseInt(concurrency) || 1,
      forceRecrawl,
      updateMenuLinks,
      limit: limit ? parseInt(limit) : undefined,
      urlIds: parsedUrlIds.length > 0 ? parsedUrlIds : undefined,
    };
    
    await startCrawling(options);
  };

  const handleDownload = async (filePath: string) => {
    try {
      const response = await fetch(`/api/daily-crawling/download?file=${encodeURIComponent(filePath)}`);
      if (!response.ok) {
        throw new Error('Download failed');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filePath.split('/').pop() || 'result.json';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      addToast({
        type: 'success',
        title: '다운로드 완료',
        message: '결과 파일이 다운로드되었습니다',
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: '다운로드 실패',
        message: '파일 다운로드에 실패했습니다',
      });
    }
  };

  const handleCopyFailedIds = (failedItems: Array<{ id?: number; url: string; error: string }>) => {
    const ids = failedItems
      .map(item => item.id)
      .filter(id => id !== undefined)
      .join(', ');
    
    if (ids) {
      navigator.clipboard.writeText(ids);
      addToast({
        type: 'success',
        title: 'ID 복사 완료',
        message: '실패한 URL ID들이 클립보드에 복사되었습니다',
      });
      setUrlIds(ids); // 입력 필드에도 자동으로 넣어줌
    }
  };

  return (
    <div className="daily-crawling-page">
      <ModernPageHeader
        title="Daily 추출"
        subtitle="input_urls 테이블의 URL을 크롤링하고 결과를 JSON으로 출력합니다"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 0 1-9 9m9-9a9 9 0 0 0-9-9m9 9H3m9 9a9 9 0 0 1-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 0 1 9-9" />
          </svg>
        }
        status={{
          text: isRunning ? '실행 중' : '대기 중',
          isActive: isRunning
        }}
      />

      {/* Stats Section */}
      {stats && (
        <div className="stats-section">
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon total">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
              <div className="stat-info">
                <span className="stat-value">{stats.total.toLocaleString()}</span>
                <span className="stat-label">전체 URL</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon active">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <div className="stat-info">
                <span className="stat-value">{stats.active.toLocaleString()}</span>
                <span className="stat-label">활성 URL</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon success">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="16 12 12 8 8 12" />
                  <line x1="12" y1="16" x2="12" y2="8" />
                </svg>
              </div>
              <div className="stat-info">
                <span className="stat-value">{stats.success.toLocaleString()}</span>
                <span className="stat-label">성공</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon failed">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
              </div>
              <div className="stat-info">
                <span className="stat-value">{stats.failed.toLocaleString()}</span>
                <span className="stat-label">실패</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Options Section */}
      <div className="options-section">
        <div className="section-header">
          <h3>크롤링 옵션</h3>
        </div>
        <div className="options-grid">
          <div className="option-group">
            <label className="option-label">실행 모드</label>
            <div className="radio-group">
              <label className={`radio-option ${mode === 'parallel' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="mode"
                  value="parallel"
                  checked={mode === 'parallel'}
                  onChange={() => setMode('parallel')}
                  disabled={isRunning}
                />
                <span className="radio-text">병렬</span>
              </label>
              <label className={`radio-option ${mode === 'sequential' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="mode"
                  value="sequential"
                  checked={mode === 'sequential'}
                  onChange={() => setMode('sequential')}
                  disabled={isRunning}
                />
                <span className="radio-text">순차</span>
              </label>
            </div>
          </div>

          {mode === 'parallel' && (
            <div className="option-group">
              <label className="option-label">동시 처리 수</label>
              <input
                type="text"
                className="option-input"
                value={concurrency}
                onChange={(e) => {
                  const val = e.target.value;
                  // 숫자만 입력 가능하도록 필터링
                  if (val === '' || /^\d+$/.test(val)) {
                    setConcurrency(val);
                  }
                }}
                onBlur={() => {
                  const num = parseInt(concurrency);
                  if (concurrency === '' || isNaN(num) || num < 1) {
                    setConcurrency('3');
                  } else if (num > 10) {
                    setConcurrency('10');
                  } else {
                    setConcurrency(num.toString());
                  }
                }}
                placeholder="3"
                disabled={isRunning}
              />
              <span className="option-hint">1~10 사이 값</span>
            </div>
          )}

          <div className="option-group">
            <label className="option-label">URL 개수 제한</label>
            <input
              type="text"
              className="option-input"
              value={limit}
              onChange={(e) => {
                const val = e.target.value;
                // 숫자만 입력 가능하도록 필터링 (완전 비우기 가능)
                if (val === '' || /^\d+$/.test(val)) {
                  setLimit(val);
                }
              }}
              onBlur={() => {
                if (limit === '') return;
                const num = parseInt(limit);
                if (isNaN(num) || num < 1) {
                  setLimit(''); // 1 미만이면 '전체'로 초기화
                } else {
                  setLimit(num.toString()); // '05' -> '5' 정규화
                }
              }}
              placeholder="전체"
              disabled={isRunning || urlIds.trim().length > 0}
            />
            <span className="option-hint">비워두면 전체 크롤링</span>
          </div>

          <div className="option-group">
            <label className="option-label">특정 URL ID 추출</label>
            <input
              type="text"
              className="option-input"
              value={urlIds}
              onChange={(e) => setUrlIds(e.target.value)}
              onBlur={() => {
                // 숫자, 콤마, 공백 제외한 문자 제거 및 형식 정리
                const cleaned = urlIds
                  .replace(/[^0-9,\s]/g, '')
                  .split(/[\s,]+/)
                  .map(id => id.trim())
                  .filter(id => id.length > 0)
                  .join(', ');
                setUrlIds(cleaned);
              }}
              placeholder="예: 1, 2, 3"
              disabled={isRunning}
            />
            <span className="option-hint">콤마(,)나 공백으로 구분된 ID 목록 (입력 시 'URL 개수 제한' 무시됨)</span>
          </div>

          <div className="option-group checkbox-group">
            <label className="checkbox-option">
              <input
                type="checkbox"
                checked={forceRecrawl}
                onChange={(e) => setForceRecrawl(e.target.checked)}
                disabled={isRunning}
              />
              <span className="checkbox-text">이미 성공한 URL도 재크롤링</span>
            </label>
          </div>

          <div className="option-group checkbox-group">
            <label className="checkbox-option">
              <input
                type="checkbox"
                checked={updateMenuLinks}
                onChange={(e) => setUpdateMenuLinks(e.target.checked)}
                disabled={isRunning}
              />
              <span className="checkbox-text">menu_links DB 업데이트</span>
            </label>
          </div>
        </div>

        <div className="action-buttons">
          {!isRunning ? (
            <button
              className="btn-primary btn-start"
              onClick={handleStartCrawling}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Daily 추출 시작
            </button>
          ) : (
            <button
              className="btn-danger btn-cancel"
              onClick={cancelCrawling}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="6" y="6" width="12" height="12" />
              </svg>
              연결 중단
            </button>
          )}
          
          <button
            className="btn-secondary btn-refresh"
            onClick={fetchStats}
            disabled={isRunning}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            통계 새로고침
          </button>
        </div>
      </div>

      {/* Progress Section */}
      {currentTask && (
        <div className="progress-section">
          <div className="section-header">
            <h3>진행 상황</h3>
            {currentTask.status === 'completed' && (
              <button className="btn-text" onClick={clearTask}>
                닫기
              </button>
            )}
          </div>
          
          <div className="progress-content">
            <div className="progress-bar-container">
              <div 
                className={`progress-bar ${currentTask.status}`}
                style={{ width: `${currentTask.progress}%` }}
              />
            </div>
            <div className="progress-info">
              <span className="progress-percent">{currentTask.progress}%</span>
              <span className="progress-message">{currentTask.message}</span>
            </div>
            
            {currentTask.currentUrl && (
              <div className="current-url">
                <span className="url-label">현재 URL:</span>
                <span className="url-value">{currentTask.currentUrl}</span>
              </div>
            )}
            
            {currentTask.status === 'completed' && (
              <div className="completion-info">
                <div className="completion-stats">
                  <span className="stat success">✓ {currentTask.successCount} 성공</span>
                  <span className="stat failed">✗ {currentTask.failedCount} 실패</span>
                </div>
                <div className="completion-actions">
                  {currentTask.jsonFilePath && (
                    <button
                      className="btn-primary btn-download"
                      onClick={() => handleDownload(currentTask.jsonFilePath!)}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      결과 다운로드
                    </button>
                  )}
                  {currentTask.failedItems && currentTask.failedItems.length > 0 && (
                    <button
                      className="btn-secondary btn-copy-failed"
                      onClick={() => handleCopyFailedIds(currentTask.failedItems!)}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                      </svg>
                      실패 ID 복사
                    </button>
                  )}
                </div>
              </div>
            )}
            
            {currentTask.status === 'completed' && currentTask.failedItems && currentTask.failedItems.length > 0 && (
              <div className="failed-items-list">
                <div className="list-header">실패 상세 내역</div>
                <div className="list-content">
                  {currentTask.failedItems.map((item, idx) => (
                    <div key={idx} className="failed-item">
                      <span className="item-id">ID: {item.id}</span>
                      <span className="item-url">{item.url}</span>
                      <span className="item-error">{item.error}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {currentTask.status === 'failed' && currentTask.error && (
              <div className="error-info">
                <span className="error-label">오류:</span>
                <span className="error-message">{currentTask.error}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* History Section */}
      {taskHistory.length > 0 && (
        <div className="history-section">
          <div className="section-header">
            <h3>최근 작업 기록</h3>
          </div>
          <div className="history-list">
            {taskHistory.map((task) => (
              <div key={task.taskId} className={`history-item ${task.status}`}>
                <div className="history-time">
                  {new Date(task.createdAt).toLocaleString('ko-KR', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
                <div className="history-info">
                  <span className="history-status">
                    {task.status === 'completed' ? '완료' : '실패'}
                  </span>
                  <span className="history-result">
                    {task.totalUrls}개 중 {task.successCount}개 성공
                  </span>
                </div>
                {task.jsonFilePath && task.status === 'completed' && (
                  <button
                    className="btn-icon btn-download-small"
                    onClick={() => handleDownload(task.jsonFilePath!)}
                    title="다운로드"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

