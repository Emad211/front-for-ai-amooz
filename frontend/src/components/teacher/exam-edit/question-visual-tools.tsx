'use client';

import { useRef, useState } from 'react';
import { ImagePlus, Loader2, Trash2, UploadCloud } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ProtectedExamVisual } from '@/components/exam-prep/protected-exam-visual';
import {
  resolveExamVisualUrl,
  type ExamVisualRefLike,
} from '@/lib/exam-visuals';
import {
  uploadExamPrepTeacherVisual,
  type ExamPrepTeacherVisual,
  type ExamPrepTeacherVisualRole,
} from '@/services/classes-service';

const ACCEPTED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

const ROLE_OPTIONS: Array<{ value: ExamPrepTeacherVisualRole; label: string }> = [
  { value: 'question', label: 'صورت سؤال' },
  { value: 'option', label: 'گزینه' },
  { value: 'solution', label: 'پاسخ تشریحی' },
];

function isAcceptedImageType(type: string): boolean {
  return ACCEPTED_IMAGE_TYPES.includes(type.toLocaleLowerCase());
}

interface TeacherVisualCardProps {
  visual: ExamVisualRefLike;
  sessionId: number;
  alt: string;
  className?: string;
  removable?: boolean;
  disabled?: boolean;
  onRemove?: (visualId: string | number) => void;
}

/**
 * Renders one exam visual exactly like the read-only path (ProtectedExamVisual
 * + resolved URL) unless it is a teacher-added visual that may be removed, in
 * which case a trash button is overlaid.
 */
export function TeacherVisualCard({
  visual,
  sessionId,
  alt,
  className,
  removable = false,
  disabled = false,
  onRemove,
}: TeacherVisualCardProps) {
  const url = resolveExamVisualUrl(visual, sessionId);
  if (!url) return null;

  const image = <ProtectedExamVisual url={url} alt={alt} className={className} />;
  if (!removable) return image;

  return (
    <div className="relative">
      {image}
      <Button
        type="button"
        variant="outline"
        size="icon"
        disabled={disabled}
        onClick={() => onRemove?.(visual.id)}
        aria-label="حذف تصویر افزوده‌شده"
        title="حذف تصویر افزوده‌شده"
        className="absolute left-2 top-2 z-10 h-8 w-8 rounded-full border-border/60 bg-background/95 text-destructive shadow-sm hover:bg-destructive hover:text-destructive-foreground"
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

interface QuestionVisualUploaderProps {
  sessionId: number;
  questionId: string;
  optionLabels: string[];
  disabled?: boolean;
  onUploadStateChange?: (uploading: boolean) => void;
  onVisualUploaded: (visual: ExamPrepTeacherVisual) => void;
}

/**
 * Upload control for one question: pick where the image attaches (question
 * stem / option / solution), pick the option when needed, then upload the file.
 */
export function QuestionVisualUploader({
  sessionId,
  questionId,
  optionLabels,
  disabled = false,
  onUploadStateChange,
  onVisualUploaded,
}: QuestionVisualUploaderProps) {
  const [role, setRole] = useState<ExamPrepTeacherVisualRole>('question');
  const [optionLabel, setOptionLabel] = useState<string>(optionLabels[0] ?? '');
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const blocked = disabled || uploading;
  const selectableRoles = ROLE_OPTIONS.filter(
    (item) => item.value !== 'option' || optionLabels.length > 0,
  );

  const runUpload = async (file: File) => {
    if (!isAcceptedImageType(file.type)) {
      setError('فرمت تصویر باید PNG، JPG یا WebP باشد.');
      return;
    }
    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      setError('حجم تصویر باید حداکثر ۵ مگابایت باشد.');
      return;
    }

    setError(null);
    setUploading(true);
    onUploadStateChange?.(true);
    try {
      const result = await uploadExamPrepTeacherVisual(sessionId, {
        questionId,
        role,
        optionLabel: role === 'option' ? optionLabel : null,
        file,
      });
      onVisualUploaded(result.visual);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'بارگذاری تصویر انجام نشد.');
    } finally {
      setUploading(false);
      onUploadStateChange?.(false);
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) void runUpload(file);
  };

  const selectRole = (value: string) => {
    const next = value as ExamPrepTeacherVisualRole;
    setRole(next);
    if (next === 'option' && !optionLabel && optionLabels[0]) {
      setOptionLabel(optionLabels[0]);
    }
  };

  return (
    <div className="space-y-3 rounded-xl border border-dashed border-border/70 bg-muted/10 p-4">
      <p className="flex items-center gap-2 text-sm font-bold">
        <ImagePlus className="h-4 w-4 text-primary" />
        افزودن تصویر به سؤال
      </p>

      <RadioGroup
        value={role}
        onValueChange={selectRole}
        disabled={blocked}
        aria-label="محل اتصال تصویر"
        className="flex flex-wrap items-center gap-x-5 gap-y-2"
      >
        {selectableRoles.map((item) => (
          <div key={item.value} className="flex items-center gap-2">
            <RadioGroupItem
              value={item.value}
              id={`${questionId}-visual-role-${item.value}`}
            />
            <Label
              htmlFor={`${questionId}-visual-role-${item.value}`}
              className="cursor-pointer text-sm font-normal"
            >
              {item.label}
            </Label>
          </div>
        ))}
      </RadioGroup>

      {role === 'option' && (
        <div className="space-y-2">
          <Label htmlFor={`${questionId}-visual-option`}>گزینه موردنظر</Label>
          <Select value={optionLabel} onValueChange={setOptionLabel} disabled={blocked}>
            <SelectTrigger id={`${questionId}-visual-option`} className="w-full sm:w-52">
              <SelectValue placeholder="انتخاب گزینه" />
            </SelectTrigger>
            <SelectContent>
              {optionLabels.map((label) => (
                <SelectItem key={label} value={label}>
                  گزینه {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={handleFileChange}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={blocked}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? (
            <Loader2 className="ml-2 h-4 w-4 animate-spin" />
          ) : (
            <UploadCloud className="ml-2 h-4 w-4" />
          )}
          {uploading ? 'در حال بارگذاری تصویر…' : 'انتخاب فایل تصویر'}
        </Button>
        <span className="text-xs text-muted-foreground">
          PNG، JPG یا WebP؛ حداکثر ۵ مگابایت
        </span>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
