'use client';

import { BookOpen, Users, Clock, Calendar, BarChart3, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import type { ClassDetail } from '@/types';

interface ClassStatsSidebarProps {
  classDetail: ClassDetail;
  totalStudents: number;
}

export function ClassStatsSidebar({ classDetail, totalStudents }: ClassStatsSidebarProps) {
  const chapters = classDetail.chapters || [];
  const totalLessons = chapters.reduce((acc, ch) => acc + ch.lessons.length, 0);
  const publishedLessons = chapters.reduce(
    (acc, ch) => acc + ch.lessons.filter(l => l.isPublished).length, 
    0
  );
  const publishedProgress = totalLessons > 0 ? (publishedLessons / totalLessons) * 100 : 0;

  const stats = [
    { 
      icon: BookOpen, 
      label: 'تعداد فصل‌ها', 
      value: chapters.length,
      color: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30'
    },
    { 
      icon: Clock, 
      label: 'کل دروس', 
      value: totalLessons,
      color: 'text-purple-600 bg-purple-100 dark:bg-purple-900/30'
    },
    { 
      icon: Users, 
      label: 'دانش‌آموزان', 
      value: totalStudents,
      color: 'text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30'
    },
    { 
      icon: BarChart3, 
      label: 'میانگین پیشرفت', 
      value: '۶۵٪',
      color: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30'
    },
  ];

  return (
    <div className="space-y-4">
      {/* Quick Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">آمار کلی</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {stats.map(({ icon: Icon, label, value, color }) => (
            <div key={label} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${color}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <span className="text-sm text-muted-foreground">{label}</span>
              </div>
              <span className="font-semibold">{value}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Publication Progress */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            وضعیت انتشار
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">دروس منتشر شده</span>
            <span className="font-medium">{publishedLessons} از {totalLessons}</span>
          </div>
          <Progress value={publishedProgress} className="h-2" />
          <p className="text-xs text-muted-foreground text-center">
            {Math.round(publishedProgress)}% از محتوای کلاس منتشر شده است
          </p>
        </CardContent>
      </Card>

      {/* Schedule */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            برنامه کلاس
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">تاریخ ایجاد:</span>
              <span>{classDetail.createdAt || 'نامشخص'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">تعداد دروس:</span>
              <span>{totalLessons} درس</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">منتشر شده:</span>
              <span>{publishedLessons} درس</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
