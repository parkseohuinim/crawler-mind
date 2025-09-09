'use client';

import React from 'react';
import { useJsonCompare } from '../hooks/useJsonCompare';
import ModernPageHeader from '@/app/_components/ui/ModernPageHeader';
import ModernFileUpload from './ModernFileUpload';
import ModernStatusCard from './ModernStatusCard';
import ModernResultsCard from './ModernResultsCard';
import ModernEmptyUrlTable from './ModernEmptyUrlTable';

export default function ModernJsonCompare() {
  const {
    file1,
    file2,
    isComparing,
    taskId,
    taskStatus,
    result,
    emptyUrlItems,
    error,
    file1Ref,
    file2Ref,
    dragOverFile1,
    dragOverFile2,
    handleFile1Change,
    handleFile2Change,
    handleCompare,
    handleDownload,
    resetForm,
    handleFileDrop,
    handleDragOver,
    handleDragEnter,
    handleDragLeave,
  } = useJsonCompare();

  return (
    <div className="modern-json-compare-page">
      <ModernPageHeader
        title="JSON 파일 비교"
        subtitle="두 JSON 파일을 비교하여 변경사항을 분석하고 PDF 리포트를 생성합니다"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14,2 14,8 20,8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10,9 9,9 8,9"></polyline>
          </svg>
        }
        status={{
          text: file1 && file2 ? '파일 준비 완료' : '파일을 선택해주세요',
          isActive: !!(file1 && file2)
        }}
      />

      <div className="modern-json-compare-container">
        {isComparing ? (
          <div className="modern-loading-container">
            <div className="modern-spinner"></div>
            <p className="modern-loading-text">JSON 파일을 비교하고 있습니다...</p>
          </div>
        ) : (
          <div className="modern-json-compare-content">
          {/* 파일 업로드 섹션 */}
          <ModernFileUpload
            file1={file1}
            file2={file2}
            file1Ref={file1Ref}
            file2Ref={file2Ref}
            dragOverFile1={dragOverFile1}
            dragOverFile2={dragOverFile2}
            isComparing={isComparing}
            onFile1Change={handleFile1Change}
            onFile2Change={handleFile2Change}
            onFileDrop={handleFileDrop}
            onDragOver={handleDragOver}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
          />

          {/* 액션 버튼들 */}
          <div className="modern-action-buttons">
            <button
              onClick={handleCompare}
              disabled={!file1 || !file2 || isComparing}
              className="modern-primary-button"
            >
              {isComparing ? (
                <>
                  <div className="modern-spinner-small"></div>
                  비교 중...
                </>
              ) : (
                <>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path>
                  </svg>
                  비교 시작
                </>
              )}
            </button>
            
            <button
              onClick={resetForm}
              disabled={isComparing}
              className="modern-secondary-button"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18"></path>
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
              </svg>
              초기화
            </button>
          </div>

          {/* 오류 메시지 */}
          {error && (
            <div className="modern-error-banner">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
              </svg>
              <span>{error}</span>
            </div>
          )}

          {/* 작업 상태 */}
          {taskStatus && (
            <ModernStatusCard taskStatus={taskStatus} />
          )}

          {/* 비교 결과 */}
          {result && (
            <ModernResultsCard 
              result={result} 
              onDownload={handleDownload}
            />
          )}

          {/* URL이 비어있는 항목들 */}
          {emptyUrlItems && emptyUrlItems.length > 0 && (
            <ModernEmptyUrlTable emptyUrlItems={emptyUrlItems} />
          )}
          </div>
        )}
      </div>
    </div>
  );
}
