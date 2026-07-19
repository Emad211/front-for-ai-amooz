'use client';

/** Student per-exercise result: own scores/feedback; reference answers only if revealed. */
import { use, useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import {
  type ExerciseResult,
  type StudentQuestion,
  getExerciseResult,
} from '@/services/exercises-service';

interface PageProps {
  params: Promise<{ exerciseId: string }>;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '')
  .replace(/\/+$/, '')
  .replace(/\/api$/, '');

function answerImageUrl(path: string): string {
  const value = String(path).trim();
  if (/^(https?:)?\/\//i.test(value) || value.startsWith('data:')) return value;
  return `${API_BASE}/media/${value.replace(/^\/+/, '').replace(/^media\//, '')}`;
}

export default function StudentExerciseResultPage({ params }: PageProps) {
  const { exerciseId } = use(params);
  const sessionId = Number(useSearchParams().get('session'));
  const [result, setResult] = useState<ExerciseResult | null>(null);
  const [loading, setLoading] = useState(true);
  const requestIdRef = useRef(0);

  const loadResult = useCallback(async (attemptId?: number) => {
    const requestId = ++requestIdRef.current;
    try {
      const nextResult = await getExerciseResult(sessionId, Number(exerciseId), attemptId);
      if (requestId === requestIdRef.current) setResult(nextResult);
    } catch {
      if (requestId === requestIdRef.current) setResult(null);
    }
  }, [sessionId, exerciseId]);

  useEffect(() => {
    if (!Number.isFinite(sessionId)) {
      requestIdRef.current += 1;
      setLoading(false);
      return;
    }
    loadResult().finally(() => setLoading(false));
  }, [sessionId, loadResult]);

  const questionById = new Map<string, StudentQuestion>();
  result?.exercise?.questions.forEach((question) =>
    questionById.set(String(question.id), question)
  );

  return (
    <main dir="rtl" className="container mx-auto max-w-3xl px-4 py-6 md:py-8">
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !result ? (
        <p className="py-16 text-center text-muted-foreground">نتیجه‌ای یافت نشد.</p>
      ) : result.status !== 'graded' ? (
        <Card>
          <CardContent className="space-y-4 py-10 text-center text-muted-foreground">
            <AttemptPicker result={result} onSelect={loadResult} />
            <p>{result.detail ?? 'پاسخ شما ارسال شد. نتیجه پس از نمره‌دهی در همین‌جا نمایش داده می‌شود.'}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <AttemptPicker result={result} onSelect={loadResult} />
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base">
                <span>کارنامهٔ این تمرین</span>
                <Badge variant="default">
                  {result.scorePoints} از {result.maxPoints}
                </Badge>
              </CardTitle>
            </CardHeader>
          </Card>

          {(result.result?.per_question ?? []).map((pq) => {
            const q = questionById.get(pq.question_id);
            const answer = result.answers?.[pq.question_id];
            const wrong = (pq.score_points ?? 0) < (pq.max_points ?? 0);
            return (
              <Card key={pq.question_id} className={wrong ? 'border-destructive/40' : 'border-primary/40'}>
                <CardContent className="space-y-2 py-4">
                  {q && <MarkdownWithMath markdown={q.questionMarkdown} />}
                  <div className="rounded-md border border-border/70 p-2 text-sm">
                    <p className="mb-1 text-muted-foreground">پاسخ شما:</p>
                    {answer?.text ? (
                      <MarkdownWithMath markdown={answer.text} />
                    ) : !answer?.images?.length ? (
                      <span className="text-muted-foreground">پاسخی ثبت نشده است.</span>
                    ) : null}
                    {!!answer?.images?.length && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {answer.images.map((image) => (
                          <a key={image} href={answerImageUrl(image)} target="_blank" rel="noreferrer">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={answerImageUrl(image)}
                              alt="تصویر پاسخ شما"
                              className="h-24 w-24 rounded-md border border-border object-cover"
                            />
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                  <p className="text-sm">
                    نمره: {pq.teacher_score ?? pq.score_points ?? 0} از {pq.max_points ?? 0}
                    {pq.teacher_score != null ? (
                      <Badge variant="outline" className="ms-2">
                        بازبینی‌شده توسط مدرس
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="ms-2">
                        نمره‌دهی هوشمند
                      </Badge>
                    )}
                  </p>
                  {(pq.teacher_feedback || pq.feedback) && (
                    <div className="rounded-md bg-muted p-2 text-sm">
                      <MarkdownWithMath markdown={pq.teacher_feedback || pq.feedback || ''} />
                    </div>
                  )}
                  {result.answersRevealed && q?.referenceAnswerMarkdown && (
                    <div className="rounded-md border border-border p-2 text-sm">
                      <p className="mb-1 font-medium text-muted-foreground">پاسخ مرجع:</p>
                      <MarkdownWithMath markdown={q.referenceAnswerMarkdown} />
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </main>
  );
}

function AttemptPicker({
  result,
  onSelect,
}: {
  result: ExerciseResult;
  onSelect: (attemptId?: number) => Promise<void>;
}) {
  if (!result.attempts || result.attempts.length < 2) return null;
  return (
    <div className="flex flex-wrap items-center justify-center gap-2" aria-label="تاریخچه ارسال‌ها">
      <span className="text-sm text-muted-foreground">تاریخچه:</span>
      {result.attempts.map((attempt) => (
        <button
          key={attempt.attemptId}
          type="button"
          className={`rounded-md border px-3 py-1 text-sm ${
            attempt.attemptId === result.attemptId
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border text-muted-foreground'
          }`}
          onClick={() => void onSelect(attempt.attemptId)}
        >
          ارسال {attempt.attemptNumber}
        </button>
      ))}
    </div>
  );
}
