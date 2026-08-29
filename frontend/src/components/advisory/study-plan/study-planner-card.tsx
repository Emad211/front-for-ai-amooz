'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertCircle,
  ChevronDown,
  ClipboardList,
  Loader2,
  Mic,
  Plus,
  RefreshCw,
  Sparkles,
  Square,
  Trash2,
  Undo2,
} from 'lucide-react';

import {
  AdvisoryService,
  type AiPlanDraftResponse,
  type SaveStudyPlanDraftBody,
  type StudyPlanDayNote,
  type StudyPlanOut,
} from '@/services/advisory-service';
import { toEnglishDigits, toPersianDigits } from '@/lib/persian-digits';
import { adherenceColorClass, formatAdherence } from '@/lib/adherence';
import { formatPersianDate } from '@/lib/date-utils';
import { cn } from '@/lib/utils';
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
import { JalaliDatePicker } from '@/components/advisory/jalali-date-picker';
import { Textarea } from '@/components/ui/textarea';

/** Preset horizons plus «دلخواه»; the wire only ever receives a plain count. */
type DurationMode = '7' | '14' | '30' | 'custom';

/** Mastery colors as the wire codes with their chip labels; '' = unset. */
const MASTERY_COLORS: { value: 'RED' | 'YELLOW' | 'GREEN'; label: string }[] = [
  { value: 'RED', label: 'قرمز' },
  { value: 'YELLOW', label: 'زرد' },
  { value: 'GREEN', label: 'سبز' },
];

/** Mastery-color wire code → dot class (mirrors study-feed-card). */
const MASTERY_DOT_CLASS: Record<string, string> = {
  RED: 'bg-red-500',
  YELLOW: 'bg-yellow-400',
  GREEN: 'bg-emerald-500',
};

/** Segmented-chip styles (shared design language L5): selected = primary
 * tint, idle = muted ghost. Applied over `variant="outline"` so the base
 * border/shape primitives stay in charge. */
const SEGMENT_SELECTED =
  'h-8 rounded-lg border-primary bg-primary/10 px-3 text-xs font-medium text-primary shadow-none hover:bg-primary/15 hover:text-primary';
const SEGMENT_IDLE =
  'h-8 rounded-lg px-3 text-xs text-muted-foreground hover:bg-muted/40 hover:text-muted-foreground';

/** The four note fields of one day, in render order. */
const DAY_NOTE_FIELDS = [
  { key: 'school', label: 'مدرسه' },
  { key: 'exams', label: 'امتحان' },
  { key: 'konkurClass', label: 'کلاس کنکور' },
  { key: 'preReading', label: 'پیش‌خوانی' },
] as const;

/** Persian weekdays, Saturday-first, with the one-char initial used by the
 * day pills and the full name used by titles/headers. */
const WEEKDAYS = [
  { initial: 'ش', name: 'شنبه' },
  { initial: 'ی', name: 'یکشنبه' },
  { initial: 'د', name: 'دوشنبه' },
  { initial: 'س', name: 'سه‌شنبه' },
  { initial: 'چ', name: 'چهارشنبه' },
  { initial: 'پ', name: 'پنجشنبه' },
  { initial: 'ج', name: 'جمعه' },
] as const;

/** Weekday of plan day `offset` (0-based): derived from the start date when
 * one is set; otherwise the fixed Saturday-first sequence as a neutral
 * fallback (display-only — never feeds state or the wire). */
function weekdayForOffset(startDate: string, offset: number) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(startDate);
  if (!match) return WEEKDAYS[offset % WEEKDAYS.length];
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );
  date.setDate(date.getDate() + offset);
  // JS getDay(): 0 = Sunday … 6 = Saturday → Saturday-first index.
  return WEEKDAYS[(date.getDay() + 1) % WEEKDAYS.length];
}

/** «شنبه ۱ شهریور» — display-only Jalali label for a plan-day subheader.
 * '' when `iso` isn't a valid ISO date. */
function formatJalaliDayLabel(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return '';
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('fa-IR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    calendar: 'persian',
    numberingSystem: 'arabext',
  }).format(date);
}

