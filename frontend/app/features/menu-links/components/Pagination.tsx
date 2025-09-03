'use client';

import React from 'react';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({ 
  currentPage, 
  totalPages, 
  totalItems, 
  onPageChange 
}: PaginationProps) {
  if (totalPages <= 1) return null;

  // 페이지 번호 생성 로직
  const getPageNumbers = () => {
    const pages = [];
    const maxVisiblePages = 7; // 표시할 최대 페이지 수
    
    if (totalPages <= maxVisiblePages) {
      // 총 페이지가 적으면 모든 페이지 표시
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // 많은 페이지의 경우 현재 페이지 중심으로 표시
      const startPage = Math.max(1, currentPage - 3);
      const endPage = Math.min(totalPages, currentPage + 3);
      
      // 첫 페이지
      if (startPage > 1) {
        pages.push(1);
        if (startPage > 2) {
          pages.push('...');
        }
      }
      
      // 중간 페이지들
      for (let i = startPage; i <= endPage; i++) {
        pages.push(i);
      }
      
      // 마지막 페이지
      if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
          pages.push('...');
        }
        pages.push(totalPages);
      }
    }
    
    return pages;
  };

  const pageNumbers = getPageNumbers();

  return (
    <div className="pagination">
      <div className="pagination-controls">
        {/* 첫 페이지로 */}
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          className="pagination-button pagination-first"
          title="첫 페이지"
        >
          ««
        </button>
        
        {/* 이전 페이지 */}
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="pagination-button"
          title="이전 페이지"
        >
          ‹
        </button>
        
        {/* 페이지 번호들 */}
        <div className="pagination-numbers">
          {pageNumbers.map((page, index) => (
            <React.Fragment key={index}>
              {page === '...' ? (
                <span className="pagination-ellipsis">...</span>
              ) : (
                <button
                  onClick={() => onPageChange(page as number)}
                  className={`pagination-number ${currentPage === page ? 'active' : ''}`}
                  title={`${page}페이지로 이동`}
                >
                  {page}
                </button>
              )}
            </React.Fragment>
          ))}
        </div>
        
        {/* 다음 페이지 */}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="pagination-button"
          title="다음 페이지"
        >
          ›
        </button>
        
        {/* 마지막 페이지로 */}
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage === totalPages}
          className="pagination-button pagination-last"
          title="마지막 페이지"
        >
          »»
        </button>
      </div>
      
      <div className="pagination-info">
        <span>총 {totalItems}개 항목</span>
        <span>{currentPage} / {totalPages} 페이지</span>
      </div>
    </div>
  );
}
