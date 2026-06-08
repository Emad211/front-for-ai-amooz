'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';
import { Wallet, Activity, Cpu, Info } from 'lucide-react';
import { TeacherService } from '@/services/teacher-service';
import { formatPersianNumber } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import type { MyAiUsage } from '@/types';

const RANGE_OPTIONS = [
  { value: '7', label: '۷ روز' },
  { value: '30', label: '۳۰ روز' },
  { value: '90', label: '۹۰ روز' },
  { value: '365', label: 'یک سال' },
];

const CHART_COLOR = '#10b981';

export default function UsagePage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<MyAiUsage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    TeacherService.getMyAiUsage(days)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) toast.error('دریافت اطلاعات مصرف با خطا مواجه شد.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  const summary = data?.summary;
  const byFeature = data?.byFeature ?? [];
  const chartData = (data?.daily ?? []).map((d) => ({
    label: d.date ? formatPersianDate(d.date) : '—',
    toman: d.costToman,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">مصرف و هزینه من</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            هزینه پردازش‌های هوش مصنوعی در فضای شخصی شما (کارهای سازمانی جداگانه محاسبه می‌شود).
          </p>
        </div>
        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="w-full sm:w-44">
            <SelectValue placeholder="بازه زمانی" />
          </SelectTrigger>
          <SelectContent>
            {RANGE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <Skeleton className="h-28 rounded-2xl" />
            <Skeleton className="h-28 rounded-2xl" />
            <Skeleton className="h-28 rounded-2xl" />
          </div>
          <Skeleton className="h-80 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      ) : (
        <>
          {/* Summary */}
          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="rounded-2xl border-border/50 shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">هزینه کل</CardTitle>
                <Wallet className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-primary">
                  {`${formatPersianNumber(Math.round(summary?.totalCostToman ?? 0))} تومان`}
                </div>
              </CardContent>
            </Card>
            <Card className="rounded-2xl border-border/50 shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">تعداد درخواست</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatPersianNumber(summary?.totalRequests ?? 0)}</div>
              </CardContent>
            </Card>
            <Card className="rounded-2xl border-border/50 shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">مجموع توکن</CardTitle>
                <Cpu className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatPersianNumber(summary?.totalTokens ?? 0)}</div>
              </CardContent>
            </Card>
          </div>

          {/* Daily chart */}
          <Card className="rounded-2xl border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold">روند هزینه روزانه</CardTitle>
            </CardHeader>
            <CardContent>
              {chartData.length === 0 ? (
                <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                  داده‌ای برای این بازه نیست
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                    <defs>
                      <linearGradient id="myTomanFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={CHART_COLOR} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={CHART_COLOR} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} tickMargin={8} stroke="currentColor" className="text-muted-foreground" />
                    <YAxis tick={{ fontSize: 11 }} width={70} stroke="currentColor" className="text-muted-foreground" tickFormatter={(v) => formatPersianNumber(v as number)} />
                    <Tooltip
                      formatter={(value) => [`${formatPersianNumber(Math.round(value as number))} تومان`, 'هزینه']}
                      labelStyle={{ direction: 'rtl' }}
                      contentStyle={{ borderRadius: 12, border: '1px solid hsl(var(--border))', background: 'hsl(var(--background))', fontSize: 12 }}
                    />
                    <Area type="monotone" dataKey="toman" stroke={CHART_COLOR} strokeWidth={2} fill="url(#myTomanFill)" fillOpacity={0.15} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* By feature */}
          <Card className="rounded-2xl border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold">هزینه به تفکیک قابلیت</CardTitle>
            </CardHeader>
            <CardContent>
              {byFeature.length === 0 ? (
                <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                  هنوز مصرفی ثبت نشده است
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>قابلیت</TableHead>
                      <TableHead>درخواست</TableHead>
                      <TableHead>توکن</TableHead>
                      <TableHead>هزینه</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {byFeature.map((row) => (
                      <TableRow key={row.feature}>
                        <TableCell className="font-medium">{row.featureLabel}</TableCell>
                        <TableCell>{formatPersianNumber(row.requests)}</TableCell>
                        <TableCell>{formatPersianNumber(row.tokens)}</TableCell>
                        <TableCell>{`${formatPersianNumber(Math.round(row.costToman))} تومان`}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <Info className="h-3.5 w-3.5 shrink-0" />
            هزینه‌ها بر اساس نرخ لحظه ثبت محاسبه شده‌اند و فقط شامل فضای شخصی شماست.
          </p>
        </>
      )}
    </div>
  );
}
