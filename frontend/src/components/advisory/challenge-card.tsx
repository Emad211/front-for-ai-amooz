'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Loader2,
  Plus,
  RefreshCw,
  Target,
  Trash2,
  XCircle,
} from 'lucide-react';

import {
  AdvisoryService,
  type Challenge,
  type ChallengeDay,
  type ChallengeStatus,
  type CreateChallengeBody,
} from '@/services/advisory-service';
import { formatPersianDate } from '@/lib/date-utils';
import { toPersianDigits } from '@/lib/persian-digits';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import { JalaliDatePicker } from '@/components/advisory/jalali-date-picker';

/** Wire statuses with their Persian labels — rendered from here everywhere. */
export const CHALLENGE_STATUS_LABELS: Record<ChallengeStatus, string> = {
  ACTIVE: 'فعال',
  DONE: 'پایان‌یافته',
  CANCELLED: 'لغوشده',
};

/** Color-coded badge classes per status (green / gray / red). */
export const CHALLENGE_STATUS_BADGE_CLASSES: Record<ChallengeStatus, string> = {
  ACTIVE:
    'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  DONE: 'border-border bg-muted text-muted-foreground',
  CANCELLED: 'border-destructive/40 bg-destructive/10 text-destructive',
};

/** Solid dot color for the compact status dot+word indicator (green/gray/red). */
const CHALLENGE_STATUS_DOT_CLASSES: Record<ChallengeStatus, string> = {
  ACTIVE: 'bg-emerald-500',
  DONE: 'bg-muted-foreground/40',
  CANCELLED: 'bg-destructive',
};

/** Server-enforced cap (`MAX_ACTIVE_CHALLENGES`); mirrored for the hint copy. */
const MAX_ACTIVE_CHALLENGES = 3;
const DAYS_PER_CHALLENGE = 7;

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

function formatJalaliDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return formatPersianDate(parseIsoDate(iso) ?? iso);
}

/** Absolute ISO date of day N of a challenge (`startDate + N - 1`). */
function challengeDayIso(startDate: string, dayNumber: number): string | null {
  const base = parseIsoDate(startDate);
  if (!base) return null;
  return toIsoDate(
    new Date(base.getFullYear(), base.getMonth(), base.getDate() + dayNumber - 1),
  );
}

function seedDays(challenge: Challenge): ChallengeDay[] {
  return Array.from({ length: DAYS_PER_CHALLENGE }, (_, i) => {
    const found = (challenge.days ?? []).find((d) => d.dayNumber === i + 1);
    return {
      dayNumber: i + 1,
      goal: found?.goal ?? '',
      summary: found?.summary ?? '',
    };
  });
}

/** Days carrying any goal/summary content — drives the «N/7 ثبت‌شده» counters. */
function countFilledDays(challenge: Challenge): number {
  return (challenge.days ?? []).filter(
    (day) => day.goal.trim() || day.summary.trim(),
  ).length;
}

/**
 * Create form of one challenge. `endDate` is deliberately absent — deriving
 * `startDate + 6` is the server's job; the client never sends it.
 */
