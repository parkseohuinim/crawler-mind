'use client';

import { useState, useEffect } from 'react';

interface DataInfo {
  success: boolean;
  qdrant: {
    success: boolean;
    collection_name: string;
    points_count: number;
  };
  opensearch: {
    success: boolean;
    index_name: string;
    document_count: number;
  };
  summary: {
    qdrant_documents: number;
    opensearch_documents: number;
  };
}

export default function RagDataManager() {
  const [dataInfo, setDataInfo] = useState<DataInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState('');

  const fetchDataInfo = async () => {
    setLoading(true);
    setMessage('');
    
    try {
      const response = await fetch('/api/rag/info');
      
      if (response.ok) {
        const result = await response.json();
        setDataInfo(result);
      } else {
        const error = await response.json();
        setMessage(`데이터 정보 조회 실패: ${error.error}`);
      }
    } catch (error) {
      console.error('Data info fetch error:', error);
      setMessage('데이터 정보 조회 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAllData = async () => {
    if (!confirm('정말로 모든 RAG 데이터를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
      return;
    }

    setDeleting(true);
    setMessage('');

    try {
      const response = await fetch('/api/rag/delete', {
        method: 'DELETE',
      });

      if (response.ok) {
        const result = await response.json();
        setMessage(`성공: ${result.message}`);
        // Refresh data info after deletion
        await fetchDataInfo();
      } else {
        const error = await response.json();
        setMessage(`삭제 실패: ${error.error}`);
      }
    } catch (error) {
      console.error('Delete error:', error);
      setMessage('데이터 삭제 중 오류가 발생했습니다.');
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    fetchDataInfo();
  }, []);

  return (
    <div className="modern-data-manager">
      <div className="modern-data-header">
        <div className="data-header-content">
          <div className="data-header-icon">
            <img 
              src="/icons/tool-screwdriver-svgrepo-com.svg" 
              alt="관리" 
              width="32" 
              height="32"
            />
          </div>
          <div className="data-header-text">
            <h2>RAG 데이터 관리</h2>
            <p>저장된 RAG 데이터 현황을 확인하고 관리하세요</p>
          </div>
        </div>
      </div>

      <div className="modern-data-content">
        {/* Data Info Section */}
        <div className="modern-data-section">
          <div className="modern-section-header">
            <h3>데이터 현황</h3>
            <button
              onClick={fetchDataInfo}
              disabled={loading}
              className="modern-refresh-button"
            >
              {loading ? '새로고침 중...' : '새로고침'}
            </button>
          </div>

          {loading && !dataInfo ? (
            <div className="modern-loading-state">
              <div className="modern-loading-spinner"></div>
              <span>데이터 정보를 불러오는 중...</span>
            </div>
          ) : dataInfo ? (
            <div className="modern-data-grid">
              <div className="modern-data-card qdrant">
                <div className="modern-card-header">
                  <img 
                    src="/icons/qdrant-icon.svg" 
                    alt="Qdrant" 
                    width="24" 
                    height="24"
                  />
                  <h4>Qdrant (벡터 DB)</h4>
                </div>
                <div className="modern-card-content">
                  <div className="modern-data-stat">
                    <span className="modern-stat-label">컬렉션:</span>
                    <span className="modern-stat-value">{dataInfo.qdrant.collection_name}</span>
                  </div>
                  <div className="modern-data-stat">
                    <span className="modern-stat-label">문서 수:</span>
                    <span className="modern-stat-value">{dataInfo.summary.qdrant_documents.toLocaleString()}</span>
                  </div>
                  <div className={`modern-status-indicator ${dataInfo.qdrant.success ? 'connected' : 'error'}`}>
                    {dataInfo.qdrant.success ? '연결됨' : '연결 실패'}
                  </div>
                </div>
              </div>

              <div className="modern-data-card opensearch">
                <div className="modern-card-header">
                  <img 
                    src="/icons/opensearch-icon.svg" 
                    alt="OpenSearch" 
                    width="24" 
                    height="24"
                  />
                  <h4>OpenSearch (검색 DB)</h4>
                </div>
                <div className="modern-card-content">
                  <div className="modern-data-stat">
                    <span className="modern-stat-label">인덱스:</span>
                    <span className="modern-stat-value">{dataInfo.opensearch.index_name}</span>
                  </div>
                  <div className="modern-data-stat">
                    <span className="modern-stat-label">문서 수:</span>
                    <span className="modern-stat-value">{dataInfo.summary.opensearch_documents.toLocaleString()}</span>
                  </div>
                  <div className={`modern-status-indicator ${dataInfo.opensearch.success ? 'connected' : 'error'}`}>
                    {dataInfo.opensearch.success ? '연결됨' : '연결 실패'}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Data Management Section */}
        <div className="modern-management-section">
          <div className="modern-section-header">
            <img 
              src="/icons/tool-screwdriver-svgrepo-com.svg" 
              alt="관리" 
              width="24" 
              height="24"
            />
            <h3>데이터 관리</h3>
          </div>

          <div className="modern-management-actions">
            <div className="modern-action-card delete-action">
              <div className="modern-action-info">
                <h4>모든 데이터 삭제</h4>
                <p>Qdrant와 OpenSearch에 저장된 모든 RAG 데이터를 삭제합니다.</p>
                <div className="modern-warning-text">
                  <strong>주의:</strong> 이 작업은 되돌릴 수 없습니다.
                </div>
              </div>
              <button
                onClick={handleDeleteAllData}
                disabled={deleting || !dataInfo}
                className="modern-delete-button"
                aria-label="모든 RAG 데이터 삭제"
                title="모든 RAG 데이터 삭제"
              >
                {deleting ? (
                  <>
                    <span className="modern-delete-spinner"></span>
                    <span className="modern-delete-label">삭제 중...</span>
                  </>
                ) : (
                  <span className="modern-delete-label">모든 데이터 삭제</span>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Message Display */}
        {message && (
          <div className={`modern-data-message ${
            message.includes('✅') ? 'success' : 'error'
          }`}>
            <span className="modern-message-icon">
              {message.includes('성공') ? '✓' : '✗'}
            </span>
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
