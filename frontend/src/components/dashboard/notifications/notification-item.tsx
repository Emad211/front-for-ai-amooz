'use client';

import { Bell, Info, CheckCircle, AlertTriangle, XCircle, MessageCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Notification, NotificationType } from '@/types';

interface NotificationItemProps {
  notification: Notification;
  onMarkAsRead: (id: string) => void;
}

const iconMap: Record<NotificationType, typeof Info> = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: XCircle,
  message: MessageCircle,
  alert: Bell,
};

const colorMap: Record<NotificationType, string> = {
  info: 'text-blue-500 bg-blue-500/10',
  success: 'text-green-500 bg-green-500/10',
  warning: 'text-amber-500 bg-amber-500/10',
  error: 'text-red-500 bg-red-500/10',
  message: 'text-purple-500 bg-purple-500/10',
  alert: 'text-orange-500 bg-orange-500/10',
};

export function NotificationItem({ notification, onMarkAsRead }: NotificationItemProps) {
  const Icon = iconMap[notification.type];
  const colorClass = colorMap[notification.type];

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('fa-IR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div
      className={cn(
        'flex items-start gap-3 sm:gap-4 p-3 sm:p-4 rounded-xl transition-colors cursor-pointer',
        notification.isRead 
          ? 'bg-muted/30 hover:bg-muted/50' 
          : 'bg-card hover:bg-muted/30 border border-border/50'
      )}
      onClick={() => !notification.isRead && onMarkAsRead(notification.id)}
    >
      <div className={cn('p-1.5 sm:p-2 rounded-lg shrink-0', colorClass)}>
        <Icon className="w-4 h-4 sm:w-5 sm:h-5" />
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1">
          <h3 className={cn(
            'font-medium truncate text-sm sm:text-base',
            notification.isRead ? 'text-muted-foreground' : 'text-foreground'
          )}>
            {notification.title}
          </h3>
          {!notification.isRead && (
            <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
          )}
        </div>
        <p className="text-xs sm:text-sm text-muted-foreground line-clamp-2">
          {notification.message}
        </p>
        <span className="text-[10px] sm:text-xs text-muted-foreground mt-1.5 sm:mt-2 block">
          {formatDate(notification.createdAt)}
        </span>
      </div>
    </div>
  );
}
