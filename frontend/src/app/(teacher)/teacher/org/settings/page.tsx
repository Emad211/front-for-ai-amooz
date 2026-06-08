'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Building2, Save } from 'lucide-react';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import { OrgManagerGuard } from '@/components/organization/org-manager-guard';
import { formatPersianNumber } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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

function PageInner() {
  const { activeWorkspace } = useWorkspace();
  const orgId = activeWorkspace?.id;

  const [org, setOrg] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Controlled form fields, initialized from the loaded organization.
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [description, setDescription] = useState('');

  async function load() {
    if (!orgId) return;
    setLoading(true);
    try {
      const data = await OrganizationService.getOrgSettings(orgId);
      setOrg(data);
      setName(data.name ?? '');
      setPhone(data.phone ?? '');
      setAddress(data.address ?? '');
      setDescription(data.description ?? '');
    } catch {
      toast.error('بارگذاری اطلاعات سازمان ناموفق بود.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (orgId) load();
    // eslint-disable-next-line
  }, [orgId]);

  async function handleSave() {
    if (!orgId) return;
    if (!name.trim()) {
      toast.error('نام سازمان نمی‌تواند خالی باشد.');
      return;
    }
    setSaving(true);
    try {
      const updated = await OrganizationService.updateOrgSettings(orgId, {
        name: name.trim(),
        phone: phone.trim(),
        address: address.trim(),
        description: description.trim(),
      });
      setOrg(updated);
      setName(updated.name ?? '');
      setPhone(updated.phone ?? '');
      setAddress(updated.address ?? '');
      setDescription(updated.description ?? '');
      toast.success('تغییرات ذخیره شد.');
    } catch {
      toast.error('ذخیره تغییرات ناموفق بود.');
    } finally {
      setSaving(false);
    }
  }

  if (!orgId) return null;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-4 sm:p-6">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Building2 className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight">تنظیمات سازمان</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          اطلاعات پایه سازمان خود را مدیریت کنید.
        </p>
      </header>

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
        </div>
      ) : !org ? (
        <Card className="rounded-2xl border-border/50 shadow-sm">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            اطلاعاتی برای نمایش وجود ندارد.
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Editable organization info */}
          <Card className="rounded-2xl border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">اطلاعات سازمان</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="org-name">
                  نام سازمان <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="org-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="نام سازمان را وارد کنید"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="org-phone">تلفن</Label>
                <Input
                  id="org-phone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="شماره تماس سازمان"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="org-address">آدرس</Label>
                <Input
                  id="org-address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="آدرس سازمان"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="org-description">توضیحات</Label>
                <Textarea
                  id="org-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="توضیحاتی درباره سازمان"
                  rows={4}
                  disabled={saving}
                />
              </div>

              <div className="flex justify-end">
                <Button onClick={handleSave} disabled={saving} className="gap-2">
                  <Save className="h-4 w-4" />
                  {saving ? 'در حال ذخیره…' : 'ذخیره تغییرات'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Read-only subscription info (managed by platform) */}
          <Card className="rounded-2xl border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">اطلاعات اشتراک (مدیریت پلتفرم)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <dt className="text-sm text-muted-foreground">شناسه یکتا (Slug)</dt>
                  <dd className="font-mono text-sm" dir="ltr">
                    {org.slug || '—'}
                  </dd>
                </div>

                <div className="space-y-1">
                  <dt className="text-sm text-muted-foreground">ظرفیت دانش‌آموز</dt>
                  <dd className="text-sm font-medium">
                    {formatPersianNumber(org.studentCapacity)} نفر
                  </dd>
                </div>

                <div className="space-y-1">
                  <dt className="text-sm text-muted-foreground">دانش‌آموزان فعلی</dt>
                  <dd className="text-sm font-medium">
                    {formatPersianNumber(org.currentStudentCount)} نفر
                  </dd>
                </div>

                <div className="space-y-1">
                  <dt className="text-sm text-muted-foreground">وضعیت اشتراک</dt>
                  <dd>
                    <Badge
                      variant={
                        org.subscriptionStatus === 'active' ? 'default' : 'secondary'
                      }
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

                <div className="space-y-1">
                  <dt className="text-sm text-muted-foreground">تاریخ ایجاد</dt>
                  <dd className="text-sm font-medium">
                    {formatPersianDate(org.createdAt)}
                  </dd>
                </div>
              </dl>

              <p className="text-xs text-muted-foreground">
                ظرفیت و وضعیت اشتراک توسط مدیریت پلتفرم تنظیم می‌شود.
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
