'use client';

import { useEffect, useState } from 'react';
import { FileSearch, Loader2, TriangleAlert } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { ExamPrepV4ExtractionRuntimePanel } from '@/components/teacher/exam-prep-v4/extraction-runtime-panel';
import { ExamPrepV4PublicationPanel } from '@/components/teacher/exam-prep-v4/publication-panel';
import { ExamPrepV4ReviewPanel } from '@/components/teacher/exam-prep-v4/review-panel';
import { ExamPrepV4SourceMapEditor } from '@/components/teacher/exam-prep-v4/source-map-editor';
import {
  getExamPrepV4Project,
  type ExamPrepV4ProjectDetail,
} from '@/services/exam-prep-v4-service';
import { getExamPrepSourceAwareBridge } from '@/services/exam-prep-source-aware-service';
import { normalizeApiError } from '@/services/auth-service';

const TERMINAL = new Set(['published', 'cancelled', 'failed']);
const EXTRACTION_STARTED = new Set([
  'segmenting',
  'extracting_questions',
  'extracting_answers',
  'matching',
  'awaiting_review',
  'ready_to_publish',
  'published',
  'failed',
  'cancelled',
]);

export function ExamPrepSourceAwareWorkspace({ sessionId }: { sessionId: number }) {
  const [project, setProject] = useState<ExamPrepV4ProjectDetail | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [isResolving, setIsResolving] = useState(true);
  const [isLegacyDraft, setIsLegacyDraft] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const controller = new AbortController();

    const load = async () => {
      try {
        const bridge = await getExamPrepSourceAwareBridge(sessionId, controller.signal);
        if (!active) return;
        if (!bridge) {
          setIsLegacyDraft(true);
          setIsResolving(false);
          return;
        }
        setProjectId(bridge.projectId);
        const nextProject = await getExamPrepV4Project(bridge.projectId, controller.signal);
        if (!active) return;
        setProject(nextProject);
        setError(null);
        setIsResolving(false);
        if (!TERMINAL.has(nextProject.status)) {
          timer = window.setTimeout(load, 3000);
        }
      } catch (requestError) {
        if (!active || controller.signal.aborted) return;
        setError(normalizeApiError(requestError).message);
        setIsResolving(false);
        timer = window.setTimeout(load, 5000);
      }
    };

    void load();
    return () => {
      active = false;
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [sessionId]);

  if (isLegacyDraft) return null;

  if (isResolving && !project) {
    return (
      <Card className="mt-4 rounded-2xl border-border/60">
        <CardContent className="flex items-center gap-3 p-4 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          در حال آماده‌سازی بررسی صفحات PDF…
        </CardContent>
      </Card>
    );
  }

  if (error && !project) {
    return (
      <Alert variant="destructive" className="mt-4 rounded-2xl">
        <TriangleAlert className="h-4 w-4" aria-hidden="true" />
        <AlertTitle>اطلاعات آماده‌سازی فایل دریافت نشد</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!project || projectId === null) return null;

  const hasSourceMap = project.documents.some((document) => document.hasSourceMap);
  const shouldShowEditor = hasSourceMap || !['draft', 'uploading', 'classifying'].includes(project.status);
  const shouldShowRuntime = EXTRACTION_STARTED.has(project.status);
  const shouldShowReview = ['awaiting_review', 'ready_to_publish', 'published'].includes(project.status);
  const shouldShowPublication = ['ready_to_publish', 'published'].includes(project.status);

  return (
    <section className="mt-6 space-y-6" aria-labelledby="exam-source-review-title" dir="rtl">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <FileSearch className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h3 id="exam-source-review-title" className="font-bold">
            بررسی و آماده‌سازی فایل آزمون
          </h3>
          <p className="mt-1 text-xs leading-6 text-muted-foreground">
            نقش و ترتیب صفحات را بررسی کنید؛ سپس سؤال‌ها، پاسخ‌ها و راه‌حل‌ها به‌صورت خودکار آماده می‌شوند.
          </p>
        </div>
      </div>

      {error ? (
        <Alert variant="destructive" className="rounded-2xl">
          <TriangleAlert className="h-4 w-4" aria-hidden="true" />
          <AlertTitle>به‌روزرسانی وضعیت کامل نشد</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {!shouldShowEditor ? (
        <Card className="rounded-2xl border-border/60">
          <CardContent className="flex items-center gap-3 p-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            در حال تشخیص ساختار و نقش صفحات…
          </CardContent>
        </Card>
      ) : (
        <div className="[&_header_button:first-child]:hidden">
          <ExamPrepV4SourceMapEditor projectId={projectId} />
        </div>
      )}

      {shouldShowRuntime ? <ExamPrepV4ExtractionRuntimePanel projectId={projectId} /> : null}
      {shouldShowReview ? <ExamPrepV4ReviewPanel projectId={projectId} /> : null}
      {shouldShowPublication ? <ExamPrepV4PublicationPanel projectId={projectId} /> : null}
    </section>
  );
}
