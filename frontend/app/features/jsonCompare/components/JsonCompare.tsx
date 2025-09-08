'use client';

import React from 'react';
import { useJsonCompare } from '../hooks/useJsonCompare';

export default function JsonCompare() {
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
    handleFile1Change,
    handleFile2Change,
    handleCompare,
    handleDownload,
    resetForm,
  } = useJsonCompare();

  return (
    <div className="json-compare-page">
      <div className="json-compare-container">
        <div className="page-header">
          <h1 className="page-title">JSON 파일 비교</h1>
          <p className="page-subtitle">두 JSON 파일을 비교하여 변경사항을 분석하고 PDF 리포트를 생성합니다</p>
        </div>

        {isComparing ? (
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p className="loading-text">JSON 파일을 비교하고 있습니다...</p>
          </div>
        ) : (
          <div className="json-compare-card">
            {/* 파일 업로드 섹션 */}
            <div className="file-upload-section">
              <div className="file-upload-grid">
                <div className="file-upload-item">
                  <label className="file-upload-label">
                    <img 
                      src="/icons/document-file-page-paper-svgrepo-com.svg" 
                      alt="파일" 
                      width="24" 
                      height="24"
                      className="file-icon"
                    />
                    첫 번째 JSON 파일
                  </label>
                  <input
                    ref={file1Ref}
                    type="file"
                    accept=".json"
                    onChange={handleFile1Change}
                    className="file-input"
                    disabled={isComparing}
                  />
                  {file1 ? (
                    <div className="file-info">
                      <span className="file-name">{file1.name}</span>
                      <span className="file-size">({(file1.size / 1024).toFixed(1)} KB)</span>
                    </div>
                  ) : (
                    <div className="file-placeholder">
                      JSON 파일을 선택해주세요
                    </div>
                  )}
                </div>
                
                <div className="file-upload-item">
                  <label className="file-upload-label">
                    <img 
                      src="/icons/document-file-page-paper-svgrepo-com.svg" 
                      alt="파일" 
                      width="24" 
                      height="24"
                      className="file-icon"
                    />
                    두 번째 JSON 파일
                  </label>
                  <input
                    ref={file2Ref}
                    type="file"
                    accept=".json"
                    onChange={handleFile2Change}
                    className="file-input"
                    disabled={isComparing}
                  />
                  {file2 ? (
                    <div className="file-info">
                      <span className="file-name">{file2.name}</span>
                      <span className="file-size">({(file2.size / 1024).toFixed(1)} KB)</span>
                    </div>
                  ) : (
                    <div className="file-placeholder">
                      JSON 파일을 선택해주세요
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* 버튼 섹션 */}
            <div className="action-buttons">
              <button
                onClick={handleCompare}
                disabled={!file1 || !file2 || isComparing}
                className="primary-button"
              >
                {isComparing ? (
                  <>
                    <div className="loading-spinner"></div>
                    비교 중...
                  </>
                ) : (
                  <>
                    <img 
                      src="/icons/rocket-spaceship-start-svgrepo-com.svg" 
                      alt="시작" 
                      width="20" 
                      height="20"
                      className="button-icon"
                    />
                    비교 시작
                  </>
                )}
              </button>
              
              <button
                onClick={resetForm}
                disabled={isComparing}
                className="secondary-button"
              >
                <img 
                  src="/icons/delete-trash-svgrepo-com.svg" 
                  alt="초기화" 
                  width="20" 
                  height="20"
                  className="button-icon"
                />
                초기화
              </button>
            </div>

            {/* 오류 메시지 */}
            {error && (
              <div className="error-banner">
                <img 
                  src="/icons/announcement-shout-svgrepo-com.svg" 
                  alt="오류" 
                  width="20" 
                  height="20"
                  className="error-icon"
                />
                <span>{error}</span>
              </div>
            )}

            {/* 작업 상태 */}
            {taskStatus && (
              <div className="status-card">
                <div className="status-header">
                  <img 
                    src="/icons/info-information-svgrepo-com.svg" 
                    alt="상태" 
                    width="24" 
                    height="24"
                    className="status-icon"
                  />
                  <h3>작업 상태</h3>
                </div>
                <div className="status-content">
                  <div className="status-item">
                    <span className="status-label">상태:</span>
                    <span className={`status-value status-${taskStatus.status}`}>
                      {taskStatus.status}
                    </span>
                  </div>
                  <div className="status-item">
                    <span className="status-label">파일:</span>
                    <span className="status-value">
                      {taskStatus.file1_name} vs {taskStatus.file2_name}
                    </span>
                  </div>
                  <div className="status-item">
                    <span className="status-label">생성 시간:</span>
                    <span className="status-value">
                      {new Date(taskStatus.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* 비교 결과 */}
            {result && (
              <div className="results-section">
                <div className="results-card">
                  <div className="results-header">
                    <img 
                      src="/icons/chart-pipe-svgrepo-com.svg" 
                      alt="결과" 
                      width="24" 
                      height="24"
                      className="results-icon"
                    />
                    <h3>비교 결과</h3>
                  </div>
                  
                  <div className="stats-grid">
                    <div className="stat-item">
                      <div className="stat-value stat-primary">{result.total_objects_1}</div>
                      <div className="stat-label">첫 번째 파일 객체 수</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value stat-primary">{result.total_objects_2}</div>
                      <div className="stat-label">두 번째 파일 객체 수</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value stat-danger">{result.objects_removed}</div>
                      <div className="stat-label">삭제된 객체</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value stat-success">{result.objects_added}</div>
                      <div className="stat-label">추가된 객체</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value stat-warning">{result.objects_modified}</div>
                      <div className="stat-label">수정된 객체</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value stat-neutral">{result.objects_unchanged}</div>
                      <div className="stat-label">변경되지 않은 객체</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value stat-info">{result.javascript_pages}</div>
                      <div className="stat-label">JavaScript 검출 페이지</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value stat-total">{result.total_changes}</div>
                      <div className="stat-label">총 변경사항</div>
                    </div>
                  </div>
                </div>

                {/* 다운로드 버튼 */}
                <div className="download-section">
                  <button
                    onClick={handleDownload}
                    className="download-button"
                  >
                    <img 
                      src="/icons/upload-file-document-svgrepo-com.svg" 
                      alt="다운로드" 
                      width="20" 
                      height="20"
                      className="button-icon"
                    />
                    PDF 리포트 다운로드
                  </button>
                </div>

                {/* 요약 리포트 */}
                {result.summary_report && (
                  <div className="summary-card">
                    <div className="summary-header">
                      <img 
                        src="/icons/feather-pen-svgrepo-com.svg" 
                        alt="요약" 
                        width="20" 
                        height="20"
                        className="summary-icon"
                      />
                      <h4>요약 리포트</h4>
                    </div>
                    <div className="summary-content">
                      <pre className="summary-text">
                        {result.summary_report}
                      </pre>
                    </div>
                  </div>
                )}

                {/* URL이 비어있는 항목들의 담당자 정보 */}
                {emptyUrlItems && emptyUrlItems.length > 0 && (
                  <div className="empty-url-card">
                    <div className="empty-url-header">
                      <img 
                        src="/icons/scientist-medium-dark-skin-tone-svgrepo-com.svg" 
                        alt="담당자" 
                        width="20" 
                        height="20"
                        className="empty-url-icon"
                      />
                      <h4>murl 필드가 비어있는 항목들의 담당자 정보</h4>
                      <span className="empty-url-count">({emptyUrlItems.length}개)</span>
                    </div>
                    <div className="empty-url-content">
                      <div className="empty-url-table">
                        <table>
                          <thead>
                            <tr>
                              <th>URL</th>
                              <th>페이지 제목</th>
                              <th>페이지 경로</th>
                              <th>담당자 정보</th>
                            </tr>
                          </thead>
                          <tbody>
                            {emptyUrlItems.map((item, index) => (
                              <tr key={index}>
                                <td className="url-cell">
                                  {item.url ? (
                                    <a href={item.url} target="_blank" rel="noopener noreferrer">
                                      {item.url.length > 50 
                                        ? `${item.url.substring(0, 50)}...` 
                                        : item.url}
                                    </a>
                                  ) : (
                                    <span className="no-url">-</span>
                                  )}
                                </td>
                                <td className="title-cell">
                                  {item.title || '-'}
                                </td>
                                <td className="hierarchy-cell">
                                  {item.hierarchy || '-'}
                                </td>
                                <td className="manager-cell">
                                  <div className="manager-info">
                                    <div className="team-name">
                                      <strong>팀:</strong> {item.manager_info.team_name}
                                    </div>
                                    <div className="manager-names">
                                      <strong>담당자:</strong> {item.manager_info.manager_names}
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}