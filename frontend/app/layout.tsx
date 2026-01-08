import type { Metadata } from 'next';
import './globals.css';
import Navigation from './_components/ui/Navigation';
import Providers from './_components/providers/Providers';

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
      <body>
        <Providers>
          <Navigation />
          {children}
        </Providers>
      </body>
    </html>
  );
}
