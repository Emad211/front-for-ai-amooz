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
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
      <div className="flex items-center gap-3">
        <div className="p-3 rounded-2xl bg-primary/10">
          <Bell className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">اعلان‌ها</h1>
          <p className="text-sm text-muted-foreground">
            {unreadCount > 0 ? `${unreadCount} اعلان خوانده نشده` : 'همه اعلان‌ها خوانده شده‌اند'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Select value={filter} onValueChange={onFilterChange}>
          <SelectTrigger className="w-[140px] rounded-xl">
            <Filter className="w-4 h-4 me-2" />
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
            className="rounded-xl gap-2"
          >
            <CheckCheck className="w-4 h-4" />
            <span className="hidden sm:inline">خواندن همه</span>
          </Button>
        )}
      </div>
    </div>
  );
}
