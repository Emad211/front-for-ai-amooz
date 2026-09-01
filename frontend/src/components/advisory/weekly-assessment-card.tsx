'use client';

import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Loader2,
  RefreshCw,
} from 'lucide-react';

import {
  AdvisoryService,
  type WeeklyAssessmentCriterion,
  type WeeklyAssessmentItem,
} from '@/services/advisory-service';
import { toPersianDigits } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

/** Parse an ISO `YYYY-MM-DD` into a LOCAL Date (no UTC day-shift). */
function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Anchor any picked date to its week's Saturday — the client twin of the
 * backend's `week_start = d - ((weekday + 2) % 7)` rule (Python weekday:
 * Mon=0). In JS terms the identical offset is `(getDay() + 8) % 7`
 * (Sat→0, Sun→1, … Fri→6), so a mid-week pick silently lands on شنبه and the
 * server never sees a non-Saturday 400 from this picker.
 */
function saturdayAnchor(iso: string): string {
  const date = parseIsoDate(iso);
  if (!date) return iso;
  const offset = (date.getDay() + 8) % 7;
  return toIsoDate(
    new Date(date.getFullYear(), date.getMonth(), date.getDate() - offset),
  );
}

/** Shift a Saturday-anchored ISO week by whole weeks (stepper navigation). */
function shiftWeek(iso: string, weeks: number): string {
  const date = parseIsoDate(iso);
  if (!date) return iso;
  return toIsoDate(
    new Date(date.getFullYear(), date.getMonth(), date.getDate() + weeks * 7),
  );
}

function formatAverage(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return toPersianDigits(value.toFixed(1)).replace('.', '٫');
}

