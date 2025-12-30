'use client';

import { useCallback, useEffect, useState } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Notification } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

export function useNotifications() {
  const mountedRef = useMountedRef();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await DashboardService.getNotifications();
      if (mountedRef.current) setNotifications(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اعلان‌ها');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef]);

  useEffect(() => {
    reload();
  }, [reload]);

  const markAsRead = (id: string) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, isRead: true } : n));
  };

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, isRead: true })));
  };

  const deleteNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  return {
    notifications,
    isLoading,
    error,
    reload,
    markAsRead,
    markAllAsRead,
    deleteNotification
  };
}
