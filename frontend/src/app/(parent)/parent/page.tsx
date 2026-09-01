'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CalendarDays,
  Clock,
  Flame,
  HeartHandshake,
  ListChecks,
  RefreshCw,
  TrendingUp,
} from 'lucide-react';
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
  getDigest,
  getMyLinks,
  type ParentDigest,
  type ParentLinkItem,
} from '@/services/parent-service';
import { getStoredUser } from '@/services/auth-service';
import { adherenceColorClass, formatAdherence } from '@/lib/adherence';
import { formatPersianDate, formatPersianMonthDay } from '@/lib/date-utils';
import { formatPersianNumber, formatPersianPercent, toPersianDigits } from '@/lib/persian-digits';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';

/** Relation codes → the exact labels of the parent contract (پدر/مادر/سرپرست).
 * An already-Persian value passes through untouched; null hides the badge. */
const RELATION_LABELS: Record<string, string> = {
  FATHER: 'پدر',
  MOTHER: 'مادر',
  GUARDIAN: 'سرپرست',
};

function relationLabel(relation: string | null): string | null {
  if (!relation || !relation.trim()) return null;
  return RELATION_LABELS[relation.trim().toUpperCase()] ?? relation.trim();
}

/** «۳ ساعت و ۲۰ دقیقه» — hours+minutes from weekMinutes. The null case is
 * handled by the caller (different sentence, no «مطالعه» suffix). */
function studyDurationLabel(weekMinutes: number): string {
  const hours = Math.floor(weekMinutes / 60);
  const minutes = weekMinutes % 60;
  const hoursPart = hours > 0 ? `${toPersianDigits(hours)} ساعت` : '';
  const minutesPart = minutes > 0 ? `${toPersianDigits(minutes)} دقیقه` : '';
  if (hoursPart && minutesPart) return `${hoursPart} و ${minutesPart}`;
  if (hoursPart) return hoursPart;
  if (minutesPart) return minutesPart;
  return '۰ دقیقه';
}

/* ── One child's digest card (fetches its own digest; degrades alone) ───── */

