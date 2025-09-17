import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from './_lib/auth/auth-context';
import AuthenticatedLayout from './_components/layout/AuthenticatedLayout';

export const metadata: Metadata = {
  title: 'Crawler Mind - Enterprise',
  description: '엔터프라이즈 웹 크롤링 및 RAG 시스템',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>
          <AuthenticatedLayout>
            {children}
          </AuthenticatedLayout>
        </AuthProvider>
      </body>
    </html>
  );
}
