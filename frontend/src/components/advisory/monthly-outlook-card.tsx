'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { newDate } from 'date-fns-jalali';
import {
  AlertCircle,
  CalendarDays,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';

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
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { JalaliDatePicker } from '@/components/advisory/study-plan/jalali-date-picker';

/** Jalali months, 1-based (۱ = فروردین … ۱۲ = اسفند). */
export const JALALI_MONTH_LABELS = [
  'فروردین',
  'اردیبهشت',
  'خرداد',
  'تیر',
  'مرداد',
  'شهریور',
  'مهر',
  'آبان',
  'آذر',
  'دی',
  'بهمن',
  'اسفند',
] as const;

/** Wire executors with their Persian labels — rendered from here everywhere. */
export const EXECUTOR_LABELS: Record<MonthlyOutlookExecutor, string> = {
  ADVISOR: 'مشاور',
  STUDENT: 'دانش‌آموز',
};

/** Exactly FOUR strategy slots per month (PDF ص۴). */
const STRATEGY_POSITIONS = [1, 2, 3, 4] as const;

const YEAR_WINDOW_BACK = 3;
const YEAR_WINDOW_FORWARD = 2;

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
 * Gregorian first day of a Jalali month (1-based) as ISO — the wire key.
 * The backend's "month" is ONLY this Gregorian date; the Jalali label is a
 * pure client concern (plan rule ق۵).
 */
export function jalaliMonthStartIso(jYear: number, jMonth: number): string {
  return toIsoDate(newDate(jYear, jMonth - 1, 1));
}

function formatJalaliDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return formatPersianDate(parseIsoDate(iso) ?? iso);
}

type EntryRow = {
  uid: number;
  /** ISO `YYYY-MM-DD`; '' = not picked yet. */
  date: string;
  event: string;
  academicNote: string;
  tasks: string;
};

type StrategySlotState = {
  title: string;
  executor: MonthlyOutlookExecutor;
  body: string;
};

function seedStrategySlots(outlook: MonthlyOutlook): StrategySlotState[] {
  const byPosition = new Map<
    number,
    { title: string; executor: MonthlyOutlookExecutor; body: string }
  >();
  for (const s of outlook.strategies ?? []) {
    byPosition.set(s.position, {
      title: s.title,
      executor: s.executor,
      body: s.body,
    });
  }
  return STRATEGY_POSITIONS.map((position) => {
    const saved = byPosition.get(position);
    return {
      title: saved?.title ?? '',
      executor: saved?.executor ?? 'ADVISOR',
      body: saved?.body ?? '',
    };
  });
}

/**
 * The shared monthly-outlook form body used by BOTH the advisor card and any
 * editable mirror. Seeds ONCE from `initial` (later prop changes never clobber
 * edits in progress); onSave receives the WHOLE set-replace payload with ISO
 * Gregorian dates only.
 */
