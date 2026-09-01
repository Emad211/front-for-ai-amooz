'use client';

import { useEffect, useState } from 'react';
import { Pause, Play, Square, Timer } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { toPersianDigits } from '@/lib/persian-digits';

export type TimerSubject = { subjectId: number; name: string };

type StudyTimerProps = {
  subjects: TimerSubject[];
  /** Controlled clock state, owned by the advisory page so the timer keeps
   * counting while the «امروز» tab content is unmounted. */
  seconds: number;
  running: boolean;
  onSecondsChange: (seconds: number) => void;
  onRunningChange: (running: boolean) => void;
  onAddMinutes: (subjectId: number, minutes: number) => void;
};

function formatClock(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${toPersianDigits(String(m).padStart(2, '0'))}:${toPersianDigits(String(s).padStart(2, '0'))}`;
}

/** A pure-front study stopwatch: pick a subject, run, and on stop the whole
 * minutes drop straight into the day's minutes for that subject. */
export function StudyTimer({
  subjects,
  seconds,
  running,
  onSecondsChange,
  onRunningChange,
  onAddMinutes,
}: StudyTimerProps) {
  const [subjectId, setSubjectId] = useState<number | null>(
    subjects[0]?.subjectId ?? null,
  );

  useEffect(() => {
    if (
      subjects.length &&
      (subjectId === null || !subjects.some((s) => s.subjectId === subjectId))
    ) {
      setSubjectId(subjects[0].subjectId);
    }
  }, [subjects, subjectId]);

  const stop = () => {
    onRunningChange(false);
    const minutes = Math.floor(seconds / 60);
    if (minutes > 0 && subjectId !== null) {
      onAddMinutes(subjectId, minutes);
    }
    onSecondsChange(0);
  };

  return (
    <Card className="rounded-2xl border-primary/20 bg-primary/5">
      <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <Timer className="h-4 w-4 text-primary" />
          </span>
          تایمر مطالعه
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={subjectId !== null ? String(subjectId) : undefined}
            onValueChange={(v) => setSubjectId(Number(v))}
          >
            <SelectTrigger className="h-9 w-40 text-xs" aria-label="درس تایمر">
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
          <span
            className={cn(
              'min-w-16 text-center text-lg font-bold tabular-nums',
              running ? 'text-primary' : 'text-muted-foreground',
            )}
          >
            {formatClock(seconds)}
          </span>
          <Button
            type="button"
            size="sm"
            onClick={() => onRunningChange(!running)}
            disabled={subjectId === null}
            aria-label={running ? 'توقف موقت' : 'شروع'}
          >
            {running ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {running ? 'توقف موقت' : 'شروع'}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={stop}
            disabled={seconds < 60 || subjectId === null}
            aria-label="ثبت دقیقه‌ها"
          >
            <Square className="h-4 w-4" />
            ثبت
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
