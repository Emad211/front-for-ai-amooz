'use client';

import { Users, BookOpen, GraduationCap, TrendingUp } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

const stats = [
  {
    title: 'کل دانش‌آموزان',
    value: '۱,۲۸۴',
    change: '+۱۲٪',
    trend: 'up',
    icon: Users,
  },
  {
    title: 'کلاس‌های فعال',
    value: '۴۲',
    change: '+۳',
    trend: 'up',
    icon: BookOpen,
  },
  {
    title: 'فارغ‌التحصیلان',
    value: '۱۵۶',
    change: '+۸٪',
    trend: 'up',
    icon: GraduationCap,
  },
  {
    title: 'نرخ تعامل',
    value: '۸۴٪',
    change: '+۵٪',
    trend: 'up',
    icon: TrendingUp,
  },
];

export function OverviewCards() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat, index) => (
        <Card key={index} className="bg-card border-border/60 hover:border-primary/30 transition-all duration-300">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-2 bg-muted rounded-lg">
                <stat.icon className="w-5 h-5 text-muted-foreground" />
              </div>
              <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                stat.trend === 'up' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-rose-500/10 text-rose-600'
              }`}>
                {stat.change}
              </span>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{stat.title}</p>
              <h3 className="text-2xl font-bold text-foreground mt-1">{stat.value}</h3>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
