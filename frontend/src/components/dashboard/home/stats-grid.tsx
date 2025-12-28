'use client';

import { BookOpen, Target, Clock } from 'lucide-react';
import { StatCard } from '@/components/dashboard/ui/stat-card';
import { DashboardStats } from '@/constants/mock/dashboard-data';

interface StatsGridProps {
  stats: DashboardStats | null;
}

export function StatsGrid({ stats }: StatsGridProps) {
  if (!stats) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
      <StatCard 
        title="پیشرفت دوره‌ها" 
        value={`${stats.activeCourses} / ${stats.totalCourses}`} 
        subValue="دوره فعال در این ترم" 
        icon={<BookOpen className="h-5 w-5 md:h-6 md:w-6"/>} 
        progress={Math.round((stats.activeCourses / stats.totalCourses) * 100)}
      />
      <StatCard 
        title="درصد تکمیل" 
        value={`${stats.completionPercent}٪`} 
        subValue="میانگین نمرات کل" 
        icon={<Target className="h-5 w-5 md:h-6 md:w-6"/>} 
        tag="ترم جاری" 
        progress={stats.completionPercent}
      />
      <StatCard 
        title="زمان مطالعه" 
        value={`${stats.studyHours}:${stats.studyMinutes}`} 
        subValue="ساعت مطالعه مفید" 
        icon={<Clock className="h-5 w-5 md:h-6 md:w-6"/>} 
        tag="این هفته" 
        progress={60}
      />
    </div>
  );
}
