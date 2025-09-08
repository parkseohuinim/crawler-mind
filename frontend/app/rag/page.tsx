'use client';

import { useState } from 'react';
import RagUpload from '../components/RagUpload';
import RagChat from '../components/RagChat';
import RagDataManager from '../components/RagDataManager';
import DocumentSearch from '../components/DocumentSearch';

export default function RagPage() {
  const [activeTab, setActiveTab] = useState<'upload' | 'chat' | 'manage' | 'search'>('chat');

  return (
    <div className="rag-page">
      <div className="rag-page-container">
        <div className="rag-page-header">
          <h1>RAG 시스템</h1>
          <p>문서를 업로드하고 AI 기반 질의응답을 사용하세요</p>
        </div>

        <div className="rag-tabs-container">
          <div className="rag-tab-navigation">
            <button
              onClick={() => setActiveTab('chat')}
              className={`rag-tab-button ${activeTab === 'chat' ? 'active' : ''}`}
            >
              <img 
                src="/icons/chat-communication-message-talk-svgrepo-com.svg" 
                alt="채팅" 
                width="35" 
                height="35"
                className="tab-icon"
              />
              <span className="tab-label">질의응답</span>
            </button>
            <button
              onClick={() => setActiveTab('upload')}
              className={`rag-tab-button ${activeTab === 'upload' ? 'active' : ''}`}
            >
              <img 
                src="/icons/upload-file-document-svgrepo-com.svg" 
                alt="업로드" 
                width="35" 
                height="35"
                className="tab-icon"
              />
              <span className="tab-label">파일 업로드</span>
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`rag-tab-button ${activeTab === 'search' ? 'active' : ''}`}
            >
              <img 
                src="/icons/search-svgrepo-com.svg" 
                alt="검색" 
                width="30" 
                height="30"
                className="tab-icon"
              />
              <span className="tab-label">문서 검색</span>
            </button>
            <button
              onClick={() => setActiveTab('manage')}
              className={`rag-tab-button ${activeTab === 'manage' ? 'active' : ''}`}
            >
              <img 
                src="/icons/tool-screwdriver-svgrepo-com.svg" 
                alt="관리" 
                width="30" 
                height="30"
                className="tab-icon"
              />
              <span className="tab-label">데이터 관리</span>
            </button>
          </div>

          <div className="rag-tab-content">
            {activeTab === 'chat' && (
              <div className="rag-chat-tab">
                <RagChat />
                
                <div className="rag-info-card tips">
                  <div className="info-card-header">
                    <img 
                      src="/icons/feather-pen-svgrepo-com.svg" 
                      alt="팁" 
                      width="35" 
                      height="35"
                      className="info-icon"
                    />
                    <h3>사용 팁</h3>
                  </div>
                  <div className="info-card-content">
                    <div className="info-item">
                      <span className="bullet">•</span>
                      구체적이고 명확한 질문을 해주세요
                    </div>
                    <div className="info-item">
                      <span className="bullet">•</span>
                      업로드된 문서 내용과 관련된 질문이 가장 정확한 답변을 제공합니다
                    </div>
                    <div className="info-item">
                      <span className="bullet">•</span>
                      답변에는 관련 문서의 출처 정보가 함께 제공됩니다
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'upload' && (
              <div className="rag-upload-tab">
                <RagUpload onUploadSuccess={() => setActiveTab('chat')} />
                
                <div className="rag-info-card">
                  <div className="info-card-header">
                    <img 
                      src="/icons/announcement-shout-svgrepo-com.svg" 
                      alt="안내" 
                      width="35" 
                      height="35"
                      className="info-icon"
                    />
                    <h3>파일 형식 안내</h3>
                  </div>
                  <div className="info-card-content">
                    <div className="info-item">
                      <span className="bullet">•</span>
                      JSON 배열 형태의 파일만 업로드 가능합니다
                    </div>
                    <div className="info-item">
                      <span className="bullet">•</span>
                      각 문서는 다음 필드를 포함해야 합니다:
                    </div>
                    <div className="info-sublist">
                      <div className="info-subitem">
                        <code>docId</code>: 문서 고유 ID
                      </div>
                      <div className="info-subitem">
                        <code>title</code>: 문서 제목
                      </div>
                      <div className="info-subitem">
                        <code>text</code>: 문서 내용
                      </div>
                      <div className="info-subitem">
                        <code>url</code> (선택): 문서 URL
                      </div>
                      <div className="info-subitem">
                        <code>hierarchy</code> (선택): 문서 계층구조
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'search' && (
              <div className="rag-search-tab">
                <DocumentSearch />
                
                <div className="rag-info-card">
                  <div className="info-card-header">
                    <img 
                      src="/icons/info-information-svgrepo-com.svg" 
                      alt="정보" 
                      width="30" 
                      height="30"
                      className="info-icon"
                    />
                    <h3>문서 검색 안내</h3>
                  </div>
                  <div className="info-card-content">
                    <div className="info-item">
                      <span className="bullet">•</span>
                      벡터 검색과 텍스트 검색을 동시에 수행하여 정확한 결과를 제공합니다
                    </div>
                    <div className="info-item">
                      <span className="bullet">•</span>
                      유사도 점수는 0-100% 범위로 표시되며, 높을수록 관련성이 높습니다
                    </div>
                    <div className="info-item">
                      <span className="bullet">•</span>
                      검색 결과에서 원본 문서 링크를 클릭하여 전체 내용을 확인할 수 있습니다
                    </div>
                    <div className="info-item">
                      <span className="bullet">•</span>
                      "전체 내용 포함" 옵션을 해제하면 검색 속도가 향상됩니다
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'manage' && (
              <div className="rag-manage-tab">
                <RagDataManager />
                
                <div className="rag-info-card">
                  <div className="info-card-header">
                    <img 
                      src="/icons/info-information-svgrepo-com.svg" 
                      alt="정보" 
                      width="30" 
                      height="30"
                      className="info-icon"
                    />
                    <h3>데이터 관리 안내</h3>
                  </div>
                  <div className="info-card-content">
                    <div className="info-item">
                      <span className="bullet">•</span>
                      현재 저장된 RAG 데이터의 현황을 실시간으로 확인할 수 있습니다
                    </div>
                    <div className="info-item">
                      <span className="bullet">•</span>
                      Qdrant와 OpenSearch에 저장된 데이터를 완전히 삭제할 수 있습니다
                    </div>
                    <div className="info-item">
                      <span className="bullet">•</span>
                      데이터 삭제 후에는 새로운 문서를 업로드해야 질의응답이 가능합니다
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
