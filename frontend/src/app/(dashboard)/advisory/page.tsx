'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  BarChart3,
  CalendarCheck2,
  CalendarDays,
  ChevronDown,
  ClipboardPenLine,
  FolderOpen,
  HeartHandshake,
  RefreshCw,
} from 'lucide-react';

import { AdvisoryCalendarTab } from '@/components/dashboard/advisory/advisory-calendar-tab';
import { AnalyticsTab } from '@/components/dashboard/advisory/analytics-tab';
import { GoalCard } from '@/components/dashboard/advisory/goal-card';
import { MistakeLogCard } from '@/components/dashboard/advisory/mistake-log-card';
import { MyChallengeCard } from '@/components/dashboard/advisory/my-challenge-card';
import { MyExamAnalysesCard } from '@/components/dashboard/advisory/my-exam-analyses-card';
import { MyExamScoresCard } from '@/components/dashboard/advisory/my-exam-scores-card';
import { MyIntakeCard } from '@/components/dashboard/advisory/my-intake-card';
import { MyMonthlyOutlookCard } from '@/components/dashboard/advisory/my-monthly-outlook-card';
import { MyParentsCard } from '@/components/dashboard/advisory/my-parents-card';
import { MySubjectsCard } from '@/components/dashboard/advisory/my-subjects-card';
import { StudyLogForm } from '@/components/dashboard/advisory/study-log-form';
import { TopicProgressCard } from '@/components/dashboard/advisory/topic-progress-card';
import { StudyPlanCard } from '@/components/dashboard/home/study-plan-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AdvisoryService, type StudentEngagement } from '@/services/advisory-service';

type AdvisoryJob = 'today' | 'plan' | 'progress' | 'record';
type EngagementPhase = 'loading' | 'ready' | 'error';

const JOBS = [
  { id: 'today', label: 'امروز', icon: ClipboardPenLine },
  { id: 'plan', label: 'برنامه', icon: CalendarCheck2 },
  { id: 'progress', label: 'پیشرفت', icon: BarChart3 },
  { id: 'record', label: 'پرونده', icon: FolderOpen },
] as const;

const LEGACY_JOB_ALIASES: Record<string, AdvisoryJob> = {
  log: 'today',
  calendar: 'plan',
  plans: 'plan',
  insights: 'progress',
  exams: 'record',
  profile: 'record',
};

function resolveJob(value: string | null): AdvisoryJob {
  if (JOBS.some((job) => job.id === value)) return value as AdvisoryJob;
  return value ? LEGACY_JOB_ALIASES[value] ?? 'today' : 'today';
}

function AdvisorInactiveNotice() {
  return (
    <Card className="border-dashed">
      <CardContent className="py-12 text-center">
        <HeartHandshake className="mx-auto h-8 w-8 text-muted-foreground" />
        <p className="mt-3 text-sm font-semibold">هنوز مشاور فعالی نداری</p>
        <p className="mx-auto mt-1 max-w-md text-xs leading-6 text-muted-foreground">
          با پذیرش دعوت مشاور، برنامه‌ها، تحلیل پیشرفت و پروندهٔ مشاوره در این بخش فعال می‌شود.
        </p>
      </CardContent>
    </Card>
  );
}

function DisclosureSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <details className="group rounded-2xl border border-border/60 bg-card">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:px-6">
        <span>
          <span className="block text-sm font-semibold">{title}</span>
          <span className="mt-1 block text-xs leading-6 text-muted-foreground">{description}</span>
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border/60 p-4 sm:p-6">{children}</div>
    </details>
  );
}

