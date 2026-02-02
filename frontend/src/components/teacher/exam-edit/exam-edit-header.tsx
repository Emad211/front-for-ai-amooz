'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface ExamEditHeaderProps {
  examId: string;
  title: string;
  status?: string;
  basePath?: string;
}

const statusConfig: Record<string, { label: string; color: string }> = {
  exam_structured: { label: 'تکمیل شده', color: 'bg-primary/10 text-primary' },
  exam_transcribed: { label: 'رونویسی شده', color: 'bg-muted text-muted-foreground' },
  exam_transcribing: { label: 'در حال رونویسی', color: 'bg-yellow-500/10 text-yellow-600' },
  exam_structuring: { label: 'در حال استخراج سوالات', color: 'bg-yellow-500/10 text-yellow-600' },
  pending: { label: 'در انتظار', color: 'bg-muted text-muted-foreground' },
  failed: { label: 'خطا', color: 'bg-destructive/10 text-destructive' },
};

export function ExamEditHeader({ examId, title, status = 'exam_structured', basePath = '/admin' }: ExamEditHeaderProps) {
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
        <Link href={`${basePath}/my-exams/${examId}`}>
          مشاهده آزمون
        </Link>
      </Button>
    </div>
  );
}
