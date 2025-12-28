
"use client";

import { DashboardHero } from '@/components/dashboard/dashboard-hero';
import { WelcomeSection } from '@/components/dashboard/home/welcome-section';
import { StatsGrid } from '@/components/dashboard/home/stats-grid';
import { RecentActivity } from '@/components/dashboard/home/recent-activity';
import { UpcomingEvents } from '@/components/dashboard/home/upcoming-events';
import { useDashboardData } from '@/hooks/use-dashboard-data';
import { Skeleton } from '@/components/ui/skeleton';

export default function StudentDashboard() {
  const { stats, activities, events, profile, isLoading, error } = useDashboardData();

  if (isLoading) {
    return (
      <main className="p-4 md:p-8 max-w-7xl mx-auto space-y-8 md:space-y-10">
        <div className="space-y-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-6 w-64" />
        </div>
        <Skeleton className="h-64 w-full rounded-3xl" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Skeleton className="h-32 rounded-2xl" />
          <Skeleton className="h-32 rounded-2xl" />
          <Skeleton className="h-32 rounded-2xl" />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="p-4 md:p-8 max-w-7xl mx-auto flex items-center justify-center h-[60vh]">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-destructive mb-2">خطا در بارگذاری</h2>
          <p className="text-muted-foreground">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="p-4 md:p-8 max-w-7xl mx-auto space-y-8 md:space-y-10">
      <WelcomeSection profile={profile} />
      
      <DashboardHero />
      
      <StatsGrid stats={stats} />
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
        <RecentActivity activities={activities} />
        <UpcomingEvents events={events} />
      </div>
    </main>
  );
}
