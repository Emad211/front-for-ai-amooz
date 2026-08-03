'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  FileStack,
  Loader2,
  RefreshCcw,
  RotateCcw,
  Save,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { SourcePageCard } from '@/components/teacher/exam-prep-v4/source-page-card';
import {
  SOURCE_ROLE_SHORT_LABELS,
  type EditableSourceMapPage,
} from '@/features/exam-prep-v4/source-map-model';
import { useExamPrepV4SourceMap } from '@/hooks/use-exam-prep-v4-source-map';
import { cn } from '@/lib/utils';

const projectStatusLabels: Record<string, string> = {
  draft: 'پیش‌نویس',
  uploading: 'در حال بارگذاری',
  classifying: 'در حال تشخیص صفحات',
  awaiting_source_confirmation: 'منتظر بررسی نقشه',
  segmenting: 'نقشه تأیید شده',
  failed: 'خطا',
};

function EditorSkeleton() {
  return (
    <div className="space-y-6" aria-label="در حال بارگذاری نقشهٔ صفحات">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-2">
          <Skeleton className="h-8 w-64 rounded-xl" />
          <Skeleton className="h-5 w-80 max-w-full rounded-lg" />
        </div>
        <Skeleton className="h-11 w-full rounded-xl md:w-52" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton key={index} className="aspect-[3/4] rounded-2xl" />
        ))}
      </div>
    </div>
  );
}

function DocumentSummary({
  pageCount,
  unknownCount,
  dirty,
  confirmed,
}: {
  pageCount: number;
  unknownCount: number;
  dirty: boolean;
  confirmed: boolean;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="خلاصهٔ نقشهٔ صفحات">
      <div className="rounded-xl border border-border/60 bg-muted/30 p-3">
        <p className="text-xs text-muted-foreground">تعداد صفحات</p>
        <p className="mt-1 text-lg font-black">{pageCount}</p>
      </div>
      <div className="rounded-xl border border-border/60 bg-muted/30 p-3">
        <p className="text-xs text-muted-foreground">صفحات نامشخص</p>
        <p className={cn('mt-1 text-lg font-black', unknownCount > 0 && 'text-amber-600 dark:text-amber-300')}>
          {unknownCount}
        </p>
      </div>
      <div className="rounded-xl border border-border/60 bg-muted/30 p-3">
        <p className="text-xs text-muted-foreground">وضعیت ذخیره</p>
        <p className={cn('mt-1 text-sm font-bold', dirty ? 'text-primary' : 'text-emerald-600 dark:text-emerald-300')}>
          {dirty ? 'ذخیره‌نشده' : 'همگام با سرور'}
        </p>
      </div>
      <div className="rounded-xl border border-border/60 bg-muted/30 p-3">
        <p className="text-xs text-muted-foreground">تأیید معلم</p>
        <p className={cn('mt-1 text-sm font-bold', confirmed ? 'text-emerald-600 dark:text-emerald-300' : 'text-muted-foreground')}>
          {confirmed ? 'تأیید شده' : 'تأیید نشده'}
        </p>
      </div>
    </div>
  );
}

