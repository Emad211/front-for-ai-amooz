'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useAdminBackups } from '@/hooks/use-admin-backups';

export default function BackupsPage() {
  const { items, isLoading, error, reload, trigger } = useAdminBackups();

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت بک‌آپ‌ها" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-foreground">بک‌آپ‌ها</h1>
          <p className="text-muted-foreground text-sm mt-1">مدیریت بک‌آپ‌های کامل و افزایشی</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" className="rounded-xl" onClick={() => trigger('full')}>بک‌آپ کامل</Button>
          <Button size="sm" variant="outline" className="rounded-xl" onClick={() => trigger('incremental')}>افزایشی</Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>آخرین بک‌آپ‌ها</CardTitle>
          <CardDescription>نمای لیست بک‌آپ‌های اخیر</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, idx) => <Skeleton key={idx} className="h-14 rounded-xl" />)
          ) : items.length ? (
            items.map((b) => (
              <div key={b.id} className="p-4 rounded-xl border bg-muted/40 flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm text-muted-foreground">{b.createdAt}</p>
                  <p className="text-base font-bold text-foreground">{b.type === 'full' ? 'بک‌آپ کامل' : 'بک‌آپ افزایشی'}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="rounded-full">{b.size}</Badge>
                  <Badge variant="default" className="rounded-full">{b.status}</Badge>
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">بک‌آپی ثبت نشده است</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
