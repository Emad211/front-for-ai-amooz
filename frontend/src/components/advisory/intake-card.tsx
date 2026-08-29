'use client';

import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertCircle,
  Contact,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';

import {
  AdvisoryService,
  type IntakePayload,
} from '@/services/advisory-service';
import { toEnglishDigits, toPersianDigits } from '@/lib/persian-digits';
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

/** Wire weekday codes with their Persian names (0 = شنبه). */
const WEEKDAY_LABELS = [
  'شنبه',
  'یکشنبه',
  'دوشنبه',
  'سه‌شنبه',
  'چهارشنبه',
  'پنجشنبه',
  'جمعه',
] as const;

const MAX_CLASSES = 10;

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;
const GPA_PATTERN = /^\d{1,2}(\.\d{1,2})?$/;

type ClassRow = {
  uid: number;
  name: string;
  teacher: string;
  weekday: number;
  /** '' = unset; otherwise `HH:MM` from the native time input. */
  startTime: string;
  endTime: string;
};

function sanitizeMinutesInput(raw: string): string {
  return toEnglishDigits(raw).replace(/\D/g, '');
}

/** Digit-tolerant GPA sanitizer: Persian digits → ASCII, «٫» → '.', at most
 * one decimal point kept. */
function sanitizeGpaInput(raw: string): string {
  const cleaned = toEnglishDigits(raw)
    .replace(/[٫]/g, '.')
    .replace(/[^0-9.]/g, '');
  const firstDot = cleaned.indexOf('.');
  if (firstDot === -1) return cleaned;
  return (
    cleaned.slice(0, firstDot + 1) + cleaned.slice(firstDot + 1).replace(/\./g, '')
  );
}

function parseGpa(raw: string): number | null {
  if (!GPA_PATTERN.test(raw)) return null;
  const value = Number(raw);
  if (value < 0 || value > 20) return null;
  return value;
}

function parseFreeDayMinutes(raw: string): number | null {
  if (!/^\d+$/.test(raw)) return null;
  const value = Number(raw);
  if (value > 1440) return null;
  return value;
}

/**
 * The shared intake form body used by BOTH the advisor card and the student
 * mirror («شناخت»). Owns every field's state, validation, and Persian copy so
 * the two surfaces cannot drift; callers only wire load/save.
 *
 * State is seeded ONCE from `initial` (the planner's draftPrefilled lesson):
 * later prop changes never clobber edits in progress. `onSave` receives the
 * whole set-replace payload — classes carry their array index as `order`.
 */
