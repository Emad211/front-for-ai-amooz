'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/shared/error-state';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Dashboard segment error boundary:', error);
  }, [error]);

  const details = error?.digest ? `digest: ${error.digest}` : undefined;

  return (
    <main className="min-h-screen bg-background/50" dir="rtl">
      <div className="container max-w-3xl mx-auto px-4 py-10 md:py-14">
        <ErrorState
          title="مشکل در بخش داشبورد"
          description="این بخش فعلاً با خطا مواجه شده. می‌توانید تلاش مجدد کنید یا به خانه برگردید."
          onRetry={reset}
          details={details}
          homeHref="/home"
        />
      </div>
    </main>
  );
}
