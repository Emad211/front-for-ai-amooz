'use client';

import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Copy,
  ImageOff,
  RotateCw,
  Sparkles,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  EXAM_PREP_V4_SOURCE_ROLES,
  SOURCE_ROLE_DESCRIPTIONS,
  SOURCE_ROLE_LABELS,
  SOURCE_ROLE_SHORT_LABELS,
  roleConfidencePercent,
  type EditableSourceMapPage,
  type ExamPrepV4Page,
  type ExamPrepV4SourceRole,
} from '@/features/exam-prep-v4/source-map-model';
import { useExamPrepV4Thumbnail } from '@/hooks/use-exam-prep-v4-thumbnail';
import { cn } from '@/lib/utils';

const roleClasses: Record<ExamPrepV4SourceRole, string> = {
  cover: 'border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300',
  questions: 'border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300',
  answer_solutions: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  answer_key: 'border-teal-500/30 bg-teal-500/10 text-teal-700 dark:text-teal-300',
  inline_question_answer: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300',
  ignored: 'border-muted-foreground/20 bg-muted text-muted-foreground',
  unknown: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
};

export function SourcePageCard({
  projectId,
  documentId,
  page,
  editablePage,
  onRoleChange,
  onRotate,
  onMoveEarlier,
  onMoveLater,
  canMoveEarlier,
  canMoveLater,
  disabled,
}: {
  projectId: number;
  documentId: number;
  page: ExamPrepV4Page;
  editablePage: EditableSourceMapPage;
  onRoleChange: (pageNumber: number, role: ExamPrepV4SourceRole) => void;
  onRotate: (pageNumber: number) => void;
  onMoveEarlier: (pageNumber: number) => void;
  onMoveLater: (pageNumber: number) => void;
  canMoveEarlier: boolean;
  canMoveLater: boolean;
  disabled: boolean;
}) {
  const thumbnail = useExamPrepV4Thumbnail({
    projectId,
    documentId,
    pageNumber: page.pageNumber,
    enabled: page.hasThumbnail,
  });
  const roleChanged = editablePage.role !== page.effectiveRole;
  const rotationChanged = editablePage.orientation !== page.orientation;
  const orderChanged = editablePage.displayOrder !== page.displayOrder;
  const hasLocalChange = roleChanged || rotationChanged || orderChanged;
  const roleDescriptionId = `source-page-${documentId}-${page.pageNumber}-role-description`;
  const predictedPercent = roleConfidencePercent(page.predictedConfidence);

  return (
    <Card
      role="group"
      aria-labelledby={`source-page-${documentId}-${page.pageNumber}-title`}
      className={cn(
        'overflow-hidden rounded-2xl border-border/60 bg-card shadow-sm transition-[border-color,box-shadow] motion-reduce:transition-none',
        'focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/20',
        hasLocalChange && 'border-primary/50 shadow-primary/5',
        editablePage.role === 'unknown' && 'border-amber-500/50',
      )}
    >
      <CardHeader className="space-y-3 p-4 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3
                id={`source-page-${documentId}-${page.pageNumber}-title`}
                className="text-base font-black"
              >
                صفحهٔ منبع {page.pageNumber}
              </h3>
              <Badge variant="secondary">
                جایگاه مجازی {editablePage.displayOrder}
              </Badge>
              {hasLocalChange ? (
                <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                  تغییر ذخیره‌نشده
                </Badge>
              ) : null}
              {page.isDuplicate ? (
                <Badge variant="outline" className="gap-1 text-muted-foreground">
                  <Copy className="h-3 w-3" aria-hidden="true" />
                  مشابه صفحهٔ دیگر
                </Badge>
              ) : null}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              شمارهٔ منبع ثابت است؛ فقط جایگاه مجازی پردازش تغییر می‌کند. ابعاد: {page.width || '—'} × {page.height || '—'}
            </p>
          </div>

          <Badge
            variant="outline"
            className={cn('shrink-0', roleClasses[editablePage.role])}
          >
            {SOURCE_ROLE_SHORT_LABELS[editablePage.role]}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            پیشنهاد مدل:
          </span>
          <Badge variant="secondary">
            {SOURCE_ROLE_SHORT_LABELS[page.predictedRole]} · {predictedPercent}٪
          </Badge>
          {page.teacherRole ? (
            <Badge variant="outline" className="border-primary/30 text-primary">
              اصلاح معلم: {SOURCE_ROLE_SHORT_LABELS[page.teacherRole]}
            </Badge>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-4 p-4 pt-0">
        <div
          className="relative flex aspect-[3/4] items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-muted/30"
          aria-busy={thumbnail.isLoading}
        >
          {thumbnail.isLoading ? (
            <Skeleton className="absolute inset-0 rounded-none" />
          ) : thumbnail.url ? (
            // Authenticated thumbnails are object URLs and cannot use Next Image.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={thumbnail.url}
              alt={`پیش‌نمایش صفحهٔ منبع ${page.pageNumber} در جایگاه مجازی ${editablePage.displayOrder} با نقش ${SOURCE_ROLE_LABELS[editablePage.role]}`}
              className="max-h-full max-w-full object-contain transition-transform duration-200 motion-reduce:transition-none"
              style={{ transform: `rotate(${editablePage.orientation}deg)` }}
            />
          ) : (
            <div className="flex max-w-[15rem] flex-col items-center gap-2 px-4 text-center text-sm text-muted-foreground">
              <ImageOff className="h-8 w-8" aria-hidden="true" />
              <span>
                {page.hasThumbnail
                  ? 'پیش‌نمایش خصوصی این صفحه بارگذاری نشد.'
                  : 'برای این صفحه پیش‌نمایش ثبت نشده است.'}
              </span>
            </div>
          )}
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-bold">ترتیب مجازی پردازش</legend>
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant="outline"
              className="h-11 rounded-xl"
              onClick={() => onMoveEarlier(page.pageNumber)}
              disabled={disabled || !canMoveEarlier}
              aria-label={`انتقال صفحهٔ منبع ${page.pageNumber} به جایگاه مجازی زودتر؛ جایگاه فعلی ${editablePage.displayOrder}`}
            >
              <ArrowUp className="ms-2 h-4 w-4" aria-hidden="true" />
              زودتر
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-11 rounded-xl"
              onClick={() => onMoveLater(page.pageNumber)}
              disabled={disabled || !canMoveLater}
              aria-label={`انتقال صفحهٔ منبع ${page.pageNumber} به جایگاه مجازی دیرتر؛ جایگاه فعلی ${editablePage.displayOrder}`}
            >
              <ArrowDown className="ms-2 h-4 w-4" aria-hidden="true" />
              دیرتر
            </Button>
          </div>
          <p className="text-xs leading-5 text-muted-foreground">
            این کنترل فقط ترتیب نمایش و پردازش را تغییر می‌دهد؛ PDF و شمارهٔ منبع بازنویسی نمی‌شوند.
          </p>
        </fieldset>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <label
              htmlFor={`source-page-${documentId}-${page.pageNumber}-role`}
              className="text-sm font-bold"
            >
              نقش نهایی صفحه
            </label>
            <Select
              value={editablePage.role}
              onValueChange={(value) => onRoleChange(
                page.pageNumber,
                value as ExamPrepV4SourceRole,
              )}
              disabled={disabled}
            >
              <SelectTrigger
                id={`source-page-${documentId}-${page.pageNumber}-role`}
                className="h-11 rounded-xl"
                aria-describedby={roleDescriptionId}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EXAM_PREP_V4_SOURCE_ROLES.map((role) => (
                  <SelectItem key={role} value={role}>
                    {SOURCE_ROLE_LABELS[role]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p id={roleDescriptionId} className="text-xs leading-5 text-muted-foreground">
              {SOURCE_ROLE_DESCRIPTIONS[editablePage.role]}
            </p>
          </div>

          <Button
            type="button"
            variant="outline"
            className="h-11 w-full rounded-xl"
            onClick={() => onRotate(page.pageNumber)}
            disabled={disabled}
            aria-label={`چرخاندن صفحهٔ منبع ${page.pageNumber}؛ زاویهٔ فعلی ${editablePage.orientation} درجه`}
          >
            <RotateCw className="ms-2 h-4 w-4" aria-hidden="true" />
            چرخش ۹۰ درجه
            <span className="me-auto text-xs text-muted-foreground">
              {editablePage.orientation}°
            </span>
          </Button>
        </div>

        {editablePage.role === 'unknown' ? (
          <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs leading-5 text-amber-800 dark:text-amber-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>برای تأیید نهایی باید نقش این صفحه مشخص شود.</span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
