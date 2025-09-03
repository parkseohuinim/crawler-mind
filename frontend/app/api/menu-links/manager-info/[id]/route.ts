import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.MCP_API_URL || 'http://localhost:8000';

// GET /api/menu-links/manager-info/[id]
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/menu-links/manager-info/${params.id}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching manager info:', error);
    return NextResponse.json(
      { error: 'Failed to fetch manager info' },
      { status: 500 }
    );
  }
}

// PUT /api/menu-links/manager-info/[id]
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    
    const response = await fetch(`${API_BASE_URL}/api/menu-links/manager-info/${params.id}`, {
      method: 'PUT',
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
    console.error('Error updating manager info:', error);
    return NextResponse.json(
      { error: 'Failed to update manager info' },
      { status: 500 }
    );
  }
}

// DELETE /api/menu-links/manager-info/[id]
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/menu-links/manager-info/${params.id}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting manager info:', error);
    return NextResponse.json(
      { error: 'Failed to delete manager info' },
      { status: 500 }
    );
  }
}
