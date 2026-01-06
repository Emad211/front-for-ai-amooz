'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { ClassInfoForm } from './class-info-form';
import { FileUploadSection } from './file-upload-section';
import { StudentInviteSection } from './student-invite-section';
import { Card } from '@/components/ui/card';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import {
  getClassCreationSessionDetail,
  type ClassCreationSessionDetail,
  listClassPrerequisites,
  publishClassCreationSession,
  runStep3Prerequisites,
  runStep4PrerequisiteTeaching,
  structureClassCreationStep2,
  transcribeClassCreationStep1,
  type ClassPrerequisite,
  type Step1TranscribeResponse,
  type Step2StructureResponse,
  updateClassCreationSession,
} from '@/services/classes-service';
import { StructuredContentView } from '@/components/teacher/class-detail/structured-content-view';

const ACTIVE_SESSION_STORAGE_KEY = 'ai_amooz_active_class_creation_session_id';

const PROCESSING_STATUSES = new Set(['transcribing', 'structuring', 'prereq_extracting', 'prereq_teaching']);

export function CreateClassPage() {
  const router = useRouter();
  const [expandedSections, setExpandedSections] = useState<string[]>(['info', 'files', 'exercises', 'students']);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [lessonFile, setLessonFile] = useState<File | null>(null);
  const [step1ClientRequestId, setStep1ClientRequestId] = useState<string | null>(null);
  const [step1Result, setStep1Result] = useState<Step1TranscribeResponse | null>(null);
  const [sessionDetail, setSessionDetail] = useState<ClassCreationSessionDetail | null>(null);
  const [step1Error, setStep1Error] = useState<string | null>(null);
  const [isStep1Loading, setIsStep1Loading] = useState(false);

  const [step2Result, setStep2Result] = useState<Step2StructureResponse | null>(null);
  const [step2Error, setStep2Error] = useState<string | null>(null);
  const [isStep2Loading, setIsStep2Loading] = useState(false);

  const [prereqs, setPrereqs] = useState<ClassPrerequisite[] | null>(null);
  const [prereqError, setPrereqError] = useState<string | null>(null);
  const [isPrereqLoading, setIsPrereqLoading] = useState(false);
  const [isStep3Loading, setIsStep3Loading] = useState(false);
  const [isStep4Loading, setIsStep4Loading] = useState(false);

  const pollTimer = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollTimer.current) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const startPolling = (sessionId: number) => {
    stopPolling();
    pollTimer.current = window.setInterval(async () => {
      try {
        const detail = await getClassCreationSessionDetail(sessionId);
        setSessionDetail(detail);

        // Keep top-level title/description in sync with server session.
        setTitle((prev) => prev || detail.title);
        setDescription((prev) => prev || detail.description);

        if (detail.status === 'failed') {
          stopPolling();
          setStep1Error(detail.error_detail || 'پردازش با خطا متوقف شد');
          return;
        }

        if (detail.status === 'transcribed' || detail.status === 'structuring' || detail.status === 'structured') {
          setStep1Result({
            id: detail.id,
            status: 'transcribed',
            title: detail.title,
            description: detail.description,
            source_mime_type: detail.source_mime_type,
            source_original_name: detail.source_original_name,
            transcript_markdown: detail.transcript_markdown,
            created_at: detail.created_at,
          });
        }

        if (String(detail.structure_json || '').trim()) {
          setStep2Result({
            id: detail.id,
            status: 'structured',
            title: detail.title,
            description: detail.description,
            structure_json: detail.structure_json,
            created_at: detail.created_at,
          });
        }

        if (!PROCESSING_STATUSES.has(detail.status)) {
          stopPolling();
          if (detail.status === 'prereq_extracted' || detail.status === 'prereq_taught' || detail.status === 'structured') {
            void refreshPrereqs(detail.id);
          }
        }
      } catch (e) {
        // Keep polling; network may be flaky.
      }
    }, 1500);
  };

  const refreshPrereqs = async (sessionId: number) => {
    setIsPrereqLoading(true);
    setPrereqError(null);
    try {
      const items = await listClassPrerequisites(sessionId);
      setPrereqs(items);
    } catch (e) {
      setPrereqs([]);
      setPrereqError(e instanceof Error ? e.message : 'خطا در بارگذاری پیش‌نیازها');
    } finally {
      setIsPrereqLoading(false);
    }
  };

  const resumeSession = async (sessionId: number) => {
    try {
      const detail = await getClassCreationSessionDetail(sessionId);
      setSessionDetail(detail);
      setTitle(detail.title);
      setDescription(detail.description);

      setStep1Result({
        id: detail.id,
        status: (detail.status === 'transcribing' ? 'transcribing' : detail.status === 'failed' ? 'failed' : 'transcribed') as Step1TranscribeResponse['status'],
        title: detail.title,
        description: detail.description,
        source_mime_type: detail.source_mime_type,
        source_original_name: detail.source_original_name,
        transcript_markdown: detail.transcript_markdown,
        created_at: detail.created_at,
      });

      if (String(detail.structure_json || '').trim()) {
        setStep2Result({
          id: detail.id,
          status: 'structured',
          title: detail.title,
          description: detail.description,
          structure_json: detail.structure_json,
          created_at: detail.created_at,
        });
      }

      await refreshPrereqs(detail.id);

      startPolling(sessionId);
    } catch {
      // If resume fails, don't block the page.
    }
  };

  useEffect(() => {
    // Resume active session if user navigated away.
    const stored = window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
    const sessionId = stored ? Number(stored) : NaN;
    if (Number.isFinite(sessionId)) {
      resumeSession(sessionId);
    }
    return () => stopPolling();
  }, []);

  const toggleSection = (section: string) => {
    setExpandedSections((prev) =>
      prev.includes(section) ? prev.filter((s) => s !== section) : [...prev, section]
    );
  };

  const canRunStep1 = Boolean(title.trim()) && Boolean(lessonFile) && !isStep1Loading;

  const runStep1 = async () => {
    if (!lessonFile) return;

    const clientRequestId = step1ClientRequestId ?? (globalThis.crypto?.randomUUID?.() ?? null);
    if (clientRequestId && clientRequestId !== step1ClientRequestId) {
      setStep1ClientRequestId(clientRequestId);
    }

    setIsStep1Loading(true);
    setStep1Error(null);
    setStep1Result(null);
    setStep2Error(null);
    setStep2Result(null);
    setPrereqs(null);
    setPrereqError(null);

    try {
      const result = await transcribeClassCreationStep1({
        title: title.trim(),
        description,
        file: lessonFile,
        clientRequestId: clientRequestId ?? undefined,
      });
      setStep1Result(result);
      setSessionDetail(null);
      window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(result.id));
      startPolling(result.id);
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'خطا در ارتباط با سرور';
      setStep1Error(
        msg +
          ' — نکته: اگر درخواست شبکه قطع شود، ممکن است پردازش در سرور ادامه داشته باشد؛ از روی «شناسه جلسه» می‌توان نتیجه را بعداً بررسی کرد.'
      );
    } finally {
      setIsStep1Loading(false);
    }
  };

  const sessionIdForActions = sessionDetail?.id ?? step1Result?.id ?? null;
  const canRunStep2 = Boolean(sessionIdForActions) && !isStep2Loading;

  const runStep2 = async () => {
    if (!sessionIdForActions) return;

    setIsStep2Loading(true);
    setStep2Error(null);
    setStep2Result(null);

    try {
      const result = await structureClassCreationStep2({ sessionId: sessionIdForActions });
      setStep2Result(result);
      window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(sessionIdForActions));
      startPolling(sessionIdForActions);
      await refreshPrereqs(sessionIdForActions);
    } catch (error) {
      setStep2Error(error instanceof Error ? error.message : 'خطا در ارتباط با سرور');
    } finally {
      setIsStep2Loading(false);
    }
  };

  const canRunStep3 = Boolean(sessionIdForActions) && Boolean(String(sessionDetail?.structure_json ?? step2Result?.structure_json ?? '').trim());
  const canRunStep4 = Boolean(sessionIdForActions) && Boolean(prereqs && prereqs.length > 0);

  const runStep3 = async () => {
    if (!sessionIdForActions) return;
    setIsStep3Loading(true);
    setPrereqError(null);
    try {
      await runStep3Prerequisites(sessionIdForActions);
      startPolling(sessionIdForActions);
      await refreshPrereqs(sessionIdForActions);
    } catch (e) {
      setPrereqError(e instanceof Error ? e.message : 'خطا در ساخت پیش‌نیازها');
    } finally {
      setIsStep3Loading(false);
    }
  };

  const runStep4 = async () => {
    if (!sessionIdForActions) return;
    setIsStep4Loading(true);
    setPrereqError(null);
    try {
      await runStep4PrerequisiteTeaching(sessionIdForActions);
      startPolling(sessionIdForActions);
      await refreshPrereqs(sessionIdForActions);
    } catch (e) {
      setPrereqError(e instanceof Error ? e.message : 'خطا در ساخت متن تدریس پیش‌نیازها');
    } finally {
      setIsStep4Loading(false);
    }
  };

  const publish = async () => {
    if (!sessionIdForActions) {
      toast.error('ابتدا مرحله ۱ را انجام دهید.');
      return;
    }
    if ((sessionDetail?.status ?? step1Result?.status) === 'failed') {
      toast.error('این جلسه با خطا متوقف شده است.');
      return;
    }

    try {
      await updateClassCreationSession(sessionIdForActions, {
        title: title.trim() || undefined,
        description,
      });
      await publishClassCreationSession(sessionIdForActions);

      window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
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
          setStep1Error(null);
          setStep1Result(null);
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
              disabled={!canRunStep1}
              onClick={runStep1}
            >
              {isStep1Loading ? 'در حال ارسال درخواست...' : 'شروع تبدیل به متن'}
            </Button>
          </div>

          {!title.trim() && (
            <div className="text-xs text-muted-foreground">برای شروع، ابتدا عنوان کلاس را وارد کنید.</div>
          )}

          {step1Error && (
            <div className="text-sm text-destructive">{step1Error}</div>
          )}

          {(step1Result || sessionDetail) && (
            <div className="space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-xs text-muted-foreground">
                <span>شناسه جلسه: {sessionIdForActions ?? '—'}</span>
                <span>وضعیت: {sessionDetail?.status ?? step1Result?.status ?? '—'}</span>
              </div>

              {(sessionDetail?.status === 'transcribing' || step1Result?.status === 'transcribing') && (
                <div className="text-xs text-muted-foreground">
                  در حال پردازش مرحله ۱… خروجی به محض آماده شدن همین‌جا نمایش داده می‌شود.
                </div>
              )}

              <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[60vh] overflow-y-auto">
                <MarkdownWithMath markdown={sessionDetail?.transcript_markdown ?? step1Result?.transcript_markdown ?? ''} />
              </div>

              <div className="pt-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <Button
                  type="button"
                  className="rounded-xl h-10 px-5"
                  disabled={!canRunStep2}
                  onClick={runStep2}
                >
                  {isStep2Loading ? 'در حال ساختاردهی...' : 'مرحله ۲: ساختاردهی محتوا'}
                </Button>
                <div className="text-xs text-muted-foreground">
                  خروجی مرحله ۲ به شکل Markdown نمایش داده می‌شود.
                </div>
              </div>

              {sessionDetail?.status === 'structuring' && (
                <div className="text-xs text-muted-foreground">
                  مرحله ۲ در حال پردازش است… خروجی به محض آماده شدن نمایش داده می‌شود.
                </div>
              )}

              {step2Error && <div className="text-sm text-destructive">{step2Error}</div>}

              {step2Result && (
                <div className="rounded-xl border border-border/60 bg-background/80 p-4">
                  <div className="max-h-[70vh] overflow-y-auto pr-1">
                    <StructuredContentView structureJson={sessionDetail?.structure_json ?? step2Result.structure_json ?? ''} />
                  </div>

                  <div className="mt-6 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-bold">پیش‌نیازها (مرحله ۳ و ۴)</div>
                      <div className="flex items-center gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={runStep3}
                          disabled={!canRunStep3 || isStep3Loading || isStep4Loading}
                        >
                          {isStep3Loading ? 'در حال ساخت…' : 'ساخت پیش‌نیازها'}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={runStep4}
                          disabled={!canRunStep4 || isStep3Loading || isStep4Loading}
                        >
                          {isStep4Loading ? 'در حال ساخت…' : 'ساخت متن تدریس'}
                        </Button>
                      </div>
                    </div>

                    {prereqError && <div className="text-sm text-destructive">{prereqError}</div>}

                    {prereqs === null || isPrereqLoading ? (
                      <div className="text-xs text-muted-foreground">در حال بارگذاری…</div>
                    ) : prereqs.length === 0 ? (
                      <div className="text-xs text-muted-foreground">—</div>
                    ) : (
                      <div className="space-y-3">
                        {prereqs
                          .slice()
                          .sort((a, b) => a.order - b.order)
                          .map((p) => (
                            <div key={p.id} className="rounded-2xl border border-border/60 bg-background/80 p-4 space-y-2">
                              <div className="text-sm font-black">{p.order}. {p.name}</div>
                              {p.teaching_text?.trim() ? (
                                <div className="max-h-[45vh] overflow-y-auto pr-1">
                                  <MarkdownWithMath markdown={p.teaching_text} />
                                </div>
                              ) : (
                                <div className="text-xs text-muted-foreground">(متن تدریس هنوز ساخته نشده است.)</div>
                              )}
                            </div>
                          ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </FileUploadSection>

      <FileUploadSection
        title="بارگذاری تمرین"
        description="اختیاری"
        icon="exercise"
        type="exercise"
        isExpanded={expandedSections.includes('exercises')}
        onToggle={() => toggleSection('exercises')}
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
          disabled={!sessionIdForActions}
          onClick={publish}
          type="button"
        >
          ذخیره و انتشار
        </Button>
      </div>
    </div>
  );
}
