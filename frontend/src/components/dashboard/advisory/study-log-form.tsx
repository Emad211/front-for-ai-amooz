'use client';

/**
 * The «گزارش روزانه» tab of the student advisor page — step 5 of the Advisor
 * MVP, extracted from the old standalone /study-log page.
 *
 * One view = one day: mood, per-subject minutes, free note. Saving is a
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
import { DayEnrichmentFields } from '@/components/dashboard/study-log/day-enrichment-fields';
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
import type { StudyLogPayload, StudyPlanOut } from '@/services/advisory-service';
import { StudyTimer } from '@/components/dashboard/advisory/study-timer';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toEnglishDigits, toPersianDigits } from '@/lib/persian-digits';
import { adherenceColorClass, formatAdherence } from '@/lib/adherence';

const MAX_MINUTES_PER_SUBJECT = 960;
const DAY_TOTAL_CAP = 1440;
/** ~85% of the cap: start warning before the hard server limit. */
const DAY_TOTAL_WARNING = 1200;
const NOTE_MAX_LENGTH = 1000;
/** Restart step 1: هدف روز / جمله انگیزشی share this ceiling (server column). */
const ENRICHMENT_TEXT_MAX_LENGTH = 200;
const TEST_PERCENT_MAX = 100;

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

/** The plan running today, else null — same string-compare rule as the
 * dashboard home card so both surfaces always agree on "current". */
function pickCurrentPlan(plans: StudyPlanOut[]): StudyPlanOut | null {
  const today = todayIso();
  return plans.find((p) => p.startDate <= today && today <= p.endDate) ?? null;
}

/** Digits-only, clamped to the per-subject server limit; '' when empty. */
function sanitizeMinutesInput(raw: string): string {
  const digits = toEnglishDigits(raw).replace(/\D/g, '');
  if (!digits) return '';
  return String(Math.min(Number.parseInt(digits, 10), MAX_MINUTES_PER_SUBJECT));
}

/** Digits-only count (تعداد تست); '' when empty. */
function sanitizeCountInput(raw: string): string {
  return toEnglishDigits(raw).replace(/\D/g, '');
}

/** Digits-only, clamped to the 0..100 percent bound; '' when empty. */
function sanitizePercentInput(raw: string): string {
  const digits = sanitizeCountInput(raw);
  if (!digits) return '';
  return String(Math.min(Number.parseInt(digits, 10), TEST_PERCENT_MAX));
}

