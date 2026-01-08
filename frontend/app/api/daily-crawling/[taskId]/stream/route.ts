import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// GET - SSE Stream for Daily Crawling Task
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;
  
  console.log(`[SSE Proxy] Connecting to backend: ${BACKEND_URL}/api/daily-crawling/${taskId}/stream`);
  
  const encoder = new TextEncoder();
  
  const stream = new ReadableStream({
    async start(controller) {
      try {
        const response = await fetch(`${BACKEND_URL}/api/daily-crawling/${taskId}/stream`, {
          method: 'GET',
          headers: {
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
          },
        });

        console.log(`[SSE Proxy] Backend response status: ${response.status}`);

        if (!response.ok) {
          const errorText = await response.text();
          console.error(`[SSE Proxy] Backend error: ${errorText}`);
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'error', data: { message: `Backend error: ${response.status}` } })}\n\n`));
          controller.close();
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          console.error('[SSE Proxy] No response body');
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'error', data: { message: 'No response body' } })}\n\n`));
          controller.close();
          return;
        }

        const decoder = new TextDecoder();
        console.log('[SSE Proxy] Starting to read stream...');
        
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            console.log('[SSE Proxy] Stream ended');
            break;
          }
          
          const chunk = decoder.decode(value, { stream: true });
          console.log(`[SSE Proxy] Received chunk: ${chunk.substring(0, 100)}...`);
          controller.enqueue(encoder.encode(chunk));
        }
        
        controller.close();
      } catch (error) {
        console.error('[SSE Proxy] Stream error:', error);
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'error', data: { message: 'Stream error' } })}\n\n`));
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
      'Access-Control-Allow-Origin': '*',
    },
  });
}

