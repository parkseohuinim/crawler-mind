import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { url, mode = 'auto' } = body;

    if (!url) {
      return NextResponse.json(
        { error: 'URL is required' },
        { status: 400 }
      );
    }

    // MCP Client 백엔드 서버 URL (환경변수로 설정)
    const mcpClientUrl = process.env.MCP_CLIENT_URL || 'http://localhost:8000';

    // MCP Client의 process-url 엔드포인트 호출
    const response = await fetch(`${mcpClientUrl}/api/process-url`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url, mode }),
    });

    if (!response.ok) {
      throw new Error(`MCP Client responded with status: ${response.status}`);
    }

    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error processing URL:', error);
    return NextResponse.json(
      { error: 'Failed to process URL' },
      { status: 500 }
    );
  }
}
