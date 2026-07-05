'use client';

/**
 * Student exercise solver: per-section text/image answers with draft autosave,
 * a section-aware assistant widget, and a final submit. The solving view never
 * receives the reference answer (the server withholds it until reveal).
 * Design: docs/features/exercise-hub.md.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Loader2, Send, Lock } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { ExerciseAssistant } from '@/components/dashboard/exercises/exercise-assistant';
import {
  type StudentExerciseDetail,
  type StudentAnswers,
  getStudentExercise,
  saveExerciseDraft,
  uploadAnswerImage,
  submitExercise,
} from '@/services/exercises-service';

export function ExerciseSolver({
  sessionId,
  exerciseId,
}: {
  sessionId: number;
  exerciseId: number;
}) {
  const router = useRouter();
  const [detail, setDetail] = useState<StudentExerciseDetail | null>(null);
  const [answers, setAnswers] = useState<StudentAnswers>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [activeSection, setActiveSection] = useState(0);
  const dirty = useRef(false);

  useEffect(() => {
    getStudentExercise(sessionId, exerciseId)
      .then((d) => {
        setDetail(d);
        setAnswers(d.myAnswers ?? {});
      })
      .catch((err) => toast.error(err instanceof Error ? err.message : 'خطا در بارگذاری تمرین'))
      .finally(() => setLoading(false));
  }, [sessionId, exerciseId]);

  const alreadySubmitted =
    detail?.submissionStatus != null && detail.submissionStatus !== 'draft';

  // Debounced autosave.
  const persistDraft = useCallback(
    (next: StudentAnswers) => {
      if (alreadySubmitted) return;
      saveExerciseDraft(sessionId, exerciseId, next).catch(() => {
        /* best-effort autosave */
      });
    },
    [sessionId, exerciseId, alreadySubmitted]
  );

  useEffect(() => {
    if (!dirty.current) return;
    const t = window.setTimeout(() => persistDraft(answers), 1200);
    return () => window.clearTimeout(t);
  }, [answers, persistDraft]);

  const setText = (qid: number, text: string) => {
    dirty.current = true;
    setAnswers((prev) => ({ ...prev, [qid]: { ...prev[String(qid)], text } }));
  };

  const addImage = async (qid: number, file: File) => {
    try {
      const { path } = await uploadAnswerImage(sessionId, exerciseId, qid, file);
      setAnswers((prev) => {
        const entry = prev[String(qid)] ?? {};
        return { ...prev, [qid]: { ...entry, images: [...(entry.images ?? []), path] } };
      });
      toast.success('تصویر پاسخ بارگذاری شد.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'بارگذاری تصویر ناموفق بود.');
    }
  };

  const doSubmit = async () => {
    setSubmitting(true);
    try {
      await submitExercise(sessionId, exerciseId, answers);
      toast.success('پاسخ شما ارسال شد. نتیجه پس از نمره‌دهی نمایش داده می‌شود.');
      router.push(`/exercises/${exerciseId}/result?session=${sessionId}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ارسال ناموفق بود.');
    } finally {
      setSubmitting(false);
    }
  };

  const section = useMemo(() => detail?.sections[activeSection], [detail, activeSection]);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!detail) {
    return <p className="py-16 text-center text-muted-foreground">تمرین پیدا نشد.</p>;
  }

  return (
    <div dir="rtl" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">
          <MarkdownWithMath markdown={detail.title} as="span" />
        </h1>
        {alreadySubmitted && <Badge variant="secondary">ارسال‌شده</Badge>}
      </div>

      {/* Section chips */}
      {detail.sections.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {detail.sections.map((s, i) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setActiveSection(i)}
              className={`shrink-0 rounded-full px-3 py-1 text-sm transition-colors ${
                i === activeSection
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {s.title || `بخش ${i + 1}`}
            </button>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          {section?.questions.map((q) => (
            <Card key={q.id}>
              <CardHeader>
                <CardTitle className="text-base font-normal">
                  <MarkdownWithMath markdown={q.questionMarkdown} />
                  <span className="mt-1 block text-xs text-muted-foreground">{q.maxPoints} نمره</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Textarea
                  placeholder="پاسخ خود را بنویسید…"
                  value={answers[String(q.id)]?.text ?? ''}
                  onChange={(e) => setText(q.id, e.target.value)}
                  disabled={alreadySubmitted}
                  rows={4}
                />
                {!alreadySubmitted && (
                  <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
                    <Input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void addImage(q.id, f);
                      }}
                    />
                    <span className="rounded-md border border-dashed border-border px-3 py-1">
                      + بارگذاری عکسِ پاسخِ دست‌نویس
                    </span>
                  </label>
                )}
                {(answers[String(q.id)]?.images?.length ?? 0) > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {answers[String(q.id)]?.images?.length} تصویر بارگذاری شد
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Assistant */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          {section && detail.assistantEnabled && section.assistantEnabled ? (
            <ExerciseAssistant
              sessionId={sessionId}
              exerciseId={exerciseId}
              questionId={section.questions[0]?.id ?? 0}
            />
          ) : (
            <Card>
              <CardContent className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Lock className="h-4 w-4" />
                دستیار برای این بخش غیرفعال است
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {!alreadySubmitted && (
        <div className="sticky bottom-0 flex justify-end border-t border-border bg-background/90 py-3 backdrop-blur">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button disabled={submitting}>
                {submitting ? <Loader2 className="ms-2 h-4 w-4 animate-spin" /> : <Send className="ms-2 h-4 w-4" />}
                ارسال پاسخ‌ها
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent dir="rtl">
              <AlertDialogHeader>
                <AlertDialogTitle>ارسال نهایی پاسخ‌ها</AlertDialogTitle>
                <AlertDialogDescription>
                  پس از ارسال، امکان ویرایش پاسخ‌ها را نخواهید داشت. مطمئن هستید؟
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>بازگشت</AlertDialogCancel>
                <AlertDialogAction onClick={doSubmit}>ارسال نهایی</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      )}
    </div>
  );
}
