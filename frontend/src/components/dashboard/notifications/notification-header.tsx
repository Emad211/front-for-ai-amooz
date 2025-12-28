'use client';

import { Bell, CheckCheck, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface NotificationHeaderProps {
  unreadCount: number;
  filter: string;
  onFilterChange: (value: string) => void;
  onMarkAllAsRead: () => void;
}

export function NotificationHeader({
  unreadCount,
  filter,
  onFilterChange,
  onMarkAllAsRead,
}: NotificationHeaderProps) {
  return (
    <div className="flex flex-col gap-4 mb-4 sm:mb-6">
      <div className="flex items-center gap-3">
        <div className="p-2.5 sm:p-3 rounded-xl sm:rounded-2xl bg-primary/10">
          <Bell className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-foreground">اعلان‌ها</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">
            {unreadCount > 0 ? `${unreadCount} اعلان خوانده نشده` : 'همه اعلان‌ها خوانده شده‌اند'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <Select value={filter} onValueChange={onFilterChange}>
          <SelectTrigger className="w-[120px] sm:w-[140px] rounded-xl text-xs sm:text-sm h-9">
            <Filter className="w-3.5 h-3.5 sm:w-4 sm:h-4 me-1.5 sm:me-2" />
            <SelectValue placeholder="فیلتر" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">همه</SelectItem>
            <SelectItem value="unread">خوانده نشده</SelectItem>
            <SelectItem value="read">خوانده شده</SelectItem>
          </SelectContent>
        </Select>

        {unreadCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={onMarkAllAsRead}
            className="rounded-xl gap-1.5 h-9 text-xs sm:text-sm"
          >
            <CheckCheck className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            <span className="hidden xs:inline">خواندن همه</span>
            <span className="xs:hidden">خواندن</span>
          </Button>
        )}
      </div>
    </div>
  );
}
