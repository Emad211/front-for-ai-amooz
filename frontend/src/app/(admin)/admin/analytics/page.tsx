'use client';

import { OverviewCards } from '@/components/admin/analytics/overview-cards';
import { ActivityChart } from '@/components/admin/analytics/activity-chart';
import { ClassDistribution } from '@/components/admin/analytics/class-distribution';
import { RecentActivity } from '@/components/admin/analytics/recent-activity';
import { Button } from '@/components/ui/button';
import { Download, Calendar } from 'lucide-react';
import { useAdminAnalytics } from '@/hooks/use-admin-analytics';
import { Skeleton } from '@/components/ui/skeleton';
import { StatsSkeleton } from '@/components/dashboard/stats-skeleton';
import { PageTransition } from '@/components/ui/page-transition';
import { ErrorState } from '@/components/shared/error-state';

export default function AnalyticsPage() {
  const { stats, chartData, distributionData, activities, isLoading, error, reload } = useAdminAnalytics();

  if (isLoading) {
    return (
      <PageTransition>
        <div className="space-y-8">
          <div className="flex justify-between">
            <div className="space-y-2">
              <Skeleton className="h-10 w-64" />
              <Skeleton className="h-4 w-48" />
            </div>
            <div className="flex gap-2">
              <Skeleton className="h-10 w-32" />
              <Skeleton className="h-10 w-32" />
            </div>
          </div>
          <StatsSkeleton />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Skeleton className="h-[400px] lg:col-span-2 rounded-3xl" />
            <Skeleton className="h-[400px] rounded-3xl" />
          </div>
        </div>
      </PageTransition>
    );
  }

  if (error) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center h-[60vh] px-4">
          <div className="w-full max-w-2xl">
            <ErrorState title="خطا در دریافت اطلاعات تحلیلی" description={error} onRetry={reload} />
          </div>
        </div>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-black text-foreground">آمار و تحلیل سیستم</h1>
            <p className="text-muted-foreground text-sm mt-1">گزارش جامع از عملکرد کلاس‌ها و دانش‌آموزان</p>
          </div>
          <div className="flex flex-col sm:flex-row items-center gap-2">
            <Button variant="outline" size="sm" className="w-full sm:w-auto h-9 rounded-xl gap-2">
              <Calendar className="w-4 h-4" />
              ۳۰ روز گذشته
            </Button>
            <Button size="sm" className="w-full sm:w-auto h-9 rounded-xl gap-2">
              <Download className="w-4 h-4" />
              خروجی گزارش
            </Button>
          </div>
        </div>

        {/* Overview Stats */}
        <OverviewCards stats={stats} />

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <ActivityChart data={chartData} />
          <RecentActivity activities={activities} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <ClassDistribution data={distributionData} />
          {/* Placeholder for more analytics if needed */}
          <div className="lg:col-span-2 bg-muted/30 rounded-3xl border border-dashed border-border flex items-center justify-center p-12">
            <p className="text-muted-foreground text-sm">بخش‌های تحلیلی بیشتر در نسخه‌های آینده اضافه خواهد شد</p>
          </div>
        </div>
      </div>
    </PageTransition>
  );
}

