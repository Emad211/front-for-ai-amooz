import { ErrorState } from '@/components/shared/error-state';

export default function NotFound() {
  return (
    <main className="min-h-screen bg-background/50" dir="rtl">
      <div className="container max-w-3xl mx-auto px-4 py-10 md:py-14">
        <ErrorState
          variant="not-found"
          title="صفحه مورد نظر پیدا نشد"
          description="ممکن است آدرس اشتباه باشد یا صفحه حذف شده باشد."
          homeHref="/home"
        />
      </div>
    </main>
  );
}