type DayPillsProps = {
  /** Currently selected plan day (0-based `dayOffset`). */
  value: number;
  onChange: (offset: number) => void;
  /** Plan start (ISO) — anchors each pill's true weekday. */
  startDate: string;
  /** Plan horizon in days; null (invalid input) renders nothing. */
  durationDays: number | null;
};

/** Segmented weekday picker replacing the old «روز N» dropdown: one pill per
 * plan day labeled with its weekday initial (the default 7-day horizon yields
 * exactly the ش·ی·د·س·چ·پ·ج row); the full day name rides on `title` for a11y.
 * Pure view layer — selection stays the row's existing `dayOffset`. */
function DayPills({ value, onChange, startDate, durationDays }: DayPillsProps) {
  if (durationDays === null) return null;
  return (
    <div
      role="radiogroup"
      aria-label="روز برنامه"
      className="flex flex-wrap items-center gap-1"
    >
      {Array.from({ length: durationDays }, (_, offset) => {
        const weekday = weekdayForOffset(startDate, offset);
        const selected = value === offset;
        return (
          <button
            key={offset}
            type="button"
            role="radio"
            aria-checked={selected}
            title={`${weekday.name} — روز ${toPersianDigits(offset + 1)}`}
            onClick={() => onChange(offset)}
            className={cn(
              'inline-flex h-8 w-9 items-center justify-center rounded-lg border text-xs transition-colors',
              selected
                ? 'border-primary bg-primary/10 font-medium text-primary'
                : 'border-transparent text-muted-foreground hover:bg-muted/40',
            )}
          >
            {weekday.initial}
          </button>
        );
      })}
    </div>
  );
}

/** Read-only rendering of a PUBLISHED plan's items grouped by day: a Jalali
 * subheader per day, then compact rows (subject — topic — minutes — mastery
 * dot, plus a test-minutes chip when set). Display only — drafts render
 * exactly as before and no wire shape is touched. */
