'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AdminService } from '@/services/admin-service';
import { Course } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

export function useAdminCourses() {
  const mountedRef = useMountedRef();
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await AdminService.getCourses();
      if (mountedRef.current) setCourses(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اطلاعات کلاس‌ها');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef]);

  useEffect(() => {
    reload();
  }, [reload]);

  const categories = useMemo(() => {
    const definedCategories = courses
      .map((c) => c.category)
      .filter((category): category is string => Boolean(category));
    return Array.from(new Set(definedCategories));
  }, [courses]);

  const filteredCourses = useMemo(() => {
    return courses.filter(course => {
      const matchesSearch = course.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           (course.instructor?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false);
      const matchesCategory = categoryFilter === 'all' || course.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [courses, searchTerm, categoryFilter]);

  const stats = useMemo(() => {
    if (courses.length === 0) return { totalClasses: 0, activeClasses: 0, totalStudents: 0, averageRating: '0' };
    return {
      totalClasses: courses.length,
      activeClasses: courses.filter(cls => cls.status === 'active').length,
      totalStudents: courses.reduce((sum, cls) => sum + (cls.studentsCount || 0), 0),
      averageRating: (courses.reduce((sum, cls) => sum + (cls.rating || 0), 0) / courses.length).toFixed(1),
    };
  }, [courses]);

  return {
    courses: filteredCourses,
    categories,
    stats,
    isLoading,
    error,
    reload,
    filters: {
      searchTerm,
      setSearchTerm,
      categoryFilter,
      setCategoryFilter
    }
  };
}
