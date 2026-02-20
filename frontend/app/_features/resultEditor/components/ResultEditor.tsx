'use client';

import React, { useEffect, useCallback } from 'react';
import { useResultEditor } from '../hooks/useResultEditor';
import ModernPageHeader from '@/app/_components/ui/ModernPageHeader';

export default function ResultEditor() {
  const {
    step,
    files,
    selectedFile,
    setSelectedFile,
    searchQuery,
    setSearchQuery,
    searchField,
    setSearchField,
    searchResults,
    docInfo,
    originalText,
    modifiedText,
    setModifiedText,
    diffLines,
    diffStats,
    isLoading,
    isSaving,
    error,
    setError,
    successMessage,
    findText,
    replaceText,
    setReplaceText,
    useRegex,
    setUseRegex,
    matchCount,
    hasChanges,
    fetchFiles,
    searchDocs,
    loadDoc,
    handleFindTextChange,
    handleReplace,
    handleReplaceAll,
    checkedDocIds,
    toggleDocCheck,
    toggleAllDocs,
    batchFindText,
    setBatchFindText,
    batchReplaceText,
    setBatchReplaceText,
    batchUseRegex,
    setBatchUseRegex,
    batchResult,
    isBatchTextSearch,
    goToBatchConfirm,
    goBackFromBatch,
    executeBatchReplace,
    goToConfirm,
    goBackToEdit,
    goBackToSelect,
    saveChanges,
    resetModifiedText,
  } = useResultEditor();

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  useEffect(() => {
    if (selectedFile) {
      searchDocs(selectedFile, searchQuery, searchField);
    }
  }, [selectedFile, searchQuery, searchField, searchDocs]);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setSelectedFile(e.target.value);
      setSearchQuery('');
    },
    [setSelectedFile, setSearchQuery]
  );

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const searchFieldLabels: Record<string, string> = {
    all: '전체',
    docId: 'docId',
    title: '제목',
    text: '본문 내용',
  };

  return (
    <div className="re-page">
      <ModernPageHeader
        title="결과 데이터 편집기"
        subtitle="크롤링 결과 JSON의 text 필드를 검색, 수정, 삭제합니다"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        }
        status={{
          text: step === 'select' ? '문서 선택' : step === 'edit' ? '편집 중' : step === 'batch-confirm' ? '일괄 작업 확인' : '변경 확인',
          isActive: step !== 'select',
        }}
      />

      <div className="re-container">
        {error && (
          <div className="modern-error-banner">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            <span>{error}</span>
            <button className="re-error-close" onClick={() => setError(null)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          </div>
        )}

        {successMessage && (
          <div className="re-success-banner">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <span>{successMessage}</span>
          </div>
        )}

        {/* Step 1: 파일/문서 선택 */}
        {step === 'select' && (
          <div className="re-content">
            <div className="re-select-section">
              <div className="re-section-header">
                <div className="re-section-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14,2 14,8 20,8" /></svg>
                </div>
                <h3>결과 파일 선택</h3>
              </div>
              <select
                className="re-file-select"
                value={selectedFile}
                onChange={handleFileChange}
              >
                <option value="">파일을 선택하세요</option>
                {files.map((f) => (
                  <option key={f.filename} value={f.filename}>
                    {f.filename} ({f.doc_count}건, {formatFileSize(f.size_bytes)})
                  </option>
                ))}
              </select>
            </div>

            {selectedFile && (
              <div className="re-select-section">
                <div className="re-section-header">
                  <div className="re-section-icon re-section-icon-search">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
                  </div>
                  <h3>문서 검색</h3>
                  <span className="re-result-count">{searchResults.length}건</span>
                </div>
                <div className="re-search-row">
                  <div className="re-search-field-tabs">
                    {(['all', 'docId', 'title', 'text'] as const).map((field) => (
                      <button
                        key={field}
                        className={`re-search-field-tab ${searchField === field ? 'active' : ''}`}
                        onClick={() => setSearchField(field)}
                      >
                        {searchFieldLabels[field]}
                      </button>
                    ))}
                  </div>
                  <input
                    type="text"
                    className="re-search-input"
                    placeholder={
                      searchField === 'docId' ? 'docId로 검색...'
                      : searchField === 'title' ? '제목으로 검색...'
                      : searchField === 'text' ? '본문 내용으로 검색...'
                      : 'docId, 제목, 본문 내용으로 검색...'
                    }
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                {/* 일괄 작업 툴바 (본문 검색 시에만 표시) */}
                {isBatchTextSearch && searchResults.length > 0 && !isLoading && (
                  <div className="re-batch-toolbar">
                    <div className="re-batch-toolbar-header">
                      <label className="re-batch-select-all" onClick={toggleAllDocs}>
                        <input
                          type="checkbox"
                          checked={checkedDocIds.size === searchResults.length && searchResults.length > 0}
                          readOnly
                        />
                        전체 선택 ({checkedDocIds.size}/{searchResults.length})
                      </label>
                    </div>
                    {checkedDocIds.size > 0 && (
                      <div className="re-batch-actions">
                        <div className="re-batch-inputs">
                          <div className="re-batch-input-group">
                            <label>찾기</label>
                            <input
                              type="text"
                              className="re-batch-input"
                              value={batchFindText}
                              onChange={(e) => setBatchFindText(e.target.value)}
                              placeholder="치환/삭제할 텍스트..."
                            />
                          </div>
                          <div className="re-batch-input-group">
                            <label>바꾸기 (비우면 삭제)</label>
                            <input
                              type="text"
                              className="re-batch-input"
                              value={batchReplaceText}
                              onChange={(e) => setBatchReplaceText(e.target.value)}
                              placeholder="대체할 텍스트 (빈 값 = 삭제)"
                            />
                          </div>
                        </div>
                        <div className="re-batch-buttons">
                          <label className="re-fr-checkbox">
                            <input
                              type="checkbox"
                              checked={batchUseRegex}
                              onChange={(e) => setBatchUseRegex(e.target.checked)}
                            />
                            정규식
                          </label>
                          <button
                            className="re-btn re-btn-danger re-btn-sm"
                            onClick={goToBatchConfirm}
                            disabled={!batchFindText || checkedDocIds.size === 0}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 11 12 14 22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
                            {checkedDocIds.size}개 문서 일괄 {batchReplaceText ? '치환' : '삭제'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {isLoading ? (
                  <div className="re-loading">
                    <div className="modern-spinner"></div>
                    <p>검색 중...</p>
                  </div>
                ) : (
                  <div className="re-doc-list">
                    {searchResults.map((doc) => (
                      <div
                        key={doc.docId}
                        className={`re-doc-item ${checkedDocIds.has(doc.docId) ? 're-doc-item-checked' : ''}`}
                      >
                        {isBatchTextSearch && (
                          <div className="re-doc-checkbox" onClick={(e) => { e.stopPropagation(); toggleDocCheck(doc.docId); }}>
                            <input
                              type="checkbox"
                              checked={checkedDocIds.has(doc.docId)}
                              readOnly
                            />
                          </div>
                        )}
                        <div className="re-doc-item-body" onClick={() => loadDoc(selectedFile, doc.docId)}>
                          <div className="re-doc-item-header">
                            <span className="re-doc-id">{doc.docId}</span>
                            <span className="re-doc-text-length">{doc.textLength.toLocaleString()}자</span>
                          </div>
                          <div className="re-doc-title">{doc.title || '(제목 없음)'}</div>
                          <div className="re-doc-url">{doc.url}</div>
                          {doc.textSnippet && (
                            <div className="re-doc-snippet">{doc.textSnippet}</div>
                          )}
                        </div>
                      </div>
                    ))}
                    {searchResults.length === 0 && !isLoading && (
                      <div className="re-empty">검색 결과가 없습니다</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 2: 편집 */}
        {step === 'edit' && docInfo && (
          <div className="re-content">
            <div className="re-edit-header">
              <div className="re-edit-doc-info">
                <span className="re-doc-id">{docInfo.docId}</span>
                <span className="re-edit-title">{docInfo.title}</span>
                {docInfo.hierarchy.length > 0 && (
                  <span className="re-edit-hierarchy">{docInfo.hierarchy.join(' > ')}</span>
                )}
              </div>
              <button className="re-back-button" onClick={goBackToSelect}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
                목록으로
              </button>
            </div>

            {/* Find & Replace */}
            <div className="re-find-replace">
              <div className="re-fr-row">
                <div className="re-fr-input-group">
                  <label>찾기</label>
                  <input
                    type="text"
                    value={findText}
                    onChange={(e) => handleFindTextChange(e.target.value)}
                    placeholder="검색할 텍스트..."
                    className="re-fr-input"
                  />
                  {findText && (
                    <span className="re-fr-match-count">
                      {matchCount}건 일치
                    </span>
                  )}
                </div>
                <div className="re-fr-input-group">
                  <label>바꾸기</label>
                  <input
                    type="text"
                    value={replaceText}
                    onChange={(e) => setReplaceText(e.target.value)}
                    placeholder="대체할 텍스트..."
                    className="re-fr-input"
                  />
                </div>
                <div className="re-fr-actions">
                  <label className="re-fr-checkbox">
                    <input
                      type="checkbox"
                      checked={useRegex}
                      onChange={(e) => setUseRegex(e.target.checked)}
                    />
                    정규식
                  </label>
                  <button
                    className="re-fr-btn"
                    onClick={handleReplace}
                    disabled={!findText || matchCount === 0}
                  >
                    치환
                  </button>
                  <button
                    className="re-fr-btn re-fr-btn-all"
                    onClick={handleReplaceAll}
                    disabled={!findText || matchCount === 0}
                  >
                    전체 치환
                  </button>
                </div>
              </div>
            </div>

            {/* Editor Area */}
            <div className="re-editor-area">
              <div className="re-editor-label">
                <span>텍스트 편집</span>
                <span className="re-editor-chars">{modifiedText.length.toLocaleString()}자</span>
              </div>
              <textarea
                className="re-textarea"
                value={modifiedText}
                onChange={(e) => setModifiedText(e.target.value)}
                spellCheck={false}
              />
            </div>

            {/* Action Buttons */}
            <div className="re-edit-actions">
              <button
                className="re-btn re-btn-secondary"
                onClick={resetModifiedText}
                disabled={!hasChanges}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" /></svg>
                되돌리기
              </button>
              <button
                className="re-btn re-btn-primary"
                onClick={goToConfirm}
                disabled={!hasChanges}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 11 12 14 22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
                변경사항 확인
              </button>
            </div>
          </div>
        )}

        {/* Step 3: 변경 확인 + Summary */}
        {step === 'confirm' && docInfo && (
          <div className="re-content">
            <div className="re-confirm-header">
              <h3>변경사항 확인</h3>
              <p>
                <span className="re-doc-id">{docInfo.docId}</span>
                {docInfo.title}
              </p>
            </div>

            {/* Diff Stats */}
            <div className="re-diff-stats">
              <div className="re-diff-stat re-diff-stat-removed">
                <span className="re-diff-stat-number">-{diffStats.removed}</span>
                <span>삭제</span>
              </div>
              <div className="re-diff-stat re-diff-stat-added">
                <span className="re-diff-stat-number">+{diffStats.added}</span>
                <span>추가</span>
              </div>
              <div className="re-diff-stat re-diff-stat-unchanged">
                <span className="re-diff-stat-number">{diffStats.unchanged}</span>
                <span>변경 없음</span>
              </div>
            </div>

            {/* Diff View */}
            <div className="re-diff-view">
              <div className="re-diff-header-row">
                <span>변경 내역 (Diff)</span>
              </div>
              <div className="re-diff-content">
                {diffLines.map((line, idx) => (
                  <div
                    key={idx}
                    className={`re-diff-line re-diff-line-${line.type}`}
                  >
                    <span className="re-diff-line-num">
                      {line.type === 'removed'
                        ? line.lineNumber.old
                        : line.type === 'added'
                        ? line.lineNumber.new
                        : line.lineNumber.old}
                    </span>
                    <span className="re-diff-line-sign">
                      {line.type === 'removed' ? '-' : line.type === 'added' ? '+' : ' '}
                    </span>
                    <span className="re-diff-line-text">{line.content || '\u00A0'}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Confirm Actions */}
            <div className="re-confirm-actions">
              <button className="re-btn re-btn-secondary" onClick={goBackToEdit}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
                편집으로 돌아가기
              </button>
              <button
                className="re-btn re-btn-danger"
                onClick={saveChanges}
                disabled={isSaving}
              >
                {isSaving ? (
                  <>
                    <div className="modern-spinner-small"></div>
                    저장 중...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" /><polyline points="17 21 17 13 7 13 7 21" /><polyline points="7 3 7 8 15 8" /></svg>
                    적용 (덮어쓰기)
                  </>
                )}
              </button>
            </div>

            <div className="re-confirm-warning">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              <span>원본 파일은 자동으로 백업됩니다. 적용 후 즉시 원본 파일이 수정됩니다.</span>
            </div>
          </div>
        )}

        {/* Step: 일괄 작업 확인 */}
        {step === 'batch-confirm' && (
          <div className="re-content">
            <div className="re-confirm-header">
              <h3>일괄 작업 확인</h3>
              <p>{checkedDocIds.size}개 문서에 대해 일괄 {batchReplaceText ? '치환' : '삭제'}를 수행합니다</p>
            </div>

            <div className="re-batch-summary">
              <div className="re-batch-summary-item">
                <span className="re-batch-summary-label">대상 문서</span>
                <span className="re-batch-summary-value">{checkedDocIds.size}개</span>
              </div>
              <div className="re-batch-summary-item">
                <span className="re-batch-summary-label">찾기</span>
                <code className="re-batch-summary-code">{batchFindText}</code>
              </div>
              <div className="re-batch-summary-item">
                <span className="re-batch-summary-label">바꾸기</span>
                <code className="re-batch-summary-code">{batchReplaceText || '(삭제)'}</code>
              </div>
              {batchUseRegex && (
                <div className="re-batch-summary-item">
                  <span className="re-batch-summary-label">모드</span>
                  <span className="re-batch-summary-value">정규식</span>
                </div>
              )}
            </div>

            <div className="re-batch-doc-list-preview">
              <div className="re-batch-preview-header">대상 문서 목록</div>
              <div className="re-batch-preview-items">
                {searchResults
                  .filter((d) => checkedDocIds.has(d.docId))
                  .map((doc) => (
                    <div key={doc.docId} className="re-batch-preview-item">
                      <span className="re-doc-id">{doc.docId}</span>
                      <span className="re-batch-preview-title">{doc.title || '(제목 없음)'}</span>
                    </div>
                  ))}
              </div>
            </div>

            {batchResult && batchResult.affected_count === 0 && (
              <div className="re-confirm-warning">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{batchResult.message}</span>
              </div>
            )}

            <div className="re-confirm-actions">
              <button className="re-btn re-btn-secondary" onClick={goBackFromBatch}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
                돌아가기
              </button>
              <button
                className="re-btn re-btn-danger"
                onClick={executeBatchReplace}
                disabled={isSaving}
              >
                {isSaving ? (
                  <>
                    <div className="modern-spinner-small"></div>
                    처리 중...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" /><polyline points="17 21 17 13 7 13 7 21" /><polyline points="7 3 7 8 15 8" /></svg>
                    일괄 {batchReplaceText ? '치환' : '삭제'} 적용
                  </>
                )}
              </button>
            </div>

            <div className="re-confirm-warning">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              <span>원본 파일은 자동으로 백업됩니다. {checkedDocIds.size}개 문서의 text 필드가 동시에 수정됩니다.</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
