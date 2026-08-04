'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Loader2,
  RefreshCcw,
  RotateCcw,
  Square,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { normalizeApiError } from '@/services/auth-service';
import {
  cancelExamPrepV4Extraction,
  getExamPrepV4ExtractionStatus,
  getExamPrepV4Project,
  retryExamPrepV4Extraction,
  type ExamPrepV4ExtractionStatus,
} from '@/services/exam-prep-v4-service';

const statusLabels: Record<string, string> = {
  segmenting: 'در حال تشخیص بخش‌ها',
  extracting_questions: 'در حال استخراج سؤال‌ها',
  extracting_answers: 'در حال استخراج پاسخ و راه‌حل',
  matching: 'در حال اتصال پاسخ‌ها',
  awaiting_review: 'آمادهٔ بازبینی',
  ready_to_publish: 'آمادهٔ انتشار',
  published: 'منتشر شده',
  failed: 'ناموفق',
  cancelled: 'لغو شده',
};

const stageLabels: Record<string, string> = {
  source_map_confirmed: 'صفحات تأیید شدند',
  extraction_queued: 'در صف پردازش',
  extraction_started: 'پردازش آغاز شد',
  block_detection: 'تشخیص بخش‌های صفحه',
  question_extraction: 'استخراج سؤال‌ها',
  questions_ready: 'سؤال‌ها آماده شدند',
  answer_solution_extraction: 'استخراج پاسخ و راه‌حل',
  answers_ready: 'پاسخ‌ها آماده شدند',
  matching_complete: 'اتصال پاسخ‌ها کامل شد',
  awaiting_review: 'آمادهٔ بازبینی',
  extraction_retrying: 'در انتظار تلاش مجدد',
  extraction_failed: 'پردازش ناموفق',
  extraction_dispatch_failed: 'شروع پردازش ناموفق',
  cancellation_requested: 'درخواست توقف ثبت شد',
  cancelled: 'پردازش لغو شد',
};

const counterLabels: Record<string, string> = {
  pageCount: 'صفحه',
  questionCount: 'سؤال',
  answerSolutionCount: 'پاسخ و راه‌حل',
  matchedCount: 'اتصال موفق',
  outOfScopeCount: 'خارج از محدوده',
  unresolvedCount: 'نیازمند بررسی',
  ambiguousCount: 'مبهم',
  conflictCount: 'تعارض',
  issueCount: 'هشدار',
};

