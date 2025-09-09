'use client';

import React from 'react';

interface ModernFileUploadProps {
  file1: File | null;
  file2: File | null;
  file1Ref: React.RefObject<HTMLInputElement>;
  file2Ref: React.RefObject<HTMLInputElement>;
  dragOverFile1: boolean;
  dragOverFile2: boolean;
  isComparing: boolean;
  onFile1Change: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFile2Change: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFileDrop: (e: React.DragEvent<HTMLDivElement>, fileNumber: 1 | 2) => void;
  onDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragEnter: (e: React.DragEvent<HTMLDivElement>, fileNumber: 1 | 2) => void;
  onDragLeave: (e: React.DragEvent<HTMLDivElement>, fileNumber: 1 | 2) => void;
}

export default function ModernFileUpload({
  file1,
  file2,
  file1Ref,
  file2Ref,
  dragOverFile1,
  dragOverFile2,
  isComparing,
  onFile1Change,
  onFile2Change,
  onFileDrop,
  onDragOver,
  onDragEnter,
  onDragLeave,
}: ModernFileUploadProps) {
  return (
    <div className="modern-file-upload-container">
      <div className="modern-file-upload-grid">
        <div className="modern-file-upload-item">
          <div className="modern-file-upload-header">
            <div className="modern-file-upload-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14,2 14,8 20,8"></polyline>
              </svg>
            </div>
            <h3>첫 번째 JSON 파일</h3>
          </div>
          
          <div 
            className={`modern-file-drop-zone ${dragOverFile1 ? 'dragover' : ''} ${file1 ? 'has-file' : ''}`}
            onDrop={(e) => onFileDrop(e, 1)}
            onDragOver={onDragOver}
            onDragEnter={(e) => onDragEnter(e, 1)}
            onDragLeave={(e) => onDragLeave(e, 2)}
          >
            <input
              ref={file1Ref}
              type="file"
              accept=".json"
              onChange={onFile1Change}
              className="modern-file-input"
              disabled={isComparing}
            />
            
            {file1 ? (
              <div className="modern-file-selected">
                <div className="modern-file-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14,2 14,8 20,8"></polyline>
                  </svg>
                </div>
                <div className="modern-file-info">
                  <div className="modern-file-name">{file1.name}</div>
                  <div className="modern-file-size">{(file1.size / 1024).toFixed(1)} KB</div>
                </div>
                <button 
                  className="modern-file-remove"
                  onClick={() => file1Ref.current?.click()}
                  disabled={isComparing}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 6L6 18"></path>
                    <path d="M6 6l12 12"></path>
                  </svg>
                </button>
              </div>
            ) : (
              <div className="modern-file-placeholder">
                <div className="modern-upload-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7,10 12,15 17,10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                </div>
                <div className="modern-upload-text">
                  <span>JSON 파일을 선택하거나 드래그하세요</span>
                  <small>(.json 파일만 지원)</small>
                </div>
              </div>
            )}
          </div>
        </div>
        
        <div className="modern-file-upload-item">
          <div className="modern-file-upload-header">
            <div className="modern-file-upload-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14,2 14,8 20,8"></polyline>
              </svg>
            </div>
            <h3>두 번째 JSON 파일</h3>
          </div>
          
          <div 
            className={`modern-file-drop-zone ${dragOverFile2 ? 'dragover' : ''} ${file2 ? 'has-file' : ''}`}
            onDrop={(e) => onFileDrop(e, 2)}
            onDragOver={onDragOver}
            onDragEnter={(e) => onDragEnter(e, 2)}
            onDragLeave={(e) => onDragLeave(e, 2)}
          >
            <input
              ref={file2Ref}
              type="file"
              accept=".json"
              onChange={onFile2Change}
              className="modern-file-input"
              disabled={isComparing}
            />
            
            {file2 ? (
              <div className="modern-file-selected">
                <div className="modern-file-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14,2 14,8 20,8"></polyline>
                  </svg>
                </div>
                <div className="modern-file-info">
                  <div className="modern-file-name">{file2.name}</div>
                  <div className="modern-file-size">{(file2.size / 1024).toFixed(1)} KB</div>
                </div>
                <button 
                  className="modern-file-remove"
                  onClick={() => file2Ref.current?.click()}
                  disabled={isComparing}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 6L6 18"></path>
                    <path d="M6 6l12 12"></path>
                  </svg>
                </button>
              </div>
            ) : (
              <div className="modern-file-placeholder">
                <div className="modern-upload-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7,10 12,15 17,10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                </div>
                <div className="modern-upload-text">
                  <span>JSON 파일을 선택하거나 드래그하세요</span>
                  <small>(.json 파일만 지원)</small>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
