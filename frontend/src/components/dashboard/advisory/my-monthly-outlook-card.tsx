'use client';

import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-react';

import {
  AdvisoryService,
  type MonthlyOutlook,
  type MonthlyOutlookExecutor,
} from '@/services/advisory-service';
import { getTodayJalali } from '@/lib/calendar';
import { formatPersianDate } from '@/lib/date-utils';
import { toPersianDigits } from '@/lib/persian-digits';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  EXECUTOR_LABELS,
  JALALI_MONTH_LABELS,
  jalaliMonthStartIso,
} from '@/components/advisory/monthly-outlook-card';

function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatJalaliDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return formatPersianDate(parseIsoDate(iso) ?? iso);
}

function ExecutorBadge({ executor }: { executor: MonthlyOutlookExecutor }) {
  return (
    <span className="shrink-0 rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
      مجری: {EXECUTOR_LABELS[executor]}
    </span>
  );
}

/**
 * The student-side read-only mirror of the monthly outlook («برنامهٔ ماه»,
 * restart step 8), browsable month by month.
 *
 * Quiet home-card rule like MySubjectsCard/MyIntakeCard: renders NOTHING until
 * a successful read confirms an active advisor AND the viewed month actually
 * has content — most students have no advisor and must not pay layout cost
 * for an empty shell. A failed fetch is swallowed by design.
 */
export function MyMonthlyOutlookCard() {
  const today = getTodayJalali();
  const [jYear, setJYear] = useState(today.year);
  const [jMonth, setJMonth] = useState(today.month);

  const monthStart = useMemo(
    () => jalaliMonthStartIso(jYear, jMonth),
    [jYear, jMonth],
  );

  const [outlook, setOutlook] = useState<MonthlyOutlook | null>(null);

  useEffect(() => {
    let active = true;
    setOutlook(null);
    AdvisoryService.getMyMonthlyOutlook(monthStart)
      .then((resp) => {
        if (active && resp.active) setOutlook(resp.outlook ?? null);
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, [monthStart]);

  const stepMonth = (delta: number) => {
    let month = jMonth + delta;
    let year = jYear;
    if (month < 1) {
      month = 12;
      year -= 1;
    } else if (month > 12) {
      month = 1;
      year += 1;
    }
    setJMonth(month);
    setJYear(year);
  };

  const entries = outlook?.entries ?? [];
  const strategies = [...(outlook?.strategies ?? [])].sort(
    (a, b) => a.position - b.position,
  );

  if (!outlook || (entries.length === 0 && strategies.length === 0)) return null;

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <span className="rounded-lg bg-primary/10 p-1.5">
              <CalendarDays className="h-4 w-4 text-primary" />
            </span>
            برنامهٔ ماه
          </CardTitle>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="ماه قبل"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={() => stepMonth(-1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <span className="min-w-20 text-center text-sm font-semibold tabular-nums">
              {JALALI_MONTH_LABELS[jMonth - 1]} {toPersianDigits(jYear)}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="ماه بعد"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={() => stepMonth(1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          تقویم و استراتژی‌هایی که مشاورت برای این ماه نوشته است.
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        {entries.length > 0 && (
          <section className="space-y-2">
            <h4 className="text-xs font-medium text-muted-foreground">
              تقویم ماه
            </h4>
            <ul className="space-y-1.5">
              {[...entries]
                .sort((a, b) => a.date.localeCompare(b.date))
                .map((entry, index) => (
                  <li
                    key={`${entry.date}-${index}`}
                    className="rounded-lg border border-border/50 bg-background/60 px-3 py-2 text-xs leading-relaxed"
                  >
                    <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 font-semibold tabular-nums text-primary">
                        {formatJalaliDate(entry.date)}
                      </span>
                      {entry.event.trim() && (
                        <span className="font-medium">{entry.event}</span>
                      )}
                    </p>
                    {entry.academicNote.trim() && (
                      <p className="mt-1 text-muted-foreground">
                        تقویم تحصیلی: {entry.academicNote}
                      </p>
                    )}
                    {entry.tasks.trim() && (
                      <p className="mt-1 whitespace-pre-line">{entry.tasks}</p>
                    )}
                  </li>
                ))}
            </ul>
          </section>
        )}

        {strategies.length > 0 && (
          <section className="space-y-2">
            <h4 className="text-xs font-medium text-muted-foreground">
              استراتژی‌های ماه
            </h4>
            <ul className="space-y-1.5">
              {strategies.map((strategy) => (
                <li
                  key={strategy.position}
                  className="space-y-1 rounded-lg border border-border/50 bg-background/60 px-3 py-2 text-xs leading-relaxed"
                >
                  <p className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                    <span className="font-medium">
                      {toPersianDigits(strategy.position)}. {strategy.title}
                    </span>
                    <ExecutorBadge executor={strategy.executor} />
                  </p>
                  {strategy.body.trim() && (
                    <p className="whitespace-pre-line text-muted-foreground">
                      {strategy.body}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
      </CardContent>
    </Card>
  );
}
