'use client';

import { useEffect, useState } from 'react';
import { BookOpenCheck, Building2 } from 'lucide-react';

import {
  AdvisoryService,
  type MySubjectsResponse,
} from '@/services/advisory-service';
import { SUBJECT_SOURCE_LABELS } from '@/components/advisory/subject-picker-dialog';
import { toPersianDigits } from '@/lib/persian-digits';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

/**
 * The student-side mirror of what their advisor selected — «درس‌های مطالعاتی شما».
 *
 * Slotted into the dashboard home, so it follows the same *quiet* rule as
 * {@link AdvisorInviteBanner}: it renders nothing at all — no skeleton, no empty
 * card — until it knows there are subjects to show. The vast majority of students
 * have no advisor, and a placeholder that reserved space on every home load would
 * be a worse regression than this card is a feature. A failed fetch is swallowed
 * for the same reason: a student mid-study never sees an advisory error they did
 * not ask for. The endpoint is already quiet on the wire (`active:false` for the
 * no-advisor case, never a 4xx), so the only thing left to guard is the render.
 */
export function MySubjectsCard() {
  const [data, setData] = useState<MySubjectsResponse | null>(null);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMySubjects()
      .then((res) => {
        if (active) setData(res);
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, []);

  if (!data || !data.active || data.subjects.length === 0) return null;

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <BookOpenCheck className="h-4 w-4 text-primary" />
          </span>
          درس‌های مطالعاتی شما
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {data.advisorName
            ? `${toPersianDigits(data.subjects.length)} درس که مشاور شما، «${data.advisorName}»، برایتان انتخاب کرده است.`
            : `${toPersianDigits(data.subjects.length)} درس که مشاور شما برایتان انتخاب کرده است.`}
        </p>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-wrap gap-2">
          {data.subjects.map((s) => (
            <li key={s.subjectId}>
              <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-sm">
                {s.name}
                {s.source && SUBJECT_SOURCE_LABELS[s.source] && (
                  <Badge variant="outline" className="font-normal">
                    {SUBJECT_SOURCE_LABELS[s.source]}
                  </Badge>
                )}
                {s.gradeLabel && (
                  <Badge variant="secondary" className="font-normal">
                    {s.gradeLabel}
                  </Badge>
                )}
                {!s.isGlobal && (
                  <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
