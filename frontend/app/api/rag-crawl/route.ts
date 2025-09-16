import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    // 백엔드 스키마에 맞춰 urls 필드만 전달
    const { urls } = body as { urls?: string };

    if (!urls || !urls.trim()) {
      return NextResponse.json(
        { error: 'urls is required' },
        { status: 400 }
      );
    }

    const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

    const response = await fetch(`${API_BASE_URL}/api/rag-crawl`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ urls }),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Upstream error: ${response.status}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error starting rag-crawl:', error);
    return NextResponse.json(
      { error: 'Failed to start rag-crawl' },
      { status: 500 }
    );
  }
}
