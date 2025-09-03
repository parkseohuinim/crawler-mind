import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.MCP_API_URL || 'http://localhost:8000';

// POST /api/menu-links/manager-info-create
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
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
    console.error('Error creating manager info:', error);
    return NextResponse.json(
      { error: 'Failed to create manager info' },
      { status: 500 }
    );
  }
}
