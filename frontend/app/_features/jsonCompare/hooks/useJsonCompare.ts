'use client';

import { useState, useRef } from 'react';
import { JsonComparisonResult, JsonComparisonTask, EmptyUrlItem } from '@/app/_lib/types';

export function useJsonCompare() {
  const [file1, setFile1] = useState<File | null>(null);
  const [file2, setFile2] = useState<File | null>(null);
  const [isComparing, setIsComparing] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<JsonComparisonTask | null>(null);
  const [result, setResult] = useState<JsonComparisonResult | null>(null);
  const [emptyUrlItems, setEmptyUrlItems] = useState<EmptyUrlItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragOverFile1, setDragOverFile1] = useState(false);
  const [dragOverFile2, setDragOverFile2] = useState(false);
  
  const file1Ref = useRef<HTMLInputElement>(null);
  const file2Ref = useRef<HTMLInputElement>(null);

  const handleFile1Change = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.name.endsWith('.json')) {
        setFile1(file);
        setError(null);
      } else {
        setError('첫 번째 파일은 JSON 형식이어야 합니다.');
        setFile1(null);
      }
    } else {
      setFile1(null);
    }
  };

  const handleFile2Change = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.name.endsWith('.json')) {
        setFile2(file);
        setError(null);
      } else {
        setError('두 번째 파일은 JSON 형식이어야 합니다.');
        setFile2(null);
      }
    } else {
      setFile2(null);
    }
  };

  const handleCompare = async () => {
    if (!file1 || !file2) {
      setError('두 개의 JSON 파일을 모두 선택해주세요.');
      return;
    }

    setIsComparing(true);
    setError(null);
    setResult(null);
    setTaskStatus(null);

    try {
      const formData = new FormData();
      formData.append('file1', file1);
      formData.append('file2', file2);

      const response = await fetch('/api/json-compare/compare', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '비교 작업 생성에 실패했습니다.');
      }

      const data = await response.json();
      setTaskId(data.task_id);
      
      // 폴링으로 작업 상태 확인
      pollTaskStatus(data.task_id);

    } catch (err) {
      setError(err instanceof Error ? err.message : '비교 작업 중 오류가 발생했습니다.');
      setIsComparing(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const poll = async () => {
      try {
        const response = await fetch(`/api/json-compare/task/${taskId}`);
        
        if (!response.ok) {
          throw new Error('작업 상태 조회에 실패했습니다.');
        }

        const status: JsonComparisonTask = await response.json();
        setTaskStatus(status);

        if (status.status === 'completed' && status.result) {
          setResult(status.result);
          setEmptyUrlItems(status.empty_url_items || []);
          setIsComparing(false);
        } else if (status.status === 'failed') {
          setError(status.error_message || '비교 작업이 실패했습니다.');
          setIsComparing(false);
        } else {
          // 2초 후 다시 폴링
          setTimeout(poll, 2000);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '작업 상태 확인 중 오류가 발생했습니다.');
        setIsComparing(false);
      }
    };

    poll();
  };

  const handleDownload = async () => {
    if (!taskId) return;

    try {
      const response = await fetch(`/api/json-compare/task/${taskId}/download`);
      
      if (!response.ok) {
        throw new Error('PDF 다운로드에 실패했습니다.');
      }

      // 현재 시간을 report_YYYY-MM-DD_HHMM 형식으로 생성
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      
      const filename = `report_${year}-${month}-${day}_${hours}${minutes}.pdf`;

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PDF 다운로드 중 오류가 발생했습니다.');
    }
  };

  const resetForm = () => {
    setFile1(null);
    setFile2(null);
    setIsComparing(false);
    setTaskId(null);
    setTaskStatus(null);
    setResult(null);
    setEmptyUrlItems([]);
    setError(null);
    
    if (file1Ref.current) file1Ref.current.value = '';
    if (file2Ref.current) file2Ref.current.value = '';
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>, fileNumber: 1 | 2) => {
    e.preventDefault();
    if (fileNumber === 1) {
      setDragOverFile1(false);
    } else {
      setDragOverFile2(false);
    }
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.name.endsWith('.json')) {
        if (fileNumber === 1) {
          setFile1(file);
        } else {
          setFile2(file);
        }
        setError(null);
      } else {
        setError(`${fileNumber === 1 ? '첫 번째' : '두 번째'} 파일은 JSON 형식이어야 합니다.`);
      }
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>, fileNumber: 1 | 2) => {
    e.preventDefault();
    if (fileNumber === 1) {
      setDragOverFile1(true);
    } else {
      setDragOverFile2(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>, fileNumber: 1 | 2) => {
    e.preventDefault();
    if (fileNumber === 1) {
      setDragOverFile1(false);
    } else {
      setDragOverFile2(false);
    }
  };

  return {
    file1,
    file2,
    isComparing,
    taskId,
    taskStatus,
    result,
    emptyUrlItems,
    error,
    file1Ref,
    file2Ref,
    dragOverFile1,
    dragOverFile2,
    handleFile1Change,
    handleFile2Change,
    handleCompare,
    handleDownload,
    resetForm,
    handleFileDrop,
    handleDragOver,
    handleDragEnter,
    handleDragLeave,
  };
}
