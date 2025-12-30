'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/shared/error-state';

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Admin segment error boundary:', error);
  }, [error]);

  const details = error?.digest ? `digest: ${error.digest}` : undefined;

  return (
    <main className="min-h-screen bg-background/50" dir="rtl">
      <div className="container max-w-3xl mx-auto px-4 py-10 md:py-14">
        <ErrorState
          title="مشکل در بخش مدیریت"
          description="در پردازش صفحه مدیریتی خطایی رخ داد. لطفاً دوباره تلاش کنید."
          onRetry={reset}
          details={details}
          homeHref="/admin"
        />
      </div>
    </main>
  );
}
