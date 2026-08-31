'use client';

import { useEffect, useMemo, useState } from 'react';
import { BookX, Check, Loader2, Plus, RotateCcw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import {
  AdvisoryService,
  type MistakeEntryOut,
  type MistakeErrorType,
} from '@/services/advisory-service';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

const ERROR_LABELS: Record<MistakeErrorType, string> = {
  CONCEPT: 'مفهومی',
  FORGET: 'فراموشی',
  METHOD: 'تشخیص روش',
  EXECUTION: 'محاسباتی/اجرایی',
  READING: 'خواندن سؤال',
  TIME: 'مدیریت زمان',
};

const ERROR_DOT: Record<MistakeErrorType, string> = {
  CONCEPT: 'bg-red-500',
  FORGET: 'bg-amber-500',
  METHOD: 'bg-blue-500',
  EXECUTION: 'bg-purple-500',
  READING: 'bg-teal-500',
  TIME: 'bg-pink-500',
};

const STATUS_LABELS: Record<string, string> = {
  WRONG: 'غلط',
  DOUBT_RIGHT: 'درست اما شک‌دار',
  UNANSWERED: 'نزده',
};

export function MistakeLogCard() {
  const [rows, setRows] = useState<MistakeEntryOut[] | null>(null);
  const [subjects, setSubjects] = useState<{ subjectId: number; name: string }[]>([]);
  const [showResolved, setShowResolved] = useState(false);
  const [filter, setFilter] = useState<'ALL' | MistakeErrorType>('ALL');
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    subjectId: '',
    topic: '',
    status: 'WRONG',
    errorType: 'CONCEPT',
    cause: '',
    fixNote: '',
    nextAction: '',
  });

  const load = () => {
    AdvisoryService.getMyMistakes()
      .then((res) => {
        if (res.active) setRows(res.mistakes);
      })
      .catch(() => {});
  };

  useEffect(() => {
    load();
    AdvisoryService.getMySubjects()
      .then((res) => {
        if (res.active && res.subjects.length) {
          setSubjects(
            res.subjects.map((s) => ({ subjectId: s.subjectId, name: s.name })),
          );
          setForm((f) => ({
            ...f,
            subjectId: f.subjectId || String(res.subjects[0].subjectId),
          }));
        }
      })
      .catch(() => {});
  }, []);

  const visible = useMemo(() => {
    return (rows ?? []).filter(
      (r) =>
        (showResolved || !r.isResolved) &&
        (filter === 'ALL' || r.errorType === filter),
    );
  }, [rows, showResolved, filter]);

  const openCount = (rows ?? []).filter((r) => !r.isResolved).length;

  const add = async () => {
    if (!form.topic.trim() || !form.subjectId) {
      toast.error('درس و مبحث را مشخص کن.');
      return;
    }
    setBusy(true);
    try {
      const created = await AdvisoryService.createMyMistake({
        subjectId: Number(form.subjectId),
        topic: form.topic.trim(),
        status: form.status as 'WRONG',
        errorType: form.errorType as MistakeErrorType,
        cause: form.cause,
        fixNote: form.fixNote,
        nextAction: form.nextAction,
      });
      setRows((prev) => [created, ...(prev ?? [])]);
      setForm((f) => ({ ...f, topic: '', cause: '', fixNote: '', nextAction: '' }));
      setAdding(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ثبت خطا ناموفق بود.');
    } finally {
      setBusy(false);
    }
  };

  const toggleResolve = async (row: MistakeEntryOut) => {
    try {
      const saved = await AdvisoryService.patchMyMistake(row.id, {
        isResolved: !row.isResolved,
      });
      setRows((prev) => (prev ?? []).map((r) => (r.id === saved.id ? saved : r)));
    } catch {
      toast.error('تغییر وضعیت ناموفق بود.');
    }
  };

  const remove = async (row: MistakeEntryOut) => {
    try {
      await AdvisoryService.deleteMyMistake(row.id);
      setRows((prev) => (prev ?? []).filter((r) => r.id !== row.id));
    } catch {
      toast.error('حذف ناموفق بود.');
    }
  };

  if (rows === null) return null;

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base font-semibold">
          <span className="flex items-center gap-2">
            <span className="rounded-lg bg-primary/10 p-1.5">
              <BookX className="h-4 w-4 text-primary" />
            </span>
            دفتر اشتباهات
            {openCount > 0 && (
              <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[11px] font-bold tabular-nums text-destructive">
                {openCount}
              </span>
            )}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setAdding((a) => !a)}
            aria-label="ثبت خطای جدید"
          >
            <Plus className="h-4 w-4" />
            خطای جدید
          </Button>
        </CardTitle>
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setFilter('ALL')}
            className={cn(
              'rounded-full px-2.5 py-0.5 text-[11px] font-semibold transition-colors',
              filter === 'ALL'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:text-foreground',
            )}
          >
            همه
          </button>
          {(Object.keys(ERROR_LABELS) as MistakeErrorType[]).map((code) => (
            <button
              key={code}
              type="button"
              onClick={() => setFilter(code)}
              className={cn(
                'flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold transition-colors',
                filter === code
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:text-foreground',
              )}
            >
              <span className={cn('h-1.5 w-1.5 rounded-full', ERROR_DOT[code])} />
              {ERROR_LABELS[code]}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setShowResolved((v) => !v)}
            className={cn(
              'ms-auto flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold transition-colors',
              showResolved
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                : 'bg-muted text-muted-foreground',
            )}
          >
            <RotateCcw className="h-3 w-3" />
            رفع‌شده‌ها
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {adding && subjects.length > 0 && (
          <div className="space-y-2 rounded-xl border border-border/60 bg-background/60 p-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Select
                value={form.subjectId}
                onValueChange={(v) => setForm((f) => ({ ...f, subjectId: v }))}
              >
                <SelectTrigger className="h-9 text-xs" aria-label="درس">
                  <SelectValue placeholder="درس" />
                </SelectTrigger>
                <SelectContent>
                  {subjects.map((s) => (
                    <SelectItem key={s.subjectId} value={String(s.subjectId)}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                value={form.topic}
                onChange={(e) => setForm((f) => ({ ...f, topic: e.target.value }))}
                placeholder="مبحث (مثل: اصطکاک)"
                aria-label="مبحث"
                className="h-9 bg-background text-xs"
              />
              <Select
                value={form.errorType}
                onValueChange={(v) => setForm((f) => ({ ...f, errorType: v }))}
              >
                <SelectTrigger className="h-9 text-xs" aria-label="نوع خطا">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(ERROR_LABELS) as MistakeErrorType[]).map((code) => (
                    <SelectItem key={code} value={code}>
                      {ERROR_LABELS[code]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={form.status}
                onValueChange={(v) => setForm((f) => ({ ...f, status: v }))}
              >
                <SelectTrigger className="h-9 text-xs" aria-label="وضعیت پاسخ">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(STATUS_LABELS).map(([code, label]) => (
                    <SelectItem key={code} value={code}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <Input
                value={form.cause}
                onChange={(e) => setForm((f) => ({ ...f, cause: e.target.value }))}
                placeholder="علت اصلی"
                aria-label="علت اصلی"
                className="h-9 bg-background text-xs"
              />
              <Input
                value={form.fixNote}
                onChange={(e) => setForm((f) => ({ ...f, fixNote: e.target.value }))}
                placeholder="نکتهٔ اصلاحی"
                aria-label="نکته اصلاحی"
                className="h-9 bg-background text-xs"
              />
              <Input
                value={form.nextAction}
                onChange={(e) => setForm((f) => ({ ...f, nextAction: e.target.value }))}
                placeholder="اقدام بعدی"
                aria-label="اقدام بعدی"
                className="h-9 bg-background text-xs"
              />
            </div>
            <div className="flex justify-end">
              <Button type="button" size="sm" onClick={add} disabled={busy}>
                {busy ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                ثبت در دفتر
              </Button>
            </div>
          </div>
        )}

        {visible.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            {rows.length === 0
              ? 'بعد از هر آزمون، خطاهای مهم را این‌جا ثبت کن تا پیش از آزمون بعدی مرورشان کنی.'
              : 'با این فیلتر چیزی نیست.'}
          </p>
        ) : (
          <ul className="space-y-2">
            {visible.map((row) => (
              <li
                key={row.id}
                className={cn(
                  'space-y-1 rounded-xl border border-border/60 bg-background/60 p-3',
                  row.isResolved && 'opacity-60',
                )}
              >
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span
                    className={cn('h-2 w-2 rounded-full', ERROR_DOT[row.errorType])}
                  />
                  <span className="text-xs font-bold">{row.topic}</span>
                  <span className="text-[11px] text-muted-foreground">
                    {row.subjectName} · {STATUS_LABELS[row.status]} ·{' '}
                    {ERROR_LABELS[row.errorType]}
                  </span>
                  <span className="ms-auto flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => void toggleResolve(row)}
                      className={cn(
                        'rounded-full p-1.5 transition-colors',
                        row.isResolved
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          : 'text-muted-foreground hover:bg-muted',
                      )}
                      aria-label={
                        row.isResolved ? 'بازگشایی خطا' : 'علامت‌گذاری رفع‌شده'
                      }
                    >
                      {row.isResolved ? (
                        <RotateCcw className="h-3.5 w-3.5" />
                      ) : (
                        <Check className="h-3.5 w-3.5" />
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => void remove(row)}
                      className="rounded-full p-1.5 text-muted-foreground/60 hover:text-destructive"
                      aria-label={`حذف ${row.topic}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </span>
                </div>
                {(row.cause || row.fixNote || row.nextAction) && (
                  <div className="space-y-0.5 text-[11px] leading-relaxed">
                    {row.cause && (
                      <p className="text-muted-foreground">علت: {row.cause}</p>
                    )}
                    {row.fixNote && <p>اصلاح: {row.fixNote}</p>}
                    {row.nextAction && (
                      <p className="text-muted-foreground">اقدام: {row.nextAction}</p>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
