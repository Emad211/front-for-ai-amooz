'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertCircle,
  ChevronDown,
  FileSearch,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';

import {
  AdvisoryService,
  type ExamAnalysis,
  type ExamAnalysisRow,
  type ExamAnalysisWriteBody,
  type ExamGradeBand,
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
import { Badge } from '@/components/ui/badge';
import { JalaliDatePicker } from '@/components/advisory/jalali-date-picker';

/** Grade bands with their Persian labels — rendered from here everywhere. */
export const GRADE_BAND_LABELS: Record<ExamGradeBand, string> = {
  G10: 'دهم',
  G11: 'یازدهم',
  G12S1: 'دوازدهم نیمسال اول',
  G12S2: 'دوازدهم نیمسال دوم',
};

const PERCENT_PATTERN = /^\d{1,3}(\.\d{1,2})?$/;
const INT_PATTERN = /^\d+$/;
const SIGNED_INT_PATTERN = /^[-+]?\d+$/;

function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatJalaliDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return formatPersianDate(parseIsoDate(iso) ?? iso);
}

function sanitizeIntInput(raw: string): string {
  return toEnglishDigits(raw).replace(/\D/g, '');
}

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

/** Integer sanitizer that tolerates one leading sign («+۱۲» / «−۵»). */
function sanitizeSignedIntInput(raw: string): string {
  const cleaned = toEnglishDigits(raw).replace(/[^0-9+\-]/g, '');
  const negative = cleaned.startsWith('-');
  const positive = !negative && cleaned.startsWith('+');
  const digits = cleaned.replace(/[+-]/g, '');
  return `${negative ? '-' : positive ? '+' : ''}${digits}`;
}

function numOrNull(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === '' || trimmed === '-' || trimmed === '+') return null;
  return Number(trimmed);
}

type AnalysisRowState = {
  uid: number;
  subjectName: string;
  wrongCountRaw: string;
  skippedCountRaw: string;
  doubtfulTotalRaw: string;
  doubtfulWrongRaw: string;
  doubtfulSkippedRaw: string;
  doubtfulCorrectRaw: string;
  causeNote: string;
};

type AnalysisNoteState = {
  uid: number;
  questionNumberRaw: string;
  subjectName: string;
  note: string;
};

type AnalysisFormState = {
  examNumberRaw: string;
  /** ISO `YYYY-MM-DD`; '' = not picked yet. */
  examDate: string;
  gradeBand: ExamGradeBand | 'none';
  totalTaraRaw: string;
  nationalRankRaw: string;
  regionRankRaw: string;
  cityRankRaw: string;
  highestPercentRaw: string;
  lowestPercentRaw: string;
  taraDeltaRaw: string;
  advisorReport: string;
  rows: AnalysisRowState[];
  notes: AnalysisNoteState[];
};

function seedAnalysisState(
  item: ExamAnalysis | null,
  nextUid: () => number,
): AnalysisFormState {
  return {
    examNumberRaw:
      item && item.examNumber !== null ? String(item.examNumber) : '',
    examDate: item?.examDate ?? '',
    gradeBand: item?.gradeBand ?? 'none',
    totalTaraRaw:
      item && item.totalTara !== null ? String(item.totalTara) : '',
    nationalRankRaw:
      item && item.nationalRank !== null ? String(item.nationalRank) : '',
    regionRankRaw:
      item && item.regionRank !== null ? String(item.regionRank) : '',
    cityRankRaw: item && item.cityRank !== null ? String(item.cityRank) : '',
    highestPercentRaw:
      item && item.highestPercent !== null ? String(item.highestPercent) : '',
    lowestPercentRaw:
      item && item.lowestPercent !== null ? String(item.lowestPercent) : '',
    taraDeltaRaw:
      item && item.taraDelta !== null ? String(item.taraDelta) : '',
    advisorReport: item?.advisorReport ?? '',
    rows: (item?.rows ?? []).map((row) => ({
      uid: nextUid(),
      subjectName: row.subjectName,
      wrongCountRaw: String(row.wrongCount),
      skippedCountRaw: String(row.skippedCount),
      doubtfulTotalRaw: String(row.doubtfulTotal),
      doubtfulWrongRaw: String(row.doubtfulWrong),
      doubtfulSkippedRaw: String(row.doubtfulSkipped),
      doubtfulCorrectRaw: String(row.doubtfulCorrect),
      causeNote: row.causeNote,
    })),
    notes: (item?.notes ?? []).map((note) => ({
      uid: nextUid(),
      questionNumberRaw: String(note.questionNumber),
      subjectName: note.subjectName,
      note: note.note,
    })),
  };
}

/**
 * Client twin of the server's Persian validation for one analysis. Returns
 * the FIRST problem as a Persian message, or null when the form is valid.
 */
