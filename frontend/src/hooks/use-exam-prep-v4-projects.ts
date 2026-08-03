'use client';

import { useCallback, useEffect, useState } from 'react';
import { normalizeApiError } from '@/services/auth-service';
import {
  listExamPrepV4Projects,
  type ExamPrepV4PaginatedProjects,
} from '@/services/exam-prep-v4-service';
import { useMountedRef } from '@/hooks/use-mounted-ref';

export function useExamPrepV4Projects() {
  const mountedRef = useMountedRef();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ExamPrepV4PaginatedProjects | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    listExamPrepV4Projects(page, controller.signal)
      .then((result) => {
        if (!mountedRef.current) return;
        setData(result);
      })
      .catch((requestError) => {
        if (!mountedRef.current || controller.signal.aborted) return;
        setError(normalizeApiError(requestError).message);
      })
      .finally(() => {
        if (mountedRef.current && !controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [mountedRef, page, reloadToken]);

  const reload = useCallback(() => {
    setReloadToken((value) => value + 1);
  }, []);

  const goToPage = useCallback((nextPage: number) => {
    setPage(Math.max(1, Math.trunc(nextPage)));
  }, []);

  return {
    projects: data?.results ?? [],
    total: data?.count ?? 0,
    page,
    hasNext: Boolean(data?.next),
    hasPrevious: Boolean(data?.previous),
    isLoading,
    error,
    reload,
    goToPage,
  };
}
