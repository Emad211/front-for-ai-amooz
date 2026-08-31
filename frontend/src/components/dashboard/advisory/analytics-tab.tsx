'use client';

import { useEffect, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlarmClock,
  BarChart3,
  CalendarClock,
  Flame,
  Target,
  TrendingUp,
} from 'lucide-react';

import {
  AdvisoryService,
  type AnalyticsPayload,
  type MistakeErrorType,
} from '@/services/advisory-service';
import { toPersianDigits } from '@/lib/persian-digits';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const ERROR_LABELS: Record<MistakeErrorType, string> = {
  CONCEPT: 'مفهومی',
  FORGET: 'فراموشی',
  METHOD: 'تشخیص روش',
  EXECUTION: 'محاسباتی',
  READING: 'خواندن سؤال',
  TIME: 'مدیریت زمان',
};

const ERROR_COLORS: Record<MistakeErrorType, string> = {
  CONCEPT: '#ef4444',
  FORGET: '#f59e0b',
  METHOD: '#3b82f6',
  EXECUTION: '#a855f7',
  READING: '#14b8a6',
  TIME: '#ec4899',
};

function StatChip({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-card px-3 py-2">
      <span className="rounded-lg bg-muted p-1.5">{icon}</span>
      <div className="min-w-0">
        <p className="text-[11px] text-muted-foreground">{label}</p>
        <p className="text-sm font-bold tabular-nums">{value}</p>
      </div>
    </div>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="py-8 text-center text-xs text-muted-foreground">{children}</p>;
}

export function AnalyticsTab() {
  const [data, setData] = useState<AnalyticsPayload | null>(null);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyAnalytics()
      .then((res) => {
        if (active && res.active) setData(res);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  if (!data) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-64 w-full rounded-2xl" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  const trend = data.examTrend.map((e) => ({
    name: e.title || 'آزمون',
    percent: e.score_percent ?? 0,
    tara: e.tara ?? 0,
  }));

  const balanceTotal = data.subjectBalance.reduce((s, b) => s + b.minutes, 0);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatChip
          icon={<Flame className="h-4 w-4 text-orange-500" />}
          label="روز پیوستهٔ ثبت گزارش"
          value={toPersianDigits(data.streak)}
        />
        <StatChip
          icon={<AlarmClock className="h-4 w-4 text-primary" />}
          label="گزارش امروز"
          value={data.loggedToday ? 'ثبت شد' : 'هنوز نه'}
        />
        <StatChip
          icon={<CalendarClock className="h-4 w-4 text-amber-500" />}
          label="عقب‌افتادگی جبران‌نشده"
          value={toPersianDigits(data.backlogTotal)}
        />
        <StatChip
          icon={<Target className="h-4 w-4 text-destructive" />}
          label="خطای باز دفتر اشتباهات"
          value={toPersianDigits(data.openMistakes)}
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card className="rounded-2xl">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-bold">
              <TrendingUp className="h-4 w-4 text-primary" />
              روند آزمون‌ها (درصد)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {trend.length < 2 ? (
              <EmptyNote>
                برای رسم روند، دست‌کم دو نمرهٔ آزمون لازم است — از تب «آزمون‌ها» یا
                دفتر مشاور ثبت می‌شود.
              </EmptyNote>
            ) : (
              <div className="h-56" dir="ltr">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 10 }}
                      stroke="hsl(var(--muted-foreground))"
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 10 }}
                      stroke="hsl(var(--muted-foreground))"
                    />
                    <Tooltip
                      contentStyle={{
                        direction: 'rtl',
                        borderRadius: 12,
                        fontSize: 12,
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="percent"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2.5}
                      dot={{ r: 4 }}
                      name="درصد"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-bold">
              <BarChart3 className="h-4 w-4 text-primary" />
              تعادل مطالعاتی (۳۰ روز اخیر)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {balanceTotal === 0 ? (
              <EmptyNote>
                هنوز دقیقه‌ای ثبت نشده؛ با گزارش روزانه، سهم هر درس این‌جا دیده می‌شود.
              </EmptyNote>
            ) : (
              <ul className="space-y-2.5">
                {data.subjectBalance.map((row) => {
                  const pct = Math.round((row.minutes / balanceTotal) * 100);
                  return (
                    <li key={row.name} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="truncate font-medium">{row.name}</span>
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {toPersianDigits(row.minutes)} دقیقه ·{' '}
                          {toPersianDigits(pct)}٪
                        </span>
                      </div>
                      <div
                        className="h-2 w-full overflow-hidden rounded-full bg-muted"
                        role="progressbar"
                        aria-valuenow={pct}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`سهم ${row.name}`}
                      >
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card className="rounded-2xl">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-bold">
              <Target className="h-4 w-4 text-primary" />
              اجرای برنامهٔ جاری
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.planExecution?.percent != null ? (
              <div className="space-y-2">
                <p className="text-3xl font-black tabular-nums text-primary">
                  {toPersianDigits(data.planExecution.percent)}٪
                </p>
                <p className="text-xs text-muted-foreground">
                  پایبندی به برنامهٔ {data.planExecution.startDate} تا{' '}
                  {data.planExecution.endDate} — دقیقهٔ ثبت‌شده ÷ دقیقهٔ برنامه تا امروز.
                </p>
                <div
                  className="h-2.5 w-full overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-valuenow={data.planExecution.percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="درصد اجرای برنامه"
                >
                  <div
                    className={cn(
                      'h-full rounded-full',
                      data.planExecution.percent >= 80
                        ? 'bg-emerald-500'
                        : data.planExecution.percent >= 50
                          ? 'bg-amber-500'
                          : 'bg-red-500',
                    )}
                    style={{
                      width: `${Math.min(100, data.planExecution.percent)}%`,
                    }}
                  />
                </div>
              </div>
            ) : (
              <EmptyNote>فعلاً برنامهٔ جاریِ در حال اجرایی نداری.</EmptyNote>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-bold">
              <CalendarClock className="h-4 w-4 text-primary" />
              عقب‌افتادگی‌ها و مرورهای امروز
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.backlog.length === 0 && data.reviewDue.length === 0 ? (
              <EmptyNote>همه‌چیز جبران شده — عقب‌مانده‌ای نیست. 🎉</EmptyNote>
            ) : (
              <>
                {data.backlog.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="text-[11px] font-semibold text-muted-foreground">
                      ردیف‌های برنامهٔ گذشته که کامل اجرا نشده‌اند
                    </p>
                    <ul className="space-y-1">
                      {data.backlog.map((row, i) => (
                        <li
                          key={`${row.date}-${row.subject}-${i}`}
                          className="flex items-center justify-between gap-2 rounded-lg border border-border/50 bg-background/60 px-2.5 py-1.5 text-[11px]"
                        >
                          <span className="min-w-0 truncate">
                            {row.subject}
                            {row.topic ? ` · ${row.topic}` : ''}
                          </span>
                          <span className="shrink-0 tabular-nums text-muted-foreground">
                            {toPersianDigits(row.actual)} از{' '}
                            {toPersianDigits(row.planned)} دقیقه
                          </span>
                        </li>
                      ))}
                    </ul>
                    {data.backlogTotal > data.backlog.length && (
                      <p className="text-[10px] text-muted-foreground">
                        و {toPersianDigits(data.backlogTotal - data.backlog.length)}{' '}
                        مورد قدیمی‌تر…
                      </p>
                    )}
                  </div>
                )}
                {data.reviewDue.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="text-[11px] font-semibold text-muted-foreground">
                      مباحث رسیده به وقت مرور
                    </p>
                    <ul className="flex flex-wrap gap-1.5">
                      {data.reviewDue.map((row) => (
                        <li
                          key={row.id}
                          className="rounded-full bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-600 dark:text-amber-400"
                        >
                          {row.student_subject__subject__name} · {row.topic}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {data.openMistakes > 0 && (
        <Card className="rounded-2xl">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold">
              خطاهای باز بر اساس نوع
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-wrap gap-2">
              {(Object.keys(ERROR_LABELS) as MistakeErrorType[]).map((code) => {
                const count = data.mistakesByType[code] ?? 0;
                if (count === 0) return null;
                return (
                  <li
                    key={code}
                    className="flex items-center gap-1.5 rounded-full border border-border/60 bg-background/60 px-3 py-1.5 text-xs"
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: ERROR_COLORS[code] }}
                    />
                    {ERROR_LABELS[code]}
                    <span className="font-bold tabular-nums">
                      {toPersianDigits(count)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
