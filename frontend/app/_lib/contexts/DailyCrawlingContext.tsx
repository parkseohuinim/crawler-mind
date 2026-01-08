'use client';

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

// Types
export interface DailyCrawlingTask {
  taskId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  totalUrls: number;
  currentUrl?: string;
  progress: number; // 0-100
  successCount: number;
  failedCount: number;
  failedItems?: Array<{ id?: number; url: string; error: string }>;
  message: string;
  jsonFilePath?: string;
  createdAt: string;
  completedAt?: string;
  error?: string;
}

export interface DailyCrawlingOptions {
  mode: 'sequential' | 'parallel';
  concurrency: number;
  forceRecrawl: boolean;
  updateMenuLinks: boolean;
  limit?: number;
  urlIds?: number[];
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
  duration?: number;
}

interface DailyCrawlingContextType {
  // Task state
  currentTask: DailyCrawlingTask | null;
  taskHistory: DailyCrawlingTask[];
  isRunning: boolean;
  
  // Actions
  startCrawling: (options: DailyCrawlingOptions) => Promise<void>;
  cancelCrawling: () => void;
  clearTask: () => void;
  
  // Toast
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

const DailyCrawlingContext = createContext<DailyCrawlingContextType | undefined>(undefined);

export function DailyCrawlingProvider({ children }: { children: React.ReactNode }) {
  const [currentTask, setCurrentTask] = useState<DailyCrawlingTask | null>(null);
  const [taskHistory, setTaskHistory] = useState<DailyCrawlingTask[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const isCompletedRef = useRef<boolean>(false); // 완료 상태 즉시 추적
  const isRunning = currentTask?.status === 'running' || currentTask?.status === 'pending';

  // Toast management
  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast = { ...toast, id };
    setToasts(prev => [...prev, newToast]);

    // Auto remove after duration
    const duration = toast.duration ?? 5000;
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // 태스크 결과 조회 (백업 완료 처리용)
  const fetchTaskResult = useCallback(async (taskId: string): Promise<{ json_file?: string; success?: number; failed?: number; total?: number } | null> => {
    try {
      const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const response = await fetch(`${BACKEND_URL}/api/daily-crawling/${taskId}`);
      if (response.ok) {
        const data = await response.json();
        console.log('fetchTaskResult response:', data);
        if ((data.status === 'completed' || data.status === 'COMPLETED') && data.result) {
          return {
            json_file: data.result.json_file,
            success: data.result.success,
            failed: data.result.failed,
            total: data.result.total,
          };
        }
      }
    } catch (error) {
      console.error('Failed to fetch task result:', error);
    }
    return null;
  }, []);

  // 백업 완료 처리 (API 조회 후 완료)
  const handleBackupCompletion = useCallback(async (task: DailyCrawlingTask) => {
    console.log('Executing backup completion for task:', task.taskId);
    
    // 약간의 대기 후 API 조회 (백엔드가 결과를 저장할 시간 확보)
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    const result = await fetchTaskResult(task.taskId);
    console.log('Backup completion result:', result);
    
    const successCount = result?.success ?? task.successCount;
    const failedCount = result?.failed ?? task.failedCount;
    const jsonFilePath = result?.json_file;
    
    const completedTask: DailyCrawlingTask = {
      ...task,
      status: 'completed',
      progress: 100,
      successCount,
      failedCount,
      jsonFilePath,
      message: 'Daily Crawling 완료',
      completedAt: new Date().toISOString(),
    };
    
    // currentTask 업데이트
    setCurrentTask(completedTask);
    
    // 히스토리에 추가 (중복 방지)
    setTaskHistory(history => {
      const exists = history.some(t => t.taskId === completedTask.taskId);
      if (exists) {
        // 기존 항목 업데이트
        return history.map(t => t.taskId === completedTask.taskId ? completedTask : t);
      }
      return [completedTask, ...history.slice(0, 9)];
    });
    
    // 토스트 표시
    addToast({
      type: 'success',
      title: 'Daily Crawling 완료',
      message: `${successCount}개 성공, ${failedCount}개 실패`,
      duration: 10000,
    });
  }, [fetchTaskResult, addToast]);

  // SSE connection for task updates
  const connectSSE = useCallback((taskId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // 새 작업 시작 시 완료 상태 초기화
    isCompletedRef.current = false;

    // 백엔드 직접 연결 (프록시 우회)
    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const sseUrl = `${BACKEND_URL}/api/daily-crawling/${taskId}/stream`;
    console.log(`🔗 SSE connecting: ${sseUrl}`);
    const eventSource = new EventSource(sseUrl);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('✅ SSE connection opened');
    };

    eventSource.onmessage = (event) => {
      console.log('📩 SSE message received:', event.data);
      try {
        const data = JSON.parse(event.data);
        console.log('📊 SSE parsed data:', data);
        handleSSEEvent(data);
      } catch (error) {
        console.error('SSE parse error:', error);
      }
    };

    eventSource.onerror = async (error) => {
      console.warn('SSE connection error:', error);
      console.log('EventSource readyState:', eventSource.readyState);
      
      // 이미 완료된 경우 EventSource를 명시적으로 닫아서 재연결 방지
      if (isCompletedRef.current) {
        console.log('Task already completed, closing EventSource');
        eventSource.close();
        eventSourceRef.current = null;
        return;
      }
      
      // 연결이 끊어졌을 때 진행률이 높으면 완료로 처리 (백업 로직)
      setCurrentTask(prev => {
        if (prev && prev.progress >= 100 && prev.status === 'running') {
          console.log('Connection lost but progress is 100%, executing backup completion');
          isCompletedRef.current = true;
          eventSource.close();
          eventSourceRef.current = null;
          
          // 백업 완료 처리를 별도 함수로 실행 (API 조회 후 완료 처리)
          handleBackupCompletion(prev);
          
          // 일단 완료 상태로 전환 (결과는 나중에 업데이트)
          return {
            ...prev,
            status: 'completed' as const,
            message: '결과 조회 중...',
            completedAt: new Date().toISOString(),
          };
        }
        return prev;
      });
    };
  }, [handleBackupCompletion]);

  const handleSSEEvent = useCallback((event: { type: string; data: Record<string, unknown> }) => {
    setCurrentTask(prev => {
      if (!prev) return prev;

      switch (event.type) {
        case 'connected':
          return { ...prev, status: 'running' as const, message: '연결됨' };
        
        case 'status':
          return {
            ...prev,
            status: 'running' as const,
            message: (event.data.message as string) || prev.message,
            totalUrls: (event.data.total_urls as number) ?? prev.totalUrls,
          };
        
        case 'progress':
          const current = event.data.current as number;
          const total = event.data.total as number;
          const progress = total > 0 ? Math.round((current / total) * 100) : 0;
          return {
            ...prev,
            progress,
            successCount: (event.data.success as number) ?? prev.successCount,
            failedCount: (event.data.failed as number) ?? prev.failedCount,
            currentUrl: (event.data.url as string) || prev.currentUrl,
            message: (event.data.message as string) || `진행 중: ${current}/${total}`,
          };
        
        case 'final':
        case 'complete':
          // 이미 완료된 경우 중복 처리 방지
          if (isCompletedRef.current || prev.status === 'completed') {
            console.log('Task already completed, skipping duplicate event');
            return prev;
          }
          
          // 완료 상태 즉시 설정
          isCompletedRef.current = true;
          
          const completedTask: DailyCrawlingTask = {
            ...prev,
            status: 'completed' as const,
            progress: 100,
            successCount: (event.data.success as number) ?? prev.successCount,
            failedCount: (event.data.failed as number) ?? prev.failedCount,
            failedItems: event.data.failed_items as any[] | undefined,
            jsonFilePath: event.data.json_file as string | undefined,
            message: (event.data.message as string) || 'Daily Crawling 완료',
            completedAt: new Date().toISOString(),
          };
          
          // Add to history (중복 방지)
          setTaskHistory(history => {
            const exists = history.some(t => t.taskId === completedTask.taskId);
            if (exists) return history;
            return [completedTask, ...history.slice(0, 9)];
          });
          
          // Show toast
          addToast({
            type: 'success',
            title: 'Daily Crawling 완료',
            message: `${completedTask.successCount}개 성공, ${completedTask.failedCount}개 실패`,
            duration: 10000,
          });
          
          // Close SSE
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
          }
          
          return completedTask;
        
        case 'error':
          // 이미 완료된 경우 에러 무시 (정상 완료 후 연결 종료 시 발생하는 에러)
          if (isCompletedRef.current || prev.status === 'completed' || prev.status === 'failed') {
            console.log('Task already finished, ignoring error event');
            return prev;
          }
          
          // 완료 상태 즉시 설정
          isCompletedRef.current = true;
          
          const failedTask: DailyCrawlingTask = {
            ...prev,
            status: 'failed' as const,
            error: event.data.message as string,
            message: `오류: ${event.data.message}`,
            completedAt: new Date().toISOString(),
          };
          
          // Add to history (중복 방지)
          setTaskHistory(history => {
            const exists = history.some(t => t.taskId === failedTask.taskId);
            if (exists) return history;
            return [failedTask, ...history.slice(0, 9)];
          });
          
          // Show toast
          addToast({
            type: 'error',
            title: 'Daily Crawling 실패',
            message: event.data.message as string || '알 수 없는 오류가 발생했습니다',
            duration: 10000,
          });
          
          // Close SSE
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
          }
          
          return failedTask;
        
        default:
          return prev;
      }
    });
  }, [addToast]);

  const fetchTaskStatus = useCallback(async (taskId: string) => {
    try {
      const response = await fetch(`/api/daily-crawling/${taskId}`);
      if (response.ok) {
        const data = await response.json();
        const status = data.status?.toLowerCase();
        
        // SSE 이벤트 형식으로 변환하여 처리
        const eventData: any = {
          message: data.error || (status === 'completed' ? '완료됨' : '진행 중'),
        };
        
        if (data.result) {
          eventData.success = data.result.success;
          eventData.failed = data.result.failed;
          eventData.total = data.result.total;
          eventData.json_file = data.result.json_file;
          eventData.failed_items = data.result.failed_items;
        }

        handleSSEEvent({
          type: status === 'completed' ? 'complete' : (status === 'failed' ? 'error' : 'status'),
          data: eventData,
        });
        
        return data;
      }
    } catch (error) {
      console.error('Failed to fetch task status:', error);
    }
    return null;
  }, [handleSSEEvent]);

  // 초기 상태 복구
  const restoreTasks = useCallback(async () => {
    try {
      const response = await fetch('/api/daily-crawling/tasks');
      if (response.ok) {
        const tasks: any[] = await response.json();
        if (tasks && tasks.length > 0) {
          // TaskResult 형식을 DailyCrawlingTask 형식으로 변환
          const formattedTasks: DailyCrawlingTask[] = tasks.map(t => {
            const status = t.status.toLowerCase();
            const successCount = t.result?.success || 0;
            const failedCount = t.result?.failed || 0;
            const totalUrls = t.result?.total || 0;
            
            // 진척도 계산
            let progress = 0;
            if (status === 'completed') progress = 100;
            else if (totalUrls > 0) progress = Math.round(((successCount + failedCount) / totalUrls) * 100);

            return {
              taskId: t.taskId,
              status: status as any,
              totalUrls,
              progress,
              successCount,
              failedCount,
              failedItems: t.result?.failed_items,
              message: status === 'completed' ? '완료됨' : (status === 'failed' ? '실패함' : '진행 중'),
              jsonFilePath: t.result?.json_file,
              createdAt: t.createdAt,
              completedAt: t.completedAt,
              error: t.error
            };
          });

          // 진행 중인 작업 찾기
          const activeTask = formattedTasks.find(t => t.status === 'running' || t.status === 'pending');
          
          if (activeTask) {
            console.log('Restoring active task:', activeTask.taskId);
            setCurrentTask(activeTask);
            connectSSE(activeTask.taskId);
          } else if (formattedTasks.length > 0) {
            // 진행 중인 게 없으면 가장 최근 완료된 것 하나를 currentTask로 (선택사항)
            // 여기서는 히스토리만 업데이트
          }
          
          setTaskHistory(formattedTasks);
        }
      }
    } catch (error) {
      console.error('Failed to restore tasks:', error);
    }
  }, [connectSSE]);

  // Start crawling
  const startCrawling = useCallback(async (options: DailyCrawlingOptions) => {
    try {
      const response = await fetch('/api/daily-crawling', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: options.mode,
          concurrency: options.concurrency,
          force_recrawl: options.forceRecrawl,
          update_menu_links: options.updateMenuLinks,
          limit: options.limit,
          url_ids: options.urlIds,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start crawling');
      }

      const data = await response.json();
      
      if (!data.task_id) {
        addToast({
          type: 'info',
          title: '크롤링 대상 없음',
          message: data.message || '크롤링할 URL이 없습니다',
        });
        return;
      }

      const newTask: DailyCrawlingTask = {
        taskId: data.task_id,
        status: 'pending',
        totalUrls: data.total_urls,
        progress: 0,
        successCount: 0,
        failedCount: 0,
        message: data.message,
        createdAt: new Date().toISOString(),
      };

      setCurrentTask(newTask);
      
      addToast({
        type: 'info',
        title: 'Daily Crawling 시작',
        message: `${data.total_urls}개 URL 크롤링을 시작합니다`,
      });

      // Connect SSE
      connectSSE(data.task_id);
      
    } catch (error) {
      console.error('Failed to start crawling:', error);
      addToast({
        type: 'error',
        title: '시작 실패',
        message: error instanceof Error ? error.message : '크롤링 시작에 실패했습니다',
      });
    }
  }, [addToast, connectSSE]);

  // Cancel crawling (disconnect SSE)
  const cancelCrawling = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    if (currentTask) {
      setCurrentTask(prev => prev ? {
        ...prev,
        status: 'failed' as const,
        message: '사용자에 의해 취소됨',
        completedAt: new Date().toISOString(),
      } : null);
    }
    
    addToast({
      type: 'warning',
      title: '크롤링 중단',
      message: 'SSE 연결이 종료되었습니다. 서버에서 작업은 계속 진행될 수 있습니다.',
    });
  }, [currentTask, addToast]);

  // Clear current task
  const clearTask = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setCurrentTask(null);
  }, []);

  // 초기 마운트 시 한 번만 실행되는 작업 복구
  useEffect(() => {
    restoreTasks();
  }, [restoreTasks]);

  // 진행 중인 작업에 대한 주기적인 폴링 및 재연결 (Resilience)
  useEffect(() => {
    // 긴 시간 작업 대비 폴링 (1분마다 상태 확인 및 SSE 재연결 시도)
    const interval = setInterval(() => {
      if (currentTask && (currentTask.status === 'running' || currentTask.status === 'pending')) {
        console.log('Polling task status for resilience:', currentTask.taskId);
        fetchTaskStatus(currentTask.taskId).then(data => {
          // SSE 연결이 끊겨있다면 재연결
          if (data && data.status.toLowerCase() === 'running' && (!eventSourceRef.current || eventSourceRef.current.readyState === EventSource.CLOSED)) {
            console.log('SSE disconnected but task still running, reconnecting...');
            connectSSE(currentTask.taskId);
          }
        });
      }
    }, 60000);

    return () => {
      clearInterval(interval);
    };
  }, [currentTask, fetchTaskStatus, connectSSE]);

  // Unmount 시 정리
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return (
    <DailyCrawlingContext.Provider
      value={{
        currentTask,
        taskHistory,
        isRunning,
        startCrawling,
        cancelCrawling,
        clearTask,
        toasts,
        addToast,
        removeToast,
      }}
    >
      {children}
    </DailyCrawlingContext.Provider>
  );
}

export function useDailyCrawling() {
  const context = useContext(DailyCrawlingContext);
  if (context === undefined) {
    throw new Error('useDailyCrawling must be used within a DailyCrawlingProvider');
  }
  return context;
}

