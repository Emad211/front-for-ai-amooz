'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ClipboardCheck,
  Loader2,
  RefreshCcw,
  Save,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { normalizeApiError } from '@/services/auth-service';
import {
  finalizeExamPrepV4Review,
  getExamPrepV4ReviewQueue,
  saveExamPrepV4ReviewDecision,
  type ExamPrepV4ReviewItem,
  type ExamPrepV4ReviewQueue,
} from '@/services/exam-prep-v4-review-service';


type DraftDecision = {
  action: 'match' | 'out_of_scope' | 'ignore';
  questionRecordId: number | null;
  note: string;
};

const decisionLabels: Record<string, string> = {
  unresolved: 'بدون مقصد قطعی',
  ambiguous: 'چند سؤال هم‌نام',
  conflict: 'تعارض اطلاعات',
  out_of_scope: 'خارج از محدودهٔ خودکار',
};

function initialDraft(item: ExamPrepV4ReviewItem): DraftDecision {
  return {
    action: item.review?.action ?? 'out_of_scope',
    questionRecordId: item.review?.questionRecordId ?? null,
    note: item.review?.note ?? '',
  };
}

export function ExamPrepV4ReviewPanel({ projectId }: { projectId: number }) {
  const [queue, setQueue] = useState<ExamPrepV4ReviewQueue | null>(null);
  const [drafts, setDrafts] = useState<Record<number, DraftDecision>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    try {
      const result = await getExamPrepV4ReviewQueue(projectId, signal);
      setQueue(result);
      setDrafts(
        Object.fromEntries(
          result.items.map((item) => [item.matchDecisionId, initialDraft(item)]),
        ),
      );
      setError(null);
      setCompleted(result.projectStatus === 'ready_to_publish');
    } catch (requestError) {
      if (signal?.aborted) return;
      const normalized = normalizeApiError(requestError);
      setError(normalized.message);
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const questionById = useMemo(
    () => new Map(queue?.questions.map((question) => [question.id, question]) ?? []),
    [queue?.questions],
  );

  const updateDraft = useCallback((
    matchDecisionId: number,
    patch: Partial<DraftDecision>,
  ) => {
    setDrafts((current) => ({
      ...current,
      [matchDecisionId]: {
        ...(current[matchDecisionId] ?? {
          action: 'out_of_scope',
          questionRecordId: null,
          note: '',
        }),
        ...patch,
      },
    }));
  }, []);

  const save = useCallback(async (item: ExamPrepV4ReviewItem) => {
    const draft = drafts[item.matchDecisionId] ?? initialDraft(item);
    if (draft.action === 'match' && !draft.questionRecordId) {
      setError('برای اتصال دستی، سؤال مقصد را انتخاب کنید.');
      return;
    }
    setSavingId(item.matchDecisionId);
    setError(null);
    try {
      await saveExamPrepV4ReviewDecision(projectId, {
        matchDecisionId: item.matchDecisionId,
        action: draft.action,
        questionRecordId: draft.action === 'match' ? draft.questionRecordId : null,
        note: draft.note,
      });
      await load();
    } catch (requestError) {
      setError(normalizeApiError(requestError).message);
    } finally {
      setSavingId(null);
    }
  }, [drafts, load, projectId]);

  const finalize = useCallback(async () => {
    if (!queue?.canFinalize) return;
    setIsFinalizing(true);
    setError(null);
    try {
      await finalizeExamPrepV4Review(projectId, {
        questionSetFingerprint: queue.questionSetFingerprint,
        answerSetFingerprint: queue.answerSetFingerprint,
      });
      setCompleted(true);
      await load();
    } catch (requestError) {
      setError(normalizeApiError(requestError).message);
    } finally {
      setIsFinalizing(false);
    }
  }, [load, projectId, queue]);

  if (isLoading && !queue) {
    return (
      <Card className="rounded-2xl border-border/60" dir="rtl">
        <CardContent className="flex items-center gap-3 p-5 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          در حال آماده‌سازی صف بازبینی
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="rounded-2xl border-border/60" dir="rtl">
      <CardHeader className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <ClipboardCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <CardTitle className="text-lg font-black">بازبینی موارد استثنا</CardTitle>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                فقط پاسخ‌هایی نمایش داده می‌شوند که اتصال خودکار قطعی نداشته‌اند.
              </p>
            </div>
          </div>
          {queue ? (
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">کل {queue.totalCount}</Badge>
              <Badge variant="secondary">باقی‌مانده {queue.remainingCount}</Badge>
            </div>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>بازبینی آماده نیست یا عملیات انجام نشد</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>{error}</p>
              <Button
                type="button"
                variant="outline"
                className="h-10 rounded-xl"
                onClick={() => void load()}
              >
                <RefreshCcw className="ms-2 h-4 w-4" aria-hidden="true" />
                بروزرسانی
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}

        {completed ? (
          <Alert className="border-emerald-500/30 bg-emerald-500/10">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>بازبینی استثناها کامل شد</AlertTitle>
            <AlertDescription>
              پروژه برای ساخت projection و انتشار آماده است.
            </AlertDescription>
          </Alert>
        ) : null}

        {queue && queue.items.length === 0 ? (
          <Alert className="border-emerald-500/30 bg-emerald-500/10">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>مورد استثنایی وجود ندارد</AlertTitle>
            <AlertDescription>
              همهٔ پاسخ‌ها به‌صورت قطعی تعیین تکلیف شده‌اند؛ بازبینی را نهایی کنید.
            </AlertDescription>
          </Alert>
        ) : null}

        {queue?.items.map((item) => {
          const draft = drafts[item.matchDecisionId] ?? initialDraft(item);
          const selectedQuestion = draft.questionRecordId
            ? questionById.get(draft.questionRecordId)
            : null;
          return (
            <article
              key={item.matchDecisionId}
              className="space-y-4 rounded-2xl border border-border/60 p-4"
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="font-black">
                    پاسخ سؤال {item.printedNumber ?? item.answer.printedNumber ?? 'بدون شماره'}
                  </h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {decisionLabels[item.automaticDecision] ?? item.automaticDecision}
                    {' · '}
                    {item.reasonCode}
                  </p>
                </div>
                <Badge variant={item.review ? 'secondary' : 'outline'}>
                  {item.review ? 'تعیین تکلیف شده' : 'نیازمند تصمیم'}
                </Badge>
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <div className="rounded-xl bg-muted/30 p-3 text-sm leading-7">
                  <p className="text-xs font-bold text-muted-foreground">پاسخ استخراج‌شده</p>
                  <p><strong>گزینه:</strong> {item.answer.correctOption ?? '—'}</p>
                  <div>
                    <strong>پاسخ نهایی:</strong>
                    <MarkdownWithMath
                      markdown={item.answer.finalAnswer ?? '—'}
                      renderKey={`review-final-${item.matchDecisionId}`}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <strong>راه‌حل:</strong>
                    <MarkdownWithMath
                      markdown={item.answer.solutionText ?? '—'}
                      renderKey={`review-solution-${item.matchDecisionId}`}
                      className="mt-1"
                    />
                  </div>
                </div>
                <div className="rounded-xl border border-border/60 p-3 text-sm leading-7">
                  <p className="text-xs font-bold text-muted-foreground">سؤال مقصد انتخاب‌شده</p>
                  {selectedQuestion ? (
                    <>
                      <p className="font-bold">
                        سؤال {selectedQuestion.printedNumber ?? 'بدون شماره'}
                      </p>
                      <MarkdownWithMath
                        markdown={selectedQuestion.questionText || '—'}
                        renderKey={`review-question-${item.matchDecisionId}-${selectedQuestion.id}`}
                        className="line-clamp-6"
                      />
                    </>
                  ) : (
                    <p className="text-muted-foreground">سؤالی انتخاب نشده است.</p>
                  )}
                </div>
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <label className="space-y-1.5 text-sm font-bold">
                  تصمیم معلم
                  <select
                    className="h-11 w-full rounded-xl border border-input bg-background px-3 text-sm"
                    value={draft.action}
                    onChange={(event) => {
                      const action = event.target.value as DraftDecision['action'];
                      updateDraft(item.matchDecisionId, {
                        action,
                        questionRecordId: action === 'match' ? draft.questionRecordId : null,
                      });
                    }}
                  >
                    <option value="match">اتصال دستی به سؤال</option>
                    <option value="out_of_scope">تأیید خارج از محدوده</option>
                    <option value="ignore">نادیده‌گرفتن این پاسخ</option>
                  </select>
                </label>

                <label className="space-y-1.5 text-sm font-bold">
                  سؤال مقصد
                  <select
                    className="h-11 w-full rounded-xl border border-input bg-background px-3 text-sm disabled:opacity-50"
                    value={draft.questionRecordId ?? ''}
                    disabled={draft.action !== 'match'}
                    onChange={(event) => updateDraft(item.matchDecisionId, {
                      questionRecordId: event.target.value ? Number(event.target.value) : null,
                    })}
                  >
                    <option value="">انتخاب سؤال</option>
                    {queue.questions.map((question) => (
                      <option key={question.id} value={question.id}>
                        {question.printedNumber ?? 'بدون شماره'} — {question.questionText.slice(0, 100)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="space-y-1.5 text-sm font-bold">
                یادداشت اختیاری
                <Textarea
                  value={draft.note}
                  maxLength={500}
                  className="min-h-20 rounded-xl"
                  onChange={(event) => updateDraft(item.matchDecisionId, {
                    note: event.target.value,
                  })}
                />
              </label>

              <Button
                type="button"
                className="h-11 rounded-xl"
                onClick={() => void save(item)}
                disabled={savingId !== null}
              >
                {savingId === item.matchDecisionId ? (
                  <Loader2 className="ms-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Save className="ms-2 h-4 w-4" aria-hidden="true" />
                )}
                ثبت تصمیم
              </Button>
            </article>
          );
        })}

        {queue ? (
          <div className="flex flex-col gap-2 border-t border-border/60 pt-4 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              className="h-11 rounded-xl"
              onClick={() => void load()}
              disabled={isFinalizing || savingId !== null}
            >
              <RefreshCcw className="ms-2 h-4 w-4" aria-hidden="true" />
              بروزرسانی صف
            </Button>
            <Button
              type="button"
              className="h-11 rounded-xl"
              onClick={() => void finalize()}
              disabled={!queue.canFinalize || isFinalizing || completed}
            >
              {isFinalizing ? (
                <Loader2 className="ms-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <CheckCircle2 className="ms-2 h-4 w-4" aria-hidden="true" />
              )}
              نهایی‌کردن بازبینی
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
