'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertCircle,
  ClipboardList,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  Undo2,
} from 'lucide-react';

import {
  AdvisoryService,
  type SaveStudyPlanDraftBody,
  type StudyPlanOut,
} from '@/services/advisory-service';
import { toEnglishDigits, toPersianDigits } from '@/lib/persian-digits';
import { adherenceColorClass, formatAdherence } from '@/lib/adherence';
import { formatPersianDate } from '@/lib/date-utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { JalaliDatePicker } from './jalali-date-picker';

/** Preset horizons plus «دلخواه»; the wire only ever receives a plain count. */
type DurationMode = '7' | '14' | '30' | 'custom';

/** One editable row. `minutes` stays a raw string so half-typed Persian-digit
 * input never fights the cursor; it is parsed (and rejected) on save. */
type PlannerRow = {
  uid: number;
  /** 0-based on the wire; the UI shows «روز N» where N = dayOffset + 1. */
  dayOffset: number;
  subjectId: number | null;
  minutes: string;
};

type ActiveSubject = {
  id: number;
  name: string;
};

type StudyPlannerCardProps = {
  engagementId: number;
  studentName: string;
  /** Engagement start (ISO) — the inclusive lower bound for the start date. */
  startedOn: string | null;
};

function parseDuration(raw: string): number | null {
  if (!/^\d+$/.test(raw)) return null;
  const value = Number(raw);
  if (value < 1 || value > 90) return null;
  return value;
}

/**
 * The advisor's authoring surface for one student's study plans («برنامه‌ریزی»).
 *
 * One DRAFT slot exists per engagement (server-side partial unique), so the
 * editor is a single form: it prefills from the current draft on load, and
 * «ذخیره پیش‌نویس» upserts it wholesale. «انتشار» persists the latest edits
 * first and only then flips the slot to PUBLISHED — publishing an unsaved edit
 * would otherwise surprise the advisor with either a 404 or a stale plan.
 * Client-side checks mirror §14.3's server order so common mistakes fail fast
 * with the same Persian wording the server would answer with.
 */
