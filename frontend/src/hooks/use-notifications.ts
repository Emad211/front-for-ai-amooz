'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Notification } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type NotificationsService = {
  getNotifications: () => Promise<Notification[]>;
  markNotificationRead?: (id: string) => Promise<any>;
  markAllNotificationsRead?: () => Promise<any>;
};

export function useNotifications(service: NotificationsService = DashboardService) {
  const mountedRef = useMountedRef();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Track first load with a ref so `reload` stays referentially stable. Putting
  // notifications.length in the dep array recreated `reload` after the first
  // fetch, which re-fired the effect below → a guaranteed double-fetch on mount.
  const hasLoadedRef = useRef(false);

  const reload = useCallback(async () => {
    try {
      setError(null);
      // Only show the loading state on the initial fetch (avoid flicker on refresh).
      if (!hasLoadedRef.current) setIsLoading(true);
      const data = await service.getNotifications();
      if (mountedRef.current) setNotifications(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اعلان‌ها');
    } finally {
      hasLoadedRef.current = true;
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, service]);

  useEffect(() => {
    reload();
  }, [reload]);

  const markAsRead = async (id: string) => {
    // Optimistic UI update
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, isRead: true } : n));
    
    // Server sync
    if (service.markNotificationRead) {
      try {
        await service.markNotificationRead(id);
      } catch (err) {
        console.error('Failed to sync notification read status:', err);
      }
    }
  };

  const markAllAsRead = async () => {
    // Optimistic UI update
    setNotifications(prev => prev.map(n => ({ ...n, isRead: true })));

    // Server sync
    if (service.markAllNotificationsRead) {
      try {
        await service.markAllNotificationsRead();
      } catch (err) {
        console.error('Failed to sync all notifications read status:', err);
      }
    }
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
