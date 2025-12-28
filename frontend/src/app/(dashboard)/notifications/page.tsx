'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { NotificationHeader, NotificationList } from '@/components/dashboard/notifications';
import { MOCK_NOTIFICATIONS, type Notification } from '@/constants/notifications-data';

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>(MOCK_NOTIFICATIONS);
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
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, isRead: true } : n))
    );
  };

  const handleMarkAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
  };

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
          <NotificationList
            notifications={filteredNotifications}
            onMarkAsRead={handleMarkAsRead}
          />
        </CardContent>
      </Card>
    </div>
  );
}
