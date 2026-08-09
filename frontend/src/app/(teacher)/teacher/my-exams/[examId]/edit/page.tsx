'use client';

import { use, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchExamPrepSession,
  updateExamPrepSession,
  type ExamPrepSessionDetail,
  type ExamPrepSessionUpdatePayload,
} from '@/services/classes-service';
import { ExamEditHeader, ExamEditForm } from '@/components/teacher/exam-edit';
import { SourceAwareExamEditForm } from '@/components/teacher/exam-edit/source-aware-exam-edit-form';

interface PageProps {
  params: Promise<{ examId: string }>;
}

function isSourceAware(detail: ExamPrepSessionDetail): boolean {
  return Boolean(
    detail.exam_prep_data?.exam_prep.questions.some((question) =>
      String(question.question_id || '').startsWith('v4-'),
    ),
  );
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

  const handleSave = async (data: ExamPrepSessionUpdatePayload) => {
    if (!detail) return;

    setIsSaving(true);
    try {
      const updated = await updateExamPrepSession(detail.id, data);
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
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <p className="text-destructive">{error || 'خطا در بارگذاری اطلاعات آزمون'}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ExamEditHeader examId={examId} title={detail.title} status={detail.status} basePath="/teacher" />
      {isSourceAware(detail) ? (
        <SourceAwareExamEditForm examDetail={detail} onSave={handleSave} isSaving={isSaving} />
      ) : (
        <ExamEditForm examDetail={detail} onSave={handleSave} isSaving={isSaving} />
      )}
    </div>
  );
}
