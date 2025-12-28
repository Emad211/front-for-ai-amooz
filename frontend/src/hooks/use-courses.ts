'use client';

import { useState, useEffect, useMemo } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Course } from '@/constants/mock/user-data';

export function useCourses() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'recent' | 'progress'>('recent');

  useEffect(() => {
    const fetchCourses = async () => {
      try {
        setIsLoading(true);
        const data = await DashboardService.getCourses();
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

  const filteredCourses = useMemo(() => {
    return courses
      .filter(course => 
        course.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        course.instructor.toLowerCase().includes(searchTerm.toLowerCase())
      )
      .sort((a, b) => {
        if (sortBy === 'progress') {
          return b.progress - a.progress;
        }
        // Default to recent (assuming higher ID or some other logic if no date)
        return b.id.localeCompare(a.id);
      });
  }, [courses, searchTerm, sortBy]);

  return {
    courses: filteredCourses,
    isLoading,
    error,
    filters: {
      searchTerm,
      setSearchTerm,
      sortBy,
      setSortBy
    }
  };
}
