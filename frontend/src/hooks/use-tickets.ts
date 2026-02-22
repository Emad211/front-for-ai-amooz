'use client';

import { useCallback, useEffect, useState } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { AdminService } from '@/services/admin-service';
import { Ticket } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type TicketService = {
  getTickets: () => Promise<Ticket[]>;
};

type TicketsOptions = {
  isAdmin?: boolean;
  userService?: TicketService;
  adminService?: TicketService;
};

export function useTickets(options: boolean | TicketsOptions = {}) {
  const { isAdmin = false, userService = DashboardService, adminService = AdminService } =
    typeof options === 'boolean' ? { isAdmin: options } : options;
  const mountedRef = useMountedRef();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = isAdmin 
        ? await adminService.getTickets() 
        : await userService.getTickets();
      // Server already filters user tickets by authenticated user — no client-side filter needed.
      if (mountedRef.current) setTickets(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت تیکت‌ها');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [adminService, isAdmin, mountedRef, userService]);

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
