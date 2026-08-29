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

/** Restart step 4: mastery-color wire code → dot class. */
const MASTERY_DOT_CLASS: Record<string, string> = {
  RED: 'bg-red-500',
  YELLOW: 'bg-yellow-400',
  GREEN: 'bg-emerald-500',
};

/** Segmented-chip styles (shared design language L5): selected = primary
 * tint, idle = muted ghost. Applied over the outline/default variants so the
 * base border/shape primitives stay in charge. */
const SEGMENT_SELECTED =
  'h-8 rounded-lg border-primary bg-primary/10 px-3 text-xs font-medium text-primary shadow-none hover:bg-primary/15 hover:text-primary';
const SEGMENT_IDLE =
  'h-8 rounded-lg px-3 text-xs text-muted-foreground hover:bg-muted/40 hover:text-muted-foreground';

/** Weekday name for a study-day ISO date — display-only Jalali formatting
 * (no data-flow impact; mirrors `formatPersianDate`'s Intl recipe). */
const WEEKDAY_FORMAT = new Intl.DateTimeFormat('fa-IR', {
  weekday: 'long',
  calendar: 'persian',
  numberingSystem: 'arabext',
});

function formatPersianWeekday(dateInput: string): string {
  try {
    const date = new Date(dateInput);
    if (Number.isNaN(date.getTime())) return '';
    return WEEKDAY_FORMAT.format(date);
  } catch {
    return '';
  }
}

/** Plain-text color for the toolbar's adherence figure: reuses the locked
 * chip palette from `adherenceColorClass` and keeps only its text tones, so
 * the thresholds can never drift between the pill and the bare-type render. */
function adherenceTextClass(percent: number): string {
  return adherenceColorClass(percent)
    .split(' ')
    .filter((cls) => cls.startsWith('text-'))
    .join(' ');
}

type StudyFeedCardProps = {
  engagementId: number;
};

