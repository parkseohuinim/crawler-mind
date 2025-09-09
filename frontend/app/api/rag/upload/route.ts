import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json(
        { error: 'No file provided' },
        { status: 400 }
      );
    }

    if (!file.name.endsWith('.json')) {
      return NextResponse.json(
        { error: 'Only JSON files are allowed' },
        { status: 400 }
      );
    }

    // Forward the file to the backend
    const backendFormData = new FormData();
    backendFormData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/rag/upload`, {
      method: 'POST',
      body: backendFormData,
      // 타임아웃을 30분으로 증가
      signal: AbortSignal.timeout(1800000), // 30분 = 1,800,000ms
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      return NextResponse.json(
        { error: errorData.detail || errorData.message || 'Upload failed' },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json({
      message: result.message,
      processedCount: result.processed_count,
      failedCount: result.failed_count,
      failedDocuments: result.failed_documents,
    });

  } catch (error) {
    console.error('RAG upload error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
