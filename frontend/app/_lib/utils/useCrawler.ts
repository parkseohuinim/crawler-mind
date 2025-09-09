'use client';

import { useState, useCallback } from 'react';
import { Message, ProcessingMode, SSEEvent, ProgressStep, CrawlingResult, TaskResponse } from '@/app/_lib/types';
import { useSSE } from './useSSE';

export function useCrawler() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'assistant',
      content: '안녕하세요! 웹사이트 크롤링 AI 어시스턴트입니다. 분석할 웹사이트의 URL을 입력해주세요.',
      timestamp: new Date(),
    }
  ]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

  const handleSSEEvent = useCallback((event: SSEEvent) => {
    setMessages(prevMessages => {
      const updatedMessages = [...prevMessages];
      const assistantMessageIndex = updatedMessages.length - 1;
      
      if (assistantMessageIndex >= 0 && updatedMessages[assistantMessageIndex].type === 'assistant') {
        const assistantMessage = { ...updatedMessages[assistantMessageIndex] };
        
        switch (event.type) {
          case 'status':
            // 진행 상태 업데이트
            const progressSteps = assistantMessage.progress || [];
            const newStep: ProgressStep = {
              id: `step-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              message: event.data.message || '처리 중...',
              status: event.data.status || 'active',
              timestamp: new Date(event.timestamp),
            };
            
            assistantMessage.progress = [...progressSteps, newStep];
            break;
            
          case 'tool_call':
            // 도구 호출 상태 업데이트
            const toolSteps = assistantMessage.progress || [];
            const toolStep: ProgressStep = {
              id: `tool-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              message: `${event.data.tool_name} 실행 중...`,
              status: 'active',
              timestamp: new Date(event.timestamp),
            };
            
            assistantMessage.progress = [...toolSteps, toolStep];
            break;
            
          case 'partial':
            // 부분 결과 업데이트
            if (assistantMessage.progress) {
              const lastStepIndex = assistantMessage.progress.length - 1;
              if (lastStepIndex >= 0) {
                assistantMessage.progress[lastStepIndex] = {
                  ...assistantMessage.progress[lastStepIndex],
                  status: 'completed',
                };
              }
            }
            break;
            
          case 'final':
            // 최종 결과 업데이트
            assistantMessage.result = event.data as CrawlingResult;
            if (assistantMessage.progress) {
              assistantMessage.progress = assistantMessage.progress.map(step => ({
                ...step,
                status: step.status === 'active' ? 'completed' : step.status,
              }));
            }
            break;
            
          case 'error':
            // 에러 처리
            assistantMessage.result = {
              error: event.data.message || '처리 중 오류가 발생했습니다.',
            };
            if (assistantMessage.progress) {
              assistantMessage.progress = assistantMessage.progress.map(step => ({
                ...step,
                status: step.status === 'active' ? 'error' : step.status,
              }));
            }
            break;
        }
        
        updatedMessages[assistantMessageIndex] = assistantMessage;
      }
      
      return updatedMessages;
    });
  }, []);

  const handleSSEComplete = useCallback(async () => {
    // SSE 완료 후 백엔드에서 최종 결과를 한번 더 조회하여 스냅샷을 보장
    if (currentTaskId) {
      try {
        const res = await fetch(`/api/result/${currentTaskId}`);
        if (res.ok) {
          const data = await res.json();
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].type === 'assistant') {
              updated[lastIdx] = {
                ...updated[lastIdx],
                result: data.result ?? updated[lastIdx].result,
              };
            }
            return updated;
          });
        }
      } catch (_) {}
    }
    setIsProcessing(false);
    setCurrentTaskId(null);
  }, [currentTaskId]);

  const handleSSEError = useCallback(async (error: Error) => {
    console.error('SSE Error:', error);
    // 에러가 와도 최종 결과가 생성되어 있을 수 있으므로 즉시 결과 조회 시도
    if (currentTaskId) {
      try {
        const res = await fetch(`/api/result/${currentTaskId}`);
        if (res.ok) {
          const data = await res.json();
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].type === 'assistant') {
              updated[lastIdx] = {
                ...updated[lastIdx],
                result: data.result ?? { error: error.message || '연결 오류가 발생했습니다.' },
              };
            }
            return updated;
          });
        }
      } catch (_) {
        // 조회 실패 시 기존 방식대로 에러 표시
        setMessages(prevMessages => {
          const updatedMessages = [...prevMessages];
          const lastMessageIndex = updatedMessages.length - 1;
          
          if (lastMessageIndex >= 0 && updatedMessages[lastMessageIndex].type === 'assistant') {
            updatedMessages[lastMessageIndex] = {
              ...updatedMessages[lastMessageIndex],
              result: {
                error: error.message || '연결 오류가 발생했습니다.',
              },
            };
          }
          
          return updatedMessages;
        });
      }
    }
    setIsProcessing(false);
    setCurrentTaskId(null);
  }, [currentTaskId]);

  const { isConnected, disconnect } = useSSE({
    taskId: currentTaskId,
    onEvent: handleSSEEvent,
    onError: handleSSEError,
    onComplete: handleSSEComplete,
  });

  const processUrl = useCallback(async (url: string, mode: ProcessingMode) => {
    if (isProcessing) return;

    // 사용자 메시지 추가
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: url,
      timestamp: new Date(),
    };

    // AI 응답 메시지 준비
    const assistantMessage: Message = {
      id: `assistant-${Date.now()}`,
      type: 'assistant',
      content: `${url} 을(를) 분석하고 있습니다...`,
      timestamp: new Date(),
      progress: [],
    };

    setMessages(prev => [...prev, userMessage, assistantMessage]);
    setIsProcessing(true);

    try {
      // 작업 시작 요청
      const response = await fetch('/api/process-url', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url, mode }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: TaskResponse = await response.json();
      console.log('Task created with ID:', data.taskId);
      
      // Task 생성 후 잠시 대기 (백엔드에서 스트림 준비 시간)
      await new Promise(resolve => setTimeout(resolve, 300));
      
      setCurrentTaskId(data.taskId);
      
    } catch (error) {
      console.error('Error starting task:', error);
      setIsProcessing(false);
      
      setMessages(prevMessages => {
        const updatedMessages = [...prevMessages];
        const lastMessageIndex = updatedMessages.length - 1;
        
        if (lastMessageIndex >= 0) {
          updatedMessages[lastMessageIndex] = {
            ...updatedMessages[lastMessageIndex],
            content: 'URL 처리를 시작하는 중 오류가 발생했습니다.',
            result: {
              error: error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.',
            },
          };
        }
        
        return updatedMessages;
      });
    }
  }, [isProcessing]);

  const stopProcessing = useCallback(() => {
    disconnect();
    setIsProcessing(false);
    setCurrentTaskId(null);
  }, [disconnect]);

  return {
    messages,
    isProcessing,
    isConnected,
    processUrl,
    stopProcessing,
  };
}
