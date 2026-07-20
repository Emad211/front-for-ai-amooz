'use client';

/**
 * Student exercise solver: flat text/image answers with draft autosave,
 * a question-aware assistant widget, and a final submit. The solving view never
 * receives the reference answer (the server withholds it until reveal).
 * Design: docs/features/exercise-hub.md.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Loader2, Send, Lock, MessageCircle } from 'lucide-react';

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
import { MathText } from '@/components/content/math-text';
import { ExerciseAssistant } from '@/components/dashboard/exercises/exercise-assistant';
import {
  QuestionAnswerOcrPreview,
  WholeAnswerOcrPanel,
} from '@/components/dashboard/exercises/answer-ocr-panel';
import { formatPersianDateTime } from '@/lib/date-utils';
import { getStoredUser } from '@/services/auth-service';
import {
  type StudentExerciseDetail,
  type StudentAnswers,
  type AnswerOcrCandidate,
  type AnswerOcrSource,
  applyExerciseAnswerSource,
  deleteExerciseAnswerAsset,
  getStudentExercise,
  saveExerciseDraft,
  updateExerciseAnswerSource,
  updateQuestionAnswerSource,
  uploadAnswerImage,
  uploadExerciseAnswerSource,
  submitExercise,
} from '@/services/exercises-service';

type DraftSaveState = 'idle' | 'pending' | 'saving' | 'saved' | 'error';

function readDraftBackup(key: string | null): StudentAnswers | null {
  if (!key) return null;
  try {
    const value = JSON.parse(window.localStorage.getItem(key) ?? 'null') as unknown;
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    const answers = (value as { answers?: unknown }).answers;
    return answers && typeof answers === 'object' && !Array.isArray(answers)
      ? (answers as StudentAnswers)
      : null;
  } catch {
    return null;
  }
}

function writeDraftBackup(key: string | null, answers: StudentAnswers) {
  if (!key) return;
  try {
    window.localStorage.setItem(key, JSON.stringify({ answers }));
  } catch {
    // Server autosave remains the primary persistence path if storage is unavailable.
  }
}

function clearDraftBackup(key: string | null) {
  if (!key) return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Nothing else is required: the server copy is already authoritative.
  }
}

function mergeDraftAnswers(server: StudentAnswers, local: StudentAnswers): StudentAnswers {
  const merged = { ...server };
  for (const [questionId, localEntry] of Object.entries(local)) {
    const serverEntry = server[questionId] ?? {};
    const mergedEntry = {
      ...serverEntry,
      ...localEntry,
      images: serverEntry.images ?? localEntry.images,
    };
    if (serverEntry.ocr) mergedEntry.ocr = serverEntry.ocr;
    else delete mergedEntry.ocr;
    merged[questionId] = mergedEntry;
  }
  return merged;
}

function canonicalAnswers(answers: StudentAnswers): string {
  return JSON.stringify(
    Object.fromEntries(
      Object.keys(answers).sort().map((questionId) => [questionId, {
        text: answers[questionId]?.text ?? '',
        images: answers[questionId]?.images ?? [],
        ocr: answers[questionId]?.ocr ? {
          sourceId: answers[questionId]?.ocr?.sourceId,
          revision: answers[questionId]?.ocr?.revision,
          text: answers[questionId]?.ocr?.text,
        } : null,
      }])
    )
  );
}

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
  const [activeQuestionId, setActiveQuestionId] = useState<number | null>(null);
  const [draftSaveState, setDraftSaveState] = useState<DraftSaveState>('idle');
  const [ocrBusy, setOcrBusy] = useState(false);
  const dirty = useRef(false);
  const answersRef = useRef<StudentAnswers>({});
  const revisionRef = useRef(0);
  const saveAbortRef = useRef<AbortController | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const finalizingRef = useRef(false);
  const submittedRef = useRef(false);
  const previousAnswersRef = useRef<StudentAnswers>({});
  const draftBackupKey = useMemo(() => {
    const studentId = getStoredUser()?.id;
    return studentId
      ? `ai_amooz_exercise_draft_${studentId}_${sessionId}_${exerciseId}`
      : null;
  }, [sessionId, exerciseId]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    getStudentExercise(sessionId, exerciseId)
      .then((d) => {
        const serverAnswers = d.myAnswers ?? {};
        const backup = d.submissionStatus == null || d.submissionStatus === 'draft'
          ? readDraftBackup(draftBackupKey)
          : null;
        if (d.submissionStatus != null && d.submissionStatus !== 'draft') {
          clearDraftBackup(draftBackupKey);
        }
        const restoredAnswers = backup ? mergeDraftAnswers(serverAnswers, backup) : serverAnswers;
        previousAnswersRef.current = serverAnswers;
        setDetail(d);
        setAnswers(restoredAnswers);
        answersRef.current = restoredAnswers;
        dirty.current = backup != null;
        setDraftSaveState(backup ? 'pending' : 'idle');
        setActiveQuestionId(d.questions[0]?.id ?? null);
      })
      .catch((err) => toast.error(err instanceof Error ? err.message : 'خطا در بارگذاری تمرین'))
      .finally(() => setLoading(false));
  }, [sessionId, exerciseId, draftBackupKey]);

  const replaceSource = useCallback((source: AnswerOcrSource) => {
    setDetail((current) => current ? {
      ...current,
      answerSources: [
        ...(current.answerSources ?? []).filter((item) => item.id !== source.id),
        source,
      ],
    } : current);
  }, []);

  const refreshExercise = useCallback(async () => {
    const next = await getStudentExercise(sessionId, exerciseId);
    setDetail(next);
    // Draft answers are server-owned for image/OCR metadata. Preserve current
    // typed text while refreshing those fields from the authoritative copy.
    const merged = mergeDraftAnswers(next.myAnswers ?? {}, answersRef.current);
    for (const [qid, serverEntry] of Object.entries(next.myAnswers ?? {})) {
      merged[qid] = { ...merged[qid], images: serverEntry.images, ocr: serverEntry.ocr };
    }
    answersRef.current = merged;
    setAnswers(merged);
  }, [sessionId, exerciseId]);

  useEffect(() => {
    const active = detail?.answerSources?.some((source) => (
      source.status === 'queued'
      || source.status === 'reading'
      || source.status === 'segmenting'
      || source.status === 'matching'
    ));
    if (!active) return;
    const timer = window.setInterval(() => void refreshExercise(), 2000);
    return () => window.clearInterval(timer);
  }, [detail?.answerSources, refreshExercise]);

  const alreadySubmitted =
    detail?.submissionStatus != null && detail.submissionStatus !== 'draft';
  const unchangedResubmission = Boolean(
    detail?.attemptCount
    && canonicalAnswers(answers) === canonicalAnswers(previousAnswersRef.current)
  );

  useEffect(() => {
    submittedRef.current = alreadySubmitted;
  }, [alreadySubmitted]);

  const persistDraft = useCallback(
    async (next: StudentAnswers, revision: number, keepalive = false) => {
      if (submittedRef.current || finalizingRef.current || !dirty.current) return;

      saveAbortRef.current?.abort();
      const controller = new AbortController();
      saveAbortRef.current = controller;
      if (mountedRef.current && revision === revisionRef.current) setDraftSaveState('saving');

      try {
        await saveExerciseDraft(sessionId, exerciseId, next, {
          keepalive,
          signal: controller.signal,
        });
        if (revision !== revisionRef.current || finalizingRef.current) return;
        dirty.current = false;
        clearDraftBackup(draftBackupKey);
        if (mountedRef.current) setDraftSaveState('saved');
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        if (revision !== revisionRef.current || finalizingRef.current) return;
        writeDraftBackup(draftBackupKey, next);
        if (mountedRef.current) setDraftSaveState('error');
      } finally {
        if (saveAbortRef.current === controller) saveAbortRef.current = null;
      }
    },
    [sessionId, exerciseId, draftBackupKey]
  );

  useEffect(() => {
    if (!dirty.current || alreadySubmitted) return;
    if (saveTimerRef.current != null) window.clearTimeout(saveTimerRef.current);
    const revision = revisionRef.current;
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      void persistDraft(answers, revision);
    }, 1200);
    return () => {
      if (saveTimerRef.current != null) window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    };
  }, [answers, persistDraft]);

  const flushDraft = useCallback((keepalive = false) => {
    if (saveTimerRef.current != null) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    if (!dirty.current || submittedRef.current || finalizingRef.current) return;
    void persistDraft(answersRef.current, revisionRef.current, keepalive);
  }, [persistDraft]);

  useEffect(() => {
    const handlePageHide = () => flushDraft(true);
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') flushDraft(true);
    };
    window.addEventListener('pagehide', handlePageHide);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.removeEventListener('pagehide', handlePageHide);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      flushDraft(true);
    };
  }, [flushDraft]);

  const setText = (qid: number, text: string) => {
    const next = {
      ...answersRef.current,
      [qid]: { ...answersRef.current[String(qid)], text },
    };
    revisionRef.current += 1;
    dirty.current = true;
    answersRef.current = next;
    writeDraftBackup(draftBackupKey, next);
    setDraftSaveState('pending');
    setAnswers(next);
  };

  const addImage = async (qid: number, file: File) => {
    try {
      const { path, source } = await uploadAnswerImage(sessionId, exerciseId, qid, file);
      const entry = answersRef.current[String(qid)] ?? {};
      const next = {
        ...answersRef.current,
        [qid]: { ...entry, images: Array.from(new Set([...(entry.images ?? []), path])) },
      };
      answersRef.current = next;
      setAnswers(next);
      if (source) replaceSource(source);
      if (dirty.current) writeDraftBackup(draftBackupKey, next);
      toast.success('تصویر پاسخ بارگذاری شد.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'بارگذاری تصویر ناموفق بود.');
    }
  };

  const uploadWholeAnswer = async (files: File[]) => {
    setOcrBusy(true);
    try {
      const source = await uploadExerciseAnswerSource(sessionId, exerciseId, files);
      replaceSource(source);
      toast.success('پاسخ‌نامه بارگذاری شد و خواندن آن در پس‌زمینه آغاز شد.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'بارگذاری پاسخ‌نامه ناموفق بود.');
    } finally {
      setOcrBusy(false);
    }
  };

  const applyWholeAnswer = async (source: AnswerOcrSource, reviewed: AnswerOcrCandidate[]) => {
    setOcrBusy(true);
    try {
      const updated = await updateExerciseAnswerSource(
        sessionId, exerciseId, source.revision, reviewed,
      );
      const applied = await applyExerciseAnswerSource(
        sessionId, exerciseId, updated.revision,
      );
      replaceSource(applied);
      await refreshExercise();
      toast.success('پاسخ‌های بازبینی‌شده اعمال شدند.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'اعمال پاسخ‌ها ناموفق بود.');
    } finally {
      setOcrBusy(false);
    }
  };

  const saveQuestionOcr = async (source: AnswerOcrSource, text: string) => {
    if (!source.questionId) return;
    setOcrBusy(true);
    try {
      const updated = await updateQuestionAnswerSource(
        sessionId,
        exerciseId,
        source.questionId,
        source.revision,
        text,
      );
      replaceSource(updated);
      await refreshExercise();
      toast.success('اصلاح خوانش ذخیره شد.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ذخیره اصلاح ناموفق بود.');
    } finally {
      setOcrBusy(false);
    }
  };

  const deleteAnswerAsset = async (assetId: number) => {
    setOcrBusy(true);
    try {
      await deleteExerciseAnswerAsset(sessionId, exerciseId, assetId);
      await refreshExercise();
      toast.success('فایل از پاسخ جاری کنار گذاشته شد.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'حذف فایل ناموفق بود.');
    } finally {
      setOcrBusy(false);
    }
  };

  const doSubmit = async () => {
    finalizingRef.current = true;
    if (saveTimerRef.current != null) window.clearTimeout(saveTimerRef.current);
    saveAbortRef.current?.abort();
    setSubmitting(true);
    try {
      const wholeSource = detail?.answerSources?.find((source) => source.scope === 'exercise');
      await submitExercise(
        sessionId,
        exerciseId,
        answersRef.current,
        Boolean(wholeSource && !wholeSource.appliedAt && wholeSource.status !== 'superseded'),
      );
      submittedRef.current = true;
      dirty.current = false;
      clearDraftBackup(draftBackupKey);
      toast.success('پاسخ شما ارسال شد. نتیجه پس از نمره‌دهی نمایش داده می‌شود.');
      router.push(`/exercises/${exerciseId}/result?session=${sessionId}`);
    } catch (err) {
      finalizingRef.current = false;
      dirty.current = true;
      writeDraftBackup(draftBackupKey, answersRef.current);
      setDraftSaveState('error');
      toast.error(err instanceof Error ? err.message : 'ارسال ناموفق بود.');
    } finally {
      setSubmitting(false);
    }
  };

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

  const deadlineMs = detail.deadline ? Date.parse(detail.deadline) : null;
  const deadlinePassed = deadlineMs != null && deadlineMs < Date.now();
  const deadlineSoon =
    deadlineMs != null && !deadlinePassed && deadlineMs - Date.now() < 24 * 3600 * 1000;
  const wholeAnswerSource = detail.answerSources?.find((source) => source.scope === 'exercise');
  const questionSources = new Map(
    (detail.answerSources ?? [])
      .filter((source) => source.scope === 'question' && source.questionId != null)
      .map((source) => [source.questionId as number, source]),
  );
  const pendingOcr = (detail.answerSources ?? []).some((source) => (
    source.status === 'queued'
    || source.status === 'reading'
    || source.status === 'segmenting'
    || source.status === 'matching'
  ));
  const failedOcr = (detail.answerSources ?? []).some((source) => source.status === 'failed');
  const unappliedWholeOcr = Boolean(
    wholeAnswerSource
    && !wholeAnswerSource.appliedAt
    && wholeAnswerSource.status !== 'superseded',
  );

  return (
    <div dir="rtl" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">
          <MathText text={detail.title} />
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          {!alreadySubmitted && draftSaveState === 'pending' && (
            <span className="text-xs text-muted-foreground">در انتظار ذخیره…</span>
          )}
          {!alreadySubmitted && draftSaveState === 'saving' && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> در حال ذخیره…
            </span>
          )}
          {!alreadySubmitted && draftSaveState === 'saved' && (
            <span className="text-xs text-muted-foreground">پیش‌نویس ذخیره شد ✓</span>
          )}
          {!alreadySubmitted && draftSaveState === 'error' && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 text-destructive"
              onClick={() => flushDraft()}
            >
              ذخیره نشد؛ تلاش دوباره
            </Button>
          )}
          {detail.deadline && !deadlinePassed && (
            <Badge variant={deadlineSoon ? 'destructive' : 'outline'}>
              {deadlineSoon ? 'کمتر از ۲۴ ساعت تا پایان مهلت' : `مهلت: ${formatPersianDateTime(detail.deadline)}`}
            </Badge>
          )}
          {deadlinePassed && <Badge variant="destructive">مهلت به پایان رسیده</Badge>}
          {alreadySubmitted && <Badge variant="secondary">ارسال‌شده</Badge>}
        </div>
      </div>

      {deadlinePassed && !alreadySubmitted && (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          مهلت ارسال این تمرین به پایان رسیده است. اگر مدرس ارسال با تأخیر را مجاز کرده باشد،
          پاسخ شما با برچسب «با تأخیر» ثبت می‌شود؛ در غیر این صورت ارسال پذیرفته نخواهد شد.
        </p>
      )}

      {detail.answerOcrEnabled && (
        <WholeAnswerOcrPanel
          source={wholeAnswerSource}
          questions={detail.questions}
          disabled={alreadySubmitted}
          busy={ocrBusy}
          onUpload={uploadWholeAnswer}
          onApply={applyWholeAnswer}
          onDeleteAsset={deleteAnswerAsset}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          {detail.questions.map((q, index) => (
            <Card key={q.id}>
              <CardHeader>
                <CardTitle className="space-y-3 text-base font-normal">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-muted-foreground">سوال {index + 1}</span>
                    {detail.assistantEnabled && (
                      <Button
                        type="button"
                        size="sm"
                        variant={activeQuestionId === q.id ? 'secondary' : 'outline'}
                        onClick={() => setActiveQuestionId(q.id)}
                      >
                        <MessageCircle className="ms-2 h-4 w-4" />
                        دستیار این سوال
                      </Button>
                    )}
                  </div>
                  <MarkdownWithMath markdown={q.questionMarkdown} />
                  <span className="block text-xs text-muted-foreground">{q.maxPoints} نمره</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Textarea
                  placeholder="پاسخ خود را بنویسید…"
                  value={answers[String(q.id)]?.text ?? ''}
                  onChange={(e) => setText(q.id, e.target.value)}
                  onBlur={() => flushDraft()}
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
                {detail.answerOcrEnabled && (
                  <QuestionAnswerOcrPreview
                    source={questionSources.get(q.id)}
                    disabled={alreadySubmitted}
                    busy={ocrBusy}
                    onSave={saveQuestionOcr}
                  />
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Assistant */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          {detail.assistantEnabled && activeQuestionId ? (
            <ExerciseAssistant
              key={activeQuestionId}
              sessionId={sessionId}
              exerciseId={exerciseId}
              questionId={activeQuestionId}
            />
          ) : (
            <Card>
              <CardContent className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Lock className="h-4 w-4" />
                دستیار این تمرین غیرفعال است
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
                  {pendingOcr
                    ? 'خواندن یکی از فایل‌ها هنوز کامل نشده است. ارسال شما ثبت می‌شود و نمره‌دهی پس از پایان خوانش ادامه پیدا می‌کند.'
                    : failedOcr
                      ? 'خواندن یکی از فایل‌ها کامل نشد. تصویر اصلی برای مدرس محفوظ می‌ماند و پاسخ برای بررسی دستی ارسال می‌شود.'
                      : unappliedWholeOcr
                        ? 'پاسخ‌نامه آماده است اما هنوز اعمال نشده. با ارسال نهایی، همین تطبیق فعلی فریز و برای نمره‌دهی استفاده می‌شود.'
                        : unchangedResubmission
                          ? 'پاسخ‌های شما نسبت به ارسال قبلی تغییری نکرده‌اند. در صورت ارسال، همان نتیجه قبلی مبنای نمره‌دهی خواهد بود.'
                          : 'پس از ارسال، امکان ویرایش پاسخ‌ها را نخواهید داشت. مطمئن هستید؟'}
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
