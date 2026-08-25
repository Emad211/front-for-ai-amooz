'use client';

import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertCircle,
  GraduationCap,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';

import {
  AdvisoryService,
  type CreateExamScoreBody,
  type ExamScore,
  type ExamScoreKind,
  type ExamScoreRating,
  type UpdateExamScoreBody,
} from '@/services/advisory-service';
import { toEnglishDigits, toPersianDigits } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
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
import { JalaliDatePicker } from '@/components/advisory/study-plan/jalali-date-picker';

/** Wire kinds with their Persian labels — rendered from here everywhere. */
export const EXAM_KIND_LABELS: Record<ExamScoreKind, string> = {
  SCHOOL: 'مدرسه',
  PERSONAL: 'شخصی',
  CLASS_C: 'کلاس',
  ONLINE: 'آنلاین',
  NATIONAL: 'کنکور کشوری',
  ADVISOR: 'آزمون مشاور',
};

/** Advisor verdicts with their Persian labels. */
export const RATING_LABELS: Record<ExamScoreRating, string> = {
  EXCELLENT: 'عالی',
  GOOD: 'خوب',
  FAIR: 'متوسط',
  WEAK: 'ضعیف',
};

/** Color-coded badge classes per verdict (green → red). */
export const RATING_BADGE_CLASSES: Record<ExamScoreRating, string> = {
  EXCELLENT:
    'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  GOOD: 'border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300',
  FAIR: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  WEAK: 'border-destructive/40 bg-destructive/10 text-destructive',
};

/** Server-enforced roster cap (`MAX_EXAM_SCORES`); mirrored for the counter. */
const MAX_EXAM_SCORES = 40;

const PERCENT_PATTERN = /^\d{1,3}(\.\d{1,2})?$/;
const INT_PATTERN = /^\d+$/;

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

function todayIso(): string {
  return toIsoDate(new Date());
}

function formatJalaliDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return formatPersianDate(parseIsoDate(iso) ?? iso);
}

/** Digit-tolerant integer sanitizer: Persian digits → ASCII, digits only. */
function sanitizeIntInput(raw: string): string {
  return toEnglishDigits(raw).replace(/\D/g, '');
}

/** Digit-tolerant decimal sanitizer (Persian «٫» → '.', single dot kept). */
function sanitizeDecimalInput(raw: string): string {
  const cleaned = toEnglishDigits(raw)
    .replace(/[٫]/g, '.')
    .replace(/[^0-9.]/g, '');
  const firstDot = cleaned.indexOf('.');
  if (firstDot === -1) return cleaned;
  return (
    cleaned.slice(0, firstDot + 1) + cleaned.slice(firstDot + 1).replace(/\./g, '')
  );
}

type ScoreFormState = {
  title: string;
  examKind: ExamScoreKind;
  /** ISO `YYYY-MM-DD`; '' = not picked yet. */
  examDate: string;
  scorePercentRaw: string;
  taraRaw: string;
  advisorRating: ExamScoreRating | null;
  advisorNote: string;
};

function seedFormState(item: ExamScore | null): ScoreFormState {
  return {
    title: item?.title ?? '',
    examKind: item?.examKind ?? 'SCHOOL',
    examDate: item?.examDate ?? todayIso(),
    scorePercentRaw: item ? String(item.scorePercent) : '',
    taraRaw: item && item.tara !== null ? String(item.tara) : '',
    advisorRating: item?.advisorRating ?? null,
    advisorNote: item?.advisorNote ?? '',
  };
}

function collectProblem(state: ScoreFormState): string | null {
  if (!state.title.trim()) return 'عنوان آزمون را بنویسید.';
  if (!state.examDate) return 'تاریخ آزمون را انتخاب کنید.';
  const percent = state.scorePercentRaw.trim();
  if (
    !PERCENT_PATTERN.test(percent) ||
    Number(percent) < 0 ||
    Number(percent) > 100
  ) {
    return 'درصد باید عددی بین ۰ و ۱۰۰ باشد.';
  }
  const tara = state.taraRaw.trim();
  if (tara !== '' && !INT_PATTERN.test(tara)) {
    return 'تراز باید عددی صحیح نامنفی باشد.';
  }
  return null;
}

function buildPayload(state: ScoreFormState): CreateExamScoreBody {
  const tara = state.taraRaw.trim();
  return {
    title: state.title.trim(),
    examKind: state.examKind,
    examDate: state.examDate,
    scorePercent: Number(state.scorePercentRaw.trim()),
    tara: tara === '' ? null : Number(tara),
    advisorRating: state.advisorRating,
    advisorNote: state.advisorNote.trim(),
  };
}