export function StudyPlannerCard({
  engagementId,
  studentName,
  startedOn,
}: StudyPlannerCardProps) {
  const [subjects, setSubjects] = useState<ActiveSubject[] | null>(null);
  const [subjectsError, setSubjectsError] = useState('');
  const [plans, setPlans] = useState<StudyPlanOut[] | null>(null);
  const [plansError, setPlansError] = useState('');

  const [startDate, setStartDate] = useState('');
  const [durationMode, setDurationMode] = useState<DurationMode>('7');
  const [customDuration, setCustomDuration] = useState('');
  const [rows, setRows] = useState<PlannerRow[]>([]);

  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [busyPlanId, setBusyPlanId] = useState<number | null>(null);

  const uidCounter = useRef(0);
  // The draft prefills the editor exactly once — later refetches (after save /
  // publish / unpublish) must never clobber edits in progress.
  const draftPrefilled = useRef(false);

  const nextUid = () => {
    uidCounter.current += 1;
    return uidCounter.current;
  };

  const loadSubjects = useCallback(() => {
    let active = true;
    setSubjectsError('');
    setSubjects(null);
    AdvisoryService.getEngagementSubjects(engagementId)
      .then((resp) => {
        if (!active) return;
        const selectedIds = new Set(resp.selectedSubjectIds);
        // Only ACTIVE selections may be planned; the derived curriculum lists
        // candidates, `selectedSubjectIds` marks what is actually focusable.
        setSubjects(
          resp.subjects
            .filter((s) => selectedIds.has(s.id))
            .map((s) => ({ id: s.id, name: s.name })),
        );
      })
      .catch((err: unknown) => {
        if (active) setSubjectsError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId]);

  const loadPlans = useCallback(() => {
    let active = true;
    setPlansError('');
    AdvisoryService.getStudentPlans(engagementId)
      .then((data) => {
        if (!active) return;
        setPlans(data);
        if (!draftPrefilled.current) {
          const draft = data.find((p) => p.status === 'DRAFT');
          if (draft) {
            draftPrefilled.current = true;
            setStartDate(draft.startDate);
            if (
              draft.durationDays === 7 ||
              draft.durationDays === 14 ||
              draft.durationDays === 30
            ) {
              setDurationMode(String(draft.durationDays) as DurationMode);
            } else {
              setDurationMode('custom');
              setCustomDuration(String(draft.durationDays));
            }
            setRows(
              draft.items.map((item) => ({
                uid: nextUid(),
                dayOffset: item.dayOffset,
                subjectId: item.subjectId,
                minutes: String(item.plannedMinutes),
              })),
            );
          }
        }
      })
      .catch((err: unknown) => {
        if (active) setPlansError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId]);

  useEffect(() => loadSubjects(), [loadSubjects]);
  useEffect(() => loadPlans(), [loadPlans]);

  const durationDays =
    durationMode === 'custom'
      ? parseDuration(toEnglishDigits(customDuration))
      : Number(durationMode);

  // Shrinking the horizon strands rows beyond it — drop them immediately so the
  // editor can never hold a body the server would reject («روز N خارج از طول…»).
  useEffect(() => {
    if (durationDays === null) return;
    setRows((prev) =>
      prev.some((row) => row.dayOffset >= durationDays)
        ? prev.filter((row) => row.dayOffset < durationDays)
        : prev,
    );
  }, [durationDays]);

  const plannedTotal = rows.reduce((sum, row) => {
    const minutes = Number(toEnglishDigits(row.minutes));
    return sum + (Number.isInteger(minutes) && minutes > 0 ? minutes : 0);
  }, 0);

  const collectProblem = (forPublish: boolean): string | null => {
    if (!startDate) return 'تاریخ شروع را انتخاب کنید.';
    if (startedOn && startDate < startedOn) {
      return 'تاریخ شروع نمی‌تواند پیش از شروع همکاری باشد.';
    }
    if (durationDays === null) return 'طول برنامه باید بین ۱ و ۹۰ روز باشد.';
    if (rows.length === 0) {
      return forPublish ? 'برنامهٔ خالی قابل انتشار نیست.' : 'حداقل یک ردیف به برنامه اضافه کنید.';
    }
    for (const row of rows) {
      if (row.subjectId === null) return 'درسِ همه‌ی ردیف‌ها را انتخاب کنید.';
      const minutes = Number(toEnglishDigits(row.minutes));
      if (!Number.isInteger(minutes) || minutes < 1 || minutes > 960) {
        return 'دقیقه‌ی هر ردیف باید عددی بین ۱ و ۹۶۰ باشد.';
      }
      if (row.dayOffset >= durationDays) {
        return `روز ${toPersianDigits(row.dayOffset + 1)} خارج از طول برنامه است.`;
      }
    }
    const seen = new Set<string>();
    for (const row of rows) {
      const key = `${row.dayOffset}:${row.subjectId}`;
      if (seen.has(key)) return 'برای هر روز و درس فقط یک ردیف بفرستید.';
      seen.add(key);
    }
    return null;
  };

  const buildBody = (): SaveStudyPlanDraftBody => {
    // Only reachable after collectProblem() passed, so every field narrows.
    const items: SaveStudyPlanDraftBody['items'] = [];
    for (const row of rows) {
      const subjectId = row.subjectId;
      const minutes = Number(toEnglishDigits(row.minutes));
      if (subjectId === null || !Number.isInteger(minutes)) continue;
      items.push({ dayOffset: row.dayOffset, subjectId, plannedMinutes: minutes });
    }
    items.sort((a, b) => a.dayOffset - b.dayOffset || a.subjectId - b.subjectId);
    return { startDate, durationDays: durationDays ?? 0, items };
  };

  const refetchPlans = () => {
    AdvisoryService.getStudentPlans(engagementId)
      .then((data) => setPlans(data))
      .catch((err: unknown) => {
        setPlansError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
  };

  const handleSave = async () => {
    const problem = collectProblem(false);
    if (problem) {
      toast.error(problem);
      return;
    }
    setSaving(true);
    try {
      await AdvisoryService.savePlanDraft(engagementId, buildBody());
      toast.success('پیش‌نویس برنامه ذخیره شد.');
      refetchPlans();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'ذخیره‌ی پیش‌نویس ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    const problem = collectProblem(true);
    if (problem) {
      toast.error(problem);
      return;
    }
    setPublishing(true);
    try {
      // Persist the latest edits first: publish validates the STORED draft, so
      // skipping this step would publish something the advisor just changed.
      await AdvisoryService.savePlanDraft(engagementId, buildBody());
      await AdvisoryService.publishPlanDraft(engagementId);
      toast.success(`برنامه برای «${studentName}» منتشر شد.`);
      refetchPlans();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'انتشار برنامه ناموفق بود.');
    } finally {
      setPublishing(false);
    }
  };

  const handleUnpublish = async (planId: number) => {
    setBusyPlanId(planId);
    try {
      await AdvisoryService.unpublishPlan(engagementId, planId);
      toast.success('انتشار برنامه لغو شد و به پیش‌نویس برگشت.');
      refetchPlans();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'لغو انتشار ناموفق بود.');
    } finally {
      setBusyPlanId(null);
    }
  };

  const addRow = () => {
    setRows((prev) => [
      ...prev,
      { uid: nextUid(), dayOffset: 0, subjectId: null, minutes: '' },
    ]);
  };

  const updateRow = (uid: number, patch: Partial<Omit<PlannerRow, 'uid'>>) => {
    setRows((prev) => prev.map((row) => (row.uid === uid ? { ...row, ...patch } : row)));
  };

  const removeRow = (uid: number) => {
    setRows((prev) => prev.filter((row) => row.uid !== uid));
  };

  const busy = saving || publishing;

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <ClipboardList className="h-4 w-4 text-primary" />
          </span>
          برنامه‌ریزی مطالعه
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          بازه‌ای دلخواه تعیین کنید و برای هر روز، درس و دقیقه‌ی مطالعه بگذارید.
          انتشار، آخرین تغییرات را ذخیره و برنامه را برای دانش‌آموز نمایان می‌کند.
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ── horizon: start date + duration ─────────────────────────────── */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="study-plan-start" className="text-xs font-medium text-muted-foreground">
              تاریخ شروع
            </label>
            <JalaliDatePicker
              id="study-plan-start"
              value={startDate}
              onChange={setStartDate}
              minDate={startedOn}
            />
          </div>
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">طول برنامه</span>
            <div className="flex flex-wrap items-center gap-1.5">
              {(['7', '14', '30'] as const).map((value) => (
                <Button
                  key={value}
                  type="button"
                  variant={durationMode === value ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setDurationMode(value)}
                  aria-pressed={durationMode === value}
                  className="h-9 rounded-full px-3"
                >
                  {toPersianDigits(value)} روز
                </Button>
              ))}
              <Button
                type="button"
                variant={durationMode === 'custom' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setDurationMode('custom')}
                aria-pressed={durationMode === 'custom'}
                className="h-9 rounded-full px-3"
              >
                دلخواه
              </Button>
              {durationMode === 'custom' && (
                <Input
                  value={customDuration}
                  onChange={(e) => setCustomDuration(e.target.value)}
                  placeholder="۱ تا ۹۰"
                  inputMode="numeric"
                  aria-label="طول دلخواه برنامه بر حسب روز"
                  className="h-9 w-24"
                />
              )}
            </div>
          </div>
        </div>

        {/* ── rows editor ────────────────────────────────────────────────── */}
        <div className="space-y-2 rounded-xl border border-border/60 p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">ردیف‌های برنامه</span>
            <span className="text-xs tabular-nums text-muted-foreground">
              مجموع برنامه‌ریزی‌شده: {toPersianDigits(plannedTotal)} دقیقه
            </span>
          </div>

          {subjectsError && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
              <p className="flex items-center gap-2 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                {subjectsError}
              </p>
              <Button variant="outline" size="sm" onClick={loadSubjects}>
                <RefreshCw className="ml-2 h-3.5 w-3.5" />
                تلاش مجدد
              </Button>
            </div>
          )}

          {!subjects && !subjectsError && (
            <div className="space-y-1.5" aria-busy="true">
              {[0, 1].map((i) => (
                <Skeleton key={i} className="h-10 w-full rounded-lg" />
              ))}
            </div>
          )}

          {subjects && subjects.length === 0 && (
            <p className="rounded-lg border border-dashed px-3 py-6 text-center text-xs leading-relaxed text-muted-foreground">
              هنوز درسی برای این دانش‌آموز انتخاب نشده است. ابتدا از فهرست
              دانش‌آموزان، با دکمه‌ی «انتخاب درس‌ها» درس‌هایی مشخص کنید.
            </p>
          )}

          {subjects && subjects.length > 0 && (
            <>
              <ul className="space-y-2">
                {rows.map((row) => (
                  <li
                    key={row.uid}
                    className="grid grid-cols-[5.5rem_1fr_6rem_2rem] items-center gap-2"
                  >
                    <Select
                      value={String(row.dayOffset)}
                      onValueChange={(value) => updateRow(row.uid, { dayOffset: Number(value) })}
                    >
                      <SelectTrigger aria-label="روز برنامه" className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(durationDays === null
                          ? []
                          : Array.from({ length: durationDays }, (_, i) => i)
                        ).map((offset) => (
                          <SelectItem key={offset} value={String(offset)}>
                            روز {toPersianDigits(offset + 1)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select
                      value={row.subjectId === null ? '' : String(row.subjectId)}
                      onValueChange={(value) => updateRow(row.uid, { subjectId: Number(value) })}
                    >
                      <SelectTrigger aria-label="درس" className="h-9">
                        <SelectValue placeholder="درس…" />
                      </SelectTrigger>
                      <SelectContent>
                        {subjects.map((subject) => (
                          <SelectItem key={subject.id} value={String(subject.id)}>
                            {subject.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Input
                      value={row.minutes}
                      onChange={(e) => updateRow(row.uid, { minutes: e.target.value })}
                      placeholder="دقیقه"
                      inputMode="numeric"
                      aria-label="دقیقه‌ی مطالعه"
                      className="h-9 text-center tabular-nums"
                    />

                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="حذف ردیف"
                      className="h-9 w-9 text-muted-foreground hover:text-destructive"
                      onClick={() => removeRow(row.uid)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </li>
                ))}
              </ul>

              {rows.length === 0 && (
                <p className="py-2 text-center text-xs text-muted-foreground">
                  ردیفی اضافه نشده است.
                </p>
              )}

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addRow}
                disabled={durationDays === null}
              >
                <Plus className="ml-2 h-4 w-4" />
                افزودن ردیف
              </Button>
              {durationDays === null && (
                <p className="text-xs text-destructive">طول برنامه باید بین ۱ و ۹۰ روز باشد.</p>
              )}
            </>
          )}
        </div>

        {/* ── actions ────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={handleSave} disabled={busy}>
            {saving && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
            ذخیره پیش‌نویس
          </Button>
          <Button type="button" onClick={handlePublish} disabled={busy}>
            {publishing && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
            انتشار
          </Button>
        </div>

        {/* ── saved plans ────────────────────────────────────────────────── */}
        <div className="space-y-2 border-t border-border/60 pt-3">
          <span className="text-sm font-medium">برنامه‌های ثبت‌شده</span>

          {plansError && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
              <p className="flex items-center gap-2 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                {plansError}
              </p>
              <Button variant="outline" size="sm" onClick={refetchPlans}>
                <RefreshCw className="ml-2 h-3.5 w-3.5" />
                تلاش مجدد
              </Button>
            </div>
          )}

          {!plans && !plansError && <Skeleton className="h-12 w-full rounded-xl" />}

          {plans && plans.length === 0 && (
            <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
              هنوز برنامه‌ای ثبت نشده است.
            </p>
          )}

          {plans && plans.length > 0 && (
            <ul className="space-y-2">
              {[...plans]
                .sort((a, b) => a.startDate.localeCompare(b.startDate))
                .map((plan) => (
                  <li
                    key={plan.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/60 px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant={plan.status === 'PUBLISHED' ? 'default' : 'outline'}
                          className="font-normal"
                        >
                          {plan.status === 'PUBLISHED' ? 'منتشرشده' : 'پیش‌نویس'}
                        </Badge>
                        {/* Step 8: per-plan adherence; quiet-null for drafts and
                        plans with no elapsed items yet (percent is null). */}
                        {plan.percent != null && (
                          <Badge
                            variant="outline"
                            className={`font-normal tabular-nums ${adherenceColorClass(plan.percent)}`}
                          >
                            پایبندی {formatAdherence(plan.percent)}
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground">
                          از {formatPersianDate(plan.startDate)} تا{' '}
                          {formatPersianDate(plan.endDate)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                        {toPersianDigits(plan.durationDays)} روز ·{' '}
                        {toPersianDigits(plan.items.length)} ردیف
                      </p>
                    </div>
                    {plan.status === 'PUBLISHED' && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={busyPlanId === plan.id}
                        onClick={() => handleUnpublish(plan.id)}
                      >
                        {busyPlanId === plan.id ? (
                          <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Undo2 className="ml-2 h-4 w-4" />
                        )}
                        لغو انتشار
                      </Button>
                    )}
                  </li>
                ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
