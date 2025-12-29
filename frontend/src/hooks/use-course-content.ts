'use client';

import { useState, useEffect } from 'react';
import { CourseContent } from '@/constants/mock/course-content-data';
import { DashboardService } from '@/services/dashboard-service';

export function useCourseContent(courseId?: string) {
  const [content, setContent] = useState<CourseContent | null>(null);
  const [currentLesson, setCurrentLesson] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchContent = async () => {
      try {
        setIsLoading(true);
        const [contentData, lessonData] = await Promise.all([
          DashboardService.getCourseContent(courseId),
          DashboardService.getLessonDetail('1') // Default lesson for mock
        ]);
        setContent(contentData);
        setCurrentLesson(lessonData);
      } catch (err) {
        setError('خطا در دریافت محتوای دوره');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchContent();
  }, [courseId]);

  return {
    content,
    currentLesson,
    isLoading,
    error
  };
}
