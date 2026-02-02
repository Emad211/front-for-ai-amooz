'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ClassInfoForm } from './class-info-form';
import { FileUploadSection } from './file-upload-section';
import { StudentInviteSection } from './student-invite-section';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  getClassCreationSessionDetail,
  type ClassCreationSessionDetail,
  publishClassCreationSession,
  transcribeClassCreationStep1,
  updateClassCreationSession,
  // Exam Prep imports
  transcribeExamPrepStep1,
  fetchExamPrepSession,
  publishExamPrepSession,
  type ExamPrepSessionDetail,
  type ExamPrepStatus,
} from '@/services/classes-service';

type PipelineType = 'class' | 'exam_prep';

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
      return { message: `وضعیت: ${status}`, isDone: false, isFailed: false } as const;
  }
}

function getExamPrepPipelineMessage(status?: string | null) {
  if (!status) {
    return { message: null, isDone: false, isFailed: false } as const;
  }
  if (status === 'failed') {
    return { message: 'پردازش با خطا متوقف شد.', isDone: false, isFailed: true } as const;
  }
  switch (status) {
    case 'exam_transcribing':
      return { message: 'در حال انجام مرحله ۱ از ۳ (ترنسکریپت)…', isDone: false, isFailed: false } as const;
    case 'exam_transcribed':
      return { message: 'مرحله ۱ از ۳ تمام شد.', isDone: false, isFailed: false } as const;
    case 'exam_structuring':
      return { message: 'در حال انجام مرحله ۲ از ۳ (استخراج سوالات)…', isDone: false, isFailed: false } as const;
    case 'exam_structured':
      return { message: 'مرحله ۲ از ۳ تمام شد. اکنون می‌توانید دانش‌آموزان را دعوت کنید.', isDone: true, isFailed: false } as const;
    default:
      return { message: `وضعیت: ${status}`, isDone: false, isFailed: false } as const;
  }
}

