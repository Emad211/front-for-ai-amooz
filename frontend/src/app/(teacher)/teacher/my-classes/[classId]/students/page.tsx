'use client';

import { use } from 'react';
import { Info, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useTeacherClassDetail } from '@/hooks/use-teacher-class-detail';
import { useTeacherClassActions } from '@/hooks/use-teacher-class-actions';
import {
  ClassStudentsHeader,
  ClassStudentsStats,
  ClassStudentsTable,
} from '@/components/teacher/class-students';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function TeacherClassStudentsPage({ params }: PageProps) {
  const { classId } = use(params);
  const { detail, students, isLoading, error, reload } = useTeacherClassDetail(classId);
  const { removeStudent } = useTeacherClassActions(classId);

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

  return (
    <div className="space-y-6">
      <ClassStudentsHeader
        title={detail.title}
        studentsCount={students.length}
        canManageRoster={!isOrgClass}
      />

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
