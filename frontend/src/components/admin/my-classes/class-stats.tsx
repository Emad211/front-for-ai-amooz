'use client';

import { BookOpen, BarChart3, Users, Star } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface ClassStatsProps {
  stats: {
    totalClasses: number;
    activeClasses: number;
    totalStudents: number;
    averageRating: string;
  };
}

export function ClassStats({ stats }: ClassStatsProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
      <Card className="bg-card border-border/60 hover:border-primary/30 transition-colors">
        <CardContent className="flex items-center p-4 md:p-6">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-muted rounded-xl">
              <BookOpen className="w-5 h-5 md:w-6 md:h-6 text-muted-foreground" />
            </div>
          </div>
          <div className="mr-3 md:mr-4">
            <p className="text-[10px] md:text-sm font-medium text-muted-foreground">کل کلاس‌ها</p>
            <p className="text-lg md:text-2xl font-bold text-foreground">{stats.totalClasses}</p>
          </div>
        </CardContent>
      </Card>
      
      <Card className="bg-card border-border/60 hover:border-primary/30 transition-colors">
        <CardContent className="flex items-center p-4 md:p-6">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-muted rounded-xl">
              <BarChart3 className="w-5 h-5 md:w-6 md:h-6 text-muted-foreground" />
            </div>
          </div>
          <div className="mr-3 md:mr-4">
            <p className="text-[10px] md:text-sm font-medium text-muted-foreground">کلاس‌های فعال</p>
            <p className="text-lg md:text-2xl font-bold text-foreground">{stats.activeClasses}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border/60 hover:border-primary/30 transition-colors">
        <CardContent className="flex items-center p-4 md:p-6">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-muted rounded-xl">
              <Users className="w-5 h-5 md:w-6 md:h-6 text-muted-foreground" />
            </div>
          </div>
          <div className="mr-3 md:mr-4">
            <p className="text-[10px] md:text-sm font-medium text-muted-foreground">کل دانش‌آموزان</p>
            <p className="text-lg md:text-2xl font-bold text-foreground">{stats.totalStudents}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border/60 hover:border-primary/30 transition-colors">
        <CardContent className="flex items-center p-4 md:p-6">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center w-10 h-10 md:w-12 md:h-12 bg-muted rounded-xl">
              <Star className="w-5 h-5 md:w-6 md:h-6 text-muted-foreground" />
            </div>
          </div>
          <div className="mr-3 md:mr-4">
            <p className="text-[10px] md:text-sm font-medium text-muted-foreground">میانگین امتیاز</p>
            <p className="text-lg md:text-2xl font-bold text-foreground">{stats.averageRating}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}