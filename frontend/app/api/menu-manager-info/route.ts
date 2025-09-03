import { NextRequest, NextResponse } from 'next/server';
import { menuManagerInfoService } from '@/app/domains/menuManagerInfo';

// 임시로 하드코딩 (환경 변수 문제 해결 후 제거)
const API_BASE_URL = 'http://localhost:8000';

// GET /api/menu-manager-info
export async function GET(request: NextRequest) {
  try {
    console.log('=== Menu Manager Info API Route Debug ===');
    console.log('Environment variables:', {
      MCP_API_URL: process.env.MCP_API_URL,
      NODE_ENV: process.env.NODE_ENV,
      API_BASE_URL
    });
    
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get('page') || '1');
    const size = parseInt(searchParams.get('size') || '10');
    const search = searchParams.get('search') || undefined;

    console.log('Request params:', { page, size, search });

    // 백엔드 API 호출 (기존 manager-info-list 엔드포인트 사용)
    const params = new URLSearchParams({
      page: page.toString(),
      size: size.toString(),
    });

    if (search) {
      params.append('search', search);
    }

    const fullUrl = `${API_BASE_URL}/api/menu-links/manager-info-list?${params}`;
    console.log('Calling API:', fullUrl);

    const response = await fetch(fullUrl, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'Next.js-API-Route'
      }
    });
    
    console.log('Response status:', response.status);
    
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
        error: 'Failed to fetch menu manager info', 
        details: error instanceof Error ? error.message : String(error),
        type: error instanceof Error ? error.constructor.name : typeof error
      },
      { status: 500 }
    );
  }
}

// POST /api/menu-manager-info
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // 백엔드 API 호출 (기존 manager-info-create 엔드포인트 사용)
    const response = await fetch(`${API_BASE_URL}/api/menu-links/manager-info-create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend API error:', response.status, errorText);
      
      if (response.status === 422) {
        return NextResponse.json(
          { error: 'Invalid request data', details: errorText },
          { status: 422 }
        );
      }
      
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error creating menu manager info:', error);
    return NextResponse.json(
      { error: 'Failed to create menu manager info' },
      { status: 500 }
    );
  }
}
