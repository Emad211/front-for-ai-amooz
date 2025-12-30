'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/shared/error-state';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Global error boundary:', error);
  }, [error]);

  const details = error?.digest ? `digest: ${error.digest}` : undefined;

  return (
    <html lang="fa" dir="rtl">
      <body className="min-h-screen bg-background">
        <div className="container max-w-3xl mx-auto px-4 py-10 md:py-14">
          <ErrorState
            title="خطای غیرمنتظره"
            description="یک خطای جدی رخ داد. اگر مشکل ادامه داشت، چند دقیقه بعد دوباره تلاش کنید."
            onRetry={reset}
            details={details}
            homeHref="/home"
          />
        </div>
      </body>
    </html>
  );
}
