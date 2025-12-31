'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Course } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type CoursesService = {
  getCourses: () => Promise<Course[]>;
};

export function useCourses(service: CoursesService = DashboardService) {
  const mountedRef = useMountedRef();
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'recent' | 'progress'>('recent');

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await service.getCourses();
      if (mountedRef.current) setCourses(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اطلاعات کلاس‌ها');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, service]);

  useEffect(() => {
    reload();
  }, [reload]);

  const filteredCourses = useMemo(() => {
    return courses
      .filter(course => 
        course.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (course.instructor?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false)
      )
      .sort((a, b) => {
        if (sortBy === 'progress') {
          return (b.progress || 0) - (a.progress || 0);
        }
        // Default to recent (assuming higher ID or some other logic if no date)
        return String(b.id).localeCompare(String(a.id));
      });
  }, [courses, searchTerm, sortBy]);

  return {
    courses: filteredCourses,
    isLoading,
    error,
    reload,
    filters: {
      searchTerm,
      setSearchTerm,
      sortBy,
      setSortBy
    }
  };
}
