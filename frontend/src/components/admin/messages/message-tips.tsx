'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function MessageTips() {
  return (
    <Card className="bg-primary/5 border-primary/20">
      <CardHeader>
        <CardTitle className="text-lg text-primary">نکات مهم</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-muted-foreground">
        <ul className="list-disc list-inside space-y-2">
          <li>پیام‌ها به صورت اعلان (Notification) برای دانش‌آموزان ارسال می‌شود.</li>
          <li>در صورت انتخاب "همه دانش‌آموزان"، پیام برای تمام کاربران فعال ارسال خواهد شد.</li>
          <li>امکان ویرایش پیام پس از ارسال وجود ندارد.</li>
          <li>تاریخ و زمان ارسال پیام ثبت می‌شود.</li>
        </ul>
      </CardContent>
    </Card>
  );
}
