'use client';

import { Message } from '../types';
import ProgressDisplay from './ProgressDisplay';
import ResultDisplay from './ResultDisplay';

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.type === 'user';

  return (
    <div className={`message ${message.type}`}>
      <div className={`message-avatar ${message.type}`}>
        {isUser ? '👤' : '🤖'}
      </div>
      <div className={`message-content ${message.type}`}>
        <div>{message.content}</div>
        
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
