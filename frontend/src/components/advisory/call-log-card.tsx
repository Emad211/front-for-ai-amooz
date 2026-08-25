'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { AlertCircle, Loader2, PhoneCall, RefreshCw } from 'lucide-react';

import {
  AdvisoryService,
  type CallLogItem,
} from '@/services/advisory-service';
import { formatPersianDate } from '@/lib/date-utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { JalaliDatePicker } from '@/components/advisory/study-plan/jalali-date-picker';

/** Parse an ISO `YYYY-MM-DD` into a LOCAL Date (no UTC day-shift). */
function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Jalali display label for one week: شنبه تا جمعه of that week. */
function weekRangeLabel(weekStart: string): string {
  const start = parseIsoDate(weekStart);
  if (!start) return weekStart;
  const end = new Date(
    start.getFullYear(),
    start.getMonth(),
    start.getDate() + 6,
  );
  return `${formatPersianDate(start)} تا ${formatPersianDate(end)}`;
}

/** The editable draft of one call-log row ('' = unset callDate). */
type CallDraft = {
  done: boolean;
  callDate: string;
  topic: string;
  note: string;
};

function draftOf(item: CallLogItem): CallDraft {
  return {
    done: item.done,
    callDate: item.callDate ?? '',
    topic: item.topic,
    note: item.note,
  };
}

/**
 * The advisor's weekly call plan (restart step 10): four recent weeks, each
 * with a done checkbox, an optional call date, an editable topic, and a short
 * note. Every row saves ITSELF — toggling or picking a date upserts at once,
 * text fields upsert on blur — so nothing is ever lost to a missed save
 * button. Fields ride along explicitly on every save (repo-wide set-replace
 * posture) so clearing a topic/note/date actually clears it server-side.
 */
export function CallLogCard({ engagementId }: { engagementId: number }) {
  const [rows, setRows] = useState<CallLogItem[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, CallDraft>>({});
  const [error, setError] = useState('');
  const [savingWeeks, setSavingWeeks] = useState<Set<string>>(new Set());
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setError('');
    setRows(null);
    AdvisoryService.getCallLogs(engagementId)
      .then((resp) => {
        if (!active) return;
        setRows(resp.weeks);
        const next: Record<string, CallDraft> = {};
        for (const item of resp.weeks) next[item.weekStart] = draftOf(item);
        setDrafts(next);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId, reloadKey]);

  const persistRow = async (weekStart: string, patch: Partial<CallDraft>) => {
    const current = drafts[weekStart];
    if (!current) return;
    const next: CallDraft = { ...current, ...patch };
    // Optimistic local echo so the row never snaps back while saving.
    setDrafts((prev) => ({ ...prev, [weekStart]: next }));
    setSavingWeeks((prev) => new Set(prev).add(weekStart));
    try {
      const saved = await AdvisoryService.putCallLog(engagementId, weekStart, {
        done: next.done,
        callDate: next.callDate || null,
        topic: next.topic.trim(),
        note: next.note.trim(),
      });
      if (saved) {
        setRows((prev) =>
          prev
            ? prev.map((row) => (row.weekStart === weekStart ? saved : row))
            : prev,
        );
        setDrafts((prev) => ({
          ...prev,
          [weekStart]: draftOf(saved),
        }));
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'ذخیره‌ی تماس ناموفق بود.');
    } finally {
      setSavingWeeks((prev) => {
        const nextSet = new Set(prev);
        nextSet.delete(weekStart);
        return nextSet;
      });
    }
  };

  const loading = rows === null && !error;

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <PhoneCall className="h-4 w-4 text-primary" />
          </span>
          طرح تماس هفتگی
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          وضعیت تماس هفتگی با دانش‌آموز را همین‌جا ثبت کنید؛ هر تغییر بلافاصله
          ذخیره می‌شود.
        </p>
      </CardHeader>

      <CardContent className="space-y-3">
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
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-24 w-full rounded-xl" />
            ))}
          </div>
        )}

        {rows && !error && rows.length === 0 && (
          <p className="rounded-lg border border-dashed px-3 py-6 text-center text-xs leading-relaxed text-muted-foreground">
            هنوز هفته‌ای برای ثبت تماس وجود ندارد.
          </p>
        )}

        {rows &&
          !error &&
          rows.map((row) => {
            const draft = drafts[row.weekStart] ?? draftOf(row);
            const busy = savingWeeks.has(row.weekStart);
            return (
              <div
                key={row.weekStart}
                className="space-y-2 rounded-xl border border-border/60 p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="flex cursor-pointer items-center gap-2 text-sm font-medium">
                    <Checkbox
                      checked={draft.done}
                      disabled={busy}
                      onCheckedChange={(checked) =>
                        void persistRow(row.weekStart, { done: checked === true })
                      }
                      aria-label={`تماس هفتۀ ${weekRangeLabel(row.weekStart)} انجام شد`}
                    />
                    انجام شد
                  </label>
                  <span className="flex items-center gap-2 text-xs tabular-nums text-muted-foreground">
                    {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    {weekRangeLabel(row.weekStart)}
                  </span>
                </div>

                <div className="grid gap-2 sm:grid-cols-[12rem_1fr]">
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">تاریخ تماس</span>
                    <JalaliDatePicker
                      value={draft.callDate}
                      onChange={(iso) => void persistRow(row.weekStart, { callDate: iso })}
                      placeholder="اختیاری"
                      disabled={busy}
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">موضوع</span>
                    <Input
                      value={draft.topic}
                      onChange={(e) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [row.weekStart]: { ...draft, topic: e.target.value },
                        }))
                      }
                      onBlur={(e) =>
                        void persistRow(row.weekStart, { topic: e.target.value })
                      }
                      maxLength={200}
                      placeholder="مثلاً ارائۀ برنامۀ هفتگی و هدف‌گذاری"
                      aria-label={`موضوع تماس هفتۀ ${weekRangeLabel(row.weekStart)}`}
                      className="h-9 text-xs"
                      disabled={busy}
                    />
                  </div>
                </div>

                <Textarea
                  value={draft.note}
                  onChange={(e) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [row.weekStart]: { ...draft, note: e.target.value },
                    }))
                  }
                  onBlur={(e) => void persistRow(row.weekStart, { note: e.target.value })}
                  rows={2}
                  maxLength={2000}
                  placeholder="یادداشت کوتاه تماس…"
                  aria-label={`یادداشت تماس هفتۀ ${weekRangeLabel(row.weekStart)}`}
                  className="min-h-[56px] text-xs leading-relaxed"
                  disabled={busy}
                />
              </div>
            );
          })}
      </CardContent>
    </Card>
  );
}
