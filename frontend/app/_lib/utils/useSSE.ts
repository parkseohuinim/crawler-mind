'use client';

import { useEffect, useRef, useState } from 'react';
import { SSEEvent } from '@/app/_lib/types';

interface UseSSEProps {
  taskId: string | null;
  onEvent: (event: SSEEvent) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export function useSSE({ taskId, onEvent, onError, onComplete }: UseSSEProps) {
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastEventWasFinalRef = useRef<boolean>(false);

  useEffect(() => {
    if (!taskId) return;

    const connectSSE = () => {
      try {
        // 직접 백엔드에 연결 (프록시 우회)
        const eventSource = new EventSource(`/api/stream/${taskId}`);
        eventSourceRef.current = eventSource;

        eventSource.onopen = () => {
          setIsConnected(true);
          console.log('SSE connection established');
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            // final/complete 수신 여부 기록 (브라우저 onerror 대비)
            if (data?.type === 'final' || data?.type === 'complete') {
              lastEventWasFinalRef.current = true;
            }
            onEvent(data);
          } catch (error) {
            console.error('Error parsing SSE data:', error);
            onError?.(new Error('Failed to parse SSE data'));
          }
        };

        eventSource.onerror = async (error) => {
          // 최종 완료 이후 발생하는 onerror는 정보성으로만 취급
          setIsConnected(false);
          
          // 이미 final/complete를 받았거나 연결이 정상 종료된 경우 완료로 처리
          if (lastEventWasFinalRef.current || eventSource.readyState === EventSource.CLOSED) {
            console.log('SSE connection closed (post-final)');
            onComplete?.();
          } else {
            console.warn('SSE connection error, readyState:', eventSource.readyState);
            // 스트림 에러 시 최종 결과가 준비되었는지 확인
            try {
              const res = await fetch(`/api/result/${taskId}`, { cache: 'no-store' });
              if (res.ok) {
                const data = await res.json();
                if (data?.result) {
                  onEvent({ type: 'final', data: data.result, timestamp: new Date().toISOString() });
                  try { eventSource.close(); } catch {}
                  onComplete?.();
                  return;
                }
              }
            } catch (_) {}
            onError?.(new Error('SSE connection error'));
          }
        };

        // 커스텀 이벤트 리스너들
        eventSource.addEventListener('connected', (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('SSE stream connected:', data);
          } catch (error) {
            console.error('Error parsing connected event:', error);
          }
        });

        eventSource.addEventListener('status', (event) => {
          try {
            const data = JSON.parse(event.data);
            onEvent({ type: 'status', data, timestamp: new Date().toISOString() });
          } catch (error) {
            console.error('Error parsing status event:', error);
          }
        });

        eventSource.addEventListener('tool_call', (event) => {
          try {
            const data = JSON.parse(event.data);
            onEvent({ type: 'tool_call', data, timestamp: new Date().toISOString() });
          } catch (error) {
            console.error('Error parsing tool_call event:', error);
          }
        });

        eventSource.addEventListener('partial', (event) => {
          try {
            const data = JSON.parse(event.data);
            onEvent({ type: 'partial', data, timestamp: new Date().toISOString() });
          } catch (error) {
            console.error('Error parsing partial event:', error);
          }
        });

        eventSource.addEventListener('final', (event) => {
          try {
            const data = JSON.parse(event.data);
            onEvent({ type: 'final', data, timestamp: new Date().toISOString() });
            // final 이벤트 후 연결 종료
            lastEventWasFinalRef.current = true;
            setTimeout(() => {
              eventSource.close();
              onComplete?.();
            }, 100);
          } catch (error) {
            console.error('Error parsing final event:', error);
          }
        });

        eventSource.addEventListener('complete', (event) => {
          try {
            const data = JSON.parse(event.data);
            onEvent({ type: 'final', data, timestamp: new Date().toISOString() });
            lastEventWasFinalRef.current = true;
            eventSource.close();
            onComplete?.();
          } catch (error) {
            console.error('Error parsing complete event:', error);
          }
        });


      } catch (error) {
        console.error('Failed to create SSE connection:', error);
        onError?.(error as Error);
      }
    };

    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsConnected(false);
    };
  }, [taskId, onEvent, onError, onComplete]);

  const disconnect = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    }
  };

  return {
    isConnected,
    disconnect,
  };
}
