import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const filename = searchParams.get('filename');
    const query = searchParams.get('query') || '';
    const searchField = searchParams.get('search_field') || 'all';
    const limit = searchParams.get('limit') || '50';

    if (!filename) {
      return NextResponse.json(
        { error: 'filename이 필요합니다' },
        { status: 400 }
      );
    }

    const params = new URLSearchParams({
      filename,
      query,
      search_field: searchField,
      limit,
    });

    const response = await fetch(
      `${API_BASE_URL}/api/result-editor/search-docs?${params}`,
      { cache: 'no-store' }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      return NextResponse.json(
        { error: error.detail || 'Failed to search documents' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error searching documents:', error);
    return NextResponse.json(
      { error: 'Failed to search documents' },
      { status: 500 }
    );
  }
}
