'use client';

import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface SearchResult {
  id: string;
  title: string;
  url?: string;
  hierarchy: string[];
  content: string;
  content_preview: string;
  similarity_score: number;
  search_type: 'vector' | 'text';
  search_source?: string;
  raw_score?: number;
  search_method?: string;
  score_label?: string;
  metadata: Record<string, any>;
}

interface SearchResponse {
  query: string;
  totalResults: number;
  vectorResultsCount: number;
  textResultsCount: number;
  results: SearchResult[];
}

export default function DocumentSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchInfo, setSearchInfo] = useState<{
    totalResults: number;
    vectorResultsCount: number;
    textResultsCount: number;
  } | null>(null);
  const [includeContent, setIncludeContent] = useState(true);
  const [limit, setLimit] = useState(20);
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    try {
      const searchUrl = new URL('/api/rag/search', window.location.origin);
      searchUrl.searchParams.set('query', searchQuery.trim());
      searchUrl.searchParams.set('limit', limit.toString());
      searchUrl.searchParams.set('include_content', includeContent.toString());

      const response = await fetch(searchUrl.toString());
      
      if (response.ok) {
        const data: SearchResponse = await response.json();
        setResults(data.results);
        setSearchInfo({
          totalResults: data.totalResults,
          vectorResultsCount: data.vectorResultsCount,
          textResultsCount: data.textResultsCount,
        });
      } else {
        const error = await response.json();
        console.error('Search error:', error);
        setResults([]);
        setSearchInfo(null);
        
        // Show user-friendly error message
        const errorMessage = error.error || '검색 중 오류가 발생했습니다.';
        alert(`검색 실패: ${errorMessage}`);
      }
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
      setSearchInfo(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(query);
  };

  const getSearchTypeIcon = (type: 'vector' | 'text') => {
    return type === 'vector' ? '[V]' : '[T]';
  };

  const getSearchTypeLabel = (type: 'vector' | 'text') => {
    return type === 'vector' ? '벡터 검색' : '텍스트 검색';
  };

  const formatHierarchy = (hierarchy: string[]) => {
    return hierarchy.length > 0 ? hierarchy.join(' > ') : '';
  };

  const toggleExpanded = (resultId: string) => {
    const newExpanded = new Set(expandedResults);
    if (newExpanded.has(resultId)) {
      newExpanded.delete(resultId);
    } else {
      newExpanded.add(resultId);
    }
    setExpandedResults(newExpanded);
  };

  const isExpanded = (resultId: string) => {
    return expandedResults.has(resultId);
  };

  const shouldTruncate = (content: string) => {
    return content.length > 1000; // 1000자 이상이면 축약 표시
  };

  return (
    <div className="document-search-container">

      <div className="search-controls">
        <form onSubmit={handleSubmit} className="search-form">
          <div className="search-input-group">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="검색할 키워드나 문구를 입력하세요..."
              className="search-input"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={!query.trim() || loading}
              className="search-button"
            >
              {loading ? '검색 중...' : '검색'}
            </button>
          </div>
        </form>

        <div className="search-options">
          <div className="option-group">
            <label className="option-label">
              <input
                type="checkbox"
                checked={includeContent}
                onChange={(e) => setIncludeContent(e.target.checked)}
                className="option-checkbox"
              />
              전체 내용 포함
            </label>
          </div>
          <div className="option-group">
            <label className="option-label">
              결과 수:
              <select
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value))}
                className="option-select"
              >
                <option value={10}>10개</option>
                <option value={20}>20개</option>
                <option value={50}>50개</option>
                <option value={100}>100개</option>
              </select>
            </label>
          </div>
        </div>
      </div>

      {searchInfo && (
        <div className="search-info">
          <div className="search-stats">
            <span className="stat-item">
              총 <strong>{searchInfo.totalResults}</strong>개 결과
            </span>
            <span className="stat-item">
              벡터 검색: <strong>{searchInfo.vectorResultsCount}</strong>개
            </span>
            <span className="stat-item">
              텍스트 검색: <strong>{searchInfo.textResultsCount}</strong>개
            </span>
          </div>
        </div>
      )}

      <div className="search-results">
        {loading ? (
          <div className="loading-state">
            <div className="loading-spinner">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p>문서를 검색하고 있습니다...</p>
          </div>
        ) : results.length > 0 ? (
          <div className="results-list">
            {results.map((result, index) => (
              <div key={result.id} className="result-item">
                <div className="result-header">
                  <div className="result-title-section">
                    <h3 className="result-title">
                      {getSearchTypeIcon(result.search_type)} {result.title}
                    </h3>
                    <div className="result-meta">
                      <span className="search-type">
                        {getSearchTypeIcon(result.search_type)} {getSearchTypeLabel(result.search_type)}
                      </span>
                      <span className="similarity-score">
                        {result.score_label || '점수'}: {result.similarity_score.toFixed(3)}
                      </span>
                      {result.search_method && (
                        <span className="search-method">
                          {result.search_source === 'vector' ? '[V]' : '[T]'} {result.search_method}
                        </span>
                      )}
                      {result.raw_score !== undefined && (
                        <span className="raw-score">
                          원본: {result.raw_score.toFixed(3)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {result.hierarchy.length > 0 && (
                  <div className="result-hierarchy">
                    <img 
                      src="/icons/document-file-page-paper-svgrepo-com.svg" 
                      alt="폴더" 
                      width="40" 
                      height="40"
                      className="hierarchy-icon"
                    />
                    {formatHierarchy(result.hierarchy)}
                  </div>
                )}

                <div className="result-content">
                  {includeContent ? (
                    <div>
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        className="markdown-content"
                      >
                        {isExpanded(result.id) || !shouldTruncate(result.content) 
                          ? result.content 
                          : result.content.substring(0, 1000) + '...'
                        }
                      </ReactMarkdown>
                      {shouldTruncate(result.content) && (
                        <button
                          onClick={() => toggleExpanded(result.id)}
                          className="expand-button"
                        >
                          {isExpanded(result.id) ? '접기 ▲' : '더 보기 ▼'}
                        </button>
                      )}
                    </div>
                  ) : (
                    <p className="content-preview">{result.content_preview}</p>
                  )}
                </div>

                {result.url && (
                  <div className="result-footer">
                    <a 
                      href={result.url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="result-url"
                    >
                      [링크] 원본 문서 보기
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : query && !loading ? (
          <div className="no-results">
            <div className="no-results-icon">[검색]</div>
            <h3>검색 결과가 없습니다</h3>
            <p>다른 키워드로 검색해보세요</p>
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">
              <img 
                src="/icons/document-file-page-paper-svgrepo-com.svg" 
                alt="문서" 
                width="40" 
                height="40"
              />
            </div>
            <h3>문서를 검색해보세요</h3>
            <p>업로드된 문서에서 원하는 정보를 찾을 수 있습니다</p>
            <div className="example-queries">
              <div className="example-title">예시 검색어:</div>
              <div className="example-item" onClick={() => handleSearch('홈코노미')}>"홈코노미"</div>
              <div className="example-item" onClick={() => handleSearch('eSIM')}>"eSIM"</div>
              <div className="example-item" onClick={() => handleSearch('요금제')}>"요금제"</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
