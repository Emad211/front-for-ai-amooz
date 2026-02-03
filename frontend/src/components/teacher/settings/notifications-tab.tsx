'use client';

import { Bell, Mail, MessageSquare, Globe } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

import { useTeacherSettings } from '@/hooks/use-teacher-settings';

interface NotificationsTabProps {
useSettings?: typeof useTeacherSettings;
}

export function NotificationsTab({ useSettings = useTeacherSettings }: NotificationsTabProps) {
const { notifications, updateNotifications } = useSettings();
return (
<div className="space-y-6 text-right">
<Card className="border-none shadow-xl shadow-foreground/5 bg-card/50 backdrop-blur-sm rounded-3xl overflow-hidden">
<CardHeader className="pb-8 pt-10 px-8 border-b border-border/50 bg-muted/30">
<CardTitle className="text-2xl font-bold flex items-center justify-end gap-2">
تنظیمات اطلاع‌رسانی
<Bell className="w-6 h-6 text-primary" />
</CardTitle>
<CardDescription className="text-base text-muted-foreground">
نحوه و زمان دریافت اعلان‌ها را مطابق سلیقه خود تنظیم کنید
</CardDescription>
</CardHeader>
<CardContent className="p-8 space-y-8">
<div className="flex items-center justify-between gap-4">
<Switch 
checked={notifications.emailNotifications} 
onCheckedChange={(checked) => updateNotifications({ emailNotifications: checked })}
/>
<div className="space-y-1 text-right">
<div className="flex items-center gap-2 justify-end">
<Label className="text-base font-bold">اعلان‌های ایمیلی</Label>
<Mail className="w-4 h-4 text-primary" />
</div>
<p className="text-sm text-muted-foreground">
دریافت گزارش‌های هفتگی و اخبار مهم از طریق ایمیل
</p>
</div>
</div>

<div className="flex items-center justify-between gap-4">
<Switch 
checked={notifications.browserNotifications} 
onCheckedChange={(checked) => updateNotifications({ browserNotifications: checked })}
/>
<div className="space-y-1 text-right">
<div className="flex items-center gap-2 justify-end">
<Label className="text-base font-bold">اعلان‌های مرورگر</Label>
<Bell className="w-4 h-4 text-primary" />
</div>
<p className="text-sm text-muted-foreground">
نمایش اعلان‌های آنی در مرورگر در زمان فعالیت
</p>
</div>
</div>

<div className="flex items-center justify-between gap-4">
<Switch 
checked={notifications.smsNotifications} 
onCheckedChange={(checked) => updateNotifications({ smsNotifications: checked })}
/>
<div className="space-y-1 text-right">
<div className="flex items-center gap-2 justify-end">
<Label className="text-base font-bold">پیام‌های سیستمی</Label>
<MessageSquare className="w-4 h-4 text-primary" />
</div>
<p className="text-sm text-muted-foreground">
دریافت پیام‌های مربوط به وضعیت کلاس‌ها و آپدیت‌های مهم
</p>
</div>
</div>

<div className="flex items-center justify-between gap-4">
<Switch 
checked={notifications.marketingEmails} 
onCheckedChange={(checked) => updateNotifications({ marketingEmails: checked })}
/>
<div className="space-y-1 text-right">
<div className="flex items-center gap-2 justify-end">
<Label className="text-base font-bold">اعلان‌های بازاریابی</Label>
<Globe className="w-4 h-4 text-primary" />
</div>
<p className="text-sm text-muted-foreground">
دریافت پیشنهادات ویژه و اطلاع‌رسانی دوره‌های جدید
</p>
</div>
</div>
</CardContent>
</Card>
</div>
);
}
