'use client';

import { useState, useEffect, useCallback } from 'react';
import { listExamPrepSessions, type ExamPrepSessionDetail } from '@/services/classes-service';

export interface UseTeacherExamPrepsReturn {
  examPreps: ExamPrepSessionDetail[];
  isLoading: boolean;
  error: string | null;
  reload: () => void;
  filters: {
    searchTerm: string;
    setSearchTerm: (term: string) => void;
    statusFilter: string;
    setStatusFilter: (status: string) => void;
  };
  stats: {
    total: number;
    published: number;
    processing: number;
    draft: number;
  };
}

export function useTeacherExamPreps(): UseTeacherExamPrepsReturn {
  const [examPreps, setExamPreps] = useState<ExamPrepSessionDetail[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listExamPrepSessions();
      setExamPreps(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در دریافت اطلاعات');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filteredExamPreps = examPreps.filter((ep) => {
    const matchesSearch =
      searchTerm === '' ||
      ep.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ep.description?.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'published' && ep.is_published) ||
      (statusFilter === 'processing' && ['exam_transcribing', 'exam_structuring'].includes(ep.status)) ||
      (statusFilter === 'draft' && !ep.is_published && !['exam_transcribing', 'exam_structuring'].includes(ep.status));

    return matchesSearch && matchesStatus;
  });

  const stats = {
    total: examPreps.length,
    published: examPreps.filter((ep) => ep.is_published).length,
    processing: examPreps.filter((ep) => ['exam_transcribing', 'exam_structuring'].includes(ep.status)).length,
    draft: examPreps.filter((ep) => !ep.is_published && !['exam_transcribing', 'exam_structuring'].includes(ep.status)).length,
  };

  return {
    examPreps: filteredExamPreps,
    isLoading,
    error,
    reload: fetchData,
    filters: {
      searchTerm,
      setSearchTerm,
      statusFilter,
      setStatusFilter,
    },
    stats,
  };
}
