'use client';

import { useState, useEffect } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Notification } from '@/types';

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        setIsLoading(true);
        const data = await DashboardService.getNotifications();
        setNotifications(data);
      } catch (err) {
        setError('خطا در دریافت اعلان‌ها');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchNotifications();
  }, []);

  const markAsRead = (id: string) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
  };

  const deleteNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  return {
    notifications,
    isLoading,
    error,
    markAsRead,
    deleteNotification
  };
}