export function ExamPrepV4SourceMapEditor({ projectId }: { projectId: number }) {
  const editor = useExamPrepV4SourceMap(projectId);
  const [pendingDocumentId, setPendingDocumentId] = useState<number | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  const editableByPage = useMemo(() => new Map<number, EditableSourceMapPage>(
    editor.draftPages.map((page) => [page.pageNumber, page]),
  ), [editor.draftPages]);

  const currentPages = editor.selectedDocument?.pages ?? [];
  const currentStatusLabel = editor.project
    ? (projectStatusLabels[editor.project.status] ?? editor.project.status)
    : '';

  const handleDocumentChange = (value: string) => {
    const documentId = Number(value);
    if (!Number.isInteger(documentId)) return;
    if (editor.hasUnsavedChanges) {
      setPendingDocumentId(documentId);
      return;
    }
    editor.selectDocument(documentId);
  };

  const confirmDocumentSwitch = () => {
    if (pendingDocumentId !== null) {
      editor.selectDocument(pendingDocumentId);
    }
    setPendingDocumentId(null);
  };

  if (editor.isLoading) return <EditorSkeleton />;

  if (editor.error && !editor.project) {
    return (
      <ErrorState
        title="نقشهٔ صفحات بارگذاری نشد"
        description={editor.error}
        onRetry={() => void editor.reloadCurrentServerMap()}
        homeHref="/teacher/exam-prep-v4"
        secondaryAction={{ label: 'بازگشت به آزمون‌های V4', href: '/teacher/exam-prep-v4' }}
      />
    );
  }

  if (!editor.project) {
    return (
      <ErrorState
        title="پروژه پیدا نشد"
        description="این پروژه وجود ندارد یا به حساب شما تعلق ندارد."
        variant="not-found"
        homeHref="/teacher/exam-prep-v4"
      />
    );
  }

  if (!editor.selectedDocument) {
    return (
      <ErrorState
        title="منبعی برای بررسی وجود ندارد"
        description="این پروژه هنوز سند آماده‌ای برای نمایش نقشهٔ صفحات ندارد."
        onRetry={() => void editor.reloadCurrentServerMap()}
        homeHref="/teacher/exam-prep-v4"
      />
    );
  }

  const document = editor.selectedDocument;
  const actionsDisabled = editor.isSaving || editor.isConfirming;
  const confirmationReason = editor.hasUnsavedChanges
    ? 'ابتدا تغییرات را ذخیره کنید.'
    : editor.unknownPageCount > 0
      ? 'نقش تمام صفحات نامشخص را تعیین کنید.'
      : !document.sourceMapFingerprint
        ? 'اثر انگشت نسخهٔ فعلی در دسترس نیست.'
        : document.isTeacherConfirmed
          ? 'این نسخه قبلاً تأیید شده است.'
          : null;

  return (
    <div className="space-y-6" dir="rtl">
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {editor.announcement}
      </div>

      <header className="space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <Button asChild variant="ghost" size="icon" className="h-11 w-11 shrink-0 rounded-full">
              <Link href="/teacher/exam-prep-v4" aria-label="بازگشت به فهرست آزمون‌های V4">
                <ArrowRight className="h-5 w-5" aria-hidden="true" />
              </Link>
            </Button>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-black tracking-tight md:text-3xl">
                  نقشهٔ صفحات آزمون
                </h1>
                <Badge variant="outline">{currentStatusLabel}</Badge>
                <Badge variant="secondary">نسخهٔ {document.classificationRevision}</Badge>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {editor.project.title} — نقش هر صفحه را بررسی کنید، تغییرات را ذخیره کنید و سپس همان نسخه را تأیید کنید.
              </p>
            </div>
          </div>

          {editor.documents.length > 1 ? (
            <div className="w-full space-y-1.5 lg:w-64">
              <label htmlFor="exam-v4-document-select" className="text-sm font-bold">
                سند منبع
              </label>
              <Select
                value={String(document.id)}
                onValueChange={handleDocumentChange}
                disabled={actionsDisabled}
              >
                <SelectTrigger id="exam-v4-document-select" className="h-11 rounded-xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {editor.documents.map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      سند {item.uploadOrder + 1} — {item.pageCount} صفحه
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
        </div>

        <DocumentSummary
          pageCount={document.pageCount}
          unknownCount={editor.unknownPageCount}
          dirty={editor.hasUnsavedChanges}
          confirmed={document.isTeacherConfirmed}
        />
      </header>

      {editor.hasUnsavedChanges ? (
        <Alert className="border-primary/30 bg-primary/5">
          <Save className="h-4 w-4" aria-hidden="true" />
          <AlertTitle>تغییرات ذخیره‌نشده دارید</AlertTitle>
          <AlertDescription>
            تا زمان انتخاب «ذخیرهٔ نقشه»، هیچ تغییری به سرور فرستاده نمی‌شود.
          </AlertDescription>
        </Alert>
      ) : null}

      {editor.conflict ? (
        <Alert variant="destructive">
          <TriangleAlert className="h-4 w-4" aria-hidden="true" />
          <AlertTitle>نسخهٔ سرور تغییر کرده است</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{editor.conflict.message}</p>
            <p>تغییرات محلی شما حفظ شده‌اند. با بارگذاری نسخهٔ سرور، تغییرات محلی کنار گذاشته می‌شوند.</p>
            <Button
              type="button"
              variant="outline"
              className="h-11 rounded-xl"
              onClick={() => void editor.reloadCurrentServerMap()}
              disabled={actionsDisabled}
            >
              <RefreshCcw className="ms-2 h-4 w-4" aria-hidden="true" />
              بارگذاری نسخهٔ فعلی سرور
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {editor.error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" aria-hidden="true" />
          <AlertTitle>عملیات انجام نشد</AlertTitle>
          <AlertDescription>{editor.error}</AlertDescription>
        </Alert>
      ) : null}

      {document.isTeacherConfirmed ? (
        <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          <AlertTitle>این نسخه تأیید شده است</AlertTitle>
          <AlertDescription>
            تأیید به نسخهٔ {document.teacherConfirmedRevision ?? document.classificationRevision} متصل است. هر ویرایش تازه، تأیید را باطل می‌کند.
          </AlertDescription>
        </Alert>
      ) : null}

      <section aria-labelledby="source-pages-heading" className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 id="source-pages-heading" className="text-xl font-black">
              صفحات منبع
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              ترتیب نمایش، شمارهٔ واقعی صفحات PDF است. جابه‌جایی صفحات در این مرحله پشتیبانی نمی‌شود.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            {document.segments.map((segment) => (
              <Badge key={segment.id} variant="outline">
                {SOURCE_ROLE_SHORT_LABELS[segment.role]}: {segment.startPage}–{segment.endPage}
              </Badge>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {currentPages.map((page) => {
            const editablePage = editableByPage.get(page.pageNumber);
            if (!editablePage) return null;
            return (
              <SourcePageCard
                key={page.pageNumber}
                projectId={projectId}
                documentId={document.id}
                page={page}
                editablePage={editablePage}
                onRoleChange={editor.changeRole}
                onRotate={editor.rotatePage}
                disabled={actionsDisabled}
              />
            );
          })}
        </div>
      </section>

      <div className="sticky bottom-4 z-20 rounded-2xl border border-border/70 bg-background/95 p-3 shadow-xl shadow-foreground/10 backdrop-blur supports-[backdrop-filter]:bg-background/85">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 text-sm">
            <p className="font-bold">
              {editor.hasUnsavedChanges
                ? 'نقشه تغییر کرده و هنوز ذخیره نشده است.'
                : document.isTeacherConfirmed
                  ? 'نسخهٔ فعلی ذخیره و تأیید شده است.'
                  : 'نسخهٔ فعلی با سرور همگام است.'}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {confirmationReason ?? 'نقشه آمادهٔ تأیید نهایی است.'}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 lg:flex lg:justify-end">
            <Button
              type="button"
              variant="ghost"
              className="h-11 rounded-xl"
              onClick={editor.discardChanges}
              disabled={!editor.hasUnsavedChanges || actionsDisabled}
            >
              <RotateCcw className="ms-2 h-4 w-4" aria-hidden="true" />
              لغو تغییرات
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-11 rounded-xl"
              onClick={() => void editor.save()}
              disabled={!editor.hasUnsavedChanges || actionsDisabled}
            >
              {editor.isSaving ? (
                <Loader2 className="ms-2 h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
              ) : (
                <Save className="ms-2 h-4 w-4" aria-hidden="true" />
              )}
              {editor.isSaving ? 'در حال ذخیره' : 'ذخیرهٔ نقشه'}
            </Button>
            <Button
              type="button"
              className="h-11 rounded-xl"
              onClick={() => setShowConfirmDialog(true)}
              disabled={!editor.canConfirm || actionsDisabled}
              aria-describedby="source-map-confirmation-help"
            >
              {editor.isConfirming ? (
                <Loader2 className="ms-2 h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
              ) : (
                <ShieldCheck className="ms-2 h-4 w-4" aria-hidden="true" />
              )}
              تأیید نقشه
            </Button>
          </div>
        </div>
        <p id="source-map-confirmation-help" className="sr-only">
          تأیید فقط زمانی فعال است که تغییر ذخیره‌نشده و صفحهٔ نامشخص وجود نداشته باشد و اثر انگشت نسخهٔ فعلی موجود باشد.
        </p>
      </div>

      <AlertDialog open={pendingDocumentId !== null} onOpenChange={(open) => !open && setPendingDocumentId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>تغییرات ذخیره‌نشده کنار گذاشته شوند؟</AlertDialogTitle>
            <AlertDialogDescription>
              با رفتن به سند دیگر، تغییرات محلی این سند حذف می‌شوند. این عملیات روی سرور اثری ندارد.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>ماندن در این سند</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDocumentSwitch}>
              کنار گذاشتن و ادامه
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>تأیید نهایی نقشهٔ صفحات</AlertDialogTitle>
            <AlertDialogDescription>
              نسخهٔ {document.classificationRevision} با همین نقش‌ها و چرخش‌ها تأیید می‌شود. این تأیید هیچ استخراج سؤال یا پردازش فاز بعدی را در این مرحله شروع نمی‌کند.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>انصراف</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setShowConfirmDialog(false);
                void editor.confirm();
              }}
              disabled={!editor.canConfirm || actionsDisabled}
            >
              تأیید همین نسخه
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
