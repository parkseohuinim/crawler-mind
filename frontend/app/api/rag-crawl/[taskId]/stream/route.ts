import { NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

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

    const upstream = await fetch(`${API_BASE_URL}/api/rag-crawl/${taskId}/stream`, {
      headers: {
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      cache: 'no-store',
      // @ts-expect-error: duplex is needed for streaming in some environments
      duplex: 'half',
    });

    if (!upstream.ok || !upstream.body) {
      return new Response(JSON.stringify({ error: `Upstream error: ${upstream.status}` }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const readable = new ReadableStream({
      start(controller) {
        const reader = upstream.body!.getReader();
        const pump = () => reader.read().then(({ done, value }) => {
          if (done) {
            controller.close();
            return;
          }
          if (value) controller.enqueue(value);
          pump();
        }).catch((err) => {
          try { controller.error(err); } catch {}
        });
        pump();
      }
    });

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (error) {
    console.error('Error streaming rag-crawl:', error);
    return new Response(JSON.stringify({ error: 'Failed to stream rag-crawl' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}