/**
 * The advisor's read view of one student's recorded study days («گزارش مطالعه»).
 *
 * Range chips drive one GET per selection; only days that actually have a saved
 * log arrive from the server, ascending. Rendering is a tight divided list —
 * one compact row per day (date + weekday, inline subject chips, quiet
 * mood/note line) under a single toolbar — an evidence screen the advisor
 * scans before planning, not a chart.
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
      <CardHeader className="p-5 pb-4">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <CalendarDays className="h-4 w-4 text-primary" />
          گزارش مطالعه
          {/* Step 8: mood mean for THIS range only; quiet-null. */}
          {!loading && moodAverage !== null && (
            <span className="ms-auto text-xs font-normal tabular-nums text-muted-foreground">
              میانگین حال‌وهوا: {formatMoodAverage(moodAverage)}
            </span>
          )}
        </CardTitle>

        {/* Compact toolbar: range chips + adherence as bare colored type +
        the exact window — everything scannable in one line. */}
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="بازه‌ی گزارش">
            {RANGE_CHIPS.map((chip) => {
              const selected = range === chip.value;
              return (
                <Button
                  key={chip.value}
                  type="button"
                  variant={selected ? 'default' : 'outline'}
                  disabled={loading}
                  onClick={() => setRange(chip.value)}
                  aria-pressed={selected}
                  className={selected ? SEGMENT_SELECTED : SEGMENT_IDLE}
                >
                  {chip.label}
                </Button>
              );
            })}
          </div>
          {!loading && adherencePercent !== null && (
            <span
              className={`text-xs font-medium tabular-nums ${adherenceTextClass(adherencePercent)}`}
            >
              پایبندی بازه: {formatAdherence(adherencePercent)}
            </span>
          )}
          {rangeLabel && !loading && (
            <span className="text-xs text-muted-foreground">
              از {formatPersianDate(rangeLabel.from)} تا {formatPersianDate(rangeLabel.to)}
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-5 pt-0 sm:p-5 sm:pt-0">
        {loading && (
          <div className="space-y-2" aria-busy="true" aria-live="polite">
            <span className="sr-only">در حال بارگذاری گزارش مطالعه…</span>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        )}

        {error && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-destructive/40 bg-destructive/5 px-3 py-2.5">
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
          <p className="py-8 text-center text-xs text-muted-foreground">
            در این بازه روزی ثبت نشده است.
          </p>
        )}

        {days && days.length > 0 && (
          <div className="divide-y divide-border/40">
            {days.map((day) => {
              const moodLabel = day.mood !== null ? MOOD_LABELS[day.mood] : undefined;
              const quietLine = [moodLabel ? `حال‌وهوا: ${moodLabel}` : '', day.note.trim()]
                .filter(Boolean)
                .join(' · ');
              return (
                <article key={day.date} className="py-2.5 first:pt-0 last:pb-0">
                  {/* Day head: Jalali date + weekday on the start edge,
                  enrichment badges + day total on the end edge. */}
                  <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                    <div className="flex min-w-0 items-baseline gap-2">
                      <span className="text-sm font-medium">{formatPersianDate(day.date)}</span>
                      <span className="text-xs text-muted-foreground">
                        {formatPersianWeekday(day.date)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {/* Restart step 1: enrichment chips — «تست» only when
                      tests were taken, «درصد» only when a percent was recorded. */}
                      {(day.testsTaken ?? 0) > 0 && (
                        <Badge variant="outline" className="px-1.5 text-[11px] font-normal tabular-nums">
                          تست: {toPersianDigits(day.testsTaken ?? 0)}
                        </Badge>
                      )}
                      {(day.testPercent ?? null) !== null && (
                        <Badge variant="outline" className="px-1.5 text-[11px] font-normal tabular-nums">
                          درصد: {toPersianDigits(day.testPercent ?? 0)}٪
                        </Badge>
                      )}
                      <span className="text-xs tabular-nums text-muted-foreground">
                        مجموع: {toPersianDigits(day.totalMinutes)} دقیقه
                      </span>
                    </div>
                  </div>

                  {/* Subjects inline as chips: mastery dot + name + detail,
                  «جبران‌نشده» as a red dot + word, minutes tabular at the end. */}
                  {day.items.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
                      {day.items.map((item) => {
                        const detail: string[] = [];
                        if (item.topic?.trim()) detail.push(item.topic.trim());
                        if (item.unitLabel?.trim()) detail.push(`واحد ${item.unitLabel.trim()}`);
                        return (
                          <span
                            key={`${item.subjectId}`}
                            className="inline-flex min-w-0 items-center gap-1.5 text-xs"
                          >
                            {/* Mastery dot rides the plan slot's color; absent
                            when the item matches no published-plan slot. */}
                            {item.masteryColor && MASTERY_DOT_CLASS[item.masteryColor] && (
                              <span
                                aria-hidden
                                className={`h-2 w-2 shrink-0 rounded-full ${MASTERY_DOT_CLASS[item.masteryColor]}`}
                              />
                            )}
                            <span className="font-medium">{item.name}</span>
                            {detail.length > 0 && (
                              <span className="truncate text-muted-foreground">
                                {detail.join(' · ')}
                              </span>
                            )}
                            {item.uncompensated === true && (
                              <span className="inline-flex shrink-0 items-center gap-1 text-[11px] text-red-500">
                                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-red-500" />
                                جبران‌نشده
                              </span>
                            )}
                            <span className="shrink-0 tabular-nums text-muted-foreground">
                              {toPersianDigits(item.minutes)} دقیقه
                            </span>
                          </span>
                        );
                      })}
                    </div>
                  )}

                  {/* Mood + note share one quiet line so a day rarely exceeds
                  two visual rows. */}
                  {quietLine && (
                    <p className="mt-1 flex items-start gap-1.5 text-[11px] leading-relaxed text-muted-foreground">
                      {day.note.trim() && <NotebookPen className="mt-0.5 h-3 w-3 shrink-0" />}
                      <span className="min-w-0">{quietLine}</span>
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