function ChallengeCreateForm({
  creating,
  onCreate,
}: {
  creating: boolean;
  onCreate: (body: CreateChallengeBody) => Promise<void>;
}) {
  const [title, setTitle] = useState('');
  const [goalText, setGoalText] = useState('');
  const [dailyRoutine, setDailyRoutine] = useState('');
  const [executionNote, setExecutionNote] = useState('');
  const [observer, setObserver] = useState('');
  const [problemTarget, setProblemTarget] = useState('');
  /** ISO `YYYY-MM-DD`; '' = not picked yet. */
  const [startDate, setStartDate] = useState('');

  const handleSubmit = async () => {
    if (!title.trim()) {
      toast.error('عنوان چالش را بنویسید.');
      return;
    }
    if (!startDate) {
      toast.error('تاریخ شروع چالش را انتخاب کنید.');
      return;
    }
    await onCreate({
      title: title.trim(),
      goalText: goalText.trim(),
      dailyRoutine: dailyRoutine.trim(),
      executionNote: executionNote.trim(),
      observer: observer.trim(),
      problemTarget: problemTarget.trim(),
      startDate,
    });
  };

  return (
    <div className="space-y-4 rounded-xl border border-border/40 p-4">
      <p className="text-sm font-medium">چالش جدید</p>
      <div className="grid grid-cols-1 gap-x-3 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-1.5 lg:col-span-2">
          <label
            htmlFor="challenge-title"
            className="text-[11px] font-medium text-muted-foreground"
          >
            عنوان چالش
          </label>
          <Input
            id="challenge-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={120}
            placeholder="مثلاً هفت روز بدون فضای مجازی"
            className="h-9 w-full rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor="challenge-start"
            className="text-[11px] font-medium text-muted-foreground"
          >
            تاریخ شروع
          </label>
          <JalaliDatePicker
            id="challenge-start"
            value={startDate}
            onChange={(iso) => setStartDate(iso)}
            placeholder="روز آغاز را انتخاب کنید"
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2 lg:col-span-3">
          <label
            htmlFor="challenge-goal"
            className="text-[11px] font-medium text-muted-foreground"
          >
            هدف و تعریف
          </label>
          <Textarea
            id="challenge-goal"
            value={goalText}
            onChange={(e) => setGoalText(e.target.value)}
            rows={3}
            maxLength={2000}
            placeholder="این چالش دقیقاً چیست و چه هدفی دارد؟"
            className="min-h-[60px] text-sm leading-relaxed"
          />
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor="challenge-routine"
            className="text-[11px] font-medium text-muted-foreground"
          >
            روتین روزانه
          </label>
          <Input
            id="challenge-routine"
            value={dailyRoutine}
            onChange={(e) => setDailyRoutine(e.target.value)}
            maxLength={200}
            placeholder="مثلاً هر شب ۲۰ صفحه کتاب"
            className="h-9 w-full rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor="challenge-execution"
            className="text-[11px] font-medium text-muted-foreground"
          >
            نوع اجرا
          </label>
          <Input
            id="challenge-execution"
            value={executionNote}
            onChange={(e) => setExecutionNote(e.target.value)}
            maxLength={200}
            placeholder="مثلاً فردی و مستمر"
            className="h-9 w-full rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <label
            htmlFor="challenge-observer"
            className="text-[11px] font-medium text-muted-foreground"
          >
            مجری و ناظر
          </label>
          <Input
            id="challenge-observer"
            value={observer}
            onChange={(e) => setObserver(e.target.value)}
            maxLength={120}
            placeholder="مثلاً دانش‌آموز — ناظر: مشاور"
            className="h-9 w-full rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2 lg:col-span-3">
          <label
            htmlFor="challenge-problem"
            className="text-[11px] font-medium text-muted-foreground"
          >
            مشکل و نتیجهٔ مدنظر
          </label>
          <Textarea
            id="challenge-problem"
            value={problemTarget}
            onChange={(e) => setProblemTarget(e.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="کدام مشکل حل شود و در پایان به کجا برسد؟"
            className="min-h-[60px] text-sm leading-relaxed"
          />
        </div>
      </div>
      <div className="flex justify-start border-t border-border/40 pt-3">
        <Button
          type="button"
          size="sm"
          className="h-9 px-4"
          onClick={handleSubmit}
          disabled={creating}
        >
          {creating && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
          {creating ? 'در حال ذخیره…' : 'ساخت چالش'}
        </Button>
      </div>
    </div>
  );
}

/**
 * The 7-day editor of one ACTIVE challenge (advisor side — every field
 * writable), collapsed by default behind an accordion. Each day is ONE compact
 * inline row (goal + summary inputs); days whose absolute date is in the
 * future render dimmed with disabled inputs — a day can only be filled once
 * it has arrived. The whole set is saved as one PUT.
 */
function ChallengeDaysEditor({
  engagementId,
  challenge,
}: {
  engagementId: number;
  challenge: Challenge;
}) {
  const [rows, setRows] = useState<ChallengeDay[]>(() => seedDays(challenge));
  const [saving, setSaving] = useState(false);

  /** Today as ISO, so ISO strings compare lexicographically against day dates. */
  const todayIso = toIsoDate(new Date());
  const filledCount = countFilledDays(challenge);

  const updateRow = (
    dayNumber: number,
    patch: Partial<Omit<ChallengeDay, 'dayNumber'>>,
  ) => {
    setRows((prev) =>
      prev.map((row) =>
        row.dayNumber === dayNumber ? { ...row, ...patch } : row,
      ),
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const savedDays = await AdvisoryService.putAdvisorDays(
        engagementId,
        challenge.id,
        rows,
      );
      if (savedDays.length > 0) {
        setRows(seedDays({ ...challenge, days: savedDays }));
      }
      toast.success('روزهای چالش ذخیره شد.');
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'ذخیرۀ روزهای چالش ناموفق بود.',
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <details className="group rounded-xl border border-border/40">
      <summary className="flex cursor-pointer select-none items-center justify-between gap-2 px-3 py-2.5 text-sm font-medium transition-colors hover:text-foreground">
        <span className="flex items-center gap-2">
          روزها
          <Badge variant="secondary" className="text-[11px] font-normal">
            {toPersianDigits(filledCount)}/{toPersianDigits(DAYS_PER_CHALLENGE)}{' '}
            ثبت‌شده
          </Badge>
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border/40 px-3 py-1">
        <div className="divide-y divide-border/40">
          {rows.map((row) => {
            const dayIso = challengeDayIso(challenge.startDate, row.dayNumber);
            const isFuture = Boolean(dayIso && dayIso > todayIso);
            return (
              <div
                key={row.dayNumber}
                className={cn(
                  'flex flex-wrap items-center gap-2 py-1.5',
                  isFuture && 'opacity-50',
                )}
              >
                <Badge
                  variant="secondary"
                  className="w-10 shrink-0 justify-center px-0 text-center text-[11px]"
                >
                  روز {toPersianDigits(row.dayNumber)}
                </Badge>
                <Input
                  value={row.goal}
                  onChange={(e) =>
                    updateRow(row.dayNumber, { goal: e.target.value })
                  }
                  placeholder={`هدف‌گذاری روز ${toPersianDigits(row.dayNumber)}`}
                  maxLength={200}
                  aria-label={`هدف روز ${toPersianDigits(row.dayNumber)}`}
                  disabled={isFuture}
                  className="h-8 basis-44 flex-1 rounded-lg text-xs"
                />
                <Input
                  value={row.summary}
                  onChange={(e) =>
                    updateRow(row.dayNumber, { summary: e.target.value })
                  }
                  placeholder="خلاصۀ کارها، مشکلات و نتیجه…"
                  maxLength={5000}
                  aria-label={`خلاصۀ روز ${toPersianDigits(row.dayNumber)}`}
                  disabled={isFuture}
                  className="h-8 basis-44 flex-1 rounded-lg text-xs"
                />
              </div>
            );
          })}
        </div>
        <div className="flex justify-start border-t border-border/40 py-2">
          <Button
            type="button"
            size="sm"
            className="h-9 px-4"
            onClick={handleSave}
            disabled={saving}
          >
            {saving && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
            {saving ? 'در حال ذخیره…' : 'ذخیرۀ روزها'}
          </Button>
        </div>
      </div>
    </details>
  );
}

/**
 * Read-only days recap of a terminal (DONE/CANCELLED) challenge: a muted
 * collapsed accordion whose header IS the summary line («۵ از ۷ روز ثبت
 * شده»); expanding lists only the days that actually carry content.
 */
function ChallengeDaysRecap({ challenge }: { challenge: Challenge }) {
  const filledCount = countFilledDays(challenge);
  const filledDays = (challenge.days ?? []).filter(
    (day) => day.goal.trim() || day.summary.trim(),
  );

  return (
    <details className="group rounded-xl border border-border/40">
      <summary className="flex cursor-pointer select-none items-center justify-between gap-2 px-3 py-2 text-xs text-muted-foreground transition-colors hover:text-foreground">
        <span>
          {toPersianDigits(filledCount)} از{' '}
          {toPersianDigits(DAYS_PER_CHALLENGE)} روز ثبت شده
        </span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border/40 px-3 py-1">
        {filledDays.length === 0 ? (
          <p className="py-2 text-center text-xs text-muted-foreground">
            هنوز روزی ثبت نشده است.
          </p>
        ) : (
          <div className="divide-y divide-border/40">
            {filledDays.map((day) => (
              <div
                key={day.dayNumber}
                className="flex items-start gap-2 py-1.5 text-xs"
              >
                <Badge
                  variant="secondary"
                  className="w-10 shrink-0 justify-center px-0 text-center text-[11px]"
                >
                  روز {toPersianDigits(day.dayNumber)}
                </Badge>
                <div className="min-w-0 flex-1 space-y-0.5">
                  {day.goal.trim() && (
                    <p className="leading-relaxed">{day.goal}</p>
                  )}
                  {day.summary.trim() && (
                    <p className="leading-relaxed text-muted-foreground">
                      {day.summary}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}

type PendingAction = {
  challenge: Challenge;
  kind: 'DONE' | 'CANCELLED' | 'DELETE';
};

const ACTION_COPY: Record<
  PendingAction['kind'],
  { title: string; description: string; confirm: string }
> = {
  DONE: {
    title: 'پایان چالش',
    description:
      'چالش به وضعیت «پایان‌یافته» می‌رود و دیگر قابل ویرایش نیست؛ این کار برگشت‌پذیر نیست.',
    confirm: 'پایان چالش',
  },
  CANCELLED: {
    title: 'لغو چالش',
    description:
      'چالش به وضعیت «لغوشده» می‌رود و دیگر قابل ویرایش نیست؛ این کار برگشت‌پذیر نیست.',
    confirm: 'لغو چالش',
  },
  DELETE: {
    title: 'حذف چالش',
    description:
      'این چالش همراه با همۀ روزهایش برای همیشه حذف می‌شود و برگشت‌پذیر نیست.',
    confirm: 'حذف',
  },
};

/**
 * The advisor's challenges card («چالش ۷ روزه», restart step 9): create form
 * (collapsed behind the «چالش جدید» toggle; auto-expanded while the list is
 * empty), compact challenge blocks with a one-row header (title + status dot +
 * date range + actions), per-challenge days accordion for ACTIVE ones, a
 * read-only recap for terminal ones, and پایان/لغو/حذف actions behind
 * confirms. The three-ACTIVE cap error arrives as the server's Persian detail
 * and surfaces verbatim via toast.
 */
export function ChallengeCard({ engagementId }: { engagementId: number }) {
  const [challenges, setChallenges] = useState<Challenge[] | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const [creating, setCreating] = useState(false);
  const [createFormOpen, setCreateFormOpen] = useState(false);

  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [acting, setActing] = useState(false);

  useEffect(() => {
    let active = true;
    setError('');
    setChallenges(null);
    AdvisoryService.getChallenges(engagementId)
      .then((list) => {
        if (active) setChallenges(list);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId, reloadKey]);

  const refetch = () => {
    AdvisoryService.getChallenges(engagementId)
      .then((list) => setChallenges(list))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
  };

  const handleCreate = async (body: CreateChallengeBody) => {
    setCreating(true);
    try {
      await AdvisoryService.createChallenge(engagementId, body);
      toast.success('چالش ساخته شد.');
      setCreateFormOpen(false);
      refetch();
    } catch (err: unknown) {
      // Includes the cap message («حداکثر ۳ چالش فعال…») verbatim.
      toast.error(err instanceof Error ? err.message : 'ساخت چالش ناموفق بود.');
    } finally {
      setCreating(false);
    }
  };

  const handleConfirmed = async () => {
    const target = pendingAction;
    if (!target) return;
    setActing(true);
    try {
      if (target.kind === 'DELETE') {
        await AdvisoryService.deleteChallenge(engagementId, target.challenge.id);
        toast.success('چالش حذف شد.');
      } else {
        await AdvisoryService.patchChallenge(engagementId, target.challenge.id, {
          status: target.kind,
        });
        toast.success('وضعیت چالش به‌روزرسانی شد.');
      }
      setPendingAction(null);
      refetch();
    } catch (err: unknown) {
      // A terminal→ACTIVE flip attempt answers 409 here; detail is verbatim.
      toast.error(err instanceof Error ? err.message : 'عملیات ناموفق بود.');
    } finally {
      setActing(false);
    }
  };

  const loading = challenges === null && !error;

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="p-5 pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Target className="h-4 w-4 text-primary" />
            چالش هفت‌روزه
          </CardTitle>
          {/* Hidden once the list is confirmed empty — the form then stands
          open on its own and a collapse toggle would be a dead control. */}
          {(challenges === null || (challenges ?? []).length > 0) && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setCreateFormOpen((open) => !open)}
            >
              {createFormOpen ? (
                'بستن فرم'
              ) : (
                <>
                  <Plus className="ml-2 h-4 w-4" />
                  چالش جدید
                </>
              )}
            </Button>
          )}
        </div>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          چالشی هفت‌روزه بسازید تا دانش‌آموز روزبه‌روز آن را پر کند؛ حداکثر{' '}
          {toPersianDigits(MAX_ACTIVE_CHALLENGES)} چالش فعال همزمان می‌توانید داشته باشید.
        </p>
      </CardHeader>

      <CardContent className="space-y-4 p-5 pt-0">
        {error && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
            <p className="flex items-center gap-2 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {error}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReloadKey((k) => k + 1)}
            >
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

        {!error && !loading && (challenges ?? []).length === 0 && (
          <p className="text-center text-xs leading-relaxed text-muted-foreground">
            هنوز چالی ساخته نشده است. یک هدف هفت‌روزهٔ مشخص برای دانش‌آموز
            تعریف کنید.
          </p>
        )}

        {/* Auto-expanded while there is nothing else on the card. */}
        {!error &&
          !loading &&
          (createFormOpen || (challenges ?? []).length === 0) && (
            <ChallengeCreateForm creating={creating} onCreate={handleCreate} />
          )}

        {!error &&
          (challenges ?? []).map((challenge) => (
            <article
              key={challenge.id}
              className="space-y-3 rounded-xl border border-border/40 p-4"
            >
              {/* One-row header: title · status · date range · actions. */}
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <h3 className="min-w-0 flex-1 basis-52 truncate text-sm font-semibold">
                  {challenge.title || 'بدون عنوان'}
                </h3>
                <span className="flex shrink-0 items-center gap-1.5 text-xs">
                  <span
                    aria-hidden="true"
                    className={cn(
                      'h-1.5 w-1.5 rounded-full',
                      CHALLENGE_STATUS_DOT_CLASSES[challenge.status],
                    )}
                  />
                  <span
                    className={cn(
                      challenge.status === 'DONE' && 'text-muted-foreground',
                    )}
                  >
                    {CHALLENGE_STATUS_LABELS[challenge.status]}
                  </span>
                </span>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {formatJalaliDate(challenge.startDate)}
                  <span aria-hidden="true"> تا </span>
                  {formatJalaliDate(challenge.endDate)}
                </span>
                <div className="ms-auto flex shrink-0 items-center gap-1.5">
                  {challenge.status === 'ACTIVE' && (
                    <>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-8 px-2.5 text-xs"
                        disabled={pendingAction !== null}
                        onClick={() =>
                          setPendingAction({ challenge, kind: 'DONE' })
                        }
                      >
                        <CheckCircle2 className="ml-1.5 h-3.5 w-3.5" />
                        پایان
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-8 px-2.5 text-xs text-destructive hover:text-destructive"
                        disabled={pendingAction !== null}
                        onClick={() =>
                          setPendingAction({ challenge, kind: 'CANCELLED' })
                        }
                      >
                        <XCircle className="ml-1.5 h-3.5 w-3.5" />
                        لغو
                      </Button>
                    </>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="حذف چالش"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    disabled={pendingAction !== null}
                    onClick={() =>
                      setPendingAction({ challenge, kind: 'DELETE' })
                    }
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              {challenge.goalText.trim() && (
                <p className="whitespace-pre-line text-sm leading-relaxed">
                  {challenge.goalText}
                </p>
              )}

              {(challenge.dailyRoutine.trim() ||
                challenge.executionNote.trim() ||
                challenge.observer.trim()) && (
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  {challenge.dailyRoutine.trim() && (
                    <span>روتین: {challenge.dailyRoutine}</span>
                  )}
                  {challenge.executionNote.trim() && (
                    <>
                      <span aria-hidden="true">·</span>
                      <span>اجرا: {challenge.executionNote}</span>
                    </>
                  )}
                  {challenge.observer.trim() && (
                    <>
                      <span aria-hidden="true">·</span>
                      <span>{challenge.observer}</span>
                    </>
                  )}
                </p>
              )}

              {challenge.problemTarget.trim() && (
                <p className="whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
                  {challenge.problemTarget}
                </p>
              )}

              {challenge.status === 'ACTIVE' ? (
                <ChallengeDaysEditor
                  engagementId={engagementId}
                  challenge={challenge}
                />
              ) : (
                <ChallengeDaysRecap challenge={challenge} />
              )}
            </article>
          ))}
      </CardContent>

      {/* ── action confirmation ─────────────────────────────────────────── */}
      <AlertDialog
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null);
        }}
      >
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pendingAction ? ACTION_COPY[pendingAction.kind].title : ''}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pendingAction ? ACTION_COPY[pendingAction.kind].description : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={acting}>انصراف</AlertDialogCancel>
            <AlertDialogAction
              className={cn(
                pendingAction?.kind === 'DONE'
                  ? ''
                  : 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
              )}
              disabled={acting}
              onClick={(e) => {
                e.preventDefault();
                handleConfirmed();
              }}
            >
              {acting && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
              {acting
                ? 'در حال انجام…'
                : pendingAction
                  ? ACTION_COPY[pendingAction.kind].confirm
                  : ''}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
