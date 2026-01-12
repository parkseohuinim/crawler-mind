import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// GET - Get Recent Daily Crawling Tasks
export async function GET(request: NextRequest) {
  try {
    // 기능이 비활성화된 경우 호출하지 않고 빈 결과 반환
    if (process.env.NEXT_PUBLIC_ENABLE_DAILY_CRAWLING === 'false') {
      return NextResponse.json([]);
    }

    const { searchParams } = new URL(request.url);
    const limit = searchParams.get('limit') || '10';
    
    const response = await fetch(`${BACKEND_URL}/api/daily-crawling/tasks?limit=${limit}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Failed to fetch tasks' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Daily crawling tasks API error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
