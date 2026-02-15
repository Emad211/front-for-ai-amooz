'use client';

import { useEffect, useRef, useState } from 'react';
import { Progress } from '@/components/ui/progress';
import type { UploadProgress } from '@/services/classes-service';

/* ------------------------------------------------------------------ */
/* Step definitions                                                    */
/* ------------------------------------------------------------------ */

type StepDef = {
  /** Backend processing statuses for this step */
  processingStatus: string;
  /** Backend done status for this step */
  doneStatus: string;
};

const CLASS_STEPS: StepDef[] = [
  { processingStatus: 'transcribing', doneStatus: 'transcribed' },
  { processingStatus: 'structuring', doneStatus: 'structured' },
  { processingStatus: 'prereq_extracting', doneStatus: 'prereq_extracted' },
  { processingStatus: 'prereq_teaching', doneStatus: 'prereq_taught' },
  { processingStatus: 'recapping', doneStatus: 'recapped' },
];

const EXAM_PREP_STEPS: StepDef[] = [
  { processingStatus: 'exam_transcribing', doneStatus: 'exam_transcribed' },
  { processingStatus: 'exam_structuring', doneStatus: 'exam_structured' },
];

/* ------------------------------------------------------------------ */
/* Elapsed timer hook                                                  */
/* ------------------------------------------------------------------ */

function useElapsed(isRunning: boolean): number {
  const startRef = useRef<number | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isRunning) {
      startRef.current = null;
      return;
    }

    if (!startRef.current) {
      startRef.current = Date.now();
    }

    const id = window.setInterval(() => {
      if (startRef.current) {
        setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
      }
    }, 1000);

    return () => window.clearInterval(id);
  }, [isRunning]);

  return elapsed;
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds} ثانیه`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')} دقیقه`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ------------------------------------------------------------------ */
/* Step state resolver                                                 */
/* ------------------------------------------------------------------ */

type StepState = 'idle' | 'active' | 'done' | 'failed';

function resolveStepStates(
  steps: StepDef[],
  currentStatus: string | null,
): StepState[] {
  if (!currentStatus) return steps.map(() => 'idle');
  if (currentStatus === 'failed') {
    // Find which step was active and mark it as failed
    const states: StepState[] = [];
    let foundActive = false;
    for (const step of steps) {
      if (step.processingStatus === currentStatus || (!foundActive && step.doneStatus !== currentStatus)) {
        // Everything before the current position is done
      }
      states.push('idle');
    }
    // Better approach: mark all up to the processing step as done, the processing one as failed
    let lastActive = -1;
    for (let i = 0; i < steps.length; i++) {
      if (steps[i].processingStatus === currentStatus) {
        lastActive = i;
      }
    }
    // If none matched (generic "failed"), find the last step in progress by checking done statuses
    return steps.map((_, i) => {
      if (i < lastActive) return 'done';
      if (i === lastActive) return 'failed';
      return 'idle';
    });
  }

  const result: StepState[] = [];
  let passedCurrent = false;

  for (const step of steps) {
    if (passedCurrent) {
      result.push('idle');
      continue;
    }
    if (step.processingStatus === currentStatus) {
      result.push('active');
      passedCurrent = true;
      continue;
    }
    if (step.doneStatus === currentStatus) {
      result.push('done');
      // Next step might be starting, let the rest be idle
      passedCurrent = true;
      continue;
    }
    // If we haven't passed current, this step is complete
    result.push('done');
  }

  return result;
}

/* ------------------------------------------------------------------ */
/* Component Props                                                     */
/* ------------------------------------------------------------------ */

export type PipelineTrackerProps = {
  pipelineType: 'class' | 'exam_prep';
  /** Current backend status string */
  status: string | null;
  /** Upload progress (only during upload phase) */
  uploadProgress: UploadProgress | null;
  /** Whether the Step-1 HTTP call is currently in-flight */
  isUploading: boolean;
  /** Error message if any */
  errorMessage: string | null;
  /** Session ID for display */
  sessionId: number | null;
};

/* ------------------------------------------------------------------ */
/* Main Component                                                      */
/* ------------------------------------------------------------------ */

