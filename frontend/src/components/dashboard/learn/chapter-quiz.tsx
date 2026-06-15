'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { MathText } from '@/components/content/math-text';
import { DashboardService } from '@/services/dashboard-service';
import { CheckCircle2, XCircle, RotateCcw, AlertCircle, Sparkles } from 'lucide-react';

type QStatus = 'correct' | 'partial' | 'wrong' | null;

// Status of a per-question grading result. Backend never returns the correct
// answer (anti-leak), so we color by correctness/score only.
function questionStatus(r: any): QStatus {
  if (!r) return null;
  if (r.label === 'correct') return 'correct';
  if (r.label === 'incorrect') return 'wrong';
  const s = Number(r.score_0_100);
  if (!Number.isFinite(s)) return null;
  return s >= 70 ? 'correct' : s > 0 ? 'partial' : 'wrong';
}

const STATUS_CARD: Record<'correct' | 'partial' | 'wrong', string> = {
  correct: 'border-green-500/50 bg-green-500/[0.06]',
  partial: 'border-amber-500/50 bg-amber-500/[0.06]',
  wrong: 'border-rose-500/50 bg-rose-500/[0.06]',
};

// Display form of a question's correct answer (true/false → صحیح/غلط).
function correctAnswerText(value: unknown): string {
  if (value === true || String(value).toLowerCase() === 'true') return 'صحیح';
  if (value === false || String(value).toLowerCase() === 'false') return 'غلط';
  return String(value ?? '').trim();
}

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
  const [isRegenerating, setIsRegenerating] = React.useState(false);
  const [submitResult, setSubmitResult] = React.useState<SubmitPayload | null>(null);
  const resultRef = React.useRef<HTMLDivElement | null>(null);

  const resultById = React.useMemo(() => {
    const m: Record<string, any> = {};
    (submitResult?.per_question ?? []).forEach((pq: any) => {
      m[String(pq.id)] = pq;
    });
    return m;
  }, [submitResult]);
  const reviewing = !!submitResult;

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

  // Scroll the result into view once it renders — the submit button is below a
  // long form, so the score/feedback was easy to miss (felt like nothing happened).
  React.useEffect(() => {
    if (submitResult) {
      resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [submitResult]);

  // The learning loop: after a fail, build a NEW quiz focused on the concepts
  // the student missed and load it fresh (leaving review mode).
  const onRegenerate = async () => {
    setIsRegenerating(true);
    setError(null);
    try {
      const q = await DashboardService.regenerateChapterQuiz(courseId, chapterId);
      setQuiz(q);
      const init: Record<string, string> = {};
      (q?.questions ?? []).forEach((qq: QuizQuestion) => {
        init[qq.id] = '';
      });
      setAnswers(init);
      setSubmitResult(null);
    } catch (e: any) {
      setError(e?.message || 'ساخت آزمون جدید با خطا مواجه شد. کمی بعد دوباره تلاش کنید.');
    } finally {
      setIsRegenerating(false);
    }
  };

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
          <h3 className="text-base font-bold text-foreground">آزمون فصل: <MathText text={chapterTitle} /></h3>
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
          const r = resultById[q.id];
          const status = reviewing ? questionStatus(r) : null;
          return (
            <div
              key={q.id}
              className={`border rounded-xl p-4 transition-colors ${
                status ? STATUS_CARD[status] : 'border-border bg-background/20'
              }`}
            >
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="text-sm font-bold text-foreground">سوال {idx + 1}</span>
                {reviewing && status && (
                  <span
                    className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-md ${
                      status === 'correct'
                        ? 'bg-green-500/15 text-green-500'
                        : status === 'partial'
                        ? 'bg-amber-500/15 text-amber-500'
                        : 'bg-rose-500/15 text-rose-500'
                    }`}
                  >
                    {status === 'correct' ? (
                      <><CheckCircle2 className="h-3.5 w-3.5" /> درست</>
                    ) : status === 'wrong' ? (
                      <><XCircle className="h-3.5 w-3.5" /> نادرست</>
                    ) : (
                      <>نمره {r?.score_0_100} از ۱۰۰</>
                    )}
                  </span>
                )}
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
                <div className="mt-3 grid grid-cols-2 gap-2 sm:gap-3">
                  {[
                    { val: 'صحیح', label: 'صحیح ✓' },
                    { val: 'غلط', label: 'غلط ✗' },
                  ].map((tf) => {
                    const selected = value === tf.val;
                    const isCorrectTF = reviewing && correctAnswerText(r?.correct_answer) === tf.val;
                    const cls = reviewing
                      ? isCorrectTF
                        ? 'border-green-500 bg-green-500/10 text-green-600'
                        : selected
                        ? 'border-rose-500 bg-rose-500/10 text-rose-600'
                        : 'border-border bg-background opacity-50'
                      : selected
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-background hover:bg-secondary/50';
                    return (
                      <label
                        key={tf.val}
                        className={`flex items-center justify-center gap-2 p-3 rounded-lg border text-xs sm:text-sm font-semibold ${
                          reviewing ? 'cursor-default' : 'cursor-pointer'
                        } ${cls}`}
                      >
                        <input
                          type="radio"
                          name={`q_${q.id}`}
                          value={tf.val}
                          checked={selected}
                          disabled={reviewing}
                          onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: tf.val }))}
                          className="sr-only"
                        />
                        {tf.label}
                      </label>
                    );
                  })}
                </div>
              )}

              {/* Multiple choice (incl. fallback when type is missing but options exist) */}
              {(q.type === 'multiple_choice' || (!q.type && Array.isArray(q.options) && q.options.length > 0)) && q.type !== 'true_false' && (
                <div className="mt-3 space-y-2">
                  {(q.options ?? []).map((opt) => {
                    const selected = value === opt;
                    const isCorrectOpt =
                      reviewing && r?.correct_answer != null &&
                      String(opt).trim() === String(r.correct_answer).trim();
                    const cls = reviewing
                      ? isCorrectOpt
                        ? 'border-green-500 bg-green-500/10'   // the correct option (revealed)
                        : selected
                        ? 'border-rose-500 bg-rose-500/10'     // your wrong choice
                        : 'border-border opacity-50'
                      : selected
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:bg-secondary/40';
                    return (
                      <label
                        key={opt}
                        className={`flex items-start gap-2 p-2.5 rounded-lg border ${
                          reviewing ? 'cursor-default' : 'cursor-pointer'
                        } ${cls}`}
                      >
                        <input
                          type="radio"
                          name={`q_${q.id}`}
                          value={opt}
                          checked={selected}
                          disabled={reviewing}
                          onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                          className="mt-1 shrink-0"
                        />
                        <span className="text-xs sm:text-sm text-foreground break-words">
                          <MarkdownWithMath markdown={opt} />
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}

              {/* Fill blank / Short answer / fallback textarea */}
              {(q.type === 'fill_blank' || q.type === 'short_answer' || (!q.type && (!q.options || q.options.length === 0))) && q.type !== 'true_false' && q.type !== 'multiple_choice' && (
                <textarea
                  value={value}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                  disabled={reviewing}
                  className="mt-3 w-full min-h-24 rounded-lg border border-border bg-background p-3 text-sm text-foreground disabled:opacity-70"
                  placeholder={q.type === 'fill_blank' ? 'پاسخ خود را برای جای خالی بنویسید...' : 'پاسخ خود را بنویسید...'}
                  dir="rtl"
                />
              )}

              {/* Inline feedback + revealed correct answer (after submission) */}
              {reviewing && r && (r.feedback || (status !== 'correct' && correctAnswerText(r.correct_answer))) && (
                <div
                  className={`mt-3 rounded-lg border p-3 text-sm leading-relaxed ${
                    status === 'correct'
                      ? 'border-green-500/30 bg-green-500/[0.06] text-foreground'
                      : status === 'partial'
                      ? 'border-amber-500/30 bg-amber-500/[0.06] text-foreground'
                      : 'border-rose-500/30 bg-rose-500/[0.06] text-foreground'
                  }`}
                >
                  {r.feedback && (
                    <div>
                      <span className="font-bold">بازخورد: </span>
                      <MarkdownWithMath markdown={r.feedback} />
                    </div>
                  )}
                  {status !== 'correct' && correctAnswerText(r.correct_answer) && (
                    <div className={r.feedback ? 'mt-2' : ''}>
                      <span className="font-bold text-green-600 dark:text-green-500">پاسخ صحیح: </span>
                      <MarkdownWithMath markdown={correctAnswerText(r.correct_answer)} />
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Result summary — scrolled into view on submit so it's never missed. */}
      {submitResult && (
        <div
          ref={resultRef}
          className={`rounded-xl border p-4 ${
            submitResult.passed
              ? 'border-green-500/50 bg-green-500/[0.06]'
              : 'border-amber-500/50 bg-amber-500/[0.06]'
          }`}
        >
          <div className="flex items-center gap-3">
            {submitResult.passed ? (
              <CheckCircle2 className="h-7 w-7 text-green-500 shrink-0" />
            ) : (
              <AlertCircle className="h-7 w-7 text-amber-500 shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <div className="text-base font-bold text-foreground">
                {submitResult.passed ? 'آفرین! قبول شدی 🎉' : 'نیاز به مرور بیشتر'}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                نمره شما <span className="font-bold text-foreground">{submitResult.score_0_100}</span> از ۱۰۰
                {' · '}حد نصاب {submitResult.passing_score}
                {' · '}پاسخ صحیح:{' '}
                {submitResult.per_question.filter((p: any) => questionStatus(p) === 'correct').length} از{' '}
                {quiz.questions.length}
              </div>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            بازخورد و پاسخ صحیح هر سؤال در کادر همان سؤال (بالا) مشخص شده است.
          </p>
          {!submitResult.passed && (
            <div className="mt-4 flex flex-col sm:flex-row sm:items-center gap-2">
              <Button onClick={onRegenerate} disabled={isRegenerating} className="rounded-xl gap-2">
                <Sparkles className="h-4 w-4" />
                {isRegenerating ? 'در حال ساخت آزمون جدید…' : 'آزمون جدید روی نقاط ضعف من'}
              </Button>
              <span className="text-xs text-muted-foreground">
                یک آزمون تازه از مباحثی که اشتباه زدی ساخته می‌شود.
              </span>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        {!reviewing && (
          <Button onClick={onSubmit} disabled={isSubmitting} className="rounded-xl">
            {isSubmitting ? 'در حال ارسال...' : 'ثبت پاسخ‌ها و دریافت نمره'}
          </Button>
        )}
        <Button variant="outline" onClick={load} disabled={isSubmitting || isRegenerating} className="rounded-xl gap-2">
          <RotateCcw className="h-4 w-4" />
          {reviewing ? 'تلاش دوباره' : 'پاک کردن پاسخ‌ها'}
        </Button>
      </div>
    </div>
  );
}