function collectAnalysisProblem(state: AnalysisFormState): string | null {
  const examNumber = state.examNumberRaw.trim();
  if (examNumber !== '' && !INT_PATTERN.test(examNumber)) {
    return 'شمارهٔ کارنامه باید عددی صحیح باشد.';
  }
  for (const [raw, label] of [
    [state.nationalRankRaw.trim(), 'رتبۀ کشوری'],
    [state.regionRankRaw.trim(), 'رتبۀ منطقه'],
    [state.cityRankRaw.trim(), 'رتبۀ شهر'],
  ] as const) {
    if (raw !== '' && (!INT_PATTERN.test(raw) || Number(raw) < 1)) {
      return `${label} باید عددی صحیح مثبت باشد.`;
    }
  }
  for (const [raw, label] of [
    [state.highestPercentRaw.trim(), 'بالاترین درصد'],
    [state.lowestPercentRaw.trim(), 'پایین‌ترین درصد'],
  ] as const) {
    if (raw !== '' && (!PERCENT_PATTERN.test(raw) || Number(raw) < 0 || Number(raw) > 100)) {
      return `${label} باید عددی بین ۰ و ۱۰۰ باشد.`;
    }
  }
  if (
    state.taraDeltaRaw.trim() !== '' &&
    !SIGNED_INT_PATTERN.test(state.taraDeltaRaw.trim())
  ) {
    return 'تغییر تراز باید عددی صحیح باشد.';
  }
  if (
    state.totalTaraRaw.trim() !== '' &&
    !INT_PATTERN.test(state.totalTaraRaw.trim())
  ) {
    return 'تراز کل باید عددی صحیح نامنفی باشد.';
  }

  for (const row of state.rows) {
    if (!row.subjectName.trim()) {
      return 'نام درس هر ردیف جدول درس‌ها را بنویسید.';
    }
    const counts = [
      row.wrongCountRaw,
      row.skippedCountRaw,
      row.doubtfulTotalRaw,
      row.doubtfulWrongRaw,
      row.doubtfulSkippedRaw,
      row.doubtfulCorrectRaw,
    ];
    if (counts.some((raw) => raw.trim() !== '' && !INT_PATTERN.test(raw.trim()))) {
      return 'تعداد غلط، نزده و شک‌دار باید اعداد صحیح نامنفی باشند.';
    }
    const doubtfulSum =
      (numOrNull(row.doubtfulWrongRaw) ?? 0) +
      (numOrNull(row.doubtfulSkippedRaw) ?? 0) +
      (numOrNull(row.doubtfulCorrectRaw) ?? 0);
    const doubtfulTotal = numOrNull(row.doubtfulTotalRaw) ?? 0;
    if (doubtfulSum > doubtfulTotal) {
      return 'جمع شک‌دارهای غلط، نزده و درست نباید از کل شک‌دارها بیشتر باشد.';
    }
  }

  const seenQuestions = new Set<string>();
  for (const note of state.notes) {
    const question = note.questionNumberRaw.trim();
    if (
      !INT_PATTERN.test(question) ||
      Number(question) < 1 ||
      Number(question) > 300
    ) {
      return 'شمارهٔ سؤال باید عددی بین ۱ و ۳۰۰ باشد.';
    }
    if (seenQuestions.has(question)) {
      return `برای سؤال شمارۀ ${toPersianDigits(Number(question))} بیش از یک یادداشت ثبت شده است؛ شماره‌ها باید یکتا باشند.`;
    }
    seenQuestions.add(question);
    if (!note.subjectName.trim()) {
      return 'نام درس هر یادداشت را بنویسید.';
    }
    if (!note.note.trim()) {
      return 'متن هر یادداشت را بنویسید.';
    }
  }

  return null;
}

function buildAnalysisPayload(state: AnalysisFormState): ExamAnalysisWriteBody {
  return {
    examNumber: numOrNull(state.examNumberRaw),
    examDate: state.examDate || null,
    gradeBand: state.gradeBand === 'none' ? null : state.gradeBand,
    totalTara: numOrNull(state.totalTaraRaw),
    nationalRank: numOrNull(state.nationalRankRaw),
    regionRank: numOrNull(state.regionRankRaw),
    cityRank: numOrNull(state.cityRankRaw),
    highestPercent: numOrNull(state.highestPercentRaw),
    lowestPercent: numOrNull(state.lowestPercentRaw),
    taraDelta: numOrNull(state.taraDeltaRaw.replace(/^\+/, '')),
    advisorReport: state.advisorReport.trim(),
    rows: state.rows.map((row) => ({
      subjectName: row.subjectName.trim(),
      wrongCount: numOrNull(row.wrongCountRaw) ?? 0,
      skippedCount: numOrNull(row.skippedCountRaw) ?? 0,
      doubtfulTotal: numOrNull(row.doubtfulTotalRaw) ?? 0,
      doubtfulWrong: numOrNull(row.doubtfulWrongRaw) ?? 0,
      doubtfulSkipped: numOrNull(row.doubtfulSkippedRaw) ?? 0,
      doubtfulCorrect: numOrNull(row.doubtfulCorrectRaw) ?? 0,
      causeNote: row.causeNote.trim(),
    })),
    notes: [...state.notes]
      .map((note) => ({
        questionNumber: Number(note.questionNumberRaw.trim()),
        subjectName: note.subjectName.trim(),
        note: note.note.trim(),
      }))
      .sort((a, b) => a.questionNumber - b.questionNumber),
  };
}

