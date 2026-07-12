'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { Progress } from '@/components/ui/progress';
import type { UploadProgress } from '@/services/classes-service';

type PipelineTrackerProps = {
  pipelineType: 'class' | 'exam_prep';
  status: string | null;
  workflowStage?: string | null;
  workflowMessage?: string | null;
  progressPercent?: number | null;
  workflowWarnings?: string[];
  readyForReview?: boolean;
  uploadProgress: UploadProgress | null;
  isUploading: boolean;
  errorMessage: string | null;
  sessionId: number | null;
  startedAt?: string | null;
};

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds} ثانیه`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')} دقیقه`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function useElapsedSince(startedAt: string | null | undefined, isRunning: boolean): number {
  const [elapsed, setElapsed] = useState(0);
  const startMs = useMemo(() => {
    if (!startedAt) return null;
    const parsed = new Date(startedAt).getTime();
    return Number.isFinite(parsed) ? parsed : null;
  }, [startedAt]);

  useEffect(() => {
    if (!isRunning || !startMs) {
      setElapsed(0);
      return;
    }

    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - startMs) / 1000)));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [isRunning, startMs]);

  return elapsed;
}

const CLASS_STAGE_LABELS: Record<string, string> = {
  queued: 'در صف',
  reading_source: 'دریافت منبع',
  transcribing: 'تبدیل به متن',
  structuring: 'ساختاردهی',
  extracting_prerequisites: 'استخراج پیش‌نیازها',
  teaching_prerequisites: 'آموزش پیش‌نیازها',
  building_recap: 'ساخت جمع‌بندی',
  ready_for_review: 'پایان پردازش',
  failed: 'خطا',
  cancelled: 'متوقف‌شده',
};

const EXAM_STAGE_LABELS: Record<string, string> = {
  queued: 'در صف',
  reading_source: 'دریافت منبع',
  transcribing: 'تبدیل به متن',
  extracting_questions: 'استخراج سوال‌ها',
  ready_for_review: 'پایان پردازش',
  failed: 'خطا',
  cancelled: 'متوقف‌شده',
};

const CLASS_FLOW = ['queued', 'reading_source', 'transcribing', 'structuring', 'extracting_prerequisites', 'teaching_prerequisites', 'building_recap', 'ready_for_review'];
const EXAM_FLOW = ['queued', 'reading_source', 'transcribing', 'extracting_questions', 'ready_for_review'];

