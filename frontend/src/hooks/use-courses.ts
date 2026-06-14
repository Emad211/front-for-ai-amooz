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
      const msg = err instanceof Error ? err.message : 'خطا در دریافت اطلاعات کلاس‌ها';
      if (mountedRef.current) setError(msg);
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, service]);

  useEffect(() => {
    reload();
  }, [reload]);

  const filteredCourses = useMemo(() => {
    // "Newest first": prefer a real creation timestamp, then fall back to a
    // NUMERIC id. The old code did `String(b.id).localeCompare(String(a.id))`
    // which compares ids as text — so id "12" sorted *after* "8" (because
    // '1' < '8'), pushing the newest, not-yet-started course to the end.
    const createdTime = (c: Course): number => {
      const raw = c.createdAt ?? (c as unknown as { created_at?: string }).created_at;
      const t = raw ? Date.parse(raw) : NaN;
      return Number.isNaN(t) ? NaN : t;
    };
    return courses
      .filter(course =>
        course.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (course.instructor?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false)
      )
      .sort((a, b) => {
        if (sortBy === 'progress') {
          return (b.progress || 0) - (a.progress || 0);
        }
        const ta = createdTime(a);
        const tb = createdTime(b);
        if (!Number.isNaN(ta) && !Number.isNaN(tb) && ta !== tb) {
          return tb - ta; // newest createdAt first
        }
        const na = Number(a.id);
        const nb = Number(b.id);
        if (Number.isFinite(na) && Number.isFinite(nb) && na !== nb) {
          return nb - na; // higher (newer) numeric id first
        }
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