/* ── Shared read-only renderers (also used by the student mirror) ────── */

function formatSigned(value: number): string {
  return value >= 0 ? `+${toPersianDigits(value)}` : toPersianDigits(value);
}

/** The report-card metric tiles of one analysis; null metrics are skipped. */
export function AnalysisMetricsGrid({ item }: { item: ExamAnalysis }) {
  const metrics: { label: string; value: string; tone?: 'up' | 'down' }[] = [];
  if (item.totalTara !== null) {
    metrics.push({ label: 'تراز کل', value: toPersianDigits(item.totalTara) });
  }
  if (item.taraDelta !== null) {
    metrics.push({
      label: 'تغییر تراز',
      value: formatSigned(item.taraDelta),
      tone: item.taraDelta >= 0 ? 'up' : 'down',
    });
  }
  if (item.nationalRank !== null) {
    metrics.push({
      label: 'رتبۀ کشوری',
      value: toPersianDigits(item.nationalRank),
    });
  }
  if (item.regionRank !== null) {
    metrics.push({
      label: 'رتبۀ منطقه',
      value: toPersianDigits(item.regionRank),
    });
  }
  if (item.cityRank !== null) {
    metrics.push({ label: 'رتبۀ شهر', value: toPersianDigits(item.cityRank) });
  }
  if (item.highestPercent !== null) {
    metrics.push({
      label: 'بالاترین درصد',
      value: `${toPersianDigits(item.highestPercent)}٪`,
    });
  }
  if (item.lowestPercent !== null) {
    metrics.push({
      label: 'پایین‌ترین درصد',
      value: `${toPersianDigits(item.lowestPercent)}٪`,
    });
  }
  if (metrics.length === 0) return null;

  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-4">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="rounded-lg border border-border/40 px-2.5 py-1.5"
        >
          <dt className="text-[11px] text-muted-foreground">{metric.label}</dt>
          <dd
            className={cn(
              'text-sm font-semibold tabular-nums',
              metric.tone === 'up' && 'text-emerald-600 dark:text-emerald-400',
              metric.tone === 'down' && 'text-destructive',
            )}
          >
            {metric.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** The per-subject rows of one analysis as compact RTL lines. */
export function AnalysisRowsList({ rows }: { rows: ExamAnalysisRow[] }) {
  if (rows.length === 0) return null;

  return (
    <ul className="divide-y divide-border/40">
      {rows.map((row, index) => (
        <li
          key={`${row.subjectName}-${index}`}
          className="py-1.5 text-xs leading-relaxed"
        >
          <p className="font-medium">{row.subjectName}</p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 tabular-nums text-muted-foreground">
            <span>غلط {toPersianDigits(row.wrongCount)}</span>
            <span aria-hidden="true">·</span>
            <span>نزده {toPersianDigits(row.skippedCount)}</span>
            {(row.doubtfulTotal > 0 ||
              row.doubtfulWrong > 0 ||
              row.doubtfulSkipped > 0 ||
              row.doubtfulCorrect > 0) && (
              <>
                <span aria-hidden="true">·</span>
                <span>
                  شک‌دار: کل {toPersianDigits(row.doubtfulTotal)} (غلط{' '}
                  {toPersianDigits(row.doubtfulWrong)}، نزده{' '}
                  {toPersianDigits(row.doubtfulSkipped)}، درست{' '}
                  {toPersianDigits(row.doubtfulCorrect)})
                </span>
              </>
            )}
          </p>
          {row.causeNote.trim() && (
            <p className="mt-0.5 text-muted-foreground">{row.causeNote}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

/** The per-question notes of one analysis as numbered lines. */
export function AnalysisNotesList({
  notes,
}: {
  notes: ExamAnalysis['notes'];
}) {
  if (notes.length === 0) return null;

  return (
    <ul className="divide-y divide-border/40">
      {[...notes]
        .sort((a, b) => a.questionNumber - b.questionNumber)
        .map((note) => (
          <li
            key={note.questionNumber}
            className="flex items-start gap-2 py-1.5 text-xs leading-relaxed"
          >
            <span className="shrink-0 rounded-md bg-primary/10 px-1.5 py-0.5 font-semibold tabular-nums text-primary">
              سؤال {toPersianDigits(note.questionNumber)}
            </span>
            <span className="min-w-0">
              {note.subjectName.trim() && (
                <span className="font-medium">{note.subjectName}: </span>
              )}
              {note.note}
            </span>
          </li>
        ))}
    </ul>
  );
}

/* ── Editor field primitives ─────────────────────────────────────────── */

function NumericField({
  id,
  label,
  value,
  onChange,
  placeholder,
  signed = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  signed?: boolean;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-[11px] font-medium text-muted-foreground">
        {label}
      </label>
      <Input
        id={id}
        value={toPersianDigits(value)}
        onChange={(e) =>
          onChange(
            signed
              ? sanitizeSignedIntInput(e.target.value)
              : sanitizeIntInput(e.target.value),
          )
        }
        inputMode="numeric"
        placeholder={placeholder}
        aria-label={label}
        className="h-9 rounded-lg text-center text-sm tabular-nums"
      />
    </div>
  );
}

function DecimalField({
  id,
  label,
  value,
  onChange,
  placeholder,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-[11px] font-medium text-muted-foreground">
        {label}
      </label>
      <Input
        id={id}
        value={toPersianDigits(value)}
        onChange={(e) => onChange(sanitizeDecimalInput(e.target.value))}
        inputMode="decimal"
        placeholder={placeholder}
        aria-label={label}
        className="h-9 rounded-lg text-center text-sm tabular-nums"
      />
    </div>
  );
}

/**
 * Create/edit form of one analysis: report-card section, per-subject rows,
 * and per-question notes. Remounted (via key) whenever its target changes so
 * state reseeds cleanly; onSubmit receives the WHOLE payload.
 */
function AnalysisEditor({
  state,
  onChange,
  saving,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  state: AnalysisFormState;
  onChange: (patch: Partial<AnalysisFormState>) => void;
  saving: boolean;
  submitLabel: string;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  // View-only density state: repeated blocks fold once they grow past a
  // handful of rows; adding a row/note always re-opens its block.
  const [rowsOpen, setRowsOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);

  const updateRow = (
    uid: number,
    patch: Partial<Omit<AnalysisRowState, 'uid'>>,
  ) => {
    onChange({
      rows: state.rows.map((row) =>
        row.uid === uid ? { ...row, ...patch } : row,
      ),
    });
  };

  const removeRow = (uid: number) => {
    onChange({ rows: state.rows.filter((row) => row.uid !== uid) });
  };

  const addRow = () => {
    onChange({
      rows: [
        ...state.rows,
        {
          uid: Date.now() + state.rows.length,
          subjectName: '',
          wrongCountRaw: '',
          skippedCountRaw: '',
          doubtfulTotalRaw: '',
          doubtfulWrongRaw: '',
          doubtfulSkippedRaw: '',
          doubtfulCorrectRaw: '',
          causeNote: '',
        },
      ],
    });
  };

  const updateNote = (
    uid: number,
    patch: Partial<Omit<AnalysisNoteState, 'uid'>>,
  ) => {
    onChange({
      notes: state.notes.map((note) =>
        note.uid === uid ? { ...note, ...patch } : note,
      ),
    });
  };

  const removeNote = (uid: number) => {
    onChange({ notes: state.notes.filter((note) => note.uid !== uid) });
  };

  const addNote = () => {
    onChange({
      notes: [
        ...state.notes,
        {
          uid: Date.now() + state.notes.length,
          questionNumberRaw: '',
          subjectName: '',
          note: '',
        },
      ],
    });
  };

  return (
    <div className="space-y-4">
      {/* ── report card section ───────────────────────────────────────── */}
      <section className="space-y-3">
        <h4 className="text-sm font-medium">کارنامه</h4>
        <div className="grid grid-cols-1 gap-x-3 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          <NumericField
            id="analysis-exam-number"
            label="شمارهٔ کارنامه (اختیاری)"
            value={state.examNumberRaw}
            onChange={(next) => onChange({ examNumberRaw: next })}
            placeholder="مثلاً ۱۲"
          />
          <div className="space-y-1">
            <label
              htmlFor="analysis-exam-date"
              className="text-[11px] font-medium text-muted-foreground"
            >
              تاریخ آزمون (اختیاری)
            </label>
            <JalaliDatePicker
              id="analysis-exam-date"
              value={state.examDate}
              onChange={(iso) => onChange({ examDate: iso })}
              placeholder="تاریخ را انتخاب کنید"
            />
          </div>
          <div className="space-y-1">
            <label
              htmlFor="analysis-grade-band"
              className="text-[11px] font-medium text-muted-foreground"
            >
              پایه (اختیاری)
            </label>
            <Select
              dir="rtl"
              value={state.gradeBand}
              onValueChange={(value) =>
                onChange({ gradeBand: value as ExamGradeBand | 'none' })
              }
            >
              <SelectTrigger id="analysis-grade-band" className="h-9 rounded-lg text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">—</SelectItem>
                {(Object.keys(GRADE_BAND_LABELS) as ExamGradeBand[]).map(
                  (band) => (
                    <SelectItem key={band} value={band}>
                      {GRADE_BAND_LABELS[band]}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </div>
          <NumericField
            id="analysis-total-tara"
            label="تراز کل (اختیاری)"
            value={state.totalTaraRaw}
            onChange={(next) => onChange({ totalTaraRaw: next })}
            placeholder="مثلاً ۶۸۰۰"
          />
          <NumericField
            id="analysis-national-rank"
            label="رتبۀ کشوری (اختیاری)"
            value={state.nationalRankRaw}
            onChange={(next) => onChange({ nationalRankRaw: next })}
          />
          <NumericField
            id="analysis-region-rank"
            label="رتبۀ منطقه (اختیاری)"
            value={state.regionRankRaw}
            onChange={(next) => onChange({ regionRankRaw: next })}
          />
          <NumericField
            id="analysis-city-rank"
            label="رتبۀ شهر (اختیاری)"
            value={state.cityRankRaw}
            onChange={(next) => onChange({ cityRankRaw: next })}
          />
          <NumericField
            id="analysis-tara-delta"
            label="تغییر تراز نسبت به قبل (± اختیاری)"
            value={state.taraDeltaRaw}
            onChange={(next) => onChange({ taraDeltaRaw: next })}
            placeholder="مثلاً ‎+۱۲۰ یا ‎−۵۰"
            signed
          />
          <DecimalField
            id="analysis-highest-percent"
            label="بالاترین درصد (اختیاری)"
            value={state.highestPercentRaw}
            onChange={(next) => onChange({ highestPercentRaw: next })}
            placeholder="۰ تا ۱۰۰"
          />
          <DecimalField
            id="analysis-lowest-percent"
            label="پایین‌ترین درصد (اختیاری)"
            value={state.lowestPercentRaw}
            onChange={(next) => onChange({ lowestPercentRaw: next })}
            placeholder="۰ تا ۱۰۰"
          />
        </div>
        <div className="space-y-1">
          <label
            htmlFor="analysis-report"
            className="text-[11px] font-medium text-muted-foreground"
          >
            گزارش مشاور
          </label>
          <Textarea
            id="analysis-report"
            value={state.advisorReport}
            onChange={(e) => onChange({ advisorReport: e.target.value })}
            rows={4}
            maxLength={5000}
            placeholder="جمع‌بندی کلی این آزمون را برای دانش‌آموز بنویسید…"
            className="min-h-[96px] text-sm leading-relaxed"
          />
        </div>
      </section>

      {/* ── per-subject rows section ──────────────────────────────────── */}
      <section className="space-y-2 border-t border-border/40 pt-4">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setRowsOpen((open) => !open)}
            aria-expanded={rowsOpen || state.rows.length <= 3}
            className="flex items-center gap-2 text-sm font-medium"
          >
            جدول درس‌ها
            <Badge
              variant="secondary"
              className="text-[11px] font-normal tabular-nums"
            >
              {toPersianDigits(state.rows.length)}
            </Badge>
            {state.rows.length > 3 && (
              <ChevronDown
                className={cn(
                  'h-4 w-4 text-muted-foreground transition-transform',
                  rowsOpen && 'rotate-180',
                )}
              />
            )}
          </button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 rounded-lg px-3 text-xs"
            onClick={() => {
              addRow();
              setRowsOpen(true);
            }}
          >
            <Plus className="ml-1.5 h-3.5 w-3.5" />
            افزودن ردیف
          </Button>
        </div>
        {state.rows.length > 3 && !rowsOpen ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {toPersianDigits(state.rows.length)} ردیف ثبت شده؛ برای مشاهده و
            ویرایش باز کنید.
          </p>
        ) : (
          <>
            {state.rows.length === 0 && (
              <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs leading-relaxed text-muted-foreground">
                تحلیل درس‌به‌درس (غلط/نزده/شک‌دار) را اینجا ردیف‌به‌ردیف اضافه کنید.
              </p>
            )}
            {state.rows.length > 0 && (
              <div className="space-y-1">
                {/* Column headers for the tight table-like rows (lg+ only). */}
                <div className="-mx-2 hidden items-end gap-2 px-2 text-[11px] leading-tight text-muted-foreground lg:flex">
                  <span className="min-w-0 flex-[3_1_8rem]">درس</span>
                  <span className="w-16 shrink-0 text-center">غلط</span>
                  <span className="w-16 shrink-0 text-center">نزده</span>
                  <span className="w-16 shrink-0 text-center">شک‌دار کل</span>
                  <span className="w-16 shrink-0 text-center">شک‌دار غلط</span>
                  <span className="w-16 shrink-0 text-center">شک‌دار نزده</span>
                  <span className="w-16 shrink-0 text-center">شک‌دار درست</span>
                  <span className="min-w-0 flex-[2_1_7rem]">علت</span>
                  <span className="w-8 shrink-0" aria-hidden="true" />
                </div>
                <ul className="divide-y divide-border/40">
                  {state.rows.map((row, index) => (
                    <li
                      key={row.uid}
                      className="flex flex-wrap items-center gap-2 py-1.5"
                    >
                      <Input
                        value={row.subjectName}
                        onChange={(e) =>
                          updateRow(row.uid, { subjectName: e.target.value })
                        }
                        placeholder={`نام درس ${toPersianDigits(index + 1)}`}
                        maxLength={120}
                        aria-label={`نام درس ردیف ${toPersianDigits(index + 1)}`}
                        className="h-9 min-w-[8rem] flex-[3_1_8rem] rounded-lg text-sm"
                      />
                      <Input
                        value={toPersianDigits(row.wrongCountRaw)}
                        onChange={(e) =>
                          updateRow(row.uid, {
                            wrongCountRaw: sanitizeIntInput(e.target.value),
                          })
                        }
                        inputMode="numeric"
                        placeholder="۰"
                        aria-label="غلط"
                        className="h-9 w-16 shrink-0 rounded-lg text-center text-xs tabular-nums"
                      />
                      <Input
                        value={toPersianDigits(row.skippedCountRaw)}
                        onChange={(e) =>
                          updateRow(row.uid, {
                            skippedCountRaw: sanitizeIntInput(e.target.value),
                          })
                        }
                        inputMode="numeric"
                        placeholder="۰"
                        aria-label="نزده"
                        className="h-9 w-16 shrink-0 rounded-lg text-center text-xs tabular-nums"
                      />
                      <Input
                        value={toPersianDigits(row.doubtfulTotalRaw)}
                        onChange={(e) =>
                          updateRow(row.uid, {
                            doubtfulTotalRaw: sanitizeIntInput(e.target.value),
                          })
                        }
                        inputMode="numeric"
                        placeholder="۰"
                        aria-label="شک‌دار کل"
                        className="h-9 w-16 shrink-0 rounded-lg text-center text-xs tabular-nums"
                      />
                      <Input
                        value={toPersianDigits(row.doubtfulWrongRaw)}
                        onChange={(e) =>
                          updateRow(row.uid, {
                            doubtfulWrongRaw: sanitizeIntInput(e.target.value),
                          })
                        }
                        inputMode="numeric"
                        placeholder="۰"
                        aria-label="شک‌دار غلط"
                        className="h-9 w-16 shrink-0 rounded-lg text-center text-xs tabular-nums"
                      />
                      <Input
                        value={toPersianDigits(row.doubtfulSkippedRaw)}
                        onChange={(e) =>
                          updateRow(row.uid, {
                            doubtfulSkippedRaw: sanitizeIntInput(e.target.value),
                          })
                        }
                        inputMode="numeric"
                        placeholder="۰"
                        aria-label="شک‌دار نزده"
                        className="h-9 w-16 shrink-0 rounded-lg text-center text-xs tabular-nums"
                      />
                      <Input
                        value={toPersianDigits(row.doubtfulCorrectRaw)}
                        onChange={(e) =>
                          updateRow(row.uid, {
                            doubtfulCorrectRaw: sanitizeIntInput(e.target.value),
                          })
                        }
                        inputMode="numeric"
                        placeholder="۰"
                        aria-label="شک‌دار درست"
                        className="h-9 w-16 shrink-0 rounded-lg text-center text-xs tabular-nums"
                      />
                      <Input
                        value={row.causeNote}
                        onChange={(e) =>
                          updateRow(row.uid, { causeNote: e.target.value })
                        }
                        placeholder="علت (اختیاری)"
                        maxLength={300}
                        aria-label={`علت ردیف ${toPersianDigits(index + 1)}`}
                        className="h-9 min-w-[7rem] flex-[2_1_7rem] rounded-lg text-sm"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`حذف ردیف ${toPersianDigits(index + 1)}`}
                        className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                        onClick={() => removeRow(row.uid)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </section>

      {/* ── per-question notes section ────────────────────────────────── */}
      <section className="space-y-2 border-t border-border/40 pt-4">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setNotesOpen((open) => !open)}
            aria-expanded={notesOpen || state.notes.length <= 3}
            className="flex items-center gap-2 text-sm font-medium"
          >
            یادداشت سؤال‌به‌سؤال
            <Badge
              variant="secondary"
              className="text-[11px] font-normal tabular-nums"
            >
              {toPersianDigits(state.notes.length)}
            </Badge>
            {state.notes.length > 3 && (
              <ChevronDown
                className={cn(
                  'h-4 w-4 text-muted-foreground transition-transform',
                  notesOpen && 'rotate-180',
                )}
              />
            )}
          </button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 rounded-lg px-3 text-xs"
            onClick={() => {
              addNote();
              setNotesOpen(true);
            }}
          >
            <Plus className="ml-1.5 h-3.5 w-3.5" />
            افزودن یادداشت
          </Button>
        </div>
        {state.notes.length > 3 && !notesOpen ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {toPersianDigits(state.notes.length)} یادداشت ثبت شده؛ برای مشاهده
            و ویرایش باز کنید.
          </p>
        ) : (
          <>
            {state.notes.length === 0 && (
              <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs leading-relaxed text-muted-foreground">
                نکات مهم سؤال‌های کلیدی آزمون را اینجا ثبت کنید؛ شمارۀ هر سؤال باید
                یکتا باشد.
              </p>
            )}
            {state.notes.length > 0 && (
              <ul className="divide-y divide-border/40">
                {state.notes.map((note, index) => (
                  <li
                    key={note.uid}
                    className="flex flex-wrap items-center gap-2 py-1.5"
                  >
                    <Input
                      value={toPersianDigits(note.questionNumberRaw)}
                      onChange={(e) =>
                        updateNote(note.uid, {
                          questionNumberRaw: sanitizeIntInput(e.target.value),
                        })
                      }
                      inputMode="numeric"
                      placeholder="۱–۳۰۰"
                      aria-label={`شمارهٔ سؤال یادداشت ${toPersianDigits(index + 1)}`}
                      className="h-9 w-14 shrink-0 rounded-lg text-center text-xs tabular-nums"
                    />
                    <Input
                      value={note.subjectName}
                      onChange={(e) =>
                        updateNote(note.uid, { subjectName: e.target.value })
                      }
                      placeholder="نام درس"
                      maxLength={120}
                      aria-label={`نام درس یادداشت ${toPersianDigits(index + 1)}`}
                      className="h-9 w-32 shrink-0 rounded-lg text-sm"
                    />
                    <Input
                      value={note.note}
                      onChange={(e) =>
                        updateNote(note.uid, { note: e.target.value })
                      }
                      placeholder="نکتۀ این سؤال…"
                      maxLength={2000}
                      aria-label={`متن یادداشت ${toPersianDigits(index + 1)}`}
                      className="h-9 min-w-[10rem] flex-1 rounded-lg text-sm"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`حذف یادداشت ${toPersianDigits(index + 1)}`}
                      className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeNote(note.uid)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      {/* ── actions ───────────────────────────────────────────────────── */}
      <div className="flex items-center justify-start gap-2 border-t border-border/40 pt-3">
        <Button
          type="button"
          onClick={onSubmit}
          disabled={saving}
          className="h-9 px-4 text-sm"
        >
          {saving && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
          {saving ? 'در حال ذخیره…' : submitLabel}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={saving}
        >
          انصراف
        </Button>
      </div>
    </div>
  );
}

/**
 * The advisor's exam-analysis card («تحلیل کارنامه», restart step 6): a list
 * of saved analyses plus a create/edit editor. Saving POSTs a new analysis or
 * PUTs the WHOLE object (set-replace of rows+notes); deletes confirm first.
 */
export function ExamAnalysisCard({ engagementId }: { engagementId: number }) {
  const [analyses, setAnalyses] = useState<ExamAnalysis[] | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  // null = list view; 'create' = new analysis; a number = editing that id.
  const [editorTarget, setEditorTarget] = useState<number | 'create' | null>(
    null,
  );
  const [editorKey, setEditorKey] = useState(0);
  const [formState, setFormState] = useState<AnalysisFormState | null>(null);
  const [saving, setSaving] = useState(false);

  const [pendingDelete, setPendingDelete] = useState<ExamAnalysis | null>(null);
  const [deleting, setDeleting] = useState(false);

  const uidCounter = useRef(0);
  const nextUid = () => {
    uidCounter.current += 1;
    return uidCounter.current;
  };

  useEffect(() => {
    let active = true;
    setError('');
    setAnalyses(null);
    AdvisoryService.getExamAnalyses(engagementId)
      .then((list) => {
        if (active) setAnalyses(list);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId, reloadKey]);

  const refetch = () => {
    AdvisoryService.getExamAnalyses(engagementId)
      .then((list) => setAnalyses(list))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
  };

  // Server orders DESC by exam date; re-sort defensively (nulls last).
  const sorted = useMemo(
    () =>
      [...(analyses ?? [])].sort((a, b) => {
        const dateDiff = (b.examDate ?? '').localeCompare(a.examDate ?? '');
        return dateDiff !== 0 ? dateDiff : b.id - a.id;
      }),
    [analyses],
  );

  const openCreate = () => {
    setFormState(seedAnalysisState(null, nextUid));
    setEditorTarget('create');
    setEditorKey((k) => k + 1);
  };

  const openEdit = (item: ExamAnalysis) => {
    setFormState(seedAnalysisState(item, nextUid));
    setEditorTarget(item.id);
    setEditorKey((k) => k + 1);
  };

  const closeEditor = () => {
    setEditorTarget(null);
    setFormState(null);
  };

  const handleSubmit = async () => {
    if (!formState) return;
    const problem = collectAnalysisProblem(formState);
    if (problem) {
      toast.error(problem);
      return;
    }
    const payload = buildAnalysisPayload(formState);
    setSaving(true);
    try {
      if (editorTarget === 'create') {
        await AdvisoryService.createExamAnalysis(engagementId, payload);
        toast.success('تحلیل کارنامه ثبت شد.');
      } else if (typeof editorTarget === 'number') {
        await AdvisoryService.replaceExamAnalysis(
          engagementId,
          editorTarget,
          payload,
        );
        toast.success('تحلیل کارنامه به‌روزرسانی شد.');
      }
      closeEditor();
      refetch();
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'ذخیرۀ تحلیل کارنامه ناموفق بود.',
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteConfirmed = async () => {
    const target = pendingDelete;
    if (!target) return;
    setDeleting(true);
    try {
      await AdvisoryService.deleteExamAnalysis(engagementId, target.id);
      toast.success('تحلیل کارنامه حذف شد.');
      if (editorTarget === target.id) closeEditor();
      setPendingDelete(null);
      refetch();
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'حذف تحلیل کارنامه ناموفق بود.',
      );
    } finally {
      setDeleting(false);
    }
  };

  const loading = analyses === null && !error;

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="p-5 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <FileSearch className="h-4 w-4 text-primary" />
            تحلیل کارنامه
          </CardTitle>
          <Button
            type="button"
            size="sm"
            variant={editorTarget !== null ? 'outline' : 'default'}
            onClick={() => (editorTarget !== null ? closeEditor() : openCreate())}
            className="h-8 rounded-lg px-3 text-xs"
          >
            {editorTarget !== null ? (
              'بستن فرم'
            ) : (
              <>
                <Plus className="ml-1.5 h-3.5 w-3.5" />
                افزودن تحلیل
              </>
            )}
          </Button>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          متریک‌های کارنامه، تحلیل درس‌به‌درس و نکات سؤال‌به‌سؤال هر آزمون را
          یکجا ثبت کنید.
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

        {/* ── editor ───────────────────────────────────────────────────── */}
        {!error && formState !== null && editorTarget !== null && (
          <div className="rounded-xl border border-primary/40 bg-primary/[0.03] p-4">
            <p className="mb-3 text-sm font-medium">
              {editorTarget === 'create'
                ? 'افزودن تحلیل جدید'
                : 'ویرایش تحلیل'}
            </p>
            <AnalysisEditor
              key={editorKey}
              state={formState}
              onChange={(patch) =>
                setFormState((prev) => (prev ? { ...prev, ...patch } : prev))
              }
              saving={saving}
              submitLabel={editorTarget === 'create' ? 'ذخیره' : 'ذخیرۀ تغییرات'}
              onSubmit={handleSubmit}
              onCancel={closeEditor}
            />
          </div>
        )}

        {/* ── saved analyses ───────────────────────────────────────────── */}
        {!error && !loading && sorted.length === 0 && editorTarget === null && (
          <p className="rounded-lg border border-dashed px-3 py-6 text-center text-xs leading-relaxed text-muted-foreground">
            هنوز تحلیلی ثبت نشده است. بعد از هر آزمون، کارنامۀ دانش‌آموز را
            اینجا تحلیل کنید.
          </p>
        )}

        {!error && sorted.length > 0 && (
          <div className="divide-y divide-border/40">
            {sorted.map((item) => {
              if (editorTarget === item.id) return null;
              return (
                <article key={item.id} className="group space-y-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="text-sm font-semibold leading-relaxed">
                          {item.examNumber !== null
                            ? `کارنامهٔ شمارۀ ${toPersianDigits(item.examNumber)}`
                            : 'کارنامهٔ آزمون'}
                        </span>
                        {item.gradeBand && (
                          <Badge
                            variant="outline"
                            className="text-[11px] font-normal text-muted-foreground"
                          >
                            {GRADE_BAND_LABELS[item.gradeBand]}
                          </Badge>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs tabular-nums text-muted-foreground">
                        {formatJalaliDate(item.examDate)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="ویرایش تحلیل"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        disabled={editorTarget !== null}
                        onClick={() => openEdit(item)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="حذف تحلیل"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        disabled={editorTarget !== null}
                        onClick={() => setPendingDelete(item)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>

                  <AnalysisMetricsGrid item={item} />

                  {item.advisorReport.trim() && (
                    <p className="whitespace-pre-line text-sm leading-relaxed">
                      {item.advisorReport}
                    </p>
                  )}

                  {item.rows.length > 0 && (
                    <div className="space-y-1">
                      <h5 className="text-[11px] font-medium text-muted-foreground">
                        جدول درس‌ها
                      </h5>
                      <AnalysisRowsList rows={item.rows} />
                    </div>
                  )}

                  {item.notes.length > 0 && (
                    <div className="space-y-1">
                      <h5 className="text-[11px] font-medium text-muted-foreground">
                        نکات سؤال‌به‌سؤال ({toPersianDigits(item.notes.length)})
                      </h5>
                      <AnalysisNotesList notes={item.notes} />
                    </div>
                  )}
                </article>
              );
            })}
          </div>
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
            <AlertDialogTitle>حذف تحلیل کارنامه</AlertDialogTitle>
            <AlertDialogDescription>
              این تحلیل همراه با همۀ ردیف‌های درس‌ها و یادداشت‌هایش برای همیشه
              حذف می‌شود و برگشت‌پذیر نیست.
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
