import { useCallback, useEffect, useState } from 'react';
import { TeacherService } from '@/services/teacher-service';
import type { ClassDetail, ClassStudent } from '@/types';

export function useTeacherClassDetail(classId: string) {
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [students, setStudents] = useState<ClassStudent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const [detailRes, studentsRes] = await Promise.all([
        TeacherService.getClassDetail(classId),
        TeacherService.getClassStudents(classId),
      ]);
      setDetail(detailRes);
      setStudents(studentsRes as ClassStudent[]);
    } catch (e) {
      console.error(e);
      setError('خطا در دریافت جزئیات کلاس');
    } finally {
      setIsLoading(false);
    }
  }, [classId]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { detail, students, isLoading, error, reload };
}
