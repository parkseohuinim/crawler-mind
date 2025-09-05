'use client';

import { useState } from 'react';

interface RagUploadProps {
  onUploadSuccess?: () => void;
}

export default function RagUpload({ onUploadSuccess }: RagUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && selectedFile.type === 'application/json') {
      setFile(selectedFile);
      setMessage('');
    } else {
      setMessage('JSON 파일만 업로드 가능합니다.');
      setFile(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setMessage('파일을 선택해주세요.');
      return;
    }

    setUploading(true);
    setMessage('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/rag/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        setMessage(`업로드 완료! ${result.processedCount}개 문서가 처리되었습니다.`);
        setFile(null);
        onUploadSuccess?.();
      } else {
        const error = await response.json();
        setMessage(`업로드 실패: ${error.error}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      setMessage('업로드 중 오류가 발생했습니다.');
    } finally {
      setUploading(false);
    }
  };

  const resetFile = () => {
    setFile(null);
    setMessage('');
  };

  return (
    <div className="rag-upload-container">
      <div className="rag-upload-header">
        <h2>📁 RAG 데이터 업로드</h2>
        <p>JSON 형태의 문서 데이터를 업로드하여 AI 질의응답에 활용하세요</p>
      </div>
      
      <div className="rag-upload-content">
        <div className="file-input-section">
          <label className="file-input-label">
            JSON 파일 선택
          </label>
          <div className="file-input-wrapper">
            <input
              type="file"
              accept=".json"
              onChange={handleFileSelect}
              disabled={uploading}
              className="file-input"
              id="rag-file-input"
            />
            <label htmlFor="rag-file-input" className="file-input-button">
              {file ? '다른 파일 선택' : '파일 선택'}
            </label>
          </div>
        </div>

        {file && (
          <div className="selected-file-info">
            <div className="file-details">
              <span className="file-icon">📄</span>
              <div className="file-info">
                <div className="file-name">{file.name}</div>
                <div className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
              </div>
              <button onClick={resetFile} className="file-remove-btn" disabled={uploading}>
                ✕
              </button>
            </div>
          </div>
        )}

        <div className="upload-actions">
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="upload-button"
          >
            {uploading ? (
              <>
                <span className="upload-spinner"></span>
                업로드 중... (최대 30분 소요)
              </>
            ) : (
              <>
                <span>📤</span>
                업로드 시작
              </>
            )}
          </button>
        </div>

        {message && (
          <div className={`upload-message ${
            message.includes('완료') ? 'success' : 'error'
          }`}>
            <span className="message-icon">
              {message.includes('완료') ? '✅' : '❌'}
            </span>
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
