'use client';

import { useEffect, useState } from 'react';
import { ClipboardList, Users, CalendarRange } from 'lucide-react';

import { getStoredUser } from '@/services/auth-service';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

/**
 * Advisor home — S1 placeholder.
 *
 * Its only job is to prove the role is reachable: an ADVISOR logs in and lands
 * here instead of on the student dashboard. Every real surface is a later step,
 * and each is named below so the page is honest about being empty rather than
 * looking half-broken.
 */
export default function AdvisorHomePage() {
  const [name, setName] = useState('');

  // Read on the client only: getStoredUser() touches localStorage, which does
  // not exist during the server render pass.
  useEffect(() => {
    const user = getStoredUser();
    const full = [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim();
    setName(full || user?.username || '');
  }, []);

  const upcoming = [
    {
      icon: Users,
      title: 'دانش‌آموزان من',
      body: 'افزودن دانش‌آموز با دعوت‌نامه، و دریافت گروهی از سازمان آموزشی.',
    },
    {
      icon: CalendarRange,
      title: 'برنامهٔ هفتگی',
      body: 'نوشتن برنامهٔ هفته برای هر دانش‌آموز و دیدن گزارش روزانهٔ مطالعه.',
    },
    {
      icon: ClipboardList,
      title: 'میزان پایبندی',
      body: 'مقایسهٔ آنچه برنامه‌ریزی شده با آنچه واقعاً مطالعه شده است.',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold sm:text-2xl">
          {name ? `${name} عزیز، خوش آمدید` : 'خوش آمدید'}
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          پنل مشاور شما فعال شد. بخش‌های زیر به‌ترتیب اضافه می‌شوند.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {upcoming.map((item) => (
          <Card key={item.title} className="border-border/50 border-dashed">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <item.icon className="h-4 w-4 text-primary" />
                {item.title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs leading-relaxed text-muted-foreground">{item.body}</p>
              <p className="mt-2 text-xs font-medium text-amber-600 dark:text-amber-500">
                به‌زودی
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
