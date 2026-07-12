'use client';

/** «پاسخ تمرین‌های تمام‌شده» — reference answers of past (deadline-passed) exercises. */
import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { MathText } from '@/components/content/math-text';
import { type FinishedAnswer, getFinishedAnswers } from '@/services/exercises-service';

export default function FinishedAnswersPage() {
  const [items, setItems] = useState<FinishedAnswer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getFinishedAnswers()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main dir="rtl" className="container mx-auto max-w-3xl px-4 py-6 md:py-8">
      <h1 className="mb-6 text-xl font-bold md:text-2xl">پاسخ تمرین‌های تمام‌شده</h1>
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : items.length === 0 ? (
        <p className="rounded-md border border-dashed border-border py-10 text-center text-muted-foreground">
          هنوز تمرینی با مهلتِ گذشته ندارید.
        </p>
      ) : (
        <div className="space-y-4">
          {items.map((ex) => (
            <Card key={ex.id}>
              <CardHeader>
                <CardTitle className="text-base">
                  <MathText text={ex.title} />
                  <MathText
                    text={ex.courseTitle}
                    className="ms-2 text-xs font-normal text-muted-foreground"
                  />
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {ex.questions.map((question, index) => (
                  <div key={question.id} className="space-y-2 rounded-md border border-border p-3">
                    <p className="text-sm font-semibold text-muted-foreground">سوال {index + 1}</p>
                    <MarkdownWithMath markdown={question.questionMarkdown} />
                    {question.referenceAnswerMarkdown && (
                      <div className="rounded-md bg-muted p-2 text-sm">
                        <p className="mb-1 font-medium text-muted-foreground">پاسخ مرجع:</p>
                        <MarkdownWithMath markdown={question.referenceAnswerMarkdown} />
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
