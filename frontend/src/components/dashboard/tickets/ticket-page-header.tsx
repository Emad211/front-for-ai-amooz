'use client';

import { Plus, Ticket } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface TicketPageHeaderProps {
  onNewTicket: () => void;
}

export function TicketPageHeader({ onNewTicket }: TicketPageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 mb-4 sm:mb-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 sm:p-3 rounded-xl sm:rounded-2xl bg-primary/10">
            <Ticket className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-foreground">تیکت‌های پشتیبانی</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">مشاهده و مدیریت درخواست‌های شما</p>
          </div>
        </div>

        <Button onClick={onNewTicket} className="rounded-xl gap-2 h-9 sm:h-10 text-xs sm:text-sm px-3 sm:px-4">
          <Plus className="w-4 h-4" />
          <span className="hidden xs:inline">تیکت جدید</span>
          <span className="xs:hidden">جدید</span>
        </Button>
      </div>
    </div>
  );
}
