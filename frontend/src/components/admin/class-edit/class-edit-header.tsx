'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface ClassEditHeaderProps {
  classId: string;
  title: string;
  status?: string;
}

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: 'فعال', color: 'bg-emerald-500/10 text-emerald-600' },
  draft: { label: 'پیش‌نویس', color: 'bg-amber-500/10 text-amber-600' },
  paused: { label: 'متوقف', color: 'bg-slate-500/10 text-slate-600' },
  archived: { label: 'آرشیو شده', color: 'bg-red-500/10 text-red-600' },
};

export function ClassEditHeader({ classId, title, status = 'draft' }: ClassEditHeaderProps) {
  const router = useRouter();

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full">
          <ArrowRight className="h-5 w-5" />
        </Button>
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className={statusConfig[status]?.color}>
              {statusConfig[status]?.label}
            </Badge>
          </div>
          <h1 className="text-xl font-bold">ویرایش: {title}</h1>
        </div>
      </div>
      <Button variant="outline" asChild>
        <Link href={`/admin/my-classes/${classId}`}>
          مشاهده کلاس
        </Link>
      </Button>
    </div>
  );
}
