'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, Users, Edit } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface ClassDetailHeaderProps {
  classId: string;
  title: string;
  status?: string;
  level?: string;
  category?: string;
}

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: 'فعال', color: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20' },
  draft: { label: 'پیش‌نویس', color: 'bg-amber-500/10 text-amber-600 border-amber-500/20' },
  paused: { label: 'متوقف', color: 'bg-slate-500/10 text-slate-600 border-slate-500/20' },
  archived: { label: 'آرشیو شده', color: 'bg-red-500/10 text-red-600 border-red-500/20' },
};

export function ClassDetailHeader({ 
  classId, 
  title, 
  status = 'draft', 
  level, 
  category,
}: ClassDetailHeaderProps) {
  const router = useRouter();
  
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-center gap-3 sm:gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full shrink-0">
          <ArrowRight className="h-5 w-5" />
        </Button>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mb-1">
            <Badge variant="outline" className={statusConfig[status]?.color}>
              {statusConfig[status]?.label}
            </Badge>
            {level && <Badge variant="outline">{level}</Badge>}
            {category && <Badge variant="secondary">{category}</Badge>}
          </div>
          <h1 className="text-xl sm:text-2xl font-bold truncate">{title}</h1>
        </div>
      </div>
      <div className="flex items-center gap-2 mr-10 sm:mr-0">
        <Button variant="outline" size="sm" className="sm:size-default" asChild>
          <Link href={`/admin/my-classes/${classId}/students`}>
            <Users className="h-4 w-4 sm:ml-2" />
            <span className="hidden sm:inline">مدیریت دانش‌آموزان</span>
          </Link>
        </Button>
        <Button size="sm" className="sm:size-default" asChild>
          <Link href={`/admin/my-classes/${classId}/edit`}>
            <Edit className="h-4 w-4 sm:ml-2" />
            <span className="hidden sm:inline">ویرایش محتوا</span>
          </Link>
        </Button>
      </div>
    </div>
  );
}
