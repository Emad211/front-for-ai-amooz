'use client';

import { use, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useTeacherClassDetail } from '@/hooks/use-teacher-class-detail';
import { useTeacherClassActions } from '@/hooks/use-teacher-class-actions';
import {
  ClassEditHeader,
  ClassEditForm,
  ClassChaptersEditor,
} from '@/components/teacher/class-edit';
import type { ClassChapter, ClassDetail } from '@/types';
import { applyChaptersToCourseStructure, parseCourseStructure } from '@/lib/classes/course-structure';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function TeacherClassEditPage({ params }: PageProps) {
  const { classId } = use(params);
  const { detail, isLoading, error, reload } = useTeacherClassDetail(classId);
  const { updateClass, isLoading: isSaving } = useTeacherClassActions(classId);
  const [chapters, setChapters] = useState<ClassChapter[]>([]);

  useEffect(() => {
    if (detail?.chapters && chapters.length === 0) {
      setChapters(detail.chapters);
    }
  }, [detail, chapters.length]);

  const handleSave = async (data: Partial<ClassDetail>) => {
    const baseStructure = parseCourseStructure(detail?.structureJson ?? '');
    const nextStructure = applyChaptersToCourseStructure(baseStructure, chapters);
    const nextStructureJson = JSON.stringify(nextStructure, null, 2);

    const ok = await updateClass({
      ...data,
      structureJson: nextStructureJson,
    } as any);
    if (ok) {
      toast.success('تغییرات با موفقیت ذخیره شد');
      reload();
    } else {
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

  if (error || !detail) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-destructive">خطا در بارگذاری اطلاعات کلاس</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ClassEditHeader classId={classId} title={detail.title} status={detail.status} basePath="/teacher" />

      <div className="space-y-6">
        <ClassEditForm classDetail={detail} onSave={handleSave} isSaving={isSaving} />

        <ClassChaptersEditor
          chapters={chapters.length > 0 ? chapters : detail.chapters || []}
          onChange={setChapters}
        />
      </div>
    </div>
  );
}
