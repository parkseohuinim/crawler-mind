import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('query');
    const limit = parseInt(searchParams.get('limit') || '20');
    const includeContent = searchParams.get('include_content') === 'true';

    if (!query || typeof query !== 'string' || !query.trim()) {
      return NextResponse.json(
        { error: 'Query parameter is required and must be a non-empty string' },
        { status: 400 }
      );
    }

    const searchUrl = new URL(`${API_BASE_URL}/api/rag/search`);
    searchUrl.searchParams.set('query', query.trim());
    searchUrl.searchParams.set('limit', limit.toString());
    searchUrl.searchParams.set('include_content', includeContent.toString());

    console.log('Fetching from:', searchUrl.toString());
    
    const response = await fetch(searchUrl.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    console.log('Response status:', response.status);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      console.error('Backend error:', errorData);
      return NextResponse.json(
        { error: errorData.detail || errorData.message || 'Search failed' },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json({
      query: result.query,
      totalResults: result.total_results,
      vectorResultsCount: result.vector_results_count,
      textResultsCount: result.text_results_count,
      results: result.results,
    });

  } catch (error) {
    console.error('Document search error:', error);
    
    // Check if it's a connection error
    if (error instanceof TypeError && error.message.includes('fetch')) {
      return NextResponse.json(
        { error: '백엔드 서버에 연결할 수 없습니다. MCP 클라이언트가 실행 중인지 확인해주세요.' },
        { status: 503 }
      );
    }
    
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
