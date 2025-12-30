'use client';

import { useCallback, useEffect, useState } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { AdminService } from '@/services/admin-service';
import { Ticket } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

export function useTickets(isAdmin = false) {
  const mountedRef = useMountedRef();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = isAdmin 
        ? await AdminService.getTickets() 
        : await DashboardService.getTickets();
      const filteredData = isAdmin ? data : data.filter(t => t.userId === 'user-1');
      if (mountedRef.current) setTickets(filteredData);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت تیکت‌ها');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, isAdmin]);

  useEffect(() => {
    reload();
  }, [reload]);
  return {
    tickets,
    isLoading,
    error,
    reload,
    setTickets,
  };
}
