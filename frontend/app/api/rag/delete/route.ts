import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export async function DELETE(request: NextRequest) {
  try {
    console.log('RAG Delete API - MCP_CLIENT_URL:', API_BASE_URL);
    console.log('RAG Delete API - Full URL:', `${API_BASE_URL}/api/rag/data`);
    
    const response = await fetch(`${API_BASE_URL}/api/rag/data`, {
      method: 'DELETE',
      cache: 'no-cache',
      headers: {
        'Cache-Control': 'no-cache',
      },
    });

    console.log('RAG Delete API - Response status:', response.status);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      return NextResponse.json(
        { error: errorData.detail || errorData.error || errorData.message || 'Delete failed' },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json({
      message: result.message,
      processingTime: result.processing_time,
      details: result.details,
    });

  } catch (error) {
    console.error('RAG delete error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
