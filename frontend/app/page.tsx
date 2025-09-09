'use client';

import { useEffect, useRef } from 'react';
import ChatMessage from '@/app/_features/home/ChatMessage';
import ChatInput from '@/app/_features/home/ChatInput';
import { useCrawler } from '@/app/_features/home/useCrawler';
import ModernPageHeader from '@/app/_components/ui/ModernPageHeader';

export default function Home() {
  const { messages, isProcessing, processUrl } = useCrawler();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const previousMessageCount = useRef(0);

  // 새 메시지가 추가될 때마다 스크롤을 맨 아래로
  useEffect(() => {
    if (messages.length > previousMessageCount.current && messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    previousMessageCount.current = messages.length;
  }, [messages]);

  return (
    <div className="home-page">
      <ModernPageHeader
        title="크롤링 AI 어시스턴트"
        subtitle="웹사이트 URL을 입력하면 AI가 자동으로 분석해드립니다"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1 .34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"></path>
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0-.34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"></path>
          </svg>
        }
        status={{
          text: `${messages.length}개 대화`,
          isActive: !isProcessing
        }}
      />

      <div className="chat-container">
        <main className="messages-container">
          {messages.length === 0 ? (
            <div className="welcome-message">
              <h2 className="welcome-title">AI 크롤링 어시스턴트에 오신 것을 환영합니다!</h2>
              <p className="welcome-subtitle">
                웹사이트 URL을 입력하면 AI가 자동으로 분석하여 메뉴 구조와 콘텐츠를 추출해드립니다.
              </p>
              <div className="welcome-features">
                <div className="welcome-feature">
                  <div className="welcome-feature-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1 .34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"></path>
                      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0-.34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"></path>
                    </svg>
                  </div>
                  <span className="welcome-feature-text">AI 자동 분석</span>
                </div>
                <div className="welcome-feature">
                  <div className="welcome-feature-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                    </svg>
                  </div>
                  <span className="welcome-feature-text">메뉴 구조 추출</span>
                </div>
                <div className="welcome-feature">
                  <div className="welcome-feature-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14,2 14,8 20,8"></polyline>
                      <line x1="16" y1="13" x2="8" y2="13"></line>
                      <line x1="16" y1="17" x2="8" y2="17"></line>
                      <polyline points="10,9 9,9 8,9"></polyline>
                    </svg>
                  </div>
                  <span className="welcome-feature-text">콘텐츠 분석</span>
                </div>
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))
          )}
          <div ref={messagesEndRef} />
        </main>

        <ChatInput onSubmit={processUrl} isProcessing={isProcessing} />
      </div>
    </div>
  );
}