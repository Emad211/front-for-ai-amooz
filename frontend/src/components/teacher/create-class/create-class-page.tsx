'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ClassInfoForm } from './class-info-form';
import { FileUploadSection } from './file-upload-section';
import { StudentInviteSection } from './student-invite-section';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  getClassCreationSessionDetail,
  type ClassCreationSessionDetail,
  addClassInvites,
  addExamPrepInvites,
  cancelClassCreationSession,
  transcribeClassCreationStep1,
  // Exam Prep imports
  transcribeExamPrepStep1,
  fetchExamPrepSession,
  cancelExamPrepSession,
  type ExamPrepSessionDetail,
  type ExamPrepStatus,
  type UploadProgress,
} from '@/services/classes-service';
import { PipelineTracker } from './pipeline-tracker';
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
import { Ban, ChevronDown, Loader2, NotebookPen } from 'lucide-react';
import { ExerciseIntakeForm, buildEmptyExerciseIntakeDraft, type ExerciseIntakeDraft } from '@/components/teacher/exercises/exercise-intake-form';
import {
  ACTIVE_EXERCISE_WORKFLOW_STAGES,
  ExerciseWorkflowTracker,
} from '@/components/teacher/exercises/exercise-workflow-tracker';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import type { StudyGroup } from '@/types';
import { CLASS_DESCRIPTION_MAX_LENGTH } from '@/constants/teacher-limits';

type PipelineType = 'class' | 'exam_prep';

const clampDescription = (value: string) => value.slice(0, CLASS_DESCRIPTION_MAX_LENGTH);

const ACTIVE_SESSION_STORAGE_KEY = 'ai_amooz_active_class_creation_session_id';
const CREATE_CLASS_DRAFT_STORAGE_KEY = 'ai_amooz_create_class_draft_v1';
const CREATE_CLASS_LAST_STATUS_STORAGE_KEY = 'ai_amooz_create_class_last_status_v1';
// Exam Prep storage keys
const ACTIVE_EXAM_PREP_SESSION_STORAGE_KEY = 'ai_amooz_active_exam_prep_session_id';
const CREATE_EXAM_PREP_DRAFT_STORAGE_KEY = 'ai_amooz_create_exam_prep_draft_v1';
const CREATE_EXAM_PREP_LAST_STATUS_STORAGE_KEY = 'ai_amooz_create_exam_prep_last_status_v1';

// Class pipeline statuses (5 steps)
const CLASS_PROCESSING_STATUSES = new Set([
  'transcribing',
  'structuring',
  'prereq_extracting',
  'prereq_teaching',
  'recapping',
]);

// Exam prep pipeline statuses (2 steps)
const EXAM_PREP_PROCESSING_STATUSES = new Set([
  'exam_transcribing',
  'exam_structuring',
]);

function getClassPipelineMessage(status?: string | null) {
  if (!status) {
    return { message: null, isDone: false, isFailed: false } as const;
  }
  if (status === 'failed') {
    return { message: 'پردازش با خطا متوقف شد.', isDone: false, isFailed: true } as const;
  }
  if (status === 'cancelled') {
    return { message: 'پردازش توسط شما لغو شد.', isDone: false, isFailed: false } as const;
  }
  switch (status) {
    case 'transcribing':
      return { message: 'در حال انجام مرحله ۱ از ۵…', isDone: false, isFailed: false } as const;
    case 'transcribed':
      return { message: 'مرحله ۱ از ۵ تمام شد.', isDone: false, isFailed: false } as const;
    case 'structuring':
      return { message: 'در حال انجام مرحله ۲ از ۵…', isDone: false, isFailed: false } as const;
    case 'structured':
      return { message: 'مرحله ۲ از ۵ تمام شد.', isDone: false, isFailed: false } as const;
    case 'prereq_extracting':
      return { message: 'در حال انجام مرحله ۳ از ۵…', isDone: false, isFailed: false } as const;
    case 'prereq_extracted':
      return { message: 'مرحله ۳ از ۵ تمام شد.', isDone: false, isFailed: false } as const;
    case 'prereq_teaching':
      return { message: 'در حال انجام مرحله ۴ از ۵…', isDone: false, isFailed: false } as const;
    case 'prereq_taught':
      return { message: 'مرحله ۴ از ۵ تمام شد.', isDone: false, isFailed: false } as const;
    case 'recapping':
      return { message: 'در حال انجام مرحله ۵ از ۵…', isDone: false, isFailed: false } as const;
    case 'recapped':
      return { message: 'مرحله ۵ از ۵ تمام شد.', isDone: true, isFailed: false } as const;
    default:
      return { message: 'در حال پردازش…', isDone: false, isFailed: false } as const;
  }
}

function getExamPrepPipelineMessage(status?: string | null) {
  if (!status) {
    return { message: null, isDone: false, isFailed: false } as const;
  }
  if (status === 'failed') {
    return { message: 'پردازش با خطا متوقف شد.', isDone: false, isFailed: true } as const;
  }
  if (status === 'cancelled') {
    return { message: 'پردازش توسط شما لغو شد.', isDone: false, isFailed: false } as const;
  }
  switch (status) {
    case 'exam_transcribing':
      return { message: 'در حال پردازش فایل…', isDone: false, isFailed: false } as const;
    case 'exam_transcribed':
      return { message: 'پردازش فایل تمام شد.', isDone: false, isFailed: false } as const;
    case 'exam_structuring':
      return { message: 'در حال آماده‌سازی سوالات…', isDone: false, isFailed: false } as const;
    case 'exam_structured':
      return { message: 'آماده‌سازی کامل شد. اکنون می‌توانید دانش‌آموزان را دعوت کنید.', isDone: true, isFailed: false } as const;
    default:
      return { message: 'در حال پردازش…', isDone: false, isFailed: false } as const;
  }
}

function hasActiveEmbeddedExercises(detail: ClassCreationSessionDetail | null): boolean {
  const rows = detail?.pendingExercises ?? [];
  if (rows.length === 0) return false;

  return rows.some((exercise) => {
    if (exercise.status === 'failed' || exercise.exerciseStatus === 'failed') return false;
    if (exercise.exerciseStatus === 'cancelled' || exercise.workflowStage === 'cancelled') return false;
    if (exercise.readyForReview || exercise.workflowStage === 'ready_for_review') return false;

    // After the class is ready, the exercise may still be materializing into a
    // real ClassExercise row. Keep polling until the exerciseId/workflow arrives.
    if (!exercise.exerciseId) return true;
    if (!exercise.workflowStage) return true;

    return ACTIVE_EXERCISE_WORKFLOW_STAGES.has(exercise.workflowStage);
  });
}

