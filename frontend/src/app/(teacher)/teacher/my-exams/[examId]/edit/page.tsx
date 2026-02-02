'use client';

import { use, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchExamPrepSession,
  updateExamPrepSession,
  type ExamPrepSessionDetail,
} from '@/services/classes-service';
import { ExamEditHeader, ExamEditForm } from '@/components/teacher/exam-edit';

interface PageProps {
  params: Promise<{ examId: string }>;
}

export default function TeacherExamEditPage({ params }: PageProps) {
  const { examId } = use(params);
  const [detail, setDetail] = useState<ExamPrepSessionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const sessionId = Number(examId);
    if (!Number.isFinite(sessionId)) {
      setError('شناسه آزمون نامعتبر است');
      setIsLoading(false);
      return;
    }

    const fetchData = async () => {
      try {
        const data = await fetchExamPrepSession(sessionId);
        setDetail(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'خطا در دریافت اطلاعات آزمون');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [examId]);

  const handleSave = async (data: Partial<ExamPrepSessionDetail>) => {
    if (!detail) return;

    setIsSaving(true);
    try {
      const updated = await updateExamPrepSession(detail.id, data as any);
      setDetail(updated);
      toast.success('تغییرات با موفقیت ذخیره شد');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ذخیره تغییرات');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-destructive">{error || 'خطا در بارگذاری اطلاعات آزمون'}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ExamEditHeader examId={examId} title={detail.title} status={detail.status} basePath="/teacher" />
      <ExamEditForm examDetail={detail} onSave={handleSave} isSaving={isSaving} />
    </div>
  );
}
