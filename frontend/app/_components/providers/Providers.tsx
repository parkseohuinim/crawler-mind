'use client';

import { DailyCrawlingProvider } from '@/app/_lib/contexts/DailyCrawlingContext';
import ToastContainer from '@/app/_components/ui/Toast';

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <DailyCrawlingProvider>
      {children}
      <ToastContainer />
    </DailyCrawlingProvider>
  );
}

