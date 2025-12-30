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
  active: { label: 'فعال', color: 'bg-primary/10 text-primary' },
  draft: { label: 'پیش‌نویس', color: 'bg-muted text-muted-foreground' },
  paused: { label: 'متوقف', color: 'bg-muted text-muted-foreground' },
  archived: { label: 'آرشیو شده', color: 'bg-destructive/10 text-destructive' },
};

export function ClassEditHeader({ classId, title, status = 'draft' }: ClassEditHeaderProps) {
  const router = useRouter();

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full shrink-0">
          <ArrowRight className="h-5 w-5" />
        </Button>
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className={statusConfig[status]?.color}>
              {statusConfig[status]?.label}
            </Badge>
          </div>
          <h1 className="text-lg sm:text-xl font-bold">ویرایش: {title}</h1>
        </div>
      </div>
      <Button variant="outline" asChild className="w-full sm:w-auto">
        <Link href={`/admin/my-classes/${classId}`}>
          مشاهده کلاس
        </Link>
      </Button>
    </div>
  );
}
