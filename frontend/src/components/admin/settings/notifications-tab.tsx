'use client';

import { Bell, Mail, MessageSquare, Globe } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

import { useAdminSettings } from '@/hooks/use-admin-settings';

export function NotificationsTab() {
  const { notifications, updateNotifications } = useAdminSettings();
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>تنظیمات اعلان‌ها</CardTitle>
          <CardDescription>
            نحوه دریافت اعلان‌ها را مدیریت کنید
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-muted-foreground" />
                <Label className="text-base">اعلان‌های ایمیلی</Label>
              </div>
              <p className="text-sm text-muted-foreground">
                دریافت گزارش‌های هفتگی و اخبار مهم از طریق ایمیل
              </p>
            </div>
            <Switch 
              checked={notifications.emailNotifications} 
              onCheckedChange={(checked) => updateNotifications({ emailNotifications: checked })}
            />
          </div>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4 text-muted-foreground" />
                <Label className="text-base">اعلان‌های مرورگر</Label>
              </div>
              <p className="text-sm text-muted-foreground">
                نمایش اعلان‌های آنی در مرورگر
              </p>
            </div>
            <Switch 
              checked={notifications.browserNotifications} 
              onCheckedChange={(checked) => updateNotifications({ browserNotifications: checked })}
            />
          </div>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-muted-foreground" />
                <Label className="text-base">پیام‌های سیستمی</Label>
              </div>
              <p className="text-sm text-muted-foreground">
                دریافت پیام‌های مربوط به وضعیت سرور و آپدیت‌ها
              </p>
            </div>
            <Switch 
              checked={notifications.smsNotifications} 
              onCheckedChange={(checked) => updateNotifications({ smsNotifications: checked })}
            />
          </div>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-muted-foreground" />
                <Label className="text-base">اعلان‌های بازاریابی</Label>
              </div>
              <p className="text-sm text-muted-foreground">
                دریافت پیشنهادات ویژه و تخفیف‌ها
              </p>
            </div>
            <Switch 
              checked={notifications.marketingEmails} 
              onCheckedChange={(checked) => updateNotifications({ marketingEmails: checked })}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}