export function PipelineTracker({
  pipelineType,
  status,
  workflowStage,
  workflowMessage,
  progressPercent,
  workflowWarnings = [],
  readyForReview = false,
  uploadProgress,
  isUploading,
  errorMessage,
  sessionId,
  startedAt,
}: PipelineTrackerProps) {
  const isCancelled = status === 'cancelled' || workflowStage === 'cancelled';
  const isFailed = status === 'failed' || workflowStage === 'failed' || Boolean(errorMessage);
  const stage = workflowStage ?? null;
  const effectiveProgress = Math.max(0, Math.min(100, Number(progressPercent ?? 0)));
  const stageLabels = pipelineType === 'class' ? CLASS_STAGE_LABELS : EXAM_STAGE_LABELS;
  const stageFlow = pipelineType === 'class' ? CLASS_FLOW : EXAM_FLOW;
  const isPipelineActive = Boolean(
    isUploading ||
      (stage && !readyForReview && stage !== 'failed' && stage !== 'cancelled')
  );
  const elapsed = useElapsedSince(startedAt, isPipelineActive);
  const currentStageIndex = stage ? stageFlow.indexOf(stage) : -1;
  const cleanedWarnings = workflowWarnings.filter(Boolean).slice(0, 3);
  const hasTracker = Boolean(stage || isUploading || errorMessage || readyForReview);
  const warningIdRef = useRef(`pipeline-warnings-${Math.random().toString(36).slice(2)}`);
  const reviewDestination = pipelineType === 'class' ? 'صفحه کلاس‌ها' : 'صفحه آمادگی آزمون‌ها';
  const readyMessage = `پردازش کامل شد. برای بررسی نهایی و انتشار، از ${reviewDestination} وارد پیش‌نویس شوید.`;

  return (
    <div className="mt-4 space-y-4">
      {isUploading && uploadProgress && (
        <div className="space-y-3 rounded-2xl border bg-card p-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between gap-3 text-sm font-medium">
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-primary" />
              </span>
              <span>{uploadProgress.phase === 'uploading' ? 'در حال بارگذاری فایل…' : 'در حال ثبت و آماده‌سازی…'}</span>
            </div>
            {uploadProgress.phase === 'uploading' && uploadProgress.percent >= 0 && (
              <span className="text-xs tabular-nums text-muted-foreground">
                {uploadProgress.percent}%{uploadProgress.total > 0 ? ` — ${formatBytes(uploadProgress.loaded)} / ${formatBytes(uploadProgress.total)}` : ''}
              </span>
            )}
          </div>
          {uploadProgress.phase === 'uploading' && uploadProgress.percent >= 0 ? (
            <Progress value={uploadProgress.percent} className="h-2" />
          ) : (
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full w-full animate-pulse rounded-full bg-primary/60" />
            </div>
          )}
        </div>
      )}

      {hasTracker && !isCancelled && (
        <div className="space-y-4 rounded-2xl border bg-card p-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                {isPipelineActive && (
                  <span className="relative flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-primary" />
                  </span>
                )}
                <h4 className="text-sm font-semibold text-foreground">
                  {readyForReview ? 'پردازش کامل شد' : 'در حال پردازش'}
                </h4>
              </div>
              <p className="text-xs leading-6 text-muted-foreground">
                {readyForReview ? readyMessage : (workflowMessage || 'وضعیت پردازش در حال به‌روزرسانی است.')}
              </p>
            </div>
            {isPipelineActive && startedAt ? (
              <span className="text-xs tabular-nums text-muted-foreground">⏱ {formatElapsed(elapsed)}</span>
            ) : null}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span>{stage ? stageLabels[stage] ?? 'در حال پردازش' : 'در حال پردازش'}</span>
              <span className="tabular-nums">{effectiveProgress}%</span>
            </div>
            <Progress value={effectiveProgress} className="h-2" />
          </div>

          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {stageFlow.map((flowStage, index) => {
              const state =
                flowStage === stage
                  ? readyForReview
                    ? 'done'
                    : 'active'
                  : currentStageIndex >= 0 && index < currentStageIndex
                    ? 'done'
                    : 'idle';
              return (
                <div
                  key={flowStage}
                  className={
                    state === 'done'
                      ? 'rounded-xl border border-primary/20 bg-primary/10 px-3 py-2 text-sm text-primary'
                      : state === 'active'
                        ? 'rounded-xl border border-primary/30 bg-primary/5 px-3 py-2 text-sm text-foreground'
                        : 'rounded-xl border border-border/70 bg-muted/20 px-3 py-2 text-sm text-muted-foreground'
                  }
                >
                  {stageLabels[flowStage] ?? flowStage}
                </div>
              );
            })}
          </div>

          {cleanedWarnings.length > 0 ? (
            <div className="space-y-2 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-3" aria-describedby={warningIdRef.current}>
              <p className="text-sm font-medium text-amber-700 dark:text-amber-300">نیازمند توجه شما</p>
              <ul id={warningIdRef.current} className="space-y-1 text-xs leading-6 text-amber-700/90 dark:text-amber-200/90">
                {cleanedWarnings.map((warning) => (
                  <li key={warning}>• {warning}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}

      {isFailed && errorMessage && (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 text-lg text-destructive">⚠️</span>
            <div className="space-y-1">
              <p className="text-sm font-medium text-destructive">خطا در پردازش</p>
              <p className="text-xs text-destructive/80">{errorMessage}</p>
            </div>
          </div>
        </div>
      )}

      {isCancelled && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center gap-2">
            <span className="text-lg text-amber-600">🚫</span>
            <p className="text-sm font-medium text-amber-700 dark:text-amber-400">پردازش توسط شما لغو شد.</p>
          </div>
        </div>
      )}

      {sessionId ? (
        <p className="text-[11px] tabular-nums text-muted-foreground/60">شناسه جلسه: {sessionId}</p>
      ) : null}
    </div>
  );
}
