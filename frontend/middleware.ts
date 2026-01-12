import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 데일리 크롤링 페이지 접근 제한
  if (pathname.startsWith('/daily-crawling')) {
    const isDailyEnabled = process.env.NEXT_PUBLIC_ENABLE_DAILY_CRAWLING !== 'false';
    
    // 환경 변수가 'false'로 명시된 경우에만 리다이렉트 (운영 배포 시 values.yaml에서 설정)
    if (!isDailyEnabled) {
      return NextResponse.redirect(new URL('/', request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/daily-crawling/:path*'],
};
