'use client';

/** Student exercises hub: overall report card + upcoming deadlines from the calendar. */
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2, CalendarClock, BookOpenCheck } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ExerciseReportCard } from '@/components/dashboard/exercises/exercise-report-card';
import {
  type ReportCard,
  type CalendarEventDto,
  getOverallReportCard,
  getStudentCalendar,
} from '@/services/exercises-service';

export default function StudentExercisesHubPage() {
  const [report, setReport] = useState<ReportCard | null>(null);
  const [events, setEvents] = useState<CalendarEventDto[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getOverallReportCard(), getStudentCalendar()])
      .then(([r, c]) => {
        setReport(r);
        setEvents(c.filter((e) => e.kind === 'exercise_deadline'));
      })
      .catch(() => {
        /* surfaced empty */
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <main dir="rtl" className="container mx-auto max-w-3xl px-4 py-6 md:py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold md:text-2xl">تمرین‌ها</h1>
        <Button variant="ghost" asChild>
          <Link href="/exercises/answers">
            <BookOpenCheck className="ms-2 h-4 w-4" />
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

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">تمرین‌های پیش‌رو</h2>
            {events.length === 0 ? (
              <p className="rounded-md border border-dashed border-border py-8 text-center text-muted-foreground">
                فعلاً تمرینی با مهلت ثبت نشده است.
              </p>
            ) : (
              events.map((ev) => (
                <Card key={ev.id}>
                  <CardContent className="flex items-center justify-between gap-2 py-4">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{ev.title}</p>
                      <p className="flex items-center gap-1 text-xs text-muted-foreground">
                        <CalendarClock className="h-3 w-3" />
                        {ev.courseTitle}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {ev.isCompleted && <Badge variant="secondary">ارسال‌شده</Badge>}
                      <Button size="sm" variant="outline" asChild>
                        <Link
                          href={
                            ev.isCompleted
                              ? `/exercises/${ev.exerciseId}/result?session=${ev.sessionId}`
                              : `/exercises/${ev.exerciseId}?session=${ev.sessionId}`
                          }
                        >
                          {ev.isCompleted ? 'مشاهدهٔ کارنامه' : 'حلِ تمرین'}
                        </Link>
                      </Button>
                    </div>
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
