'use client';

/**
 * The student's «مشاور» page — the consolidated home of every advisor
 * feature that used to be scattered across the dashboard (the old
 * «گزارش روزانه» page plus six advisory cards on /home), plus the student
 * calendar wired to REAL merged events: exercise deadlines, scheduled
 * exam-prep, published study-plan rows, the month's outlook entries and
 * 7-day challenge days.
 *
 * Tabs are deep-linkable via `?tab=` (log | calendar | plans | exams |
 * profile, default `log`). The calendar tab works for every student; the
 * advisor-specific tabs quiet themselves when there is no active advisor.
 */
import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { HeartHandshake } from 'lucide-react';

import { StudyLogForm } from '@/components/dashboard/advisory/study-log-form';
import { MySubjectsCard } from '@/components/dashboard/advisory/my-subjects-card';
import { MyIntakeCard } from '@/components/dashboard/advisory/my-intake-card';
import { MyExamScoresCard } from '@/components/dashboard/advisory/my-exam-scores-card';
import { MyExamAnalysesCard } from '@/components/dashboard/advisory/my-exam-analyses-card';
import { MyChallengeCard } from '@/components/dashboard/advisory/my-challenge-card';
import { MyMonthlyOutlookCard } from '@/components/dashboard/advisory/my-monthly-outlook-card';
import { StudyPlanCard } from '@/components/dashboard/home/study-plan-card';
import { AdvisoryCalendarTab } from '@/components/dashboard/advisory/advisory-calendar-tab';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { AdvisoryService, type StudentEngagement } from '@/services/advisory-service';

type AdvisorTab = 'log' | 'calendar' | 'plans' | 'exams' | 'profile';

const TABS: { id: AdvisorTab; label: string }[] = [
  { id: 'log', label: 'گزارش روزانه' },
  { id: 'calendar', label: 'تقویم' },
  { id: 'plans', label: 'برنامه‌ها' },
  { id: 'exams', label: 'آزمون‌ها' },
  { id: 'profile', label: 'مشخصات' },
];

function isAdvisorTab(value: string | null): value is AdvisorTab {
  return value === 'log' || value === 'calendar' || value === 'plans' || value === 'exams' || value === 'profile';
}

function AdvisorInactiveNotice() {
  return (
    <Card className="rounded-2xl">
      <CardContent className="py-12 text-center">
        <p className="text-sm text-muted-foreground md:text-base">
          فعلاً مشاور فعالی نداری؛ وقتی دعوت یک مشاور را بپذیری اینجا فعال می‌شود.
        </p>
      </CardContent>
    </Card>
  );
}

function AdvisorPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tabParam = searchParams.get('tab');
  const activeTab: AdvisorTab = isAdvisorTab(tabParam) ? tabParam : 'log';

  const [engagement, setEngagement] = useState<StudentEngagement | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyEngagement()
      .then((res) => {
        if (active) setEngagement(res.active);
      })
      .catch(() => {
        if (active) setEngagement(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleTabChange = (tab: AdvisorTab) => {
    router.replace(tab === 'log' ? '/advisory' : `/advisory?tab=${tab}`, { scroll: false });
  };

  const engagementBadge = useMemo(() => {
    if (engagement === undefined) return null;
    if (engagement === null) return <Badge variant="secondary" className="font-normal">بدون مشاور فعال</Badge>;
    return <Badge className="font-normal">مشاور: {engagement.advisorName}</Badge>;
  }, [engagement]);

  return (
    <main dir="rtl" className="container mx-auto max-w-6xl px-4 py-6 md:py-8">
      <div className="space-y-6">
        {/* ── header ── */}
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-xl bg-primary/10 p-2">
              <HeartHandshake className="h-5 w-5 text-primary" />
            </span>
            <h1 className="text-xl font-bold md:text-2xl">مشاور</h1>
            {engagementBadge}
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground md:text-sm">
            گزارش روزانه، تقویم برنامه‌ها، چالش‌ها و یادداشت‌های مشاورت — همه در یک جا.
          </p>
        </div>

        {/* ── tabs ── */}
        <div
          role="tablist"
          aria-label="بخش‌های مشاور"
          className="flex gap-1.5 overflow-x-auto rounded-2xl border border-border/60 bg-card p-1.5"
        >
          {TABS.map((tab) => {
            const isActive = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => handleTabChange(tab.id)}
                className={cn(
                  'whitespace-nowrap rounded-xl px-4 py-2 text-xs font-bold transition-colors md:text-sm',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* ── tab content ── */}
        <div role="tabpanel">
          {activeTab === 'log' && <StudyLogForm />}

          {activeTab === 'calendar' && <AdvisoryCalendarTab />}

          {activeTab === 'plans' &&
            (engagement === null ? (
              <AdvisorInactiveNotice />
            ) : (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div className="space-y-6">
                  <StudyPlanCard showEmptyState />
                  <MyChallengeCard />
                </div>
                <MyMonthlyOutlookCard />
              </div>
            ))}

          {activeTab === 'exams' &&
            (engagement === null ? (
              <AdvisorInactiveNotice />
            ) : (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <MyExamScoresCard showEmptyState />
                <MyExamAnalysesCard showEmptyState />
              </div>
            ))}

          {activeTab === 'profile' &&
            (engagement === null ? (
              <AdvisorInactiveNotice />
            ) : (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <MyIntakeCard />
                <MySubjectsCard />
              </div>
            ))}
        </div>
      </div>
    </main>
  );
}

export default function AdvisoryPage() {
  return (
    <Suspense
      fallback={
        <main dir="rtl" className="container mx-auto max-w-6xl px-4 py-6 md:py-8">
          <div className="space-y-6">
            <Skeleton className="h-10 w-48 rounded-xl" />
            <Skeleton className="h-12 w-full rounded-2xl" />
            <Skeleton className="h-64 w-full rounded-2xl" />
          </div>
        </main>
      }
    >
      <AdvisorPageContent />
    </Suspense>
  );
}
