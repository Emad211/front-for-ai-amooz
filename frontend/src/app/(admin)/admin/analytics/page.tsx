'use client';

import { OverviewCards } from '@/components/admin/analytics/overview-cards';
import { ActivityChart } from '@/components/admin/analytics/activity-chart';
import { ClassDistribution } from '@/components/admin/analytics/class-distribution';
import { RecentActivity } from '@/components/admin/analytics/recent-activity';
import { Button } from '@/components/ui/button';
import { Download, Calendar } from 'lucide-react';

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-foreground">آمار و تحلیل سیستم</h1>
          <p className="text-muted-foreground text-sm mt-1">گزارش جامع از عملکرد کلاس‌ها و دانش‌آموزان</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-9 rounded-xl gap-2">
            <Calendar className="w-4 h-4" />
            ۳۰ روز گذشته
          </Button>
          <Button size="sm" className="h-9 rounded-xl gap-2">
            <Download className="w-4 h-4" />
            خروجی گزارش
          </Button>
        </div>
      </div>

      {/* Overview Stats */}
      <OverviewCards />

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ActivityChart />
        <RecentActivity />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ClassDistribution />
        {/* Placeholder for more analytics if needed */}
        <div className="lg:col-span-2 bg-muted/30 rounded-3xl border border-dashed border-border flex items-center justify-center p-12">
          <p className="text-muted-foreground text-sm">بخش‌های تحلیلی بیشتر در نسخه‌های آینده اضافه خواهد شد</p>
        </div>
      </div>
    </div>
  );
}
