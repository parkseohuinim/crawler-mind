'use client';

import { useEffect, useRef } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { useCrawler } from './useCrawler';

export default function Home() {
  const { messages, isProcessing, processUrl } = useCrawler();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 새 메시지가 추가될 때마다 스크롤을 맨 아래로
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1 className="chat-title">크롤링 AI 어시스턴트</h1>
        <p className="chat-subtitle">
          웹사이트 URL을 입력하면 AI가 자동으로 분석해드립니다
        </p>
      </header>

      <main className="messages-container">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        <div ref={messagesEndRef} />
      </main>

      <ChatInput onSubmit={processUrl} isProcessing={isProcessing} />
    </div>
  );
}