function ChildDigestCard({ link }: { link: ParentLinkItem }) {
  const [digest, setDigest] = useState<ParentDigest | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setDigest(null);
    setError('');

    getDigest(link.id)
      .then((data) => {
        if (active) setDigest(data);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [link.id, reloadKey]);

  const loading = !digest && !error;
  const relation = relationLabel(link.relation);

  // The line draws scorePercent only — points without one are skipped.
  const chartData = useMemo(
    () =>
      (digest?.examTrend ?? [])
        .filter((p) => p.scorePercent !== null)
        .map((p) => ({
          day: formatPersianMonthDay(p.date),
          score: p.scorePercent,
        })),
    [digest],
  );

  return (
    <Card className="rounded-2xl border-border/50" aria-live="polite">
      <CardContent className="space-y-5 p-4 sm:p-6">
        {/* ── child identity ─────────────────────────────────────────── */}
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-bold sm:text-xl">{link.studentName}</h2>
            {relation && (
              <Badge
                variant="outline"
                className="border-primary/20 bg-primary/10 px-3 py-1 text-base text-primary"
              >
                {relation}
              </Badge>
            )}
          </div>
          {link.advisorName && (
            <p className="mt-1 text-base text-muted-foreground">
              مشاور: {link.advisorName}
            </p>
          )}
        </div>

        {loading ? (
          <div aria-busy="true">
            <span className="sr-only">در حال بارگذاری گزارش…</span>
            <Skeleton className="h-48 rounded-2xl" />
          </div>
        ) : error ? (
          <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-4">
            <p className="flex items-center gap-2 text-base text-destructive">
              <AlertCircle className="h-5 w-5 shrink-0" />
              {error}
            </p>
            <Button
              variant="outline"
              className="mt-3 h-12 rounded-xl px-4 text-base"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              <RefreshCw className="ml-2 h-4 w-4" />
              تلاش مجدد
            </Button>
          </div>
        ) : (
          digest && (
            <>
              {/* ── this week's study time (the headline) ─────────────── */}
              <div className="rounded-xl bg-muted/60 p-4">
                <p className="flex items-center gap-2 text-xl font-bold leading-relaxed tabular-nums sm:text-2xl">
                  <Clock className="h-6 w-6 shrink-0 text-muted-foreground" />
                  {digest.weekMinutes === null
                    ? 'این هفته: هنوز مطالعه‌ای ثبت نشده'
                    : `این هفته: ${studyDurationLabel(digest.weekMinutes)} مطالعه`}
                </p>
                {digest.weekMinutes !== null && digest.weekPlanMinutes !== null && (
                  <p className="mt-2 text-base text-muted-foreground tabular-nums">
                    برنامهٔ این هفته: {studyDurationLabel(digest.weekPlanMinutes)}
                  </p>
                )}
                {digest.adherencePercent === null ? (
                  <p className="mt-2 text-base text-muted-foreground">
                    برنامه‌ای ثبت نشده
                  </p>
                ) : (
                  <span
                    title="چقدر از برنامهٔ این هفته انجام شد"
                    className={`mt-3 inline-flex items-center rounded-lg px-3 py-1.5 text-base font-bold tabular-nums ${adherenceColorClass(
                      digest.adherencePercent,
                    )}`}
                  >
                    {formatAdherence(digest.adherencePercent)} از برنامه
                  </span>
                )}
              </div>

              {/* ── tests / challenge / streak strip ──────────────────── */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <Badge
                  variant="outline"
                  className="gap-1.5 bg-muted px-3 py-1.5 text-base tabular-nums text-foreground"
                >
                  <ListChecks className="h-4 w-4 text-muted-foreground" />
                  تست این هفته: {formatPersianNumber(digest.testsTaken)}
                </Badge>
                {digest.activeChallengeTitle && (
                  <Badge
                    variant="outline"
                    className="border-primary/20 bg-primary/10 px-3 py-1.5 text-base text-primary"
                  >
                    چالش: {digest.activeChallengeTitle}
                  </Badge>
                )}
                {digest.streak !== null && digest.streak > 0 && (
                  <span className="flex items-center gap-1.5 text-base tabular-nums text-foreground">
                    <Flame className="h-5 w-5 text-primary" />
                    {toPersianDigits(digest.streak)} روز پیوسته گزارش داده
                  </span>
                )}
              </div>

              {/* ── exam trend mini line-chart ────────────────────────── */}
              <div>
                <h3 className="flex items-center gap-1.5 text-base font-semibold">
                  <TrendingUp className="h-5 w-5 text-primary" />
                  روند آزمون‌ها
                </h3>
                {chartData.length >= 2 && (
                  <p className="mt-1 text-base text-muted-foreground tabular-nums">
                    آخرین نتیجه: {formatPersianPercent(chartData[chartData.length - 1].score)} ·
                    اولین: {formatPersianPercent(chartData[0].score)}
                  </p>
                )}
                {chartData.length > 0 ? (
                  <div className="mt-2 h-40 w-full" dir="ltr">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={chartData}
                        margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          vertical={false}
                          stroke="hsl(var(--border))"
                        />
                        <XAxis
                          dataKey="day"
                          axisLine={false}
                          tickLine={false}
                          tick={{
                            fill: 'hsl(var(--muted-foreground))',
                            fontSize: 12,
                          }}
                          dy={6}
                        />
                        <YAxis
                          domain={[0, 100]}
                          axisLine={false}
                          tickLine={false}
                          allowDecimals={false}
                          tickFormatter={(value) => toPersianDigits(value)}
                          tick={{
                            fill: 'hsl(var(--muted-foreground))',
                            fontSize: 12,
                          }}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'hsl(var(--card))',
                            borderColor: 'hsl(var(--border))',
                            borderRadius: '12px',
                            fontSize: '13px',
                          }}
                          formatter={(value) =>
                            [
                              `${toPersianDigits(String(value))}٪`,
                              'درصد',
                            ] as [string, string]
                          }
                        />
                        <Line
                          type="monotone"
                          dataKey="score"
                          stroke="hsl(var(--primary))"
                          strokeWidth={2}
                          dot={{ r: 3, fill: 'hsl(var(--primary))' }}
                          activeDot={{ r: 4 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="mt-1 text-base text-muted-foreground">
                    هنوز آزمونی ثبت نشده
                  </p>
                )}
              </div>

              {/* ── follow-up counters ────────────────────────────────── */}
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="flex items-center justify-between gap-2 rounded-xl bg-muted/40 px-4 py-3">
                  <span className="flex items-center gap-2 text-base text-muted-foreground">
                    <AlertCircle className="h-5 w-5 shrink-0" />
                    اشتباه‌های رفع‌نشده
                  </span>
                  <span className="text-base font-bold tabular-nums">
                    {formatPersianNumber(digest.openMistakesCount)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2 rounded-xl bg-muted/40 px-4 py-3">
                  <span className="flex items-center gap-2 text-base text-muted-foreground">
                    <RefreshCw className="h-5 w-5 shrink-0" />
                    مباحث نیازمند مرور
                  </span>
                  <span className="text-base font-bold tabular-nums">
                    {formatPersianNumber(digest.reviewDueCount)}
                  </span>
                </div>
              </div>

              {/* ── freshness footer ──────────────────────────────────── */}
              {digest.asOf && (
                <>
                  <Separator />
                  <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <CalendarDays className="h-4 w-4 shrink-0" />
                    به‌روزرسانی: {formatPersianDate(digest.asOf)}
                  </p>
                </>
              )}
            </>
          )
        )}
      </CardContent>
    </Card>
  );
}

/* ── The panel index: links list → one card per ACTIVE link ────────────── */

export default function ParentDashboardPage() {
  const [name, setName] = useState('');
  const [links, setLinks] = useState<ParentLinkItem[] | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setName(getStoredUser()?.first_name ?? '');
  }, []);

  useEffect(() => {
    let active = true;
    setLinks(null);
    setError('');

    getMyLinks()
      .then((data) => {
        if (active) setLinks(data);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [reloadKey]);

  const loading = !links && !error;

  // One child is expected, but the map stays general — the card owns its own
  // digest fetch so multiple children degrade independently.
  const activeLinks = (links ?? []).filter((l) => l.status === 'ACTIVE');

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold sm:text-2xl">
          {name ? `${name} عزیز، خوش آمدید` : 'گزارش فرزند شما'}
        </h1>
        <p className="mt-1.5 text-base leading-relaxed text-muted-foreground">
          خلاصهٔ هفتگی مطالعه، آزمون‌ها و چالش‌های فرزندتان.
        </p>
      </div>

      <div aria-live="polite">
        {loading ? (
          <div aria-busy="true">
            <span className="sr-only">در حال بارگذاری گزارش‌ها…</span>
            <Skeleton className="h-72 rounded-2xl" />
          </div>
        ) : error ? (
          <Card className="border-destructive/40 bg-destructive/5">
            <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
              <p className="flex items-center gap-2 text-base text-destructive">
                <AlertCircle className="h-5 w-5 shrink-0" />
                {error}
              </p>
              <Button
                variant="outline"
                className="h-12 rounded-xl px-4 text-base"
                onClick={() => setReloadKey((k) => k + 1)}
              >
                <RefreshCw className="ml-2 h-4 w-4" />
                تلاش مجدد
              </Button>
            </CardContent>
          </Card>
        ) : activeLinks.length === 0 ? (
          <Card className="rounded-2xl border-border/50">
            <CardContent className="flex flex-col items-center gap-3 px-6 py-12 text-center">
              <span className="rounded-full bg-primary/10 p-3">
                <HeartHandshake className="h-6 w-6 text-primary" />
              </span>
              <p className="text-lg font-bold">هنوز گزارشی برای شما فعال نیست</p>
              <p className="max-w-sm text-base leading-relaxed text-muted-foreground">
                مشاور فرزند شما شمارهٔ شما را ثبت می‌کند؛ پس از آن گزارش
                هفتگی فرزندتان را همین‌جا می‌بینید.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-5">
            {activeLinks.map((link) => (
              <ChildDigestCard key={link.id} link={link} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
