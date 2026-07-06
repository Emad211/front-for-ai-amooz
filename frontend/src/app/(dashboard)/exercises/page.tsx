'use client';

/**
 * Student exercises hub:
 * overall report card + upcoming deadlines + the COMPLETE per-class exercise list
 * (so exercises without a deadline are also discoverable).
 */
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2, CalendarClock, BookOpenCheck, NotebookPen } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ExerciseReportCard } from '@/components/dashboard/exercises/exercise-report-card';
import { MathText } from '@/components/content/math-text';
import { DashboardService } from '@/services/dashboard-service';
import { formatPersianDateTime } from '@/lib/date-utils';
import {
  type ReportCard,
  type CalendarEventDto,
  type StudentExerciseListItem,
  getOverallReportCard,
  getStudentCalendar,
  listStudentExercises,
} from '@/services/exercises-service';

type ClassExercises = {
  sessionId: number;
  courseTitle: string;
  items: StudentExerciseListItem[];
};

/** Submission window is closed: deadline passed and late submission not allowed. */
function isClosed(ex: StudentExerciseListItem): boolean {
  return ex.deadlinePassed && !ex.allowLate;
}

function statusBadge(ex: StudentExerciseListItem) {
  switch (ex.submissionStatus) {
    case 'graded':
      return <Badge variant="default">نمره ثبت شد</Badge>;
    case 'submitted':
    case 'grading':
      return <Badge variant="secondary">در انتظار نمره‌دهی</Badge>;
    case 'grading_failed':
      return <Badge variant="destructive">خطا در نمره‌دهی</Badge>;
    case 'draft':
      return isClosed(ex) ? (
        <Badge variant="secondary">مهلت به پایان رسید</Badge>
      ) : (
        <Badge variant="outline">پیش‌نویس</Badge>
      );
    default:
      return ex.deadlinePassed ? <Badge variant="secondary">مهلت به پایان رسید</Badge> : null;
  }
}

function actionFor(ex: StudentExerciseListItem, sessionId: number): { label: string; href: string } {
  if (ex.submissionStatus && ex.submissionStatus !== 'draft') {
    return { label: 'مشاهدهٔ کارنامه', href: `/exercises/${ex.id}/result?session=${sessionId}` };
  }
  // Window closed (deadline passed, no late submission) → the only honest action
  // is browsing the revealed answers; solving/submitting would 409.
  if (isClosed(ex)) {
    return { label: 'مشاهدهٔ پاسخ‌ها', href: '/exercises/answers' };
  }
  if (ex.submissionStatus === 'draft') {
    return { label: 'ادامهٔ حل', href: `/exercises/${ex.id}?session=${sessionId}` };
  }
  return { label: 'حلِ تمرین', href: `/exercises/${ex.id}?session=${sessionId}` };
}

export default function StudentExercisesHubPage() {
  const [report, setReport] = useState<ReportCard | null>(null);
  const [events, setEvents] = useState<CalendarEventDto[]>([]);
  const [classes, setClasses] = useState<ClassExercises[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const [r, cal, courses] = await Promise.all([
        getOverallReportCard().catch(() => null),
        getStudentCalendar().catch(() => [] as CalendarEventDto[]),
        DashboardService.getCourses().catch(() => []),
      ]);
      setReport(r);
      // Agenda = only OPEN exercise deadlines still in the future.
      const now = Date.now();
      setEvents(
        cal.filter(
          (e) =>
            e.kind === 'exercise_deadline' &&
            !e.isCompleted &&
            e.datetime !== null &&
            Date.parse(e.datetime) > now
        )
      );
      // Complete catalog: every published exercise of every enrolled class.
      const perClass = await Promise.all(
        courses.map(async (course) => {
          const sessionId = Number(course.id);
          if (!Number.isFinite(sessionId)) return null;
          const items = await listStudentExercises(sessionId).catch(
            () => [] as StudentExerciseListItem[]
          );
          return { sessionId, courseTitle: course.title, items };
        })
      );
      setClasses(
        perClass.filter((c): c is ClassExercises => c !== null && c.items.length > 0)
      );
    };
    load().finally(() => setLoading(false));
  }, []);

  return (
    <main dir="rtl" className="container mx-auto max-w-3xl px-4 py-6 md:py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold md:text-2xl">تمرین‌ها</h1>
        <Button variant="ghost" asChild>
          <Link href="/exercises/answers">
            <BookOpenCheck className="h-4 w-4" />
            پاسخ تمرین‌های تمام‌شده
          </Link>
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-6">
          {report && <ExerciseReportCard data={report} title="کارنامهٔ کلی" />}

          {events.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-lg font-semibold">مهلت‌های پیش‌رو</h2>
              {events.map((ev) => (
                <Card key={ev.id}>
                  <CardContent className="flex items-center justify-between gap-2 py-4">
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        <MathText text={ev.title} />
                      </p>
                      <p className="flex items-center gap-1 text-xs text-muted-foreground">
                        <CalendarClock className="h-3 w-3" />
                        <MathText text={ev.courseTitle} />
                        {ev.datetime && <span>· مهلت: {formatPersianDateTime(ev.datetime)}</span>}
                      </p>
                    </div>
                    <Button size="sm" variant="outline" asChild>
                      <Link href={`/exercises/${ev.exerciseId}?session=${ev.sessionId}`}>
                        حلِ تمرین
                      </Link>
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </section>
          )}

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">همهٔ تمرین‌ها</h2>
            {classes.length === 0 ? (
              <p className="rounded-md border border-dashed border-border py-8 text-center text-muted-foreground">
                هنوز تمرینی برای کلاس‌های شما منتشر نشده است.
              </p>
            ) : (
              classes.map((cls) => (
                <Card key={cls.sessionId}>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <NotebookPen className="h-4 w-4 text-primary" />
                      <MathText text={cls.courseTitle} />
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {cls.items.map((ex) => {
                      const action = actionFor(ex, cls.sessionId);
                      return (
                        <div
                          key={ex.id}
                          className="flex items-center justify-between gap-2 rounded-md border border-border p-3"
                        >
                          <div className="min-w-0">
                            <p className="truncate font-medium">
                              <MathText text={ex.title} />
                            </p>
                            <p className="flex items-center gap-1 text-xs text-muted-foreground">
                              {ex.deadline ? (
                                <>
                                  <CalendarClock className="h-3 w-3" />
                                  مهلت: {formatPersianDateTime(ex.deadline)}
                                </>
                              ) : (
                                'بدون مهلت'
                              )}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {statusBadge(ex)}
                            <Button size="sm" variant="outline" asChild>
                              <Link href={action.href}>{action.label}</Link>
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>
              ))
            )}
          </section>
        </div>
      )}
    </main>
  );
}
