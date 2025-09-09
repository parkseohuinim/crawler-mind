import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const { query, maxResults = 5, similarityThreshold = 0.7 } = await request.json();

    if (!query || typeof query !== 'string' || !query.trim()) {
      return NextResponse.json(
        { error: 'Query is required and must be a non-empty string' },
        { status: 400 }
      );
    }

    const requestBody = {
      query: query.trim(),
      max_results: maxResults,
      similarity_threshold: similarityThreshold,
    };

    const response = await fetch(`${API_BASE_URL}/api/rag/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      return NextResponse.json(
        { error: errorData.detail || errorData.message || 'Query failed' },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json({
      answer: result.answer,
      sources: result.sources,
      query: result.query,
      processingTime: result.processing_time,
    });

  } catch (error) {
    console.error('RAG query error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