function buildPatch(
  original: ExamScore,
  state: ScoreFormState,
): UpdateExamScoreBody {
  const next = buildPayload(state);
  const patch: UpdateExamScoreBody = {};
  if (next.title !== original.title) patch.title = next.title;
  if (next.examKind !== original.examKind) patch.examKind = next.examKind;
  if (next.examDate !== original.examDate) patch.examDate = next.examDate;
  if (next.scorePercent !== original.scorePercent) {
    patch.scorePercent = next.scorePercent;
  }
  if ((next.tara ?? null) !== (original.tara ?? null)) {
    patch.tara = next.tara ?? null;
  }
  if ((next.advisorRating ?? null) !== (original.advisorRating ?? null)) {
    patch.advisorRating = next.advisorRating ?? null;
  }
  if (next.advisorNote !== original.advisorNote) {
    patch.advisorNote = next.advisorNote;
  }
  return patch;
}

/**
 * The shared field grid of both the add-form and the inline editor. Numeric
 * inputs render Persian digits while typing and store ASCII internally.
 */
function ScoreFields({
  state,
  onChange,
  idPrefix,
}: {
  state: ScoreFormState;
  onChange: (patch: Partial<ScoreFormState>) => void;
  idPrefix: string;
}) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label
            htmlFor={`${idPrefix}-title`}
            className="text-xs font-medium text-muted-foreground"
          >
            عنوان آزمون
          </label>
          <Input
            id={`${idPrefix}-title`}
            value={state.title}
            onChange={(e) => onChange({ title: e.target.value })}
            maxLength={120}
            placeholder="مثلاً آزمون جامع ریاضی قلم‌چی"
            className="h-9"
          />
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor={`${idPrefix}-kind`}
            className="text-xs font-medium text-muted-foreground"
          >
            نوع آزمون
          </label>
          <Select
            value={state.examKind}
            onValueChange={(value) =>
              onChange({ examKind: value as ExamScoreKind })
            }
          >
            <SelectTrigger id={`${idPrefix}-kind`} className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(EXAM_KIND_LABELS) as ExamScoreKind[]).map((kind) => (
                <SelectItem key={kind} value={kind}>
                  {EXAM_KIND_LABELS[kind]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor={`${idPrefix}-date`}
            className="text-xs font-medium text-muted-foreground"
          >
            تاریخ آزمون
          </label>
          <JalaliDatePicker
            id={`${idPrefix}-date`}
            value={state.examDate}
            onChange={(iso) => onChange({ examDate: iso })}
            placeholder="تاریخ آزمون را انتخاب کنید"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label
              htmlFor={`${idPrefix}-percent`}
              className="text-xs font-medium text-muted-foreground"
            >
              درصد
            </label>
            <Input
              id={`${idPrefix}-percent`}
              value={toPersianDigits(state.scorePercentRaw)}
              onChange={(e) =>
                onChange({ scorePercentRaw: sanitizeDecimalInput(e.target.value) })
              }
              inputMode="decimal"
              placeholder="۰ تا ۱۰۰"
              aria-label="درصد آزمون"
              className="h-9 text-center tabular-nums"
            />
          </div>
          <div className="space-y-1.5">
            <label
              htmlFor={`${idPrefix}-tara`}
              className="text-xs font-medium text-muted-foreground"
            >
              تراز (اختیاری)
            </label>
            <Input
              id={`${idPrefix}-tara`}
              value={toPersianDigits(state.taraRaw)}
              onChange={(e) =>
                onChange({ taraRaw: sanitizeIntInput(e.target.value) })
              }
              inputMode="numeric"
              placeholder="مثلاً ۶۵۰۰"
              aria-label="تراز آزمون"
              className="h-9 text-center tabular-nums"
            />
          </div>
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <label
            htmlFor={`${idPrefix}-rating`}
            className="text-xs font-medium text-muted-foreground"
          >
            ارزیابی مشاور (اختیاری)
          </label>
          <Select
            value={state.advisorRating ?? 'none'}
            onValueChange={(value) =>
              onChange({
                advisorRating:
                  value === 'none' ? null : (value as ExamScoreRating),
              })
            }
          >
            <SelectTrigger id={`${idPrefix}-rating`} className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">بدون ارزیابی</SelectItem>
              {(Object.keys(RATING_LABELS) as ExamScoreRating[]).map((rating) => (
                <SelectItem key={rating} value={rating}>
                  {RATING_LABELS[rating]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="space-y-1.5">
        <label
          htmlFor={`${idPrefix}-note`}
          className="text-xs font-medium text-muted-foreground"
        >
          یادداشت مشاور
        </label>
        <Textarea
          id={`${idPrefix}-note`}
          value={state.advisorNote}
          onChange={(e) => onChange({ advisorNote: e.target.value })}
          rows={2}
          maxLength={2000}
          placeholder="نظر کوتاه درباره‌ی این آزمون…"
          className="min-h-[56px] text-sm leading-relaxed"
        />
      </div>
    </div>
  );
}

/**
 * The advisor's exam-scores card («نمرات آزمون», restart step 5): a
 * date-descending list with add / inline-edit (PATCH sends only changed keys)
 * / delete-with-confirm. The server's 40-row cap answers 400 with a Persian
 * detail that surfaces verbatim via toast.
 */
export function ExamScoresCard({ engagementId }: { engagementId: number }) {
  const [scores, setScores] = useState<ExamScore[] | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const [addOpen, setAddOpen] = useState(false);
  const [addState, setAddState] = useState<ScoreFormState>(() =>
    seedFormState(null),
  );
  const [savingAdd, setSavingAdd] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editState, setEditState] = useState<ScoreFormState>(() =>
    seedFormState(null),
  );
  const [savingEdit, setSavingEdit] = useState(false);

  const [pendingDelete, setPendingDelete] = useState<ExamScore | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let active = true;
    setError('');
    setScores(null);
    AdvisoryService.getExamScores(engagementId)
      .then((list) => {
        if (active) setScores(list);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId, reloadKey]);

  const refetch = () => {
    AdvisoryService.getExamScores(engagementId)
      .then((list) => setScores(list))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
  };

  // Server already returns DESC by date; re-sort defensively so shape drift
  // can never flip the reading order.
  const sorted = useMemo(
    () =>
      [...(scores ?? [])].sort(
        (a, b) => b.examDate.localeCompare(a.examDate) || b.id - a.id,
      ),
    [scores],
  );

  const atCap = sorted.length >= MAX_EXAM_SCORES;

  const handleAdd = async () => {
    const problem = collectProblem(addState);
    if (problem) {
      toast.error(problem);
      return;
    }
    setSavingAdd(true);
    try {
      await AdvisoryService.createExamScore(engagementId, buildPayload(addState));
      toast.success('نمره ثبت شد.');
      setAddState(seedFormState(null));
      setAddOpen(false);
      refetch();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'ثبت نمره ناموفق بود.');
    } finally {
      setSavingAdd(false);
    }
  };

  const startEdit = (item: ExamScore) => {
    setEditingId(item.id);
    setEditState(seedFormState(item));
    setAddOpen(false);
  };

  const handleEditSave = async (original: ExamScore) => {
    const problem = collectProblem(editState);
    if (problem) {
      toast.error(problem);
      return;
    }
    const patch = buildPatch(original, editState);
    if (Object.keys(patch).length === 0) {
      toast.info('تغییری برای ذخیره نیست.');
      setEditingId(null);
      return;
    }
    setSavingEdit(true);
    try {
      await AdvisoryService.updateExamScore(engagementId, original.id, patch);
      toast.success('نمره به‌روزرسانی شد.');
      setEditingId(null);
      refetch();
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'به‌روزرسانی نمره ناموفق بود.',
      );
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDeleteConfirmed = async () => {
    const target = pendingDelete;
    if (!target) return;
    setDeleting(true);
    try {
      await AdvisoryService.deleteExamScore(engagementId, target.id);
      toast.success('نمره حذف شد.');
      if (editingId === target.id) setEditingId(null);
      setPendingDelete(null);
      refetch();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'حذف نمره ناموفق بود.');
    } finally {
      setDeleting(false);
    }
  };

  const loading = scores === null && !error;

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <span className="rounded-lg bg-primary/10 p-1.5">
              <GraduationCap className="h-4 w-4 text-primary" />
            </span>
            نمرات آزمون
          </CardTitle>
          <Button
            type="button"
            size="sm"
            variant={addOpen ? 'outline' : 'default'}
            disabled={atCap && !addOpen}
            onClick={() => {
              setAddOpen((open) => !open);
              setEditingId(null);
            }}
          >
            {addOpen ? (
              'بستن فرم'
            ) : (
              <>
                <Plus className="ml-2 h-4 w-4" />
                افزودن نمره
              </>
            )}
          </Button>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          نمرات، تراز و ارزیابی هر آزمون را اینجا ثبت کنید؛ دانش‌آموز همین
          فهرست را به‌ترتیب تاریخ می‌بیند.
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        <p className="text-xs tabular-nums text-muted-foreground">
          {toPersianDigits(sorted.length)} از {toPersianDigits(MAX_EXAM_SCORES)}{' '}
          ردیف
        </p>
        {atCap && (
          <p className="rounded-lg border border-dashed px-3 py-2 text-center text-xs text-muted-foreground">
            سقف {toPersianDigits(MAX_EXAM_SCORES)} ردیف پر شده است؛ برای افزودن
            نمرۀ جدید یکی را حذف کنید.
          </p>
        )}

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
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-14 w-full rounded-xl" />
            ))}
          </div>
        )}

        {/* ── add form ─────────────────────────────────────────────────── */}
        {!error && addOpen && (
          <div className="space-y-3 rounded-xl border border-border/60 p-3">
            <ScoreFields
              idPrefix="exam-score-add"
              state={addState}
              onChange={(patch) =>
                setAddState((prev) => ({ ...prev, ...patch }))
              }
            />
            <div className="flex items-center justify-end gap-2 border-t border-border/60 pt-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setAddOpen(false);
                  setAddState(seedFormState(null));
                }}
                disabled={savingAdd}
              >
                انصراف
              </Button>
              <Button type="button" onClick={handleAdd} disabled={savingAdd}>
                {savingAdd && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
                {savingAdd ? 'در حال ذخیره…' : 'ذخیره'}
              </Button>
            </div>
          </div>
        )}

        {/* ── score rows ───────────────────────────────────────────────── */}
        {!error && !loading && sorted.length === 0 && (
          <p className="rounded-lg border border-dashed px-3 py-6 text-center text-xs leading-relaxed text-muted-foreground">
            هنوز نمره‌ای ثبت نشده است. اولین آزمون دانش‌آموز را اضافه کنید.
          </p>
        )}

        {!error && sorted.length > 0 && (
          <ul className="space-y-2">
            {sorted.map((score) => {
              const isEditing = editingId === score.id;
              if (isEditing) {
                return (
                  <li
                    key={score.id}
                    className="space-y-3 rounded-xl border border-primary/40 bg-primary/[0.03] p-3"
                  >
                    <ScoreFields
                      idPrefix={`exam-score-edit-${score.id}`}
                      state={editState}
                      onChange={(patch) =>
                        setEditState((prev) => ({ ...prev, ...patch }))
                      }
                    />
                    <div className="flex items-center justify-end gap-2 border-t border-border/60 pt-3">
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => setEditingId(null)}
                        disabled={savingEdit}
                      >
                        انصراف
                      </Button>
                      <Button
                        type="button"
                        onClick={() => handleEditSave(score)}
                        disabled={savingEdit}
                      >
                        {savingEdit && (
                          <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                        )}
                        {savingEdit ? 'در حال ذخیره…' : 'ذخیره'}
                      </Button>
                    </div>
                  </li>
                );
              }
              return (
                <li
                  key={score.id}
                  className="rounded-xl border border-border/60 p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
                    <div className="min-w-0 flex-1 space-y-1">
                      <p className="text-sm font-medium leading-relaxed">
                        {score.title || 'بدون عنوان'}
                      </p>
                      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                        <span>{EXAM_KIND_LABELS[score.examKind]}</span>
                        <span aria-hidden="true">·</span>
                        <span className="tabular-nums">
                          {formatJalaliDate(score.examDate)}
                        </span>
                        {score.subjectName && (
                          <>
                            <span aria-hidden="true">·</span>
                            <span>{score.subjectName}</span>
                          </>
                        )}
                      </p>
                      {score.advisorNote.trim() && (
                        <p className="text-xs leading-relaxed text-muted-foreground">
                          {score.advisorNote}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold tabular-nums text-primary">
                        {toPersianDigits(score.scorePercent)}٪
                      </span>
                      {score.tara !== null && (
                        <span className="rounded-full bg-muted px-2 py-0.5 text-xs tabular-nums text-muted-foreground">
                          تراز {toPersianDigits(score.tara)}
                        </span>
                      )}
                      {score.advisorRating && (
                        <span
                          className={cn(
                            'rounded-full border px-2 py-0.5 text-xs font-semibold',
                            RATING_BADGE_CLASSES[score.advisorRating],
                          )}
                        >
                          {RATING_LABELS[score.advisorRating]}
                        </span>
                      )}
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`ویرایش ${score.title}`}
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        disabled={editingId !== null}
                        onClick={() => startEdit(score)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`حذف ${score.title}`}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        disabled={editingId !== null}
                        onClick={() => setPendingDelete(score)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>

      {/* ── delete confirmation ────────────────────────────────────────── */}
      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
      >
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>حذف نمره</AlertDialogTitle>
            <AlertDialogDescription>
              «{pendingDelete?.title}» برای همیشه حذف می‌شود و این کار برگشت‌پذیر
              نیست.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>انصراف</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault();
                handleDeleteConfirmed();
              }}
            >
              {deleting && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
              {deleting ? 'در حال حذف…' : 'حذف'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
