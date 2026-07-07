'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, CalendarClock, Loader2, NotebookPen } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { MathText } from '@/components/content/math-text';
import { cn } from '@/lib/utils';
import { toPersianDigits } from '@/lib/persian-digits';
import { formatPersianDateTime } from '@/lib/date-utils';
import {
  getStudentExerciseAction,
  getStudentExerciseActionKind,
  pickStudentExerciseActionTarget,
} from '@/lib/exercise-actions';
import {
  listStudentExercises,
  type StudentExerciseListItem,
} from '@/services/exercises-service';

type StudentExerciseQuickActionProps = {
  sessionId: number;
  variant?: 'course-card' | 'learn-bar';
  className?: string;
  showEmpty?: boolean;
};

const exerciseListRequests = new Map<number, Promise<StudentExerciseListItem[]>>();

function loadStudentExercises(sessionId: number): Promise<StudentExerciseListItem[]> {
  const pending = exerciseListRequests.get(sessionId);
  if (pending) return pending;

  const request = listStudentExercises(sessionId).finally(() => {
    exerciseListRequests.delete(sessionId);
  });
  exerciseListRequests.set(sessionId, request);
  return request;
}

function openExerciseCount(exercises: StudentExerciseListItem[]): number {
  return exercises.filter((exercise) => {
    const kind = getStudentExerciseActionKind(exercise);
    return kind === 'start' || kind === 'continue';
  }).length;
}

function summaryFor(exercise: StudentExerciseListItem): string {
  if (exercise.deadline) {
    return `مهلت: ${formatPersianDateTime(exercise.deadline)}`;
  }
  return 'بدون مهلت';
}

export function StudentExerciseQuickAction({
  sessionId,
  variant = 'course-card',
  className,
  showEmpty = false,
}: StudentExerciseQuickActionProps) {
  const [items, setItems] = useState<StudentExerciseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(sessionId)) return;

    let mounted = true;
    setLoading(true);
    setFailed(false);
    loadStudentExercises(sessionId)
      .then((exercises) => {
        if (mounted) setItems(exercises);
      })
      .catch(() => {
        if (mounted) {
          setItems([]);
          setFailed(true);
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [sessionId]);

  const target = useMemo(() => pickStudentExerciseActionTarget(items), [items]);
  const action = target ? getStudentExerciseAction(target, sessionId) : null;
  const openCount = useMemo(() => openExerciseCount(items), [items]);

  if (!Number.isFinite(sessionId)) return null;

  if (loading) {
    if (variant === 'course-card') return null;

    return (
      <div
        className={cn(
          'flex min-h-12 items-center gap-2 rounded-2xl border border-border/60 bg-muted/20 px-3 text-xs text-muted-foreground',
          className
        )}
        dir="rtl"
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        در حال بررسی تمرین‌ها
      </div>
    );
  }

  if (failed || !target || !action) {
    if (!showEmpty) return null;
    return (
      <div
        className={cn(
          'rounded-2xl border border-dashed border-border/70 bg-muted/10 px-3 py-2 text-xs text-muted-foreground',
          className
        )}
        dir="rtl"
      >
        هنوز تمرینی برای این کلاس منتشر نشده است.
      </div>
    );
  }

  const isLearnBar = variant === 'learn-bar';

  return (
    <div
      dir="rtl"
      className={cn(
        'rounded-2xl border border-primary/20 bg-primary/5',
        isLearnBar ? 'px-3 py-2 md:px-4 md:py-3' : 'p-3',
        className
      )}
    >
      <div className={cn('flex gap-3', isLearnBar ? 'items-center justify-between' : 'flex-col')}>
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-background text-primary">
            <NotebookPen className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-sm font-bold text-foreground">
                <MathText text={target.title} />
              </p>
              {openCount > 1 && (
                <span className="rounded-full border border-primary/20 bg-background px-2 py-0.5 text-[11px] font-bold text-primary">
                  {toPersianDigits(openCount)} باز
                </span>
              )}
            </div>
            <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
              <CalendarClock className="h-3 w-3" aria-hidden="true" />
              {summaryFor(target)}
            </p>
          </div>
        </div>

        <Button
          asChild
          size="sm"
          className={cn(
            'h-10 shrink-0 rounded-xl px-3 font-bold',
            !isLearnBar && 'w-full'
          )}
        >
          <Link href={action.href}>
            {action.label}
            <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>
    </div>
  );
}
