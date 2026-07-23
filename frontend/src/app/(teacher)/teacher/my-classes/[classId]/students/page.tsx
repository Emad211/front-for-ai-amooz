'use client';

import { use, useState } from 'react';
import { Info, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useTeacherClassDetail } from '@/hooks/use-teacher-class-detail';
import { useTeacherClassActions } from '@/hooks/use-teacher-class-actions';
import { ClassWorkspaceNav } from '@/components/teacher/class-detail';
import {
  ClassStudentsHeader,
  ClassStudentsStats,
  ClassStudentsTable,
  InviteStudentsDialog,
} from '@/components/teacher/class-students';
import { addClassInvites } from '@/services/classes-service';
import { exportClassStudentsXlsx } from '@/lib/export-class-students-xlsx';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function TeacherClassStudentsPage({ params }: PageProps) {
  const { classId } = use(params);
  const { detail, students, isLoading, error, reload } = useTeacherClassDetail(classId);
  const { removeStudent } = useTeacherClassActions(classId);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const handleRemoveStudent = async (studentId: string) => {
    const ok = await removeStudent(studentId);
    if (ok) {
      toast.success('دانش‌آموز از کلاس حذف شد');
      reload();
    } else {
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

  if (error || !detail) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-destructive">خطا در بارگذاری اطلاعات</p>
      </div>
    );
  }

  const isOrgClass = detail.organizationId != null;

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportClassStudentsXlsx(detail.title, students);
      toast.success('فایل اکسل آماده شد.');
    } catch (exportError) {
      toast.error(exportError instanceof Error ? exportError.message : 'ساخت فایل اکسل انجام نشد.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <ClassStudentsHeader
        title={detail.title}
        studentsCount={students.length}
        canManageRoster={!isOrgClass}
        onAddStudent={() => setInviteOpen(true)}
        onExport={() => void handleExport()}
        isExporting={isExporting}
      />
      <InviteStudentsDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        destinationTitle={detail.title}
        successMessage="دعوت ثبت شد؛ دانش‌آموز پس از ورود به کلاس در این فهرست نمایش داده می‌شود."
        onSubmit={async (phones) => {
          await addClassInvites(Number(classId), phones);
          await reload();
        }}
      />
      <ClassWorkspaceNav classId={classId} basePath="/teacher" pendingExercises={detail.pendingExercises} />

      {isOrgClass && (
        <div
          dir="rtl"
          className="rounded-2xl border border-border/60 bg-muted/40 p-4 text-sm text-muted-foreground flex items-start gap-2"
        >
          <Info className="h-4 w-4 mt-0.5 shrink-0 text-primary" />
          <span>
            این کلاس به سازمان آموزشی متصل است؛ فهرست دانش‌آموزان از «گروه آموزشی» توسط مدیر سازمان آموزشی
            تعیین و مدیریت می‌شود و قابل تغییر از این‌جا نیست.
          </span>
        </div>
      )}

      <ClassStudentsStats students={students} />

      <ClassStudentsTable
        students={students}
        onRemove={handleRemoveStudent}
        allowRemove={!isOrgClass}
      />
    </div>
  );
}
