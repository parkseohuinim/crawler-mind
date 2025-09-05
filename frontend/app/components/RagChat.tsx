'use client';

import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  sources?: Array<{
    id: string;
    title: string;
    url?: string;
    similarity_score: number;
    score_label?: string;
    search_source?: string;
    raw_score?: number;
    search_method?: string;
  }>;
  timestamp: Date;
}

const STORAGE_KEY = 'rag-chat-messages';

export default function RagChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 컴포넌트 마운트 시 저장된 메시지 불러오기
  useEffect(() => {
    const savedMessages = localStorage.getItem(STORAGE_KEY);
    if (savedMessages) {
      try {
        const parsedMessages = JSON.parse(savedMessages);
        setMessages(parsedMessages.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp)
        })));
      } catch (error) {
        console.error('Failed to load saved messages:', error);
      }
    }
  }, []);

  // 메시지가 변경될 때마다 localStorage에 저장
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    }
  }, [messages]);

  // 자동 스크롤 기능
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ 
      behavior: 'smooth',
      block: 'end'
    });
  };

  // 메시지가 추가되거나 로딩 상태가 변경될 때 자동 스크롤
  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const clearHistory = () => {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('/api/rag/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: userMessage.content }),
      });

      if (response.ok) {
        const result = await response.json();
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: result.answer,
          sources: result.sources,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, assistantMessage]);
      } else {
        const error = await response.json();
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: `오류가 발생했습니다: ${error.error}`,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Query error:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: '질의 처리 중 오류가 발생했습니다.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rag-chat-container">
      <div className="rag-chat-header">
        <div className="chat-header-content">
          <div className="header-title-section">
            <h2>💬 스마트 AI 어시스턴트</h2>
            <p>업로드된 문서를 기반으로 정확한 답변을 제공합니다</p>
          </div>
          {messages.length > 0 && (
            <button 
              onClick={clearHistory}
              className="clear-history-button"
              title="대화 내역 삭제"
            >
              🗑️
            </button>
          )}
        </div>
      </div>

      <div className="rag-messages-container">
        {messages.length === 0 ? (
          <div className="rag-empty-state">
            <div className="empty-icon">🤖</div>
            <div className="empty-title">질문을 입력해보세요</div>
            <div className="empty-subtitle">
              업로드된 문서를 기반으로 정확한 답변을 제공해드립니다
            </div>
            <div className="example-queries">
              <div className="example-title">예시 질문:</div>
              <div className="example-item">"eSIM 이동 방법을 알려주세요"</div>
              <div className="example-item">"KT 요금제에 대해 설명해주세요"</div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.type}`}>
                <div className={`message-avatar ${message.type}`}>
                  {message.type === 'user' ? '👤' : '🤖'}
                </div>
                <div className="message-content">
                  <div className="message-text">
                    {message.type === 'assistant' ? (
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        className="markdown-content"
                      >
                        {message.content}
                      </ReactMarkdown>
                    ) : (
                      message.content
                    )}
                  </div>
                  {message.sources && message.sources.length > 0 && (
                    <div className="message-sources">
                      <div className="sources-title">📚 참고 문서</div>
                      {message.sources.slice(0, 3).map((source, index) => (
                        <div key={source.id} className="source-item">
                          <span className="source-number">{index + 1}</span>
                          <div className="source-info">
                            <div className="source-title">{source.title}</div>
                            <div className="source-details">
                              <div className="source-score">
                                {source.score_label || '점수'}: {source.similarity_score.toFixed(3)}
                              </div>
                              <div className="source-method">
                                {source.search_source === 'vector' ? '🔍' : '📝'} {source.search_method || '알 수 없음'}
                              </div>
                              {source.raw_score !== undefined && (
                                <div className="source-raw-score">
                                  원본: {source.raw_score.toFixed(3)}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="message-time">
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="message assistant">
                <div className="message-avatar assistant">🤖</div>
                <div className="message-content">
                  <div className="message-text loading">
                    <span className="loading-dots">
                      <span></span>
                      <span></span>
                      <span></span>
                    </span>
                    답변을 생성하고 있습니다...
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="rag-input-form">
        <div className="input-wrapper">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="질문을 입력하세요..."
            disabled={loading}
            className="chat-input"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="send-button"
          >
            {loading ? '⏳' : '📤'}
          </button>
        </div>
      </form>
    </div>
  );
}
