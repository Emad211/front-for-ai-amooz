'use client';

import { Ticket, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface AdminTicketHeaderProps {
  totalCount: number;
  openCount: number;
  searchTerm: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
}

export function AdminTicketHeader({
  totalCount,
  openCount,
  searchTerm,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
}: AdminTicketHeaderProps) {
  return (
    <div className="space-y-3 sm:space-y-4 mb-4 sm:mb-6">
      <div className="flex items-center gap-3">
        <div className="p-2.5 sm:p-3 rounded-xl sm:rounded-2xl bg-primary/10">
          <Ticket className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-foreground">مدیریت تیکت‌ها</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">
            {totalCount} تیکت • {openCount} باز
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
        <div className="relative flex-1">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="جستجو در تیکت‌ها..."
            className="ps-10 rounded-xl h-9 sm:h-10 text-sm"
          />
        </div>
        <Select value={statusFilter} onValueChange={onStatusFilterChange}>
          <SelectTrigger className="w-full sm:w-[160px] rounded-xl h-9 sm:h-10 text-xs sm:text-sm">
            <SelectValue placeholder="وضعیت" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">همه وضعیت‌ها</SelectItem>
            <SelectItem value="open">باز</SelectItem>
            <SelectItem value="pending">در انتظار پاسخ</SelectItem>
            <SelectItem value="answered">پاسخ داده شده</SelectItem>
            <SelectItem value="closed">بسته شده</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
