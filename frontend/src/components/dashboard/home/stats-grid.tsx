'use client';

import { BookOpen, Flame, Target } from 'lucide-react';
import { StatCard } from '@/components/dashboard/ui/stat-card';
import { toPersianDigits } from '@/lib/persian-digits';
import { DashboardStats } from '@/types';

interface StatsGridProps {
  stats: DashboardStats | null;
}

export function StatsGrid({ stats }: StatsGridProps) {
  if (!stats) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
      <StatCard
        title="پیشرفت دوره‌ها"
        value={`${toPersianDigits(stats.activeCourses)} / ${toPersianDigits(stats.totalCourses)}`}
        subValue="دوره فعال در این ترم"
        icon={<BookOpen className="h-5 w-5 md:h-6 md:w-6"/>}
      />
      <StatCard
        title="درصد تکمیل"
        value={`${toPersianDigits(stats.completionPercent)}٪`}
        subValue="تکمیل دوره‌های فعال"
        icon={<Target className="h-5 w-5 md:h-6 md:w-6"/>}
        tag="ترم جاری"
      />
      <StatCard
        title="روزهای پیوسته"
        value={stats.streak === null ? '—' : toPersianDigits(stats.streak)}
        subValue={stats.streak === null ? 'با پذیرش مشاور فعال می‌شود' : 'روز متوالی ثبت گزارش'}
        icon={<Flame className="h-5 w-5 md:h-6 md:w-6"/>}
      />
    </div>
  );
}
