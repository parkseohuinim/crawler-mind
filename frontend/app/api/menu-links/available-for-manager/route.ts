import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

// GET /api/menu-links/available-for-manager
export async function GET(request: NextRequest) {
  try {
    console.log('=== Available Menu Links for Manager API Route Debug ===');
    console.log('Request URL:', request.url);
    console.log('Request pathname:', new URL(request.url).pathname);
    console.log('Environment variables:', {
      MCP_API_URL: process.env.MCP_API_URL,
      NODE_ENV: process.env.NODE_ENV,
      API_BASE_URL
    });
    
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

    const fullUrl = `${API_BASE_URL}/api/menu-links/available-for-manager?${params}`;
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
        error: 'Failed to fetch available menu links for manager', 
        details: error instanceof Error ? error.message : String(error),
        type: error instanceof Error ? error.constructor.name : typeof error
      },
      { status: 500 }
    );
  }
}
