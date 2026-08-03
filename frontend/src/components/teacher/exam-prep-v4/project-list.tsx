'use client';

import Link from 'next/link';
import {
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileStack,
  ScanSearch,
  TriangleAlert,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useExamPrepV4Projects } from '@/hooks/use-exam-prep-v4-projects';
import { cn } from '@/lib/utils';

const statusLabels: Record<string, string> = {
  draft: 'پیش‌نویس',
  uploading: 'در حال بارگذاری',
  classifying: 'در حال تشخیص صفحات',
  awaiting_source_confirmation: 'منتظر بررسی نقشه',
  segmenting: 'در حال تشخیص بلوک‌ها',
  extracting_questions: 'در حال استخراج سؤال',
  extracting_answers: 'در حال استخراج پاسخ',
  matching: 'در حال اتصال پاسخ‌ها',
  awaiting_review: 'منتظر بازبینی',
  ready_to_publish: 'آماده انتشار',
  published: 'منتشر شده',
  cancelled: 'لغو شده',
  failed: 'خطا',
};

function ProjectListSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <Skeleton key={index} className="h-56 rounded-2xl" />
      ))}
    </div>
  );
}

export function ExamPrepV4ProjectList() {
  const projects = useExamPrepV4Projects();

  if (projects.error && projects.projects.length === 0) {
    return (
      <ErrorState
        title="پروژه‌های V4 بارگذاری نشدند"
        description={projects.error}
        onRetry={projects.reload}
        homeHref="/teacher/my-exams"
        secondaryAction={{ label: 'بازگشت به آزمون‌های من', href: '/teacher/my-exams' }}
      />
    );
  }

  return (
    <div className="space-y-6" dir="rtl">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-black tracking-tight md:text-3xl">
              آماده‌سازی آزمون V4
            </h1>
            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
              Source Map + Extraction
            </Badge>
          </div>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            نقش، چرخش و ترتیب صفحات را بررسی کنید. با تأیید نقشه، استخراج سؤال، پاسخ و راه‌حل به‌صورت خودکار روی worker پروداکشن آغاز می‌شود و وضعیت آن با Run ID قابل پیگیری است.
          </p>
        </div>

        <Button asChild variant="outline" className="h-11 w-full rounded-xl lg:w-auto">
          <Link href="/teacher/my-exams">
            <ArrowLeft className="ms-2 h-4 w-4" aria-hidden="true" />
            آزمون‌های فعلی
          </Link>
        </Button>
      </header>

      <Card className="rounded-2xl border-border/60 bg-muted/20">
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <FileStack className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="font-bold">{projects.total} پروژهٔ مستقل</p>
              <p className="text-xs leading-5 text-muted-foreground">
                پروژه‌های فعال هر چهار ثانیه به‌طور خودکار بروزرسانی می‌شوند.
              </p>
            </div>
          </div>
          {projects.error ? (
            <div className="flex items-center gap-2 text-sm text-destructive" role="status">
              <TriangleAlert className="h-4 w-4" aria-hidden="true" />
              بروزرسانی فهرست کامل نشد.
            </div>
          ) : null}
        </CardContent>
      </Card>

      {projects.isLoading ? (
        <ProjectListSkeleton />
      ) : projects.projects.length === 0 ? (
        <Card className="rounded-2xl border-dashed border-border/70">
          <CardContent className="flex min-h-72 flex-col items-center justify-center gap-4 p-6 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
              <ScanSearch className="h-8 w-8" aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-lg font-black">هنوز پروژهٔ V4 آماده‌ای وجود ندارد</h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                پس از ایجاد و طبقه‌بندی یک PDF با موتور V4، پروژه در این فهرست نمایش داده می‌شود.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.projects.map((project) => {
            const completed = ['awaiting_review', 'ready_to_publish', 'published'].includes(project.status);
            const failed = project.status === 'failed';
            return (
              <Card
                key={project.id}
                className="group rounded-2xl border-border/60 transition-[border-color,box-shadow] motion-reduce:transition-none hover:border-primary/50 hover:shadow-md"
              >
                <CardHeader className="space-y-3 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <CardTitle className="line-clamp-2 text-lg font-black">
                        {project.title}
                      </CardTitle>
                      <p className="mt-1 text-xs text-muted-foreground">
                        نسخهٔ پروژه {project.revision} · {project.documentCount} سند
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className={cn(
                        'shrink-0',
                        completed && 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
                        failed && 'border-destructive/30 bg-destructive/10 text-destructive',
                      )}
                    >
                      {completed ? (
                        <CheckCircle2 className="ms-1 h-3.5 w-3.5" aria-hidden="true" />
                      ) : null}
                      {statusLabels[project.status] ?? project.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 pt-0">
                  <p className="line-clamp-3 min-h-16 text-sm leading-6 text-muted-foreground">
                    {project.description || 'توضیحی برای این پروژه ثبت نشده است.'}
                  </p>

                  <div className="space-y-2" aria-label="پیشرفت پروژه">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">پیشرفت آماده‌سازی</span>
                      <span className="font-bold">{project.progress.progressPercent}٪</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-[width] motion-reduce:transition-none"
                        style={{ width: `${Math.min(100, Math.max(0, project.progress.progressPercent))}%` }}
                      />
                    </div>
                  </div>

                  <Button asChild className="h-11 w-full rounded-xl">
                    <Link href={`/teacher/exam-prep-v4/${project.id}`}>
                      <ScanSearch className="ms-2 h-4 w-4" aria-hidden="true" />
                      بررسی نقشه و پردازش
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <nav className="flex items-center justify-between" aria-label="صفحه‌بندی پروژه‌های V4">
        <Button
          type="button"
          variant="outline"
          className="h-11 rounded-xl"
          onClick={() => projects.goToPage(projects.page - 1)}
          disabled={!projects.hasPrevious || projects.isLoading}
        >
          <ChevronRight className="ms-2 h-4 w-4" aria-hidden="true" />
          صفحهٔ قبل
        </Button>
        <span className="text-sm text-muted-foreground">صفحهٔ {projects.page}</span>
        <Button
          type="button"
          variant="outline"
          className="h-11 rounded-xl"
          onClick={() => projects.goToPage(projects.page + 1)}
          disabled={!projects.hasNext || projects.isLoading}
        >
          صفحهٔ بعد
          <ChevronLeft className="me-2 h-4 w-4" aria-hidden="true" />
        </Button>
      </nav>
    </div>
  );
}
