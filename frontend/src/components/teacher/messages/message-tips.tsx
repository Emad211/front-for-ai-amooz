'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function MessageTips() {
  return (
    <Card className="bg-primary/5 border-primary/20">
      <CardHeader className="text-start">
        <CardTitle className="text-lg text-primary">نکات مهم</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-muted-foreground text-start">
        <ul className="space-y-3">
          <li className="flex items-start gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
            <span>پیام‌ها به صورت اعلان (Notification) برای دانش‌آموزان ارسال می‌شود.</span>
          </li>
          <li className="flex items-start gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
            <span>در صورت انتخاب "همه دانش‌آموزان"، پیام برای تمام دانش‌آموزان کلاس‌های شما ارسال خواهد شد.</span>
          </li>
          <li className="flex items-start gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
            <span>امکان ویرایش پیام پس از ارسال وجود ندارد.</span>
          </li>
          <li className="flex items-start gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
            <span>تاریخ و زمان ارسال پیام ثبت می‌شود.</span>
          </li>
        </ul>
      </CardContent>
    </Card>
  );
}
