'use client';

import { Progress } from '@/components/ui/progress';
import type { ExerciseStatus, ExerciseWorkflowStage } from '@/services/exercises-service';

const STAGE_LABELS: Record<ExerciseWorkflowStage, string> = {
  queued: 'در صف',
  reading_sources: 'دریافت منبع',
  ocr_and_transcription: 'خواندن/OCR',
  extracting_questions: 'استخراج سوال‌ها',
  matching_reference_answers: 'تطبیق پاسخ‌ها',
  building_review_draft: 'ساخت پیش‌نویس',
  ready_for_review: 'آماده بازبینی',
  cancelled: 'متوقف‌شده',
  failed: 'خطا',
};

const STAGE_FLOW: ExerciseWorkflowStage[] = [
  'queued',
  'reading_sources',
  'ocr_and_transcription',
  'extracting_questions',
  'matching_reference_answers',
  'building_review_draft',
  'ready_for_review',
];

export const ACTIVE_EXERCISE_WORKFLOW_STAGES = new Set<ExerciseWorkflowStage>([
  'queued',
  'reading_sources',
  'ocr_and_transcription',
  'extracting_questions',
  'matching_reference_answers',
  'building_review_draft',
]);

const RAW_WORKFLOW_WARNING_RE = /(answer for q|traceback|exception|runtimeerror|http\s*\d{3}|\\[a-z]+|\$[A-Za-z\\])/i;

export function sanitizeExerciseWorkflowWarnings(warnings: string[] = []): string[] {
  const out: string[] = [];
  let genericNeeded = false;

  for (const warning of warnings) {
    const text = warning.replace(/\s+/g, ' ').trim();
    if (!text) continue;

    const asciiLetters = [...text].filter((ch) => /[A-Za-z]/.test(ch)).length;
    if (text.length > 180 || asciiLetters >= 18 || RAW_WORKFLOW_WARNING_RE.test(text)) {
      genericNeeded = true;
      continue;
    }
    if (!out.includes(text)) {
      out.push(text);
    }
  }

  if (genericNeeded) {
    out.unshift('برخی موارد این پیش‌نویس برای بازبینی دستی علامت‌گذاری شده‌اند.');
  }

  return out.slice(0, 3);
}

type ExerciseWorkflowTrackerProps = {
  workflowStage?: ExerciseWorkflowStage | null;
  workflowMessage?: string | null;
  progressPercent?: number | null;
  workflowWarnings?: string[];
  readyForReview?: boolean;
  exerciseStatus?: ExerciseStatus | null;
  compact?: boolean;
};

export function ExerciseWorkflowTracker({
  workflowStage,
  workflowMessage,
  progressPercent,
  workflowWarnings = [],
  readyForReview = false,
  exerciseStatus,
  compact = false,
}: ExerciseWorkflowTrackerProps) {
  const stage = workflowStage ?? null;
  const effectiveProgress = Math.max(0, Math.min(100, Number(progressPercent ?? 0)));
  const currentStageIndex = stage ? STAGE_FLOW.indexOf(stage) : -1;
  const isFailed = stage === 'failed' || exerciseStatus === 'failed';
  const isCancelled = stage === 'cancelled' || exerciseStatus === 'cancelled';
  const isActive = Boolean(stage && ACTIVE_EXERCISE_WORKFLOW_STAGES.has(stage) && !isFailed && !isCancelled);
  const cleanedWarnings = sanitizeExerciseWorkflowWarnings(workflowWarnings);

  return (
    <div className={compact ? 'space-y-3' : 'space-y-4'}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            {isActive ? (
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
              </span>
            ) : null}
            <p className={compact ? 'text-xs font-semibold text-foreground' : 'text-sm font-semibold text-foreground'}>
              {readyForReview || stage === 'ready_for_review'
                ? 'پیش‌نویس تمرین آماده بازبینی است'
                : isFailed
                  ? 'ساخت پیش‌نویس تمرین کامل نشد'
                  : isCancelled
                    ? 'استخراج تمرین متوقف شد'
                    : 'در حال ساخت پیش‌نویس تمرین'}
            </p>
          </div>
          <p className="text-xs leading-6 text-muted-foreground">
            {workflowMessage || 'وضعیت ساخت تمرین در حال به‌روزرسانی است.'}
          </p>
        </div>
        {stage ? (
          <span className="rounded-full border border-border/70 px-2 py-1 text-[11px] text-muted-foreground">
            {STAGE_LABELS[stage] ?? stage}
          </span>
        ) : null}
      </div>

      {stage ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>{STAGE_LABELS[stage] ?? 'در حال پردازش'}</span>
            <span className="tabular-nums">{effectiveProgress}%</span>
          </div>
          <Progress value={effectiveProgress} className="h-2" />
        </div>
      ) : null}

      {stage ? (
        <div className={compact ? 'grid gap-2 sm:grid-cols-2 lg:grid-cols-3' : 'grid gap-2 sm:grid-cols-2 xl:grid-cols-4'}>
          {STAGE_FLOW.map((flowStage, index) => {
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
                    ? 'rounded-xl border border-primary/20 bg-primary/10 px-3 py-2 text-xs text-primary'
                    : state === 'active'
                      ? 'rounded-xl border border-primary/30 bg-primary/5 px-3 py-2 text-xs text-foreground'
                      : 'rounded-xl border border-border/70 bg-muted/20 px-3 py-2 text-xs text-muted-foreground'
                }
              >
                {STAGE_LABELS[flowStage]}
              </div>
            );
          })}
        </div>
      ) : null}

      {cleanedWarnings.length > 0 ? (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-3">
          <p className="text-xs font-medium text-amber-700 dark:text-amber-300">نیازمند توجه شما</p>
          <ul className="mt-2 space-y-1 text-xs leading-6 text-amber-700/90 dark:text-amber-200/90">
            {cleanedWarnings.map((warning) => (
              <li key={warning}>• {warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
