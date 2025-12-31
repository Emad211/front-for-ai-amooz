'use client';

import { useRouter } from 'next/navigation';
import { ArrowRight, UserPlus, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ClassStudentsHeaderProps {
  title: string;
  studentsCount: number;
  onAddStudent?: () => void;
  onExport?: () => void;
}

export function ClassStudentsHeader({ 
  title, 
  studentsCount,
  onAddStudent,
  onExport,
}: ClassStudentsHeaderProps) {
  const router = useRouter();

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full shrink-0">
          <ArrowRight className="h-5 w-5" />
        </Button>
        <div>
          <p className="text-xs sm:text-sm text-muted-foreground">مدیریت دانش‌آموزان</p>
          <h1 className="text-lg sm:text-xl font-bold">{title}</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">{studentsCount} دانش‌آموز</p>
        </div>
      </div>
      <div className="flex items-center gap-2 w-full sm:w-auto">
        <Button variant="outline" size="sm" onClick={onExport} className="flex-1 sm:flex-none">
          <Download className="h-4 w-4 sm:ml-2" />
          <span className="hidden sm:inline">خروجی اکسل</span>
        </Button>
        <Button size="sm" onClick={onAddStudent} className="flex-1 sm:flex-none">
          <UserPlus className="h-4 w-4 sm:ml-2" />
          <span className="hidden sm:inline">افزودن دانش‌آموز</span>
        </Button>
      </div>
    </div>
  );
}
