'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { NotificationHeader, NotificationList } from '@/components/dashboard/notifications';
import { useNotifications } from '@/hooks/use-notifications';
import { TeacherService } from '@/services/teacher-service';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { Bell } from 'lucide-react';
import { motion } from 'framer-motion';

export default function TeacherNotificationsPage() {
  const { notifications, isLoading, error, reload, markAsRead } = useNotifications(TeacherService);
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
    notifications.forEach(n => markAsRead(n.id));
  };

  if (error) {
    return (
      <div className="max-w-4xl mx-auto py-10">
        <ErrorState title="خطا در دریافت اعلان‌ها" description={error} onRetry={reload} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-foreground flex items-center gap-3">
            <Bell className="w-8 h-8 text-primary" />
            اعلان‌ها
          </h1>
          <p className="text-muted-foreground font-bold mt-1">
            آخرین رویدادها و پیام‌های سیستم را در اینجا مشاهده کنید
          </p>
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-6"
      >
        <NotificationHeader
          unreadCount={unreadCount}
          filter={filter}
          onFilterChange={setFilter}
          onMarkAllAsRead={handleMarkAllAsRead}
        />

        <Card className="rounded-3xl border-border/40 shadow-sm overflow-hidden">
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-6 space-y-4">
                <Skeleton className="h-24 w-full rounded-2xl" />
                <Skeleton className="h-24 w-full rounded-2xl" />
                <Skeleton className="h-24 w-full rounded-2xl" />
              </div>
            ) : (
              <NotificationList
                notifications={filteredNotifications}
                onMarkAsRead={handleMarkAsRead}
              />
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