function PublishedPlanItems({ items }: { items: StudyPlanOut['items'] }) {
  const groups = new Map<number, StudyPlanOut['items']>();
  for (const item of [...items].sort((a, b) => a.dayOffset - b.dayOffset)) {
    const bucket = groups.get(item.dayOffset);
    if (bucket) bucket.push(item);
    else groups.set(item.dayOffset, [item]);
  }
  return (
    <div className="space-y-3 rounded-lg bg-muted/20 p-3">
      {[...groups.entries()].map(([offset, dayItems]) => {
        const dayLabel =
          formatJalaliDayLabel(dayItems[0]?.date ?? '') ||
          `روز ${toPersianDigits(offset + 1)}`;
        return (
          <section key={offset}>
            <p className="pb-0.5 text-[11px] font-medium text-muted-foreground">
              {dayLabel}
            </p>
            <ul className="divide-y divide-border/40">
              {dayItems.map((item, index) => (
                <li
                  key={`${offset}-${index}`}
                  className="flex flex-wrap items-center gap-x-2 gap-y-0.5 py-1.5 text-xs first:pt-1 last:pb-0"
                >
                  <span className="font-medium">{item.name}</span>
                  {item.topic && (
                    <span className="min-w-0 truncate text-muted-foreground">
                      — {item.topic}
                    </span>
                  )}
                  <span className="tabular-nums text-muted-foreground">
                    — {toPersianDigits(item.plannedMinutes)} دقیقه
                  </span>
                  {item.masteryColor && MASTERY_DOT_CLASS[item.masteryColor] && (
                    <span
                      aria-hidden
                      className={cn(
                        'h-2 w-2 shrink-0 rounded-full',
                        MASTERY_DOT_CLASS[item.masteryColor],
                      )}
                    />
                  )}
                  {item.testMinutes != null && (
                    <Badge
                      variant="secondary"
                      className="px-1.5 text-[11px] font-normal tabular-nums"
                    >
                      تست {toPersianDigits(item.testMinutes)} دقیقه
                    </Badge>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

/** One editable row. `minutes`/`testMinutes` stay raw strings so half-typed
 * Persian-digit input never fights the cursor; both are parsed on save. */
type PlannerRow = {
  uid: number;
  /** 0-based on the wire; the UI shows «روز N» where N = dayOffset + 1. */
  dayOffset: number;
  subjectId: number | null;
  minutes: string;
  topic: string;
  unitLabel: string;
  testMinutes: string;
  masteryColor: '' | 'RED' | 'YELLOW' | 'GREEN';
};

/** Persian-digit-tolerant digit sanitizer (same pattern as study-log). */
function sanitizeDigits(raw: string): string {
  return toEnglishDigits(raw).replace(/\D/g, '');
}

/** ISO `YYYY-MM-DD` + whole days → ISO date, for day-group subheaders only
 * (display-only; never feeds state or the wire). '' when `iso` isn't ISO. */
function shiftIsoDate(iso: string, days: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return '';
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  date.setDate(date.getDate() + days);
  return [
    String(date.getFullYear()),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
}

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
 *
 * Density contract: each row renders as one compact bar (weekday pills /
 * subject / minutes / topic); enrichment fields collapse behind a per-row
 * toggle and day-notes behind per-day accordions — all view-only state with
 * zero wire impact, so the default add flow stays compact.
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
  // Per-day note accordion: which days expose their 4-field editor. All
  // collapsed by default so the section reads as seven scannable rows instead
  // of a wall of unlabeled inputs.
  const [dayNotes, setDayNotes] = useState<Record<string, StudyPlanDayNote>>({});
  const [openNoteDays, setOpenNoteDays] = useState<ReadonlySet<number>>(new Set());
  // View-only density state (no wire impact): which rows expose their
  // enrichment editor, mirroring the day-notes accordion pattern.
  const [expandedRows, setExpandedRows] = useState<ReadonlySet<number>>(new Set());

  // ── Risman steps 5+6: the AI draftsman ──────────────────────────────────────
  // Collapsed by default (density contract L5); opening it is the only way to
  // reach the generator, and a successful run REPLACES the editor rows with
  // the fresh draft (the server already replaced the stored DRAFT slot).
  const [aiOpen, setAiOpen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  // MediaRecorder lives in a ref (imperative lifecycle) while only the
  // recording flag drives the UI; chunks accumulate across dataavailable.
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordChunks = useRef<Blob[]>([]);

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
        const catalog = Array.isArray(resp.subjects) ? resp.subjects : [];
        const selectedIds = new Set(
          Array.isArray(resp.selectedSubjectIds) ? resp.selectedSubjectIds : [],
        );
        // Only ACTIVE selections may be planned; the derived curriculum lists
        // candidates, `selectedSubjectIds` marks what is actually focusable.
        setSubjects(
          catalog
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
                topic: item.topic ?? '',
                unitLabel: item.unitLabel ?? '',
                testMinutes:
                  item.testMinutes === null || item.testMinutes === undefined
                    ? ''
                    : String(item.testMinutes),
                masteryColor: item.masteryColor ?? '',
              })),
            );
            setDayNotes(draft.dayNotes ?? {});
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
      // Restart step 4: empty test-minutes means «not set»; a filled field must
      // be an integer inside 0..480 — the server's exact message, mirrored.
      if (row.testMinutes.trim() !== '') {
        const testMinutes = Number(sanitizeDigits(row.testMinutes));
        if (
          !Number.isInteger(testMinutes) ||
          testMinutes < 0 ||
          testMinutes > 480
        ) {
          return 'زمان تست باید بین ۰ تا ۴۸۰ دقیقه باشد.';
        }
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
      const item: SaveStudyPlanDraftBody['items'][number] = {
        dayOffset: row.dayOffset,
        subjectId,
        plannedMinutes: minutes,
      };
      // Enrichment keys ride along only when the advisor filled them, so an
      // untouched row stores the column defaults instead of empty noise.
      if (row.topic.trim()) item.topic = row.topic.trim();
      if (row.unitLabel.trim()) item.unitLabel = row.unitLabel.trim();
      if (row.testMinutes.trim() !== '') {
        item.testMinutes = Number(sanitizeDigits(row.testMinutes));
      }
      if (row.masteryColor) item.masteryColor = row.masteryColor;
      items.push(item);
    }
    items.sort((a, b) => a.dayOffset - b.dayOffset || a.subjectId - b.subjectId);

    // Wire rule: an all-empty grid OMITS dayNotes entirely, because the server
    // treats an absent key as «keep stored notes» and only a present key
    // (even {}) replaces them.
    const notes: Record<string, StudyPlanDayNote> = {};
    for (const [dayKey, block] of Object.entries(dayNotes)) {
      const cleaned: StudyPlanDayNote = {};
      for (const { key } of DAY_NOTE_FIELDS) {
        const value = (block?.[key] ?? '').trim();
        if (value) cleaned[key] = value;
      }
      if (Object.keys(cleaned).length > 0) notes[dayKey] = cleaned;
    }

    return {
      startDate,
      durationDays: durationDays ?? 0,
      items,
      ...(Object.keys(notes).length > 0 ? { dayNotes: notes } : {}),
    };
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

  // ── Risman steps 5+6 handlers ────────────────────────────────────────────────

  /** Swap the editor over to the freshly created AI draft. The response carries
   * the whole PlanOut, so the editor is filled directly (no refetch race) and
   * the one-shot prefill guard is satisfied — the advisor then reviews/edits
   * and publishes through the ordinary doors. */
  const applyAiDraft = (resp: AiPlanDraftResponse) => {
    toast.success(resp.detail || 'پیش‌نویس هوشمند ساخته شد.');
    setAiPrompt('');
    setAiOpen(false);
    setStartDate(resp.plan.startDate);
    // The endpoint hard-caps the horizon at this week's 7 days.
    setDurationMode('7');
    setCustomDuration('');
    setRows(
      resp.plan.items.map((item) => ({
        uid: nextUid(),
        dayOffset: item.dayOffset,
        subjectId: item.subjectId,
        minutes: String(item.plannedMinutes),
        topic: item.topic ?? '',
        unitLabel: item.unitLabel ?? '',
        testMinutes:
          item.testMinutes === null || item.testMinutes === undefined
            ? ''
            : String(item.testMinutes),
        masteryColor: item.masteryColor ?? '',
      })),
    );
    draftPrefilled.current = true;
    refetchPlans();
  };

  const handleAiDraft = async () => {
    const prompt = aiPrompt.trim();
    if (!prompt) {
      toast.error('متن درخواست را بنویسید یا پیام صوتی بگذارید.');
      return;
    }
    if (prompt.length > 2000) {
      toast.error('متن درخواست حداکثر ۲۰۰۰ نویسه است.');
      return;
    }
    setAiBusy(true);
    try {
      applyAiDraft(await AdvisoryService.draftAiPlan(engagementId, prompt));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'تولید پیش‌نویس هوشمند ناموفق بود.');
    } finally {
      setAiBusy(false);
    }
  };

  const handleAiVoice = async (blob: Blob, mimeType: string) => {
    if (blob.size > 5 * 1024 * 1024) {
      toast.error('حجم پیام صوتی حداکثر ۵ مگابایت است.');
      return;
    }
    setAiBusy(true);
    try {
      applyAiDraft(
        await AdvisoryService.draftAiPlanFromVoice(engagementId, blob, mimeType),
      );
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'تولید پیش‌نویس هوشمند ناموفق بود.');
    } finally {
      setAiBusy(false);
    }
  };

  const startRecording = async () => {
    if (
      typeof navigator === 'undefined' ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === 'undefined'
    ) {
      toast.error('مرورگر شما از ضبط صدا پشتیبانی نمی‌کند.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      recordChunks.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordChunks.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        recorderRef.current = null;
        setRecording(false);
        const mimeType = recorder.mimeType || 'audio/webm';
        const blob = new Blob(recordChunks.current, { type: mimeType });
        recordChunks.current = [];
        if (!blob.size) {
          toast.error('صدایی ضبط نشد؛ دوباره تلاش کنید.');
          return;
        }
        void handleAiVoice(blob, mimeType);
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      toast.error('دسترسی به میکروفون داده نشد.');
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
  };

  const addRow = () => {
    setRows((prev) => [
      ...prev,
      {
        uid: nextUid(),
        dayOffset: 0,
        subjectId: null,
        minutes: '',
        topic: '',
        unitLabel: '',
        testMinutes: '',
        masteryColor: '',
      },
    ]);
  };

  const setDayNote = (
    dayKey: string,
    field: (typeof DAY_NOTE_FIELDS)[number]['key'],
    value: string,
  ) => {
    setDayNotes((prev) => ({
      ...prev,
      [dayKey]: { ...prev[dayKey], [field]: value },
    }));
  };

  const updateRow = (uid: number, patch: Partial<Omit<PlannerRow, 'uid'>>) => {
    setRows((prev) => prev.map((row) => (row.uid === uid ? { ...row, ...patch } : row)));
  };

  const toggleRowExpanded = (uid: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(uid)) {
        next.delete(uid);
      } else {
        next.add(uid);
      }
      return next;
    });
  };

  const toggleNoteDay = (offset: number) => {
    setOpenNoteDays((prev) => {
      const next = new Set(prev);
      if (next.has(offset)) {
        next.delete(offset);
      } else {
        next.add(offset);
      }
      return next;
    });
  };

  const removeRow = (uid: number) => {
    setRows((prev) => prev.filter((row) => row.uid !== uid));
  };

  const busy = saving || publishing || aiBusy;

  // Display-only grouping: rows bucketed by day ascending, insertion order
  // preserved inside each day. Renders every row even while the horizon is
  // momentarily invalid — the strand-dropping effect owns that cleanup.
  const rowGroups = (() => {
    const buckets = new Map<number, PlannerRow[]>();
    for (const row of rows) {
      const bucket = buckets.get(row.dayOffset);
      if (bucket) {
        bucket.push(row);
      } else {
        buckets.set(row.dayOffset, [row]);
      }
    }
    return [...buckets.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([offset, groupRows]) => ({ offset, rows: groupRows }));
  })();

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="p-5 pb-4">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <ClipboardList className="h-4 w-4 text-primary" />
          برنامه‌ریزی مطالعه
          <span className="ms-auto text-xs font-normal tabular-nums text-muted-foreground">
            مجموع برنامه‌ریزی‌شده: {toPersianDigits(plannedTotal)} دقیقه
          </span>
        </CardTitle>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          بازه‌ای دلخواه تعیین کنید و برای هر روز، درس و دقیقه‌ی مطالعه بگذارید.
          انتشار، آخرین تغییرات را ذخیره و برنامه را برای دانش‌آموز نمایان می‌کند.
        </p>
      </CardHeader>

      <CardContent className="space-y-4 p-5 pt-0 sm:p-5 sm:pt-0">
        {/* ── Risman steps 5+6: the AI draftsman, collapsed by default ──────── */}
        <div className="rounded-xl border border-dashed border-border/60 p-3">
          <button
            type="button"
            onClick={() => setAiOpen((v) => !v)}
            aria-expanded={aiOpen}
            className="flex w-full items-center gap-2 text-start text-xs font-medium text-foreground"
          >
            <Sparkles className="h-4 w-4 text-primary" />
            ساخت پیش‌نویس با هوش مصنوعی
            {aiOpen && (
              <span className="hidden text-[11px] font-normal text-muted-foreground sm:inline">
                پیش‌نویس فعلی جایگزین می‌شود
              </span>
            )}
            <ChevronDown
              className={cn(
                'ms-auto h-4 w-4 text-muted-foreground transition-transform',
                aiOpen && 'rotate-180',
              )}
            />
          </button>
          {aiOpen && (
            <div className="mt-3 space-y-2">
              <Textarea
                value={aiPrompt}
                onChange={(event) => setAiPrompt(event.target.value)}
                dir="rtl"
                rows={3}
                maxLength={2000}
                disabled={busy}
                placeholder='مثلاً: «زهرا این هفته روزی ۲ ساعت ریاضی و ۱ ساعت ادبیات بخواند.»'
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" size="sm" onClick={handleAiDraft} disabled={busy}>
                  {aiBusy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  تولید پیش‌نویس
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={recording ? stopRecording : startRecording}
                  disabled={busy}
                  aria-pressed={recording}
                >
                  {recording ? (
                    <>
                      <Square className="h-4 w-4 animate-pulse text-red-500" />
                      پایان ضبط
                    </>
                  ) : (
                    <>
                      <Mic className="h-4 w-4" />
                      پیام صوتی
                    </>
                  )}
                </Button>
                {recording && (
                  <span className="text-[11px] font-medium text-red-500">در حال ضبط…</span>
                )}
                <span className="ms-auto text-[11px] tabular-nums text-muted-foreground">
                  {toPersianDigits(aiPrompt.length)}/۲۰۰۰
                </span>
              </div>
            </div>
          )}
        </div>

        {/* ── horizon: start date + duration in one compact meta row ─────── */}
        <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
          <div className="space-y-1">
            <label htmlFor="study-plan-start" className="text-[11px] font-medium text-muted-foreground">
              تاریخ شروع
            </label>
            <JalaliDatePicker
              id="study-plan-start"
              value={startDate}
              onChange={setStartDate}
              minDate={startedOn}
            />
          </div>
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-muted-foreground">طول برنامه</span>
            <div className="flex flex-wrap items-center gap-1.5">
              {(['7', '14', '30'] as const).map((value) => (
                <Button
                  key={value}
                  type="button"
                  variant={durationMode === value ? 'default' : 'outline'}
                  onClick={() => setDurationMode(value)}
                  aria-pressed={durationMode === value}
                  className={durationMode === value ? SEGMENT_SELECTED : SEGMENT_IDLE}
                >
                  {toPersianDigits(value)} روزه
                </Button>
              ))}
              <Button
                type="button"
                variant={durationMode === 'custom' ? 'default' : 'outline'}
                onClick={() => setDurationMode('custom')}
                aria-pressed={durationMode === 'custom'}
                className={durationMode === 'custom' ? SEGMENT_SELECTED : SEGMENT_IDLE}
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
                  className="h-9 w-24 rounded-lg"
                />
              )}
            </div>
          </div>
        </div>

        {/* ── rows editor: one compact bar per row, grouped by day ───────── */}
        <div className="space-y-3 rounded-xl border border-border/40 p-4">
          <span className="text-sm font-medium">ردیف‌های برنامه</span>

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
                <Skeleton key={i} className="h-9 w-full rounded-lg" />
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
              {rows.length === 0 && (
                <p className="py-1 text-center text-xs text-muted-foreground">
                  ردیفی اضافه نشده است.
                </p>
              )}

              {rowGroups.map((group) => {
                const groupDate = shiftIsoDate(startDate, group.offset);
                return (
                  <section key={group.offset} className="space-y-0.5">
                    {/* Day subheader: «روز N — تاریخ» when a start date exists. */}
                    <p className="text-xs font-medium text-muted-foreground">
                      روز {toPersianDigits(group.offset + 1)}
                      {groupDate && <> — {formatPersianDate(groupDate)}</>}
                    </p>
                    <ul className="divide-y divide-border/40">
                      {group.rows.map((row) => {
                        const expanded = expandedRows.has(row.uid);
                        const hasEnrichment =
                          row.unitLabel.trim() !== '' ||
                          row.testMinutes.trim() !== '' ||
                          row.masteryColor !== '';
                        return (
                          <li key={row.uid} className="py-2 first:pt-1 last:pb-0">
                            {/* Quick-add bar: the four constant fields on one
                            line; everything else hides behind the toggle. */}
                            <div className="flex flex-wrap items-center gap-2">
                              <DayPills
                                value={row.dayOffset}
                                onChange={(offset) =>
                                  updateRow(row.uid, { dayOffset: offset })
                                }
                                startDate={startDate}
                                durationDays={durationDays}
                              />

                              {/* dir="rtl" on the Root: Radix portals the
                              content to <body>, where its own dir context
                              (default ltr without a DirectionProvider) would
                              override the document's rtl and left-align the
                              value. */}
                              <Select
                                dir="rtl"
                                value={row.subjectId === null ? '' : String(row.subjectId)}
                                onValueChange={(value) => updateRow(row.uid, { subjectId: Number(value) })}
                              >
                                <SelectTrigger
                                  aria-label="درس"
                                  className="h-9 w-full rounded-lg text-xs sm:w-auto sm:min-w-[9rem] sm:flex-1"
                                >
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
                                className="h-9 w-20 rounded-lg text-center text-xs tabular-nums"
                              />

                              <Input
                                value={row.topic}
                                onChange={(e) => updateRow(row.uid, { topic: e.target.value })}
                                placeholder="موضوع"
                                maxLength={200}
                                aria-label="موضوع"
                                className="h-9 w-full rounded-lg text-xs sm:w-auto sm:min-w-[10rem] sm:flex-1"
                              />

                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                aria-label={expanded ? 'بستن جزئیات' : 'جزئیات بیشتر'}
                                aria-expanded={expanded}
                                className="relative h-9 w-9 shrink-0 text-muted-foreground hover:text-foreground"
                                onClick={() => toggleRowExpanded(row.uid)}
                              >
                                <ChevronDown
                                  className={`h-4 w-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
                                />
                                {hasEnrichment && !expanded && (
                                  <span
                                    aria-hidden
                                    className="absolute end-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-primary"
                                  />
                                )}
                              </Button>

                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                aria-label="حذف ردیف"
                                className="h-9 w-9 shrink-0 text-muted-foreground hover:text-destructive"
                                onClick={() => removeRow(row.uid)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>

                            {/* Per-row enrichment editor: unit / test-minutes /
                            mastery color — collapsed until asked for. */}
                            {expanded && (
                              <div className="mt-2 grid grid-cols-1 gap-2 rounded-lg bg-muted/30 p-2 sm:grid-cols-3">
                                <Input
                                  value={row.unitLabel}
                                  onChange={(e) => updateRow(row.uid, { unitLabel: e.target.value })}
                                  placeholder="واحد"
                                  maxLength={60}
                                  aria-label="واحد"
                                  className="h-9 rounded-lg text-xs"
                                />
                                <Input
                                  value={row.testMinutes}
                                  onChange={(e) =>
                                    updateRow(row.uid, { testMinutes: sanitizeDigits(e.target.value) })
                                  }
                                  placeholder="زمان تست (دقیقه)"
                                  inputMode="numeric"
                                  aria-label="زمان تست بر حسب دقیقه"
                                  className="h-9 rounded-lg text-center text-xs tabular-nums"
                                />
                                <Select
                                  dir="rtl"
                                  value={row.masteryColor}
                                  onValueChange={(value) =>
                                    updateRow(row.uid, {
                                      masteryColor: value as PlannerRow['masteryColor'],
                                    })
                                  }
                                >
                                  <SelectTrigger aria-label="رنگ تسلط" className="h-9 rounded-lg text-xs">
                                    <SelectValue placeholder="رنگ تسلط…" />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {MASTERY_COLORS.map((color) => (
                                      <SelectItem key={color.value} value={color.value}>
                                        {color.label}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}

              <div className="flex flex-wrap items-center gap-2 pt-1">
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
              </div>
            </>
          )}
        </div>

        {/* ── day notes: one collapsible row per day ──────────────────────── */}
        <div className="rounded-xl border border-border/40">
          <div className="flex items-center justify-between gap-2 px-4 pt-3">
            <span className="text-sm font-medium">یادداشت روزها</span>
            <Badge variant="secondary" className="px-1.5 text-[11px] font-normal">
              {toPersianDigits(durationDays === null ? 7 : Math.min(durationDays, 7))} روز
            </Badge>
          </div>
          <p className="px-4 pb-3 text-xs leading-relaxed text-muted-foreground">
            یادداشت هر روز: مدرسه، امتحان، کلاس کنکور و پیش‌خوانی
          </p>
          <div className="divide-y divide-border/40 border-t border-border/40 px-4">
            {(durationDays === null
              ? []
              : Array.from({ length: Math.min(durationDays, 7) }, (_, i) => i)
            ).map((offset) => {
              const dayKey = String(offset);
              const open = openNoteDays.has(offset);
              const filledCount = DAY_NOTE_FIELDS.filter(
                ({ key }) => (dayNotes[dayKey]?.[key] ?? '').trim() !== '',
              ).length;
              const weekday = weekdayForOffset(startDate, offset);
              return (
                <div key={dayKey}>
                  <button
                    type="button"
                    onClick={() => toggleNoteDay(offset)}
                    aria-expanded={open}
                    className="flex w-full items-center justify-between gap-2 py-2.5 text-right"
                  >
                    <span className="flex items-center gap-2 text-xs font-medium">
                      روز {toPersianDigits(offset + 1)} — {weekday.name}
                      <Badge
                        variant="secondary"
                        className="px-1.5 text-[11px] font-normal tabular-nums"
                      >
                        {toPersianDigits(filledCount)} از{' '}
                        {toPersianDigits(DAY_NOTE_FIELDS.length)}
                      </Badge>
                    </span>
                    <ChevronDown
                      className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`}
                    />
                  </button>
                  {open && (
                    <div className="grid grid-cols-1 gap-2 pb-3 sm:grid-cols-2">
                      {DAY_NOTE_FIELDS.map(({ key, label }) => (
                        <div key={key} className="space-y-1">
                          <label
                            htmlFor={`day-note-${offset}-${key}`}
                            className="text-[11px] font-medium text-muted-foreground"
                          >
                            {label}
                          </label>
                          <Input
                            id={`day-note-${offset}-${key}`}
                            value={dayNotes[dayKey]?.[key] ?? ''}
                            onChange={(e) => setDayNote(dayKey, key, e.target.value)}
                            maxLength={120}
                            aria-label={`${label} — روز ${toPersianDigits(offset + 1)}`}
                            className="h-9 rounded-lg text-xs"
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {durationDays !== null && durationDays > 7 && (
            <p className="border-t border-border/40 px-4 py-3 text-xs leading-relaxed text-muted-foreground">
              یادداشت روزها برای هفتۀ اول برنامه ثبت می‌شود.
            </p>
          )}
        </div>

        {/* ── actions: primary publish leads, start-aligned ───────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" onClick={handlePublish} disabled={busy} className="h-9 px-4 text-sm">
            {publishing && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
            انتشار
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={handleSave} disabled={busy}>
            {saving && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
            ذخیره پیش‌نویس
          </Button>
        </div>

        {/* ── saved plans: tight divided list ─────────────────────────────── */}
        <div className="space-y-2 border-t border-border/40 pt-4">
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

          {!plans && !plansError && <Skeleton className="h-10 w-full rounded-lg" />}

          {plans && plans.length === 0 && (
            <p className="py-4 text-center text-xs text-muted-foreground">
              هنوز برنامه‌ای ثبت نشده است.
            </p>
          )}

          {plans && plans.length > 0 && (
            <ul className="divide-y divide-border/40">
              {[...plans]
                .sort((a, b) => a.startDate.localeCompare(b.startDate))
                .map((plan) => (
                  <li key={plan.id} className="space-y-2 py-2.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge
                            variant={plan.status === 'PUBLISHED' ? 'default' : 'outline'}
                            className="text-[11px] font-normal"
                          >
                            {plan.status === 'PUBLISHED' ? 'منتشرشده' : 'پیش‌نویس'}
                          </Badge>
                          {/* Step 8: per-plan adherence; quiet-null for drafts and
                          plans with no elapsed items yet (percent is null). */}
                          {plan.percent != null && (
                            <Badge
                              variant="outline"
                              className={`text-[11px] font-normal tabular-nums ${adherenceColorClass(plan.percent)}`}
                            >
                              پایبندی {formatAdherence(plan.percent)}
                            </Badge>
                          )}
                          <span className="text-xs tabular-nums text-muted-foreground">
                            {toPersianDigits(plan.durationDays)} روز ·{' '}
                            {toPersianDigits(plan.items.length)} ردیف
                          </span>
                        </div>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          از {formatPersianDate(plan.startDate)} تا{' '}
                          {formatPersianDate(plan.endDate)}
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
                    </div>
                    {/* Published plans are readable here, not just cancellable:
                    their items render read-only, grouped by day. */}
                    {plan.status === 'PUBLISHED' && plan.items.length > 0 && (
                      <PublishedPlanItems items={plan.items} />
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
