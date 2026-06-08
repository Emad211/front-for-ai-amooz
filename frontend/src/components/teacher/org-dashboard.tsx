'use client';

import { useEffect, useState } from 'react';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import type { OrgDashboard, OrgCosts } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Users, BookOpen, GraduationCap, KeyRound, Building2, CheckCircle2,
  Wallet, UserCog, Settings, PlusCircle, FolderOpen, ArrowLeft,
} from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { formatPersianNumber } from '@/lib/persian-digits';

/** Quick-action tiles shown to org managers (admin/deputy). */
const MANAGER_ACTIONS = [
  { label: 'گروه‌های آموزشی', href: '/teacher/org/study-groups', icon: GraduationCap, desc: 'ساخت و مدیریت گروه‌های کلاسی' },
  { label: 'معلمان', href: '/teacher/org/teachers', icon: UserCog, desc: 'دعوت معلم و تخصیص به گروه‌ها' },
  { label: 'اعضا و کدهای دعوت', href: '/teacher/org/members', icon: KeyRound, desc: 'مدیریت اعضا و کدهای ورود' },
  { label: 'هزینه و مصرف هوش مصنوعی', href: '/teacher/org/costs', icon: Wallet, desc: 'ردیابی هزینه به تفکیک معلم و گروه' },
  { label: 'ایجاد کلاس جدید', href: '/teacher/create-class', icon: PlusCircle, desc: 'ساخت محتوای آموزشی با هوش مصنوعی' },
  { label: 'تنظیمات سازمان', href: '/teacher/org/settings', icon: Settings, desc: 'ویرایش مشخصات سازمان' },
];

/** Quick-action tiles shown to plain org teachers. */
const TEACHER_ACTIONS = [
  { label: 'گروه‌های من', href: '/teacher/org/my-groups', icon: GraduationCap, desc: 'گروه‌هایی که در آن‌ها تدریس می‌کنید' },
  { label: 'ایجاد کلاس جدید', href: '/teacher/create-class', icon: PlusCircle, desc: 'ساخت محتوای آموزشی با هوش مصنوعی' },
  { label: 'کلاس‌های سازمان', href: '/teacher/my-classes', icon: FolderOpen, desc: 'کلاس‌های ساخته‌شده' },
];

export function OrgDashboardPage() {
  const { activeWorkspace } = useWorkspace();
  const [dashboard, setDashboard] = useState<OrgDashboard | null>(null);
  const [costs, setCosts] = useState<OrgCosts | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isManager = activeWorkspace?.orgRole === 'admin' || activeWorkspace?.orgRole === 'deputy';

  useEffect(() => {
    if (!activeWorkspace) return;
    let cancelled = false;

    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await OrganizationService.getDashboard(activeWorkspace!.id);
        if (!cancelled) setDashboard(data);
      } catch {
        if (!cancelled) setError('خطا در دریافت اطلاعات داشبورد سازمان');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [activeWorkspace]);

  // Managers also get a 30-day cost preview (best-effort; never blocks the page).
  useEffect(() => {
    if (!activeWorkspace || !isManager) return;
    let cancelled = false;
    OrganizationService.getOrgCosts(activeWorkspace.id, 30)
      .then((c) => { if (!cancelled) setCosts(c); })
      .catch(() => { /* cost preview is optional */ });
    return () => { cancelled = true; };
  }, [activeWorkspace, isManager]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !dashboard) {
    return <p className="text-destructive text-center py-12">{error ?? 'داده‌ای یافت نشد.'}</p>;
  }

  const { stats, organization } = dashboard;

  const cards = [
    { label: 'اعضای فعال', value: formatPersianNumber(stats.totalMembers), icon: Users, color: 'text-blue-500' },
    { label: 'دانش‌آموزان', value: `${formatPersianNumber(stats.students)} / ${formatPersianNumber(stats.studentCapacity)}`, icon: GraduationCap, color: 'text-green-500' },
    { label: 'معلمان', value: formatPersianNumber(stats.teachers), icon: UserCog, color: 'text-purple-500' },
    { label: 'کل کلاس‌ها', value: formatPersianNumber(stats.totalClasses), icon: BookOpen, color: 'text-orange-500' },
    { label: 'کلاس‌های منتشر شده', value: formatPersianNumber(stats.publishedClasses), icon: CheckCircle2, color: 'text-emerald-500' },
    { label: 'کدهای دعوت فعال', value: formatPersianNumber(stats.activeInviteCodes), icon: KeyRound, color: 'text-amber-500' },
  ];

  const actions = isManager ? MANAGER_ACTIONS : TEACHER_ACTIONS;

  return (
    <div className="space-y-8">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4">
        <div className="flex items-center gap-3">
          {organization.logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={organization.logo} alt={organization.name} className="h-10 w-10 rounded-xl object-cover" />
          ) : (
            <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Building2 className="h-5 w-5 text-primary" />
            </div>
          )}
          <div>
            <h1 className="text-2xl font-black text-foreground">{organization.name}</h1>
            <p className="text-sm text-muted-foreground">
              {isManager ? 'داشبورد مدیریت سازمان' : 'فضای سازمانی معلم'}
            </p>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((card) => (
          <Card key={card.label} className="rounded-2xl border-border/50 shadow-sm">
            <CardContent className="flex items-center gap-4 p-5">
              <div className={`flex items-center justify-center h-12 w-12 rounded-xl bg-muted/50 ${card.color}`}>
                <card.icon className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{card.label}</p>
                <p className="text-2xl font-bold text-foreground">{card.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Manager: 30-day AI cost preview */}
      {isManager && costs && (
        <Card className="rounded-2xl border-border/50 shadow-sm bg-gradient-to-l from-primary/5 to-transparent">
          <CardContent className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5">
            <div className="flex items-center gap-4">
              <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-primary/10 text-primary">
                <Wallet className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">هزینه هوش مصنوعی (۳۰ روز اخیر)</p>
                <p className="text-2xl font-bold text-foreground">
                  {formatPersianNumber(Math.round(costs.summary.totalCostToman))} تومان
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/teacher/org/costs" className="gap-1">
                جزئیات هزینه‌ها <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <Card className="rounded-2xl border-border/50 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg font-bold">دسترسی سریع</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {actions.map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="group flex items-start gap-3 rounded-2xl border border-border/50 p-4 transition-colors hover:bg-muted/50 hover:border-primary/40"
            >
              <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-muted/50 text-primary shrink-0">
                <action.icon className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="font-bold text-foreground group-hover:text-primary transition-colors">{action.label}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{action.desc}</p>
              </div>
            </Link>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
