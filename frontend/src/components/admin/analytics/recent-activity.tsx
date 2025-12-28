'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { UserPlus, BookOpen, MessageSquare, Award } from 'lucide-react';

const activities = [
  {
    id: 1,
    type: 'registration',
    user: 'سارا احمدی',
    action: 'در کلاس فیزیک ثبت‌نام کرد',
    time: '۱۰ دقیقه پیش',
    icon: UserPlus,
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
  },
  {
    id: 2,
    type: 'class',
    user: 'مدیر',
    action: 'کلاس جدید "شیمی آلی" را ایجاد کرد',
    time: '۲ ساعت پیش',
    icon: BookOpen,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
  },
  {
    id: 3,
    type: 'message',
    user: 'علی محمدی',
    action: 'یک پیام جدید ارسال کرد',
    time: '۵ ساعت پیش',
    icon: MessageSquare,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
  },
  {
    id: 4,
    type: 'award',
    user: 'رضا کریمی',
    action: 'دوره ریاضی پیشرفته را به پایان رساند',
    time: 'دیروز',
    icon: Award,
    color: 'text-purple-500',
    bg: 'bg-purple-500/10',
  },
];

export function RecentActivity() {
  return (
    <Card className="bg-card border-border/60 lg:col-span-1">
      <CardHeader>
        <CardTitle className="text-lg font-bold">فعالیت‌های اخیر</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {activities.map((activity) => (
            <div key={activity.id} className="flex items-start gap-4">
              <div className={`p-2 rounded-lg ${activity.bg}`}>
                <activity.icon className={`w-4 h-4 ${activity.color}`} />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm font-medium text-foreground">
                  <span className="font-bold">{activity.user}</span> {activity.action}
                </p>
                <p className="text-xs text-muted-foreground">{activity.time}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
