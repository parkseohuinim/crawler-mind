import { NextRequest, NextResponse } from 'next/server';

// 임시로 하드코딩 (환경 변수 문제 해결 후 제거)
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

// GET /api/menu-manager-info/[id]
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    console.log('=== Menu Manager Info [id] API Route Debug ===');
    console.log('Request URL:', request.url);
    console.log('Params id:', params.id);
    
    // ID 유효성 검사
    const id = params.id.trim();
    
    if (!id) {
      console.error('Empty menu manager info ID provided');
      return NextResponse.json(
        { error: 'Menu Manager Info ID is required' },
        { status: 400 }
      );
    }
    
    if (isNaN(Number(id))) {
      console.error('Invalid menu manager info ID provided (not a number):', id);
      return NextResponse.json(
        { error: `Invalid menu_manager_info_id: ${id}. ID must be a number.` },
        { status: 400 }
      );
    }
    
    const numericId = Number(id);
    if (numericId <= 0) {
      console.error('Invalid menu manager info ID provided (negative or zero):', numericId);
      return NextResponse.json(
        { error: `Invalid menu_manager_info_id: ${numericId}. ID must be a positive number.` },
        { status: 400 }
      );
    }
    
    if (!Number.isInteger(numericId)) {
      console.error('Invalid menu manager info ID provided (not an integer):', numericId);
      return NextResponse.json(
        { error: `Invalid menu_manager_info_id: ${numericId}. ID must be an integer.` },
        { status: 400 }
      );
    }
    
    console.log('Menu Manager Info ID validation passed:', numericId);
    
    // 백엔드 API 호출 (기존 manager-info 엔드포인트 사용)
    const apiUrl = `${API_BASE_URL}/api/menu-links/manager-info/${numericId}`;
    console.log('Calling backend API:', apiUrl);
    
    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'Next.js-API-Route'
      }
    });
    
    console.log('Backend response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend API error:', response.status, errorText);
      
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Menu Manager Info not found' },
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
    console.log('Successfully fetched menu manager info data');
    return NextResponse.json(data);
  } catch (error) {
    console.error('=== Error Details ===');
    console.error('Error type:', error instanceof Error ? error.constructor.name : typeof error);
    console.error('Error message:', error instanceof Error ? error.message : String(error));
    console.error('Error stack:', error instanceof Error ? error.stack : 'No stack trace');
    
    return NextResponse.json(
      { 
        error: 'Failed to fetch menu manager info', 
        details: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    );
  }
}

// PUT /api/menu-manager-info/[id]
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // ID 유효성 검사
    const id = params.id.trim();
    
    if (!id || isNaN(Number(id)) || Number(id) <= 0 || !Number.isInteger(Number(id))) {
      return NextResponse.json(
        { error: `Invalid menu_manager_info_id: ${id}. ID must be a positive integer.` },
        { status: 400 }
      );
    }
    
    const numericId = Number(id);
    const body = await request.json();
    
    // 백엔드 API 호출 (기존 manager-info-update 엔드포인트 사용)
    const response = await fetch(`${API_BASE_URL}/api/menu-links/manager-info-update/${numericId}`, {
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
          { error: 'Menu Manager Info not found' },
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
    console.error('Error updating menu manager info:', error);
    return NextResponse.json(
      { error: 'Failed to update menu manager info' },
      { status: 500 }
    );
  }
}

// DELETE /api/menu-manager-info/[id]
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // ID 유효성 검사
    const id = params.id.trim();
    
    if (!id || isNaN(Number(id)) || Number(id) <= 0 || !Number.isInteger(Number(id))) {
      return NextResponse.json(
        { error: `Invalid menu_manager_info_id: ${id}. ID must be a positive integer.` },
        { status: 400 }
      );
    }
    
    const numericId = Number(id);
    
    // 백엔드 API 호출 (기존 manager-info-delete 엔드포인트 사용)
    const response = await fetch(`${API_BASE_URL}/api/menu-links/manager-info-delete/${numericId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend API error:', response.status, errorText);
      
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Menu Manager Info not found' },
          { status: 404 }
        );
      }
      
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting menu manager info:', error);
    return NextResponse.json(
      { error: 'Failed to delete menu manager info' },
      { status: 500 }
    );
  }
}
