'use client';

import { use, useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useClassDetail } from '@/hooks/use-class-detail';
import { toast } from 'sonner';
import {
  ClassEditHeader,
  ClassEditForm,
  ClassChaptersEditor,
} from '@/components/admin/class-edit';
import type { ClassChapter, ClassDetail } from '@/types';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function ClassEditPage({ params }: PageProps) {
  const { classId } = use(params);
  const { classDetail, isLoading, error, updateClass, isUpdating } = useClassDetail(classId);
  const [chapters, setChapters] = useState<ClassChapter[]>([]);

  // Initialize chapters when classDetail loads
  useEffect(() => {
    if (classDetail?.chapters && chapters.length === 0) {
      setChapters(classDetail.chapters);
    }
  }, [classDetail, chapters.length]);

  const handleSave = async (data: Partial<ClassDetail>) => {
    try {
      await updateClass(data);
      toast.success('تغییرات با موفقیت ذخیره شد');
    } catch {
      toast.error('خطا در ذخیره تغییرات');
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
        <p className="text-destructive">خطا در بارگذاری اطلاعات کلاس</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ClassEditHeader 
        classId={classId}
        title={classDetail.title}
        status={classDetail.status}
      />

      <div className="space-y-6">
        <ClassEditForm 
          classDetail={classDetail}
          onSave={handleSave}
          isSaving={isUpdating}
        />

        <ClassChaptersEditor 
          chapters={chapters.length > 0 ? chapters : (classDetail.chapters || [])}
          onChange={setChapters}
        />
      </div>
    </div>
  );
}
