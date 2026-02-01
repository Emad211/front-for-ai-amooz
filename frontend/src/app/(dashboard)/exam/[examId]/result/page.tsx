'use client';

import React from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { DashboardService } from '@/services/dashboard-service';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { toPersianOptionLabel } from '@/lib/persian-option-label';
import type { Exam } from '@/types';

type ExamPrepResult = {
  finalized: boolean;
  score_0_100: number;
  correct_count: number;
  total_questions: number;
  answers: Record<string, string>;
  items: { question_id: string; selected_label: string; is_correct: boolean }[];
};

export default function ExamResultPage() {
  const params = useParams();
  const router = useRouter();
  const rawExamId = (params as any)?.examId as string | string[] | undefined;
  const examId = Array.isArray(rawExamId) ? rawExamId[0] : rawExamId;

  const [exam, setExam] = React.useState<Exam | null>(null);
  const [result, setResult] = React.useState<ExamPrepResult | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [isResetting, setIsResetting] = React.useState(false);

  React.useEffect(() => {
    const eid = String(examId ?? '').trim();
    if (!eid) {
      setError('شناسه آزمون نامعتبر است.');
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    const run = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [examData, resultData] = await Promise.all([
          DashboardService.getExam(eid),
          DashboardService.getExamPrepResult(eid),
        ]);
        if (cancelled) return;
        setExam(examData);
        setResult(resultData);
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : 'خطا در دریافت نتیجه آزمون';
        setError(msg);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [examId]);

  const questionIndex = React.useMemo(() => {
    const map = new Map<string, { number: number; text: string }>();
    for (const q of exam?.questionsList ?? []) {
      map.set(String(q.id), { number: q.number, text: q.text });
    }
    return map;
  }, [exam?.questionsList]);

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-[60vh]">در حال بارگذاری نتیجه...</div>;
  }

  if (error || !examId) {
    return (
      <main className="p-4 md:p-8 max-w-5xl mx-auto">
        <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
          <h1 className="text-lg font-bold">نتیجه آزمون</h1>
          <div className="text-sm text-muted-foreground">{error || 'شناسه آزمون نامعتبر است.'}</div>
          <div className="flex gap-2">
            <Link href="/exam-prep">
              <Button variant="outline">بازگشت به لیست آزمون‌ها</Button>
            </Link>
            {examId ? (
              <Link href={`/exam/${examId}`}>
                <Button>بازگشت به آزمون</Button>
              </Link>
            ) : null}
          </div>
        </div>
      </main>
    );
  }

  if (!result) {
    return (
      <main className="p-4 md:p-8 max-w-5xl mx-auto">
        <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
          <h1 className="text-lg font-bold">نتیجه آزمون</h1>
          <div className="text-sm text-muted-foreground">نتیجه‌ای برای نمایش وجود ندارد.</div>
          <div className="flex gap-2">
            <Link href={`/exam/${examId}`}>
              <Button>بازگشت به آزمون</Button>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const items = Array.isArray(result.items) ? result.items : [];

  const handleRetake = async () => {
    const eid = String(examId ?? '').trim();
    if (!eid || isResetting) return;
    setIsResetting(true);
    try {
      await DashboardService.resetExamPrepAttempt(eid);
      router.push(`/exam/${eid}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'خطا در شروع آزمون مجدد';
      setError(msg);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <main className="p-4 md:p-8 max-w-5xl mx-auto space-y-6">
      <div className="bg-card border border-border rounded-2xl p-6 space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-bold">نتیجه آزمون</h1>
            <div className="text-sm text-muted-foreground">{exam?.title ?? ''}</div>
          </div>
          <Badge variant={result.finalized ? 'default' : 'secondary'}>
            {result.finalized ? 'نهایی شده' : 'پیش‌نویس'}
          </Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="bg-background border border-border rounded-xl p-4">
            <div className="text-xs text-muted-foreground">نمره</div>
            <div className="text-2xl font-bold">{result.score_0_100}</div>
          </div>
          <div className="bg-background border border-border rounded-xl p-4">
            <div className="text-xs text-muted-foreground">پاسخ درست</div>
            <div className="text-2xl font-bold">{result.correct_count}</div>
          </div>
          <div className="bg-background border border-border rounded-xl p-4">
            <div className="text-xs text-muted-foreground">تعداد سوال</div>
            <div className="text-2xl font-bold">{result.total_questions}</div>
          </div>
        </div>

        <div className="flex gap-2">
          <Button variant="outline" onClick={handleRetake} disabled={isResetting}>
            {isResetting ? 'در حال آماده‌سازی...' : 'آزمون مجدد'}
          </Button>
          <Link href="/exam-prep">
            <Button>بازگشت به لیست آزمون‌ها</Button>
          </Link>
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-6">
        <h2 className="text-base font-bold mb-4">جزئیات پاسخ‌ها</h2>
        <div className="space-y-3">
          {items.map((it) => {
            const meta = questionIndex.get(String(it.question_id));
            const number = meta?.number ?? '?';
            const qText = meta?.text ?? '';
            const selected = String(it.selected_label || result.answers?.[String(it.question_id)] || '').trim();

            const question = (exam?.questionsList ?? []).find(q => String(q.id) === String(it.question_id));
            const optionIndex = question?.options?.findIndex(o => String(o.label).trim() === selected) ?? -1;
            const selectedOption = optionIndex >= 0 ? (question?.options?.[optionIndex] ?? null) : null;
            const displayLabel = selected ? toPersianOptionLabel(selected, optionIndex >= 0 ? optionIndex : undefined) : '';

            const status = result.finalized
              ? it.is_correct
                ? { label: 'درست', className: 'bg-green-500/15 text-green-600 border-green-500/30' }
                : { label: 'غلط', className: 'bg-red-500/15 text-red-600 border-red-500/30' }
              : { label: 'نامشخص', className: 'bg-secondary text-secondary-foreground' };

            return (
              <div key={it.question_id} className="bg-background border border-border rounded-xl p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="text-sm font-semibold">سوال {number}</div>
                    {qText ? <MarkdownWithMath markdown={qText} className="text-sm text-muted-foreground" renderKey={`res-q-${it.question_id}`} /> : null}
                  </div>
                  <span className={["text-xs px-2 py-1 rounded-md border", status.className].join(' ')}>{status.label}</span>
                </div>

                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                  <div className="flex items-center justify-between gap-2 bg-card border border-border rounded-lg px-3 py-2">
                    <span className="text-muted-foreground">پاسخ شما</span>
                    {selected ? (
                      <span className="font-semibold text-right" dir="rtl">
                        {displayLabel ? `${displayLabel}) ` : ''}
                        {selectedOption?.text ? (
                          <MarkdownWithMath
                            as="span"
                            markdown={selectedOption.text}
                            className="inline leading-6"
                            renderKey={`res-ans-${it.question_id}-${selected}`}
                          />
                        ) : (
                          <span>{displayLabel || selected}</span>
                        )}
                      </span>
                    ) : (
                      <span className="font-semibold">ثبت نشده</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
