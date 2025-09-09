import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file1 = formData.get('file1') as File;
    const file2 = formData.get('file2') as File;

    if (!file1 || !file2) {
      return NextResponse.json(
        { error: 'Both files are required' },
        { status: 400 }
      );
    }

    if (!file1.name.endsWith('.json') || !file2.name.endsWith('.json')) {
      return NextResponse.json(
        { error: 'Only JSON files are allowed' },
        { status: 400 }
      );
    }

    // 파일 내용 읽기
    const file1Content = await file1.text();
    const file2Content = await file2.text();

    // JSON 유효성 검사
    try {
      JSON.parse(file1Content);
      JSON.parse(file2Content);
    } catch (error) {
      return NextResponse.json(
        { error: 'Invalid JSON format in one or both files' },
        { status: 400 }
      );
    }

    // 백엔드로 요청 전송
    const response = await fetch(`${API_BASE_URL}/api/json-compare/compare`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        file1_name: file1.name,
        file2_name: file2.name,
        file1_content: file1Content,
        file2_content: file2Content,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      return NextResponse.json(
        { error: errorData.detail || errorData.message || 'Comparison failed' },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json(result);

  } catch (error) {
    console.error('JSON compare error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
