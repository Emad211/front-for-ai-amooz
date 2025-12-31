'use client';

import { Bell, Check, MessageSquare, Info, AlertTriangle, Trash2, ExternalLink } from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useNotifications } from '@/hooks/use-notifications';
import type { Notification } from '@/types';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function NotificationPopover() {
  const { notifications, isLoading, markAsRead, markAllAsRead, deleteNotification } = useNotifications();
  const pathname = usePathname();
  const isTeacher = pathname.startsWith('/teacher');
  const notificationsLink = isTeacher ? '/teacher/notifications' : '/notifications';
  
  const unreadCount = notifications.filter(n => !n.isRead).length;

  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'message': return <MessageSquare className="h-4 w-4 text-blue-500" />;
      case 'alert': return <AlertTriangle className="h-4 w-4 text-amber-500" />;
      case 'info': return <Info className="h-4 w-4 text-emerald-500" />;
    }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative h-9 w-9 md:h-10 md:w-10">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute top-2.5 right-2.5 w-2 h-2 bg-primary rounded-full border-2 border-background animate-pulse"></span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0" dir="rtl">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <h4 className="font-bold">اعلان‌ها</h4>
            {unreadCount > 0 && (
              <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
                {unreadCount} جدید
              </Badge>
            )}
          </div>
          {unreadCount > 0 && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={markAllAsRead}
              className="h-auto p-0 text-xs text-primary hover:bg-transparent"
            >
              خوانده شده همه
            </Button>
          )}
        </div>
        
        <ScrollArea className="h-[350px]">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-[300px] text-muted-foreground space-y-2">
              <Bell className="h-8 w-8 opacity-20" />
              <p className="text-sm">در حال بارگذاری...</p>
            </div>
          ) : notifications.length > 0 ? (
            <div className="flex flex-col">
              {notifications.map((notification) => (
                <div 
                  key={notification.id}
                  className={cn(
                    "p-4 border-b last:border-0 transition-colors hover:bg-muted/50 relative group",
                    !notification.isRead && "bg-primary/5"
                  )}
                >
                  <div className="flex gap-3">
                    <div className="mt-1">
                      {getIcon(notification.type)}
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center justify-between">
                        <p className={cn(
                          "text-sm font-medium leading-none",
                          !notification.isRead ? "text-foreground" : "text-muted-foreground"
                        )}>
                          {notification.title}
                        </p>
                        <span className="text-[10px] text-muted-foreground">
                          {notification.time}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                        {notification.message}
                      </p>
                    </div>
                  </div>
                  
                  <div className="absolute left-2 top-1/2 -translate-y-1/2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {!notification.isRead && (
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-7 w-7 rounded-full hover:bg-primary/10 hover:text-primary"
                        onClick={() => markAsRead(notification.id)}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-7 w-7 rounded-full hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => deleteNotification(notification.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-[300px] text-muted-foreground space-y-2">
              <Bell className="h-8 w-8 opacity-20" />
              <p className="text-sm">اعلانی وجود ندارد</p>
            </div>
          )}
        </ScrollArea>
        
        <div className="p-2 border-t bg-muted/20">
          <Button 
            variant="ghost" 
            size="sm" 
            className="w-full text-xs font-bold text-primary hover:bg-primary/5"
            asChild
          >
            <Link href={notificationsLink} className="flex items-center justify-center gap-2">
              مشاهده همه اعلان‌ها
              <ExternalLink className="w-3 h-3" />
            </Link>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
