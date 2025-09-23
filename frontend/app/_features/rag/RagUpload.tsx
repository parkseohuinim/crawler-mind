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
    console.log('Selected file:', selectedFile);
    console.log('File type:', selectedFile?.type);
    console.log('File name:', selectedFile?.name);
    
    if (selectedFile && (selectedFile.type === 'application/json' || selectedFile.name.endsWith('.json'))) {
      setFile(selectedFile);
      setMessage('');
      console.log('File accepted');
    } else {
      setMessage('JSON 파일만 업로드 가능합니다.');
      setFile(null);
      console.log('File rejected - type:', selectedFile?.type, 'name:', selectedFile?.name);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setMessage('파일을 선택해주세요.');
      return;
    }

    console.log('Starting upload for file:', file.name, 'size:', file.size);
    setUploading(true);
    setMessage('');

    try {
      const formData = new FormData();
      formData.append('file', file);
      console.log('FormData created, sending request...');

      const response = await fetch('/api/rag/upload', {
        method: 'POST',
        body: formData,
      });
      
      console.log('Response received:', response.status, response.statusText);

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
    <div className="modern-upload-container">
      <div className="modern-upload-header">
        <div className="upload-header-content">
          <div className="upload-icon">
            <img 
              src="/icons/upload-file-document-svgrepo-com.svg" 
              alt="업로드" 
              width="32" 
              height="32"
            />
          </div>
          <div className="upload-text">
            <h2>RAG 데이터 업로드</h2>
            <p>JSON 형태의 문서 데이터를 업로드하여 AI 질의응답에 활용하세요</p>
          </div>
        </div>
      </div>
      
      <div className="modern-upload-content">
        <div className="modern-file-section">
          <label className="modern-file-label">
            JSON 파일 선택
          </label>
          <div className="modern-file-wrapper">
            <input
              type="file"
              accept=".json"
              onChange={handleFileSelect}
              disabled={uploading}
              className="modern-file-input"
              id="rag-file-input"
            />
            <label htmlFor="rag-file-input" className="modern-file-button">
              {file ? '다른 파일 선택' : '파일 선택'}
            </label>
          </div>
        </div>

        {file && (
          <div className="modern-selected-file">
            <div className="modern-file-details">
              <div className="modern-file-icon">
                <img 
                  src="/icons/document-file-page-paper-svgrepo-com.svg" 
                  alt="파일" 
                  width="24" 
                  height="24"
                />
              </div>
              <div className="modern-file-info">
                <div className="modern-file-name">{file.name}</div>
                <div className="modern-file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
              </div>
              <button onClick={resetFile} className="modern-remove-btn" disabled={uploading}>
                <img 
                  src="/icons/delete-trash-svgrepo-com.svg" 
                  alt="삭제" 
                  width="16" 
                  height="16"
                />
              </button>
            </div>
          </div>
        )}

        <div className="modern-upload-actions">
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="modern-upload-button"
          >
            {uploading ? (
              <>
                <span className="modern-upload-spinner"></span>
                업로드 중... (최대 30분 소요)
              </>
            ) : (
              <>
                <img 
                  src="/icons/rocket-spaceship-start-svgrepo-com.svg" 
                  alt="업로드" 
                  width="20" 
                  height="20"
                />
                업로드 시작
              </>
            )}
          </button>
        </div>

        {message && (
          <div className={`modern-upload-message ${
            message.includes('완료') ? 'success' : 'error'
          }`}>
            <span className="modern-message-icon">
              {message.includes('완료') ? '✓' : '✗'}
            </span>
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
