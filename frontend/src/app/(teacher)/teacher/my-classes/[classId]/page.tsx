'use client';

import { use } from 'react';
import { Loader2 } from 'lucide-react';
import { useTeacherClassDetail } from '@/hooks/use-teacher-class-detail';
import {
  ClassDetailHeader,
  ClassInfoCard,
  ClassChaptersCard,
  ClassStudentsPreview,
  ClassStatsSidebar,
  ClassAnnouncementsCard,
} from '@/components/admin/class-detail';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function TeacherClassDetailPage({ params }: PageProps) {
  const { classId } = use(params);
  const { detail, students, isLoading, error } = useTeacherClassDetail(classId);

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
        <p className="text-destructive">خطا در بارگذاری اطلاعات کلاس</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ClassDetailHeader
        classId={classId}
        title={detail.title}
        category={detail.category}
        level={detail.level}
        status={detail.status}
        basePath="/teacher"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <ClassInfoCard description={detail.description} tags={detail.tags} />
          <ClassChaptersCard classId={classId} chapters={detail.chapters || []} basePath="/teacher" />
          <ClassStudentsPreview classId={classId} students={students} basePath="/teacher" />
          <ClassAnnouncementsCard />
        </div>

        <div className="lg:col-span-1">
          <ClassStatsSidebar classDetail={detail} totalStudents={students.length} />
        </div>
      </div>
    </div>
  );
}
