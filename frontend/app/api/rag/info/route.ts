import { NextRequest, NextResponse } from 'next/server';

const MCP_CLIENT_URL = process.env.MCP_CLIENT_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    console.log('RAG Info API - MCP_CLIENT_URL:', MCP_CLIENT_URL);
    console.log('RAG Info API - Full URL:', `${MCP_CLIENT_URL}/api/rag/data/info`);
    
    const response = await fetch(`${MCP_CLIENT_URL}/api/rag/data/info`, {
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
