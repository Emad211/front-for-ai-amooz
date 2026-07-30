'use client';

import { useState } from 'react';
import { AlertTriangle, CheckCircle2, ImageIcon, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { ExamPrepSessionDetail, ExamPrepSourceUnitIssue } from '@/services/classes-service';
import {
  confirmExamPrepExtractionReview,
  getExamPrepExtractionUnitSourceUrl,
  retryExamPrepExtractionUnit,
  selectExamPrepVisual,
} from '@/services/classes-service';
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
  unprocessed_source_block: 'بخشی از منبع معتبر تشخیص داده نشد و وارد خروجی نهایی نشده است.',
};

const stageLabels: Record<ExamPrepSourceUnitIssue['stage'], string> = {
  ocr: 'خواندن منبع',
  manifest: 'تشخیص ساختار صفحات',
  questions: 'استخراج سؤال‌ها',
  answers: 'استخراج پاسخ‌ها',
  visuals: 'پردازش تصاویر',
};

const qualityIssueLabels: Record<string, string> = {
  empty_output: 'متنی از این بخش خوانده نشد.',
  incomplete_finish_reason: 'پاسخ سرویس پردازش کامل دریافت نشد.',
  absolute_length_limit: 'حجم متن استخراج‌شده غیرعادی بود.',
  length_outlier: 'حجم متن این صفحه با صفحات دیگر سازگار نبود.',
  native_text_ratio: 'خروجی خوانده‌شده با متن داخلی فایل اختلاف غیرعادی داشت.',
  duplicate_lines: 'تکرار غیرعادی در متن استخراج‌شده دیده شد.',
  numeric_instability: 'اعداد در دو بار خواندن این صفحه یکسان نبودند.',
};

export function ExamExtractionReview({ exam, onChanged, onRetry }: ExamExtractionReviewProps) {
  const [changingId, setChangingId] = useState<number | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryingUnitId, setRetryingUnitId] = useState<number | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
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

  const retryUnit = async (unitId: number) => {
    if (exam.artifactRevision == null) return;
    setRetryingUnitId(unitId);
    try {
      await retryExamPrepExtractionUnit(exam.id, unitId, exam.artifactRevision);
      await onChanged();
      toast.success('خواندن دوباره این بخش در صف پردازش قرار گرفت.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'تلاش دوباره آغاز نشد.');
    } finally {
      setRetryingUnitId(null);
    }
  };

  const confirmReview = async () => {
    if (exam.artifactRevision == null || !exam.projectionFingerprint) return;
    setIsConfirming(true);
    try {
      await confirmExamPrepExtractionReview(
        exam.id,
        exam.artifactRevision,
        exam.projectionFingerprint,
      );
      await onChanged();
      toast.success('بازبینی نهایی ثبت شد. آزمون آماده انتشار است.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'ثبت بازبینی انجام نشد.');
    } finally {
      setIsConfirming(false);
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

      {(exam.sourceUnitIssues?.length ?? 0) > 0 && (
        <div className="space-y-3">
          <div>
            <h3 className="font-semibold">بخش‌های پردازش‌نشده منبع</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              این بخش‌ها وارد سؤال‌ها و پاسخ‌های نهایی نشده‌اند. منبع را ببینید و فقط همان بخش را دوباره پردازش کنید.
            </p>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {exam.sourceUnitIssues?.map((unit) => {
              const qualityCodes = [
                ...(unit.qualityReport?.hardIssues ?? []),
                ...(unit.qualityReport?.softIssues ?? []),
              ];
              const canRetry =
                ['retryable', 'quarantined', 'failed'].includes(unit.status)
                && exam.status !== 'exam_structuring';
              return (
                <article key={unit.id} className="space-y-3 rounded-md border border-amber-500/30 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-600" />
                      <span className="text-sm font-semibold">{stageLabels[unit.stage]}</span>
                    </div>
                    <Badge variant="outline">
                      {unit.pageNumber ? `صفحه ${unit.pageNumber}` : `بخش ${unit.segmentIndex ?? unit.id}`}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {qualityCodes.length
                      ? qualityCodes.map((code) => qualityIssueLabels[code] ?? 'کیفیت این بخش قابل اتکا نبود.').join(' ')
                      : 'پردازش این بخش کامل نشد و برای جلوگیری از ساخت سؤال نادرست کنار گذاشته شد.'}
                  </p>
                  {unit.pageNumber && (
                    <ProtectedExamVisual
                      url={getExamPrepExtractionUnitSourceUrl(exam.id, unit.id)}
                      alt={`منبع صفحه ${unit.pageNumber}`}
                      className="h-56 w-full rounded-md border bg-muted/20 object-contain"
                    />
                  )}
                  <div className="flex items-center justify-end gap-2">
                    {canRetry && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={retryingUnitId === unit.id}
                        onClick={() => void retryUnit(unit.id)}
                      >
                        {retryingUnitId === unit.id ? (
                          <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="ml-2 h-4 w-4" />
                        )}
                        پردازش دوباره
                      </Button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
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

      {(exam.extractionVersion ?? 1) >= 3 && exam.teacherReviewRequired && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
          <div>
            <p className="font-semibold">
              {exam.teacherReviewedAt ? 'بازبینی نهایی ثبت شده است.' : 'تأیید نهایی بازبینی'}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              پس از بررسی سؤال‌ها، پاسخ‌ها و منبع بخش‌های مشکوک، نتیجه را تأیید کنید.
            </p>
          </div>
          {exam.teacherReviewedAt ? (
            <Badge variant="outline">
              <CheckCircle2 className="ml-1 h-3.5 w-3.5 text-emerald-600" />
              تأییدشده
            </Badge>
          ) : (
            <Button
              type="button"
              disabled={
                isConfirming
                || audit.criticalIssueCount > 0
                || !exam.projectionFingerprint
                || exam.artifactRevision == null
              }
              onClick={() => void confirmReview()}
            >
              {isConfirming && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
              تأیید بازبینی
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
