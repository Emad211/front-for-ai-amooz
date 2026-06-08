'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Building2, Lock } from 'lucide-react';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import { OrgManagerGuard } from '@/components/organization/org-manager-guard';
import { formatPersianNumber, toPersianDigits } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import type { Organization } from '@/types';

export default function Page() {
  return (
    <OrgManagerGuard>
      <PageInner />
    </OrgManagerGuard>
  );
}

const SUBSCRIPTION_LABEL: Record<Organization['subscriptionStatus'], string> = {
  active: 'فعال',
  expired: 'منقضی',
  suspended: 'معلق',
};

/** A single read-only label/value row. */
function Field({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="space-y-1">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={`text-sm font-medium ${mono ? 'font-mono' : ''}`} dir={mono ? 'ltr' : undefined}>
        {value}
      </dd>
    </div>
  );
}

function PageInner() {
  const { activeWorkspace } = useWorkspace();
  const orgId = activeWorkspace?.id;

  const [org, setOrg] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    setLoading(true);
    OrganizationService.getOrgSettings(orgId)
      .then((data) => { if (!cancelled) setOrg(data); })
      .catch(() => { if (!cancelled) toast.error('بارگذاری اطلاعات سازمان ناموفق بود.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [orgId]);

  if (!orgId) return null;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-4 sm:p-6">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Building2 className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight">مشخصات سازمان</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          اطلاعات سازمان شما. تغییر این تنظیمات فقط توسط مدیریت پلتفرم انجام می‌شود.
        </p>
      </header>

      {/* Read-only notice */}
      <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300">
        <Lock className="h-4 w-4 shrink-0" />
        <span>این صفحه فقط‌خواندنی است. برای تغییر نام، ظرفیت یا وضعیت اشتراک با پشتیبانی پلتفرم در تماس باشید.</span>
      </div>

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-40 rounded-2xl" />
          <Skeleton className="h-40 rounded-2xl" />
        </div>
      ) : !org ? (
        <Card className="rounded-2xl border-border/50 shadow-sm">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            اطلاعاتی برای نمایش وجود ندارد.
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Organization profile (read-only) */}
          <Card className="rounded-2xl border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">اطلاعات سازمان</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <Field label="نام سازمان" value={org.name || '—'} />
                <Field label="تلفن" value={org.phone ? toPersianDigits(org.phone) : '—'} mono />
                <div className="sm:col-span-2">
                  <Field label="آدرس" value={org.address || '—'} />
                </div>
                <div className="sm:col-span-2">
                  <Field label="توضیحات" value={org.description || '—'} />
                </div>
              </dl>
            </CardContent>
          </Card>

          {/* Subscription info (platform-managed) */}
          <Card className="rounded-2xl border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">اطلاعات اشتراک (مدیریت پلتفرم)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="شناسه یکتا (Slug)" value={org.slug || '—'} mono />
                <Field label="ظرفیت دانش‌آموز" value={`${formatPersianNumber(org.studentCapacity)} نفر`} />
                <Field label="دانش‌آموزان فعلی" value={`${formatPersianNumber(org.currentStudentCount)} نفر`} />
                <div className="space-y-1">
                  <dt className="text-sm text-muted-foreground">وضعیت اشتراک</dt>
                  <dd>
                    <Badge
                      variant={org.subscriptionStatus === 'active' ? 'default' : 'secondary'}
                      className={
                        org.subscriptionStatus === 'active'
                          ? 'border-transparent bg-emerald-100 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/40 dark:text-emerald-300'
                          : org.subscriptionStatus === 'expired'
                            ? 'border-transparent bg-destructive/10 text-destructive hover:bg-destructive/10'
                            : 'border-transparent bg-amber-100 text-amber-700 hover:bg-amber-100 dark:bg-amber-900/40 dark:text-amber-300'
                      }
                    >
                      {SUBSCRIPTION_LABEL[org.subscriptionStatus]}
                    </Badge>
                  </dd>
                </div>
                <Field label="تاریخ ایجاد" value={formatPersianDate(org.createdAt)} />
              </dl>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
