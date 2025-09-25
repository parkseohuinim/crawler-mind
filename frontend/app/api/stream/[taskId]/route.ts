import { NextRequest, NextResponse } from 'next/server';

export async function GET(
  request: NextRequest,
  { params }: { params: { taskId: string } }
) {
  try {
    const { taskId } = params;

    if (!taskId) {
      return NextResponse.json(
        { error: 'Task ID is required' },
        { status: 400 }
      );
    }

    const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

    // MCP Client의 RAG 크롤링 SSE 스트림에 연결
    const response = await fetch(`${API_BASE_URL}/api/rag-crawl/${taskId}/stream`, {
      headers: {
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
    });

    if (!response.ok) {
      throw new Error(`MCP Client responded with status: ${response.status}`);
    }

    // SSE 스트림을 그대로 프록시
    return new NextResponse(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
        'Access-Control-Allow-Headers': 'Cache-Control',
      },
    });
  } catch (error) {
    console.error('Error streaming task:', error);
    return NextResponse.json(
      { error: 'Failed to stream task updates' },
      { status: 500 }
    );
  }
}
