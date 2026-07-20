'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  FileText,
  Loader2,
  Trash2,
  UploadCloud,
} from 'lucide-react';

import { LatexMarkdownEditor } from '@/components/exercises/latex-markdown-editor';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import type {
  AnswerOcrCandidate,
  AnswerOcrSource,
  StudentQuestion,
} from '@/services/exercises-service';

const PROCESSING = new Set(['queued', 'reading', 'segmenting', 'matching']);

function sourceCandidates(source: AnswerOcrSource): AnswerOcrCandidate[] {
  return [
    ...source.answers,
    ...source.unmatchedFragments.map((text) => ({
      question_id: null,
      text,
      match_status: 'unmatched' as const,
      unclear_parts: [],
    })),
  ];
}

export function AnswerSourceProgress({ source }: { source: AnswerOcrSource }) {
  const active = PROCESSING.has(source.status);
  return (
    <div className="space-y-2 rounded-md border border-border/70 bg-muted/20 p-3">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="inline-flex items-center gap-2 font-medium">
          {active && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
          {source.status === 'failed' && <AlertTriangle className="h-4 w-4 text-destructive" />}
          {(source.status === 'ready' || source.status === 'needs_review') && (
            <CheckCircle2 className="h-4 w-4 text-primary" />
          )}
          {source.workflowMessage || 'در انتظار پردازش'}
        </span>
        <span className="text-xs text-muted-foreground">{source.progressPercent}%</span>
      </div>
      <Progress value={source.progressPercent} className="h-1.5" />
    </div>
  );
}

type WholeAnswerOcrPanelProps = {
  source?: AnswerOcrSource;
  questions: StudentQuestion[];
  disabled?: boolean;
  busy?: boolean;
  onUpload: (files: File[]) => Promise<void>;
  onApply: (source: AnswerOcrSource, answers: AnswerOcrCandidate[]) => Promise<void>;
  onDeleteAsset: (assetId: number) => Promise<void>;
};

export function WholeAnswerOcrPanel({
  source,
  questions,
  disabled,
  busy,
  onUpload,
  onApply,
  onDeleteAsset,
}: WholeAnswerOcrPanelProps) {
  const [open, setOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [answers, setAnswers] = useState<AnswerOcrCandidate[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const loadedSourceRevisionRef = useRef('');

  useEffect(() => {
    if (!source) return;
    const sourceRevision = `${source.id}:${source.revision}`;
    if (loadedSourceRevisionRef.current === sourceRevision) return;
    loadedSourceRevisionRef.current = sourceRevision;
    setAnswers(sourceCandidates(source));
  }, [source]);

  const duplicateTargets = useMemo(() => {
    const ids = answers.map((answer) => answer.question_id).filter((id): id is number => id != null);
    return ids.some((id, index) => ids.indexOf(id) !== index);
  }, [answers]);

  const receiveFiles = (files: FileList | File[]) => {
    const next = Array.from(files).filter((file) => (
      file.type.startsWith('image/') || file.type === 'application/pdf'
    ));
    if (next.length) void onUpload(next);
  };

  const ready = source && (source.status === 'ready' || source.status === 'needs_review');

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-lg border border-border bg-card">
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center justify-between gap-4 px-4 py-4 text-right"
        >
          <span className="space-y-1">
            <span className="block font-semibold">ارسال پاسخ‌نامه دست‌نویس همه سؤال‌ها</span>
            <span className="block text-xs leading-5 text-muted-foreground">
              عکس‌ها یا PDF را یکجا بفرستید؛ متن هر پاسخ را پیش از اعمال بررسی می‌کنید.
            </span>
          </span>
          <span className="flex shrink-0 items-center gap-2">
            {source && <Badge variant="outline">{source.assets.length} فایل</Badge>}
            <ChevronDown className={cn('h-4 w-4 transition-transform', open && 'rotate-180')} />
          </span>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-4 border-t border-border px-4 py-4">
        {!disabled && (
          <button
            type="button"
            className={cn(
              'flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed p-5 text-center transition-colors',
              dragging ? 'border-primary bg-primary/10' : 'border-border bg-muted/10 hover:border-primary/60',
            )}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              receiveFiles(event.dataTransfer.files);
            }}
          >
            <UploadCloud className="h-7 w-7 text-primary" />
            <p className="text-sm font-medium">فایل‌ها را بکشید و رها کنید یا کلیک کنید</p>
            <p className="text-xs text-muted-foreground">عکس یا PDF، حداکثر ۲۰ صفحه و ۳۰ مگابایت</p>
          </button>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*,application/pdf"
          multiple
          className="hidden"
          onChange={(event) => {
            if (event.target.files) receiveFiles(event.target.files);
            event.target.value = '';
          }}
        />

        {source?.assets.length ? (
          <div className="flex flex-wrap gap-2">
            {source.assets.map((asset, index) => (
              <div key={asset.id} className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span>فایل {index + 1}</span>
                {!disabled && (
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6 text-destructive"
                    aria-label="حذف فایل"
                    onClick={() => void onDeleteAsset(asset.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        ) : null}

        {source && <AnswerSourceProgress source={source} />}

        {ready && (
          <div className="space-y-4">
            <div className="border-b border-border pb-2">
              <h3 className="font-semibold">بازبینی پاسخ‌های خوانده‌شده</h3>
              <p className="text-xs leading-5 text-muted-foreground">
                فقط خوانش دست‌خط را بررسی کنید. متن تایپی شما با این متن جایگزین نمی‌شود.
              </p>
            </div>
            {answers.map((answer, index) => (
              <div key={`${source.revision}-${index}`} className="space-y-3 rounded-md border border-border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-medium">پاسخ تشخیص‌داده‌شده {index + 1}</span>
                  <Select
                    value={answer.question_id != null ? String(answer.question_id) : 'unmatched'}
                    onValueChange={(value) => setAnswers((current) => current.map((item, itemIndex) => (
                      itemIndex === index
                        ? { ...item, question_id: value === 'unmatched' ? null : Number(value) }
                        : item
                    )))}
                  >
                    <SelectTrigger className="w-52"><SelectValue placeholder="سؤال مقصد" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unmatched">نیازمند انتخاب سؤال</SelectItem>
                      {questions.map((question, questionIndex) => (
                        <SelectItem key={question.id} value={String(question.id)}>
                          سؤال {questionIndex + 1}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <LatexMarkdownEditor
                  label="متن خوانده‌شده"
                  previewLabel="پیش‌نمایش پاسخ"
                  value={answer.text}
                  onChange={(value) => setAnswers((current) => current.map((item, itemIndex) => (
                    itemIndex === index ? { ...item, text: value } : item
                  )))}
                  placeholder="متن استخراج‌شده را بررسی و در صورت نیاز اصلاح کنید."
                  rows={5}
                />
                {answer.unclear_parts.length > 0 && (
                  <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs leading-6 text-amber-700 dark:text-amber-300">
                    <span className="font-semibold">این قسمت‌ها ممکن است دقیق خوانده نشده باشند:</span>
                    {answer.unclear_parts.map((part, partIndex) => (
                      <p key={partIndex}>{part.excerpt || 'بخشی از پاسخ'}: {part.reason || 'خوانایی پایین'}</p>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {duplicateTargets && (
              <p className="text-sm text-destructive">برای هر سؤال فقط یک پاسخ مقصد انتخاب کنید.</p>
            )}
            <Button
              type="button"
              disabled={busy || duplicateTargets || answers.some((answer) => answer.question_id == null)}
              onClick={() => source && void onApply(source, answers)}
            >
              {busy && <Loader2 className="ms-2 h-4 w-4 animate-spin" />}
              اعمال پاسخ‌های بازبینی‌شده
            </Button>
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}

export function QuestionAnswerOcrPreview({
  source,
  disabled,
  busy,
  onSave,
}: {
  source?: AnswerOcrSource;
  disabled?: boolean;
  busy?: boolean;
  onSave: (source: AnswerOcrSource, text: string) => Promise<void>;
}) {
  const [text, setText] = useState('');
  const answer = source?.answers[0];
  useEffect(() => setText(answer?.text ?? ''), [source?.revision, answer?.text]);
  if (!source) return null;

  const ready = source.status === 'ready' || source.status === 'needs_review';
  return (
    <div className="space-y-3">
      <AnswerSourceProgress source={source} />
      {ready && answer && (
        <div className="space-y-3">
          <LatexMarkdownEditor
            label="خوانش دست‌خط"
            previewLabel="پیش‌نمایش پاسخ خوانده‌شده"
            value={text}
            onChange={setText}
            placeholder="متن خوانده‌شده را بررسی کنید."
            rows={4}
          />
          {answer.unclear_parts.length > 0 && (
            <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs leading-6 text-amber-700 dark:text-amber-300">
              {answer.unclear_parts.map((part, index) => (
                <p key={index}>{part.excerpt || 'بخشی از پاسخ'}: {part.reason || 'خوانایی پایین'}</p>
              ))}
            </div>
          )}
          {!disabled && (
            <Button type="button" variant="outline" disabled={busy} onClick={() => void onSave(source, text)}>
              {busy && <Loader2 className="ms-2 h-4 w-4 animate-spin" />}
              ذخیره اصلاح خوانش
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
