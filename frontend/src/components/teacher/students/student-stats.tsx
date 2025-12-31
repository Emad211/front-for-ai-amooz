'use client';

import { Users, UserCheck, GraduationCap, BookOpen } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface StudentStatsProps {
  stats: {
    totalStudents: number;
    activeStudents: number;
    averageScore: number;
    totalEnrollments: number;
  };
}

export function StudentStats({ stats }: StudentStatsProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
      <Card className="bg-card border-border/60 shadow-sm hover:shadow-md transition-all duration-300">
        <CardContent className="flex items-center justify-between p-4 md:p-6">
          <div className="space-y-1">
            <p className="text-[10px] sm:text-xs font-medium text-muted-foreground">کل دانش‌آموزان</p>
            <p className="text-lg sm:text-2xl font-bold text-foreground tracking-tight">{stats.totalStudents}</p>
          </div>
          <div className="h-9 w-9 sm:h-10 sm:w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary shrink-0">
            <Users className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
        </CardContent>
      </Card>
      
      <Card className="bg-card border-border/60 shadow-sm hover:shadow-md transition-all duration-300">
        <CardContent className="flex items-center justify-between p-4 md:p-6">
          <div className="space-y-1">
            <p className="text-[10px] sm:text-xs font-medium text-muted-foreground">دانش‌آموزان فعال</p>
            <p className="text-lg sm:text-2xl font-bold text-foreground tracking-tight">{stats.activeStudents}</p>
          </div>
          <div className="h-9 w-9 sm:h-10 sm:w-10 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
            <UserCheck className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border/60 shadow-sm hover:shadow-md transition-all duration-300">
        <CardContent className="flex items-center justify-between p-4 md:p-6">
          <div className="space-y-1">
            <p className="text-[10px] sm:text-xs font-medium text-muted-foreground">میانگین نمره</p>
            <p className="text-lg sm:text-2xl font-bold text-foreground tracking-tight">{stats.averageScore}</p>
          </div>
          <div className="h-9 w-9 sm:h-10 sm:w-10 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-600 dark:text-blue-400 shrink-0">
            <GraduationCap className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border/60 shadow-sm hover:shadow-md transition-all duration-300">
        <CardContent className="flex items-center justify-between p-4 md:p-6">
          <div className="space-y-1">
            <p className="text-[10px] sm:text-xs font-medium text-muted-foreground">کل ثبت‌نام‌ها</p>
            <p className="text-lg sm:text-2xl font-bold text-foreground tracking-tight">{stats.totalEnrollments}</p>
          </div>
          <div className="h-9 w-9 sm:h-10 sm:w-10 rounded-full bg-violet-500/10 flex items-center justify-center text-violet-600 dark:text-violet-400 shrink-0">
            <BookOpen className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}