'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { useAdminServerSettings } from '@/hooks/use-admin-server-settings';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';

export default function ServerSettingsPage() {
  const { settings, isLoading, error, reload, update } = useAdminServerSettings();

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت تنظیمات" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  const handleToggle = (key: string) => update({ [key]: !settings?.[key] });
  const handleChange = (key: string, value: any) => update({ [key]: value });

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-foreground">تنظیمات کلی سرور</h1>
          <p className="text-muted-foreground text-sm mt-1">مدیریت بک‌آپ، نگهداری و اعلان‌های زیرساخت</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>بک‌آپ</CardTitle>
          <CardDescription>زمان‌بندی و نگهداری</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading || !settings ? (
            <Skeleton className="h-28 rounded-xl" />
          ) : (
            <>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <Label className="text-sm">بک‌آپ خودکار</Label>
                  <p className="text-xs text-muted-foreground">فعال‌سازی بک‌آپ شبانه</p>
                </div>
                <Switch checked={settings.autoBackup} onCheckedChange={() => handleToggle('autoBackup')} />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label htmlFor="backupWindow">بازه بک‌آپ</Label>
                  <Input id="backupWindow" value={settings.backupWindow} onChange={(e) => handleChange('backupWindow', e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="backupRetentionDays">روزهای نگهداری</Label>
                  <Input id="backupRetentionDays" type="number" value={settings.backupRetentionDays} onChange={(e) => handleChange('backupRetentionDays', Number(e.target.value))} />
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>نگهداری و هشدار</CardTitle>
          <CardDescription>کنترل تأیید نگهداری و ایمیل هشدار</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading || !settings ? (
            <Skeleton className="h-24 rounded-xl" />
          ) : (
            <>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <Label className="text-sm">تأیید خودکار نگهداری</Label>
                  <p className="text-xs text-muted-foreground">اجرای خودکار وظایف زمان‌بندی شده</p>
                </div>
                <Switch checked={settings.maintenanceAutoApprove} onCheckedChange={() => handleToggle('maintenanceAutoApprove')} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="alertEmail">ایمیل هشدار</Label>
                <Input id="alertEmail" dir="ltr" value={settings.alertEmail} onChange={(e) => handleChange('alertEmail', e.target.value)} />
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Button onClick={reload} variant="outline" className="rounded-xl">تازه‌سازی</Button>
    </div>
  );
}
