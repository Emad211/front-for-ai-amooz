'use client';

import { useCallback, useEffect, useState } from 'react';
import { CourseContent, Lesson } from '@/types';
import { DashboardService } from '@/services/dashboard-service';
import { useMountedRef } from '@/hooks/use-mounted-ref';

export function useCourseContent(courseId?: string) {
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
        DashboardService.getCourseContent(courseId),
        DashboardService.getLessonDetail('1'), // Default lesson for mock
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
  }, [courseId, mountedRef]);

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