export function StudyLogForm() {
  const [phase, setPhase] = useState<PagePhase>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [payload, setPayload] = useState<StudyLogPayload | null>(null);

  // Form state — rebuilt from every server response.
  const [selectedDate, setSelectedDate] = useState<string>(todayIso());
  const [mood, setMood] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [minutesBySubject, setMinutesBySubject] = useState<Record<number, string>>({});
  // Restart step 1: the four enrichment inputs hold RAW strings (the numeric
  // ones are digits-sanitized on change); '' means «empty field», which maps
  // to testsTaken=0 / testPercent=null on the wire.
  const [dayGoal, setDayGoal] = useState('');
  const [motivationNote, setMotivationNote] = useState('');
  const [testsTakenRaw, setTestsTakenRaw] = useState('');
  const [testPercentRaw, setTestPercentRaw] = useState('');
  // Research wave (2026-08-31): the day's dominant activity — rides every item
  // of the save payload ('' = plain minutes, the pre-field meaning).
  const [activityType, setActivityType] = useState('');
  const [saving, setSaving] = useState(false);
  // Step 8: adherence of the plan running today; null ⇒ chip is not rendered
  // (quiet-null for students without plans or with nothing elapsed yet).
  const [planPercent, setPlanPercent] = useState<number | null>(null);

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
    // Restart step 1: hydrate the enrichment fields off the stored day.
    setDayGoal(data.log?.dayGoal ?? '');
    setMotivationNote(data.log?.motivationNote ?? '');
    setTestsTakenRaw(data.log && data.log.testsTaken > 0 ? String(data.log.testsTaken) : '');
    setTestPercentRaw(
      data.log && data.log.testPercent !== null ? String(data.log.testPercent) : ''
    );
    setActivityType(
      data.log?.items?.find((item) => item.activityType)?.activityType ?? '',
    );
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

  // Step 8: one best-effort read of the published plans for the adherence
  // chip. Silent on failure — this tab must never block or error over a
  // decorative metric (same quiet rule as the dashboard home card).
  useEffect(() => {
    let active = true;
    AdvisoryService.getMyPlans()
      .then((res) => {
        if (!active) return;
        const current = pickCurrentPlan(
          res.plans.filter((p) => p.status === 'PUBLISHED')
        );
        setPlanPercent(current?.percent ?? null);
      })
      .catch(() => {
        // Quiet by design — see the comment above.
      });
    return () => {
      active = false;
    };
  }, []);

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

  // Client-side validation before submit (restart step 1): the numeric inputs
  // are digits-sanitized on change, so the only reachable failure is a percent
  // above 100 typed before the clamp — guarded here as defense in depth.
  const buildEnrichmentBody = (): { dayGoal: string; motivationNote: string; testsTaken: number; testPercent: number | null } | null => {
    const testsTaken = testsTakenRaw ? Number.parseInt(testsTakenRaw, 10) : 0;
    if (!Number.isFinite(testsTaken) || testsTaken < 0) {
      toast.error('تعداد تست باید عددی بزرگ‌تر یا مساوی صفر باشد.');
      return null;
    }
    if (!testPercentRaw) {
      return { dayGoal, motivationNote, testsTaken, testPercent: null };
    }
    const testPercent = Number.parseInt(testPercentRaw, 10);
    if (!Number.isFinite(testPercent) || testPercent < 0 || testPercent > TEST_PERCENT_MAX) {
      toast.error('درصد آزمون باید عددی بین ۰ تا ۱۰۰ باشد.');
      return null;
    }
    return { dayGoal, motivationNote, testsTaken, testPercent };
  };

  const handleSave = async () => {
    const enrichment = buildEnrichmentBody();
    if (enrichment === null) return;

    setSaving(true);
    try {
      // WHOLE-day payload: only entries with minutes > 0 are sent; an empty
      // array is a valid "cleared day". The day's activity rides every row.
      const items = Object.entries(minutesBySubject)
        .map(([subjectId, raw]) => ({
          subjectId: Number(subjectId),
          minutes: parseMinutes(raw),
          activityType: activityType || undefined,
        }))
        .filter((item) => item.minutes > 0);

      const response = await AdvisoryService.saveMyStudyLog({
        date: selectedDate,
        mood,
        note,
        items,
        ...enrichment,
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
      <div className="space-y-6">
        <Skeleton className="h-10 w-full rounded-xl" />
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-48 w-full rounded-2xl" />
        <Skeleton className="h-36 w-full rounded-2xl" />
      </div>
    );
  }

  if (phase === 'error') {
    return (
      <ErrorState
        title="خطا در بارگذاری گزارش روزانه"
        description={errorMessage}
        onRetry={() => void load(selectedDate)}
      />
    );
  }

  if (phase === 'inactive' || !payload) {
    return (
      <Card className="rounded-2xl">
        <CardContent className="py-12 text-center">
          <p className="text-sm text-muted-foreground md:text-base">
            فعلاً مشاور فعالی نداری؛ وقتی دعوت یک مشاور را بپذیری اینجا فعال می‌شود.
          </p>
        </CardContent>
      </Card>
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
    <div className="space-y-6">
      <StudyLogHeader
        date={selectedDate}
        advisorName={payload.advisorName}
        minDate={payload.minDate}
        maxDate={payload.maxDate}
        onPrevDay={() => handleShiftDay(-1)}
        onNextDay={() => handleShiftDay(1)}
      />

      <StudyTimer
        subjects={payload.subjects.map((s) => ({ subjectId: s.subjectId, name: s.name }))}
        onAddMinutes={(subjectId, minutes) => {
          setMinutesBySubject((prev) => {
            const next = Math.min(
              parseMinutes(prev[subjectId] ?? '') + minutes,
              MAX_MINUTES_PER_SUBJECT,
            );
            return { ...prev, [subjectId]: String(next) };
          });
          toast.success(`${toPersianDigits(minutes)} دقیقه به ${payload.subjects.find((s) => s.subjectId === subjectId)?.name ?? ''} اضافه شد.`);
        }}
      />

      {/* Step 8: adherence of the plan running today; renders nothing when
      there is no current plan or nothing has elapsed yet (quiet-null). */}
      {planPercent !== null && (
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium tabular-nums ${adherenceColorClass(planPercent)}`}
          >
            پایبندی برنامه جاری: {formatAdherence(planPercent)}
          </span>
        </div>
      )}

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
          <CardTitle className="text-base">هدف و آزمون امروز</CardTitle>
          <CardDescription>هدف‌گذاری، جمله انگیزشی و نتیجهٔ آزمون‌های امروزت را ثبت کن.</CardDescription>
        </CardHeader>
        <CardContent>
          <DayEnrichmentFields
            dayGoal={dayGoal}
            motivationNote={motivationNote}
            testsTaken={testsTakenRaw}
            testPercent={testPercentRaw}
            onDayGoalChange={(value) => setDayGoal(value.slice(0, ENRICHMENT_TEXT_MAX_LENGTH))}
            onMotivationNoteChange={(value) => setMotivationNote(value.slice(0, ENRICHMENT_TEXT_MAX_LENGTH))}
            onTestsTakenChange={(value) => setTestsTakenRaw(sanitizeCountInput(value))}
            onTestPercentChange={(value) => setTestPercentRaw(sanitizePercentInput(value))}
            disabled={saving}
          />
        </CardContent>
      </Card>

      <Card className="rounded-2xl">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">دقایق مطالعه به تفکیک درس</CardTitle>
            <div className="flex items-center gap-2">
              <Select value={activityType || 'plain'} onValueChange={setActivityType}>
                <SelectTrigger className="h-8 w-36 text-xs" aria-label="نوع مطالعه">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="plain">ثبت ساده</SelectItem>
                  <SelectItem value="LESSON">درسنامه</SelectItem>
                  <SelectItem value="EDU_TEST">تست آموزشی</SelectItem>
                  <SelectItem value="TIMED_TEST">تست زمان‌دار</SelectItem>
                  <SelectItem value="REVIEW">مرور</SelectItem>
                  <SelectItem value="SUMMARY">خلاصه‌نویسی</SelectItem>
                </SelectContent>
              </Select>
              <span className={`text-sm font-semibold ${totalTone}`}>
                مجموع امروز: {toPersianDigits(totalMinutes)} دقیقه
              </span>
            </div>
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
  );
}
