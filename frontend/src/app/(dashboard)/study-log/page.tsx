'use client';

/**
 * Student daily study log (گزارش روزانه) — step 5 of the Advisor MVP.
 *
 * One page = one day: mood, per-subject minutes, free note. Saving is a
 * WHOLE-day set-replace and the server answer is the source of truth — every
 * successful save re-renders ALL state from the response payload, never from
 * local guesses (server-side totals and removed-subject history win).
 */
import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { MoodSelector } from '@/components/dashboard/study-log/mood-selector';
import { StudyLogHeader } from '@/components/dashboard/study-log/study-log-header';
import { SubjectMinuteRows } from '@/components/dashboard/study-log/subject-minute-rows';
import { ErrorState } from '@/components/shared/error-state';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { AdvisoryService } from '@/services/advisory-service';
import type { StudyLogPayload } from '@/services/advisory-service';
import { toEnglishDigits, toPersianDigits } from '@/lib/persian-digits';

const MAX_MINUTES_PER_SUBJECT = 960;
const DAY_TOTAL_CAP = 1440;
/** ~85% of the cap: start warning before the hard server limit. */
const DAY_TOTAL_WARNING = 1200;
const NOTE_MAX_LENGTH = 1000;

type PagePhase = 'loading' | 'error' | 'inactive' | 'ready';

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function toIsoDate(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function todayIso(): string {
  return toIsoDate(new Date());
}

/** Shift an ISO `YYYY-MM-DD` by whole days in LOCAL time (no UTC drift). */
function shiftIsoDate(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00`);
  date.setDate(date.getDate() + days);
  return toIsoDate(date);
}

function parseMinutes(raw: string): number {
  const parsed = Number.parseInt(toEnglishDigits(raw), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

/** Digits-only, clamped to the per-subject server limit; '' when empty. */
function sanitizeMinutesInput(raw: string): string {
  const digits = toEnglishDigits(raw).replace(/\D/g, '');
  if (!digits) return '';
  return String(Math.min(Number.parseInt(digits, 10), MAX_MINUTES_PER_SUBJECT));
}

export default function StudyLogPage() {
  const [phase, setPhase] = useState<PagePhase>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [payload, setPayload] = useState<StudyLogPayload | null>(null);

  // Form state — rebuilt from every server response.
  const [selectedDate, setSelectedDate] = useState<string>(todayIso());
  const [mood, setMood] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [minutesBySubject, setMinutesBySubject] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);

  const applyResponse = useCallback((data: StudyLogPayload) => {
    setPayload(data);
    setSelectedDate(data.date);
    setMood(data.log?.mood ?? null);
    setNote(data.log?.note ?? '');
    const nextMinutes: Record<number, string> = {};
    for (const item of data.log?.items ?? []) {
      if (item.isSelected && item.minutes > 0) {
        nextMinutes[item.subjectId] = String(item.minutes);
      }
    }
    setMinutesBySubject(nextMinutes);
  }, []);

  const load = useCallback(
    async (dateIso?: string) => {
      setPhase('loading');
      try {
        const data = await AdvisoryService.getMyStudyLog(dateIso);
        applyResponse(data);
        setPhase(data.active ? 'ready' : 'inactive');
      } catch (err: unknown) {
        setErrorMessage(
          err instanceof Error ? err.message : 'خطا در بارگذاری گزارش روزانه.'
        );
        setPhase('error');
      }
    },
    [applyResponse]
  );

  useEffect(() => {
    void load();
  }, [load]);

  const handleShiftDay = (days: number) => {
    const next = shiftIsoDate(selectedDate, days);
    setSelectedDate(next);
    void load(next);
  };

  const handleMinutesChange = (subjectId: number, raw: string) => {
    setMinutesBySubject((prev) => ({ ...prev, [subjectId]: sanitizeMinutesInput(raw) }));
  };

  const handleQuickAdd = (subjectId: number, delta: number) => {
    setMinutesBySubject((prev) => {
      const current = parseMinutes(prev[subjectId] ?? '');
      const next = Math.min(current + delta, MAX_MINUTES_PER_SUBJECT);
      return { ...prev, [subjectId]: String(next) };
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // WHOLE-day payload: only entries with minutes > 0 are sent; an empty
      // array is a valid "cleared day".
      const items = Object.entries(minutesBySubject)
        .map(([subjectId, raw]) => ({
          subjectId: Number(subjectId),
          minutes: parseMinutes(raw),
        }))
        .filter((item) => item.minutes > 0);

      const response = await AdvisoryService.saveMyStudyLog({
        date: selectedDate,
        mood,
        note,
        items,
      });
      applyResponse(response);
      toast.success('گزارش امروز ثبت شد');
    } catch (err: unknown) {
      // Persian `detail` from the server (409 no advisor / 400 over-limits…).
      toast.error(err instanceof Error ? err.message : 'ثبت گزارش ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  if (phase === 'loading') {
    return (
      <main dir="rtl" className="container mx-auto max-w-3xl px-4 py-6 md:py-8">
        <div className="space-y-6">
          <Skeleton className="h-10 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-2xl" />
          <Skeleton className="h-48 w-full rounded-2xl" />
          <Skeleton className="h-36 w-full rounded-2xl" />
        </div>
      </main>
    );
  }

  if (phase === 'error') {
    return (
      <main dir="rtl" className="container mx-auto max-w-3xl px-4 py-6 md:py-8">
        <ErrorState
          title="خطا در بارگذاری گزارش روزانه"
          description={errorMessage}
          onRetry={() => void load(selectedDate)}
        />
      </main>
    );
  }

  if (phase === 'inactive' || !payload) {
    return (
      <main dir="rtl" className="container mx-auto max-w-3xl px-4 py-6 md:py-8">
        <Card className="rounded-2xl">
          <CardContent className="py-12 text-center">
            <p className="text-sm text-muted-foreground md:text-base">
              فعلاً مشاور فعالی نداری؛ وقتی دعوت یک مشاور را بپذیری اینجا فعال می‌شود.
            </p>
          </CardContent>
        </Card>
      </main>
    );
  }

  const removedItems = (payload.log?.items ?? []).filter((item) => !item.isSelected);
  const removedTotal = removedItems.reduce((sum, item) => sum + item.minutes, 0);
  const activeTotal = Object.values(minutesBySubject).reduce(
    (sum, raw) => sum + parseMinutes(raw),
    0
  );
  const totalMinutes = activeTotal + removedTotal;
  const totalTone =
    totalMinutes > DAY_TOTAL_CAP
      ? 'text-destructive'
      : totalMinutes >= DAY_TOTAL_WARNING
        ? 'text-amber-600 dark:text-amber-400'
        : 'text-muted-foreground';

  return (
    <main dir="rtl" className="container mx-auto max-w-3xl px-4 py-6 md:py-8">
      <div className="space-y-6">
        <StudyLogHeader
          date={selectedDate}
          advisorName={payload.advisorName}
          minDate={payload.minDate}
          maxDate={payload.maxDate}
          onPrevDay={() => handleShiftDay(-1)}
          onNextDay={() => handleShiftDay(1)}
        />

        <Card className="rounded-2xl">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">حال و هوای امروز</CardTitle>
            <CardDescription>امروز مطالعه را چطور حس کردی؟</CardDescription>
          </CardHeader>
          <CardContent>
            <MoodSelector value={mood} onChange={setMood} disabled={saving} />
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">دقایق مطالعه به تفکیک درس</CardTitle>
              <span className={`text-sm font-semibold ${totalTone}`}>
                مجموع امروز: {toPersianDigits(totalMinutes)} دقیقه
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <SubjectMinuteRows
              subjects={payload.subjects}
              minutesBySubject={minutesBySubject}
              removedItems={removedItems}
              onMinutesChange={handleMinutesChange}
              onQuickAdd={handleQuickAdd}
              disabled={saving}
            />
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">یادداشت</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, NOTE_MAX_LENGTH))}
              maxLength={NOTE_MAX_LENGTH}
              rows={4}
              disabled={saving}
              placeholder="هر نکته‌ای دربارهٔ امروز…"
              aria-label="یادداشت روز"
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {toPersianDigits(note.length)} / {toPersianDigits(NOTE_MAX_LENGTH)}
              </span>
              <Button onClick={() => void handleSave()} disabled={saving}>
                {saving ? (
                  <>
                    <Loader2 className="me-1.5 h-4 w-4 animate-spin" />
                    در حال ثبت…
                  </>
                ) : (
                  'ثبت گزارش'
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
