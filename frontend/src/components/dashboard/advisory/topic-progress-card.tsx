'use client';

import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ListChecks, Loader2, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import {
  AdvisoryService,
  type TopicProgressOut,
  type TopicStatus,
} from '@/services/advisory-service';
import { toPersianDigits } from '@/lib/persian-digits';
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

const STATUS_ORDER: TopicStatus[] = ['NEW', 'STUDIED', 'NEEDS_REVIEW', 'MASTERED'];

const STATUS_META: Record<TopicStatus, { label: string; chip: string }> = {
  NEW: { label: 'شروع‌نشده', chip: 'bg-muted text-muted-foreground' },
  STUDIED: {
    label: 'خوانده‌شده',
    chip: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  },
  NEEDS_REVIEW: {
    label: 'نیاز به مرور',
    chip: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  },
  MASTERED: {
    label: 'تسلط‌یافته',
    chip: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  },
};

export function TopicProgressCard() {
  const [topics, setTopics] = useState<TopicProgressOut[] | null>(null);
  const [subjects, setSubjects] = useState<{ subjectId: number; name: string }[]>([]);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [subjectId, setSubjectId] = useState<string>('');
  const [topicName, setTopicName] = useState('');

  const load = () => {
    AdvisoryService.getMyTopics()
      .then((res) => {
        if (res.active) setTopics(res.topics);
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
          setSubjectId(String(res.subjects[0].subjectId));
        }
      })
      .catch(() => {});
  }, []);

  const grouped = useMemo(() => {
    const bySubject = new Map<string, TopicProgressOut[]>();
    for (const row of topics ?? []) {
      const bucket = bySubject.get(row.subjectName);
      if (bucket) bucket.push(row);
      else bySubject.set(row.subjectName, [row]);
    }
    return [...bySubject.entries()];
  }, [topics]);

  const addTopic = async () => {
    if (!topicName.trim() || !subjectId) return;
    setBusy(true);
    try {
      await AdvisoryService.createMyTopic({
        subjectId: Number(subjectId),
        topic: topicName.trim(),
      });
      setTopicName('');
      setAdding(false);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ثبت مبحث ناموفق بود.');
    } finally {
      setBusy(false);
    }
  };

  const cycleStatus = async (row: TopicProgressOut) => {
    const next =
      STATUS_ORDER[(STATUS_ORDER.indexOf(row.status) + 1) % STATUS_ORDER.length];
    try {
      const saved = await AdvisoryService.patchMyTopic(row.id, { status: next });
      setTopics((prev) =>
        (prev ?? []).map((t) => (t.id === saved.id ? saved : t)),
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'تغییر وضعیت ناموفق بود.');
    }
  };

  const removeTopic = async (row: TopicProgressOut) => {
    try {
      await AdvisoryService.deleteMyTopic(row.id);
      setTopics((prev) => (prev ?? []).filter((t) => t.id !== row.id));
    } catch {
      toast.error('حذف مبحث ناموفق بود.');
    }
  };

  if (topics === null) return null;

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-base font-semibold">
          <span className="flex items-center gap-2">
            <span className="rounded-lg bg-primary/10 p-1.5">
              <ListChecks className="h-4 w-4 text-primary" />
            </span>
            پوشش مباحث
          </span>
          {subjects.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setAdding((a) => !a)}
              aria-label="افزودن مبحث"
            >
              <Plus className="h-4 w-4" />
              مبحث جدید
            </Button>
          )}
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          روی وضعیت هر مبحث بزن تا جلو برود؛ «نیاز به مرور» خودش تاریخ مرور را دو روز بعد می‌گذارد.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {adding && (
          <div className="flex flex-wrap items-center gap-2">
            <Select value={subjectId} onValueChange={setSubjectId}>
              <SelectTrigger className="h-9 w-40 text-xs" aria-label="درس مبحث">
                <SelectValue />
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
              value={topicName}
              onChange={(e) => setTopicName(e.target.value.slice(0, 200))}
              placeholder="نام مبحث…"
              aria-label="نام مبحث"
              className="h-9 flex-1 bg-background text-xs"
              onKeyDown={(e) => {
                if (e.key === 'Enter') void addTopic();
              }}
            />
            <Button
              type="button"
              size="sm"
              onClick={addTopic}
              disabled={busy || !topicName.trim()}
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              افزودن
            </Button>
          </div>
        )}

        {topics.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            هنوز مبحثی اضافه نشده؛ با «مبحث جدید» فهرست مطالعهٔ هر درس را بساز.
          </p>
        ) : (
          grouped.map(([subjectName, rows]) => {
            const done = rows.filter(
              (r) => r.status === 'STUDIED' || r.status === 'MASTERED',
            ).length;
            const pct = Math.round((done / rows.length) * 100);
            return (
              <section key={subjectName} className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold">{subjectName}</p>
                  <p className="text-[11px] tabular-nums text-muted-foreground">
                    {toPersianDigits(done)} از {toPersianDigits(rows.length)} (
                    {toPersianDigits(pct)}٪)
                  </p>
                </div>
                <div
                  className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`پوشش ${subjectName}`}
                >
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <ul className="space-y-1">
                  {rows.map((row) => (
                    <li
                      key={row.id}
                      className="flex items-center justify-between gap-2 rounded-lg border border-border/50 bg-background/60 px-2.5 py-1.5"
                    >
                      <button
                        type="button"
                        onClick={() => void cycleStatus(row)}
                        className="flex min-w-0 flex-1 items-center gap-2 text-start text-xs"
                        aria-label={`وضعیت ${row.topic}: ${STATUS_META[row.status].label}`}
                      >
                        <span
                          className={cn(
                            'h-2 w-2 shrink-0 rounded-full',
                            row.status === 'MASTERED'
                              ? 'bg-emerald-500'
                              : row.status === 'NEEDS_REVIEW'
                                ? 'bg-amber-500'
                                : row.status === 'STUDIED'
                                  ? 'bg-blue-500'
                                  : 'bg-muted-foreground/40',
                          )}
                        />
                        <span
                          className={cn(
                            'truncate',
                            row.status === 'MASTERED' &&
                              'text-muted-foreground line-through',
                          )}
                        >
                          {row.topic}
                        </span>
                      </button>
                      <span
                        className={cn(
                          'shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold',
                          STATUS_META[row.status].chip,
                        )}
                      >
                        {row.status === 'MASTERED' ? (
                          <CheckCircle2 className="inline h-3 w-3" />
                        ) : null}{' '}
                        {STATUS_META[row.status].label}
                      </span>
                      <button
                        type="button"
                        onClick={() => void removeTopic(row)}
                        className="shrink-0 text-muted-foreground/60 hover:text-destructive"
                        aria-label={`حذف ${row.topic}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
