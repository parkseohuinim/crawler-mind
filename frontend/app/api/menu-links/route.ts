import { NextRequest, NextResponse } from 'next/server';
import { menuLinkService } from '@/app/_lib/domains/menuLink';

// 임시로 하드코딩 (환경 변수 문제 해결 후 제거)
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

// GET /api/menu-links
export async function GET(request: NextRequest) {
  try {
    console.log('=== Menu Links API Route Debug ===');
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

    const fullUrl = `${API_BASE_URL}/api/menu-links?${params}`;
    console.log('Calling API:', fullUrl);
    console.log('Request URL:', request.url);
    console.log('Search params:', Object.fromEntries(searchParams.entries()));

    // 백엔드 서버 연결 테스트
    console.log('Testing backend connection...');
    
    // 클라이언트에서 전달받은 Authorization 헤더를 백엔드로 전달
    const authHeader = request.headers.get('authorization');
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'User-Agent': 'Next.js-API-Route'
    };
    
    if (authHeader) {
      headers['Authorization'] = authHeader;
      console.log('Forwarding authorization header to backend');
    } else {
      console.warn('No authorization header found in request');
    }

    const response = await fetch(fullUrl, {
      method: 'GET',
      headers
    });
    
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
    
    if (error instanceof TypeError && error.message.includes('fetch')) {
      console.error('Network error - backend server might be down');
      return NextResponse.json(
        { 
          error: 'Backend server connection failed', 
          details: 'Please check if the MCP server is running on port 8000',
          message: error.message
        },
        { status: 503 }
      );
    }
    
    return NextResponse.json(
      { 
        error: 'Failed to fetch menu links', 
        details: error instanceof Error ? error.message : String(error),
        type: error instanceof Error ? error.constructor.name : typeof error
      },
      { status: 500 }
    );
  }
}

// POST /api/menu-links
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    const response = await fetch(`${API_BASE_URL}/api/menu-links`, {
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
    console.error('Error creating menu link:', error);
    return NextResponse.json(
      { error: 'Failed to create menu link' },
      { status: 500 }
    );
  }
}
