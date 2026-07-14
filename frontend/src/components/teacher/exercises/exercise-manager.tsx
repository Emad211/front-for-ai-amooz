'use client';

/**
 * Teacher exercise manager for one class: list + create (upload) + extraction
 * polling + reference-answer/points editing + publish/delete + gradebook link.
 * Design: docs/features/exercise-hub.md.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Upload, Trash2, CheckCircle2, FileText, Plus, Ban, Save, Settings2, ChevronDown, NotebookPen } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { JalaliDateTimePicker } from '@/components/ui/jalali-date-time-picker';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import {
  buildEmptyExerciseIntakeDraft,
  ExerciseIntakeForm,
  type ExerciseIntakeDraft,
} from '@/components/teacher/exercises/exercise-intake-form';
import { ReferenceIngestPanel } from '@/components/teacher/exercises/reference-ingest-panel';
import { LatexMarkdownEditor } from '@/components/teacher/exercises/latex-markdown-editor';
import {
  ACTIVE_EXERCISE_WORKFLOW_STAGES,
  ExerciseWorkflowTracker,
} from '@/components/teacher/exercises/exercise-workflow-tracker';
import { MathText } from '@/components/content/math-text';
import { formatPersianDateTime, toLocalDateTimeValue } from '@/lib/date-utils';
import {
  type ExerciseDetail,
  type ExerciseListItem,
  type ExerciseStatus,
  listExercises,
  createExercise,
  getExercise,
  extractExercise,
  cancelExerciseExtraction,
  publishExercise,
  deleteExercise,
  updateExercise,
  updateQuestion,
  createQuestion,
  deleteQuestion,
} from '@/services/exercises-service';

const STATUS_LABEL: Record<ExerciseStatus, string> = {
  draft: 'پیش‌نویس',
  extracting: 'در حال استخراج',
  extracted: 'آمادهٔ ویرایش',
  published: 'منتشرشده',
  cancelled: 'متوقف‌شده',
  failed: 'خطا در استخراج',
};

const STATUS_VARIANT: Record<ExerciseStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  draft: 'outline',
  extracting: 'secondary',
  extracted: 'secondary',
  published: 'default',
  cancelled: 'outline',
  failed: 'destructive',
};

export function ExerciseManager({
  sessionId,
  classIsPublished,
}: {
  sessionId: number;
  classIsPublished: boolean;
}) {
  const [exercises, setExercises] = useState<ExerciseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [draft, setDraft] = useState<ExerciseIntakeDraft>(buildEmptyExerciseIntakeDraft);

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
    () => exercises.some((e) => ACTIVE_EXERCISE_WORKFLOW_STAGES.has(e.workflowStage)),
    [exercises]
  );

  // Poll while any exercise is still moving through the async draft-building stages.
  useEffect(() => {
    if (!anyProcessing) return;
    const id = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(id);
  }, [anyProcessing, refresh]);

  const handleCreate = async () => {
    if (!draft.title.trim()) {
      toast.error('عنوان تمرین را وارد کنید.');
      return;
    }
    if (draft.sources.length === 0) {
      toast.error('حداقل یک منبع برای ساخت تمرین لازم است.');
      return;
    }
    if (!draft.noDeadline && !draft.deadline) {
      toast.error('برای این تمرین باید مهلت ارسال را تعیین کنید.');
      return;
    }
    if (!draft.noDeadline && new Date(draft.deadline).getTime() <= Date.now()) {
      toast.error('مهلت ارسال باید زمانی در آینده باشد.');
      return;
    }
    setCreating(true);
    try {
      await createExercise(sessionId, {
        title: draft.title.trim(),
        no_deadline: draft.noDeadline,
        deadline: draft.noDeadline ? null : new Date(draft.deadline).toISOString(),
        allow_late: !draft.noDeadline && draft.allowLate,
        assistant_enabled: draft.assistantEnabled,
        teacher_note: draft.teacherNote.trim(),
        files: draft.sources.map((item) => ({
          clientFileKey: item.clientFileKey,
          file: item.file,
        })),
        sources: draft.sources.map((item) => ({
          clientFileKey: item.clientFileKey,
          role: item.role,
          writingMode: item.writingMode,
          answerLayout: item.answerLayout,
        })),
      });
      setDraft(buildEmptyExerciseIntakeDraft());
      setCreateOpen(false);
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
      <Card className="overflow-hidden border-border/60 bg-card/70">
        <CardHeader className="p-0">
          <button
            type="button"
            className="flex w-full items-center justify-between gap-3 px-6 py-5 text-start transition-colors hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
            aria-expanded={createOpen}
            aria-controls="create-exercise-content"
            onClick={() => setCreateOpen((current) => !current)}
          >
            <span className="flex min-w-0 items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <NotebookPen className="h-5 w-5" />
              </span>
              <span className="min-w-0 space-y-1">
                <span className="block text-base font-semibold leading-none tracking-tight sm:text-lg">ایجاد تمرین جدید</span>
                <span className="block text-xs font-normal leading-5 text-muted-foreground">
                  فایل‌ها و تنظیمات تمرین را یک‌بار ثبت کنید؛ ساخت پیش‌نویس در پس‌زمینه انجام می‌شود.
                </span>
              </span>
            </span>
            <ChevronDown
              className={`h-5 w-5 shrink-0 text-muted-foreground transition-transform duration-200 ${createOpen ? 'rotate-180' : ''}`}
            />
          </button>
        </CardHeader>
        <CardContent
          id="create-exercise-content"
          hidden={!createOpen}
          className="space-y-5 border-t border-border/50 pt-5"
        >
          <ExerciseIntakeForm
            value={draft}
            onChange={setDraft}
            disabled={creating}
            submitLabel="ساخت پیش‌نویس تمرین"
            submitting={creating}
            onSubmit={handleCreate}
          />
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
            <ExerciseCard
              key={ex.id}
              summary={ex}
              classIsPublished={classIsPublished}
              onChanged={refresh}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ExerciseCard({
  summary,
  classIsPublished,
  onChanged,
}: {
  summary: ExerciseListItem;
  classIsPublished: boolean;
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
    if (!classIsPublished) {
      toast.error('ابتدا خود کلاس را منتشر کنید؛ بعد از آن می‌توانید تمرین را منتشر کنید.');
      return;
    }
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

  const doCancel = async () => {
    setBusy(true);
    try {
      await cancelExerciseExtraction(summary.id);
      toast.success('استخراج تمرین متوقف شد.');
      await onChanged();
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'لغو استخراج ناموفق بود.');
    } finally {
      setBusy(false);
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
          {ACTIVE_EXERCISE_WORKFLOW_STAGES.has(summary.workflowStage) && (
            <Button size="sm" variant="outline" onClick={doCancel} disabled={busy}>
              {busy ? <Loader2 className="ms-2 h-4 w-4 animate-spin" /> : <Ban className="ms-2 h-4 w-4" />}
              لغو استخراج
            </Button>
          )}
          {(summary.status === 'failed' || summary.status === 'cancelled') && (
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
          {summary.deadline ? (
            <Badge variant="outline">مهلت: {formatPersianDateTime(summary.deadline)}</Badge>
          ) : (
            <Badge variant="outline">بدون مهلت</Badge>
          )}
        </div>
        <ExerciseWorkflowTracker
          workflowStage={summary.workflowStage}
          workflowMessage={summary.workflowMessage}
          progressPercent={summary.progressPercent}
          workflowWarnings={summary.workflowWarnings}
          readyForReview={summary.readyForReview}
          exerciseStatus={summary.status}
        />
      </CardContent>

      {open && detail && (
        <CardContent className="space-y-4">
          <ExerciseEditor detail={detail} onSaved={loadDetail} />
          <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
            <Button
              onClick={doPublish}
              disabled={busy || !classIsPublished}
              title={!classIsPublished ? 'ابتدا خود کلاس را منتشر کنید.' : undefined}
            >
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
  const [deadline, setDeadline] = useState(toLocalDateTimeValue(detail.deadline));
  const [assistantEnabled, setAssistantEnabled] = useState(detail.assistantEnabled);
  const [savingSettings, setSavingSettings] = useState(false);
  const [adding, setAdding] = useState(false);
  const allQuestions = detail.questions.map((question, index) => ({
    ...question,
    label: `سوال ${index + 1}`,
  }));

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      const payload: Parameters<typeof updateExercise>[1] = {
        assistant_enabled: assistantEnabled,
      };
      if (deadline !== toLocalDateTimeValue(detail.deadline)) {
        payload.deadline = deadline ? new Date(deadline).toISOString() : null;
      }
      await updateExercise(detail.id, payload);
      toast.success('تنظیمات ذخیره شد.');
      await onSaved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ذخیرهٔ تنظیمات ناموفق بود.');
    } finally {
      setSavingSettings(false);
    }
  };

  const addQuestion = async () => {
    setAdding(true);
    try {
      await createQuestion(detail.id, {
        question_markdown: 'متن سوال جدید را اینجا بنویسید.',
        max_points: 1,
      });
      toast.success('سوال جدید اضافه شد. متن، پاسخ مرجع و بارم آن را تکمیل کنید.');
      await onSaved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'افزودن سوال ناموفق بود.');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="space-y-4">
      <section className="overflow-hidden rounded-xl border border-border/70 bg-muted/20">
        <div className="flex items-center gap-3 border-b border-border/60 px-4 py-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Settings2 className="h-4 w-4" />
          </span>
          <div>
            <h3 className="text-sm font-semibold">تنظیمات قابل تغییر</h3>
            <p className="text-xs leading-5 text-muted-foreground">
              زمان تحویل و دستیار حل تمرین را هر زمان لازم بود تغییر دهید.
            </p>
          </div>
        </div>

        <div className="grid gap-3 p-4 lg:grid-cols-2">
          <div className="flex min-h-20 items-center justify-between gap-4 rounded-lg border border-border/60 bg-background/70 px-4 py-3">
            <div className="space-y-1">
              <Label htmlFor={`asst-${detail.id}`} className="text-sm font-medium">
                دستیار حل تمرین
              </Label>
              <p className="text-xs leading-5 text-muted-foreground">
                دانش‌آموز می‌تواند هنگام حل سؤال‌ها از دستیار هوشمند راهنمایی بگیرد.
              </p>
            </div>
            <Switch
              id={`asst-${detail.id}`}
              checked={assistantEnabled}
              onCheckedChange={setAssistantEnabled}
              disabled={savingSettings}
              aria-label="فعال یا غیرفعال کردن دستیار حل تمرین"
            />
          </div>

          <div className="min-h-20 space-y-2 rounded-lg border border-border/60 bg-background/70 px-4 py-3">
            <div className="space-y-1">
              <p className="text-sm font-medium">زمان تحویل تمرین</p>
              <p className="text-xs leading-5 text-muted-foreground">
                تاریخ و ساعت پایان دریافت پاسخ‌ها را مشخص کنید.
              </p>
            </div>
            <JalaliDateTimePicker
              id={`dl-${detail.id}`}
              value={deadline}
              onChange={setDeadline}
              className="w-full"
            />
          </div>
        </div>

        <div className="flex justify-end border-t border-border/60 px-4 py-3">
          <Button size="sm" onClick={saveSettings} disabled={savingSettings}>
            {savingSettings ? (
              <Loader2 className="ms-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="ms-2 h-4 w-4" />
            )}
            ذخیره تنظیمات
          </Button>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex flex-col gap-3 border-b border-border/60 pb-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold">سوال‌ها و پاسخ‌های مرجع</h3>
            <p className="text-xs leading-5 text-muted-foreground">
              متن سوال، پاسخ مرجع و بارم هر سوال را بازبینی و ویرایش کنید.
            </p>
          </div>
          <ReferenceIngestPanel
            exerciseId={detail.id}
            questions={allQuestions}
            onApplied={onSaved}
          />
        </div>

        {detail.questions.map((question, index) => (
          <div key={question.id} className="space-y-2">
            <p className="text-sm font-semibold text-muted-foreground">سوال {index + 1}</p>
            <QuestionEditor question={question} onChanged={onSaved} />
          </div>
        ))}
        <Button size="sm" variant="outline" onClick={addQuestion} disabled={adding}>
          {adding ? (
            <Loader2 className="ms-2 h-4 w-4 animate-spin" />
          ) : (
            <Plus className="ms-2 h-4 w-4" />
          )}
          افزودن سوال
        </Button>
      </section>
    </div>
  );
}

function QuestionEditor({
  question,
  onChanged,
}: {
  question: ExerciseDetail['questions'][number];
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
        <LatexMarkdownEditor
          label="متن سوال"
          previewLabel="پیش‌نمایش سوال"
          placeholder="متن سوال را بنویسید یا با کیبورد ریاضی فرمول اضافه کنید."
          value={text}
          onChange={setText}
          rows={3}
          className="min-w-0 flex-1"
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
      <LatexMarkdownEditor
        label="پاسخ مرجع"
        previewLabel="پیش‌نمایش پاسخ مرجع"
        placeholder="پاسخ مرجع را بنویسید؛ این پاسخ مبنای نمره‌دهی است."
        value={reference}
        onChange={setReference}
        rows={4}
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
