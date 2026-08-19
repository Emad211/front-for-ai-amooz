'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, ClipboardList, Users, CalendarRange, ArrowLeft } from 'lucide-react';

import { getStoredUser } from '@/services/auth-service';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

/**
 * Advisor home.
 *
 * Its job is to be honest about what works today: live surfaces get a real link,
 * everything still unbuilt is named and marked «به‌زودی» rather than hidden — an
 * advisor who cannot tell "not built yet" from "broken" files the second one.
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

  const live = [
    {
      icon: BookOpen,
      title: 'درس‌ها',
      body: 'فهرست درس‌هایی که می‌توانید در برنامهٔ دانش‌آموزان استفاده کنید.',
      href: '/advisor/subjects',
    },
  ];

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
        {live.map((item) => (
          <Link key={item.title} href={item.href} className="group">
            <Card className="h-full border-border/50 transition-colors hover:border-primary/50 hover:bg-muted/40">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <item.icon className="h-4 w-4 text-primary" />
                  {item.title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs leading-relaxed text-muted-foreground">{item.body}</p>
                <p className="mt-2 flex items-center gap-1 text-xs font-medium text-primary">
                  مشاهده
                  <ArrowLeft className="h-3 w-3 transition-transform group-hover:-translate-x-0.5" />
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}

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