export function PipelineTracker({
  pipelineType,
  status,
  uploadProgress,
  isUploading,
  errorMessage,
  sessionId,
}: PipelineTrackerProps) {
  const steps = pipelineType === 'class' ? CLASS_STEPS : EXAM_PREP_STEPS;
  const stepStates = resolveStepStates(steps, status);
  const isPipelineActive = isUploading || (status !== null && status !== 'failed' && !steps.some(s => s.doneStatus === status));
  const isPipelineDone = status !== null && steps.some(s => s.doneStatus === status) && steps[steps.length - 1].doneStatus === status;
  const elapsed = useElapsed(isPipelineActive);

  // Upload phase is before any status
  const isUploadPhase = isUploading && !status;

  return (
    <div className="mt-4 space-y-4">
      {/* ── Upload Progress ── */}
      {isUploadPhase && uploadProgress && (
        <div className="rounded-xl border bg-card p-4 space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between text-sm font-medium">
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-primary" />
              </span>
              <span>
                {uploadProgress.phase === 'uploading' ? 'در حال آپلود فایل…' : 'در حال پردازش سرور…'}
              </span>
            </div>
            {uploadProgress.phase === 'uploading' && uploadProgress.percent >= 0 && (
              <span className="text-xs tabular-nums text-muted-foreground">
                {uploadProgress.percent}%
                {uploadProgress.total > 0 && (
                  <> — {formatBytes(uploadProgress.loaded)} / {formatBytes(uploadProgress.total)}</>
                )}
              </span>
            )}
          </div>

          {uploadProgress.phase === 'uploading' && uploadProgress.percent >= 0 ? (
            <Progress value={uploadProgress.percent} className="h-2" />
          ) : (
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div className="h-full bg-primary/60 rounded-full animate-pulse w-full" />
            </div>
          )}
        </div>
      )}

      {/* ── Pipeline Steps ── */}
      {(status || isPipelineDone) && (
        <div className="rounded-xl border bg-card p-4 space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isPipelineActive && (
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-primary" />
                </span>
              )}
              <h4 className="text-sm font-semibold">
                {isPipelineDone ? 'پردازش کامل شد' : 'در حال پردازش…'}
              </h4>
            </div>
            {isPipelineActive && (
              <span className="text-xs tabular-nums text-muted-foreground">
                ⏱ {formatElapsed(elapsed)}
              </span>
            )}
          </div>

          {/* Overall progress bar */}
          <OverallProgress stepStates={stepStates} />
        </div>
      )}

      {/* ── Error display ── */}
      {errorMessage && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-start gap-2">
            <span className="text-destructive text-lg mt-0.5">⚠️</span>
            <div className="space-y-1">
              <p className="text-sm font-medium text-destructive">خطا در پردازش</p>
              <p className="text-xs text-destructive/80">{errorMessage}</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Done banner ── */}
      {isPipelineDone && !errorMessage && (
        <div className="rounded-xl border border-green-500/30 bg-green-500/5 p-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center gap-2">
            <span className="text-green-600 text-lg">✅</span>
            <p className="text-sm font-medium text-green-700 dark:text-green-400">
              پردازش با موفقیت کامل شد!
            </p>
          </div>
        </div>
      )}

      {/* ── Session ID ── */}
      {sessionId && (
        <p className="text-[11px] text-muted-foreground/60 tabular-nums">
          شناسه جلسه: {sessionId}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Overall progress bar                                                */
/* ------------------------------------------------------------------ */

function OverallProgress({ stepStates }: { stepStates: StepState[] }) {
  const total = stepStates.length;
  const doneCount = stepStates.filter((s) => s === 'done').length;
  const activeCount = stepStates.filter((s) => s === 'active').length;

  // Each done step = 1 full, active step = 0.5
  const progress = Math.round(((doneCount + activeCount * 0.5) / total) * 100);

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>پیشرفت کلی</span>
        <span className="tabular-nums">{progress}%</span>
      </div>
      <Progress value={progress} className="h-1.5" />
    </div>
  );
}
