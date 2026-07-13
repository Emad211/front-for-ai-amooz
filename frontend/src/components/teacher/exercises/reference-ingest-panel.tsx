'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { CheckCircle2, Loader2, Upload, Wand2 } from 'lucide-react';

import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
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
import { Textarea } from '@/components/ui/textarea';
import {
  applyReferenceIngest,
  previewReferenceIngest,
  type ExerciseDetail,
  type ReferenceIngestMode,
  type ReferenceIngestPreview,
  type ReferenceIngestPreviewItem,
} from '@/services/exercises-service';

type ReferenceIngestQuestion = ExerciseDetail['questions'][number] & {
  label: string;
};

export function ReferenceIngestPanel({
  exerciseId,
  questions,
  onApplied,
}: {
  exerciseId: number;
  questions: ReferenceIngestQuestion[];
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
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="w-full sm:w-auto">
          <Wand2 className="ms-2 h-4 w-4" />
          اصلاح گروهی از روی منبع
        </Button>
      </SheetTrigger>
      <SheetContent side="left" dir="rtl" className="flex h-full w-full flex-col overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>اصلاح گروهی پاسخ‌های مرجع</SheetTitle>
          <SheetDescription>
            متن یا فایل تکمیلی را وارد کنید. هیچ تغییری پیش از بازبینی و تایید شما اعمال نمی‌شود.
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
                پیش‌نمایش اصلاح
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
