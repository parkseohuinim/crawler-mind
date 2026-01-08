import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// GET - Get Daily Crawling Task Status
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  try {
    const { taskId } = await params;
    
    const response = await fetch(`${BACKEND_URL}/api/daily-crawling/${taskId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Failed to fetch task status' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: unknown) {
    // 연결 실패 시 더 친절한 에러 메시지
    if (error instanceof Error && error.cause && (error.cause as { code?: string }).code === 'ECONNREFUSED') {
      console.warn('Backend server is not running');
      return NextResponse.json(
        { error: '백엔드 서버가 실행되지 않았습니다. 서버를 시작해주세요.' },
        { status: 503 }
      );
    }
    console.error('Daily crawling task API error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

