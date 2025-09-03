import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.MCP_API_URL || 'http://localhost:8000';

// GET /api/menu-links/manager-info
export async function GET(request: NextRequest) {
  try {
    console.log('=== Manager Info API Route Debug ===');
    console.log('Environment variables:', {
      MCP_API_URL: process.env.MCP_API_URL,
      NODE_ENV: process.env.NODE_ENV,
      API_BASE_URL
    });
    
    const { searchParams } = new URL(request.url);
    const page = searchParams.get('page') || '1';
    const size = searchParams.get('size') || '10';

    const params = new URLSearchParams({
      page,
      size,
    });

    const fullUrl = `${API_BASE_URL}/api/menu-links/manager-info-list?${params}`;
    console.log('Calling API:', fullUrl);
    console.log('Request URL:', request.url);
    console.log('Search params:', Object.fromEntries(searchParams.entries()));

    const response = await fetch(fullUrl);
    
    console.log('Response status:', response.status);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('API response error:', response.status, response.statusText);
      console.error('Error response body:', errorText);
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
    }

    const data = await response.json();
    console.log('Response data received successfully');
    return NextResponse.json(data);
  } catch (error) {
    console.error('=== Error Details ===');
    console.error('Error type:', error instanceof Error ? error.constructor.name : typeof error);
    console.error('Error message:', error instanceof Error ? error.message : String(error));
    console.error('Error stack:', error instanceof Error ? error.stack : 'No stack trace');
    
    return NextResponse.json(
      { 
        error: 'Failed to fetch manager info', 
        details: error instanceof Error ? error.message : String(error),
        type: error instanceof Error ? error.constructor.name : typeof error
      },
      { status: 500 }
    );
  }
}

// POST /api/menu-links/manager-info
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    const response = await fetch(`${API_BASE_URL}/api/menu-links/manager-info`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error creating manager info:', error);
    return NextResponse.json(
      { error: 'Failed to create manager info' },
      { status: 500 }
    );
  }
}
