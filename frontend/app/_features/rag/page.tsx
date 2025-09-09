'use client';

import { useState } from 'react';
import RagUpload from './RagUpload';
import RagChat from './RagChat';
import RagDataManager from './RagDataManager';
import DocumentSearch from './DocumentSearch';
import ModernPageHeader from '@/app/_components/ui/ModernPageHeader';

export default function RagPage() {
  const [activeTab, setActiveTab] = useState<'upload' | 'chat' | 'manage' | 'search'>('chat');

  return (
    <div className="modern-rag-page">
      <ModernPageHeader
        title="RAG 시스템"
        subtitle="문서를 업로드하고 AI 기반 질의응답을 사용하세요"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 12l2 2 4-4"></path>
            <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"></path>
            <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"></path>
            <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"></path>
            <path d="M12 21c0-1 1-3 3-3s3 2 3 3-1 3-3 3-3-2-3-3"></path>
          </svg>
        }
      />

      <div className="modern-rag-container">
        <div className="modern-rag-tabs">
          <div className="modern-tab-navigation">
            <button
              onClick={() => setActiveTab('chat')}
              className={`modern-tab-button ${activeTab === 'chat' ? 'active' : ''}`}
            >
              <div className="tab-icon">
                <img 
                  src="/icons/chat-communication-message-talk-svgrepo-com.svg" 
                  alt="채팅" 
                  width="20" 
                  height="20"
                />
              </div>
              <span className="tab-label">질의응답</span>
            </button>
            <button
              onClick={() => setActiveTab('upload')}
              className={`modern-tab-button ${activeTab === 'upload' ? 'active' : ''}`}
            >
              <div className="tab-icon">
                <img 
                  src="/icons/upload-file-document-svgrepo-com.svg" 
                  alt="업로드" 
                  width="20" 
                  height="20"
                />
              </div>
              <span className="tab-label">파일 업로드</span>
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`modern-tab-button ${activeTab === 'search' ? 'active' : ''}`}
            >
              <div className="tab-icon">
                <img 
                  src="/icons/search-svgrepo-com.svg" 
                  alt="검색" 
                  width="18" 
                  height="18"
                />
              </div>
              <span className="tab-label">문서 검색</span>
            </button>
            <button
              onClick={() => setActiveTab('manage')}
              className={`modern-tab-button ${activeTab === 'manage' ? 'active' : ''}`}
            >
              <div className="tab-icon">
                <img 
                  src="/icons/tool-screwdriver-svgrepo-com.svg" 
                  alt="관리" 
                  width="18" 
                  height="18"
                />
              </div>
              <span className="tab-label">데이터 관리</span>
            </button>
          </div>

          <div className="modern-tab-content">
            {activeTab === 'chat' && (
              <div className="modern-tab-panel">
                <RagChat />
                
                <div className="modern-info-card tips">
                  <div className="info-header">
                    <div className="info-icon">
                      <img 
                        src="/icons/feather-pen-svgrepo-com.svg" 
                        alt="팁" 
                        width="24" 
                        height="24"
                      />
                    </div>
                    <h3>사용 팁</h3>
                  </div>
                  <div className="info-content">
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
              <div className="modern-tab-panel">
                <RagUpload onUploadSuccess={() => setActiveTab('chat')} />
                
                <div className="modern-info-card">
                  <div className="info-header">
                    <div className="info-icon">
                      <img 
                        src="/icons/announcement-shout-svgrepo-com.svg" 
                        alt="안내" 
                        width="24" 
                        height="24"
                      />
                    </div>
                    <h3>파일 형식 안내</h3>
                  </div>
                  <div className="info-content">
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
              <div className="modern-tab-panel">
                <DocumentSearch />
                
                <div className="modern-info-card">
                  <div className="info-header">
                    <div className="info-icon">
                      <img 
                        src="/icons/info-information-svgrepo-com.svg" 
                        alt="정보" 
                        width="20" 
                        height="20"
                      />
                    </div>
                    <h3>문서 검색 안내</h3>
                  </div>
                  <div className="info-content">
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
              <div className="modern-tab-panel">
                <RagDataManager />
                
                <div className="modern-info-card">
                  <div className="info-header">
                    <div className="info-icon">
                      <img 
                        src="/icons/info-information-svgrepo-com.svg" 
                        alt="정보" 
                        width="20" 
                        height="20"
                      />
                    </div>
                    <h3>데이터 관리 안내</h3>
                  </div>
                  <div className="info-content">
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
