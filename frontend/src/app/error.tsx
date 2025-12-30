'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/shared/error-state';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Keep logs minimal; do not leak sensitive details to the UI.
    console.error('App error boundary:', error);
  }, [error]);

  const details = error?.digest ? `digest: ${error.digest}` : undefined;

  return (
    <main className="min-h-screen bg-background/50" dir="rtl">
      <div className="container max-w-3xl mx-auto px-4 py-10 md:py-14">
        <ErrorState
          title="مشکلی پیش آمد"
          description="در پردازش درخواست شما خطایی رخ داد. لطفاً دوباره تلاش کنید."
          onRetry={reset}
          details={details}
          homeHref="/home"
        />
      </div>
    </main>
  );
}
