'use client';

import { use, useCallback, useEffect, useState } from 'react';
import { Info, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { ClassStudentsHeader, ClassStudentsStats, ClassStudentsTable, InviteStudentsDialog } from '@/components/teacher/class-students';
import { addExamPrepInvites, deleteExamPrepInvite, fetchExamPrepSession, listExamPrepInvites, type ClassInvite } from '@/services/classes-service';
import { exportClassStudentsXlsx } from '@/lib/export-class-students-xlsx';
import type { ClassStudent } from '@/types';

interface PageProps {
  params: Promise<{ examId: string }>;
}

export default function TeacherExamStudentsPage({ params }: PageProps) {
  const { examId } = use(params);
  const [title, setTitle] = useState('');
  const [students, setStudents] = useState<ClassStudent[]>([]);
  const [isOrgExam, setIsOrgExam] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

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
      setIsOrgExam(detail.organization_id != null);
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

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportClassStudentsXlsx(title, students);
      toast.success('فایل اکسل آماده شد.');
    } catch (exportError) {
      toast.error(exportError instanceof Error ? exportError.message : 'ساخت فایل اکسل انجام نشد.');
    } finally {
      setIsExporting(false);
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
      <ClassStudentsHeader
        title={title}
        studentsCount={students.length}
        canManageRoster={!isOrgExam}
        onAddStudent={() => setInviteOpen(true)}
        onExport={() => void handleExport()}
        isExporting={isExporting}
      />
      <InviteStudentsDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        destinationTitle={title}
        successMessage="دعوت دانش‌آموزان به آمادگی آزمون ثبت شد."
        onSubmit={async (phones) => {
          await addExamPrepInvites(Number(examId), phones);
          await loadData();
        }}
      />

      {isOrgExam && (
        <div
          dir="rtl"
          className="rounded-2xl border border-border/60 bg-muted/40 p-4 text-sm text-muted-foreground flex items-start gap-2"
        >
          <Info className="h-4 w-4 mt-0.5 shrink-0 text-primary" />
          <span>
            این آزمون به سازمان آموزشی متصل است؛ فهرست دانش‌آموزان از «گروه آموزشی» توسط مدیر سازمان آموزشی
            تعیین و مدیریت می‌شود و قابل تغییر از این‌جا نیست.
          </span>
        </div>
      )}

      <ClassStudentsStats students={students} />

      <ClassStudentsTable
        students={students}
        onRemove={handleRemoveStudent}
        allowRemove={!isOrgExam}
      />
    </div>
  );
}

function mapInvitesToStudents(invites: ClassInvite[]): ClassStudent[] {
  return invites.map((inv) => ({
    id: String(inv.id),
    name: inv.phone,
    email: '',
    phone: inv.phone,
    inviteCode: inv.invite_code,
    avatar: '',
    joinDate: inv.created_at,
    progress: 0,
    lastActivity: inv.created_at,
    status: 'inactive',
  }));
}
