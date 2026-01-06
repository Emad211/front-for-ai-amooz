'use client';

import { useCallback, useEffect, useState } from 'react';
import { CourseContent, Lesson } from '@/types';
import { DashboardService } from '@/services/dashboard-service';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type CourseContentService = {
  getCourseContent: (courseId?: string) => Promise<CourseContent>;
};

export function useCourseContent(courseId?: string, service: CourseContentService = DashboardService) {
  const mountedRef = useMountedRef();
  const [content, setContent] = useState<CourseContent | null>(null);
  const [currentLesson, setCurrentLesson] = useState<Lesson | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const contentData = await service.getCourseContent(courseId);
      if (!mountedRef.current) return;
      setContent(contentData);

      const allLessons = contentData.chapters.flatMap((c) => c.lessons);
      const activeLesson = allLessons.find((l) => l.isActive) ?? allLessons[0] ?? null;
      setCurrentLesson(activeLesson as Lesson | null);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت محتوای دوره');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [courseId, mountedRef, service]);

  useEffect(() => {
    reload();
  }, [reload]);

  return {
    content,
    currentLesson,
    isLoading,
    error,
    reload,
    setCurrentLesson,
    setContent,
  };
}
