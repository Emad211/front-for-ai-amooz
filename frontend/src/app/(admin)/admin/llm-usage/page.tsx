'use client';

import { useEffect, useState, useCallback } from 'react';
import { AdminService } from '@/services/admin-service';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageTransition } from '@/components/ui/page-transition';
import { ErrorState } from '@/components/shared/error-state';
import { formatPersianDateTime, formatPersianMonthDay } from '@/lib/date-utils';
import {
  Coins,
  TrendingUp,
  AlertCircle,
  Clock,
  RefreshCw,
  DollarSign,
  Zap,
  Users,
  Layers,
  Server,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface Summary {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_duration_ms: number;
  total_audio_input_tokens: number;
  total_cached_input_tokens: number;
  total_thinking_tokens: number;
  total_cost_toman: number | null;
  usdt_toman_rate: number | null;
}

interface ByFeature {
  feature: string;
  feature_label: string;
  count: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_duration_ms: number;
}

interface ByUser {
  user_id: number | null;
  username: string;
  full_name: string;
  role: string;
  count: number;
  total_tokens: number;
  total_cost_usd: number;
}

interface ByProvider {
  provider: string;
  count: number;
  total_tokens: number;
  total_cost_usd: number;
}

interface DailyData {
  date: string;
  count: number;
  total_tokens: number;
  total_cost_usd: number;
}

interface RecentLog {
  id: number;
  user: string | null;
  feature: string;
  provider: string;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  audio_input_tokens: number;
  cached_input_tokens: number;
  thinking_tokens: number;
  estimated_cost_usd: number;
  duration_ms: number;
  success: boolean;
  created_at: string;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function formatNumber(n: number): string {
  return new Intl.NumberFormat('fa-IR').format(n);
}

function formatCost(usd: number): string {
  if (usd < 0.001) return '$0.00';
  return `$${usd.toFixed(4)}`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatToman(amount: number | null): string {
  if (amount === null || amount === undefined) return '—';
  return `${new Intl.NumberFormat('fa-IR').format(Math.round(amount))} تومان`;
}

const ROLE_MAP: Record<string, string> = {
  admin: 'مدیر',
  teacher: 'معلم',
  student: 'دانش‌آموز',
};

const DAYS_OPTIONS = [7, 14, 30, 60, 90];

const ROLE_FILTER_OPTIONS = [
  { value: '', label: 'همه' },
  { value: 'teacher', label: 'معلم' },
  { value: 'student', label: 'دانش‌آموز' },
  { value: 'admin', label: 'مدیر' },
];

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function LLMUsagePage() {
  const [days, setDays] = useState(30);
  const [roleFilter, setRoleFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<Summary | null>(null);
  const [byFeature, setByFeature] = useState<ByFeature[]>([]);
  const [byUser, setByUser] = useState<ByUser[]>([]);
  const [byProvider, setByProvider] = useState<ByProvider[]>([]);
  const [daily, setDaily] = useState<DailyData[]>([]);
  const [recentLogs, setRecentLogs] = useState<RecentLog[]>([]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, f, u, p, d, r] = await Promise.all([
        AdminService.getLLMUsageSummary(days),
        AdminService.getLLMUsageByFeature(days),
        AdminService.getLLMUsageByUser(days, roleFilter || undefined),
        AdminService.getLLMUsageByProvider(days),
        AdminService.getLLMUsageDaily(days),
        AdminService.getLLMUsageRecentLogs(50),
      ]);
      setSummary(s);
      setByFeature(f);
      setByUser(u);
      setByProvider(p);
      setDaily(d);
      setRecentLogs(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در دریافت اطلاعات');
    } finally {
      setLoading(false);
    }
  }, [days, roleFilter]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  /* ---------- Loading ---------- */
  if (loading) {
    return (
      <PageTransition>
        <div className="space-y-6">
          <Skeleton className="h-10 w-64" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-2xl" />
            ))}
          </div>
          <Skeleton className="h-80 rounded-2xl" />
        </div>
      </PageTransition>
    );
  }

  /* ---------- Error ---------- */
  if (error) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center h-[60vh] px-4">
          <div className="w-full max-w-2xl">
            <ErrorState title="خطا در دریافت اطلاعات مصرف" description={error} onRetry={fetchAll} />
          </div>
        </div>
      </PageTransition>
    );
  }

  const s = summary!;

  /* ---------- Render ---------- */
  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-black text-foreground">مصرف توکن LLM</h1>
            <p className="text-muted-foreground text-sm mt-1">
              گزارش دقیق مصرف توکن‌های هوش مصنوعی و هزینه‌ها
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {DAYS_OPTIONS.map((d) => (
              <Button
                key={d}
                variant={days === d ? 'default' : 'outline'}
                size="sm"
                className="h-8 rounded-xl text-xs"
                onClick={() => setDays(d)}
              >
                {d} روز
              </Button>
            ))}
            <Button variant="ghost" size="sm" className="h-8 rounded-xl" onClick={fetchAll}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* ── Summary Cards ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SummaryCard
            icon={<Zap className="w-5 h-5 text-blue-500" />}
            label="تعداد درخواست‌ها"
            value={formatNumber(s.total_requests)}
            sub={`${formatNumber(s.failed_requests)} ناموفق`}
          />
          <SummaryCard
            icon={<Coins className="w-5 h-5 text-amber-500" />}
            label="مجموع توکن‌ها"
            value={formatNumber(s.total_tokens)}
            sub={`ورودی: ${formatNumber(s.total_input_tokens)} | خروجی: ${formatNumber(s.total_output_tokens)}`}
          />
          <SummaryCard
            icon={<DollarSign className="w-5 h-5 text-green-500" />}
            label="هزینه (دلار)"
            value={formatCost(s.total_cost_usd)}
            sub={formatToman(s.total_cost_toman)}
          />
          <SummaryCard
            icon={<Clock className="w-5 h-5 text-purple-500" />}
            label="میانگین زمان پاسخ"
            value={formatDuration(s.avg_duration_ms)}
            sub={`${formatNumber(s.successful_requests)} موفق`}
          />
        </div>

        {/* ── Token Type Breakdown ── */}
        {(s.total_audio_input_tokens > 0 || s.total_cached_input_tokens > 0 || s.total_thinking_tokens > 0) && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <SummaryCard
              icon={<Layers className="w-5 h-5 text-orange-500" />}
              label="توکن صوتی ورودی"
              value={formatNumber(s.total_audio_input_tokens)}
              sub="$1.00 / 1M توکن"
            />
            <SummaryCard
              icon={<Layers className="w-5 h-5 text-teal-500" />}
              label="توکن کش شده"
              value={formatNumber(s.total_cached_input_tokens)}
              sub="$0.03 / 1M توکن"
            />
            <SummaryCard
              icon={<Layers className="w-5 h-5 text-indigo-500" />}
              label="توکن تفکر"
              value={formatNumber(s.total_thinking_tokens)}
              sub="جزو خروجی محاسبه می‌شود"
            />
          </div>
        )}

        {/* ── Exchange Rate ── */}
        {s.usdt_toman_rate && (
          <div className="text-xs text-muted-foreground text-left">
            نرخ USDT: {new Intl.NumberFormat('fa-IR').format(Math.round(s.usdt_toman_rate))} تومان
          </div>
        )}

        {/* ── By Feature + By Provider ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Feature Table */}
          <Card className="lg:col-span-2 rounded-2xl">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Layers className="w-5 h-5" />
                مصرف بر اساس قابلیت
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="text-right pb-2 font-medium">قابلیت</th>
                      <th className="text-center pb-2 font-medium">تعداد</th>
                      <th className="text-center pb-2 font-medium">توکن</th>
                      <th className="text-center pb-2 font-medium">هزینه</th>
                      <th className="text-center pb-2 font-medium">میانگین زمان</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byFeature.map((f) => (
                      <tr key={f.feature} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-2 font-medium">{f.feature_label}</td>
                        <td className="py-2 text-center">{formatNumber(f.count)}</td>
                        <td className="py-2 text-center">{formatNumber(f.total_tokens)}</td>
                        <td className="py-2 text-center text-green-600">{formatCost(f.total_cost_usd)}</td>
                        <td className="py-2 text-center text-muted-foreground">{formatDuration(f.avg_duration_ms)}</td>
                      </tr>
                    ))}
                    {byFeature.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-muted-foreground">
                          هنوز داده‌ای ثبت نشده
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Provider Breakdown */}
          <Card className="rounded-2xl">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Server className="w-5 h-5" />
                بر اساس ارائه‌دهنده
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {byProvider.map((p) => (
                <div key={p.provider} className="p-3 rounded-xl bg-muted/50 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold capitalize">{p.provider}</span>
                    <span className="text-green-600 font-mono text-sm">{formatCost(p.total_cost_usd)}</span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatNumber(p.count)} درخواست &middot; {formatNumber(p.total_tokens)} توکن
                  </div>
                </div>
              ))}
              {byProvider.length === 0 && (
                <p className="text-center text-muted-foreground py-4">بدون داده</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ── By User ── */}
        <Card className="rounded-2xl">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Users className="w-5 h-5" />
                مصرف بر اساس کاربر
              </CardTitle>
              <div className="flex items-center gap-2">
                {ROLE_FILTER_OPTIONS.map((opt) => (
                  <Button
                    key={opt.value}
                    variant={roleFilter === opt.value ? 'default' : 'outline'}
                    size="sm"
                    className="h-7 rounded-lg text-xs"
                    onClick={() => setRoleFilter(opt.value)}
                  >
                    {opt.label}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="text-right pb-2 font-medium">کاربر</th>
                    <th className="text-center pb-2 font-medium">نقش</th>
                    <th className="text-center pb-2 font-medium">تعداد</th>
                    <th className="text-center pb-2 font-medium">توکن</th>
                    <th className="text-center pb-2 font-medium">هزینه</th>
                  </tr>
                </thead>
                <tbody>
                  {byUser.map((u, idx) => (
                    <tr key={u.user_id ?? idx} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-2">
                        <div className="font-medium">{u.full_name}</div>
                        <div className="text-xs text-muted-foreground">{u.username}</div>
                      </td>
                      <td className="py-2 text-center">
                        <span className="px-2 py-0.5 rounded-full text-xs bg-muted">
                          {ROLE_MAP[u.role] || u.role}
                        </span>
                      </td>
                      <td className="py-2 text-center">{formatNumber(u.count)}</td>
                      <td className="py-2 text-center">{formatNumber(u.total_tokens)}</td>
                      <td className="py-2 text-center text-green-600 font-mono">{formatCost(u.total_cost_usd)}</td>
                    </tr>
                  ))}
                  {byUser.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-muted-foreground">
                        هنوز داده‌ای ثبت نشده
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* ── Daily Chart (simple bar representation) ── */}
        {daily.length > 0 && (() => {
          const maxTokens = Math.max(...daily.map((x) => x.total_tokens), 1);
          const BAR_MAX_HEIGHT = 180;
          return (
          <Card className="rounded-2xl">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <TrendingUp className="w-5 h-5" />
                روند روزانه
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <div className="space-y-2 min-w-[700px]">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>توکن مصرفی روزانه</span>
                    <span>حداکثر: {formatNumber(maxTokens)}</span>
                  </div>
                  <div className="relative rounded-xl border border-border/60 bg-muted/20 p-3">
                    <div className="absolute inset-x-3 top-3 bottom-10 pointer-events-none">
                      <div className="h-full flex flex-col justify-between">
                        {[0, 1, 2, 3].map((tick) => (
                          <div key={tick} className="border-t border-dashed border-border/50" />
                        ))}
                      </div>
                    </div>
                    <div className="relative flex items-end gap-1" style={{ height: `${BAR_MAX_HEIGHT + 32}px` }}>
                  {daily.map((d) => {
                    const barH = Math.max(4, (d.total_tokens / maxTokens) * BAR_MAX_HEIGHT);
                    const jalaliLabel = formatPersianMonthDay(d.date);
                    return (
                      <div key={d.date} className="flex-1 flex flex-col items-center justify-end gap-1" style={{ height: '100%' }}>
                        <div className="text-[10px] text-muted-foreground">{formatNumber(d.count)}</div>
                        <div
                          className="w-full bg-primary/80 hover:bg-primary rounded-t-md transition-all"
                          style={{ height: `${barH}px` }}
                          title={`${formatPersianDateTime(d.date)}: ${formatNumber(d.total_tokens)} توکن | ${formatCost(d.total_cost_usd)}`}
                        />
                        <div className="text-[10px] text-muted-foreground whitespace-nowrap">
                          {jalaliLabel}
                        </div>
                      </div>
                    );
                  })}
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          );
        })()}

        {/* ── Recent Logs ── */}
        <Card className="rounded-2xl">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <AlertCircle className="w-5 h-5" />
              آخرین لاگ‌ها
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="text-right pb-2 font-medium">زمان</th>
                    <th className="text-right pb-2 font-medium">کاربر</th>
                    <th className="text-right pb-2 font-medium">قابلیت</th>
                    <th className="text-center pb-2 font-medium">ارائه‌دهنده</th>
                    <th className="text-center pb-2 font-medium">مدل</th>
                    <th className="text-center pb-2 font-medium">ورودی</th>
                    <th className="text-center pb-2 font-medium">خروجی</th>
                    <th className="text-center pb-2 font-medium">هزینه</th>
                    <th className="text-center pb-2 font-medium">زمان</th>
                    <th className="text-center pb-2 font-medium">وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {recentLogs.map((log) => (
                    <tr key={log.id} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-1.5 whitespace-nowrap">
                        {formatPersianDateTime(log.created_at)}
                      </td>
                      <td className="py-1.5">{log.user ?? 'سیستم'}</td>
                      <td className="py-1.5">{log.feature}</td>
                      <td className="py-1.5 text-center capitalize">{log.provider}</td>
                      <td className="py-1.5 text-center font-mono">{log.model_name.replace('models/', '')}</td>
                      <td className="py-1.5 text-center">{formatNumber(log.input_tokens)}</td>
                      <td className="py-1.5 text-center">{formatNumber(log.output_tokens)}</td>
                      <td className="py-1.5 text-center text-green-600">{formatCost(log.estimated_cost_usd)}</td>
                      <td className="py-1.5 text-center">{formatDuration(log.duration_ms)}</td>
                      <td className="py-1.5 text-center">
                        {log.success ? (
                          <span className="text-green-600">✓</span>
                        ) : (
                          <span className="text-red-500">✗</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {recentLogs.length === 0 && (
                    <tr>
                      <td colSpan={10} className="py-8 text-center text-muted-foreground">
                        هنوز لاگی ثبت نشده
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageTransition>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function SummaryCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <Card className="rounded-2xl">
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-muted/80">{icon}</div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="text-xl font-black truncate">{value}</p>
            <p className="text-[11px] text-muted-foreground truncate">{sub}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
