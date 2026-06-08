'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  AdminService,
  type LLMUsageFilter,
  type LLMUsageSummary,
  type LLMUsageByFeature,
  type LLMUsageByProvider,
  type LLMUsageDaily,
  type LLMUsageBreakdownRow,
  type ModelPrice,
} from '@/services/admin-service';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageTransition } from '@/components/ui/page-transition';
import { ErrorState } from '@/components/shared/error-state';
import { formatPersianDateTime, formatPersianMonthDay } from '@/lib/date-utils';
import { toast } from 'sonner';
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
  Download,
  Tag,
  Plus,
  Trash2,
  Save,
  Building2,
  GraduationCap,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/* Types (local for recent logs)                                       */
/* ------------------------------------------------------------------ */

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
  estimated_cost_toman: number;
  duration_ms: number;
  success: boolean;
  created_at: string;
}

interface UserTaskGroup {
  key: string;
  user_id: number | null;
  username: string;
  full_name: string;
  role: string;
  totalToman: number;
  totalUsd: number;
  totalTokens: number;
  count: number;
  items: LLMUsageBreakdownRow[];
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function formatNumber(n: number): string {
  return new Intl.NumberFormat('fa-IR').format(n ?? 0);
}

function formatCost(usd: number): string {
  if (!usd) return '$0.00';
  if (usd < 0.001) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatToman(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '—';
  return `${new Intl.NumberFormat('fa-IR').format(Math.round(amount))} تومان`;
}

const ROLE_MAP: Record<string, string> = {
  admin: 'مدیر',
  ADMIN: 'مدیر',
  teacher: 'معلم',
  TEACHER: 'معلم',
  student: 'دانش‌آموز',
  STUDENT: 'دانش‌آموز',
};

const DAYS_OPTIONS = [7, 14, 30, 60, 90];

const ROLE_FILTER_OPTIONS = [
  { value: '', label: 'همه' },
  { value: 'teacher', label: 'معلم' },
  { value: 'student', label: 'دانش‌آموز' },
  { value: 'admin', label: 'مدیر' },
];

const inputCls =
  'h-8 rounded-lg border border-border bg-background px-2 text-xs outline-none focus:ring-2 focus:ring-primary/40';

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function LLMUsagePage() {
  const [days, setDays] = useState(30);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<LLMUsageSummary | null>(null);
  const [byFeature, setByFeature] = useState<LLMUsageByFeature[]>([]);
  const [byProvider, setByProvider] = useState<LLMUsageByProvider[]>([]);
  const [daily, setDaily] = useState<LLMUsageDaily[]>([]);
  const [breakdown, setBreakdown] = useState<LLMUsageBreakdownRow[]>([]);
  const [byOrg, setByOrg] = useState<LLMUsageBreakdownRow[]>([]);
  const [byStudyGroup, setByStudyGroup] = useState<LLMUsageBreakdownRow[]>([]);
  const [recentLogs, setRecentLogs] = useState<RecentLog[]>([]);

  // Base date filter (no role) — applies to global aggregations.
  const baseFilter: LLMUsageFilter = useMemo(() => {
    if (from && to) return { from, to };
    return { days };
  }, [from, to, days]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const roleFilterObj: LLMUsageFilter = roleFilter
        ? { ...baseFilter, role: roleFilter }
        : baseFilter;
      const [s, f, p, d, b, org, sg, r] = await Promise.all([
        AdminService.getLLMUsageSummary(baseFilter),
        AdminService.getLLMUsageByFeature(baseFilter),
        AdminService.getLLMUsageByProvider(baseFilter),
        AdminService.getLLMUsageDaily(baseFilter),
        AdminService.getLLMUsageBreakdown({ ...roleFilterObj, group_by: 'user,feature' }),
        AdminService.getLLMUsageBreakdown({ ...baseFilter, group_by: 'organization' }),
        AdminService.getLLMUsageBreakdown({ ...baseFilter, group_by: 'study_group' }),
        AdminService.getLLMUsageRecentLogs(50),
      ]);
      setSummary(s);
      setByFeature(f);
      setByProvider(p);
      setDaily(d);
      setBreakdown(b.results);
      setByOrg(org.results);
      setByStudyGroup(sg.results);
      setRecentLogs(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در دریافت اطلاعات');
    } finally {
      setLoading(false);
    }
  }, [baseFilter, roleFilter]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Group the per-user×per-task breakdown by user for the primary table.
  const userGroups: UserTaskGroup[] = useMemo(() => {
    const map = new Map<string, UserTaskGroup>();
    for (const row of breakdown) {
      const key = row.user_id != null ? `u${row.user_id}` : `name:${row.username ?? 'system'}`;
      let g = map.get(key);
      if (!g) {
        g = {
          key,
          user_id: row.user_id ?? null,
          username: row.username ?? 'system',
          full_name: row.full_name ?? '-',
          role: row.role ?? '-',
          totalToman: 0,
          totalUsd: 0,
          totalTokens: 0,
          count: 0,
          items: [],
        };
        map.set(key, g);
      }
      g.totalToman += row.total_cost_toman || 0;
      g.totalUsd += row.total_cost_usd || 0;
      g.totalTokens += row.total_tokens || 0;
      g.count += row.count || 0;
      g.items.push(row);
    }
    const groups = Array.from(map.values());
    groups.forEach((g) => g.items.sort((a, b) => (b.total_cost_toman || 0) - (a.total_cost_toman || 0)));
    groups.sort((a, b) => b.totalToman - a.totalToman);
    return groups;
  }, [breakdown]);

  const handleExportCSV = useCallback(async () => {
    try {
      const roleFilterObj: LLMUsageFilter = roleFilter
        ? { ...baseFilter, role: roleFilter }
        : baseFilter;
      const blob = await AdminService.exportLLMUsageCSV({
        ...roleFilterObj,
        group_by: 'user,feature',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `llm-usage-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'دانلود CSV ناموفق بود');
    }
  }, [baseFilter, roleFilter]);

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
  const rangeActive = Boolean(from && to);

  /* ---------- Render ---------- */
  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-black text-foreground">مصرف و هزینه LLM</h1>
            <p className="text-muted-foreground text-sm mt-1">
              گزارش دقیق هزینه هر کاربر به تفکیک هر تسک (به تومان)
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button variant="outline" size="sm" className="h-8 rounded-xl text-xs gap-1" onClick={handleExportCSV}>
              <Download className="w-4 h-4" /> خروجی CSV
            </Button>
            <Button variant="ghost" size="sm" className="h-8 rounded-xl" onClick={fetchAll}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* ── Date range controls ── */}
        <Card className="rounded-2xl">
          <CardContent className="p-4 flex flex-col lg:flex-row lg:items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 flex-wrap">
              {DAYS_OPTIONS.map((d) => (
                <Button
                  key={d}
                  variant={!rangeActive && days === d ? 'default' : 'outline'}
                  size="sm"
                  className="h-8 rounded-xl text-xs"
                  onClick={() => {
                    setFrom('');
                    setTo('');
                    setDays(d);
                  }}
                >
                  {d} روز
                </Button>
              ))}
            </div>
            <div className="flex items-center gap-2 flex-wrap lg:mr-auto">
              <span className="text-xs text-muted-foreground">بازه دقیق:</span>
              <input
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                className={inputCls}
                aria-label="از تاریخ"
              />
              <span className="text-xs text-muted-foreground">تا</span>
              <input
                type="date"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                className={inputCls}
                aria-label="تا تاریخ"
              />
              {rangeActive && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 rounded-xl text-xs"
                  onClick={() => {
                    setFrom('');
                    setTo('');
                  }}
                >
                  پاک کردن بازه
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* ── Summary Cards (Toman primary) ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SummaryCard
            icon={<Coins className="w-5 h-5 text-amber-500" />}
            label="هزینه کل (تومان)"
            value={formatToman(s.total_cost_toman)}
            sub={formatCost(s.total_cost_usd)}
          />
          <SummaryCard
            icon={<Zap className="w-5 h-5 text-blue-500" />}
            label="تعداد درخواست‌ها"
            value={formatNumber(s.total_requests)}
            sub={`${formatNumber(s.failed_requests)} ناموفق`}
          />
          <SummaryCard
            icon={<DollarSign className="w-5 h-5 text-green-500" />}
            label="مجموع توکن‌ها"
            value={formatNumber(s.total_tokens)}
            sub={`ورودی: ${formatNumber(s.total_input_tokens)} | خروجی: ${formatNumber(s.total_output_tokens)}`}
          />
          <SummaryCard
            icon={<Clock className="w-5 h-5 text-purple-500" />}
            label="میانگین زمان پاسخ"
            value={formatDuration(s.avg_duration_ms)}
            sub={`${formatNumber(s.successful_requests)} موفق`}
          />
        </div>

        {/* ── Exchange Rate ── */}
        {s.usdt_toman_rate && (
          <div className="text-xs text-muted-foreground text-left">
            نرخ لحظه‌ای USDT: {new Intl.NumberFormat('fa-IR').format(Math.round(s.usdt_toman_rate))} تومان
          </div>
        )}

        {/* ── PRIMARY: per-user × per-task Toman ── */}
        <Card className="rounded-2xl">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Users className="w-5 h-5" />
                هزینه هر کاربر به تفکیک تسک
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
          <CardContent className="space-y-3">
            {userGroups.length === 0 && (
              <p className="py-8 text-center text-muted-foreground text-sm">هنوز داده‌ای ثبت نشده</p>
            )}
            {userGroups.map((g) => (
              <details key={g.key} className="rounded-xl border border-border/60 bg-muted/20 overflow-hidden">
                <summary className="cursor-pointer list-none p-3 flex items-center justify-between gap-3 hover:bg-muted/40">
                  <div className="min-w-0">
                    <div className="font-bold truncate">{g.full_name}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {g.username} · <span className="px-1.5 py-0.5 rounded bg-muted">{ROLE_MAP[g.role] || g.role}</span>
                    </div>
                  </div>
                  <div className="text-left shrink-0">
                    <div className="font-black text-amber-600 dark:text-amber-400">{formatToman(g.totalToman)}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {formatCost(g.totalUsd)} · {formatNumber(g.count)} درخواست
                    </div>
                  </div>
                </summary>
                <div className="px-3 pb-3 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-muted-foreground">
                        <th className="text-right py-1.5 font-medium">تسک</th>
                        <th className="text-center py-1.5 font-medium">تعداد</th>
                        <th className="text-center py-1.5 font-medium">توکن</th>
                        <th className="text-center py-1.5 font-medium">هزینه (دلار)</th>
                        <th className="text-center py-1.5 font-medium">هزینه (تومان)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {g.items.map((it) => (
                        <tr key={`${g.key}-${it.feature}`} className="border-b border-border/40">
                          <td className="py-1.5">{it.feature_label || it.feature}</td>
                          <td className="py-1.5 text-center">{formatNumber(it.count)}</td>
                          <td className="py-1.5 text-center">{formatNumber(it.total_tokens)}</td>
                          <td className="py-1.5 text-center text-muted-foreground">{formatCost(it.total_cost_usd)}</td>
                          <td className="py-1.5 text-center font-medium text-amber-600 dark:text-amber-400">
                            {formatToman(it.total_cost_toman)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ))}
          </CardContent>
        </Card>

        {/* ── By Feature + By Provider ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2 rounded-2xl">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Layers className="w-5 h-5" />
                مصرف بر اساس تسک
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="text-right pb-2 font-medium">تسک</th>
                      <th className="text-center pb-2 font-medium">تعداد</th>
                      <th className="text-center pb-2 font-medium">توکن</th>
                      <th className="text-center pb-2 font-medium">هزینه (تومان)</th>
                      <th className="text-center pb-2 font-medium">دلار</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byFeature.map((f) => (
                      <tr key={f.feature} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-2 font-medium">{f.feature_label}</td>
                        <td className="py-2 text-center">{formatNumber(f.count)}</td>
                        <td className="py-2 text-center">{formatNumber(f.total_tokens)}</td>
                        <td className="py-2 text-center font-medium text-amber-600 dark:text-amber-400">
                          {formatToman(f.total_cost_toman)}
                        </td>
                        <td className="py-2 text-center text-muted-foreground">{formatCost(f.total_cost_usd)}</td>
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
                    <span className="text-amber-600 dark:text-amber-400 font-mono text-sm">
                      {formatToman(p.total_cost_toman)}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatNumber(p.count)} درخواست &middot; {formatNumber(p.total_tokens)} توکن &middot; {formatCost(p.total_cost_usd)}
                  </div>
                </div>
              ))}
              {byProvider.length === 0 && (
                <p className="text-center text-muted-foreground py-4">بدون داده</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ── By Organization + By Study Group ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="rounded-2xl">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Building2 className="w-5 h-5" />
                هزینه به تفکیک سازمان
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="text-right pb-2 font-medium">سازمان</th>
                      <th className="text-center pb-2 font-medium">درخواست</th>
                      <th className="text-center pb-2 font-medium">توکن</th>
                      <th className="text-center pb-2 font-medium">هزینه (تومان)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byOrg.map((o) => (
                      <tr key={o.organization_id ?? 'personal'} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-2 font-medium">{o.organization_name || '— شخصی —'}</td>
                        <td className="py-2 text-center">{formatNumber(o.count)}</td>
                        <td className="py-2 text-center">{formatNumber(o.total_tokens)}</td>
                        <td className="py-2 text-center font-medium text-amber-600 dark:text-amber-400">
                          {formatToman(o.total_cost_toman)}
                        </td>
                      </tr>
                    ))}
                    {byOrg.length === 0 && (
                      <tr>
                        <td colSpan={4} className="py-8 text-center text-muted-foreground">
                          هنوز داده‌ای ثبت نشده
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-2xl">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <GraduationCap className="w-5 h-5" />
                هزینه به تفکیک گروه آموزشی
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="text-right pb-2 font-medium">گروه آموزشی</th>
                      <th className="text-center pb-2 font-medium">درخواست</th>
                      <th className="text-center pb-2 font-medium">توکن</th>
                      <th className="text-center pb-2 font-medium">هزینه (تومان)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byStudyGroup.map((g) => (
                      <tr key={g.study_group_id ?? 'none'} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-2 font-medium">{g.study_group_name || '—'}</td>
                        <td className="py-2 text-center">{formatNumber(g.count)}</td>
                        <td className="py-2 text-center">{formatNumber(g.total_tokens)}</td>
                        <td className="py-2 text-center font-medium text-amber-600 dark:text-amber-400">
                          {formatToman(g.total_cost_toman)}
                        </td>
                      </tr>
                    ))}
                    {byStudyGroup.length === 0 && (
                      <tr>
                        <td colSpan={4} className="py-8 text-center text-muted-foreground">
                          هنوز داده‌ای ثبت نشده
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ── Daily Chart ── */}
        {daily.length > 0 && (() => {
          const maxToman = Math.max(...daily.map((x) => x.total_cost_toman), 1);
          const BAR_MAX_HEIGHT = 180;
          return (
            <Card className="rounded-2xl">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <TrendingUp className="w-5 h-5" />
                  روند هزینه روزانه (تومان)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <div className="space-y-2 min-w-[700px]">
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>هزینه روزانه</span>
                      <span>حداکثر: {formatToman(maxToman)}</span>
                    </div>
                    <div className="relative rounded-xl border border-border/60 bg-muted/20 p-3">
                      <div className="relative flex items-end gap-1" style={{ height: `${BAR_MAX_HEIGHT + 32}px` }}>
                        {daily.map((d) => {
                          const barH = Math.max(4, (d.total_cost_toman / maxToman) * BAR_MAX_HEIGHT);
                          const jalaliLabel = formatPersianMonthDay(d.date);
                          return (
                            <div key={d.date} className="flex-1 flex flex-col items-center justify-end gap-1" style={{ height: '100%' }}>
                              <div className="text-[10px] text-muted-foreground">{formatNumber(d.count)}</div>
                              <div
                                className="w-full bg-amber-500/80 hover:bg-amber-500 rounded-t-md transition-all"
                                style={{ height: `${barH}px` }}
                                title={`${formatPersianDateTime(d.date)}: ${formatToman(d.total_cost_toman)} | ${formatNumber(d.total_tokens)} توکن`}
                              />
                              <div className="text-[10px] text-muted-foreground whitespace-nowrap">{jalaliLabel}</div>
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
                    <th className="text-right pb-2 font-medium">تسک</th>
                    <th className="text-center pb-2 font-medium">مدل</th>
                    <th className="text-center pb-2 font-medium">ورودی</th>
                    <th className="text-center pb-2 font-medium">خروجی</th>
                    <th className="text-center pb-2 font-medium">تومان</th>
                    <th className="text-center pb-2 font-medium">وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {recentLogs.map((log) => (
                    <tr key={log.id} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-1.5 whitespace-nowrap">{formatPersianDateTime(log.created_at)}</td>
                      <td className="py-1.5">{log.user ?? 'سیستم'}</td>
                      <td className="py-1.5">{log.feature}</td>
                      <td className="py-1.5 text-center font-mono">{log.model_name.replace('models/', '')}</td>
                      <td className="py-1.5 text-center">{formatNumber(log.input_tokens)}</td>
                      <td className="py-1.5 text-center">{formatNumber(log.output_tokens)}</td>
                      <td className="py-1.5 text-center text-amber-600 dark:text-amber-400">
                        {formatToman(log.estimated_cost_toman)}
                      </td>
                      <td className="py-1.5 text-center">
                        {log.success ? <span className="text-green-600">✓</span> : <span className="text-red-500">✗</span>}
                      </td>
                    </tr>
                  ))}
                  {recentLogs.length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-muted-foreground">
                        هنوز لاگی ثبت نشده
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* ── Model price editor ── */}
        <ModelPriceEditor />
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

const emptyNewPrice = {
  provider: '',
  model_name: '',
  input_usd_per_1m: '',
  output_usd_per_1m: '',
  audio_input_usd_per_1m: '',
  cached_input_usd_per_1m: '',
};

function ModelPriceEditor() {
  const [prices, setPrices] = useState<ModelPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [newRow, setNewRow] = useState({ ...emptyNewPrice });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setPrices(await AdminService.getModelPrices());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت قیمت‌ها');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const patchLocal = (id: number, field: keyof ModelPrice, value: string | boolean) => {
    setPrices((prev) => prev.map((p) => (p.id === id ? { ...p, [field]: value } : p)));
  };

  const saveRow = async (row: ModelPrice) => {
    setSavingId(row.id);
    try {
      await AdminService.updateModelPrice(row.id, {
        provider: row.provider,
        model_name: row.model_name,
        input_usd_per_1m: row.input_usd_per_1m,
        output_usd_per_1m: row.output_usd_per_1m,
        audio_input_usd_per_1m: row.audio_input_usd_per_1m || null,
        cached_input_usd_per_1m: row.cached_input_usd_per_1m || null,
        is_active: row.is_active,
        note: row.note,
      });
      toast.success('ذخیره شد');
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ذخیره ناموفق بود');
    } finally {
      setSavingId(null);
    }
  };

  const deleteRow = async (id: number) => {
    try {
      await AdminService.deleteModelPrice(id);
      toast.success('حذف شد');
      setPrices((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'حذف ناموفق بود');
    }
  };

  const createRow = async () => {
    if (!newRow.model_name.trim()) {
      toast.error('نام مدل الزامی است');
      return;
    }
    setAdding(true);
    try {
      await AdminService.createModelPrice({
        provider: newRow.provider,
        model_name: newRow.model_name,
        input_usd_per_1m: newRow.input_usd_per_1m || 0,
        output_usd_per_1m: newRow.output_usd_per_1m || 0,
        audio_input_usd_per_1m: newRow.audio_input_usd_per_1m || null,
        cached_input_usd_per_1m: newRow.cached_input_usd_per_1m || null,
      });
      toast.success('قیمت جدید اضافه شد');
      setNewRow({ ...emptyNewPrice });
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'افزودن ناموفق بود');
    } finally {
      setAdding(false);
    }
  };

  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Tag className="w-5 h-5" />
          جدول قیمت مدل‌ها (دلار به ازای هر ۱ میلیون توکن)
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">
          قیمت‌ها به دلار وارد می‌شوند و در لحظه‌ی هر فراخوانی با نرخ زنده‌ی دلار به تومان تبدیل می‌شوند.
          ارائه‌دهنده‌ی خالی یعنی برای همه‌ی ارائه‌دهنده‌ها.
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-40 rounded-xl" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-right pb-2 font-medium">ارائه‌دهنده</th>
                  <th className="text-right pb-2 font-medium">مدل</th>
                  <th className="text-center pb-2 font-medium">ورودی</th>
                  <th className="text-center pb-2 font-medium">خروجی</th>
                  <th className="text-center pb-2 font-medium">صوتی</th>
                  <th className="text-center pb-2 font-medium">کش‌شده</th>
                  <th className="text-center pb-2 font-medium">فعال</th>
                  <th className="text-center pb-2 font-medium">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {prices.map((p) => (
                  <tr key={p.id} className="border-b border-border/40">
                    <td className="py-1.5">
                      <input className={`${inputCls} w-24`} value={p.provider} placeholder="(همه)"
                        onChange={(e) => patchLocal(p.id, 'provider', e.target.value)} />
                    </td>
                    <td className="py-1.5">
                      <input className={`${inputCls} w-40`} value={p.model_name}
                        onChange={(e) => patchLocal(p.id, 'model_name', e.target.value)} />
                    </td>
                    <td className="py-1.5 text-center">
                      <input className={`${inputCls} w-20 text-center`} value={p.input_usd_per_1m}
                        onChange={(e) => patchLocal(p.id, 'input_usd_per_1m', e.target.value)} />
                    </td>
                    <td className="py-1.5 text-center">
                      <input className={`${inputCls} w-20 text-center`} value={p.output_usd_per_1m}
                        onChange={(e) => patchLocal(p.id, 'output_usd_per_1m', e.target.value)} />
                    </td>
                    <td className="py-1.5 text-center">
                      <input className={`${inputCls} w-20 text-center`} value={p.audio_input_usd_per_1m ?? ''}
                        onChange={(e) => patchLocal(p.id, 'audio_input_usd_per_1m', e.target.value)} />
                    </td>
                    <td className="py-1.5 text-center">
                      <input className={`${inputCls} w-20 text-center`} value={p.cached_input_usd_per_1m ?? ''}
                        onChange={(e) => patchLocal(p.id, 'cached_input_usd_per_1m', e.target.value)} />
                    </td>
                    <td className="py-1.5 text-center">
                      <input type="checkbox" checked={p.is_active}
                        onChange={(e) => patchLocal(p.id, 'is_active', e.target.checked)} />
                    </td>
                    <td className="py-1.5 text-center whitespace-nowrap">
                      <Button variant="ghost" size="sm" className="h-7 px-2" disabled={savingId === p.id}
                        onClick={() => saveRow(p)}>
                        <Save className="w-3.5 h-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-red-500"
                        onClick={() => deleteRow(p.id)}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}

                {/* Add new */}
                <tr className="bg-muted/20">
                  <td className="py-1.5">
                    <input className={`${inputCls} w-24`} value={newRow.provider} placeholder="(همه)"
                      onChange={(e) => setNewRow({ ...newRow, provider: e.target.value })} />
                  </td>
                  <td className="py-1.5">
                    <input className={`${inputCls} w-40`} value={newRow.model_name} placeholder="gemini-2.5-flash"
                      onChange={(e) => setNewRow({ ...newRow, model_name: e.target.value })} />
                  </td>
                  <td className="py-1.5 text-center">
                    <input className={`${inputCls} w-20 text-center`} value={newRow.input_usd_per_1m} placeholder="0.30"
                      onChange={(e) => setNewRow({ ...newRow, input_usd_per_1m: e.target.value })} />
                  </td>
                  <td className="py-1.5 text-center">
                    <input className={`${inputCls} w-20 text-center`} value={newRow.output_usd_per_1m} placeholder="2.50"
                      onChange={(e) => setNewRow({ ...newRow, output_usd_per_1m: e.target.value })} />
                  </td>
                  <td className="py-1.5 text-center">
                    <input className={`${inputCls} w-20 text-center`} value={newRow.audio_input_usd_per_1m}
                      onChange={(e) => setNewRow({ ...newRow, audio_input_usd_per_1m: e.target.value })} />
                  </td>
                  <td className="py-1.5 text-center">
                    <input className={`${inputCls} w-20 text-center`} value={newRow.cached_input_usd_per_1m}
                      onChange={(e) => setNewRow({ ...newRow, cached_input_usd_per_1m: e.target.value })} />
                  </td>
                  <td />
                  <td className="py-1.5 text-center">
                    <Button variant="outline" size="sm" className="h-7 px-2 gap-1 text-xs" disabled={adding}
                      onClick={createRow}>
                      <Plus className="w-3.5 h-3.5" /> افزودن
                    </Button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
