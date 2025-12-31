"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Student } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type StudentsService = {
  getStudents: () => Promise<Student[]>;
};

export function useStudents(service: StudentsService) {
  const mountedRef = useMountedRef();
  const [students, setStudents] = useState<Student[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [performanceFilter, setPerformanceFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recent');

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await service.getStudents();
      if (mountedRef.current) setStudents(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت لیست دانش‌آموزان');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef]);

  useEffect(() => {
    reload();
  }, [reload]);

  const filteredStudents = useMemo(() => {
    return students
      .filter(student => {
        const matchesSearch = student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                             student.email.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesStatus = statusFilter === 'all' || student.status === statusFilter;
        const matchesPerformance = performanceFilter === 'all' || student.performance === performanceFilter;
        return matchesSearch && matchesStatus && matchesPerformance;
      })
      .sort((a, b) => {
        switch (sortBy) {
          case 'recent':
            return new Date(b.lastActivity || 0).getTime() - new Date(a.lastActivity || 0).getTime();
          case 'name':
            return a.name.localeCompare(b.name, 'fa');
          case 'score':
            return b.averageScore - a.averageScore;
          case 'progress':
            return (b.completedLessons / b.totalLessons) - (a.completedLessons / a.totalLessons);
          default:
            return 0;
        }
      });
  }, [students, searchTerm, statusFilter, performanceFilter, sortBy]);

  const stats = useMemo(() => {
    if (students.length === 0) return {
      totalStudents: 0,
      activeStudents: 0,
      averageScore: 0,
      totalEnrollments: 0,
    };

    return {
      totalStudents: students.length,
      activeStudents: students.filter(s => s.status === 'active').length,
      averageScore: Math.round(students.reduce((sum, s) => sum + s.averageScore, 0) / students.length),
      totalEnrollments: students.reduce((sum, s) => sum + s.enrolledClasses, 0),
    };
  }, [students]);

  return {
    students: filteredStudents,
    stats,
    isLoading,
    error,
    reload,
    filters: {
      searchTerm,
      setSearchTerm,
      statusFilter,
      setStatusFilter,
      performanceFilter,
      setPerformanceFilter,
      sortBy,
      setSortBy
    }
  };
}
