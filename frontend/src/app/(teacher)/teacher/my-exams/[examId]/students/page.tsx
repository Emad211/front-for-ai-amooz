'use client';

import { use, useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { ClassStudentsHeader, ClassStudentsStats, ClassStudentsTable } from '@/components/teacher/class-students';
import { deleteExamPrepInvite, fetchExamPrepSession, listExamPrepInvites, type ClassInvite } from '@/services/classes-service';
import type { ClassStudent } from '@/types';

interface PageProps {
  params: Promise<{ examId: string }>;
}

export default function TeacherExamStudentsPage({ params }: PageProps) {
  const { examId } = use(params);
  const [title, setTitle] = useState('');
  const [students, setStudents] = useState<ClassStudent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    const sessionId = Number(examId);
    if (!Number.isFinite(sessionId)) {
      setError('شناسه آزمون نامعتبر است');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const [detail, invites] = await Promise.all([
        fetchExamPrepSession(sessionId),
        listExamPrepInvites(sessionId),
      ]);
      setTitle(detail.title || '');
      setStudents(mapInvitesToStudents(invites));
    } catch (err) {
      console.error(err);
      setError('خطا در دریافت اطلاعات آزمون');
    } finally {
      setIsLoading(false);
    }
  }, [examId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleRemoveStudent = async (studentId: string) => {
    const sessionId = Number(examId);
    const inviteId = Number(studentId);
    if (!Number.isFinite(sessionId) || !Number.isFinite(inviteId)) return;
    try {
      await deleteExamPrepInvite(sessionId, inviteId);
      toast.success('دانش‌آموز از آزمون حذف شد');
      void loadData();
    } catch (err) {
      console.error(err);
      toast.error('خطا در حذف دانش‌آموز');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ClassStudentsHeader title={title} studentsCount={students.length} />

      <ClassStudentsStats students={students} />

      <ClassStudentsTable students={students} onRemove={handleRemoveStudent} />
    </div>
  );
}

function mapInvitesToStudents(invites: ClassInvite[]): ClassStudent[] {
  return invites.map((inv) => ({
    id: String(inv.id),
    name: inv.phone,
    email: inv.invite_code,
    avatar: '',
    joinDate: inv.created_at,
    progress: 0,
    lastActivity: inv.created_at,
    status: 'inactive',
  }));
}
