'use client';

import { useEffect, useState } from 'react';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import type { OrgDashboard } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Users, BookOpen, GraduationCap, KeyRound, Building2, CheckCircle2 } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';

export function OrgDashboardPage() {
  const { activeWorkspace } = useWorkspace();
  const [dashboard, setDashboard] = useState<OrgDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    { label: 'اعضای فعال', value: stats.totalMembers, icon: Users, color: 'text-blue-500' },
    { label: 'دانش‌آموزان', value: `${stats.students} / ${stats.studentCapacity}`, icon: GraduationCap, color: 'text-green-500' },
    { label: 'معلمان', value: stats.teachers, icon: Users, color: 'text-purple-500' },
    { label: 'کل کلاس‌ها', value: stats.totalClasses, icon: BookOpen, color: 'text-orange-500' },
    { label: 'کلاس‌های منتشر شده', value: stats.publishedClasses, icon: CheckCircle2, color: 'text-emerald-500' },
    { label: 'کدهای دعوت فعال', value: stats.activeInviteCodes, icon: KeyRound, color: 'text-amber-500' },
  ];

  return (
    <div className="space-y-8">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {organization.logo ? (
            <img src={organization.logo} alt={organization.name} className="h-10 w-10 rounded-xl object-cover" />
          ) : (
            <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Building2 className="h-5 w-5 text-primary" />
            </div>
          )}
          <div>
            <h1 className="text-2xl font-black text-foreground">{organization.name}</h1>
            <p className="text-sm text-muted-foreground">داشبورد مدیریت سازمان</p>
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

      {/* Quick Actions */}
      <Card className="rounded-2xl border-border/50 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg font-bold">دسترسی سریع</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button variant="outline" size="sm" asChild>
            <Link href="/teacher/my-classes">کلاس‌های سازمان</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href="/teacher/create-class">ایجاد کلاس جدید</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href="/teacher/students">مدیریت دانش‌آموزان</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
