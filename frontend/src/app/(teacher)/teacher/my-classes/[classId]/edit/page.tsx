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
import {
  applyChaptersToCourseStructure,
  applyObjectivesToCourseStructure,
  courseStructureToObjectives,
  parseCourseStructure,
} from '@/lib/classes/course-structure';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function TeacherClassEditPage({ params }: PageProps) {
  const { classId } = use(params);
  const { detail, isLoading, error, reload } = useTeacherClassDetail(classId);
  const { updateClass, isLoading: isSaving } = useTeacherClassActions(classId);
  const [chapters, setChapters] = useState<ClassChapter[]>([]);
  const [objectives, setObjectives] = useState<string[]>([]);

  useEffect(() => {
    if (detail?.chapters && chapters.length === 0) {
      setChapters(detail.chapters);
    }
  }, [detail, chapters.length]);

  useEffect(() => {
    if (!detail) return;
    const structure = parseCourseStructure(detail.structureJson ?? '');
    setObjectives(courseStructureToObjectives(structure));
  }, [detail?.structureJson]);

  const handleSave = async (data: Partial<ClassDetail>) => {
    const baseStructure = parseCourseStructure(detail?.structureJson ?? '');
    const withObjectives = applyObjectivesToCourseStructure(baseStructure, objectives);
    const nextStructure = applyChaptersToCourseStructure(withObjectives, chapters);
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

        <div className="rounded-3xl border border-border/60 p-4 md:p-6 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-base font-black">اهداف یادگیری</div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setObjectives((prev) => [...prev, ''])}
            >
              افزودن هدف
            </Button>
          </div>

          {objectives.length === 0 ? (
            <div className="text-xs text-muted-foreground">—</div>
          ) : (
            <div className="space-y-2">
              {objectives.map((obj, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <Input
                    value={obj}
                    onChange={(e) =>
                      setObjectives((prev) => prev.map((x, i) => (i === idx ? e.target.value : x)))
                    }
                    className="text-start"
                    placeholder={`هدف ${idx + 1}`}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setObjectives((prev) => prev.filter((_, i) => i !== idx))}
                  >
                    حذف
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <ClassChaptersEditor
          chapters={chapters.length > 0 ? chapters : detail.chapters || []}
          onChange={setChapters}
        />
      </div>
    </div>
  );
}
