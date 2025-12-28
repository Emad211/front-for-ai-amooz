'use client';

import { useState, useEffect, useMemo } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Exam } from '@/types';

export function useExams() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    const fetchExams = async () => {
      try {
        setIsLoading(true);
        const data = await DashboardService.getExams();
        setExams(data);
      } catch (err) {
        setError('خطا در دریافت اطلاعات آزمون‌ها');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchExams();
  }, []);

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
    filters: {
      searchTerm,
      setSearchTerm
    }
  };
}
