'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { DashboardService } from '@/services/dashboard-service';

type FinalExamQuestion = {
  id: string;
  type: string;
  question: string;
  options?: string[];
  points?: number;
  chapter?: string;
};

type FinalExamPayload = {
  exam_id: number;
  session_id: number;
  exam_title: string;
  time_limit: number;
  passing_score: number;
  questions: FinalExamQuestion[];
  last_score_0_100?: number | null;
  last_passed?: boolean | null;
};

type SubmitPayload = {
  score_0_100: number;
  passed: boolean;
  passing_score: number;
  per_question: Array<Record<string, any>>;
};

export function FinalExam({ courseId }: { courseId: string }) {
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [exam, setExam] = React.useState<FinalExamPayload | null>(null);
  const [answers, setAnswers] = React.useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [submitResult, setSubmitResult] = React.useState<SubmitPayload | null>(null);

  const load = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setSubmitResult(null);
    try {
      const q = await DashboardService.getFinalExam(courseId);
      setExam(q);
      const init: Record<string, string> = {};
      (q?.questions ?? []).forEach((qq: FinalExamQuestion) => {
        init[qq.id] = '';
      });
      setAnswers(init);
    } catch (e: any) {
      setError(e?.message || 'خطا در دریافت آزمون نهایی');
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  React.useEffect(() => {
    load();
  }, [load]);

  const onSubmit = async () => {
    if (!exam) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await DashboardService.submitFinalExam(courseId, answers);
      setSubmitResult(res);
      try {
        const q2 = await DashboardService.getFinalExam(courseId);
        setExam(q2);
      } catch {
        // ignore
      }
    } catch (e: any) {
      setError(e?.message || 'خطا در ثبت پاسخ‌ها');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-56" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-10 w-32" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-3">
        <div className="text-sm text-destructive">{error}</div>
        <Button variant="outline" onClick={load}>
          تلاش مجدد
        </Button>
      </div>
    );
  }

  if (!exam) {
    return (
      <div className="space-y-3">
        <div className="text-sm text-muted-foreground">آزمون نهایی در دسترس نیست.</div>
        <Button variant="outline" onClick={load}>
          تلاش مجدد
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-base font-bold text-foreground">{exam.exam_title}</h3>
          <div className="text-xs text-muted-foreground mt-1">
            حد نصاب قبولی: {exam.passing_score} از ۱۰۰ · زمان: {exam.time_limit} دقیقه
          </div>
        </div>
        {typeof exam.last_score_0_100 === 'number' && (
          <div className="text-sm">
            <span className="text-muted-foreground">آخرین نمره: </span>
            <span className="font-bold text-foreground">{exam.last_score_0_100}</span>
          </div>
        )}
      </div>

      <div className="space-y-5">
        {exam.questions.map((q, idx) => {
          const value = answers[q.id] ?? '';
          return (
            <div key={q.id} className="border border-border rounded-xl p-4 bg-background/20">
              <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                <div className="text-sm font-bold text-foreground">سوال {idx + 1}</div>
                {typeof q.points === 'number' && (
                  <div className="text-xs text-muted-foreground">امتیاز: {q.points}</div>
                )}
              </div>

              <div className="text-sm text-muted-foreground leading-relaxed">
                <MarkdownWithMath markdown={q.question} />
              </div>

              {Array.isArray(q.options) && q.options.length > 0 ? (
                <div className="mt-3 space-y-2">
                  {q.options.map((opt) => (
                    <label key={opt} className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name={`q_${q.id}`}
                        value={opt}
                        checked={value === opt}
                        onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                        className="mt-1"
                      />
                      <span className="text-sm text-foreground">{opt}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <textarea
                  value={value}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                  className="mt-3 w-full min-h-24 rounded-lg border border-border bg-background p-3 text-sm text-foreground"
                  placeholder="پاسخ خود را بنویسید..."
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        <Button onClick={onSubmit} disabled={isSubmitting} className="rounded-xl">
          {isSubmitting ? 'در حال ارسال...' : 'ثبت پاسخ‌ها و دریافت نمره'}
        </Button>
        <Button variant="outline" onClick={load} disabled={isSubmitting} className="rounded-xl">
          بازخوانی آزمون
        </Button>
      </div>

      {submitResult && (
        <div className="border border-border rounded-xl p-4 bg-card">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="text-sm">
              <span className="text-muted-foreground">نمره: </span>
              <span className="font-bold text-foreground">{submitResult.score_0_100}</span>
            </div>
            <div className={submitResult.passed ? 'text-sm text-green-500 font-bold' : 'text-sm text-destructive font-bold'}>
              {submitResult.passed ? 'قبول شدی' : 'نیاز به مرور بیشتر'}
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {submitResult.per_question.map((pq: any) => (
              <div key={pq.id} className="text-sm text-muted-foreground border-t border-border/50 pt-3">
                <div className="font-bold text-foreground">{pq.question}</div>
                {pq.feedback && <div className="mt-1">بازخورد: {pq.feedback}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
