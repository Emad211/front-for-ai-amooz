'use client';

import { use } from 'react';
import { Loader2 } from 'lucide-react';
import { useTeacherClassDetail as useClassDetail } from '@/hooks/use-teacher-class-detail';
import {
  ClassDetailHeader,
  ClassInfoCard,
  ClassChaptersCard,
  ClassStudentsPreview,
  ClassStatsSidebar,
  ClassAnnouncementsCard,
} from '@/components/teacher/class-detail';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function ClassDetailPage({ params }: PageProps) {
  const { classId } = use(params);
  const { detail: classDetail, students, isLoading, error } = useClassDetail(classId);

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
        <p className="text-destructive">خطا در بارگذاری اطلاعات کلاس</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ClassDetailHeader 
        classId={classId}
        title={classDetail.title}
        category={classDetail.category}
        level={classDetail.level}
        status={classDetail.status}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          <ClassInfoCard 
            description={classDetail.description}
            tags={classDetail.tags}
          />
          
          <ClassChaptersCard 
            classId={classId}
            chapters={classDetail.chapters || []}
          />
          
          <ClassStudentsPreview 
            classId={classId}
            students={students}
          />
          
          <ClassAnnouncementsCard />
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1">
          <ClassStatsSidebar 
            classDetail={classDetail}
            totalStudents={students.length}
          />
        </div>
      </div>
    </div>
  );
}
