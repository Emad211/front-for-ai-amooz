'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, ClipboardList, Download } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { toPersianDigits } from '@/lib/persian-digits';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  downloadPlannerReportXlsx,
  getPlannerReport,
  type PlannerReport,
} from '@/services/advisory-reports';

/** Range chips in days; default mirrors the study feed's «۷ روز». */
const RANGE_CHIPS = [7, 14, 30] as const;
type RangeDays = (typeof RANGE_CHIPS)[number];

/** Segmented-chip styles — the shared design language L5 (see study-feed-card). */
const SEGMENT_SELECTED =
  'h-8 rounded-lg border-primary bg-primary/10 px-3 text-xs font-medium text-primary shadow-none hover:bg-primary/15 hover:text-primary';
const SEGMENT_IDLE =
  'h-8 rounded-lg px-3 text-xs text-muted-foreground hover:bg-muted/40 hover:text-muted-foreground';

/** Locked adherence palette, text-only variant (>=80 green / >=50 amber / else red). */
function coverageTextClass(percent: number | null): string {
  if (percent === null) return 'text-muted-foreground';
  if (percent >= 80) return 'text-emerald-600 dark:text-emerald-400';
  if (percent >= 50) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

function rangeWindow(days: RangeDays): { from: string; to: string } {
  const today = new Date();
  const from = new Date(today);
  from.setDate(today.getDate() - (days - 1));
  return { from: isoDate(from), to: isoDate(today) };
}

type PlannerReportCardProps = {
  engagementId: number;
};

/**
 * «گزارش برنامه» — planned-vs-actual over a selectable trailing window.
 *
 * One GET per range selection; the body is a per-subject bar chart plus the
 * subjects table (planned / actual / colored coverage) closed by a totals
 * row. The Excel button streams the same report as an xlsx blob download.
 */
export function PlannerReportCard({ engagementId }: PlannerReportCardProps) {
  const [range, setRange] = useState<RangeDays>(7);
  const [report, setReport] = useState<PlannerReport | null>(null);
  const [error, setError] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const windowDates = useMemo(() => rangeWindow(range), [range]);

  useEffect(() => {
    let active = true;
    setError('');
    setReport(null);

    getPlannerReport(engagementId, windowDates.from, windowDates.to)
      .then((data) => {
        if (active) setReport(data);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [engagementId, windowDates.from, windowDates.to, reloadKey]);

  const loading = !report && !error;

  const chartData = useMemo(
    () =>
      (report?.subjects ?? []).map((subject) => ({
        name: subject.name,
        planned: subject.planned,
        actual: subject.actual,
      })),
    [report],
  );

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadPlannerReportXlsx(engagementId, windowDates.from, windowDates.to);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'خطای نامشخص');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="p-5 pb-4">
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <ClipboardList className="h-4 w-4 text-primary" />
            گزارش برنامه
          </CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading || downloading}
            onClick={handleDownload}
          >
            <Download className="ml-1.5 h-4 w-4" />
            {downloading ? 'در حال دریافت…' : 'خروجی اکسل'}
          </Button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="بازه‌ی گزارش">
            {RANGE_CHIPS.map((days) => {
              const selected = range === days;
              return (
                <Button
                  key={days}
                  type="button"
                  variant={selected ? 'default' : 'outline'}
                  disabled={loading}
                  onClick={() => setRange(days)}
                  aria-pressed={selected}
                  className={selected ? SEGMENT_SELECTED : SEGMENT_IDLE}
                >
                  {toPersianDigits(days)} روز
                </Button>
              );
            })}
          </div>
          {!loading && report && (
            <span className="text-xs text-muted-foreground">
              از {toPersianDigits(windowDates.from)} تا {toPersianDigits(windowDates.to)}
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-5 pt-0 sm:p-5 sm:pt-0">
        {loading && (
          <div className="space-y-2" aria-busy="true" aria-live="polite">
            <span className="sr-only">در حال بارگذاری گزارش برنامه…</span>
            <Skeleton className="h-40 w-full rounded-xl" />
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-9 w-full rounded-xl" />
            ))}
          </div>
        )}

        {!loading && error && (
          <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </p>
        )}

        {!loading && !error && report && (
          <div className="space-y-5">
            {chartData.length > 0 ? (
              <div className="h-[220px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="name"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                      dy={8}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      allowDecimals={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        borderColor: 'hsl(var(--border))',
                        borderRadius: '12px',
                        fontSize: '12px',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '6px' }} />
                    <Bar dataKey="planned" name="برنامه‌ریزی‌شده" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} maxBarSize={36} />
                    <Bar dataKey="actual" name="انجام‌شده" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={36} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="py-6 text-center text-xs text-muted-foreground">
                در این بازه برنامه یا مطالعه‌ای ثبت نشده است.
              </p>
            )}

            {report.subjects.length > 0 && (
              <div className="overflow-hidden rounded-xl border border-border/50">
                <table className="w-full text-right text-sm">
                  <thead>
                    <tr className="bg-muted/40 text-xs text-muted-foreground">
                      <th scope="col" className="px-3 py-2 font-medium">درس</th>
                      <th scope="col" className="px-3 py-2 font-medium">برنامه‌ریزی‌شده</th>
                      <th scope="col" className="px-3 py-2 font-medium">انجام‌شده</th>
                      <th scope="col" className="px-3 py-2 font-medium">پوشش٪</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {report.subjects.map((subject) => (
                      <tr key={subject.subjectId}>
                        <td className="px-3 py-2">{subject.name}</td>
                        <td className="px-3 py-2 tabular-nums text-muted-foreground">
                          {toPersianDigits(subject.planned)}
                        </td>
                        <td className="px-3 py-2 tabular-nums">
                          {toPersianDigits(subject.actual)}
                        </td>
                        <td
                          className={`px-3 py-2 text-xs font-medium tabular-nums ${coverageTextClass(subject.coveragePercent)}`}
                        >
                          {subject.coveragePercent === null
                            ? '—'
                            : toPersianDigits(subject.coveragePercent)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-border/60 bg-muted/20 font-medium">
                      <td className="px-3 py-2">جمع</td>
                      <td className="px-3 py-2 tabular-nums text-muted-foreground">
                        {toPersianDigits(report.totals.planned)}
                      </td>
                      <td className="px-3 py-2 tabular-nums">
                        {toPersianDigits(report.totals.actual)}
                      </td>
                      <td
                        className={`px-3 py-2 text-xs font-medium tabular-nums ${coverageTextClass(report.totals.coveragePercent)}`}
                      >
                        {report.totals.coveragePercent === null
                          ? '—'
                          : toPersianDigits(report.totals.coveragePercent)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