/** Live mean over the currently-set editor scores, or null when none set. */
function liveAverage(scores: Record<string, number>): number | null {
  const values = Object.values(scores);
  if (values.length === 0) return null;
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

const SCORE_VALUES = [1, 2, 3, 4, 5] as const;

/**
 * The advisor's weekly assessment card (restart step 7): criteria × score
 * 1..5 per Saturday-anchored week plus a textual summary, one upsert per week.
 *
 * Criteria rows render FROM the server's meta list (`criteria`) — labels are
 * never hardcoded client-side, so a backend relabel lands here for free.
 * A compact stepper (هفتهٔ قبل / هفتهٔ بعد) walks weeks one Saturday at a
 * time; selecting a saved week below loads that week's stored values back
 * into the editor. Saving upserts and refreshes the list.
 */
export function WeeklyAssessmentCard({ engagementId }: { engagementId: number }) {
  const [criteria, setCriteria] = useState<WeeklyAssessmentCriterion[] | null>(null);
  const [assessments, setAssessments] = useState<WeeklyAssessmentItem[]>([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  // Default editor target: the CURRENT week's Saturday.
  const [selectedWeekStart, setSelectedWeekStart] = useState(() =>
    saturdayAnchor(toIsoDate(new Date())),
  );
  const [scores, setScores] = useState<Record<string, number>>({});
  const [summary, setSummary] = useState('');

  useEffect(() => {
    let active = true;
    setError('');
    setCriteria(null);
    AdvisoryService.getWeeklyAssessments(engagementId)
      .then((resp) => {
        if (!active) return;
        setCriteria(resp.criteria);
        setAssessments(resp.assessments);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId, reloadKey]);

  // Switching weeks (or a post-save refresh) reseeds the editor from whatever
  // is stored for that week — blank when nothing is saved yet.
  useEffect(() => {
    const found =
      assessments.find((a) => a.weekStart === selectedWeekStart) ?? null;
    setScores(found ? { ...found.scores } : {});
    setSummary(found?.advisorSummary ?? '');
  }, [selectedWeekStart, assessments]);

  const setScore = (code: string, value: number) => {
    setScores((prev) => ({ ...prev, [code]: value }));
  };

  const complete =
    criteria !== null &&
    criteria.length > 0 &&
    criteria.every((c) => {
      const value = scores[c.code];
      return Number.isInteger(value) && value >= 1 && value <= 5;
    });

  const average = useMemo(() => liveAverage(scores), [scores]);

  const refetch = () => {
    AdvisoryService.getWeeklyAssessments(engagementId)
      .then((resp) => {
        setCriteria(resp.criteria);
        setAssessments(resp.assessments);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
  };

  const handleSave = async () => {
    if (criteria === null || criteria.length === 0) return;
    if (!complete) {
      toast.error(
        `به همهٔ ${toPersianDigits(criteria.length)} معیار نمرهٔ ۱ تا ۵ بدهید.`,
      );
      return;
    }
    setSaving(true);
    try {
      await AdvisoryService.putWeeklyAssessment(engagementId, selectedWeekStart, {
        scores,
        advisorSummary: summary.trim(),
      });
      toast.success('ارزیابی این هفته ذخیره شد.');
      refetch();
    } catch (err: unknown) {
      // Server 400s name the offending criterion in Persian — surface verbatim.
      toast.error(err instanceof Error ? err.message : 'ذخیرهٔ ارزیابی ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  const loading = criteria === null && !error;

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="p-5 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <ClipboardCheck className="h-4 w-4 shrink-0 text-primary" />
            ارزیابی هفتگی
          </CardTitle>
          {/* The week's headline metric, live as the advisor scores. */}
          <div className="ms-auto flex items-baseline gap-1.5" aria-live="polite">
            <span className="text-xs text-muted-foreground">میانگین هفته</span>
            <span className="text-2xl font-bold tabular-nums text-primary">
              {formatAverage(average)}
            </span>
          </div>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          برای هر هفته، به همهٔ معیارها نمرهٔ ۱ تا ۵ بدهید و جمع‌بندی مشاور را
          بنویسید.
        </p>
      </CardHeader>

      <CardContent className="space-y-4 p-5 pt-0">
        {/* ── week stepper ──────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setSelectedWeekStart(shiftWeek(selectedWeekStart, -1))}
            className="inline-flex h-8 items-center gap-1 rounded-lg border px-3 text-xs text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
          >
            <ChevronRight className="h-3.5 w-3.5" />
            هفتهٔ قبل
          </button>
          <div className="rounded-lg border border-border/40 bg-muted/30 px-3 py-1.5 text-xs tabular-nums text-muted-foreground">
            هفتهٔ{' '}
            <span className="font-medium text-foreground">
              {formatPersianDate(parseIsoDate(selectedWeekStart) ?? selectedWeekStart)}
            </span>{' '}
            (شنبه)
          </div>
          <button
            type="button"
            onClick={() => setSelectedWeekStart(shiftWeek(selectedWeekStart, 1))}
            className="inline-flex h-8 items-center gap-1 rounded-lg border px-3 text-xs text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
          >
            هفتهٔ بعد
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
        </div>

        {error && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
            <p className="flex items-center gap-2 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {error}
            </p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              <RefreshCw className="ml-2 h-3.5 w-3.5" />
              تلاش مجدد
            </Button>
          </div>
        )}

        {loading && (
          <div className="space-y-2" aria-busy="true">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-9 w-full rounded-lg" />
            ))}
          </div>
        )}

        {/* ── criteria rows — rendered FROM server meta, never hardcoded ── */}
        {criteria && !error && (
          <ul className="divide-y divide-border/40">
            {criteria.map((criterion) => (
              <li key={criterion.code} className="flex items-center justify-between gap-3 py-1.5">
                <span
                  className="min-w-0 flex-1 truncate text-sm leading-relaxed"
                  title={criterion.label}
                >
                  {criterion.label}
                </span>
                <div
                  role="group"
                  aria-label={`نمرهٔ «${criterion.label}»`}
                  className="flex shrink-0 items-center gap-1"
                >
                  {SCORE_VALUES.map((value) => {
                    const selected = scores[criterion.code] === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={selected}
                        aria-label={`نمرهٔ ${toPersianDigits(value)}`}
                        onClick={() => setScore(criterion.code, value)}
                        className={cn(
                          'h-8 w-9 rounded-md border text-sm tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                          selected
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-border text-muted-foreground hover:border-primary/40 hover:bg-muted/40',
                        )}
                      >
                        {toPersianDigits(value)}
                      </button>
                    );
                  })}
                </div>
              </li>
            ))}
            {criteria.length === 0 && (
              <li className="py-6 text-center text-xs text-muted-foreground">
                فهرست معیارها دریافت نشد.
              </li>
            )}
          </ul>
        )}

        {/* ── summary + save ────────────────────────────────────────────── */}
        {criteria && !error && (
          <>
            <div className="space-y-1.5">
              <label
                htmlFor="assessment-summary"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                جمع‌بندی مشاور
              </label>
              <Textarea
                id="assessment-summary"
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder="جمع‌بندی این هفته را بنویسید…"
                className="min-h-[60px] text-sm leading-relaxed"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2 border-t border-border/40 pt-4">
              <Button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="h-9 px-4 text-sm"
              >
                {saving && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
                {saving ? 'در حال ذخیره…' : 'ذخیره'}
              </Button>
              {!complete && (
                <span className="text-xs text-muted-foreground">
                  هنوز به همهٔ معیارها نمره داده نشده است.
                </span>
              )}
            </div>
          </>
        )}

        {/* ── saved weeks ───────────────────────────────────────────────── */}
        {criteria && !error && assessments.length > 0 && (
          <div className="border-t border-border/40 pt-4">
            <span className="text-sm font-medium">هفته‌های ثبت‌شده</span>
            <ul className="mt-2 divide-y divide-border/40">
              {[...assessments]
                .sort((a, b) => b.weekStart.localeCompare(a.weekStart))
                .map((item) => {
                  const isSelected = item.weekStart === selectedWeekStart;
                  return (
                    <li key={item.weekStart}>
                      <button
                        type="button"
                        onClick={() => setSelectedWeekStart(item.weekStart)}
                        aria-pressed={isSelected}
                        className={cn(
                          '-mx-2 flex w-full items-center justify-between gap-2 rounded-lg px-2 py-2 text-right transition-colors',
                          isSelected ? 'bg-primary/10' : 'hover:bg-muted/30',
                        )}
                      >
                        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                          هفتهٔ{' '}
                          {formatPersianDate(parseIsoDate(item.weekStart) ?? item.weekStart)}
                        </span>
                        <span className="flex min-w-0 items-center gap-2">
                          {item.advisorSummary.trim() && (
                            <span className="hidden min-w-0 max-w-48 truncate text-xs text-muted-foreground sm:inline">
                              {item.advisorSummary.trim()}
                            </span>
                          )}
                          <Badge variant="outline" className="shrink-0 text-[11px] tabular-nums">
                            میانگین {formatAverage(item.average)}
                          </Badge>
                        </span>
                      </button>
                    </li>
                  );
                })}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
