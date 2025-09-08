import { NextRequest, NextResponse } from 'next/server';

const MCP_CLIENT_URL = process.env.MCP_CLIENT_URL || 'http://localhost:8000';

export async function DELETE(request: NextRequest) {
  try {
    console.log('RAG Delete API - MCP_CLIENT_URL:', MCP_CLIENT_URL);
    console.log('RAG Delete API - Full URL:', `${MCP_CLIENT_URL}/api/rag/data`);
    
    const response = await fetch(`${MCP_CLIENT_URL}/api/rag/data`, {
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
