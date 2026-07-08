'use client';

import { Trash2, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { JalaliDateTimePicker } from '@/components/ui/jalali-date-time-picker';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

import type {
  ExerciseAnswerLayout,
  ExerciseSourceRole,
  ExerciseWritingMode,
} from '@/services/exercises-service';

export type ExerciseIntakeSourceDraft = {
  clientFileKey: string;
  file: File;
  role: ExerciseSourceRole;
  writingMode: ExerciseWritingMode;
  answerLayout: ExerciseAnswerLayout;
};

export type ExerciseIntakeDraft = {
  clientExerciseKey: string;
  title: string;
  noDeadline: boolean;
  deadline: string;
  allowLate: boolean;
  assistantEnabled: boolean;
  teacherNote: string;
  sources: ExerciseIntakeSourceDraft[];
};

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

type ExerciseIntakeFormProps = {
  value: ExerciseIntakeDraft;
  onChange: (next: ExerciseIntakeDraft) => void;
  disabled?: boolean;
  compact?: boolean;
  submitLabel?: string;
  submitting?: boolean;
  onSubmit?: () => void;
};

export function buildEmptyExerciseIntakeDraft(): ExerciseIntakeDraft {
  return {
    clientExerciseKey: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`,
    title: '',
    noDeadline: true,
    deadline: '',
    allowLate: false,
    assistantEnabled: true,
    teacherNote: '',
    sources: [],
  };
}

export function ExerciseIntakeForm({
  value,
  onChange,
  disabled = false,
  compact = false,
  submitLabel,
  submitting = false,
  onSubmit,
}: ExerciseIntakeFormProps) {
  const setField = <K extends keyof ExerciseIntakeDraft>(field: K, fieldValue: ExerciseIntakeDraft[K]) => {
    onChange({ ...value, [field]: fieldValue });
  };

  const addFiles = (nextFiles: File[]) => {
    const sources = [
      ...value.sources,
      ...nextFiles.map((file, index) => ({
        clientFileKey: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${index}-${Math.random()}`,
        file,
        role: 'auto' as ExerciseSourceRole,
        writingMode: 'auto' as ExerciseWritingMode,
        answerLayout: 'auto' as ExerciseAnswerLayout,
      })),
    ];
    setField('sources', sources);
  };

  const updateSource = <K extends keyof ExerciseIntakeSourceDraft>(
    clientFileKey: string,
    field: K,
    fieldValue: ExerciseIntakeSourceDraft[K],
  ) => {
    setField(
      'sources',
      value.sources.map((source) =>
        source.clientFileKey === clientFileKey ? { ...source, [field]: fieldValue } : source,
      ),
    );
  };

  const removeSource = (clientFileKey: string) => {
    setField(
      'sources',
      value.sources.filter((source) => source.clientFileKey !== clientFileKey),
    );
  };

  return (
    <div className="space-y-5" dir="rtl">
      <div className="space-y-4 rounded-2xl border border-border/70 bg-muted/15 p-4">
        <div className="space-y-2">
          <Label htmlFor={`exercise-title-${value.clientExerciseKey}`}>عنوان تمرین</Label>
          <Input
            id={`exercise-title-${value.clientExerciseKey}`}
            placeholder="مثلاً: تمرین فصل سوم"
            value={value.title}
            disabled={disabled}
            onChange={(event) => setField('title', event.target.value)}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="flex items-center justify-between rounded-xl border border-border bg-background/70 px-3 py-2.5">
            <div>
              <p className="text-sm font-medium">بدون مهلت</p>
              <p className="text-xs text-muted-foreground">
                اگر خاموش باشد، تمرین با تاریخ و ساعت مشخص ساخته می‌شود.
              </p>
            </div>
            <Switch checked={value.noDeadline} disabled={disabled} onCheckedChange={(checked) => setField('noDeadline', checked)} />
          </div>
          <div className="flex items-center justify-between rounded-xl border border-border bg-background/70 px-3 py-2.5">
            <div>
              <p className="text-sm font-medium">اجازهٔ ارسال دیرهنگام</p>
              <p className="text-xs text-muted-foreground">
                پاسخ‌های بعد از مهلت را نگه می‌داریم و با برچسب دیرهنگام مشخص می‌کنیم.
              </p>
            </div>
            <Switch checked={value.allowLate} disabled={disabled} onCheckedChange={(checked) => setField('allowLate', checked)} />
          </div>
        </div>

        {!value.noDeadline ? (
          <div className="space-y-2">
            <Label htmlFor={`exercise-deadline-${value.clientExerciseKey}`}>مهلت ارسال</Label>
            <JalaliDateTimePicker
              id={`exercise-deadline-${value.clientExerciseKey}`}
              value={value.deadline}
              onChange={(next) => setField('deadline', next)}
              disabled={disabled}
            />
          </div>
        ) : null}

        <div className="flex items-center justify-between rounded-xl border border-border bg-background/70 px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">دستیار هوشمند</p>
            <p className="text-xs text-muted-foreground">
              وضعیت پیش‌فرض دستیار برای این تمرین از همین‌جا تعیین می‌شود.
            </p>
          </div>
          <Switch checked={value.assistantEnabled} disabled={disabled} onCheckedChange={(checked) => setField('assistantEnabled', checked)} />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor={`exercise-note-${value.clientExerciseKey}`}>توضیح معلم</Label>
        <Textarea
          id={`exercise-note-${value.clientExerciseKey}`}
          rows={compact ? 2 : 3}
          placeholder="هر توضیحی که به تشخیص بهتر ساختار، پاسخ‌نامه یا بازبینی بعدی کمک می‌کند."
          value={value.teacherNote}
          disabled={disabled}
          onChange={(event) => setField('teacherNote', event.target.value)}
        />
      </div>

      <div className="space-y-3 rounded-2xl border border-dashed border-border p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <p className="text-sm font-medium">منابع تمرین</p>
            <p className="text-xs leading-6 text-muted-foreground">
              PDF یا عکس را یک‌جا بدهید. اگر لازم باشد، برای هر فایل فقط نقش و نوع آن را اصلاح می‌کنید.
            </p>
          </div>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted">
            <Upload className="h-4 w-4" />
            <span>افزودن فایل</span>
            <input
              type="file"
              multiple
              accept="application/pdf,image/*"
              className="hidden"
              disabled={disabled}
              onChange={(event) => {
                addFiles(Array.from(event.target.files ?? []));
                event.currentTarget.value = '';
              }}
            />
          </label>
        </div>

        {value.sources.length === 0 ? (
          <p className="rounded-xl bg-muted/40 px-3 py-4 text-sm text-muted-foreground">
            هنوز فایلی انتخاب نشده است.
          </p>
        ) : (
          <div className="space-y-3">
            {value.sources.map((source, index) => (
              <div key={source.clientFileKey} className="space-y-3 rounded-xl border border-border p-3">
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
                    disabled={disabled}
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
                      disabled={disabled}
                      onValueChange={(next) => updateSource(source.clientFileKey, 'role', next as ExerciseSourceRole)}
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
                      disabled={disabled}
                      onValueChange={(next) => updateSource(source.clientFileKey, 'writingMode', next as ExerciseWritingMode)}
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
                      disabled={disabled}
                      onValueChange={(next) => updateSource(source.clientFileKey, 'answerLayout', next as ExerciseAnswerLayout)}
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

      {onSubmit && submitLabel ? (
        <div className="flex justify-end">
          <Button type="button" disabled={disabled || submitting} onClick={onSubmit}>
            {submitting ? 'در حال ثبت…' : submitLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
