import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.MCP_API_URL || 'http://localhost:8000';

// GET /api/menu-links/[menuLinkId]
export async function GET(
  request: NextRequest,
  { params }: { params: { menuLinkId: string } }
) {
  try {
    console.log('=== Menu Link [menuLinkId] API Route Debug ===');
    console.log('Request URL:', request.url);
    console.log('Request pathname:', new URL(request.url).pathname);
    console.log('Params menuLinkId:', params.menuLinkId);
    console.log('menuLinkId type:', typeof params.menuLinkId);
    console.log('menuLinkId isNaN:', isNaN(Number(params.menuLinkId)));
    console.log('menuLinkId parsed as number:', Number(params.menuLinkId));
    console.log('Request headers:', Object.fromEntries(request.headers.entries()));
    console.log('Request method:', request.method);
    console.log('Request referer:', request.headers.get('referer'));
    console.log('User agent:', request.headers.get('user-agent'));
    console.log('Request timestamp:', new Date().toISOString());
    
    // 강력한 ID 유효성 검사
    const id = params.menuLinkId.trim();
    
    // 빈 문자열 체크
    if (!id) {
      console.error('Empty menuLinkId provided');
      return NextResponse.json(
        { error: 'Menu link ID is required' },
        { status: 400 }
      );
    }
    
    // 숫자가 아닌 경우 체크
    if (isNaN(Number(id))) {
      console.error('Invalid menuLinkId provided (not a number):', id);
      console.error('This suggests a routing issue - static routes should not match [menuLinkId]');
      return NextResponse.json(
        { error: `Invalid menu_link_id: ${id}. ID must be a number.` },
        { status: 400 }
      );
    }
    
    // 음수 체크
    const numericId = Number(id);
    if (numericId <= 0) {
      console.error('Invalid menuLinkId provided (negative or zero):', numericId);
      return NextResponse.json(
        { error: `Invalid menu_link_id: ${numericId}. ID must be a positive number.` },
        { status: 400 }
      );
    }
    
    // 정수 체크
    if (!Number.isInteger(numericId)) {
      console.error('Invalid menuLinkId provided (not an integer):', numericId);
      return NextResponse.json(
        { error: `Invalid menu_link_id: ${numericId}. ID must be an integer.` },
        { status: 400 }
      );
    }
    
    console.log('menuLinkId validation passed:', numericId);
    
    const apiUrl = `${API_BASE_URL}/api/menu-links/${numericId}`;
    console.log('Calling backend API:', apiUrl);
    console.log('Environment variables:', {
      MCP_API_URL: process.env.MCP_API_URL,
      NODE_ENV: process.env.NODE_ENV,
      API_BASE_URL
    });
    
    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'Next.js-API-Route'
      }
    });
    
    console.log('Backend response status:', response.status);
    console.log('Backend response headers:', Object.fromEntries(response.headers.entries()));
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend API error:', response.status, errorText);
      console.error('Backend error details:', {
        status: response.status,
        statusText: response.statusText,
        url: apiUrl,
        id: numericId,
        idType: typeof numericId,
        originalId: params.menuLinkId
      });
      
      // 백엔드 에러를 프론트엔드에 전달
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Menu link not found' },
          { status: 404 }
        );
      }
      
      if (response.status === 422) {
        return NextResponse.json(
          { error: 'Invalid request data', details: errorText },
          { status: 422 }
        );
      }
      
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
    }

    const data = await response.json();
    console.log('Successfully fetched menu link data');
    return NextResponse.json(data);
  } catch (error) {
    console.error('=== Error Details ===');
    console.error('Error type:', error instanceof Error ? error.constructor.name : typeof error);
    console.error('Error message:', error instanceof Error ? error.message : String(error));
    console.error('Error stack:', error instanceof Error ? error.stack : 'No stack trace');
    
    return NextResponse.json(
      { 
        error: 'Failed to fetch menu link', 
        details: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    );
  }
}

// PUT /api/menu-links/[menuLinkId]
export async function PUT(
  request: NextRequest,
  { params }: { params: { menuLinkId: string } }
) {
  try {
    // ID 유효성 검사
    const id = params.menuLinkId.trim();
    
    if (!id || isNaN(Number(id)) || Number(id) <= 0 || !Number.isInteger(Number(id))) {
      return NextResponse.json(
        { error: `Invalid menu_link_id: ${id}. ID must be a positive integer.` },
        { status: 400 }
      );
    }
    
    const numericId = Number(id);
    const body = await request.json();
    
    const response = await fetch(`${API_BASE_URL}/api/menu-links/${numericId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend API error:', response.status, errorText);
      
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Menu link not found' },
          { status: 404 }
        );
      }
      
      if (response.status === 422) {
        return NextResponse.json(
          { error: 'Invalid request data', details: errorText },
          { status: 422 }
        );
      }
      
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating menu link:', error);
    return NextResponse.json(
      { error: 'Failed to update menu link' },
      { status: 500 }
    );
  }
}

// DELETE /api/menu-links/[menuLinkId]
export async function DELETE(
  request: NextRequest,
  { params }: { params: { menuLinkId: string } }
) {
  try {
    // ID 유효성 검사
    const id = params.menuLinkId.trim();
    
    if (!id || isNaN(Number(id)) || Number(id) <= 0 || !Number.isInteger(Number(id))) {
      return NextResponse.json(
        { error: `Invalid menu_link_id: ${id}. ID must be a positive integer.` },
        { status: 400 }
      );
    }
    
    const numericId = Number(id);
    const response = await fetch(`${API_BASE_URL}/api/menu-links/${numericId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend API error:', response.status, errorText);
      
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Menu link not found' },
          { status: 404 }
        );
      }
      
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting menu link:', error);
    return NextResponse.json(
      { error: 'Failed to delete menu link' },
      { status: 500 }
    );
  }
}
