'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import { useOrgDashboard } from '@/hooks/use-organizations';
import { OrgManagementPanel } from '@/components/organization/org-management-panel';
import { PageTransition } from '@/components/ui/page-transition';
import { ErrorState } from '@/components/shared/error-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Users,
  BookOpen,
  KeyRound,
  Building2,
  ChevronRight,
  GraduationCap,
} from 'lucide-react';

export default function OrganizationDetailPage({
  params: paramsPromise,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const params = use(paramsPromise);
  const orgId = parseInt(params.id);

  // Guard against invalid/NaN org ID
  if (Number.isNaN(orgId)) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center h-[60vh] px-4">
          <div className="w-full max-w-2xl">
            <ErrorState title="خطا" description="شناسه سازمان آموزشی نامعتبر است." onRetry={() => router.push('/admin/organizations')} />
          </div>
        </div>
      </PageTransition>
    );
  }

  const { dashboard, isLoading: dashLoading, error: dashError, reload: reloadDash } = useOrgDashboard(orgId);

  // ── Loading ──
  if (dashLoading) {
    return (
      <PageTransition>
        <div className="space-y-8">
          <div className="flex items-center gap-3">
            <Skeleton className="w-12 h-12 rounded-xl" />
            <div className="space-y-2">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-4 w-32" />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-24 rounded-2xl" />
            ))}
          </div>
          <Skeleton className="h-96 rounded-2xl" />
        </div>
      </PageTransition>
    );
  }

  if (dashError || !dashboard) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center h-[60vh] px-4">
          <div className="w-full max-w-2xl">
            <ErrorState title="خطا" description={dashError || 'سازمان آموزشی یافت نشد'} onRetry={reloadDash} />
          </div>
        </div>
      </PageTransition>
    );
  }

  const org = dashboard.organization;
  const stats = dashboard.stats;
  const capacityPercent = stats.studentCapacity
    ? Math.round((stats.students / stats.studentCapacity) * 100)
    : 0;

  const orgInfoItems = [
    { label: 'مدیر', value: org.ownerName || '—' },
    { label: 'توضیحات', value: org.description || '—' },
    { label: 'تلفن', value: org.phone || '—' },
    { label: 'آدرس', value: org.address || '—' },
    { label: 'تاریخ ایجاد', value: org.createdAt ? new Date(org.createdAt).toLocaleDateString('fa-IR') : '—' },
  ];

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* ── Breadcrumb + Header ── */}
        <div>
          <button
            onClick={() => router.push('/admin/organizations')}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
          >
            <ChevronRight className="w-4 h-4" />
            بازگشت به لیست سازمان‌های آموزشی
          </button>
          <div className="flex items-center gap-4">
            {org.logo ? (
              <img src={org.logo} alt={org.name} className="w-14 h-14 rounded-xl object-cover ring-1 ring-border" />
            ) : (
              <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center">
                <Building2 className="w-7 h-7 text-primary" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl md:text-3xl font-black text-foreground">{org.name}</h1>
              <p className="text-sm text-muted-foreground font-mono" dir="ltr">
                {org.slug}
              </p>
            </div>
            <Badge
              className={`shrink-0 text-xs border ${
                org.subscriptionStatus === 'active'
                  ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20'
                  : org.subscriptionStatus === 'expired'
                    ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20'
                    : 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20'
              }`}
            >
              {org.subscriptionStatus === 'active' ? 'فعال' : org.subscriptionStatus === 'expired' ? 'منقضی' : 'معلق'}
            </Badge>
          </div>

          {/* Org Info Row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 mt-4 p-4 bg-muted/50 rounded-xl">
            {orgInfoItems.map((item) => (
              <div key={item.label}>
                <p className="text-[11px] text-muted-foreground">{item.label}</p>
                <p className="text-sm font-medium truncate">{item.value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Stats Cards ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="rounded-2xl">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center shrink-0">
                  <Users className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="text-2xl font-black">{stats.totalMembers}</p>
                  <p className="text-xs text-muted-foreground">کل اعضا</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4 space-y-2">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
                  <GraduationCap className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div>
                  <p className="text-2xl font-black tabular-nums">
                    {stats.students}
                    <span className="text-sm font-normal text-muted-foreground">/{stats.studentCapacity}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">دانش‌آموزان</p>
                </div>
              </div>
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    capacityPercent >= 90
                      ? 'bg-red-500'
                      : capacityPercent >= 70
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(capacityPercent, 100)}%` }}
                />
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center shrink-0">
                  <BookOpen className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <p className="text-2xl font-black tabular-nums">
                    {stats.publishedClasses}
                    <span className="text-sm font-normal text-muted-foreground">/{stats.totalClasses}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">کلاس‌ها</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center shrink-0">
                  <KeyRound className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <p className="text-2xl font-black">{stats.activeInviteCodes}</p>
                  <p className="text-xs text-muted-foreground">کد فعال</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ── Members + Invitation Codes management ── */}
        <OrgManagementPanel orgId={orgId} onMembersChanged={reloadDash} />
      </div>
    </PageTransition>
  );
}