export function MonthlyOutlookForm({
  monthStart,
  initial,
  saving,
  onSave,
}: {
  monthStart: string;
  initial: MonthlyOutlook;
  saving: boolean;
  onSave: (payload: MonthlyOutlook) => Promise<void>;
}) {
  const [entries, setEntries] = useState<EntryRow[]>(() =>
    (initial.entries ?? []).map((e, index) => ({
      uid: index + 1,
      date: e.date ?? '',
      event: e.event ?? '',
      academicNote: e.academicNote ?? '',
      tasks: e.tasks ?? '',
    })),
  );
  const [strategies, setStrategies] = useState<StrategySlotState[]>(() =>
    seedStrategySlots(initial),
  );

  // uids continue past the seeded rows so addEntry never collides with them.
  const uidCounter = useRef(initial.entries.length);
  const nextUid = () => {
    uidCounter.current += 1;
    return uidCounter.current;
  };

  const updateEntry = (uid: number, patch: Partial<Omit<EntryRow, 'uid'>>) => {
    setEntries((prev) =>
      prev.map((row) => (row.uid === uid ? { ...row, ...patch } : row)),
    );
  };

  const removeEntry = (uid: number) => {
    setEntries((prev) => prev.filter((row) => row.uid !== uid));
  };

  const addEntry = () => {
    setEntries((prev) => [
      ...prev,
      { uid: nextUid(), date: '', event: '', academicNote: '', tasks: '' },
    ]);
  };

  const updateStrategy = (
    index: number,
    patch: Partial<StrategySlotState>,
  ) => {
    setStrategies((prev) =>
      prev.map((slot, i) => (i === index ? { ...slot, ...patch } : slot)),
    );
  };

  /** Client twin of the server's Persian validation; FIRST problem wins. */
  const collectProblem = (): string | null => {
    for (const row of entries) {
      if (!row.date) return 'تاریخ هر ردیف تقویم را انتخاب کنید.';
    }
    const seen = new Set<string>();
    for (const row of entries) {
      if (seen.has(row.date)) {
        return 'برای یک روز بیش از یک ردیف ثبت شده است؛ تاریخ‌های تقویم باید یکتا باشند.';
      }
      seen.add(row.date);
    }
    for (let i = 0; i < strategies.length; i++) {
      if (!strategies[i].title.trim()) {
        return `عنوان استراتژی شمارۀ ${toPersianDigits(i + 1)} را بنویسید.`;
      }
    }
    return null;
  };

  const buildPayload = (): MonthlyOutlook => ({
    monthStart,
    entries: entries.map((row) => ({
      date: row.date,
      event: row.event.trim(),
      academicNote: row.academicNote.trim(),
      tasks: row.tasks.trim(),
    })),
    strategies: strategies.map((slot, index) => ({
      position: index + 1,
      title: slot.title.trim(),
      executor: slot.executor,
      body: slot.body.trim(),
    })),
  });

  const handleSubmit = async () => {
    const problem = collectProblem();
    if (problem) {
      toast.error(problem);
      return;
    }
    await onSave(buildPayload());
  };

  return (
    <div className="space-y-4">
      {/* ── monthly calendar entries ─────────────────────────────────────── */}
      <section className="space-y-2 rounded-xl border border-border/60 p-3">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-sm font-medium">تقویم ماه</h4>
          <Button type="button" variant="outline" size="sm" onClick={addEntry}>
            <Plus className="ml-2 h-4 w-4" />
            افزودن روز
          </Button>
        </div>
        {entries.length === 0 && (
          <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs leading-relaxed text-muted-foreground">
            مناسبت‌ها، تقویم تحصیلی و کارهای مهم روزهای این ماه را اینجا
            ردیف‌به‌ردیف اضافه کنید.
          </p>
        )}
        <ul className="space-y-2">
          {entries.map((row, index) => (
            <li
              key={row.uid}
              className="space-y-2 rounded-lg border border-border/50 p-2"
            >
              <div className="grid grid-cols-[1fr_1fr_2rem] items-start gap-2 sm:grid-cols-[10rem_1fr_1fr_2rem]">
                <JalaliDatePicker
                  value={row.date}
                  onChange={(iso) => updateEntry(row.uid, { date: iso })}
                  placeholder="تاریخ"
                  id={`outlook-entry-date-${row.uid}`}
                />
                <Input
                  value={row.event}
                  onChange={(e) => updateEntry(row.uid, { event: e.target.value })}
                  placeholder="مناسبت"
                  maxLength={120}
                  aria-label={`مناسبت ردیف ${toPersianDigits(index + 1)}`}
                  className="h-9 text-xs"
                />
                <Input
                  value={row.academicNote}
                  onChange={(e) =>
                    updateEntry(row.uid, { academicNote: e.target.value })
                  }
                  placeholder="تقویم تحصیلی"
                  maxLength={200}
                  aria-label={`تقویم تحصیلی ردیف ${toPersianDigits(index + 1)}`}
                  className="h-9 text-xs"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`حذف ردیف ${toPersianDigits(index + 1)}`}
                  className="h-9 w-9 text-muted-foreground hover:text-destructive"
                  onClick={() => removeEntry(row.uid)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              <Textarea
                value={row.tasks}
                onChange={(e) => updateEntry(row.uid, { tasks: e.target.value })}
                rows={2}
                maxLength={2000}
                placeholder="کارها…"
                aria-label={`کارهای ردیف ${toPersianDigits(index + 1)}`}
                className="min-h-[56px] text-xs leading-relaxed"
              />
            </li>
          ))}
        </ul>
      </section>

      {/* ── strategy slots ───────────────────────────────────────────────── */}
      <section className="space-y-2 rounded-xl border border-border/60 p-3">
        <h4 className="text-sm font-medium">استراتژی‌های ماه</h4>
        <p className="text-xs leading-relaxed text-muted-foreground">
          چهار استراتژی این ماه را با مجریِ مشخص بنویسید؛ ذخیره، همۀ اسلات‌ها را
          یکجا جایگزین می‌کند.
        </p>
        <ul className="space-y-2">
          {strategies.map((slot, index) => (
            <li
              key={index}
              className="space-y-2 rounded-lg border border-border/50 p-2"
            >
              <div className="grid grid-cols-[1fr_7rem] items-start gap-2">
                <Input
                  value={slot.title}
                  onChange={(e) =>
                    updateStrategy(index, { title: e.target.value })
                  }
                  placeholder={`عنوان استراتژی ${toPersianDigits(index + 1)}`}
                  maxLength={120}
                  aria-label={`عنوان استراتژی ${toPersianDigits(index + 1)}`}
                  className="h-9 text-xs"
                />
                <Select
                  value={slot.executor}
                  onValueChange={(value) =>
                    updateStrategy(index, {
                      executor: value as MonthlyOutlookExecutor,
                    })
                  }
                >
                  <SelectTrigger
                    aria-label={`مجری استراتژی ${toPersianDigits(index + 1)}`}
                    className="h-9 text-xs"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(
                      Object.keys(EXECUTOR_LABELS) as MonthlyOutlookExecutor[]
                    ).map((executor) => (
                      <SelectItem key={executor} value={executor}>
                        {EXECUTOR_LABELS[executor]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Textarea
                value={slot.body}
                onChange={(e) => updateStrategy(index, { body: e.target.value })}
                rows={2}
                maxLength={5000}
                placeholder="متن استراتژی…"
                aria-label={`متن استراتژی ${toPersianDigits(index + 1)}`}
                className="min-h-[56px] text-xs leading-relaxed"
              />
            </li>
          ))}
        </ul>
      </section>

      {/* ── actions ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-end gap-2 border-t border-border/60 pt-3">
        <Button type="button" onClick={handleSubmit} disabled={saving}>
          {saving && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
          {saving ? 'در حال ذخیره…' : 'ذخیره'}
        </Button>
      </div>
    </div>
  );
}

/**
 * The advisor's per-student «ماه در یک نگاه» card (restart step 8): a Jalali
 * month selector converts to the Gregorian first-day key client-side, then the
 * calendar rows and the four strategy slots save as one wholesale PUT.
 */
export function MonthlyOutlookCard({ engagementId }: { engagementId: number }) {
  const today = getTodayJalali();
  const [jYear, setJYear] = useState(today.year);
  const [jMonth, setJMonth] = useState(today.month);

  const monthStart = useMemo(
    () => jalaliMonthStartIso(jYear, jMonth),
    [jYear, jMonth],
  );

  const yearOptions = useMemo(() => {
    const list: number[] = [];
    for (
      let year = today.year - YEAR_WINDOW_BACK;
      year <= today.year + YEAR_WINDOW_FORWARD;
      year++
    ) {
      list.push(year);
    }
    return list;
  }, [today.year]);

  const [initial, setInitial] = useState<MonthlyOutlook | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setError('');
    setInitial(null);
    AdvisoryService.getMonthlyOutlook(engagementId, monthStart)
      .then((payload) => {
        if (active) setInitial(payload);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId, monthStart, reloadKey]);

  const handleSave = async (payload: MonthlyOutlook) => {
    setSaving(true);
    try {
      await AdvisoryService.putMonthlyOutlook(engagementId, monthStart, payload);
      toast.success('برنامۀ ماه ذخیره شد.');
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'ذخیرۀ برنامۀ ماه ناموفق بود.',
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <CalendarDays className="h-4 w-4 text-primary" />
          </span>
          ماه در یک نگاه
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          تقویم ماه (مناسبت، تقویم تحصیلی، کارها) و چهار استراتژی ماه را ثبت
          کنید؛ دانش‌آموز همین نما را می‌بیند.
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ── Jalali month selector ─────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={String(jMonth)}
            onValueChange={(value) => setJMonth(Number(value))}
          >
            <SelectTrigger aria-label="ماه جلالی" className="h-9 w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {JALALI_MONTH_LABELS.map((label, index) => (
                <SelectItem key={index + 1} value={String(index + 1)}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={String(jYear)}
            onValueChange={(value) => setJYear(Number(value))}
          >
            <SelectTrigger aria-label="سال جلالی" className="h-9 w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {yearOptions.map((year) => (
                <SelectItem key={year} value={String(year)}>
                  {toPersianDigits(year)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-xs tabular-nums text-muted-foreground">
            شروع ماه میلادی: {formatJalaliDate(monthStart)}
          </span>
        </div>

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

        {!initial && !error && (
          <div className="space-y-2" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        )}

        {initial && !error && (
          <MonthlyOutlookForm
            key={`${monthStart}-${reloadKey}`}
            monthStart={monthStart}
            initial={initial}
            saving={saving}
            onSave={handleSave}
          />
        )}
      </CardContent>
    </Card>
  );
}
