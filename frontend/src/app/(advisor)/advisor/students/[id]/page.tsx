'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, ArrowRight, RefreshCw, Users } from 'lucide-react';

import {
  AdvisoryService,
  type AdvisorStudent,
} from '@/services/advisory-service';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { StudyFeedCard } from '@/components/advisory/study-plan/study-feed-card';
import { StudyPlannerCard } from '@/components/advisory/study-plan/study-planner-card';
import { IntakeCard } from '@/components/advisory/intake-card';
import { WeeklyAssessmentCard } from '@/components/advisory/weekly-assessment-card';
import { CallLogCard } from '@/components/advisory/call-log-card';
import {
  resolveStudentDetailTab,
  StudentDetailTabKey,
  StudentDetailTabs,
  StudentDetailTabPlaceholder,
} from '@/components/advisory/student-detail-tabs';

/**
 * Advisor → one student's detail («گزارش و برنامه»), split into 7 query-param
 * tabs (`?tab=feed|plan|exams|intake|assess|month|challenges`, default feed).
 *
 * Next.js 15: useSearchParams() opts its subtree out of static prerender, so
 * every consumer of it must sit inside a <Suspense> boundary or
 * `next build` fails with "missing suspense boundary with useSearchParams".
 * The default export therefore only wraps the interactive content in Suspense;
 * everything else lives in AdvisorStudentDetailContent below.
 */
export default function AdvisorStudentDetailPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <AdvisorStudentDetailContent />
    </Suspense>
  );
}

function PageFallback() {
  return (
    <div className="space-y-6" aria-busy="true" aria-live="polite">
      <span className="sr-only">در حال بارگذاری…</span>
      <Skeleton className="mx-auto h-11 w-full max-w-4xl rounded-full" />
      <Skeleton className="mx-auto h-40 w-full max-w-4xl rounded-2xl" />
    </div>
  );
}

/**
 * The route param is the ENGAGEMENT id — the same key every advisory route is
 * addressed by. The roster is fetched once to resolve the student's name and
 * engagement start: the name anchors the header immediately, and `startedOn`
 * becomes the planner's inclusive lower bound for the start date (rule C3,
 * enforced again server-side). A missing/foreign id resolves to a "not found"
 * state, never "forbidden" — mirroring the API's 404-not-403 leak posture.
 */
function AdvisorStudentDetailContent() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawId = params?.id ?? '';
  const engagementId = Number(rawId);
  const validId = Number.isInteger(engagementId) && engagementId > 0;

  const activeTab = resolveStudentDetailTab(searchParams.get('tab'));

  // Tabs are view state: replace() avoids polluting history, scroll:false
  // keeps the reader's position while switching.
  const handleTabChange = (key: StudentDetailTabKey) => {
    router.replace(`/advisor/students/${rawId}?tab=${key}`, { scroll: false });
  };

  const [student, setStudent] = useState<AdvisorStudent | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!validId) return;
    let active = true;
    setError('');
    setStudent(null);

    AdvisoryService.getStudents()
      .then((data) => {
        if (!active) return;
        const found = data.students.find((s) => s.id === engagementId) ?? null;
        setStudent(found);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [validId, engagementId, reloadKey]);

  if (!validId) {
    return <NotFoundState />;
  }

  const loading = !student && !error;

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Button asChild variant="ghost" size="sm" className="-ms-2 text-muted-foreground">
          <Link href="/advisor/students">
            <ArrowRight className="ml-1 h-4 w-4" />
            بازگشت به دانش‌آموزان
          </Link>
        </Button>
        <h1 className="flex flex-wrap items-center gap-2 text-xl font-bold sm:text-2xl">
          <Users className="h-5 w-5 text-primary" />
          {loading ? <Skeleton className="inline-block h-8 w-48" /> : student?.studentName}
        </h1>
      </div>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <p className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              <RefreshCw className="ml-2 h-4 w-4" />
              تلاش مجدد
            </Button>
          </CardContent>
        </Card>
      )}

      {!loading && !error && !student && <NotFoundState />}

      {student && (
        <div className="mx-auto w-full max-w-4xl space-y-6">
          <StudentDetailTabs activeTab={activeTab} onTabChange={handleTabChange} />

          {/* Read the evidence first, then plan — DOM order = visual order.
          Tabs whose cards have not landed yet render the «به‌زودی» placeholder
          so the IA stays stable until their waves arrive. */}
          {activeTab === 'feed' && <StudyFeedCard engagementId={engagementId} />}
          {activeTab === 'plan' && (
            <StudyPlannerCard
              engagementId={engagementId}
              studentName={student.studentName}
              startedOn={student.startedOn}
            />
          )}
          {activeTab === 'intake' && <IntakeCard engagementId={engagementId} />}
          {activeTab === 'assess' && (
            <div className="space-y-6">
              <WeeklyAssessmentCard engagementId={engagementId} />
              <CallLogCard engagementId={engagementId} />
            </div>
          )}
          {activeTab !== 'feed' &&
            activeTab !== 'plan' &&
            activeTab !== 'intake' &&
            activeTab !== 'assess' && (
              <StudentDetailTabPlaceholder tabKey={activeTab} />
            )}
        </div>
      )}
    </div>
  );
}

function NotFoundState() {
  return (
    <Card className="border-dashed">
      <CardContent className="py-12 text-center">
        <Users className="mx-auto h-8 w-8 text-muted-foreground/60" />
        <p className="mt-3 text-sm font-medium">این دانش‌آموز پیدا نشد.</p>
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
          ممکن است نشانی اشتباه باشد یا این همکاری دیگر در فهرست شما نباشد.
        </p>
        <Button asChild variant="outline" size="sm" className="mt-4">
          <Link href="/advisor/students">بازگشت به فهرست</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
