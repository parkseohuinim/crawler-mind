'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navigation() {
  const pathname = usePathname();
  // 환경 변수가 'false'로 명시되어 있지 않으면 로컬 환경에서는 기본적으로 보이게 설정
  const isDailyEnabled = process.env.NEXT_PUBLIC_ENABLE_DAILY_CRAWLING !== 'false';

  return (
    <nav className="navigation">
      <div className="nav-container">
        <div className="nav-brand">
          <Link href="/" className="brand-link">
            크롤링 AI 어시스턴트
          </Link>
        </div>
        
        <div className="nav-links">
          <Link 
            href="/" 
            className={`nav-link ${pathname === '/' ? 'active' : ''}`}
          >
            홈
          </Link>
          <Link 
            href="/rag" 
            className={`nav-link ${pathname === '/rag' ? 'active' : ''}`}
          >
            RAG 시스템
          </Link>
          <Link 
            href="/menu-links" 
            className={`nav-link ${pathname === '/menu-links' ? 'active' : ''}`}
          >
            메뉴 링크 관리
          </Link>
          <Link 
            href="/menu-managers" 
            className={`nav-link ${pathname === '/menu-managers' ? 'active' : ''}`}
          >
            메뉴 매니저 관리
          </Link>
          <Link 
            href="/menu-links/tree" 
            className={`nav-link ${pathname === '/menu-links/tree' ? 'active' : ''}`}
          >
            메뉴 트리뷰
          </Link>
          <Link 
            href="/json-compare" 
            className={`nav-link ${pathname === '/json-compare' ? 'active' : ''}`}
          >
            JSON 비교
          </Link>
          {isDailyEnabled && (
            <Link 
              href="/daily-crawling" 
              className={`nav-link ${pathname === '/daily-crawling' ? 'active' : ''}`}
            >
              Daily 추출
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
