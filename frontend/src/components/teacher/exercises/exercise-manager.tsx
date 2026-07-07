'use client';

/**
 * Teacher exercise manager for one class: list + create (upload) + extraction
 * polling + reference-answer/points editing + publish/delete + gradebook link.
 * Design: docs/features/exercise-hub.md.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Upload, Trash2, CheckCircle2, FileText, Plus, Wand2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Checkbox } from '@/components/ui/checkbox';
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
import { MathText } from '@/components/content/math-text';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import {
  type ExerciseDetail,
  type ExerciseListItem,
  type ExerciseStatus,
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
  previewReferenceIngest,
  applyReferenceIngest,
  type ReferenceIngestMode,
  type ReferenceIngestPreview,
  type ReferenceIngestPreviewItem,
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

export function ExerciseManager({ sessionId }: { sessionId: number }) {
  const [exercises, setExercises] = useState<ExerciseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [files, setFiles] = useState<File[]>([]);

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

  const anyExtracting = useMemo(
    () => exercises.some((e) => e.status === 'extracting'),
    [exercises]
  );

  // Poll while any exercise is extracting.
  useEffect(() => {
    if (!anyExtracting) return;
    const id = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(id);
  }, [anyExtracting, refresh]);

  const handleCreate = async () => {
    if (!title.trim()) {
      toast.error('عنوان تمرین را وارد کنید.');
      return;
    }
    setCreating(true);
    try {
      const created = await createExercise(sessionId, { title: title.trim(), files });
      setTitle('');
      setFiles([]);
      toast.success('تمرین ساخته شد. برای استخراج سوال‌ها، «استخراج سوال‌ها» را بزنید.');
      await refresh();
      if (files.length > 0) {
        await extractExercise(created.id);
        await refresh();
      }
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
        <CardContent className="space-y-3">
          <Input
            placeholder="عنوان تمرین"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground hover:bg-muted">
              <Upload className="h-4 w-4" />
              <span>بارگذاری فایل تمرین (PDF یا عکس)</span>
              <input
                type="file"
                multiple
                accept="application/pdf,image/*"
                className="hidden"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              />
            </label>
            {files.length > 0 && (
              <span className="text-sm text-muted-foreground">{files.length} فایل انتخاب شد</span>
            )}
            <Button onClick={handleCreate} disabled={creating}>
              {creating ? <Loader2 className="ms-2 h-4 w-4 animate-spin" /> : null}
              ایجاد تمرین جدید
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
          هنوز تمرینی برای این کلاس نساخته‌اید. اولین تمرین را با بارگذاری PDF یا عکس بسازید.
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
      toast.info('در حال استخراج سوال‌ها از فایل شما… این کار ممکن است چند دقیقه طول بکشد.');
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
          {(summary.status === 'draft' || summary.status === 'failed') && (
            <Button size="sm" variant="secondary" onClick={doExtract} disabled={busy}>
              استخراج سوال‌ها
            </Button>
          )}
          {(summary.status === 'extracted' || summary.status === 'published') && (
            <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>
              {open ? 'بستن' : 'ویرایش سوال‌ها'}
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
  const [deadline, setDeadline] = useState(detail.deadline ? detail.deadline.slice(0, 16) : '');
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
          <Input
            id={`dl-${detail.id}`}
            type="datetime-local"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
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

function ReferenceIngestPanel({
  exerciseId,
  questions,
  onApplied,
}: {
  exerciseId: number;
  questions: Array<ExerciseDetail['sections'][number]['questions'][number] & { label: string }>;
  onApplied: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [modeHint, setModeHint] = useState<ReferenceIngestMode>('auto');
  const [targetQuestion, setTargetQuestion] = useState('all');
  const [sourceText, setSourceText] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<ReferenceIngestPreview | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [replaceExisting, setReplaceExisting] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);

  const resetPreview = () => {
    setPreview(null);
    setSelected({});
    setReplaceExisting({});
  };

  const runPreview = async () => {
    if (!sourceText.trim() && files.length === 0) {
      toast.error('متن یا فایل پاسخ مرجع را وارد کنید.');
      return;
    }
    setBusy(true);
    try {
      const result = await previewReferenceIngest(exerciseId, {
        modeHint,
        sourceText,
        files,
        targetQuestionId: targetQuestion === 'all' ? null : Number(targetQuestion),
      });
      setPreview(result);
      const nextSelected: Record<string, boolean> = {};
      result.items.forEach((item) => {
        nextSelected[item.id] = item.matchStatus === 'matched' && item.targetQuestionId != null;
      });
      setSelected(nextSelected);
      setReplaceExisting({});
      if (result.counts.matched === 0) {
        toast.info('مورد قابل اعمال خودکار پیدا نشد. موارد مبهم را دستی بررسی کنید.');
      } else {
        toast.success('پیشنهادها آماده است. قبل از اعمال، موارد را بررسی کنید.');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'استخراج کامل نشد. دوباره تلاش کنید یا دستی وارد کنید.');
    } finally {
      setBusy(false);
    }
  };

  const applySelected = async () => {
    if (!preview) return;
    const items = preview.items
      .filter((item) => selected[item.id] && item.targetQuestionId != null)
      .map((item) => ({
        targetQuestionId: item.targetQuestionId as number,
        referenceAnswerMarkdown: item.referenceAnswerMarkdown,
        maxPoints: item.maxPoints,
        questionMarkdown: item.questionMarkdown,
        questionType: item.questionType,
        options: item.options,
        replaceExisting: replaceExisting[item.id] === true,
        replaceQuestionText: false,
      }));
    if (items.length === 0) {
      toast.error('هیچ مورد تاییدشده‌ای برای اعمال انتخاب نشده است.');
      return;
    }
    setBusy(true);
    try {
      const result = await applyReferenceIngest(exerciseId, items);
      toast.success(`${result.appliedCount} پاسخ مرجع اعمال شد.`);
      await onApplied();
      setOpen(false);
      setSourceText('');
      setFiles([]);
      resetPreview();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'اعمال پاسخ‌های مرجع ناموفق بود.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-md border border-border bg-background p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold">ورود سؤال و پاسخ مرجع</h3>
          <p className="max-w-3xl text-xs leading-6 text-muted-foreground">
            می‌توانید پاسخ‌نامهٔ جدا، عکس دست‌نویس، متن تایپ‌شده یا فایل شامل سؤال و پاسخ را بدهید.
            قبل از ذخیره، هر مورد برای بازبینی شما نمایش داده می‌شود.
          </p>
        </div>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="sm">
              <Wand2 className="ms-2 h-4 w-4" />
              استخراج سؤال‌ها و پاسخ‌های مرجع
            </Button>
          </SheetTrigger>
          <SheetContent side="left" dir="rtl" className="flex h-full w-full flex-col overflow-y-auto sm:max-w-2xl">
            <SheetHeader>
              <SheetTitle>استخراج سؤال و پاسخ مرجع</SheetTitle>
              <SheetDescription>
                منبع را وارد کنید؛ خروجی فقط پس از تایید شما روی سوال‌های تمرین اعمال می‌شود.
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-4 py-4">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <Label>نوع ورودی</Label>
                  <Select value={modeHint} onValueChange={(value) => {
                    setModeHint(value as ReferenceIngestMode);
                    resetPreview();
                  }}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">تشخیص خودکار</SelectItem>
                      <SelectItem value="full_qa">سؤال و پاسخ باهم</SelectItem>
                      <SelectItem value="single_qa">یک سؤال و یک پاسخ</SelectItem>
                      <SelectItem value="numbered_answers">فقط پاسخ‌های شماره‌دار</SelectItem>
                      <SelectItem value="answer_only">فقط یک پاسخ</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>سوال هدف</Label>
                  <Select value={targetQuestion} onValueChange={(value) => {
                    setTargetQuestion(value);
                    resetPreview();
                  }}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">تشخیص از بین همه سوال‌ها</SelectItem>
                      {questions.map((question) => (
                        <SelectItem key={question.id} value={String(question.id)}>
                          {question.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1">
                <Label htmlFor={`ref-source-${exerciseId}`}>متن پاسخ‌نامه یا توضیح معلم</Label>
                <Textarea
                  id={`ref-source-${exerciseId}`}
                  value={sourceText}
                  onChange={(event) => {
                    setSourceText(event.target.value);
                    resetPreview();
                  }}
                  rows={5}
                  placeholder="مثلاً: پاسخ سوال ۱: ... یا متن OCR/پاسخ مرجع را اینجا وارد کنید."
                />
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground hover:bg-muted">
                  <Upload className="h-4 w-4" />
                  <span>بارگذاری منبع تمرین یا پاسخ‌نامه (PDF یا عکس)</span>
                  <input
                    type="file"
                    multiple
                    accept="application/pdf,image/*"
                    className="hidden"
                    onChange={(event) => {
                      setFiles(Array.from(event.target.files ?? []));
                      resetPreview();
                    }}
                  />
                </label>
                {files.length > 0 && (
                  <span className="text-xs text-muted-foreground">{files.length} فایل انتخاب شد</span>
                )}
              </div>

              <Button onClick={runPreview} disabled={busy} variant="secondary">
                {busy ? <Loader2 className="ms-2 h-4 w-4 animate-spin" /> : <Wand2 className="ms-2 h-4 w-4" />}
                پیش‌نمایش استخراج
              </Button>

              {preview && (
                <ReferenceIngestPreviewList
                  preview={preview}
                  selected={selected}
                  replaceExisting={replaceExisting}
                  onSelectedChange={(id, value) => setSelected((prev) => ({ ...prev, [id]: value }))}
                  onReplaceChange={(id, value) => setReplaceExisting((prev) => ({ ...prev, [id]: value }))}
                />
              )}
            </div>

            <SheetFooter className="sticky bottom-0 mt-auto border-t border-border bg-background pt-3">
              <Button onClick={applySelected} disabled={busy || !preview}>
                {busy ? <Loader2 className="ms-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="ms-2 h-4 w-4" />}
                اعمال موارد تاییدشده
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </div>
    </div>
  );
}

function ReferenceIngestPreviewList({
  preview,
  selected,
  replaceExisting,
  onSelectedChange,
  onReplaceChange,
}: {
  preview: ReferenceIngestPreview;
  selected: Record<string, boolean>;
  replaceExisting: Record<string, boolean>;
  onSelectedChange: (id: string, value: boolean) => void;
  onReplaceChange: (id: string, value: boolean) => void;
}) {
  const statusLabel: Record<ReferenceIngestPreviewItem['matchStatus'], string> = {
    matched: 'قابل اعمال',
    ambiguous: 'نیازمند بررسی',
    unmatched: 'بدون تطبیق',
  };

  return (
    <div className="space-y-3">
      {preview.warnings.length > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs leading-6 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
          {preview.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">کل: {preview.counts.total}</Badge>
        <Badge variant="secondary">قابل اعمال: {preview.counts.matched}</Badge>
        <Badge variant="outline">نیازمند بررسی: {preview.counts.ambiguous}</Badge>
        <Badge variant="outline">بدون تطبیق: {preview.counts.unmatched}</Badge>
      </div>
      {preview.items.map((item) => {
        const selectable = item.matchStatus === 'matched' && item.targetQuestionId != null;
        return (
          <div key={item.id} className="space-y-2 rounded-md border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={selected[item.id] ?? false}
                  disabled={!selectable}
                  onCheckedChange={(value) => onSelectedChange(item.id, value === true)}
                  aria-label="انتخاب مورد برای اعمال"
                />
                <Badge variant={item.matchStatus === 'matched' ? 'secondary' : 'outline'}>
                  {statusLabel[item.matchStatus]}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  اطمینان: {Math.round((item.confidence ?? 0) * 100)}٪
                </span>
              </div>
              {item.targetQuestionLabel && (
                <span className="text-xs text-muted-foreground">{item.targetQuestionLabel}</span>
              )}
            </div>
            {item.referenceAnswerMarkdown ? (
              <div className="rounded-md bg-muted/40 p-2">
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  پاسخ مرجع؛ مبنای نمره‌دهی هوشمند
                </p>
                <MarkdownWithMath markdown={item.referenceAnswerMarkdown} />
              </div>
            ) : (
              <p className="text-xs text-destructive">پاسخ مرجع صریحی پیدا نشد.</p>
            )}
            {item.questionMarkdown && (
              <div className="rounded-md bg-muted/20 p-2">
                <p className="mb-1 text-xs font-medium text-muted-foreground">متن سوال استخراج‌شده</p>
                <MarkdownWithMath markdown={item.questionMarkdown} />
              </div>
            )}
            {item.notes && <p className="text-xs leading-6 text-muted-foreground">{item.notes}</p>}
            {item.hasExistingReference && selectable && (
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <Checkbox
                  checked={replaceExisting[item.id] ?? false}
                  onCheckedChange={(value) => onReplaceChange(item.id, value === true)}
                  aria-label="جایگزینی پاسخ مرجع موجود"
                />
                پاسخ مرجع موجود این سوال را جایگزین کن
              </label>
            )}
          </div>
        );
      })}
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
