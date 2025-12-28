'use client';

import { useState, useEffect, useMemo } from 'react';
import { AdminService } from '@/services/admin-service';
import { Course } from '@/types';

export function useAdminCourses() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');

  useEffect(() => {
    const fetchCourses = async () => {
      try {
        setIsLoading(true);
        const data = await AdminService.getCourses();
        setCourses(data);
      } catch (err) {
        setError('خطا در دریافت اطلاعات کلاس‌ها');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchCourses();
  }, []);

  const categories = useMemo(() => {
    return Array.from(new Set(courses.map(c => c.category)));
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
    filters: {
      searchTerm,
      setSearchTerm,
      categoryFilter,
      setCategoryFilter
    }
  };
}
