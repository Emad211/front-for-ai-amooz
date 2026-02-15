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
  course_progress?: number;
};

export function ChapterQuiz({
  courseId,
  chapterId,
  chapterTitle,
  onProgressUpdate,
}: {
  courseId: string;
  chapterId: string;
  chapterTitle: string;
  onProgressUpdate?: (progress: number) => void;
}) {
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
      const maybeProgress = Number(res?.course_progress);
      if (Number.isFinite(maybeProgress)) {
        onProgressUpdate?.(Math.max(0, Math.min(100, maybeProgress)));
      }
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
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-bold text-foreground">سوال {idx + 1}</span>
                {q.type === 'true_false' && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-blue-500/15 text-blue-400">صحیح / غلط</span>
                )}
                {q.type === 'fill_blank' && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-400">جای خالی</span>
                )}
                {q.type === 'short_answer' && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-purple-500/15 text-purple-400">تشریحی</span>
                )}
                {q.type === 'multiple_choice' && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-green-500/15 text-green-400">چندگزینه‌ای</span>
                )}
              </div>
              <div className="text-sm text-muted-foreground leading-relaxed">
                <MarkdownWithMath markdown={q.question} />
              </div>

              {/* True / False */}
              {q.type === 'true_false' && (
                <div className="mt-3 grid grid-cols-2 gap-3">
                  {[
                    { val: 'صحیح', label: 'صحیح ✓' },
                    { val: 'غلط', label: 'غلط ✗' },
                  ].map((tf) => (
                    <label
                      key={tf.val}
                      className={`flex items-center justify-center gap-2 p-3 rounded-lg border cursor-pointer text-sm font-semibold ${
                        value === tf.val
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border bg-background hover:bg-secondary/50'
                      }`}
                    >
                      <input
                        type="radio"
                        name={`q_${q.id}`}
                        value={tf.val}
                        checked={value === tf.val}
                        onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: tf.val }))}
                        className="sr-only"
                      />
                      {tf.label}
                    </label>
                  ))}
                </div>
              )}

              {/* Multiple choice (incl. fallback when type is missing but options exist) */}
              {(q.type === 'multiple_choice' || (!q.type && Array.isArray(q.options) && q.options.length > 0)) && q.type !== 'true_false' && (
                <div className="mt-3 space-y-2">
                  {(q.options ?? []).map((opt) => (
                    <label key={opt} className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name={`q_${q.id}`}
                        value={opt}
                        checked={value === opt}
                        onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                        className="mt-1"
                      />
                      <span className="text-sm text-foreground">
                        <MarkdownWithMath markdown={opt} />
                      </span>
                    </label>
                  ))}
                </div>
              )}

              {/* Fill blank / Short answer / fallback textarea */}
              {(q.type === 'fill_blank' || q.type === 'short_answer' || (!q.type && (!q.options || q.options.length === 0))) && q.type !== 'true_false' && q.type !== 'multiple_choice' && (
                <textarea
                  value={value}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                  className="mt-3 w-full min-h-24 rounded-lg border border-border bg-background p-3 text-sm text-foreground"
                  placeholder={q.type === 'fill_blank' ? 'پاسخ خود را برای جای خالی بنویسید...' : 'پاسخ خود را بنویسید...'}
                  dir="rtl"
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