export function CreateClassPage() {
  const router = useRouter();
  const [pipelineType, setPipelineType] = useState<PipelineType>('class');
  const [expandedSections, setExpandedSections] = useState<string[]>(['info', 'files', 'exercises', 'students']);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [level, setLevel] = useState<string>('');
  const [duration, setDuration] = useState<string>('');
  const [lessonFile, setLessonFile] = useState<File | null>(null);
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

  const pollTimer = useRef<number | null>(null);
  const pollFailures = useRef<number>(0);

  const loadDraft = () => {
    try {
      const raw = window.localStorage.getItem(CREATE_CLASS_DRAFT_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { title?: string; description?: string };
      if (typeof parsed.title === 'string' && parsed.title) setTitle((prev) => prev || (parsed.title as string));
      if (typeof parsed.description === 'string' && parsed.description) setDescription((prev) => prev || (parsed.description as string));
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
      window.clearInterval(pollTimer.current);
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

        if (detail?.status) {
          persistLastStatus({ sessionId: detail.id, status: detail.status });
        }

        setTitle((prev) => prev || detail.title);
        setDescription((prev) => prev || detail.description);
        setLevel((prev) => prev || String((detail as any).level || '').trim());
        setDuration((prev) => prev || String((detail as any).duration || '').trim());

        if (detail.status === 'failed') {
          stopPolling();
          setPipelineError(detail.error_detail || 'پردازش با خطا متوقف شد');
          return;
        }

        if (detail.status === 'recapped') {
          stopPolling();
        }
      } catch {
        pollFailures.current += 1;
        if (pollFailures.current >= 4) {
          setPipelineError('ارتباط با سرور برای دریافت وضعیت پایپ‌لاین برقرار نشد.');
        }
      }
    };

    void tick();
    pollTimer.current = window.setInterval(() => void tick(), 1500);
  };

  const resumeSession = async (sessionId: number) => {
    try {
      const detail = await getClassCreationSessionDetail(sessionId);
      pollFailures.current = 0;
      setOptimisticStatus(null);
      setSessionDetail(detail);
      setActiveSessionId(detail.id);
      setTitle(detail.title);
      setDescription(detail.description);
      setLevel(String((detail as any).level || '').trim());
      setDuration(String((detail as any).duration || '').trim());

      if (detail.status !== 'failed' && detail.status !== 'recapped') {
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
        setDescription((prev) => prev || detail.description);

        if (detail.status === 'failed') {
          stopPolling();
          setExamPrepPipelineError(detail.error_detail || 'پردازش با خطا متوقف شد');
          return;
        }

        if (detail.status === 'exam_structured') {
          stopPolling();
        }
      } catch {
        pollFailures.current += 1;
        if (pollFailures.current >= 4) {
          setExamPrepPipelineError('ارتباط با سرور برای دریافت وضعیت پایپ‌لاین برقرار نشد.');
        }
      }
    };

    void tick();
    pollTimer.current = window.setInterval(() => void tick(), 1500);
  };

  const resumeExamPrepSession = async (sessionId: number) => {
    try {
      const detail = await fetchExamPrepSession(sessionId);
      pollFailures.current = 0;
      setExamPrepOptimisticStatus(null);
      setExamPrepSessionDetail(detail);
      setActiveExamPrepSessionId(detail.id);
      setTitle(detail.title);
      setDescription(detail.description);

      if (detail.status !== 'failed' && detail.status !== 'exam_structured') {
        startExamPrepPolling(sessionId);
      }
    } catch {
      // If resume fails, don't block the page.
    }
  };

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
    persistDraft({ title, description });
  }, [title, description]);

  const toggleSection = (section: string) => {
    setExpandedSections((prev) =>
      prev.includes(section) ? prev.filter((s) => s !== section) : [...prev, section]
    );
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
  const currentPipelineMessage = pipelineType === 'class' ? classPipelineMessage : examPrepPipelineMessage;
  const currentIsPipelineDone = pipelineType === 'class' ? isClassPipelineDone : isExamPrepPipelineDone;
  const currentIsPipelineFailed = pipelineType === 'class' ? isClassPipelineFailed : isExamPrepPipelineFailed;
  const currentPipelineError = pipelineType === 'class' ? pipelineError : examPrepPipelineError;
  const currentIsPipelineRunning = pipelineType === 'class' ? isClassPipelineRunning : isExamPrepPipelineRunning;
  const currentCanStartPipeline = pipelineType === 'class' ? canStartClassPipeline : canStartExamPrepPipeline;
  const currentIsPipelineStarting = pipelineType === 'class' ? isPipelineStarting : isExamPrepPipelineStarting;
  const currentStatus = pipelineType === 'class' ? status : examPrepStatus;

  const startFullPipeline = async () => {
    if (!lessonFile) return;

    const clientRequestId = step1ClientRequestId ?? (globalThis.crypto?.randomUUID?.() ?? null);
    if (clientRequestId && clientRequestId !== step1ClientRequestId) {
      setStep1ClientRequestId(clientRequestId);
    }

    if (pipelineType === 'class') {
      setIsPipelineStarting(true);
      setPipelineError(null);
      pollFailures.current = 0;
      setOptimisticStatus(null);
      stopPolling();
      setSessionDetail(null);
      setActiveSessionId(null);

      try {
        const result = await transcribeClassCreationStep1({
          title: title.trim(),
          description,
          file: lessonFile,
          clientRequestId: clientRequestId ?? undefined,
          runFullPipeline: true,
        });
        setOptimisticStatus(result.status);
        setActiveSessionId(result.id);
        window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(result.id));
        persistLastStatus({ sessionId: result.id, status: result.status });
        startPolling(result.id);
      } catch (error) {
        const msg = error instanceof Error ? error.message : 'خطا در ارتباط با سرور';
        setPipelineError(msg);
      } finally {
        setIsPipelineStarting(false);
      }
    } else {
      // Exam Prep Pipeline
      setIsExamPrepPipelineStarting(true);
      setExamPrepPipelineError(null);
      pollFailures.current = 0;
      setExamPrepOptimisticStatus(null);
      stopPolling();
      setExamPrepSessionDetail(null);
      setActiveExamPrepSessionId(null);

      try {
        const result = await transcribeExamPrepStep1({
          title: title.trim(),
          description,
          file: lessonFile,
          clientRequestId: clientRequestId ?? undefined,
          runFullPipeline: true,
        });
        setExamPrepOptimisticStatus(result.status);
        setActiveExamPrepSessionId(result.id);
        window.localStorage.setItem(ACTIVE_EXAM_PREP_SESSION_STORAGE_KEY, String(result.id));
        try {
          window.localStorage.setItem(CREATE_EXAM_PREP_LAST_STATUS_STORAGE_KEY, JSON.stringify({ sessionId: result.id, status: result.status }));
        } catch { /* ignore */ }
        startExamPrepPolling(result.id);
      } catch (error) {
        const msg = error instanceof Error ? error.message : 'خطا در ارتباط با سرور';
        setExamPrepPipelineError(msg);
      } finally {
        setIsExamPrepPipelineStarting(false);
      }
    }
  };

  const publish = async () => {
    if (pipelineType === 'class') {
      if (!sessionIdForActions) {
        toast.error('ابتدا مرحله ۱ را انجام دهید.');
        return;
      }
      if (sessionDetail?.status === 'failed') {
        toast.error('این جلسه با خطا متوقف شده است.');
        return;
      }
      if (sessionDetail?.status !== 'recapped') {
        toast.error('ابتدا پایپ‌لاین را تا مرحله ۵ کامل کنید.');
        return;
      }

      try {
        await updateClassCreationSession(sessionIdForActions, {
          title: title.trim() || undefined,
          description,
          level: level.trim() || undefined,
          duration: duration.trim() || undefined,
        });
        await publishClassCreationSession(sessionIdForActions);

        window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
        window.localStorage.removeItem(CREATE_CLASS_DRAFT_STORAGE_KEY);
        window.localStorage.removeItem(CREATE_CLASS_LAST_STATUS_STORAGE_KEY);
        toast.success('کلاس با موفقیت منتشر شد');
        router.push(`/teacher/my-classes/${sessionIdForActions}`);
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'خطا در انتشار کلاس';
        toast.error(msg);
      }
    } else {
      // Exam Prep Pipeline
      if (!examPrepSessionIdForActions) {
        toast.error('ابتدا مرحله ۱ را انجام دهید.');
        return;
      }
      if (examPrepSessionDetail?.status === 'failed') {
        toast.error('این جلسه با خطا متوقف شده است.');
        return;
      }
      if (examPrepSessionDetail?.status !== 'exam_structured') {
        toast.error('ابتدا پایپ‌لاین را تا مرحله ۲ کامل کنید.');
        return;
      }

      try {
        await publishExamPrepSession(examPrepSessionIdForActions);

        window.localStorage.removeItem(ACTIVE_EXAM_PREP_SESSION_STORAGE_KEY);
        window.localStorage.removeItem(CREATE_EXAM_PREP_DRAFT_STORAGE_KEY);
        window.localStorage.removeItem(CREATE_EXAM_PREP_LAST_STATUS_STORAGE_KEY);
        toast.success('آمادگی آزمون با موفقیت منتشر شد');
        router.push(`/teacher/my-classes/${examPrepSessionIdForActions}`);
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'خطا در انتشار';
        toast.error(msg);
      }
    }
  };

  return (
    <div className="space-y-8" dir="rtl">
      <Card className="relative overflow-hidden border-border/40 bg-gradient-to-l from-primary/10 via-background to-background rounded-3xl shadow-xl shadow-primary/5">
        <div className="absolute inset-y-0 left-0 w-40 bg-primary/10 blur-3xl" />
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
                ? 'اطلاعات را تکمیل کنید، فایل‌ها را بارگذاری کنید و با کد دعوت دانش‌آموزان را اضافه کنید.'
                : 'فایل صوتی یا ویدیویی حل تست‌ها را بارگذاری کنید تا سوالات و پاسخ‌ها استخراج شوند.'}
            </p>
          </div>
          {pipelineType === 'class' ? (
            <div className="flex flex-wrap gap-2 text-xs md:text-sm text-muted-foreground">
              <span className={cn("px-3 py-1 rounded-full", !status ? "bg-primary/10 text-primary" : "bg-muted")}>۱. اطلاعات کلاس</span>
              <span className={cn("px-3 py-1 rounded-full", (status && status !== 'recapped') ? "bg-primary/10 text-primary" : "bg-muted")}>۲. فایل‌ها و تمرین‌ها</span>
              <span className={cn("px-3 py-1 rounded-full", status === 'recapped' ? "bg-primary/10 text-primary" : "bg-muted")}>۳. دعوت دانش‌آموزان</span>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2 text-xs md:text-sm text-muted-foreground">
              <span className={cn("px-3 py-1 rounded-full", (!examPrepStatus || examPrepStatus.includes('trans')) ? "bg-primary/10 text-primary" : "bg-muted")}>۱. ترنسکریپت</span>
              <span className={cn("px-3 py-1 rounded-full", examPrepStatus === 'exam_structuring' ? "bg-primary/10 text-primary" : "bg-muted")}>۲. استخراج سوالات</span>
              <span className={cn("px-3 py-1 rounded-full", examPrepStatus === 'exam_structured' ? "bg-primary/10 text-primary" : "bg-muted")}>۳. دعوت دانش‌آموزان</span>
            </div>
          )}
        </div>
      </Card>

      {/* Pipeline Type Selector */}
      <Card className="p-4 sm:p-5 rounded-3xl border-border/40">
        <div className="space-y-3">
          <Label className="text-sm font-semibold">نوع پایپ‌لاین</Label>
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

      <ClassInfoForm
        isExpanded={expandedSections.includes('info')}
        onToggle={() => toggleSection('info')}
        title={title}
        description={description}
        onTitleChange={setTitle}
        onDescriptionChange={setDescription}
      />

      <FileUploadSection
        title={pipelineType === 'class' ? 'بارگذاری فایل درسی' : 'بارگذاری فایل حل تست'}
        icon="upload"
        type="lesson"
        isExpanded={expandedSections.includes('files')}
        onToggle={() => toggleSection('files')}
        accept="audio/*,video/*"
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
              {lessonFile ? `فایل انتخاب‌شده: ${lessonFile.name}` : 'یک فایل صوتی یا ویدیویی انتخاب کنید.'}
            </div>
            <Button
              type="button"
              className="rounded-xl h-10 px-5"
              disabled={!currentCanStartPipeline}
              onClick={startFullPipeline}
            >
              {currentIsPipelineStarting || currentIsPipelineRunning
                ? 'در حال اجرای پایپ‌لاین…'
                : pipelineType === 'class'
                  ? 'اجرای کامل پایپ‌لاین (۱ تا ۵)'
                  : 'اجرای کامل پایپ‌لاین (۱ تا ۳)'}
            </Button>
          </div>

          {!title.trim() && (
            <div className="text-xs text-muted-foreground">
              {pipelineType === 'class' ? 'برای شروع، ابتدا عنوان کلاس را وارد کنید.' : 'برای شروع، ابتدا عنوان را وارد کنید.'}
            </div>
          )}

          {currentPipelineError && <div className="text-sm text-destructive">{currentPipelineError}</div>}

          {currentSessionId && (
            <div className="space-y-1">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-xs text-muted-foreground">
                <span>شناسه جلسه: {currentSessionId}</span>
                <span>وضعیت: {currentStatus ?? '—'}</span>
              </div>
              {currentPipelineMessage && (
                <div className={currentIsPipelineFailed ? 'text-sm text-destructive' : 'text-xs text-muted-foreground'}>
                  {currentPipelineMessage}
                </div>
              )}
              {currentIsPipelineDone && (
                <div className="text-xs text-muted-foreground">پایپ‌لاین کامل شد.</div>
              )}
            </div>
          )}
        </div>
      </FileUploadSection>

      {/* Only show exercise section for class pipeline */}
      {pipelineType === 'class' && (
        <FileUploadSection
          title="بارگذاری تمرین"
          description="اختیاری"
          badgeText="کامینگ سون"
          icon="exercise"
          type="exercise"
          isExpanded={expandedSections.includes('exercises')}
          onToggle={() => toggleSection('exercises')}
          disabled
        />
      )}

      {/* Student invite section for both pipelines */}
      <StudentInviteSection
        isExpanded={expandedSections.includes('students')}
        onToggle={() => toggleSection('students')}
        sessionId={currentSessionId}
        pipelineType={pipelineType}
      />

      {/* Only show level/duration for class pipeline */}
      {pipelineType === 'class' && (
        <Card className="p-4 sm:p-5 rounded-3xl border-border/40">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5" dir="rtl">
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

      <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-4">
        <Button variant="outline" className="w-full sm:w-auto rounded-xl h-11 px-6">
          انصراف
        </Button>
        <Button
          className="w-full sm:w-auto bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl h-11 px-8"
          disabled={
            pipelineType === 'class'
              ? !sessionIdForActions || sessionDetail?.status !== 'recapped'
              : !examPrepSessionIdForActions || examPrepSessionDetail?.status !== 'exam_structured'
          }
          onClick={publish}
          type="button"
        >
          ذخیره و انتشار
        </Button>
      </div>
    </div>
  );
}
