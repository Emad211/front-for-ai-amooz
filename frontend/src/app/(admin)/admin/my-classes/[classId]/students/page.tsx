'use client';

import { use } from 'react';
import { Loader2 } from 'lucide-react';
import { useClassDetail } from '@/hooks/use-class-detail';
import { toast } from 'sonner';
import {
  ClassStudentsHeader,
  ClassStudentsStats,
  ClassStudentsTable,
} from '@/components/admin/class-students';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function ClassStudentsPage({ params }: PageProps) {
  const { classId } = use(params);
  const { classDetail, students, isLoading, error, removeStudent } = useClassDetail(classId);

  const handleRemoveStudent = async (studentId: string) => {
    try {
      await removeStudent(studentId);
      toast.success('دانش‌آموز از کلاس حذف شد');
    } catch {
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

  if (error || !classDetail) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-destructive">خطا در بارگذاری اطلاعات</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ClassStudentsHeader 
        title={classDetail.title}
        studentsCount={students.length}
      />

      <ClassStudentsStats students={students} />

      <ClassStudentsTable 
        students={students}
        onRemove={handleRemoveStudent}
      />
    </div>
  );
}
