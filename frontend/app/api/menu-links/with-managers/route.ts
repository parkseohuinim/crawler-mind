import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

// GET /api/menu-links/with-managers
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const page = searchParams.get('page') || '1';
    const size = searchParams.get('size') || '10';
    const search = searchParams.get('search') || '';

    const params = new URLSearchParams({
      page,
      size,
    });

    if (search) {
      params.append('search', search);
    }

    const response = await fetch(`${API_BASE_URL}/api/menu-links/with-managers?${params}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching menu links with managers:', error);
    return NextResponse.json(
      { error: 'Failed to fetch menu links with managers' },
      { status: 500 }
    );
  }
}