export function ExamPrepV4ExtractionRuntimePanel({ projectId }: { projectId: number }) {
  const [documentId, setDocumentId] = useState<number | null>(null);
  const [runtime, setRuntime] = useState<ExamPrepV4ExtractionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuntime = useCallback(async (signal?: AbortSignal) => {
    if (!Number.isInteger(projectId) || projectId < 1) return;
    try {
      let selectedDocumentId = documentId;
      if (!selectedDocumentId) {
        const project = await getExamPrepV4Project(projectId, signal);
        selectedDocumentId = project.documents[0]?.id ?? null;
        if (!selectedDocumentId) {
          setRuntime(null);
          return;
        }
        setDocumentId(selectedDocumentId);
      }
      const result = await getExamPrepV4ExtractionStatus(
        projectId,
        selectedDocumentId,
        signal,
      );
      setRuntime(result);
      setError(null);
    } catch (requestError) {
      if (signal?.aborted) return;
      setError(normalizeApiError(requestError).message);
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, [documentId, projectId]);

  useEffect(() => {
    const controller = new AbortController();
    void loadRuntime(controller.signal);
    return () => controller.abort();
  }, [loadRuntime]);

  useEffect(() => {
    if (!runtime?.active || !documentId) return;
    const timer = window.setInterval(() => {
      void loadRuntime();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [documentId, loadRuntime, runtime?.active]);

  const counters = useMemo(
    () => Object.entries(runtime?.counters ?? {}).filter(
      ([key, value]) => counterLabels[key] && typeof value === 'number',
    ),
    [runtime?.counters],
  );

  const retry = useCallback(async () => {
    if (!documentId || isRetrying) return;
    setIsRetrying(true);
    setError(null);
    try {
      setRuntime(await retryExamPrepV4Extraction(projectId, documentId));
    } catch (requestError) {
      setError(normalizeApiError(requestError).message);
    } finally {
      setIsRetrying(false);
    }
  }, [documentId, isRetrying, projectId]);

  const cancel = useCallback(async () => {
    if (!documentId || isCancelling) return;
    setIsCancelling(true);
    setError(null);
    try {
      setRuntime(await cancelExamPrepV4Extraction(projectId, documentId));
    } catch (requestError) {
      setError(normalizeApiError(requestError).message);
    } finally {
      setIsCancelling(false);
    }
  }, [documentId, isCancelling, projectId]);

  if (isLoading && !runtime) {
    return (
      <Card className="rounded-2xl border-border/60" dir="rtl">
        <CardContent className="flex items-center gap-3 p-5 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          در حال دریافت وضعیت آماده‌سازی
        </CardContent>
      </Card>
    );
  }

  const controlsBusy = isRetrying || isCancelling;

  return (
    <Card className="rounded-2xl border-border/60" dir="rtl">
      <CardHeader className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Activity className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <CardTitle className="text-lg font-black">وضعیت آماده‌سازی سؤال‌ها</CardTitle>
              <p className="mt-1 text-xs text-muted-foreground">
                استخراج سؤال‌ها، پاسخ‌ها و راه‌حل‌ها به‌صورت خودکار انجام می‌شود.
              </p>
            </div>
          </div>
          {runtime ? (
            <Badge variant="outline">
              {statusLabels[runtime.projectStatus] ?? runtime.projectStatus}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>عملیات انجام نشد</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {runtime ? (
          <>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold">
                  {stageLabels[runtime.stage] ?? (runtime.stage || 'در انتظار تأیید صفحات')}
                </span>
                <span className="text-muted-foreground">{runtime.progressPercent}٪</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-[width] motion-reduce:transition-none"
                  style={{ width: `${Math.min(100, Math.max(0, runtime.progressPercent))}%` }}
                />
              </div>
            </div>

            {runtime.cancellationRequested && runtime.active ? (
              <Alert className="border-amber-500/30 bg-amber-500/10">
                <Square className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>درخواست توقف ثبت شد</AlertTitle>
                <AlertDescription>
                  پردازش در اولین نقطهٔ امن متوقف می‌شود.
                </AlertDescription>
              </Alert>
            ) : null}

            {counters.length > 0 ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                {counters.map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-border/60 p-3">
                    <p className="text-xs text-muted-foreground">{counterLabels[key]}</p>
                    <p className="mt-1 text-lg font-black">{value}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {runtime.projectStatus === 'awaiting_review' ? (
              <Alert className="border-emerald-500/30 bg-emerald-500/10">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>استخراج کامل شد</AlertTitle>
                <AlertDescription>
                  سؤال‌ها و پاسخ‌ها آماده‌اند؛ موارد نامطمئن را در بخش بعدی بررسی کنید.
                </AlertDescription>
              </Alert>
            ) : null}

            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              <Button
                type="button"
                variant="outline"
                className="h-11 rounded-xl"
                onClick={() => void loadRuntime()}
                disabled={controlsBusy}
              >
                <RefreshCcw className="ms-2 h-4 w-4" aria-hidden="true" />
                بروزرسانی وضعیت
              </Button>
              {runtime.active ? (
                <Button
                  type="button"
                  variant="destructive"
                  className="h-11 rounded-xl"
                  onClick={() => void cancel()}
                  disabled={controlsBusy || runtime.cancellationRequested}
                >
                  {isCancelling ? (
                    <Loader2 className="ms-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Square className="ms-2 h-4 w-4" aria-hidden="true" />
                  )}
                  توقف پردازش
                </Button>
              ) : null}
              {runtime.retryable && !runtime.active ? (
                <Button
                  type="button"
                  className="h-11 rounded-xl"
                  onClick={() => void retry()}
                  disabled={controlsBusy}
                >
                  {isRetrying ? (
                    <Loader2 className="ms-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <RotateCcw className="ms-2 h-4 w-4" aria-hidden="true" />
                  )}
                  تلاش مجدد
                </Button>
              ) : null}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            پس از تأیید نقش و ترتیب صفحات، وضعیت آماده‌سازی در این بخش نمایش داده می‌شود.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
