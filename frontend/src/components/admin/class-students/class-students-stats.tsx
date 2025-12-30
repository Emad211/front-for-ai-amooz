'use client';

import { Users, UserCheck, UserX, TrendingUp } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { ClassStudent } from '@/types';

interface ClassStudentsStatsProps {
  students: ClassStudent[];
}

export function ClassStudentsStats({ students }: ClassStudentsStatsProps) {
  const activeCount = students.filter(s => s.status === 'active').length;
  const inactiveCount = students.filter(s => s.status === 'inactive').length;
  const avgProgress = students.length > 0 
    ? Math.round(students.reduce((acc, s) => acc + s.progress, 0) / students.length)
    : 0;

  const stats = [
    {
      icon: Users,
      label: 'کل دانش‌آموزان',
      value: students.length,
      color: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30',
    },
    {
      icon: UserCheck,
      label: 'دانش‌آموزان فعال',
      value: activeCount,
      color: 'text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30',
    },
    {
      icon: UserX,
      label: 'غیرفعال',
      value: inactiveCount,
      color: 'text-purple-600 bg-purple-100 dark:bg-purple-900/30',
    },
    {
      icon: TrendingUp,
      label: 'میانگین پیشرفت',
      value: `${avgProgress}%`,
      color: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map(({ icon: Icon, label, value, color }) => (
        <Card key={label}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl ${color}`}>
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{value}</p>
                <p className="text-xs text-muted-foreground">{label}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
