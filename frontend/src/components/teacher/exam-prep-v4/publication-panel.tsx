'use client';

import { useCallback, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  FileCheck2,
  Loader2,
  Rocket,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { normalizeApiError } from '@/services/auth-service';
import {
  buildExamPrepV4Projection,
  publishExamPrepV4Project,
  type ExamPrepV4ProjectionResult,
} from '@/services/exam-prep-v4-projection-service';


export function ExamPrepV4PublicationPanel({ projectId }: { projectId: number }) {
  const [projection, setProjection] = useState<ExamPrepV4ProjectionResult | null>(null);
  const [isBuilding, setIsBuilding] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const build = useCallback(async () => {
    setIsBuilding(true);
    setError(null);
    try {
      setProjection(await buildExamPrepV4Projection(projectId));
    } catch (requestError) {
      setError(normalizeApiError(requestError).message);
    } finally {
      setIsBuilding(false);
    }
  }, [projectId]);

  const publish = useCallback(async () => {
    setIsPublishing(true);
    setError(null);
    try {
      setProjection(await publishExamPrepV4Project(projectId));
    } catch (requestError) {
      setError(normalizeApiError(requestError).message);
    } finally {
      setIsPublishing(false);
    }
  }, [projectId]);

  return (
    <Card className="rounded-2xl border-border/60" dir="rtl">
      <CardHeader className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Rocket className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <CardTitle className="text-lg font-black">نسخهٔ دانش‌آموز و انتشار</CardTitle>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                خروجی V4 به قرارداد فعلی آزمون دانش‌آموز تبدیل می‌شود؛ پاسخ و راه‌حل در API سؤال‌های دانش‌آموز افشا نمی‌شود.
              </p>
            </div>
          </div>
          {projection ? (
            <Badge variant={projection.published ? 'default' : 'outline'}>
              {projection.published ? 'منتشر شده' : 'projection آماده'}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>آماده‌سازی یا انتشار انجام نشد</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {projection ? (
          <div className="grid gap-2 text-sm sm:grid-cols-3">
            <div className="rounded-xl border border-border/60 p-3">
              <p className="text-xs text-muted-foreground">شناسه آزمون موجود</p>
              <p className="mt-1 font-black">{projection.sessionId}</p>
            </div>
            <div className="rounded-xl border border-border/60 p-3">
              <p className="text-xs text-muted-foreground">تعداد سؤال</p>
              <p className="mt-1 font-black">{projection.questionCount}</p>
            </div>
            <div className="rounded-xl border border-border/60 p-3">
              <p className="text-xs text-muted-foreground">اثر انگشت projection</p>
              <code className="mt-1 block break-all font-mono text-[11px]">
                {projection.projectionFingerprint.slice(0, 16)}…
              </code>
            </div>
          </div>
        ) : null}

        {projection?.published ? (
          <Alert className="border-emerald-500/30 bg-emerald-500/10">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>آزمون منتشر شد</AlertTitle>
            <AlertDescription>
              اکنون می‌توانید دعوت دانش‌آموزان، جزئیات آزمون و نتایج را از جریان موجود مدیریت کنید.
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <Button
            type="button"
            variant="outline"
            className="h-11 rounded-xl"
            onClick={() => void build()}
            disabled={isBuilding || isPublishing}
          >
            {isBuilding ? (
              <Loader2 className="ms-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <FileCheck2 className="ms-2 h-4 w-4" aria-hidden="true" />
            )}
            ساخت نسخهٔ دانش‌آموز
          </Button>
          <Button
            type="button"
            className="h-11 rounded-xl"
            onClick={() => void publish()}
            disabled={isPublishing || isBuilding || projection?.published}
          >
            {isPublishing ? (
              <Loader2 className="ms-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Rocket className="ms-2 h-4 w-4" aria-hidden="true" />
            )}
            انتشار آزمون
          </Button>
          {projection ? (
            <Button asChild variant="ghost" className="h-11 rounded-xl">
              <Link href={`/teacher/my-exams/${projection.sessionId}`}>
                <ExternalLink className="ms-2 h-4 w-4" aria-hidden="true" />
                مدیریت آزمون موجود
              </Link>
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
