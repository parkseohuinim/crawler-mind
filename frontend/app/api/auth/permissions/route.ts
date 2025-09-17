import { NextRequest, NextResponse } from 'next/server';

// MCP Client에서 사용자 권한 조회
export async function POST(request: NextRequest) {
  try {
    const { roles } = await request.json();
    
    if (!roles || !Array.isArray(roles)) {
      return NextResponse.json(
        { error: 'Valid roles array is required' },
        { status: 400 }
      );
    }

    // Authorization 헤더에서 JWT 토큰 추출
    const authHeader = request.headers.get('authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json(
        { error: 'Authorization token is required' },
        { status: 401 }
      );
    }

    const token = authHeader.substring(7);

    // MCP Client API 호출
    const mcpClientUrl = process.env.MCP_CLIENT_URL || 'http://localhost:8000';
    const response = await fetch(`${mcpClientUrl}/api/auth/permissions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ roles }),
    });

    if (!response.ok) {
      console.error('MCP Client permissions request failed:', response.status);
      return NextResponse.json(
        { permissions: [] },
        { status: 200 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Error fetching permissions:', error);
    return NextResponse.json(
      { permissions: [] },
      { status: 200 }
    );
  }
}