function hasPersistedEmbeddedExercises(detail: ClassCreationSessionDetail | null): boolean {
  return Boolean(detail?.pendingExercises?.length);
}

export function CreateClassPage() {
  const { activeWorkspace } = useWorkspace();
  const [studyGroups, setStudyGroups] = useState<StudyGroup[]>([]);
  const [selectedStudyGroupId, setSelectedStudyGroupId] = useState<string>('none');
  const [pipelineType, setPipelineType] = useState<PipelineType>('class');
  const [expandedSections, setExpandedSections] = useState<string[]>(['info', 'files', 'students']);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [level, setLevel] = useState<string>('');
  const [duration, setDuration] = useState<string>('');
  const [lessonFile, setLessonFile] = useState<File | null>(null);
  const [includeExercises, setIncludeExercises] = useState(false);
  const [pendingExercises, setPendingExercises] = useState<ExerciseIntakeDraft[]>([buildEmptyExerciseIntakeDraft()]);
  const [draftInvitePhones, setDraftInvitePhones] = useState<string[]>([]);
  const [step1ClientRequestId, setStep1ClientRequestId] = useState<string | null>(null);
  // Class pipeline state
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [sessionDetail, setSessionDetail] = useState<ClassCreationSessionDetail | null>(null);
  const [optimisticStatus, setOptimisticStatus] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [isPipelineStarting, setIsPipelineStarting] = useState(false);
  // Exam prep pipeline state
  const [activeExamPrepSessionId, setActiveExamPrepSessionId] = useState<number | null>(null);
  const [examPrepSessionDetail, setExamPrepSessionDetail] = useState<ExamPrepSessionDetail | null>(null);
  const [examPrepOptimisticStatus, setExamPrepOptimisticStatus] = useState<string | null>(null);
  const [examPrepPipelineError, setExamPrepPipelineError] = useState<string | null>(null);
  const [isExamPrepPipelineStarting, setIsExamPrepPipelineStarting] = useState(false);

  // Shared across both pipelines: an in-flight cancel request (locks the dialog).
  const [isCancelling, setIsCancelling] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);

  // Upload progress state (shared between class & exam prep)
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

  const pollTimer = useRef<number | null>(null);
  const pollFailures = useRef<number>(0);
  const pipelineSectionRef = useRef<HTMLDivElement | null>(null);

  const syncEmbeddedExercisesFromSession = (detail: ClassCreationSessionDetail) => {
    if (hasPersistedEmbeddedExercises(detail)) {
      setIncludeExercises(true);
    }
  };

  const loadDraft = () => {
    try {
      const raw = window.localStorage.getItem(CREATE_CLASS_DRAFT_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { title?: string; description?: string };
      if (typeof parsed.title === 'string' && parsed.title) setTitle((prev) => prev || (parsed.title as string));
      if (typeof parsed.description === 'string' && parsed.description) {
        setDescription((prev) => prev || clampDescription(parsed.description as string));
      }
    } catch {
      // ignore
    }
  };

  const persistDraft = (next: { title: string; description: string }) => {
    try {
      window.localStorage.setItem(CREATE_CLASS_DRAFT_STORAGE_KEY, JSON.stringify(next));
    } catch {
      // ignore
    }
  };

  const persistLastStatus = (next: { sessionId: number; status: string }) => {
    try {
      window.localStorage.setItem(CREATE_CLASS_LAST_STATUS_STORAGE_KEY, JSON.stringify(next));
    } catch {
      // ignore
    }
  };

  const stopPolling = () => {
    if (pollTimer.current) {
      window.clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const startPolling = (sessionId: number) => {
    stopPolling();
    const tick = async () => {
      try {
        const detail = await getClassCreationSessionDetail(sessionId);
        pollFailures.current = 0;
        setOptimisticStatus(null);
        setSessionDetail(detail);
        setActiveSessionId(detail.id);
        syncEmbeddedExercisesFromSession(detail);

        if (detail?.status) {
          persistLastStatus({ sessionId: detail.id, status: detail.status });
        }

        setTitle((prev) => prev || detail.title);
        setDescription((prev) => prev || clampDescription(detail.description));
        setLevel((prev) => prev || String((detail as any).level || '').trim());
        setDuration((prev) => prev || String((detail as any).duration || '').trim());

        if (detail.status === 'failed') {
          stopPolling();
          setPipelineError(detail.error_detail || 'پردازش با خطا متوقف شد');
          return;
        }

        if (detail.status === 'cancelled') {
          stopPolling();
          return;
        }

        if (detail.status === 'recapped' && !hasActiveEmbeddedExercises(detail)) {
          stopPolling();
          return;
        }

        // Schedule next tick (setTimeout prevents pileup from slow responses)
        pollTimer.current = window.setTimeout(() => void tick(), 2000);
      } catch {
        pollFailures.current += 1;
        if (pollFailures.current >= 4) {
          stopPolling();
          setPipelineError('ارتباط با سرور برای دریافت وضعیت پردازش برقرار نشد.');
          return;
        }
        pollTimer.current = window.setTimeout(() => void tick(), 2000);
      }
    };

    void tick();
  };

  const resumeSession = async (sessionId: number) => {
    try {
      const detail = await getClassCreationSessionDetail(sessionId);
      pollFailures.current = 0;
      setOptimisticStatus(null);
      setSessionDetail(detail);
      setActiveSessionId(detail.id);
      syncEmbeddedExercisesFromSession(detail);
      setTitle(detail.title);
      setDescription(clampDescription(detail.description));
      setLevel(String((detail as any).level || '').trim());
      setDuration(String((detail as any).duration || '').trim());

      if (
        detail.status !== 'failed' &&
        detail.status !== 'cancelled' &&
        (detail.status !== 'recapped' || hasActiveEmbeddedExercises(detail))
      ) {
        startPolling(sessionId);
      }
    } catch {
      // If resume fails, don't block the page.
    }
  };

  // Exam Prep Polling
  const startExamPrepPolling = (sessionId: number) => {
    stopPolling();
    const tick = async () => {
      try {
        const detail = await fetchExamPrepSession(sessionId);
        pollFailures.current = 0;
        setExamPrepOptimisticStatus(null);
        setExamPrepSessionDetail(detail);
        setActiveExamPrepSessionId(detail.id);

        try {
          window.localStorage.setItem(CREATE_EXAM_PREP_LAST_STATUS_STORAGE_KEY, JSON.stringify({ sessionId: detail.id, status: detail.status }));
        } catch { /* ignore */ }

        setTitle((prev) => prev || detail.title);
        setDescription((prev) => prev || clampDescription(detail.description));

        if (detail.status === 'failed') {
          stopPolling();
          setExamPrepPipelineError(detail.error_detail || 'پردازش با خطا متوقف شد');
          return;
        }

        if (detail.status === 'cancelled') {
          stopPolling();
          return;
        }

        if (detail.status === 'exam_structured') {
          stopPolling();
          return;
        }

        pollTimer.current = window.setTimeout(() => void tick(), 2000);
      } catch {
        pollFailures.current += 1;
        if (pollFailures.current >= 4) {
          stopPolling();
          setExamPrepPipelineError('ارتباط با سرور برای دریافت وضعیت پردازش برقرار نشد.');
          return;
        }
        pollTimer.current = window.setTimeout(() => void tick(), 2000);
      }
    };

    void tick();
  };

  const resumeExamPrepSession = async (sessionId: number) => {
    try {
      const detail = await fetchExamPrepSession(sessionId);
      pollFailures.current = 0;
      setExamPrepOptimisticStatus(null);
      setExamPrepSessionDetail(detail);
      setActiveExamPrepSessionId(detail.id);
      setTitle(detail.title);
      setDescription(clampDescription(detail.description));

      if (detail.status !== 'failed' && detail.status !== 'cancelled' && detail.status !== 'exam_structured') {
        startExamPrepPolling(sessionId);
      }
    } catch {
      // If resume fails, don't block the page.
    }
  };

  useEffect(() => {
    // A newly selected file must get a fresh idempotency key. Otherwise the
    // backend's client_request_id de-duplication returns the PREVIOUS session
    // (the old video). Reset on any change to the selected lesson file.
    setStep1ClientRequestId(null);
  }, [lessonFile]);

  useEffect(() => {
    // In org mode, offer the teacher's study groups so a new class/exam can be
    // attached to one. Personal mode → no groups.
    if (!activeWorkspace) {
      setStudyGroups([]);
      setSelectedStudyGroupId('none');
      return;
    }
    let cancelled = false;
    OrganizationService.getMyStudyGroups(activeWorkspace.id)
      .then((data) => { if (!cancelled) setStudyGroups(data); })
      .catch(() => { if (!cancelled) setStudyGroups([]); });
    return () => { cancelled = true; };
  }, [activeWorkspace]);

  useEffect(() => {
    // Resume active session if user navigated away.
    const stored = window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
    const sessionId = stored ? Number(stored) : NaN;
    if (Number.isFinite(sessionId)) {
      try {
        const lastRaw = window.localStorage.getItem(CREATE_CLASS_LAST_STATUS_STORAGE_KEY);
        if (lastRaw) {
          const last = JSON.parse(lastRaw) as { sessionId?: number; status?: string };
          if (last && last.sessionId === sessionId && typeof last.status === 'string') {
            setOptimisticStatus(last.status);
          }
        }
      } catch {
        // ignore
      }
      resumeSession(sessionId);
    } else {
      // Check for exam prep session
      const examPrepStored = window.localStorage.getItem(ACTIVE_EXAM_PREP_SESSION_STORAGE_KEY);
      const examPrepSessionId = examPrepStored ? Number(examPrepStored) : NaN;
      if (Number.isFinite(examPrepSessionId)) {
        try {
          const lastRaw = window.localStorage.getItem(CREATE_EXAM_PREP_LAST_STATUS_STORAGE_KEY);
          if (lastRaw) {
            const last = JSON.parse(lastRaw) as { sessionId?: number; status?: string };
            if (last && last.sessionId === examPrepSessionId && typeof last.status === 'string') {
              setExamPrepOptimisticStatus(last.status);
              setPipelineType('exam_prep');
            }
          }
        } catch { /* ignore */ }
        setPipelineType('exam_prep');
        resumeExamPrepSession(examPrepSessionId);
      } else {
        loadDraft();
      }
    }
    return () => stopPolling();
  }, []);

  useEffect(() => {
    persistDraft({ title, description: clampDescription(description) });
  }, [title, description]);

  const toggleSection = (section: string) => {
    setExpandedSections((prev) =>
      prev.includes(section) ? prev.filter((s) => s !== section) : [...prev, section]
    );
  };

  const setEmbeddedExercisesEnabled = (checked: boolean) => {
    setIncludeExercises(checked);
    if (checked) {
      setExpandedSections((prev) => (prev.includes('exercises') ? prev : [...prev, 'exercises']));
    }
  };

  const revealPipelineProgress = (message: string) => {
    setExpandedSections((prev) => (prev.includes('files') ? prev : [...prev, 'files']));
    toast.success(message, {
      description: 'وضعیت پردازش در بخش بارگذاری فایل نمایش داده می‌شود.',
    });
    window.setTimeout(() => {
      pipelineSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  };

  const updatePendingExercise = (clientExerciseKey: string, next: ExerciseIntakeDraft) => {
    setPendingExercises((prev) =>
      prev.map((exercise) => (exercise.clientExerciseKey === clientExerciseKey ? next : exercise)),
    );
  };

  const addPendingExercise = () => {
    setPendingExercises((prev) => [...prev, buildEmptyExerciseIntakeDraft()]);
  };

  const removePendingExercise = (clientExerciseKey: string) => {
    setPendingExercises((prev) => {
      const next = prev.filter((exercise) => exercise.clientExerciseKey !== clientExerciseKey);
      return next.length > 0 ? next : [buildEmptyExerciseIntakeDraft()];
    });
  };

  const startNewDraft = () => {
    stopPolling();
    pollFailures.current = 0;

    setExpandedSections(['info', 'files', 'students']);
    setTitle('');
    setDescription('');
    setLevel('');
    setDuration('');
    setLessonFile(null);
    setIncludeExercises(false);
    setPendingExercises([buildEmptyExerciseIntakeDraft()]);
    setDraftInvitePhones([]);
    setStep1ClientRequestId(null);
    setSelectedStudyGroupId('none');

    setActiveSessionId(null);
    setSessionDetail(null);
    setOptimisticStatus(null);
    setPipelineError(null);
    setIsPipelineStarting(false);

    setActiveExamPrepSessionId(null);
    setExamPrepSessionDetail(null);
    setExamPrepOptimisticStatus(null);
    setExamPrepPipelineError(null);
    setIsExamPrepPipelineStarting(false);

    setIsCancelling(false);
    setCancelDialogOpen(false);
    setUploadProgress(null);

    try {
      window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
      window.localStorage.removeItem(CREATE_CLASS_DRAFT_STORAGE_KEY);
      window.localStorage.removeItem(CREATE_CLASS_LAST_STATUS_STORAGE_KEY);
      window.localStorage.removeItem(ACTIVE_EXAM_PREP_SESSION_STORAGE_KEY);
      window.localStorage.removeItem(CREATE_EXAM_PREP_DRAFT_STORAGE_KEY);
      window.localStorage.removeItem(CREATE_EXAM_PREP_LAST_STATUS_STORAGE_KEY);
    } catch {
      // ignore
    }

    toast.success(pipelineType === 'class' ? 'فرم برای ساخت کلاس جدید آماده شد.' : 'فرم برای ساخت آمادگی آزمون جدید آماده شد.');
  };

  // Class Pipeline computed values
  const sessionIdForActions = sessionDetail?.id ?? activeSessionId ?? null;
  const status = sessionDetail?.status ?? optimisticStatus ?? null;
  const { message: classPipelineMessage, isDone: isClassPipelineDone, isFailed: isClassPipelineFailed } = getClassPipelineMessage(status);
  const isClassPipelineRunning = Boolean(status && CLASS_PROCESSING_STATUSES.has(status));
  const canStartClassPipeline = Boolean(title.trim()) && Boolean(lessonFile) && !isPipelineStarting && !isClassPipelineRunning;

  // Exam Prep Pipeline computed values
  const examPrepSessionIdForActions = examPrepSessionDetail?.id ?? activeExamPrepSessionId ?? null;
  const examPrepStatus = examPrepSessionDetail?.status ?? examPrepOptimisticStatus ?? null;
  const { message: examPrepPipelineMessage, isDone: isExamPrepPipelineDone, isFailed: isExamPrepPipelineFailed } = getExamPrepPipelineMessage(examPrepStatus);
  const isExamPrepPipelineRunning = Boolean(examPrepStatus && EXAM_PREP_PROCESSING_STATUSES.has(examPrepStatus));
  const canStartExamPrepPipeline = Boolean(title.trim()) && Boolean(lessonFile) && !isExamPrepPipelineStarting && !isExamPrepPipelineRunning;

  // Current pipeline state based on selected type
  const currentSessionId = pipelineType === 'class' ? sessionIdForActions : examPrepSessionIdForActions;
  const currentPipelineError = pipelineType === 'class' ? pipelineError : examPrepPipelineError;
  const currentIsPipelineRunning = pipelineType === 'class' ? isClassPipelineRunning : isExamPrepPipelineRunning;
  const currentCanStartPipeline = pipelineType === 'class' ? canStartClassPipeline : canStartExamPrepPipeline;
  const currentIsPipelineStarting = pipelineType === 'class' ? isPipelineStarting : isExamPrepPipelineStarting;
  const currentStatus = pipelineType === 'class' ? status : examPrepStatus;
  const currentWorkflowStage = pipelineType === 'class' ? sessionDetail?.workflowStage ?? null : examPrepSessionDetail?.workflowStage ?? null;
  const currentWorkflowMessage = pipelineType === 'class' ? sessionDetail?.workflowMessage ?? null : examPrepSessionDetail?.workflowMessage ?? null;
  const currentProgressPercent = pipelineType === 'class' ? sessionDetail?.progressPercent ?? null : examPrepSessionDetail?.progressPercent ?? null;
  const currentWorkflowWarnings = pipelineType === 'class' ? sessionDetail?.workflowWarnings ?? [] : examPrepSessionDetail?.workflowWarnings ?? [];
  const currentReadyForReview = pipelineType === 'class' ? sessionDetail?.readyForReview ?? false : examPrepSessionDetail?.readyForReview ?? false;
  const currentStartedAt = pipelineType === 'class' ? sessionDetail?.created_at ?? null : examPrepSessionDetail?.created_at ?? null;
  const currentIsPipelineCancelled = currentStatus === 'cancelled';
  const currentHasActiveEmbeddedExercises = pipelineType === 'class' && status === 'recapped' && hasActiveEmbeddedExercises(sessionDetail);
  const persistedEmbeddedExercises = pipelineType === 'class' ? (sessionDetail?.pendingExercises ?? []) : [];
  const hasSubmittedEmbeddedExercises = persistedEmbeddedExercises.length > 0;
  const effectiveIncludeExercises = includeExercises || hasSubmittedEmbeddedExercises;
  const embeddedExerciseCount = hasSubmittedEmbeddedExercises ? persistedEmbeddedExercises.length : pendingExercises.length;
  const currentIsTerminalSession = Boolean(currentSessionId) && (
    pipelineType === 'class'
      ? currentStatus === 'failed' || currentStatus === 'cancelled' || (currentStatus === 'recapped' && !currentHasActiveEmbeddedExercises)
      : currentStatus === 'failed' || currentStatus === 'cancelled' || currentStatus === 'exam_structured'
  );
  const currentCanSubmitNewPipeline = currentCanStartPipeline && !currentSessionId;
  const destinationHref = pipelineType === 'class' ? '/teacher/my-classes' : '/teacher/my-exams';
  const newDraftLabel = pipelineType === 'class' ? 'ساخت کلاس جدید' : 'ساخت آمادگی آزمون جدید';
  const destinationLabel = pipelineType === 'class' ? 'رفتن به کلاس‌ها' : 'رفتن به آمادگی آزمون‌ها';
  const terminalActionCopy = currentStatus === 'failed'
    ? 'پردازش این مورد با خطا متوقف شده است. می‌توانید فرم را برای ساخت مورد جدید خالی کنید.'
    : currentStatus === 'cancelled'
      ? 'پردازش این مورد لغو شده است. برای شروع دوباره، فرم را از نو بسازید.'
      : pipelineType === 'class'
        ? 'پیش‌نویس این کلاس آماده است و از صفحه کلاس‌ها قابل بازبینی و انتشار است.'
        : 'پیش‌نویس آمادگی آزمون آماده است و از صفحه آمادگی آزمون‌ها قابل بازبینی و انتشار است.';
  // A running pipeline with a known session id is the only thing we can revoke.
  const canCancelPipeline = currentIsPipelineRunning && Boolean(currentSessionId);

  const startFullPipeline = async () => {
    if (!lessonFile) return;
    if (pipelineType === 'class' && includeExercises) {
      const invalid = pendingExercises.find(
        (exercise) =>
          !exercise.title.trim() ||
          exercise.sources.length === 0 ||
          (!exercise.noDeadline && !exercise.deadline),
      );
      if (invalid) {
        toast.error('بخش تمرین را کامل کنید: عنوان، منبع و وضعیت مهلت هر تمرین باید مشخص باشد.');
        return;
      }
    }

    const clientRequestId = step1ClientRequestId ?? (globalThis.crypto?.randomUUID?.() ?? null);
    if (clientRequestId && clientRequestId !== step1ClientRequestId) {
      setStep1ClientRequestId(clientRequestId);
    }

    if (pipelineType === 'class') {
      setIsPipelineStarting(true);
      setPipelineError(null);
      pollFailures.current = 0;
      setOptimisticStatus(null);
      setUploadProgress(null);
      stopPolling();
      setSessionDetail(null);
      setActiveSessionId(null);

      try {
        const result = await transcribeClassCreationStep1(
          {
            title: title.trim(),
            description: clampDescription(description),
            file: lessonFile,
            clientRequestId: clientRequestId ?? undefined,
            runFullPipeline: true,
            organizationId: activeWorkspace?.id ?? undefined,
            studyGroupId: selectedStudyGroupId !== 'none' ? Number(selectedStudyGroupId) : undefined,
            pendingExercises: includeExercises
              ? pendingExercises.map((exercise) => ({
                  clientExerciseKey: exercise.clientExerciseKey,
                  title: exercise.title.trim(),
                  noDeadline: exercise.noDeadline,
                  deadline: exercise.noDeadline ? null : new Date(exercise.deadline).toISOString(),
                  allowLate: !exercise.noDeadline && exercise.allowLate,
                  assistantEnabled: exercise.assistantEnabled,
                  teacherNote: exercise.teacherNote.trim(),
                  sources: exercise.sources,
                }))
              : [],
          },
          { onProgress: (p) => setUploadProgress(p) },
        );
        setUploadProgress(null);
        setOptimisticStatus(result.status);
        setActiveSessionId(result.id);
        window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(result.id));
        persistLastStatus({ sessionId: result.id, status: result.status });
        if (draftInvitePhones.length > 0) {
          addClassInvites(result.id, draftInvitePhones)
            .then(() => setDraftInvitePhones([]))
            .catch(() => {
              toast.warning('کلاس ذخیره شد، اما دعوت دانش‌آموزان ثبت نشد. بعداً از همین بخش دوباره اضافه کنید.');
            });
        }
        startPolling(result.id);
        revealPipelineProgress('پردازش کلاس شروع شد.');
      } catch (error) {
        const msg = error instanceof Error ? error.message : 'خطا در ارتباط با سرور';
        setPipelineError(msg);
        setUploadProgress(null);
      } finally {
        setIsPipelineStarting(false);
      }
    } else {
      // Exam Prep Pipeline
      setIsExamPrepPipelineStarting(true);
      setExamPrepPipelineError(null);
      pollFailures.current = 0;
      setExamPrepOptimisticStatus(null);
      setUploadProgress(null);
      stopPolling();
      setExamPrepSessionDetail(null);
      setActiveExamPrepSessionId(null);

      try {
        const result = await transcribeExamPrepStep1(
          {
            title: title.trim(),
            description: clampDescription(description),
            file: lessonFile,
            clientRequestId: clientRequestId ?? undefined,
            runFullPipeline: true,
            organizationId: activeWorkspace?.id ?? undefined,
            studyGroupId: selectedStudyGroupId !== 'none' ? Number(selectedStudyGroupId) : undefined,
          },
          { onProgress: (p) => setUploadProgress(p) },
        );
        setUploadProgress(null);
        setExamPrepOptimisticStatus(result.status);
        setActiveExamPrepSessionId(result.id);
        window.localStorage.setItem(ACTIVE_EXAM_PREP_SESSION_STORAGE_KEY, String(result.id));
        if (draftInvitePhones.length > 0) {
          addExamPrepInvites(result.id, draftInvitePhones)
            .then(() => setDraftInvitePhones([]))
            .catch(() => {
              toast.warning('آمادگی آزمون ذخیره شد، اما دعوت دانش‌آموزان ثبت نشد. بعداً از همین بخش دوباره اضافه کنید.');
            });
        }
        try {
          window.localStorage.setItem(CREATE_EXAM_PREP_LAST_STATUS_STORAGE_KEY, JSON.stringify({ sessionId: result.id, status: result.status }));
        } catch { /* ignore */ }
        startExamPrepPolling(result.id);
        revealPipelineProgress('پردازش آمادگی آزمون شروع شد.');
      } catch (error) {
        const msg = error instanceof Error ? error.message : 'خطا در ارتباط با سرور';
        setExamPrepPipelineError(msg);
        setUploadProgress(null);
      } finally {
        setIsExamPrepPipelineStarting(false);
      }
    }
  };

  const cancelPipeline = async () => {
    // Guard: nothing running, or no session id to revoke.
    if (!canCancelPipeline) return;
    setIsCancelling(true);
    try {
      if (pipelineType === 'class') {
        const detail = await cancelClassCreationSession(sessionIdForActions as number);
        stopPolling();
        setSessionDetail(detail);
        setOptimisticStatus(detail.status);
        setPipelineError(null);
        persistLastStatus({ sessionId: detail.id, status: detail.status });
        // Terminal state: don't auto-resume this session on the next visit.
        window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
        toast.success('پردازش کلاس لغو شد.');
      } else {
        const detail = await cancelExamPrepSession(examPrepSessionIdForActions as number);
        stopPolling();
        setExamPrepSessionDetail(detail);
        setExamPrepOptimisticStatus(detail.status);
        setExamPrepPipelineError(null);
        try {
          window.localStorage.setItem(
            CREATE_EXAM_PREP_LAST_STATUS_STORAGE_KEY,
            JSON.stringify({ sessionId: detail.id, status: detail.status }),
          );
        } catch { /* ignore */ }
        window.localStorage.removeItem(ACTIVE_EXAM_PREP_SESSION_STORAGE_KEY);
        toast.success('پردازش آمادگی آزمون لغو شد.');
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'خطا در لغو پردازش';
      toast.error(msg);
      // Re-throw so the confirm dialog stays open and the user can retry.
      throw e;
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <div className="space-y-8" dir="rtl">
      <Card className="relative overflow-hidden border-border/40 bg-gradient-to-l from-primary/10 via-background to-background rounded-3xl shadow-xl shadow-primary/5">
        <div className="absolute inset-y-0 left-0 w-32 sm:w-40 bg-primary/10 blur-3xl" />
        <div className="relative p-6 sm:p-8 flex flex-col gap-3">
          <div className="flex items-center gap-3 text-primary">
            <span className="h-10 w-10 rounded-2xl bg-primary/10 flex items-center justify-center font-black text-lg">+</span>
            <p className="text-sm text-primary">{pipelineType === 'class' ? 'مسیر ساخت کلاس' : 'مسیر آمادگی آزمون'}</p>
          </div>
          <div className="flex flex-col gap-2">
            <h1 className="text-2xl md:text-3xl font-black text-foreground">
              {pipelineType === 'class' ? 'ایجاد کلاس جدید' : 'ایجاد آمادگی آزمون'}
            </h1>
            <p className="text-muted-foreground text-sm md:text-base">
              {pipelineType === 'class'
                ? 'همه اطلاعات کلاس را یک‌جا ثبت کنید و ذخیره و پردازش را بزنید؛ بعد از آماده‌شدن، از صفحه کلاس‌ها پیش‌نویس را بازبینی و منتشر کنید.'
                : 'اطلاعات و فایل آمادگی آزمون را یک‌جا ثبت کنید؛ بعد از پایان پردازش، از صفحه آمادگی آزمون‌ها پیش‌نویس را بازبینی و منتشر کنید.'}
            </p>
          </div>
          {pipelineType === 'class' ? (
            <div className="flex flex-wrap gap-2 text-xs md:text-sm text-muted-foreground">
              <span className={cn("px-3 py-1 rounded-full", !status ? "bg-primary/10 text-primary" : "bg-muted")}>ثبت اطلاعات</span>
              <span className={cn("px-3 py-1 rounded-full", (status && status !== 'recapped') ? "bg-primary/10 text-primary" : "bg-muted")}>پردازش خودکار</span>
              <span className={cn("px-3 py-1 rounded-full", status === 'recapped' ? "bg-primary/10 text-primary" : "bg-muted")}>بازبینی در کلاس‌ها</span>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2 text-xs md:text-sm text-muted-foreground">
              <span className={cn("px-3 py-1 rounded-full", (!examPrepStatus || examPrepStatus.includes('trans')) ? "bg-primary/10 text-primary" : "bg-muted")}>ثبت اطلاعات</span>
              <span className={cn("px-3 py-1 rounded-full", examPrepStatus === 'exam_structuring' ? "bg-primary/10 text-primary" : "bg-muted")}>پردازش خودکار</span>
              <span className={cn("px-3 py-1 rounded-full", examPrepStatus === 'exam_structured' ? "bg-primary/10 text-primary" : "bg-muted")}>بازبینی در آزمون‌ها</span>
            </div>
          )}
        </div>
      </Card>

      {/* Pipeline Type Selector */}
      <Card className="p-4 sm:p-5 rounded-3xl border-border/40">
        <div className="space-y-3">
          <Label className="text-sm font-semibold">نوع پردازش</Label>
          <Tabs
            value={pipelineType}
            onValueChange={(v) => {
              if (!currentIsPipelineRunning && !currentIsPipelineStarting) {
                setPipelineType(v as PipelineType);
              }
            }}
            className="w-full"
          >
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger
                value="class"
                disabled={currentIsPipelineRunning || currentIsPipelineStarting}
                className="rounded-xl"
              >
                ساخت کلاس 
              </TabsTrigger>
              <TabsTrigger
                value="exam_prep"
                disabled={currentIsPipelineRunning || currentIsPipelineStarting}
                className="rounded-xl"
              >
                آمادگی آزمون
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <p className="text-xs text-muted-foreground">
            {pipelineType === 'class'
              ? 'برای ساخت کلاس آموزشی از این گزینه استفاده کنید. شامل ترنسکریپت، ساختاردهی، پیش‌نیازها، آموزش پیش‌نیازها و خلاصه.'
              : 'برای استخراج سوالات و پاسخ‌ها از ویدیوی حل تست استفاده کنید. شامل ترنسکریپت، استخراج سوالات و دعوت دانش‌آموزان.'}
          </p>
        </div>
      </Card>

      {/* Study group picker — only in org mode, when the teacher has groups */}
      {activeWorkspace && studyGroups.length > 0 && (
        <Card className="p-4 sm:p-5 rounded-3xl border-border/40">
          <div className="space-y-3" dir="rtl">
            <Label className="text-sm font-semibold">گروه آموزشی (اختیاری)</Label>
            <Select value={selectedStudyGroupId} onValueChange={setSelectedStudyGroupId}>
              <SelectTrigger>
                <SelectValue placeholder="بدون گروه" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">بدون گروه</SelectItem>
                {studyGroups.map((g) => (
                  <SelectItem key={g.id} value={String(g.id)}>
                    {g.name}{g.gradeLabel ? ` · ${g.gradeLabel}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              این مورد به گروه انتخاب‌شده در سازمان آموزشی «{activeWorkspace.name}» نسبت داده می‌شود.
            </p>
          </div>
        </Card>
      )}

      <ClassInfoForm
        isExpanded={expandedSections.includes('info')}
        onToggle={() => toggleSection('info')}
        title={title}
        description={description}
        onTitleChange={setTitle}
        onDescriptionChange={(value) => setDescription(clampDescription(value))}
      />

      <div ref={pipelineSectionRef} className="scroll-mt-6">
        <FileUploadSection
          title={pipelineType === 'class' ? 'بارگذاری فایل درسی' : 'بارگذاری فایل حل تست'}
          isExpanded={expandedSections.includes('files')}
          onToggle={() => toggleSection('files')}
          accept="audio/*,video/*,application/pdf,.pdf"
          multiple={false}
          onFilesSelected={(files) => {
            const file = files && files.length ? files[0] : null;
            setLessonFile(file);
            setStep1ClientRequestId(null);
            if (pipelineType === 'class') {
              setPipelineError(null);
              stopPolling();
              setSessionDetail(null);
              setActiveSessionId(null);
              window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
            } else {
              setExamPrepPipelineError(null);
              stopPolling();
              setExamPrepSessionDetail(null);
              setActiveExamPrepSessionId(null);
              window.localStorage.removeItem(ACTIVE_EXAM_PREP_SESSION_STORAGE_KEY);
            }
          }}
        >
          <div className="mt-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="text-xs text-muted-foreground">
                {lessonFile ? `فایل انتخاب‌شده: ${lessonFile.name}` : 'یک فایل صوتی، ویدیویی یا PDF انتخاب کنید.'}
              </div>
            </div>

          {!title.trim() && (
            <div className="text-xs text-muted-foreground">
              {pipelineType === 'class' ? 'برای شروع، ابتدا عنوان کلاس را وارد کنید.' : 'برای شروع، ابتدا عنوان را وارد کنید.'}
            </div>
          )}

          {/* ── Pipeline Tracker (upload progress + step-by-step status) ── */}
          <PipelineTracker
            pipelineType={pipelineType}
            status={currentStatus}
            workflowStage={currentWorkflowStage}
            workflowMessage={currentWorkflowMessage}
            progressPercent={currentProgressPercent}
            workflowWarnings={currentWorkflowWarnings}
            readyForReview={currentReadyForReview}
            uploadProgress={uploadProgress}
            isUploading={currentIsPipelineStarting}
            errorMessage={currentPipelineError}
            sessionId={currentSessionId}
            startedAt={currentStartedAt}
          />
        </div>
        </FileUploadSection>
      </div>

      {pipelineType === 'class' ? (
        <Card className="overflow-hidden rounded-2xl border-border/40 bg-card/70 backdrop-blur" dir="rtl">
          <CardHeader
            className="cursor-pointer transition-colors hover:bg-primary/5"
            onClick={() => toggleSection('exercises')}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                  <NotebookPen className="h-5 w-5 text-primary" />
                </div>
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-lg">تمرین‌های کلاس</CardTitle>
                    <Badge variant={effectiveIncludeExercises ? 'default' : 'outline'} className="rounded-full px-2.5 py-0.5">
                      {effectiveIncludeExercises ? `${embeddedExerciseCount} تمرین` : 'اختیاری'}
                    </Badge>
                  </div>
                  <p className="text-xs leading-6 text-muted-foreground">
                    {effectiveIncludeExercises
                      ? 'پیش‌نویس تمرین‌ها بعد از آماده‌شدن کلاس ساخته و برای بازبینی آماده می‌شوند.'
                      : 'در صورت نیاز، تمرین را همین‌جا همراه کلاس بسازید.'}
                  </p>
                </div>
              </div>
              <ChevronDown
                className={cn(
                  'h-5 w-5 shrink-0 text-muted-foreground transition-transform duration-200',
                  expandedSections.includes('exercises') && 'rotate-180',
                )}
              />
            </div>
          </CardHeader>

          {expandedSections.includes('exercises') ? (
            <CardContent className="space-y-4 pt-0 text-start">
              <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                <div className="flex items-start justify-start gap-3">
                  <Checkbox
                    id="include-embedded-exercises"
                    checked={effectiveIncludeExercises}
                    disabled={Boolean(currentSessionId)}
                    onCheckedChange={(checked) => setEmbeddedExercisesEnabled(Boolean(checked))}
                    className="mt-1 h-5 w-5 shrink-0"
                  />
                  <div className="space-y-1">
                    <Label htmlFor="include-embedded-exercises" className="cursor-pointer text-sm font-semibold">
                      برای این کلاس تمرین هم می‌سازم
                    </Label>
                    <p className="text-xs leading-6 text-muted-foreground">
                      همه اطلاعات تمرین را یک‌بار می‌گیرید؛ بعد از آماده‌شدن کلاس، ساخت تمرین خودکار شروع می‌شود.
                    </p>
                  </div>
                </div>
              </div>

              {effectiveIncludeExercises ? (
                <div className="space-y-4">
                  {hasSubmittedEmbeddedExercises ? (
                    <div className="space-y-2 rounded-2xl border border-border/70 bg-muted/20 p-3">
                      <p className="text-sm font-medium">وضعیت تمرین‌های ثبت‌شده برای این کلاس</p>
                      <div className="space-y-3">
                        {persistedEmbeddedExercises.map((exercise) => (
                          <div key={`${exercise.clientExerciseKey}-${exercise.exerciseId ?? 'pending'}`} className="space-y-3 rounded-xl border border-border/60 bg-background/70 px-3 py-3">
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-sm font-medium">{exercise.title}</span>
                              <Badge
                                variant={
                                  exercise.status === 'failed' || exercise.exerciseStatus === 'failed'
                                    ? 'destructive'
                                    : exercise.readyForReview || exercise.workflowStage === 'ready_for_review'
                                      ? 'default'
                                      : exercise.exerciseId
                                        ? 'secondary'
                                        : 'outline'
                                }
                              >
                                {exercise.status === 'failed' || exercise.exerciseStatus === 'failed'
                                  ? 'خطا در ساخت'
                                  : exercise.readyForReview || exercise.workflowStage === 'ready_for_review'
                                    ? 'آماده بازبینی'
                                    : exercise.workflowStage
                                      ? 'در حال ساخت'
                                      : exercise.exerciseId
                                        ? 'در صف استخراج'
                                    : 'در انتظار آماده‌شدن کلاس'}
                              </Badge>
                            </div>
                            {exercise.workflowStage ? (
                              <ExerciseWorkflowTracker
                                compact
                                workflowStage={exercise.workflowStage}
                                workflowMessage={exercise.workflowMessage ?? exercise.message}
                                progressPercent={exercise.progressPercent}
                                workflowWarnings={exercise.workflowWarnings ?? []}
                                readyForReview={exercise.readyForReview}
                                exerciseStatus={exercise.exerciseStatus}
                              />
                            ) : exercise.message ? (
                              <p className="mt-1 text-xs text-muted-foreground">{exercise.message}</p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {!currentSessionId ? (
                    <>
                      {pendingExercises.map((exercise, index) => (
                        <div key={exercise.clientExerciseKey} className="rounded-2xl border border-border/60 bg-background/30 p-4">
                          <div className="mb-4 flex items-center justify-between gap-3">
                            <div className="space-y-1">
                              <p className="text-sm font-semibold">تمرین {index + 1}</p>
                              <p className="text-xs text-muted-foreground">
                                این تمرین بعد از کامل‌شدن پردازش کلاس، خودکار ساخته و استخراج می‌شود.
                              </p>
                            </div>
                            {pendingExercises.length > 1 ? (
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => removePendingExercise(exercise.clientExerciseKey)}
                              >
                                حذف
                              </Button>
                            ) : null}
                          </div>
                          <ExerciseIntakeForm
                            value={exercise}
                            compact
                            onChange={(next) => updatePendingExercise(exercise.clientExerciseKey, next)}
                          />
                        </div>
                      ))}

                      <div className="flex justify-end">
                        <Button type="button" variant="outline" onClick={addPendingExercise}>
                          افزودن تمرین دیگر
                        </Button>
                      </div>
                    </>
                  ) : null}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border/70 bg-background/30 px-4 py-4 text-sm leading-7 text-muted-foreground">
                  تمرین اختیاری است. اگر الان فعالش نکنید، بعداً از صفحه تمرین‌های همین کلاس می‌توانید تمرین اضافه کنید.
                </div>
              )}
            </CardContent>
          ) : null}
        </Card>
      ) : null}

      {/* Student roster:
          - org class → managed by the org via the study group (no manual invites)
          - personal class → the teacher invites students by phone */}
      {activeWorkspace ? (
        <Card className="p-4 sm:p-5 rounded-3xl border-border/40" dir="rtl">
          <div className="space-y-1.5">
            <Label className="text-sm font-semibold">
              دانش‌آموزان {pipelineType === 'class' ? 'کلاس' : 'آزمون'}
            </Label>
            <p className="text-xs text-muted-foreground leading-6">
              دانش‌آموزانِ {pipelineType === 'class' ? 'کلاس‌های' : 'آزمون‌های'} سازمان آموزشی از «گروه آموزشیِ» انتخاب‌شده
              تعیین می‌شوند و مدیریتِ آن‌ها با مدیر سازمان آموزشی است؛ پس از انتشار، اعضای گروه به‌صورت خودکار اضافه می‌شوند.
              {selectedStudyGroupId === 'none' && ' برای داشتن دانش‌آموز، در بالا یک گروه آموزشی انتخاب کنید.'}
            </p>
          </div>
        </Card>
      ) : (
        <StudentInviteSection
          isExpanded={expandedSections.includes('students')}
          onToggle={() => toggleSection('students')}
          sessionId={currentSessionId}
          pipelineType={pipelineType}
          draftPhones={draftInvitePhones}
          onDraftPhonesChange={setDraftInvitePhones}
        />
      )}

      {/* Only show level/duration for class pipeline */}
      {pipelineType === 'class' && (
        <Card className="p-4 sm:p-5 rounded-3xl border-border/40">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5" dir="rtl">
            <div className="space-y-2">
              <Label>سطح (اختیاری)</Label>
              <Select value={level} onValueChange={(value) => setLevel(value)}>
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب سطح" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">بدون تعیین</SelectItem>
                  <SelectItem value="مبتدی">مبتدی</SelectItem>
                  <SelectItem value="متوسط">متوسط</SelectItem>
                  <SelectItem value="پیشرفته">پیشرفته</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="duration">زمان تقریبی دوره (اختیاری)</Label>
              <Input
                id="duration"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                placeholder="مثلاً ۶ ساعت یا ۲ هفته"
              />
            </div>
          </div>
        </Card>
      )}

      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4">
        <p className="text-xs leading-6 text-muted-foreground">
          {currentIsTerminalSession
            ? terminalActionCopy
            : 'انتشار از این صفحه انجام نمی‌شود؛ بعد از آماده‌شدن، از صفحه کلاس‌ها یا آمادگی آزمون وارد پیش‌نویس شوید و همان‌جا بازبینی و منتشر کنید.'}
        </p>
        {canCancelPipeline ? (
          <AlertDialog
            open={cancelDialogOpen}
            onOpenChange={(open) => {
              if (!isCancelling) setCancelDialogOpen(open);
            }}
          >
            <AlertDialogTrigger asChild>
              <Button
                type="button"
                variant="destructive"
                className="h-11 w-full rounded-xl border border-red-400/70 bg-red-600 px-6 text-white shadow-sm shadow-red-950/40 hover:bg-red-500 focus-visible:ring-red-400 sm:w-auto"
                title="لغو پردازش پایپ‌لاین"
              >
                <Ban className="h-4 w-4" />
                <span className="ms-1.5">لغو پردازش</span>
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent
              dir="rtl"
              onEscapeKeyDown={(e) => {
                if (isCancelling) e.preventDefault();
              }}
            >
              <AlertDialogHeader>
                <AlertDialogTitle>لغو پردازش پایپ‌لاین؟</AlertDialogTitle>
                <AlertDialogDescription>
                  با لغو، پردازش جاری بلافاصله متوقف می‌شود و این جلسه دیگر قابل ادامه نیست.
                  برای تولید دوباره باید فایل را آپلود کرده و پردازش را از ابتدا شروع کنید.
                  این عمل قابل بازگشت نیست.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={isCancelling}>انصراف</AlertDialogCancel>
                <AlertDialogAction
                  disabled={isCancelling}
                  onClick={async (e) => {
                    e.preventDefault();
                    try {
                      await cancelPipeline();
                      setCancelDialogOpen(false);
                    } catch {
                      // toast already shown; keep the dialog open to retry.
                    }
                  }}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {isCancelling ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="ms-1.5">در حال لغو…</span>
                    </>
                  ) : (
                    'بله، لغو کن'
                  )}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        ) : currentIsTerminalSession ? (
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <Button
              type="button"
              className="h-11 w-full rounded-xl px-6 sm:w-auto"
              onClick={startNewDraft}
            >
              {newDraftLabel}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-11 w-full rounded-xl px-6 sm:w-auto"
              asChild
            >
              <Link href={destinationHref}>{destinationLabel}</Link>
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            className="h-11 w-full rounded-xl px-6 sm:w-auto"
            disabled={!currentCanSubmitNewPipeline}
            onClick={startFullPipeline}
          >
            {currentHasActiveEmbeddedExercises
              ? 'در حال ساخت تمرین‌ها…'
              : currentIsPipelineStarting || currentIsPipelineRunning
              ? 'در حال پردازش…'
              : 'ذخیره و پردازش'}
          </Button>
        )}
      </div>
    </div>
  );
}
