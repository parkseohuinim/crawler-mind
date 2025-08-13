import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

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

    const mcpClientUrl = process.env.MCP_CLIENT_URL || 'http://localhost:8000';

    // MCP Client의 결과 조회 엔드포인트 호출
    const response = await fetch(`${mcpClientUrl}/api/result/${taskId}`, {
      method: 'GET',
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Task not found' },
          { status: 404 }
        );
      }
      throw new Error(`MCP Client responded with status: ${response.status}`);
    }

    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching task result:', error);
    return NextResponse.json(
      { error: 'Failed to fetch task result' },
      { status: 500 }
    );
  }
}
