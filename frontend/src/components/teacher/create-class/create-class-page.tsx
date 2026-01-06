'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { ClassInfoForm } from './class-info-form';
import { FileUploadSection } from './file-upload-section';
import { StudentInviteSection } from './student-invite-section';
import { Card } from '@/components/ui/card';
import {
  getClassCreationSessionDetail,
  type ClassCreationSessionDetail,
  publishClassCreationSession,
  transcribeClassCreationStep1,
  updateClassCreationSession,
} from '@/services/classes-service';

const ACTIVE_SESSION_STORAGE_KEY = 'ai_amooz_active_class_creation_session_id';
const CREATE_CLASS_DRAFT_STORAGE_KEY = 'ai_amooz_create_class_draft_v1';
const CREATE_CLASS_LAST_STATUS_STORAGE_KEY = 'ai_amooz_create_class_last_status_v1';

const PROCESSING_STATUSES = new Set([
  'transcribing',
  'structuring',
  'prereq_extracting',
  'prereq_teaching',
  'recapping',
]);

function getPipelineMessage(status?: string | null) {
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

export function CreateClassPage() {
  const router = useRouter();
  const [expandedSections, setExpandedSections] = useState<string[]>(['info', 'files', 'exercises', 'students']);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [lessonFile, setLessonFile] = useState<File | null>(null);
  const [step1ClientRequestId, setStep1ClientRequestId] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [sessionDetail, setSessionDetail] = useState<ClassCreationSessionDetail | null>(null);
  const [optimisticStatus, setOptimisticStatus] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [isPipelineStarting, setIsPipelineStarting] = useState(false);

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

      if (detail.status !== 'failed' && detail.status !== 'recapped') {
        startPolling(sessionId);
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
      loadDraft();
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

  const sessionIdForActions = sessionDetail?.id ?? activeSessionId ?? null;
  const status = sessionDetail?.status ?? optimisticStatus ?? null;
  const { message: pipelineMessage, isDone: isPipelineDone, isFailed: isPipelineFailed } = getPipelineMessage(status);
  const isPipelineRunning = Boolean(status && PROCESSING_STATUSES.has(status));
  const canStartPipeline = Boolean(title.trim()) && Boolean(lessonFile) && !isPipelineStarting && !isPipelineRunning;

  const startFullPipeline = async () => {
    if (!lessonFile) return;

    const clientRequestId = step1ClientRequestId ?? (globalThis.crypto?.randomUUID?.() ?? null);
    if (clientRequestId && clientRequestId !== step1ClientRequestId) {
      setStep1ClientRequestId(clientRequestId);
    }

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
  };

  const publish = async () => {
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
  };

  return (
    <div className="space-y-8" dir="rtl">
      <Card className="relative overflow-hidden border-border/40 bg-gradient-to-l from-primary/10 via-background to-background rounded-3xl shadow-xl shadow-primary/5">
        <div className="absolute inset-y-0 left-0 w-40 bg-primary/10 blur-3xl" />
        <div className="relative p-6 sm:p-8 flex flex-col gap-3">
          <div className="flex items-center gap-3 text-primary">
            <span className="h-10 w-10 rounded-2xl bg-primary/10 flex items-center justify-center font-black text-lg">+</span>
            <p className="text-sm text-primary">مسیر ساخت کلاس</p>
          </div>
          <div className="flex flex-col gap-2">
            <h1 className="text-2xl md:text-3xl font-black text-foreground">ایجاد کلاس جدید</h1>
            <p className="text-muted-foreground text-sm md:text-base">اطلاعات را تکمیل کنید، فایل‌ها را بارگذاری کنید و با کد دعوت دانش‌آموزان را اضافه کنید.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs md:text-sm text-muted-foreground">
            <span className="px-3 py-1 rounded-full bg-primary/10 text-primary">۱. اطلاعات کلاس</span>
            <span className="px-3 py-1 rounded-full bg-muted">۲. فایل‌ها و تمرین‌ها</span>
            <span className="px-3 py-1 rounded-full bg-muted">۳. دعوت دانش‌آموزان</span>
          </div>
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
        title="بارگذاری فایل درسی"
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
          setPipelineError(null);
          stopPolling();
          setSessionDetail(null);
          setActiveSessionId(null);
          window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
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
              disabled={!canStartPipeline}
              onClick={startFullPipeline}
            >
              {isPipelineStarting || isPipelineRunning ? 'در حال اجرای پایپ‌لاین…' : 'اجرای کامل پایپ‌لاین (۱ تا ۵)'}
            </Button>
          </div>

          {!title.trim() && (
            <div className="text-xs text-muted-foreground">برای شروع، ابتدا عنوان کلاس را وارد کنید.</div>
          )}

          {pipelineError && <div className="text-sm text-destructive">{pipelineError}</div>}

          {sessionIdForActions && (
            <div className="space-y-1">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-xs text-muted-foreground">
                <span>شناسه جلسه: {sessionIdForActions}</span>
                <span>وضعیت: {status ?? '—'}</span>
              </div>
              {pipelineMessage && (
                <div className={isPipelineFailed ? 'text-sm text-destructive' : 'text-xs text-muted-foreground'}>
                  {pipelineMessage}
                </div>
              )}
              {isPipelineDone && (
                <div className="text-xs text-muted-foreground">پایپ‌لاین کامل شد.</div>
              )}
            </div>
          )}
        </div>
      </FileUploadSection>

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

      <StudentInviteSection
        isExpanded={expandedSections.includes('students')}
        onToggle={() => toggleSection('students')}
        sessionId={sessionIdForActions}
      />

      <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-4">
        <Button variant="outline" className="w-full sm:w-auto rounded-xl h-11 px-6">
          انصراف
        </Button>
        <Button
          className="w-full sm:w-auto bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl h-11 px-8"
          disabled={!sessionIdForActions || sessionDetail?.status !== 'recapped'}
          onClick={publish}
          type="button"
        >
          ذخیره و انتشار
        </Button>
      </div>
    </div>
  );
}
