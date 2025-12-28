'use client';

import { useState, useEffect, useMemo } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { AdminService } from '@/services/admin-service';
import { Ticket } from '@/types';

export function useTickets(isAdmin = false) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTickets = async () => {
      try {
        setIsLoading(true);
        const data = isAdmin 
          ? await AdminService.getTickets() 
          : await DashboardService.getTickets();
        
        // If not admin, filter for current user (mock user-1)
        const filteredData = isAdmin ? data : data.filter(t => t.userId === 'user-1');
        setTickets(filteredData);
      } catch (err) {
        setError('خطا در دریافت تیکت‌ها');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTickets();
  }, [isAdmin]);

  return {
    tickets,
    isLoading,
    error,
    setTickets
  };
}
