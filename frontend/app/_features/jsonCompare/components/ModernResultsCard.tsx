'use client';

import React from 'react';
import { JsonComparisonResult } from '@/app/_lib/types';

interface ModernResultsCardProps {
  result: JsonComparisonResult;
  onDownload: () => void;
}

export default function ModernResultsCard({ result, onDownload }: ModernResultsCardProps) {
  const stats = [
    {
      key: 'total_objects_1',
      label: '첫 번째 파일 객체 수',
      value: result.total_objects_1,
      type: 'primary',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14,2 14,8 20,8"></polyline>
        </svg>
      )
    },
    {
      key: 'total_objects_2',
      label: '두 번째 파일 객체 수',
      value: result.total_objects_2,
      type: 'primary',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14,2 14,8 20,8"></polyline>
        </svg>
      )
    },
    {
      key: 'objects_removed',
      label: '삭제된 객체',
      value: result.objects_removed,
      type: 'danger',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 6h18"></path>
          <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
          <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
        </svg>
      )
    },
    {
      key: 'objects_added',
      label: '추가된 객체',
      value: result.objects_added,
      type: 'success',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
      )
    },
    {
      key: 'objects_modified',
      label: '수정된 객체',
      value: result.objects_modified,
      type: 'warning',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
          <path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
        </svg>
      )
    },
    {
      key: 'objects_unchanged',
      label: '변경되지 않은 객체',
      value: result.objects_unchanged,
      type: 'neutral',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22,4 12,14.01 9,11.01"></polyline>
        </svg>
      )
    },
    {
      key: 'javascript_pages',
      label: 'JavaScript 검출 페이지',
      value: result.javascript_pages,
      type: 'info',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="16,18 22,12 16,6"></polyline>
          <polyline points="8,6 2,12 8,18"></polyline>
        </svg>
      )
    },
    {
      key: 'total_changes',
      label: '총 변경사항',
      value: result.total_changes,
      type: 'total',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path>
        </svg>
      )
    }
  ];

  return (
    <div className="modern-results-container">
      <div className="modern-results-header">
        <div className="modern-results-title">
          <div className="modern-results-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 3v18h18"></path>
              <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"></path>
            </svg>
          </div>
          <div>
            <h3>비교 결과</h3>
            <p>JSON 파일 비교 분석 결과입니다</p>
          </div>
        </div>
      </div>

      <div className="modern-stats-grid">
        {stats.map((stat) => (
          <div key={stat.key} className={`modern-stat-item modern-stat-${stat.type}`}>
            <div className="modern-stat-icon">
              {stat.icon}
            </div>
            <div className="modern-stat-content">
              <div className="modern-stat-value">{stat.value}</div>
              <div className="modern-stat-label">{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="modern-download-section">
        <button
          onClick={onDownload}
          className="modern-download-button"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7,10 12,15 17,10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
          PDF 리포트 다운로드
        </button>
      </div>

      {result.summary_report && (
        <div className="modern-summary-card">
          <div className="modern-summary-header">
            <div className="modern-summary-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14,2 14,8 20,8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10,9 9,9 8,9"></polyline>
              </svg>
            </div>
            <h4>요약 리포트</h4>
          </div>
          <div className="modern-summary-content">
            <pre className="modern-summary-text">
              {result.summary_report}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
