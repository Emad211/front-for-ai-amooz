'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  ArrowLeft,
  BarChart3,
  CalendarCheck2,
  ClipboardCheck,
  RefreshCw,
} from 'lucide-react';

import {
  AdvisoryService,
  type AdvisorGrowthEvidenceValue,
  type AdvisorGrowthRecommendation,
  type AdvisorGrowthResponse,
} from '@/services/advisory-service';
import { formatPersianDate } from '@/lib/date-utils';
import { toPersianDigits } from '@/lib/persian-digits';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

const EVIDENCE_LABELS: Record<string, string> = {
  streak: 'روزهای پیوستهٔ ثبت گزارش',
  loggedToday: 'گزارش امروز ثبت شده',
  planExecutionPercent: 'درصد اجرای برنامهٔ فعلی',
  latestExamPercent: 'آخرین درصد آزمون',
  examTrend: 'تغییر روند آزمون',
  openMistakes: 'اشتباه‌های رفع‌نشده',
  reviewDue: 'مرورهای سررسیدشده',
  backlogTotal: 'عقب‌افتادگی‌های باز',
  testDensity: 'میانگین تست روزهای ثبت‌شده (۱۴ روز)',
  mistakeResolutionDays: 'میانهٔ روزهای رفع اشتباه (۳۰ روز)',
  planCalibration: 'نسبت برنامه به اجرا (۱۴ روز)',
  reportRate7d: 'درصد روزهای ثبت‌گزارش (۷ روز)',
  advisorDosageDays: 'روز از آخرین تماس مشاور',
};

/** Evidence keys whose numeric value is a percent; rendered with «٪». */
const PERCENT_EVIDENCE_KEYS = new Set(['reportRate7d', 'planExecutionPercent']);

const PRIORITY_LABELS: Record<NonNullable<AdvisorGrowthRecommendation['priority']>, string> = {
  HIGH: 'اولویت بالا',
  MEDIUM: 'اولویت متوسط',
  LOW: 'اولویت پایین',
};

type AdvisorGrowthPanelProps = {
  engagementId: number;
};

function formatEvidenceValue(value: AdvisorGrowthEvidenceValue): string {
  if (value === null || value === '') return 'ثبت نشده';
  if (typeof value === 'boolean') return value ? 'بله' : 'خیر';
  // Decimals (e.g. testDensity) use the Persian separator «٫», not «.».
  if (typeof value === 'number') return toPersianDigits(String(value).replace('.', '٫'));
  return toPersianDigits(value);
}

/** Key-aware evidence label: known percent keys and the planCalibration
 * ratio render as «…٪»; everything else falls through to the generic
 * formatter. */
function evidenceValueLabel(key: string, value: AdvisorGrowthEvidenceValue): string {
  if (typeof value === 'number') {
    if (key === 'planCalibration') return `${toPersianDigits(Math.round(value * 100))}٪`;
    if (PERCENT_EVIDENCE_KEYS.has(key)) return `${toPersianDigits(value)}٪`;
  }
  return formatEvidenceValue(value);
}

function recommendationBody(recommendation: AdvisorGrowthRecommendation): string {
  return recommendation.description?.trim() || recommendation.reason?.trim() || '';
}

function actionHref(engagementId: number, area: AdvisorGrowthRecommendation['actionArea']): string {
  if (area === 'exams') return `/advisor/students/${engagementId}?tab=exams`;
  if (area === 'feed') return `/advisor/students/${engagementId}?tab=feed`;
  return `/advisor/students/${engagementId}?tab=plan`;
}