function EngagementBoundary({
  phase,
  engagement,
  onRetry,
  children,
}: {
  phase: EngagementPhase;
  engagement: StudentEngagement | null;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  if (phase === 'loading') {
    return <Skeleton className="h-48 w-full rounded-2xl" />;
  }
  if (phase === 'error') {
    return (
      <Card className="border-destructive/40 bg-destructive/5" role="alert">
        <CardContent className="flex flex-col items-start gap-4 py-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-destructive">وضعیت همکاری با مشاور دریافت نشد.</p>
          <Button variant="outline" className="h-11" onClick={onRetry}>
            <RefreshCw className="h-4 w-4" />
            تلاش مجدد
          </Button>
        </CardContent>
      </Card>
    );
  }
  if (!engagement) return <AdvisorInactiveNotice />;
  return <>{children}</>;
}

function AdvisorPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeJob = resolveJob(searchParams.get('tab'));
  const [engagement, setEngagement] = useState<StudentEngagement | null>(null);
  const [engagementPhase, setEngagementPhase] = useState<EngagementPhase>('loading');
  const [reloadKey, setReloadKey] = useState(0);
  // Page-owned study-timer clock and unsaved-edits flag: Radix TabsContent
  // unmounts the «امروز» form, so this state must live above the Tabs to
  // survive a tab switch (the timer keeps counting on other tabs).
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [timerRunning, setTimerRunning] = useState(false);
  const [logDirty, setLogDirty] = useState(false);

  useEffect(() => {
    if (!timerRunning) return;
    const tick = setInterval(() => setTimerSeconds((s) => s + 1), 1000);
    return () => clearInterval(tick);
  }, [timerRunning]);

  const loadEngagement = useCallback(() => {
    setEngagementPhase('loading');
    AdvisoryService.getMyEngagement()
      .then((response) => {
        setEngagement(response.active);
        setEngagementPhase('ready');
      })
      .catch(() => {
        setEngagement(null);
        setEngagementPhase('error');
      });
  }, []);

  useEffect(() => {
    loadEngagement();
  }, [loadEngagement, reloadKey]);

  const handleJobChange = (value: string) => {
    const job = resolveJob(value);
    if (activeJob === 'today' && job !== 'today' && (logDirty || timerRunning)) {
      const confirmed = window.confirm(
        'تغییرات ذخیره‌نشده داری. مطمئنی می‌خواهی خارج شوی؟',
      );
      if (!confirmed) return;
    }
    router.replace(job === 'today' ? '/advisory' : `/advisory?tab=${job}`, { scroll: false });
  };

  return (
    <main dir="rtl" className="container mx-auto max-w-6xl px-4 py-6 md:py-8">
      <div className="space-y-6">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-xl bg-primary/10 p-2">
                <HeartHandshake className="h-5 w-5 text-primary" />
              </span>
              <h1 className="text-xl font-bold md:text-2xl">مسیر مشاوره</h1>
              {engagementPhase === 'ready' && (
                <Badge variant={engagement ? 'default' : 'secondary'} className="font-normal">
                  {engagement ? `مشاور: ${engagement.advisorName}` : 'بدون مشاور فعال'}
                </Badge>
              )}
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-muted-foreground">
              از کار امروز شروع کن؛ برنامه، روند پیشرفت و جزئیات پرونده همیشه در دسترس‌اند.
            </p>
          </div>
          {activeJob === 'today' && (
            <p className="text-xs text-muted-foreground">اقدام اصلی امروز: تکمیل و ثبت گزارش روز</p>
          )}
        </header>

        <Tabs value={activeJob} onValueChange={handleJobChange} dir="rtl">
          <div className="overflow-x-auto rounded-2xl border border-border/60 bg-card p-1.5">
            <TabsList aria-label="کارهای مسیر مشاوره" className="h-auto min-w-max justify-start bg-transparent p-0">
              {JOBS.map((job) => (
                <TabsTrigger
                  key={job.id}
                  value={job.id}
                  className="h-11 gap-2 rounded-xl px-4 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-none"
                >
                  <job.icon className="h-4 w-4" />
                  {job.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>

          <TabsContent value="today" className="mt-6">
            <StudyLogForm
              timerSeconds={timerSeconds}
              timerRunning={timerRunning}
              onTimerSecondsChange={setTimerSeconds}
              onTimerRunningChange={setTimerRunning}
              onDirtyChange={setLogDirty}
            />
          </TabsContent>

          <TabsContent value="plan" className="mt-6 space-y-6">
            <section aria-labelledby="advisory-calendar-heading">
              <div className="mb-3 flex items-center gap-2">
                <CalendarDays className="h-5 w-5 text-primary" />
                <h2 id="advisory-calendar-heading" className="text-base font-semibold">زمان‌بندی پیش رو</h2>
              </div>
              <AdvisoryCalendarTab />
            </section>
            <EngagementBoundary
              phase={engagementPhase}
              engagement={engagement}
              onRetry={() => setReloadKey((key) => key + 1)}
            >
              <div className="grid gap-6 lg:grid-cols-2">
                <div className="space-y-6">
                  <StudyPlanCard showEmptyState />
                  <MyChallengeCard />
                </div>
                <MyMonthlyOutlookCard />
              </div>
            </EngagementBoundary>
          </TabsContent>

          <TabsContent value="progress" className="mt-6">
            <EngagementBoundary
              phase={engagementPhase}
              engagement={engagement}
              onRetry={() => setReloadKey((key) => key + 1)}
            >
              <div className="space-y-6">
                <AnalyticsTab />
                <DisclosureSection
                  title="پوشش مباحث"
                  description="وضعیت خواندن، مرور و تسلط هر مبحث را در صورت نیاز باز کن."
                >
                  <TopicProgressCard />
                </DisclosureSection>
              </div>
            </EngagementBoundary>
          </TabsContent>

          <TabsContent value="record" className="mt-6">
            <EngagementBoundary
              phase={engagementPhase}
              engagement={engagement}
              onRetry={() => setReloadKey((key) => key + 1)}
            >
              <div className="space-y-4">
                <DisclosureSection
                  title="آزمون‌ها و دفتر اشتباهات"
                  description="نمره‌ها، تحلیل آزمون و خطاهایی که باید دوباره مرور شوند."
                >
                  <div className="space-y-6">
                    <div className="grid gap-6 lg:grid-cols-2">
                      <MyExamScoresCard showEmptyState />
                      <MyExamAnalysesCard showEmptyState />
                    </div>
                    <MistakeLogCard />
                  </div>
                </DisclosureSection>
                <DisclosureSection
                  title="هدف و شناخت"
                  description="هدف تحصیلی، فرم شناخت و درس‌های انتخاب‌شده توسط مشاور."
                >
                  <div className="grid gap-6 lg:grid-cols-2">
                    <MyIntakeCard />
                    <MySubjectsCard />
                    <MyParentsCard />
                    <div className="lg:col-span-2"><GoalCard /></div>
                  </div>
                </DisclosureSection>
              </div>
            </EngagementBoundary>
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}

export default function AdvisoryPage() {
  return (
    <Suspense fallback={<AdvisorPageFallback />}>
      <AdvisorPageContent />
    </Suspense>
  );
}

function AdvisorPageFallback() {
  return (
    <main dir="rtl" className="container mx-auto max-w-6xl px-4 py-6 md:py-8" aria-busy="true">
      <span className="sr-only">در حال بارگذاری مسیر مشاوره…</span>
      <div className="space-y-6">
        <Skeleton className="h-14 w-full max-w-lg rounded-xl" />
        <Skeleton className="h-14 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    </main>
  );
}
