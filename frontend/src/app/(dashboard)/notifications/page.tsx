'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { NotificationHeader, NotificationList } from '@/components/dashboard/notifications';
import { type Notification } from '@/constants/mock';
import { useNotifications } from '@/hooks/use-notifications';
import { Skeleton } from '@/components/ui/skeleton';

export default function NotificationsPage() {
  const { notifications, isLoading, error, markAsRead } = useNotifications();
  const [filter, setFilter] = useState('all');

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.isRead).length,
    [notifications]
  );

  const filteredNotifications = useMemo(() => {
    switch (filter) {
      case 'unread':
        return notifications.filter((n) => !n.isRead);
      case 'read':
        return notifications.filter((n) => n.isRead);
      default:
        return notifications;
    }
  }, [notifications, filter]);

  const handleMarkAsRead = (id: string) => {
    markAsRead(id);
  };

  const handleMarkAllAsRead = () => {
    // In a real app, this would be an API call
    notifications.forEach(n => markAsRead(n.id));
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-destructive font-bold">{error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-0 space-y-4 sm:space-y-6">
      <NotificationHeader
        unreadCount={unreadCount}
        filter={filter}
        onFilterChange={setFilter}
        onMarkAllAsRead={handleMarkAllAsRead}
      />

      <Card className="rounded-2xl">
        <CardContent className="p-3 sm:p-4">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-20 w-full rounded-xl" />
              <Skeleton className="h-20 w-full rounded-xl" />
              <Skeleton className="h-20 w-full rounded-xl" />
            </div>
          ) : (
            <NotificationList
              notifications={filteredNotifications}
              onMarkAsRead={handleMarkAsRead}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
