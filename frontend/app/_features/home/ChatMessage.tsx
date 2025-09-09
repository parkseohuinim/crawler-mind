'use client';

import { Message } from '@/app/_lib/types';
import ProgressDisplay from '../rag/ProgressDisplay';
import ResultDisplay from '../rag/ResultDisplay';

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.type === 'user';

  return (
    <div className={`home-message ${message.type}`}>
      <div className={`home-message-avatar ${message.type}`}>
        <img 
          src={isUser ? '/icons/account-avatar-profile-user-7-svgrepo-com.svg' : '/icons/scientist-medium-dark-skin-tone-svgrepo-com.svg'} 
          alt={isUser ? '사용자' : 'AI'} 
          width="50" 
          height="50"
          className="home-avatar-icon"
        />
      </div>
      <div className={`home-message-content ${message.type}`}>
        <div className="home-message-text">{message.content}</div>
        
        {message.progress && message.progress.length > 0 && (
          <ProgressDisplay steps={message.progress} />
        )}
        
        {message.result && (
          <ResultDisplay result={message.result} />
        )}
      </div>
    </div>
  );
}
