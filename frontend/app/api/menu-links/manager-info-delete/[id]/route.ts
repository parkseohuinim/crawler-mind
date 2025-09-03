import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.MCP_API_URL || 'http://localhost:8000';

// DELETE /api/menu-links/manager-info-delete/[id]
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    console.log('=== Delete Manager Info API Route Debug ===');
    console.log('Request URL:', request.url);
    console.log('Manager ID:', params.id);
    console.log('Environment variables:', {
      MCP_API_URL: process.env.MCP_API_URL,
      NODE_ENV: process.env.NODE_ENV,
      API_BASE_URL
    });
    
    const fullUrl = `${API_BASE_URL}/api/menu-links/manager-info-delete/${params.id}`;
    console.log('Calling API:', fullUrl);

    const response = await fetch(fullUrl, {
      method: 'DELETE',
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
    
    return NextResponse.json(
      { 
        error: 'Failed to delete manager info', 
        details: error instanceof Error ? error.message : String(error),
        type: error instanceof Error ? error.constructor.name : typeof error
      },
      { status: 500 }
    );
  }
}
