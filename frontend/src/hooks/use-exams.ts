'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Exam } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type ExamsService = {
  getExams: () => Promise<Exam[]>;
};

export function useExams(service: ExamsService = DashboardService) {
  const mountedRef = useMountedRef();
  const [exams, setExams] = useState<Exam[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  
  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await service.getExams();
      if (mountedRef.current) setExams(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اطلاعات آزمون‌ها');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, service]);

  useEffect(() => {
    reload();
  }, [reload]);

  const filteredExams = useMemo(() => {
    return exams.filter(exam => 
      exam.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      exam.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      exam.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()))
    );
  }, [exams, searchTerm]);

  return {
    exams: filteredExams,
    isLoading,
    error,
    reload,
    filters: {
      searchTerm,
      setSearchTerm
    }
  };
}