export function IntakeProfileForm({
  initial,
  saving,
  onSave,
}: {
  initial: IntakePayload;
  saving: boolean;
  onSave: (payload: IntakePayload) => Promise<void>;
}) {
  const [school, setSchool] = useState(initial.school);
  const [city, setCity] = useState(initial.city);
  const [lastGpaRaw, setLastGpaRaw] = useState(
    initial.lastGpa === null ? '' : String(initial.lastGpa),
  );
  const [targetMajor, setTargetMajor] = useState(initial.targetMajor);
  const [targetUniversity, setTargetUniversity] = useState(initial.targetUniversity);
  const [mockExamInstitute, setMockExamInstitute] = useState(
    initial.mockExamInstitute,
  );
  const [freeDayMinutesRaw, setFreeDayMinutesRaw] = useState(
    initial.freeDayMinutes === null ? '' : String(initial.freeDayMinutes),
  );
  const seedRows = (): ClassRow[] =>
    initial.classes.map((c, index) => ({
      uid: index + 1,
      name: c.name,
      teacher: c.teacher,
      weekday: c.weekday >= 0 && c.weekday <= 6 ? c.weekday : 0,
      startTime: c.startTime ?? '',
      endTime: c.endTime ?? '',
    }));
  const [rows, setRows] = useState<ClassRow[]>(seedRows);

  // uids continue past the seeded rows so addRow never collides with them.
  const uidCounter = useRef(initial.classes.length);

  const nextUid = () => {
    uidCounter.current += 1;
    return uidCounter.current;
  };

  const updateRow = (uid: number, patch: Partial<Omit<ClassRow, 'uid'>>) => {
    setRows((prev) => prev.map((row) => (row.uid === uid ? { ...row, ...patch } : row)));
  };

  const removeRow = (uid: number) => {
    setRows((prev) => prev.filter((row) => row.uid !== uid));
  };

  const addRow = () => {
    if (rows.length >= MAX_CLASSES) return;
    setRows((prev) => [
      ...prev,
      { uid: nextUid(), name: '', teacher: '', weekday: 0, startTime: '', endTime: '' },
    ]);
  };

  const collectProblem = (): string | null => {
    if (lastGpaRaw.trim() !== '' && parseGpa(lastGpaRaw.trim()) === null) {
      return 'معدل سال گذشته باید عددی بین ۰ و ۲۰ باشد.';
    }
    if (
      freeDayMinutesRaw.trim() !== '' &&
      parseFreeDayMinutes(freeDayMinutesRaw.trim()) === null
    ) {
      return 'میانگین مطالعۀ روز آزاد باید عددی بین ۰ و ۱۴۴۰ دقیقه باشد.';
    }
    for (const row of rows) {
      if (!row.name.trim()) return 'نام کلاس هر ردیف را بنویسید.';
      if (row.startTime && !TIME_PATTERN.test(row.startTime)) {
        return 'قالب ساعت شروع باید HH:MM باشد.';
      }
      if (row.endTime && !TIME_PATTERN.test(row.endTime)) {
        return 'قالب ساعت پایان باید HH:MM باشد.';
      }
      if (
        row.startTime &&
        row.endTime &&
        TIME_PATTERN.test(row.startTime) &&
        TIME_PATTERN.test(row.endTime) &&
        row.endTime <= row.startTime
      ) {
        return 'ساعت پایان کلاس باید بعد از ساعت شروع باشد.';
      }
    }
    return null;
  };

  const buildPayload = (): IntakePayload => ({
    school: school.trim(),
    city: city.trim(),
    lastGpa: lastGpaRaw.trim() === '' ? null : parseGpa(lastGpaRaw.trim()),
    targetMajor: targetMajor.trim(),
    targetUniversity: targetUniversity.trim(),
    mockExamInstitute: mockExamInstitute.trim(),
    freeDayMinutes:
      freeDayMinutesRaw.trim() === ''
        ? null
        : parseFreeDayMinutes(freeDayMinutesRaw.trim()),
    classes: rows.map((row, index) => ({
      name: row.name.trim(),
      teacher: row.teacher.trim(),
      weekday: row.weekday,
      startTime: row.startTime || null,
      endTime: row.endTime || null,
      order: index,
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

  const atCap = rows.length >= MAX_CLASSES;

  return (
    <div className="space-y-4">
      {/* ── basic profile fields ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-x-3 gap-y-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="intake-school" className="text-[11px] font-medium text-muted-foreground">
            مدرسه
          </label>
          <Input
            id="intake-school"
            value={school}
            onChange={(e) => setSchool(e.target.value)}
            maxLength={120}
            placeholder="مثلاً دبیرستان انرژی اتمی"
            className="h-9 rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="intake-city" className="text-[11px] font-medium text-muted-foreground">
            شهر
          </label>
          <Input
            id="intake-city"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            maxLength={60}
            placeholder="مثلاً تهران"
            className="h-9 rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="intake-gpa" className="text-[11px] font-medium text-muted-foreground">
            معدل سال گذشته
          </label>
          <Input
            id="intake-gpa"
            value={toPersianDigits(lastGpaRaw)}
            onChange={(e) => setLastGpaRaw(sanitizeGpaInput(e.target.value))}
            inputMode="decimal"
            placeholder="۰ تا ۲۰"
            aria-label="معدل سال گذشته"
            className="h-9 rounded-lg text-center text-sm tabular-nums"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="intake-major" className="text-[11px] font-medium text-muted-foreground">
            رشتهٔ هدف
          </label>
          <Input
            id="intake-major"
            value={targetMajor}
            onChange={(e) => setTargetMajor(e.target.value)}
            maxLength={120}
            placeholder="مثلاً مهندسی کامپیوتر"
            className="h-9 rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1">
          <label
            htmlFor="intake-university"
            className="text-[11px] font-medium text-muted-foreground"
          >
            دانشگاه هدف
          </label>
          <Input
            id="intake-university"
            value={targetUniversity}
            onChange={(e) => setTargetUniversity(e.target.value)}
            maxLength={120}
            placeholder="مثلاً صنعتی شریف"
            className="h-9 rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1">
          <label
            htmlFor="intake-institute"
            className="text-[11px] font-medium text-muted-foreground"
          >
            مؤسسۀ آزمون
          </label>
          <Input
            id="intake-institute"
            value={mockExamInstitute}
            onChange={(e) => setMockExamInstitute(e.target.value)}
            maxLength={120}
            placeholder="مثلاً قلم‌چی"
            className="h-9 rounded-lg text-sm"
          />
        </div>
        <div className="space-y-1">
          <label
            htmlFor="intake-free-minutes"
            className="text-[11px] font-medium text-muted-foreground"
          >
            میانگین مطالعۀ روزِ آزاد (دقیقه)
          </label>
          <Input
            id="intake-free-minutes"
            value={toPersianDigits(freeDayMinutesRaw)}
            onChange={(e) =>
              setFreeDayMinutesRaw(sanitizeMinutesInput(e.target.value))
            }
            inputMode="numeric"
            placeholder="۰ تا ۱۴۴۰"
            aria-label="میانگین مطالعۀ روز آزاد بر حسب دقیقه"
            className="h-9 rounded-lg text-center text-sm tabular-nums"
          />
        </div>
      </div>

      {/* ── classes table ────────────────────────────────────────────────── */}
      <div className="space-y-2 rounded-xl border border-border/60 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">کلاس‌ها</span>
          <span className="text-xs tabular-nums text-muted-foreground">
            {toPersianDigits(rows.length)} از {toPersianDigits(MAX_CLASSES)} ردیف
          </span>
        </div>

        {rows.length === 0 && (
          <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs leading-relaxed text-muted-foreground">
            هنوز کلاسی ثبت نشده است. کلاس‌های کنکور یا مدرسۀ دانش‌آموز را اینجا اضافه کنید.
          </p>
        )}

        <ul className="space-y-2">
          {rows.map((row, index) => (
            <li key={row.uid} className="space-y-2 rounded-lg border border-border/50 p-2">
              <div className="grid grid-cols-[1fr_2rem] items-start gap-2 sm:grid-cols-[1fr_1fr_2rem]">
                <Input
                  value={row.name}
                  onChange={(e) => updateRow(row.uid, { name: e.target.value })}
                  placeholder={`نام کلاس ${toPersianDigits(index + 1)}`}
                  maxLength={120}
                  aria-label={`نام کلاس ${toPersianDigits(index + 1)}`}
                  className="h-9 text-xs"
                />
                <Input
                  value={row.teacher}
                  onChange={(e) => updateRow(row.uid, { teacher: e.target.value })}
                  placeholder="استاد"
                  maxLength={120}
                  aria-label={`استاد کلاس ${toPersianDigits(index + 1)}`}
                  className="h-9 text-xs"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`حذف کلاس ${toPersianDigits(index + 1)}`}
                  className="h-9 w-9 text-muted-foreground hover:text-destructive"
                  onClick={() => removeRow(row.uid)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <Select
                  value={String(row.weekday)}
                  onValueChange={(value) =>
                    updateRow(row.uid, { weekday: Number(value) })
                  }
                >
                  <SelectTrigger
                    aria-label={`روز هفتهٔ کلاس ${toPersianDigits(index + 1)}`}
                    className="h-9 text-xs"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {WEEKDAY_LABELS.map((label, day) => (
                      <SelectItem key={day} value={String(day)}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  type="time"
                  value={row.startTime}
                  onChange={(e) => updateRow(row.uid, { startTime: e.target.value })}
                  aria-label={`ساعت شروع کلاس ${toPersianDigits(index + 1)}`}
                  className="h-9 text-center text-xs tabular-nums"
                />
                <Input
                  type="time"
                  value={row.endTime}
                  onChange={(e) => updateRow(row.uid, { endTime: e.target.value })}
                  aria-label={`ساعت پایان کلاس ${toPersianDigits(index + 1)}`}
                  className="h-9 text-center text-xs tabular-nums"
                />
              </div>
            </li>
          ))}
        </ul>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addRow}
          disabled={atCap}
        >
          <Plus className="ml-2 h-4 w-4" />
          افزودن کلاس
        </Button>
        {atCap && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            حداکثر {toPersianDigits(MAX_CLASSES)} ردیف کلاس می‌توانید ثبت کنید.
          </p>
        )}
      </div>

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
 * The advisor's per-student «شناخت» card (restart step 2): the whole intake
 * profile plus the classes table, saved as one set-replace. Loads fresh on
 * mount and on retry; a missing/foreign engagement surfaces its Persian 404
 * detail in the error box, never as "forbidden".
 */
export function IntakeCard({ engagementId }: { engagementId: number }) {
  const [initial, setInitial] = useState<IntakePayload | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setError('');
    setInitial(null);
    AdvisoryService.getIntake(engagementId)
      .then((payload) => {
        if (active) setInitial(payload);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId, reloadKey]);

  const handleSave = async (payload: IntakePayload) => {
    setSaving(true);
    try {
      await AdvisoryService.putIntake(engagementId, payload);
      toast.success('فرم شناخت ذخیره شد.');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'ذخیره‌ی فرم شناخت ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <Contact className="h-4 w-4 text-primary" />
          </span>
          فرم شناخت دانش‌آموز
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          اطلاعات فردی، هدف‌ها و کلاس‌های دانش‌آموز را ثبت کنید. ذخیره، کل فرم را
          یکجا جایگزین می‌کند.
        </p>
      </CardHeader>

      <CardContent>
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

        {!initial && !error && (
          <div className="space-y-2" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10 w-full rounded-lg" />
            ))}
          </div>
        )}

        {initial && !error && (
          <IntakeProfileForm initial={initial} saving={saving} onSave={handleSave} />
        )}
      </CardContent>
    </Card>
  );
}
