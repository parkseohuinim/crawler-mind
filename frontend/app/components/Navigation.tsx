'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navigation() {
  const pathname = usePathname();

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
        </div>
      </div>
    </nav>
  );
}
