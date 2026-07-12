'use client';

import { Progress } from '@/components/ui/progress';
import type { ExerciseStatus, ExerciseWorkflowStage } from '@/services/exercises-service';

const STAGE_LABELS: Record<ExerciseWorkflowStage, string> = {
  queued: 'در صف',
  reading_sources: 'دریافت و خواندن منبع',
  ocr_and_transcription: 'دریافت و خواندن منبع',
  extracting_questions: 'استخراج سوال‌ها',
  matching_reference_answers: 'تطبیق پاسخ‌ها',
  building_review_draft: 'ساخت پیش‌نویس',
  ready_for_review: 'پایان پردازش',
  cancelled: 'متوقف‌شده',
  failed: 'خطا',
};

const STAGE_FLOW: ExerciseWorkflowStage[] = [
  'queued',
  'reading_sources',
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
  readyForReview = false,
  exerciseStatus,
  compact = false,
}: ExerciseWorkflowTrackerProps) {
  const stage = workflowStage ?? null;
  const normalizedStage = stage === 'ocr_and_transcription' ? 'reading_sources' : stage;
  const effectiveProgress = Math.max(0, Math.min(100, Number(progressPercent ?? 0)));
  const currentStageIndex = normalizedStage ? STAGE_FLOW.indexOf(normalizedStage) : -1;
  const isFailed = stage === 'failed' || exerciseStatus === 'failed';
  const isCancelled = stage === 'cancelled' || exerciseStatus === 'cancelled';
  const isActive = Boolean(stage && ACTIVE_EXERCISE_WORKFLOW_STAGES.has(stage) && !isFailed && !isCancelled);
  const finalMessage = 'پردازش تمرین کامل شد. برای بررسی و انتشار، پیش‌نویس را باز کنید.';

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
                ? 'پردازش تمرین کامل شد'
                : isFailed
                  ? 'ساخت پیش‌نویس تمرین کامل نشد'
                  : isCancelled
                    ? 'استخراج تمرین متوقف شد'
                    : 'در حال ساخت پیش‌نویس تمرین'}
            </p>
          </div>
          <p className="text-xs leading-6 text-muted-foreground">
            {readyForReview || stage === 'ready_for_review'
              ? finalMessage
              : workflowMessage || 'وضعیت ساخت تمرین در حال به‌روزرسانی است.'}
          </p>
        </div>
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
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {STAGE_FLOW.map((flowStage, index) => {
            const state =
              flowStage === normalizedStage
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
    </div>
  );
}
