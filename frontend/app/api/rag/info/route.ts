import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    console.log('RAG Info API - MCP_CLIENT_URL:', API_BASE_URL);
    console.log('RAG Info API - Full URL:', `${API_BASE_URL}/api/rag/data/info`);
    
    const response = await fetch(`${API_BASE_URL}/api/rag/data/info`, {
      method: 'GET',
      cache: 'no-cache', // 캐시 비활성화
      headers: {
        'Cache-Control': 'no-cache',
      },
    });

    console.log('RAG Info API - Response status:', response.status);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      console.log('RAG Info API - Error response:', errorData);
      return NextResponse.json(
        { error: errorData.detail || errorData.error || errorData.message || 'Failed to get data info' },
        { status: response.status }
      );
    }

    const result = await response.json();
    console.log('RAG Info API - Success response:', result);
    return NextResponse.json(result);

  } catch (error) {
    console.error('RAG info error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
