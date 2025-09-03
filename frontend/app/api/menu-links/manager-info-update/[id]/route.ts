import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.MCP_API_URL || 'http://localhost:8000';

// PUT /api/menu-links/manager-info-update/[id]
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const id = params.id.trim();
    
    if (!id || isNaN(Number(id)) || Number(id) <= 0 || !Number.isInteger(Number(id))) {
      return NextResponse.json(
        { error: `Invalid manager_id: ${id}. ID must be a positive integer.` },
        { status: 400 }
      );
    }
    
    const numericId = Number(id);
    const body = await request.json();
    
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
          { error: 'Manager not found' },
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
    console.error('Error updating manager info:', error);
    return NextResponse.json(
      { error: 'Failed to update manager info' },
      { status: 500 }
    );
  }
}
