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
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full">
          <ArrowRight className="h-5 w-5" />
        </Button>
        <div>
          <p className="text-sm text-muted-foreground">مدیریت دانش‌آموزان</p>
          <h1 className="text-xl font-bold">{title}</h1>
          <p className="text-sm text-muted-foreground">{studentsCount} دانش‌آموز</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onExport}>
          <Download className="h-4 w-4 ml-2" />
          خروجی اکسل
        </Button>
        <Button size="sm" onClick={onAddStudent}>
          <UserPlus className="h-4 w-4 ml-2" />
          افزودن دانش‌آموز
        </Button>
      </div>
    </div>
  );
}
