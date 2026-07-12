'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { BookOpen, LayoutDashboard, Megaphone, NotebookPen, Users } from 'lucide-react';

import { cn } from '@/lib/utils';
import { toPersianDigits } from '@/lib/persian-digits';
import {
  listExercises,
  type ExerciseListItem,
} from '@/services/exercises-service';
import type { ClassPendingExerciseSnapshot } from '@/types';

interface ClassWorkspaceNavProps {
  classId: string;
  basePath?: string;
  className?: string;
  pendingExercises?: ClassPendingExerciseSnapshot[];
}

type WorkspaceNavItem = {
  label: string;
  href: string;
  match: (pathname: string) => boolean;
  icon: typeof LayoutDashboard;
  showExerciseSummary?: boolean;
};

function summarizeExerciseState(exercises: ExerciseListItem[]): string {
  const state = exercises.some((exercise) => exercise.status === 'extracting')
    ? 'در حال استخراج'
    : exercises.some((exercise) => exercise.status === 'failed')
      ? 'نیازمند بررسی'
      : exercises.some((exercise) => exercise.status === 'extracted')
        ? 'آماده انتشار'
        : exercises.some((exercise) => exercise.status === 'draft')
          ? 'پیش‌نویس'
          : 'منتشرشده';

  return `${toPersianDigits(exercises.length)} · ${state}`;
}

function summarizePendingExercises(pendingExercises: ClassPendingExerciseSnapshot[]): string | null {
  if (pendingExercises.length === 0) return null;

  const state = pendingExercises.some((exercise) => exercise.workflowStage === 'failed' || exercise.exerciseStatus === 'failed' || exercise.status === 'failed')
    ? 'نیازمند بررسی'
    : pendingExercises.some((exercise) => exercise.readyForReview || exercise.workflowStage === 'ready_for_review' || exercise.exerciseStatus === 'extracted')
      ? 'آماده بازبینی'
      : pendingExercises.some((exercise) => exercise.exerciseId || exercise.status === 'queued' || exercise.exerciseStatus === 'extracting')
        ? 'در حال ساخت'
        : 'در صف ساخت';

  return `${toPersianDigits(pendingExercises.length)} · ${state}`;
}

export function ClassWorkspaceNav({
  classId,
  basePath = '/teacher',
  className,
  pendingExercises = [],
}: ClassWorkspaceNavProps) {
  const pathname = usePathname();
  const rootPath = `${basePath}/my-classes/${classId}`;
  const [exerciseSummary, setExerciseSummary] = useState<string | null>(null);
  const pendingSummary = useMemo(() => summarizePendingExercises(pendingExercises), [pendingExercises]);

  useEffect(() => {
    if (basePath !== '/teacher') return;

    const sessionId = Number(classId);
    if (!Number.isFinite(sessionId)) return;

    let mounted = true;
    listExercises(sessionId)
      .then((exercises) => {
        if (!mounted) return;
        setExerciseSummary(exercises.length > 0 ? summarizeExerciseState(exercises) : null);
      })
      .catch(() => {
        if (mounted) setExerciseSummary(null);
      });

    return () => {
      mounted = false;
    };
  }, [basePath, classId]);

  const items: WorkspaceNavItem[] = useMemo(
    () => [
      {
        label: 'نمای کلی',
        href: rootPath,
        icon: LayoutDashboard,
        match: (path) => path === rootPath,
      },
      {
        label: 'محتوا',
        href: `${rootPath}/edit`,
        icon: BookOpen,
        match: (path) => path === `${rootPath}/edit`,
      },
      {
        label: 'تمرین‌ها',
        href: `${rootPath}/exercises`,
        icon: NotebookPen,
        match: (path) => path.startsWith(`${rootPath}/exercises`),
        showExerciseSummary: true,
      },
      {
        label: 'دانش‌آموزان',
        href: `${rootPath}/students`,
        icon: Users,
        match: (path) => path === `${rootPath}/students`,
      },
      {
        label: 'اطلاعیه‌ها',
        href: `${rootPath}#announcements`,
        icon: Megaphone,
        match: () => false,
      },
    ],
    [rootPath]
  );

  return (
    <nav
      aria-label="بخش‌های کلاس"
      dir="rtl"
      className={cn(
        'overflow-x-auto rounded-2xl border border-border/70 bg-background/80 p-1',
        className
      )}
    >
      <ul className="flex min-w-max items-center gap-1">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = item.match(pathname);

          return (
            <li key={item.label}>
              <Link
                href={item.href}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex min-h-11 items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium text-muted-foreground transition-colors',
                  'hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                  isActive && 'bg-primary text-primary-foreground shadow-sm hover:bg-primary hover:text-primary-foreground'
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                <span>{item.label}</span>
                {item.showExerciseSummary && (exerciseSummary || pendingSummary || 'بدون تمرین') && (
                  <span
                    className={cn(
                      'rounded-full border px-2 py-0.5 text-[11px] leading-none',
                      isActive
                        ? 'border-primary-foreground/30 bg-primary-foreground/15 text-primary-foreground'
                        : 'border-border bg-muted text-muted-foreground'
                    )}
                  >
                    {exerciseSummary || pendingSummary || 'بدون تمرین'}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
