'use client';

/**
 * Teacher exercise manager for one class: list + create (upload) + extraction
 * polling + reference-answer/points editing + publish/delete + gradebook link.
 * Design: docs/features/exercise-hub.md.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Upload, Trash2, CheckCircle2, FileText, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { JalaliDateTimePicker } from '@/components/ui/jalali-date-time-picker';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
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
import { GradebookTable } from '@/components/teacher/exercises/gradebook-table';
import { ReferenceIngestPanel } from '@/components/teacher/exercises/reference-ingest-panel';
import { MathText } from '@/components/content/math-text';
import { formatPersianDateTime, toLocalDateTimeValue } from '@/lib/date-utils';
import {
  type ExerciseAnswerLayout,
  type ExerciseDetail,
  type ExerciseListItem,
  type ExerciseSourceRole,
  type ExerciseStatus,
  type ExerciseWritingMode,
  listExercises,
  createExercise,
  getExercise,
  extractExercise,
  publishExercise,
  deleteExercise,
  updateExercise,
  updateSection,
  updateQuestion,
  createQuestion,
  deleteQuestion,
} from '@/services/exercises-service';

const STATUS_LABEL: Record<ExerciseStatus, string> = {
  draft: 'پیش‌نویس',
  extracting: 'در حال استخراج',
  extracted: 'آمادهٔ ویرایش',
  published: 'منتشرشده',
  failed: 'خطا در استخراج',
};

const STATUS_VARIANT: Record<ExerciseStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  draft: 'outline',
  extracting: 'secondary',
  extracted: 'secondary',
  published: 'default',
  failed: 'destructive',
};

const ACTIVE_WORKFLOW_STAGES = new Set([
  'queued',
  'reading_sources',
  'ocr_and_transcription',
  'extracting_questions',
  'matching_reference_answers',
  'building_review_draft',
]);

const SOURCE_ROLE_OPTIONS: Array<{ value: ExerciseSourceRole; label: string }> = [
  { value: 'auto', label: 'تشخیص خودکار' },
  { value: 'question_only', label: 'فقط سوال' },
  { value: 'question_and_answer', label: 'سوال و پاسخ با هم' },
  { value: 'answer_only', label: 'فقط پاسخ‌نامه' },
];

const WRITING_MODE_OPTIONS: Array<{ value: ExerciseWritingMode; label: string }> = [
  { value: 'auto', label: 'تشخیص خودکار' },
  { value: 'typed', label: 'تایپی' },
  { value: 'handwritten', label: 'دست‌نویس' },
  { value: 'mixed', label: 'ترکیبی' },
];

const ANSWER_LAYOUT_OPTIONS: Array<{ value: ExerciseAnswerLayout; label: string }> = [
  { value: 'auto', label: 'تشخیص خودکار' },
  { value: 'inline', label: 'پاسخ زیر هر سوال' },
  { value: 'end', label: 'پاسخ‌ها در انتهای فایل' },
  { value: 'separate', label: 'پاسخ‌نامه جداگانه' },
];

type IntakeSourceDraft = {
  clientFileKey: string;
  file: File;
  role: ExerciseSourceRole;
  writingMode: ExerciseWritingMode;
  answerLayout: ExerciseAnswerLayout;
};

export function ExerciseManager({ sessionId }: { sessionId: number }) {
  const [exercises, setExercises] = useState<ExerciseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [noDeadline, setNoDeadline] = useState(true);
  const [deadline, setDeadline] = useState('');
  const [allowLate, setAllowLate] = useState(false);
  const [assistantEnabled, setAssistantEnabled] = useState(true);
  const [teacherNote, setTeacherNote] = useState('');
  const [sources, setSources] = useState<IntakeSourceDraft[]>([]);

  const addFiles = (nextFiles: File[]) => {
    setSources((prev) => [
      ...prev,
      ...nextFiles.map((file, index) => ({
        clientFileKey: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${index}-${Math.random()}`,
        file,
        role: 'auto' as ExerciseSourceRole,
        writingMode: 'auto' as ExerciseWritingMode,
        answerLayout: 'auto' as ExerciseAnswerLayout,
      })),
    ]);
  };

  const updateSource = <K extends keyof IntakeSourceDraft>(
    clientFileKey: string,
    field: K,
    value: IntakeSourceDraft[K]
  ) => {
    setSources((prev) =>
      prev.map((item) => (item.clientFileKey === clientFileKey ? { ...item, [field]: value } : item))
    );
  };

  const removeSource = (clientFileKey: string) => {
    setSources((prev) => prev.filter((item) => item.clientFileKey !== clientFileKey));
  };

  const refresh = useCallback(async () => {
    try {
      setExercises(await listExercises(sessionId));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در بارگذاری تمرین‌ها');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const anyProcessing = useMemo(
    () => exercises.some((e) => ACTIVE_WORKFLOW_STAGES.has(e.workflowStage)),
    [exercises]
  );

  // Poll while any exercise is still moving through the async draft-building stages.
  useEffect(() => {
    if (!anyProcessing) return;
    const id = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(id);
  }, [anyProcessing, refresh]);

  const handleCreate = async () => {
    if (!title.trim()) {
      toast.error('عنوان تمرین را وارد کنید.');
      return;
    }
    if (sources.length === 0) {
      toast.error('حداقل یک منبع برای ساخت تمرین لازم است.');
      return;
    }
    if (!noDeadline && !deadline) {
      toast.error('برای این تمرین باید مهلت ارسال را تعیین کنید.');
      return;
    }
    setCreating(true);
    try {
      await createExercise(sessionId, {
        title: title.trim(),
        no_deadline: noDeadline,
        deadline: noDeadline ? null : new Date(deadline).toISOString(),
        allow_late: allowLate,
        assistant_enabled: assistantEnabled,
        teacher_note: teacherNote.trim(),
        files: sources.map((item) => ({
          clientFileKey: item.clientFileKey,
          file: item.file,
        })),
        sources: sources.map((item) => ({
          clientFileKey: item.clientFileKey,
          role: item.role,
          writingMode: item.writingMode,
          answerLayout: item.answerLayout,
        })),
      });
      setTitle('');
      setNoDeadline(true);
      setDeadline('');
      setAllowLate(false);
      setAssistantEnabled(true);
      setTeacherNote('');
      setSources([]);
      toast.success('پیش‌نویس تمرین در صف ساخت قرار گرفت. پس از آماده‌شدن برای بازبینی به شما اطلاع می‌دهیم.');
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ساخت تمرین ناموفق بود.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div dir="rtl" className="space-y-6">
      {/* Create */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">ایجاد تمرین جدید</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="exercise-title">عنوان تمرین</Label>
              <Input
                id="exercise-title"
                placeholder="مثلاً: تمرین فصل سوم"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <div>
                  <p className="text-sm font-medium">بدون مهلت</p>
                  <p className="text-xs text-muted-foreground">
                    اگر خاموش باشد، تمرین با تاریخ و ساعت مشخص ساخته می‌شود.
                  </p>
                </div>
                <Switch checked={noDeadline} onCheckedChange={setNoDeadline} />
              </div>
              {!noDeadline && (
                <div className="space-y-2">
                  <Label htmlFor="exercise-deadline">مهلت ارسال</Label>
                  <JalaliDateTimePicker
                    id="exercise-deadline"
                    value={deadline}
                    onChange={setDeadline}
                  />
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <div>
                <p className="text-sm font-medium">اجازهٔ ارسال دیرهنگام</p>
                <p className="text-xs text-muted-foreground">
                  پاسخ‌های بعد از مهلت را نگه می‌داریم و با برچسب دیرهنگام مشخص می‌کنیم.
                </p>
              </div>
              <Switch checked={allowLate} onCheckedChange={setAllowLate} />
            </div>
            <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <div>
                <p className="text-sm font-medium">دستیار هوشمند</p>
                <p className="text-xs text-muted-foreground">
                  معلم می‌تواند همین حالا وضعیت پیش‌فرض دستیار را برای کل تمرین تعیین کند.
                </p>
              </div>
              <Switch checked={assistantEnabled} onCheckedChange={setAssistantEnabled} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="teacher-note">توضیح معلم</Label>
            <Textarea
              id="teacher-note"
              rows={3}
              placeholder="هر توضیحی که به تشخیص بهتر ساختار، پاسخ‌نامه یا بازبینی بعدی کمک می‌کند."
              value={teacherNote}
              onChange={(e) => setTeacherNote(e.target.value)}
            />
          </div>

          <div className="space-y-3 rounded-md border border-dashed border-border p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <p className="text-sm font-medium">منابع تمرین</p>
                <p className="text-xs leading-6 text-muted-foreground">
                  PDF یا عکس را یک‌جا بدهید. اگر لازم باشد، برای هر فایل فقط نقش و نوع آن را اصلاح می‌کنید.
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted">
                <Upload className="h-4 w-4" />
                <span>افزودن فایل</span>
                <input
                  type="file"
                  multiple
                  accept="application/pdf,image/*"
                  className="hidden"
                  onChange={(e) => {
                    addFiles(Array.from(e.target.files ?? []));
                    e.currentTarget.value = '';
                  }}
                />
              </label>
            </div>

            {sources.length === 0 ? (
              <p className="rounded-md bg-muted/40 px-3 py-4 text-sm text-muted-foreground">
                هنوز فایلی انتخاب نشده است.
              </p>
            ) : (
              <div className="space-y-3">
                {sources.map((source, index) => (
                  <div key={source.clientFileKey} className="space-y-3 rounded-md border border-border p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium">{source.file.name}</p>
                        <p className="text-xs text-muted-foreground">
                          منبع {index + 1} • {Math.max(1, Math.round(source.file.size / 1024))} کیلوبایت
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label="حذف منبع"
                        onClick={() => removeSource(source.clientFileKey)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                    <div className="grid gap-3 lg:grid-cols-3">
                      <div className="space-y-1">
                        <Label>نقش منبع</Label>
                        <Select
                          value={source.role}
                          onValueChange={(value) =>
                            updateSource(source.clientFileKey, 'role', value as ExerciseSourceRole)
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {SOURCE_ROLE_OPTIONS.map((option) => (
                              <SelectItem key={option.value} value={option.value}>
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label>نوع نوشتار</Label>
                        <Select
                          value={source.writingMode}
                          onValueChange={(value) =>
                            updateSource(source.clientFileKey, 'writingMode', value as ExerciseWritingMode)
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {WRITING_MODE_OPTIONS.map((option) => (
                              <SelectItem key={option.value} value={option.value}>
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label>چیدمان پاسخ‌ها</Label>
                        <Select
                          value={source.answerLayout}
                          onValueChange={(value) =>
                            updateSource(source.clientFileKey, 'answerLayout', value as ExerciseAnswerLayout)
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ANSWER_LAYOUT_OPTIONS.map((option) => (
                              <SelectItem key={option.value} value={option.value}>
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-muted/30 px-4 py-3">
            <p className="text-sm text-muted-foreground">
              بعد از زدن این دکمه، ساخت پیش‌نویس و استخراج سوال‌ها در پس‌زمینه انجام می‌شود و برای بازبینی به شما اطلاع می‌دهیم.
            </p>
            <Button onClick={handleCreate} disabled={creating}>
              {creating ? <Loader2 className="ms-2 h-4 w-4 animate-spin" /> : null}
              ساخت پیش‌نویس تمرین
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : exercises.length === 0 ? (
        <p className="rounded-md border border-dashed border-border py-10 text-center text-muted-foreground">
          هنوز تمرینی برای این کلاس نساخته‌اید. فایل‌ها را یک‌بار بارگذاری کنید تا پیش‌نویس تمرین برای بازبینی آماده شود.
        </p>
      ) : (
        <div className="space-y-4">
          {exercises.map((ex) => (
            <ExerciseCard key={ex.id} summary={ex} onChanged={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}

function ExerciseCard({
  summary,
  onChanged,
}: {
  summary: ExerciseListItem;
  onChanged: () => Promise<void>;
}) {
  const [detail, setDetail] = useState<ExerciseDetail | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showGradebook, setShowGradebook] = useState(false);
  const loadedFor = useRef<ExerciseStatus | null>(null);

  const loadDetail = useCallback(async () => {
    try {
      setDetail(await getExercise(summary.id));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در بارگذاری تمرین');
    }
  }, [summary.id]);

  useEffect(() => {
    if ((open || summary.status === 'extracted') && loadedFor.current !== summary.status) {
      loadedFor.current = summary.status;
      void loadDetail();
    }
  }, [open, summary.status, loadDetail]);

  const doExtract = async () => {
    setBusy(true);
    try {
      await extractExercise(summary.id);
      toast.info('استخراج دوباره در پس‌زمینه آغاز شد. بعد از آماده‌شدن می‌توانید بازبینی کنید.');
      await onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'استخراج ناموفق بود.');
    } finally {
      setBusy(false);
    }
  };

  const doPublish = async () => {
    setBusy(true);
    try {
      await publishExercise(summary.id);
      toast.success('تمرین منتشر شد و برای دانش‌آموزان کلاس قابل مشاهده است.');
      await onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'برای انتشار، هر سوال باید پاسخ مرجع و بارم داشته باشد.');
    } finally {
      setBusy(false);
    }
  };

  const doDelete = async () => {
    try {
      await deleteExercise(summary.id);
      toast.success('تمرین حذف شد.');
      await onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'حذف ناموفق بود.');
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">
            <MathText text={summary.title} />
          </CardTitle>
          <Badge variant={STATUS_VARIANT[summary.status]}>{STATUS_LABEL[summary.status]}</Badge>
        </div>
        <div className="flex items-center gap-2">
          {summary.status === 'failed' && (
            <Button size="sm" variant="secondary" onClick={doExtract} disabled={busy}>
              استخراج دوباره
            </Button>
          )}
          {(summary.status === 'extracted' || summary.status === 'published') && (
            <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>
              {open ? 'بستن' : summary.status === 'published' ? 'مشاهده و مدیریت' : 'بازبینی و انتشار'}
            </Button>
          )}
          {summary.status === 'published' && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowGradebook((v) => !v)}
            >
              کارنامهٔ کلاس
            </Button>
          )}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="icon" variant="ghost" aria-label="حذف">
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent dir="rtl">
              <AlertDialogHeader>
                <AlertDialogTitle>حذف تمرین</AlertDialogTitle>
                <AlertDialogDescription>
                  این تمرین و همهٔ پاسخ‌های ثبت‌شده برای آن حذف می‌شوند. مطمئن هستید؟
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>بازگشت</AlertDialogCancel>
                <AlertDialogAction onClick={doDelete}>حذف</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 pt-0">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>آخرین وضعیت: {summary.workflowMessage}</span>
          {summary.deadline ? (
            <Badge variant="outline">مهلت: {formatPersianDateTime(summary.deadline)}</Badge>
          ) : (
            <Badge variant="outline">بدون مهلت</Badge>
          )}
        </div>
        <Progress value={summary.progressPercent} className="h-2" />
        {summary.workflowWarnings.length > 0 && (
          <div className="rounded-md border border-amber-300/40 bg-amber-500/5 p-3 text-xs leading-6 text-amber-800 dark:text-amber-200">
            {summary.workflowWarnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        )}
      </CardContent>

      {open && detail && (
        <CardContent className="space-y-4">
          <ExerciseEditor detail={detail} onSaved={loadDetail} />
          <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
            <Button onClick={doPublish} disabled={busy}>
              {busy ? <Loader2 className="ms-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="ms-2 h-4 w-4" />}
              انتشار تمرین
            </Button>
          </div>
        </CardContent>
      )}

      {showGradebook && (
        <CardContent>
          <GradebookTable exerciseId={summary.id} />
        </CardContent>
      )}
    </Card>
  );
}

function ExerciseEditor({
  detail,
  onSaved,
}: {
  detail: ExerciseDetail;
  onSaved: () => Promise<void>;
}) {
  const [assistant, setAssistant] = useState(detail.assistantEnabled);
  const [deadline, setDeadline] = useState(toLocalDateTimeValue(detail.deadline));
  const allQuestions = useMemo(
    () =>
      detail.sections.flatMap((section) =>
        section.questions.map((question, index) => ({
          ...question,
          label: `${section.title || 'بخش بدون عنوان'} - سوال ${index + 1}`,
        }))
      ),
    [detail.sections]
  );

  const saveSettings = async () => {
    try {
      await updateExercise(detail.id, {
        assistant_enabled: assistant,
        deadline: deadline ? new Date(deadline).toISOString() : null,
      });
      toast.success('تنظیمات ذخیره شد.');
      await onSaved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ذخیرهٔ تنظیمات ناموفق بود.');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4 rounded-md bg-muted/40 p-3">
        <div className="flex items-center gap-2">
          <Switch checked={assistant} onCheckedChange={setAssistant} id={`asst-${detail.id}`} />
          <Label htmlFor={`asst-${detail.id}`}>دستیار هوشمند فعال باشد</Label>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor={`dl-${detail.id}`}>مهلت ارسال</Label>
          <JalaliDateTimePicker
            id={`dl-${detail.id}`}
            value={deadline}
            onChange={setDeadline}
            className="w-56"
          />
        </div>
        <Button variant="secondary" size="sm" onClick={saveSettings}>
          ذخیرهٔ تنظیمات
        </Button>
      </div>

      <ReferenceIngestPanel
        exerciseId={detail.id}
        questions={allQuestions}
        onApplied={onSaved}
      />

      <Accordion type="multiple" className="w-full">
        {detail.sections.map((section) => (
          <SectionEditor
            key={section.id}
            exerciseId={detail.id}
            section={section}
            onChanged={onSaved}
          />
        ))}
      </Accordion>
    </div>
  );
}

function SectionEditor({
  exerciseId,
  section,
  onChanged,
}: {
  exerciseId: number;
  section: ExerciseDetail['sections'][number];
  onChanged: () => Promise<void>;
}) {
  const [assistant, setAssistant] = useState(section.assistantEnabled);
  const [adding, setAdding] = useState(false);

  // Per-section assistant switch — AND-ed with the exercise-level flag server-side.
  const toggleAssistant = async (value: boolean) => {
    setAssistant(value);
    try {
      await updateSection(section.id, { assistant_enabled: value });
      toast.success(
        value ? 'دستیار برای این بخش فعال شد.' : 'دستیار برای این بخش غیرفعال شد.'
      );
    } catch (err) {
      setAssistant(!value); // revert optimistic update
      toast.error(err instanceof Error ? err.message : 'ذخیرهٔ تنظیم بخش ناموفق بود.');
    }
  };

  // Manual question entry — the fallback when extraction misses a question.
  const addQuestion = async () => {
    setAdding(true);
    try {
      await createQuestion(exerciseId, {
        section_id: section.id,
        question_markdown: 'متن سوال جدید را اینجا بنویسید.',
        max_points: 1,
      });
      toast.success('سوال جدید اضافه شد. متن، پاسخ مرجع و بارم آن را تکمیل کنید.');
      await onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'افزودن سوال ناموفق بود.');
    } finally {
      setAdding(false);
    }
  };

  return (
    <AccordionItem value={`s-${section.id}`}>
      <AccordionTrigger>
        <MathText text={section.title || 'بخش بدون عنوان'} />
      </AccordionTrigger>
      <AccordionContent className="space-y-4">
        <div className="flex items-center gap-2 rounded-md bg-muted/40 p-2">
          <Switch
            checked={assistant}
            onCheckedChange={toggleAssistant}
            id={`sec-asst-${section.id}`}
          />
          <Label htmlFor={`sec-asst-${section.id}`}>دستیار هوشمند برای این بخش</Label>
        </div>
        {section.questions.map((q) => (
          <QuestionEditor key={q.id} question={q} onChanged={onChanged} />
        ))}
        <Button size="sm" variant="outline" onClick={addQuestion} disabled={adding}>
          {adding ? (
            <Loader2 className="ms-2 h-4 w-4 animate-spin" />
          ) : (
            <Plus className="ms-2 h-4 w-4" />
          )}
          افزودن سوال
        </Button>
      </AccordionContent>
    </AccordionItem>
  );
}

function QuestionEditor({
  question,
  onChanged,
}: {
  question: ExerciseDetail['sections'][number]['questions'][number];
  onChanged: () => Promise<void>;
}) {
  const [text, setText] = useState(question.questionMarkdown);
  const [reference, setReference] = useState(question.referenceAnswerMarkdown);
  const [points, setPoints] = useState(question.maxPoints);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await updateQuestion(question.id, {
        question_markdown: text,
        reference_answer_markdown: reference,
        max_points: Number(points),
      });
      toast.success('سوال ذخیره شد.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ذخیره ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    try {
      await deleteQuestion(question.id);
      toast.success('سوال حذف شد.');
      await onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'حذف سوال ناموفق بود.');
    }
  };

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="flex items-start gap-2">
        <Textarea
          placeholder="متن سوال"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={2}
          className="text-sm font-medium"
        />
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button size="icon" variant="ghost" aria-label="حذف سوال">
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent dir="rtl">
            <AlertDialogHeader>
              <AlertDialogTitle>حذف سوال</AlertDialogTitle>
              <AlertDialogDescription>
                این سوال از تمرین حذف می‌شود. مطمئن هستید؟
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>بازگشت</AlertDialogCancel>
              <AlertDialogAction onClick={remove}>حذف</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
      <Textarea
        placeholder="پاسخ مرجع (مبنای نمره‌دهی)"
        value={reference}
        onChange={(e) => setReference(e.target.value)}
        rows={3}
      />
      <div className="flex items-center gap-2">
        <Label className="text-sm">بارم</Label>
        <Input
          type="number"
          min={0}
          step="0.25"
          value={points}
          onChange={(e) => setPoints(e.target.value)}
          className="w-24"
        />
        <Button size="sm" variant="secondary" onClick={save} disabled={saving} className="ms-auto">
          ذخیرهٔ سوال
        </Button>
      </div>
    </div>
  );
}
