'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useAdminOps } from '@/hooks/use-admin-ops';

export default function MaintenancePage() {
  const { health, maintenance, isLoading, error, reload } = useAdminOps();

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت وضعیت سرور" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-foreground">نگهداری و سلامت سرور</h1>
          <p className="text-muted-foreground text-sm mt-1">پایش سلامت و برنامه‌های نگهداری زیرساخت</p>
        </div>
        {health && (
          <Badge variant={health.status === 'healthy' ? 'default' : 'destructive'} className="px-4 py-2 rounded-full text-sm">
            وضعیت: {health.status === 'healthy' ? 'سالم' : 'هشدار'}
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>شاخص‌های سلامت</CardTitle>
          <CardDescription>نمای کلی مصرف منابع و آپتایم</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {isLoading || !health ? (
            Array.from({ length: 4 }).map((_, idx) => <Skeleton key={idx} className="h-20 rounded-xl" />)
          ) : (
            [
              { label: 'Uptime', value: health.uptime },
              { label: 'CPU', value: `${health.cpu}%` },
              { label: 'RAM', value: `${health.memory}%` },
              { label: 'Disk', value: `${health.disk}%` },
            ].map((item) => (
              <div key={item.label} className="p-4 rounded-xl border bg-muted/50">
                <p className="text-xs text-muted-foreground">{item.label}</p>
                <p className="text-lg font-bold">{item.value}</p>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>برنامه‌های نگهداری</CardTitle>
          <CardDescription>لیست عملیات زمان‌بندی شده</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, idx) => <Skeleton key={idx} className="h-16 rounded-xl" />)
          ) : maintenance.length ? (
            maintenance.map((task) => (
              <div key={task.id} className="p-4 rounded-xl border flex flex-col md:flex-row md:items-center md:justify-between gap-3 bg-muted/50">
                <div>
                  <p className="text-base font-bold text-foreground">{task.title}</p>
                  <p className="text-sm text-muted-foreground">{task.window}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="rounded-full">{task.owner}</Badge>
                  <Badge variant={task.status === 'scheduled' ? 'default' : 'outline'} className="rounded-full">
                    {task.status === 'scheduled' ? 'زمان‌بندی شده' : 'آماده اجرا'}
                  </Badge>
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">برنامه‌ای ثبت نشده است</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
