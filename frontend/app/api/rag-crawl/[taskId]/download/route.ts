import { NextRequest } from 'next/server';

export async function GET(
  request: NextRequest,
  { params }: { params: { taskId: string } }
) {
  try {
    const { taskId } = params;
    if (!taskId) {
      return new Response(JSON.stringify({ error: 'Task ID is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

    const upstream = await fetch(`${API_BASE_URL}/api/rag-crawl/${taskId}`, {
      method: 'GET',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!upstream.ok) {
      return new Response(JSON.stringify({ error: `Upstream error: ${upstream.status}` }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const data = await upstream.json();

    // json_data 배열이 있으면 그 배열만 직렬화하여 파일 시작을 []로 맞춤
    const payload = Array.isArray((data as any)?.json_data) ? (data as any).json_data : data;

    const filename = `rag-crawl-${taskId}.json`;
    const body = JSON.stringify(payload, null, 2);

    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    console.error('Error creating download:', error);
    return new Response(JSON.stringify({ error: 'Failed to download rag-crawl result' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}


