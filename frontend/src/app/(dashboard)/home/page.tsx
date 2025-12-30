
"use client";

import { DashboardHero } from '@/components/dashboard/dashboard-hero';
import { WelcomeSection } from '@/components/dashboard/home/welcome-section';
import { StatsGrid } from '@/components/dashboard/home/stats-grid';
import { RecentActivity } from '@/components/dashboard/home/recent-activity';
import { UpcomingEvents } from '@/components/dashboard/home/upcoming-events';
import { useDashboardData } from '@/hooks/use-dashboard-data';
import { Skeleton } from '@/components/ui/skeleton';
import { StatsSkeleton } from '@/components/dashboard/stats-skeleton';
import { PageTransition } from '@/components/ui/page-transition';
import { ErrorState } from '@/components/shared/error-state';

export default function StudentDashboard() {
  const { stats, activities, events, profile, isLoading, error, reload } = useDashboardData();

  if (isLoading) {
    return (
      <PageTransition>
        <main className="p-4 md:p-8 max-w-7xl mx-auto space-y-8 md:space-y-10">
          <div className="space-y-4">
            <Skeleton className="h-10 w-48" />
            <Skeleton className="h-6 w-64" />
          </div>
          <Skeleton className="h-64 w-full rounded-3xl" />
          <StatsSkeleton />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
            <div className="lg:col-span-2 space-y-4">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-[400px] w-full rounded-2xl" />
            </div>
            <div className="space-y-4">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-[400px] w-full rounded-2xl" />
            </div>
          </div>
        </main>
      </PageTransition>
    );
  }

  if (error) {
    return (
      <PageTransition>
        <main className="p-4 md:p-8 max-w-7xl mx-auto flex items-center justify-center h-[60vh]">
          <div className="w-full max-w-2xl">
            <ErrorState title="خطا در بارگذاری" description={error} onRetry={reload} />
          </div>
        </main>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <main className="p-4 md:p-8 max-w-7xl mx-auto space-y-8 md:space-y-10">
        <WelcomeSection profile={profile} />
        
        <DashboardHero />
        
        <StatsGrid stats={stats} />
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
          <RecentActivity activities={activities} />
          <UpcomingEvents events={events} />
        </div>
      </main>
    </PageTransition>
  );
}
