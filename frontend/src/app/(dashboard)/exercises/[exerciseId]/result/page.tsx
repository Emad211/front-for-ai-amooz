'use client';

/** Student per-exercise result: own scores/feedback; reference answers only if revealed. */
import { use, useEffect, useState } from 'react';
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

export default function StudentExerciseResultPage({ params }: PageProps) {
  const { exerciseId } = use(params);
  const sessionId = Number(useSearchParams().get('session'));
  const [result, setResult] = useState<ExerciseResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!Number.isFinite(sessionId)) {
      setLoading(false);
      return;
    }
    getExerciseResult(sessionId, Number(exerciseId))
      .then(setResult)
      .catch(() => setResult(null))
      .finally(() => setLoading(false));
  }, [sessionId, exerciseId]);

  const questionById = new Map<string, StudentQuestion>();
  result?.exercise?.sections.forEach((s) =>
    s.questions.forEach((q) => questionById.set(String(q.id), q))
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
          <CardContent className="py-10 text-center text-muted-foreground">
            {result.detail ?? 'پاسخ شما ارسال شد. نتیجه پس از نمره‌دهی در همین‌جا نمایش داده می‌شود.'}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
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
            const wrong = (pq.score_points ?? 0) < (pq.max_points ?? 0);
            return (
              <Card key={pq.question_id} className={wrong ? 'border-destructive/40' : 'border-primary/40'}>
                <CardContent className="space-y-2 py-4">
                  {q && <MarkdownWithMath markdown={q.questionMarkdown} />}
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
