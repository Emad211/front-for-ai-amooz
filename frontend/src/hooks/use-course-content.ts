'use client';

import { useCallback, useEffect, useState } from 'react';
import { CourseContent, Lesson } from '@/types';
import { DashboardService } from '@/services/dashboard-service';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type CourseContentService = {
  getCourseContent: (courseId?: string) => Promise<CourseContent>;
  getLessonDetail: (lessonId: string) => Promise<Lesson>;
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
      const [contentData, lessonData] = await Promise.all([
        service.getCourseContent(courseId),
        service.getLessonDetail('1'), // Default lesson for mock
      ]);
      if (!mountedRef.current) return;
      setContent(contentData);
      setCurrentLesson(lessonData);
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
    reload
  };
}
