import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '크롤링 AI 어시스턴트',
  description: '웹사이트를 분석하고 데이터를 추출하는 AI 어시스턴트',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
