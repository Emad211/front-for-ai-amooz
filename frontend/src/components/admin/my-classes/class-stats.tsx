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
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
        <CardContent className="flex items-center p-6">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center w-12 h-12 bg-primary/20 rounded-xl">
              <BookOpen className="w-6 h-6 text-primary" />
            </div>
          </div>
          <div className="mr-4">
            <p className="text-sm font-medium text-muted-foreground">کل کلاس‌ها</p>
            <p className="text-2xl font-bold text-foreground">{stats.totalClasses}</p>
          </div>
        </CardContent>
      </Card>
      
      <Card className="bg-gradient-to-br from-green-500/5 to-green-500/10 border-green-500/20">
        <CardContent className="flex items-center p-6">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center w-12 h-12 bg-green-500/20 rounded-xl">
              <BarChart3 className="w-6 h-6 text-green-500" />
            </div>
          </div>
          <div className="mr-4">
            <p className="text-sm font-medium text-muted-foreground">کلاس‌های فعال</p>
            <p className="text-2xl font-bold text-foreground">{stats.activeClasses}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-gradient-to-br from-blue-500/5 to-blue-500/10 border-blue-500/20">
        <CardContent className="flex items-center p-6">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center w-12 h-12 bg-blue-500/20 rounded-xl">
              <Users className="w-6 h-6 text-blue-500" />
            </div>
          </div>
          <div className="mr-4">
            <p className="text-sm font-medium text-muted-foreground">کل دانش‌آموزان</p>
            <p className="text-2xl font-bold text-foreground">{stats.totalStudents}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-gradient-to-br from-yellow-500/5 to-yellow-500/10 border-yellow-500/20">
        <CardContent className="flex items-center p-6">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center w-12 h-12 bg-yellow-500/20 rounded-xl">
              <Star className="w-6 h-6 text-yellow-500" />
            </div>
          </div>
          <div className="mr-4">
            <p className="text-sm font-medium text-muted-foreground">میانگین امتیاز</p>
            <p className="text-2xl font-bold text-foreground">{stats.averageRating}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}