export function AdvisorGrowthPanel({ engagementId }: AdvisorGrowthPanelProps) {
  const [data, setData] = useState<AdvisorGrowthResponse | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setData(null);
    setError('');
    AdvisoryService.getStudentGrowth(engagementId)
      .then((response) => {
        if (active) setData(response);
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : 'دریافت پیشنهادها ناموفق بود.');
        }
      });
    return () => {
      active = false;
    };
  }, [engagementId, reloadKey]);

  if (error) {
    return (
      <Card className="border-destructive/40 bg-destructive/5" role="alert">
        <CardContent className="flex flex-col items-start gap-4 py-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-semibold">پیشنهادهای امروز بارگذاری نشد</p>
              <p className="mt-1 text-xs leading-6">{error}</p>
            </div>
          </div>
          <Button variant="outline" className="h-11" onClick={() => setReloadKey((key) => key + 1)}>
            <RefreshCw className="h-4 w-4" />
            تلاش مجدد
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <div className="space-y-4" aria-busy="true" aria-live="polite">
        <span className="sr-only">در حال آماده‌سازی پیشنهادهای امروز…</span>
        <Skeleton className="h-40 w-full rounded-2xl" />
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (!data.active) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-12 text-center">
          <ClipboardCheck className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm font-semibold">برای این دانش‌آموز پیشنهاد روزانه ساخته نمی‌شود</p>
          <p className="mx-auto mt-1 max-w-md text-xs leading-6 text-muted-foreground">
            پرونده حفظ شده است، اما تا فعال‌شدن دوبارهٔ همکاری پیشنهاد تازه‌ای ساخته نمی‌شود.
          </p>
        </CardContent>
      </Card>
    );
  }

  const evidenceEntries = Object.entries(data.evidence);
  const primaryRecommendation = data.recommendations[0];

  return (
    <div className="space-y-4" aria-live="polite">
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="rounded-xl bg-primary/10 p-2">
                  <ClipboardCheck className="h-5 w-5 text-primary" />
                </span>
                پیشنهادهای امروز
              </CardTitle>
              <p className="mt-2 text-xs leading-6 text-muted-foreground">
                بر اساس گزارش‌های ثبت‌شدهٔ دانش‌آموز؛ به‌روزرسانی: {formatPersianDate(data.asOf)}
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {data.recommendations.length === 0 ? (
            <div className="rounded-xl border border-dashed p-5 text-center">
              <p className="text-sm font-medium">فعلاً پیشنهاد فوری‌ای وجود ندارد</p>
              <p className="mt-1 text-xs leading-6 text-muted-foreground">
                داده‌های فعلی نشانهٔ قطعی برای تغییر برنامه یا پیگیری آزمون نشان نمی‌دهند.
              </p>
            </div>
          ) : (
            <ol className="space-y-3">
              {data.recommendations.map((recommendation, index) => (
                <li key={recommendation.code ?? `${recommendation.title}-${index}`} className="rounded-xl border border-border/60 bg-background p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold">{recommendation.title}</p>
                      {recommendationBody(recommendation) && (
                        <p className="mt-1 text-xs leading-6 text-muted-foreground">
                          {recommendationBody(recommendation)}
                        </p>
                      )}
                    </div>
                    {recommendation.priority && (
                      <Badge variant="secondary" className="shrink-0 font-normal">
                        {PRIORITY_LABELS[recommendation.priority]}
                      </Badge>
                    )}
                  </div>
                  {recommendation.evidenceKeys && recommendation.evidenceKeys.length > 0 && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      بر پایهٔ: {recommendation.evidenceKeys.map((key) => EVIDENCE_LABELS[key] ?? key).join('، ')}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}

          {primaryRecommendation && (
            <Button asChild className="mt-4 h-11 w-full sm:w-auto">
              <Link href={actionHref(engagementId, primaryRecommendation.actionArea)}>
                دیدن جزئیات
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <BarChart3 className="h-4 w-4 text-primary" />
            شاخص‌های دانش‌آموز
          </CardTitle>
        </CardHeader>
        <CardContent>
          {evidenceEntries.length === 0 ? (
            <p className="py-5 text-center text-xs leading-6 text-muted-foreground">
              هنوز دادهٔ کافی برای نمایش وضعیت دانش‌آموز ثبت نشده است.
            </p>
          ) : (
            <dl className="grid gap-2 sm:grid-cols-2">
              {evidenceEntries.map(([key, value]) => (
                <div key={key} className="rounded-xl bg-muted/60 p-3">
                  <dt className="text-xs text-muted-foreground">{EVIDENCE_LABELS[key] ?? key}</dt>
                  <dd
                    className="mt-1 text-sm font-semibold tabular-nums"
                    title={
                      key === 'planCalibration' && typeof value === 'number'
                        ? 'نسبت دقیقهٔ برنامه به اجرا؛ ۱۰۰٪ یعنی مطابق برنامه'
                        : undefined
                    }
                  >
                    {evidenceValueLabel(key, value)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <div className="mt-4 flex flex-wrap gap-2 border-t border-border/60 pt-4">
            <Button asChild variant="outline" className="h-11">
              <Link href={`/advisor/students/${engagementId}?tab=activity`}>
                <BarChart3 className="h-4 w-4" />
                گزارش مطالعه
              </Link>
            </Button>
            <Button asChild variant="outline" className="h-11">
              <Link href={`/advisor/students/${engagementId}?tab=record`}>
                <CalendarCheck2 className="h-4 w-4" />
                نتایج آزمون‌ها
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
