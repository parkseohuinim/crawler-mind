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
        setMessage(`✅ ${result.message}`);
        // Refresh data info after deletion
        await fetchDataInfo();
      } else {
        const error = await response.json();
        setMessage(`❌ 삭제 실패: ${error.error}`);
      }
    } catch (error) {
      console.error('Delete error:', error);
      setMessage('❌ 데이터 삭제 중 오류가 발생했습니다.');
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    fetchDataInfo();
  }, []);

  return (
    <div className="rag-data-manager-container">
      <div className="rag-data-manager-header">
        <h2>🗄️ RAG 데이터 관리</h2>
        <p>저장된 RAG 데이터 현황을 확인하고 관리하세요</p>
      </div>

      <div className="rag-data-manager-content">
        {/* Data Info Section */}
        <div className="data-info-section">
          <div className="section-header">
            <h3>📊 데이터 현황</h3>
            <button
              onClick={fetchDataInfo}
              disabled={loading}
              className="refresh-button"
            >
              {loading ? '🔄' : '🔄'} 새로고침
            </button>
          </div>

          {loading && !dataInfo ? (
            <div className="loading-state">
              <div className="loading-spinner"></div>
              <span>데이터 정보를 불러오는 중...</span>
            </div>
          ) : dataInfo ? (
            <div className="data-info-grid">
              <div className="data-info-card qdrant">
                <div className="card-header">
                  <span className="card-icon">🔍</span>
                  <h4>Qdrant (벡터 DB)</h4>
                </div>
                <div className="card-content">
                  <div className="data-stat">
                    <span className="stat-label">컬렉션:</span>
                    <span className="stat-value">{dataInfo.qdrant.collection_name}</span>
                  </div>
                  <div className="data-stat">
                    <span className="stat-label">문서 수:</span>
                    <span className="stat-value">{dataInfo.summary.qdrant_documents.toLocaleString()}</span>
                  </div>
                  <div className={`status-indicator ${dataInfo.qdrant.success ? 'connected' : 'error'}`}>
                    {dataInfo.qdrant.success ? '✅ 연결됨' : '❌ 연결 실패'}
                  </div>
                </div>
              </div>

              <div className="data-info-card opensearch">
                <div className="card-header">
                  <span className="card-icon">🔎</span>
                  <h4>OpenSearch (검색 DB)</h4>
                </div>
                <div className="card-content">
                  <div className="data-stat">
                    <span className="stat-label">인덱스:</span>
                    <span className="stat-value">{dataInfo.opensearch.index_name}</span>
                  </div>
                  <div className="data-stat">
                    <span className="stat-label">문서 수:</span>
                    <span className="stat-value">{dataInfo.summary.opensearch_documents.toLocaleString()}</span>
                  </div>
                  <div className={`status-indicator ${dataInfo.opensearch.success ? 'connected' : 'error'}`}>
                    {dataInfo.opensearch.success ? '✅ 연결됨' : '❌ 연결 실패'}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Data Management Section */}
        <div className="data-management-section">
          <div className="section-header">
            <h3>🛠️ 데이터 관리</h3>
          </div>

          <div className="management-actions">
            <div className="action-card delete-action">
              <div className="action-info">
                <h4>⚠️ 모든 데이터 삭제</h4>
                <p>Qdrant와 OpenSearch에 저장된 모든 RAG 데이터를 삭제합니다.</p>
                <div className="warning-text">
                  <strong>주의:</strong> 이 작업은 되돌릴 수 없습니다.
                </div>
              </div>
              <button
                onClick={handleDeleteAllData}
                disabled={deleting || !dataInfo}
                className="delete-button"
              >
                {deleting ? (
                  <>
                    <span className="delete-spinner"></span>
                    삭제 중...
                  </>
                ) : (
                  <>
                    🗑️ 모든 데이터 삭제
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Message Display */}
        {message && (
          <div className={`data-message ${
            message.includes('✅') ? 'success' : 'error'
          }`}>
            <span className="message-icon">
              {message.includes('✅') ? '✅' : '❌'}
            </span>
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
