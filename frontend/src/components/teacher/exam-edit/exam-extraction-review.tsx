'use client';

import { useState } from 'react';
import { AlertTriangle, CheckCircle2, ImageIcon, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { ExamPrepSessionDetail } from '@/services/classes-service';
import { selectExamPrepVisual } from '@/services/classes-service';
import { ProtectedExamVisual } from '@/components/exam-prep/protected-exam-visual';

interface ExamExtractionReviewProps {
  exam: ExamPrepSessionDetail;
  onChanged: () => Promise<void>;
  onRetry?: () => Promise<void>;
}

const issueLabels: Record<string, string> = {
  missing_answer: 'پاسخ این سؤال در منبع پیدا یا تطبیق داده نشده است.',
  unmatched_answer: 'یک پاسخ به سؤال مشخصی متصل نشده است.',
  duplicate_question_number: 'برای یک شماره سؤال، دو صورت متفاوت تشخیص داده شده است.',
  conflicting_answers: 'برای یک سؤال، پاسخ‌های ناسازگار تشخیص داده شده است.',
  failed_chunk: 'بخشی از منبع کامل پردازش نشده است.',
  visual_processing_failed: 'پردازش تصاویر کامل نشده است.',
  unmatched_visual: 'یک تصویر به سؤال مشخصی متصل نشده است.',
  invalid_visual_bbox: 'محدوده یک تصویر به‌درستی تشخیص داده نشده است.',
};

export function ExamExtractionReview({ exam, onChanged, onRetry }: ExamExtractionReviewProps) {
  const [changingId, setChangingId] = useState<number | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const audit = exam.extractionAudit;
  if (!audit || (exam.extractionVersion ?? 1) < 2) return null;
  const hasFailedChunks = (exam.extractionReview?.failedChunks.length ?? 0) > 0;

  const changeVariant = async (assetId: number, variant: 'source' | 'generated') => {
    setChangingId(assetId);
    try {
      await selectExamPrepVisual(exam.id, assetId, variant);
      await onChanged();
      toast.success(variant === 'source' ? 'تصویر اصلی انتخاب شد.' : 'نسخه بازطراحی‌شده تأیید شد.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'تغییر تصویر انجام نشد.');
    } finally {
      setChangingId(null);
    }
  };

  const retryExtraction = async () => {
    if (!onRetry) return;
    setIsRetrying(true);
    try {
      await onRetry();
      toast.success('بازپردازش بخش‌های ناموفق آغاز شد.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'بازپردازش آغاز نشد.');
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <section className="space-y-5 rounded-lg border border-border bg-card p-4 md:p-5" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-bold">بازبینی کیفیت استخراج</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {audit.questionCount} سؤال استخراج شده و {audit.matchedAnswerCount} پاسخ به سؤال مقصد متصل شده است.
          </p>
        </div>
        <Badge variant={audit.status === 'passed' ? 'default' : 'destructive'}>
          {audit.status === 'passed' ? 'کنترل‌ها کامل است' : `${audit.criticalIssueCount} مورد نیازمند اصلاح`}
        </Badge>
      </div>

      {audit.criticalIssueCount > 0 && (
        <div className="space-y-2 rounded-md border border-destructive/30 bg-destructive/5 p-3">
          {audit.issues
            .filter((issue) => issue.severity === 'critical')
            .map((issue, index) => (
              <div key={`${issue.code}-${index}`} className="flex items-start gap-2 text-sm">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                <span>{issueLabels[issue.code] ?? 'بخشی از خروجی باید پیش از انتشار بررسی شود.'}</span>
              </div>
            ))}
        </div>
      )}

      {hasFailedChunks && onRetry && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
          <p className="text-sm text-muted-foreground">
            بخشی از منبع کامل پردازش نشده است. بازپردازش، خروجی فعلی را تا آماده‌شدن نتیجه جدید حفظ می‌کند.
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={isRetrying || exam.status === 'exam_structuring'}
            onClick={() => void retryExtraction()}
          >
            {isRetrying ? (
              <Loader2 className="ml-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="ml-2 h-4 w-4" />
            )}
            بازپردازش بخش ناموفق
          </Button>
        </div>
      )}

      {audit.outOfScopeAnswerCount > 0 && (
        <p className="text-sm text-muted-foreground">
          {audit.outOfScopeAnswerCount} پاسخ خارج از محدوده سؤال‌های این دفترچه کنار گذاشته شد و سؤال جدیدی نساخت.
        </p>
      )}

      {(exam.visualAssets?.length ?? 0) > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 font-semibold">
            <ImageIcon className="h-4 w-4 text-primary" />
            تصاویر استخراج‌شده
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {exam.visualAssets?.map((asset) => (
              <article key={asset.id} className="space-y-3 rounded-md border p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{asset.altText || 'تصویر سؤال'}</span>
                  {asset.selectedVariant === 'generated' && asset.teacherApprovedGenerated && (
                    <Badge variant="outline">
                      <CheckCircle2 className="ml-1 h-3 w-3" />
                      بازطراحی تأییدشده
                    </Badge>
                  )}
                </div>
                <div className={`grid gap-3 ${asset.generatedUrl ? 'sm:grid-cols-2' : 'grid-cols-1'}`}>
                  <div className="space-y-2">
                    <ProtectedExamVisual
                      url={asset.sourceUrl}
                      alt="برش اصلی منبع"
                      className="h-48 w-full rounded-md border object-contain"
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant={asset.selectedVariant === 'source' ? 'default' : 'outline'}
                      className="w-full"
                      disabled={changingId === asset.id}
                      onClick={() => void changeVariant(asset.id, 'source')}
                    >
                      استفاده از تصویر اصلی
                    </Button>
                  </div>
                  {asset.generatedUrl && (
                    <div className="space-y-2">
                      <ProtectedExamVisual
                        url={asset.generatedUrl}
                        alt="نسخه بازطراحی‌شده"
                        className="h-48 w-full rounded-md border object-contain"
                      />
                      <Button
                        type="button"
                        size="sm"
                        variant={asset.selectedVariant === 'generated' ? 'default' : 'outline'}
                        className="w-full"
                        disabled={changingId === asset.id || asset.status !== 'verified'}
                        onClick={() => void changeVariant(asset.id, 'generated')}
                      >
                        {changingId === asset.id && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
                        استفاده از بازطراحی
                      </Button>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
