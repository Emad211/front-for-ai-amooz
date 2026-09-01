'use client';

import { useEffect, useState } from 'react';
import { GraduationCap } from 'lucide-react';

import { AdvisoryService, type ExamScore } from '@/services/advisory-service';
import { toPersianDigits } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import {
  EXAM_KIND_LABELS,
  RATING_BADGE_CLASSES,
  RATING_LABELS,
} from '@/components/advisory/exam-scores-card';

function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * The student-side mirror of the advisor's exam scores («نمرات آزمون‌های من»,
 * restart step 5): a compact read-only list, newest first.
 *
 * Quiet home-card rule like MySubjectsCard/MyIntakeCard: it renders NOTHING
 * until a successful read confirms an active advisor AND at least one saved
 * score — most students have no advisor (or no scores yet) and must not pay
 * layout cost for an empty shell.
 */
export function MyExamScoresCard({ showEmptyState = false }: { showEmptyState?: boolean }) {
  const [scores, setScores] = useState<ExamScore[] | null>(null);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyExamScores()
      .then((resp) => {
        if (active && resp.active) {
          setScores(Array.isArray(resp.scores) ? resp.scores : []);
        }
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, []);

  if (!scores || scores.length === 0) {
    if (showEmptyState && scores) {
      return (
        <Card dir="rtl" className="rounded-2xl border-dashed">
          <CardContent className="py-10 text-center">
            <p className="text-sm text-muted-foreground">
              هنوز نمره یا ارزیابی‌ای از سوی مشاور برایت ثبت نشده است.
            </p>
          </CardContent>
        </Card>
      );
    }
    return null;
  }

  const sorted = [...scores].sort(
    (a, b) => b.examDate.localeCompare(a.examDate) || b.id - a.id,
  );

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <GraduationCap className="h-4 w-4 text-primary" />
          </span>
          نمرات آزمون‌های من
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          نمرات و ارزیابی‌هایی که مشاورت برای آزمون‌هایت ثبت کرده است، به
          ترتیب تاریخ.
        </p>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {sorted.map((score) => (
            <li
              key={score.id}
              className="rounded-xl border border-border/60 bg-background/60 p-3"
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
                      {formatPersianDate(
                        parseIsoDate(score.examDate) ?? score.examDate,
                      )}
                    </span>
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
                </div>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
