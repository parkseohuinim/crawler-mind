import { NextRequest, NextResponse } from 'next/server';

const MCP_CLIENT_URL = process.env.MCP_CLIENT_URL || 'http://localhost:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: { taskId: string } }
) {
  try {
    const { taskId } = params;

    const response = await fetch(`${MCP_CLIENT_URL}/api/json-compare/task/${taskId}/download`, {
      method: 'GET',
    });

    if (!response.ok) {
      const errorData = await response.text().catch(() => 'Unknown error');
      return NextResponse.json(
        { error: errorData || 'Failed to download PDF' },
        { status: response.status }
      );
    }

    const pdfBuffer = await response.arrayBuffer();
    
    // 현재 시간을 report_YYYY-MM-DD_HHMM 형식으로 생성
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    
    const filename = `report_${year}-${month}-${day}_${hours}${minutes}.pdf`;
    
    return new NextResponse(pdfBuffer, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });

  } catch (error) {
    console.error('Download PDF error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
