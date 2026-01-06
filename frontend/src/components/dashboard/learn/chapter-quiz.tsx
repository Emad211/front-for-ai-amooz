'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { DashboardService } from '@/services/dashboard-service';

type QuizQuestion = {
  id: string;
  type: string;
  question: string;
  options?: string[];
};

type QuizPayload = {
  quiz_id: number;
  session_id: number;
  chapter_id: string;
  chapter_title: string;
  passing_score: number;
  questions: QuizQuestion[];
  last_score_0_100?: number | null;
  last_passed?: boolean | null;
};

type SubmitPayload = {
  score_0_100: number;
  passed: boolean;
  passing_score: number;
  per_question: Array<Record<string, any>>;
};

export function ChapterQuiz({ courseId, chapterId, chapterTitle }: { courseId: string; chapterId: string; chapterTitle: string }) {
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [quiz, setQuiz] = React.useState<QuizPayload | null>(null);
  const [answers, setAnswers] = React.useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [submitResult, setSubmitResult] = React.useState<SubmitPayload | null>(null);

  const load = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setSubmitResult(null);
    try {
      const q = await DashboardService.getChapterQuiz(courseId, chapterId);
      setQuiz(q);
      const init: Record<string, string> = {};
      (q?.questions ?? []).forEach((qq: QuizQuestion) => {
        init[qq.id] = '';
      });
      setAnswers(init);
    } catch (e: any) {
      setError(e?.message || 'خطا در دریافت آزمون');
    } finally {
      setIsLoading(false);
    }
  }, [courseId, chapterId]);

  React.useEffect(() => {
    load();
  }, [load]);

  const onSubmit = async () => {
    if (!quiz) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await DashboardService.submitChapterQuiz(courseId, chapterId, answers);
      setSubmitResult(res);
      // refresh quiz meta (last score/pass)
      try {
        const q2 = await DashboardService.getChapterQuiz(courseId, chapterId);
        setQuiz(q2);
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
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-10 w-32" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-3">
        <div className="text-sm text-destructive">{error}</div>
        <Button variant="outline" onClick={load}>تلاش مجدد</Button>
      </div>
    );
  }

  if (!quiz) {
    return (
      <div className="space-y-3">
        <div className="text-sm text-muted-foreground">آزمون در دسترس نیست.</div>
        <Button variant="outline" onClick={load}>تلاش مجدد</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-base font-bold text-foreground">آزمون فصل: {chapterTitle}</h3>
          <div className="text-xs text-muted-foreground mt-1">حد نصاب قبولی: {quiz.passing_score} از ۱۰۰</div>
        </div>
        {typeof quiz.last_score_0_100 === 'number' && (
          <div className="text-sm">
            <span className="text-muted-foreground">آخرین نمره: </span>
            <span className="font-bold text-foreground">{quiz.last_score_0_100}</span>
          </div>
        )}
      </div>

      <div className="space-y-5">
        {quiz.questions.map((q, idx) => {
          const value = answers[q.id] ?? '';
          return (
            <div key={q.id} className="border border-border rounded-xl p-4 bg-background/20">
              <div className="text-sm font-bold text-foreground mb-2">سوال {idx + 1}</div>
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
