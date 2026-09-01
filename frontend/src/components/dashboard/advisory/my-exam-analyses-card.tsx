'use client';

import { useEffect, useState } from 'react';
import { FileSearch } from 'lucide-react';

import { AdvisoryService, type ExamAnalysis } from '@/services/advisory-service';
import { toPersianDigits } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  AnalysisMetricsGrid,
  AnalysisRowsList,
  GRADE_BAND_LABELS,
} from '@/components/advisory/exam-analysis-card';

function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * The student-side mirror of the advisor's exam analyses («تحلیل کارنامهٔ من»,
 * restart step 6): report-card metrics, the advisor's report, per-subject
 * rows, and per-question notes behind an accordion — all read-only.
 *
 * Quiet home-card rule: renders NOTHING without an active advisor or when no
 * analysis exists yet.
 */
export function MyExamAnalysesCard({ showEmptyState = false }: { showEmptyState?: boolean }) {
  const [analyses, setAnalyses] = useState<ExamAnalysis[] | null>(null);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyExamAnalyses()
      .then((resp) => {
        if (active && resp.active) {
          setAnalyses(Array.isArray(resp.analyses) ? resp.analyses : []);
        }
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, []);

  if (!analyses || analyses.length === 0) {
    if (showEmptyState && analyses) {
      return (
        <Card dir="rtl" className="rounded-2xl border-dashed">
          <CardContent className="py-10 text-center">
            <p className="text-sm text-muted-foreground">
              هنوز تحلیل یا گزارشی از سوی مشاور برایت نوشته نشده است.
            </p>
          </CardContent>
        </Card>
      );
    }
    return null;
  }

  const sorted = [...analyses].sort((a, b) => {
    const dateDiff = (b.examDate ?? '').localeCompare(a.examDate ?? '');
    return dateDiff !== 0 ? dateDiff : b.id - a.id;
  });

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <FileSearch className="h-4 w-4 text-primary" />
          </span>
          تحلیل کارنامهٔ من
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          تحلیل‌ها و گزارش‌هایی که مشاورت بعد از آزمون‌هایت نوشته است.
        </p>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {sorted.map((item) => (
            <li
              key={item.id}
              className="space-y-3 rounded-xl border border-border/60 bg-background/60 p-3"
            >
              <div className="space-y-1">
                <p className="text-sm font-medium leading-relaxed">
                  {item.examNumber !== null
                    ? `کارنامهٔ شمارهٔ ${toPersianDigits(item.examNumber)}`
                    : 'کارنامهٔ آزمون'}
                </p>
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  <span className="tabular-nums">
                    {item.examDate
                      ? formatPersianDate(
                          parseIsoDate(item.examDate) ?? item.examDate,
                        )
                      : '—'}
                  </span>
                  {item.gradeBand && (
                    <>
                      <span aria-hidden="true">·</span>
                      <span>{GRADE_BAND_LABELS[item.gradeBand]}</span>
                    </>
                  )}
                </p>
              </div>

              <AnalysisMetricsGrid item={item} />

              {item.advisorReport.trim() && (
                <p className="whitespace-pre-line text-sm leading-relaxed">
                  {item.advisorReport}
                </p>
              )}

              {item.rows.length > 0 && <AnalysisRowsList rows={item.rows} />}

              {item.notes.length > 0 && (
                <Accordion type="single" collapsible>
                  <AccordionItem value={`notes-${item.id}`} className="border-b-0">
                    <AccordionTrigger className="py-2 text-xs font-medium text-muted-foreground hover:no-underline">
                      نکات سؤال‌به‌سؤال ({toPersianDigits(item.notes.length)})
                    </AccordionTrigger>
                    <AccordionContent className="pb-1">
                      <ul className="space-y-1.5">
                        {[...item.notes]
                          .sort((a, b) => a.questionNumber - b.questionNumber)
                          .map((note) => (
                            <li
                              key={note.questionNumber}
                              className="flex items-start gap-2 rounded-lg border border-border/50 px-3 py-2 text-xs leading-relaxed"
                            >
                              <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 font-semibold tabular-nums text-primary">
                                سؤال {toPersianDigits(note.questionNumber)}
                              </span>
                              <span className="min-w-0">
                                {note.subjectName.trim() && (
                                  <span className="font-medium">
                                    {note.subjectName}:{' '}
                                  </span>
                                )}
                                {note.note}
                              </span>
                            </li>
                          ))}
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
