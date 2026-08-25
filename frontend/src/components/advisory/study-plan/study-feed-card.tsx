'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, CalendarDays, NotebookPen, RefreshCw } from 'lucide-react';

import {
  AdvisoryService,
  type StudyFeedDay,
  type StudyFeedRange,
} from '@/services/advisory-service';
import { toPersianDigits } from '@/lib/persian-digits';
import {
  adherenceColorClass,
  formatAdherence,
  formatMoodAverage,
} from '@/lib/adherence';
import { formatPersianDate } from '@/lib/date-utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

/** Wire values for the `?days=` param with their Persian chip labels. */
const RANGE_CHIPS: { value: StudyFeedRange; label: string }[] = [
  { value: '7', label: '۷ روز اخیر' },
  { value: '14', label: '۱۴ روز اخیر' },
  { value: '30', label: '۳۰ روز اخیر' },
  { value: 'all', label: 'از شروع' },
];

/** Word chips for mood 1..5 — mirrors dashboard/study-log/mood-selector.tsx
 * labels byte-for-byte so advisor and student read the same scale. */
const MOOD_LABELS: Record<number, string> = {
  1: 'بد',
  2: 'نه چندان',
  3: 'متوسط',
  4: 'خوب',
  5: 'عالی',
};

type StudyFeedCardProps = {
  engagementId: number;
};

/**
 * The advisor's read view of one student's recorded study days («گزارش مطالعه»).
 *
 * Range chips drive one GET per selection; only days that actually have a saved
 * log arrive from the server, ascending. Rendering is deliberately plain rows:
 * this is an evidence screen the advisor scans before planning, not a chart.
 */
export function StudyFeedCard({ engagementId }: StudyFeedCardProps) {
  const [range, setRange] = useState<StudyFeedRange>('7');
  const [days, setDays] = useState<StudyFeedDay[] | null>(null);
  const [rangeLabel, setRangeLabel] = useState<{ from: string; to: string } | null>(null);
  // Step 8 aggregates — scoped to the selected range by the server; null when
  // nothing elapsed / no mood recorded (quiet-null rendering below).
  const [adherencePercent, setAdherencePercent] = useState<number | null>(null);
  const [moodAverage, setMoodAverage] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setError('');
    setDays(null);
    setAdherencePercent(null);
    setMoodAverage(null);

    AdvisoryService.getStudentStudyFeed(engagementId, range)
      .then((data) => {
        if (!active) return;
        setDays(Array.isArray(data.days) ? data.days : []);
        setRangeLabel(data.range);
        setAdherencePercent(data.adherencePercent ?? null);
        setMoodAverage(data.moodAverage ?? null);
      })
      .catch((err: unknown) => {
        // Keep `days` null so the retry stays reachable and the empty state
        // never claims "no logs" when the request simply failed.
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [engagementId, range, reloadKey]);

  const loading = !days && !error;

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <CalendarDays className="h-4 w-4 text-primary" />
          </span>
          گزارش مطالعه
        </CardTitle>
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          {RANGE_CHIPS.map((chip) => {
            const selected = range === chip.value;
            return (
              <Button
                key={chip.value}
                type="button"
                variant={selected ? 'default' : 'outline'}
                size="sm"
                disabled={loading}
                onClick={() => setRange(chip.value)}
                aria-pressed={selected}
                className="h-8 rounded-full px-3 text-xs"
              >
                {chip.label}
              </Button>
            );
          })}
        </div>
        {rangeLabel && !loading && (
          <p className="text-xs text-muted-foreground">
            بازه: از {formatPersianDate(rangeLabel.from)} تا {formatPersianDate(rangeLabel.to)}
          </p>
        )}
        {/* Step 8: weighted overall adherence + mood mean for THIS range only;
        each chip renders only when its value exists (quiet-null). */}
        {!loading && (adherencePercent !== null || moodAverage !== null) && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {adherencePercent !== null && (
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium tabular-nums ${adherenceColorClass(adherencePercent)}`}
              >
                پایبندی بازه: {formatAdherence(adherencePercent)}
              </span>
            )}
            {moodAverage !== null && (
              <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
                میانگین حال‌وهوا: {formatMoodAverage(moodAverage)}
              </span>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-2">
        {loading && (
          <div className="space-y-2" aria-busy="true" aria-live="polite">
            <span className="sr-only">در حال بارگذاری گزارش مطالعه…</span>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-20 w-full rounded-xl" />
            ))}
          </div>
        )}

        {error && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-destructive/40 bg-destructive/5 px-3 py-3">
            <p className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              <RefreshCw className="ml-2 h-4 w-4" />
              تلاش مجدد
            </Button>
          </div>
        )}

        {days && days.length === 0 && (
          <p className="rounded-xl border border-dashed px-3 py-8 text-center text-sm leading-relaxed text-muted-foreground">
            در این بازه روزی ثبت نشده است.
          </p>
        )}

        {days &&
          days.map((day) => (
            <article
              key={day.date}
              className="rounded-xl border border-border/60 bg-background/50 p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{formatPersianDate(day.date)}</span>
                  {day.mood !== null && MOOD_LABELS[day.mood] && (
                    <Badge variant="secondary" className="font-normal">
                      {MOOD_LABELS[day.mood]}
                    </Badge>
                  )}
                  {/* Restart step 1: enrichment chips — «تست» only when tests
                  were taken, «درصد» only when a percent was recorded. */}
                  {(day.testsTaken ?? 0) > 0 && (
                    <Badge variant="outline" className="font-normal tabular-nums">
                      تست: {toPersianDigits(day.testsTaken ?? 0)}
                    </Badge>
                  )}
                  {(day.testPercent ?? null) !== null && (
                    <Badge variant="outline" className="font-normal tabular-nums">
                      درصد: {toPersianDigits(day.testPercent ?? 0)}٪
                    </Badge>
                  )}
                </div>
                <span className="text-xs font-medium tabular-nums text-muted-foreground">
                  مجموع: {toPersianDigits(day.totalMinutes)} دقیقه
                </span>
              </div>

              {day.note.trim() && (
                <p className="mt-2 flex items-start gap-1.5 text-xs leading-relaxed text-muted-foreground">
                  <NotebookPen className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {day.note}
                </p>
              )}

              {day.items.length > 0 && (
                <ul className="mt-2 space-y-1 border-t border-border/40 pt-2">
                  {day.items.map((item) => (
                    <li
                      key={`${item.subjectId}`}
                      className="flex items-center justify-between gap-2 text-xs"
                    >
                      <span className="min-w-0 truncate">{item.name}</span>
                      <span className="shrink-0 tabular-nums text-muted-foreground">
                        {toPersianDigits(item.minutes)} دقیقه
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
      </CardContent>
    </Card>
  );
}
