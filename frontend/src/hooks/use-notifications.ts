'use client';

import { useCallback, useEffect, useState } from 'react';
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

  const reload = useCallback(async () => {
    try {
      setError(null);
      // Only set loading on initial fetch to avoid flickering during read-sync
      if (notifications.length === 0) setIsLoading(true);
      const data = await service.getNotifications();
      if (mountedRef.current) setNotifications(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اعلان‌ها');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, service, notifications.length]);

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
